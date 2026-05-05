"""CLI entrypoint for Trentingrana captioning models.

Usage:
    python -m training.cli --model m1 --attributo Texture
    python -m training.cli --model m2 --attributo all --epochs 50
    python -m training.cli --model m3 --attributo Profumo --eval-only
    python -m training.cli --model m1 --attributo Sapore --resume
    python -m training.cli --model m2 --attributo all --finetune

Three model variants:
    m1: ResNet-50 (global) + LSTM
    m2: ResNet-50 (spatial) + Transformer
    m3: ViT-B/16 + Transformer
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.vocabulary import ItalianTokenizer
from training.dataset import GranaTrentinoDataset
from training.models import build_model
from training.train import train_model
from training.metrics import full_eval

DATASET_CSV = ROOT / "data" / "final" / "dataset_captioning.csv"
SPLITS_JSON = ROOT / "data" / "final" / "splits.json"
MODELS_DIR = ROOT / "training" / "runs"

DEFAULTS = {
    "m1": dict(epochs=50, batch_size=32, lr=3e-4, patience=7, scheduler="steplr"),
    "m2": dict(epochs=50, batch_size=32, lr=3e-4, patience=7, scheduler="steplr"),
    "m3": dict(epochs=30, batch_size=16, lr=1e-4, patience=5, scheduler="cosine"),
}
DEFAULTS_FT = {
    "m1": dict(epochs=30, batch_size=8, lr=1e-4, patience=7, scheduler="cosine"),
    "m2": dict(epochs=30, batch_size=8, lr=1e-4, patience=7, scheduler="cosine"),
    "m3": dict(epochs=20, batch_size=4, lr=5e-5, patience=5, scheduler="cosine"),
}
MODEL_DIR_NAMES = {
    "m1": "m1_cnn_lstm",
    "m2": "m2_cnn_transformer",
    "m3": "m3_vit_transformer",
}


def parse_args():
    p = argparse.ArgumentParser(description="Trentingrana captioning")
    p.add_argument("--model", required=True, choices=["m1", "m2", "m3"])
    p.add_argument(
        "--attributo", required=True,
        help="Attribute name with underscores ('Struttura_della_Pasta', 'Texture', etc.) or 'all'",
    )
    p.add_argument("--caption-column", default="caption_sentence",
                   choices=["caption", "caption_sentence"],
                   help="Which caption form to train on (default: sentence)")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--beam-size", type=int, default=3)
    p.add_argument("--decode-strategy", choices=["beam", "nucleus"], default="nucleus")
    p.add_argument("--top-p", type=float, default=0.9)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--include-fetta-only", action="store_true")
    p.add_argument("--eval-only", action="store_true")
    p.add_argument("--finetune", action="store_true",
                   help="Unfreeze encoder for end-to-end fine-tuning with differential LR")
    return p.parse_args()


class _CollateFn:
    """Picklable collate function (compatible with multiprocessing spawn)."""

    def __init__(self, pad_id: int) -> None:
        self.pad_id = pad_id

    def __call__(self, batch):
        fette = torch.stack([b["fetta"] for b in batch])
        grana = torch.stack([b["grana"] for b in batch])
        caps = pad_sequence(
            [b["caption"] for b in batch],
            batch_first=True, padding_value=self.pad_id,
        )
        weights = torch.tensor([b["weight"] for b in batch], dtype=torch.float)
        return fette, grana, caps, weights


def make_loader(split, tokenizer, attributo, caption_column, batch_size,
                require_both_views) -> DataLoader:
    ds = GranaTrentinoDataset(
        csv_path=DATASET_CSV,
        tokenizer=tokenizer,
        splits_path=SPLITS_JSON,
        attributo=attributo,
        split=split,
        require_both_views=require_both_views,
        caption_column=caption_column,
    )
    return DataLoader(
        ds, batch_size=batch_size, shuffle=(split == "train"),
        collate_fn=_CollateFn(tokenizer.PAD_ID),
        num_workers=0 if sys.platform == "win32" else 2,
        pin_memory=True,
    )


def main():
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    if not DATASET_CSV.exists() or not SPLITS_JSON.exists():
        print(f"ERROR: missing dataset/splits files. Run:")
        print(f"  python -m training.prepare_data")
        sys.exit(1)

    attributo = None if args.attributo == "all" else args.attributo
    attr_dir = "global" if attributo is None else attributo

    defaults = (DEFAULTS_FT if args.finetune else DEFAULTS)[args.model]
    epochs = args.epochs or defaults["epochs"]
    batch_size = args.batch_size or defaults["batch_size"]
    lr = args.lr or defaults["lr"]

    suffix = "_ft" if args.finetune else ""
    run_dir = MODELS_DIR / (MODEL_DIR_NAMES[args.model] + suffix) / attr_dir

    print("Loading tokenizer (GePpeTto)...")
    tokenizer = ItalianTokenizer()

    print(f"Building model {args.model.upper()}{' [fine-tune]' if args.finetune else ''}")
    model = build_model(args.model, vocab_size=len(tokenizer), device=device)
    if args.finetune:
        model.unfreeze_encoder()
        n = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"Encoder unfrozen — trainable params: {n:,}")

    if args.eval_only:
        best_pt = run_dir / "best.pt"
        if not best_pt.exists():
            sys.exit(f"ERROR: {best_pt} not found.")
        state = torch.load(best_pt, map_location="cpu", weights_only=True)
        model.load_state_dict(state["model_state"])
        model.to(device)
        test_loader = make_loader("test", tokenizer, attributo, args.caption_column,
                                  batch_size, not args.include_fetta_only)
        results = full_eval(model, test_loader, tokenizer, device,
                            predictions_path=run_dir / "predictions.csv",
                            beam_size=args.beam_size, strategy=args.decode_strategy,
                            top_p=args.top_p, temperature=args.temperature)
        print("Test results:")
        for k, v in results.items():
            print(f"  {k}: {v:.4f}")
        return

    if (run_dir / "best.pt").exists() and not args.resume:
        ans = input(f"Run dir {run_dir} already has best.pt. Overwrite? [y/N] ")
        if ans.lower() not in ("y", "yes", "s", "si"):
            sys.exit("Aborted.")

    require_both = not args.include_fetta_only
    train_loader = make_loader("train", tokenizer, attributo, args.caption_column,
                               batch_size, require_both)
    val_loader = make_loader("val", tokenizer, attributo, args.caption_column,
                             batch_size, require_both)
    print(f"Train: {len(train_loader.dataset)}  |  Val: {len(val_loader.dataset)}")

    # Optimizer + scheduler with optional differential LR
    use_diff_lr = args.finetune or args.model == "m3"
    if use_diff_lr:
        encoder_params = [p for n, p in model.named_parameters()
                          if p.requires_grad and "encoder" in n and "proj" not in n]
        other_params = [p for n, p in model.named_parameters()
                        if p.requires_grad and ("encoder" not in n or "proj" in n)]
        optimizer = torch.optim.AdamW([
            {"params": encoder_params, "lr": lr * 0.1},
            {"params": other_params, "lr": lr},
        ])
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    else:
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    config = dict(
        model=args.model, attributo=attr_dir, epochs=epochs, batch_size=batch_size,
        lr=lr, seed=args.seed, beam_size=args.beam_size,
        decode_strategy=args.decode_strategy, top_p=args.top_p,
        temperature=args.temperature, label_smoothing=0.1,
        early_stopping_patience=defaults["patience"],
        include_fetta_only=args.include_fetta_only,
        finetune=args.finetune, caption_column=args.caption_column,
    )

    train_model(
        model=model, train_loader=train_loader, val_loader=val_loader,
        optimizer=optimizer, scheduler=scheduler, tokenizer=tokenizer,
        device=device, run_dir=run_dir, config=config, resume=args.resume,
    )

    print("\nFinal eval on test set with best.pt...")
    from training.train import load_checkpoint
    load_checkpoint(run_dir / "best.pt", model, optimizer)
    test_loader = make_loader("test", tokenizer, attributo, args.caption_column,
                              batch_size, require_both)
    results = full_eval(model, test_loader, tokenizer, device,
                        predictions_path=run_dir / "predictions.csv",
                        beam_size=args.beam_size, strategy=args.decode_strategy,
                        top_p=args.top_p, temperature=args.temperature)
    print("Test results:")
    for k, v in results.items():
        print(f"  {k}: {v:.4f}")


if __name__ == "__main__":
    main()
