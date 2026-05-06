# src/models/train.py
from __future__ import annotations
import csv
import json
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    pad_id: int,
    device: torch.device,
) -> float:
    """Teacher-forcing training. Restituisce la loss media sull'epoca."""
    model.train()
    criterion = nn.CrossEntropyLoss(ignore_index=pad_id, reduction="none",
                                     label_smoothing=0.1)
    total_loss, total_weight = 0.0, 0.0

    for batch in tqdm(loader, leave=False, desc="train"):
        fetta, grana, caps, weights = [b.to(device) for b in batch]
        # Input: tutti i token tranne l'ultimo; target: tutti tranne il primo
        inp = caps[:, :-1]
        tgt = caps[:, 1:]
        logits = model(fetta, grana, inp)                    # (B, T-1, vocab)
        B, T, V = logits.shape
        loss_per_token = criterion(logits.reshape(B * T, V), tgt.reshape(B * T))
        loss_per_sample = loss_per_token.reshape(B, T).mean(dim=1)  # (B,)
        weighted_loss = (loss_per_sample * weights).sum()
        optimizer.zero_grad()
        weighted_loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()
        total_loss += weighted_loss.item()
        total_weight += weights.sum().item()

    return total_loss / max(total_weight, 1.0)


def evaluate_epoch(
    model: nn.Module,
    loader: DataLoader,
    pad_id: int,
    device: torch.device,
) -> dict[str, float]:
    """Calcola la val_loss. BLEU-4 aggiunto solo da quick_eval (più lento)."""
    model.eval()
    criterion = nn.CrossEntropyLoss(ignore_index=pad_id)
    total_loss, n_batches = 0.0, 0

    with torch.no_grad():
        for batch in loader:
            fetta, grana, caps, _weights = [b.to(device) for b in batch]
            inp = caps[:, :-1]
            tgt = caps[:, 1:]
            logits = model(fetta, grana, inp)
            B, T, V = logits.shape
            loss = criterion(logits.reshape(B * T, V), tgt.reshape(B * T))
            total_loss += loss.item()
            n_batches += 1

    return {"val_loss": total_loss / max(n_batches, 1)}


def cleanup_checkpoints(run_dir: Path, keep_last: bool = False) -> None:
    """Delete `last.pt` after a successful run unless asked to keep it.

    `last.pt` is only needed for resuming an *interrupted* training. Once
    training completes successfully, only `best.pt` is needed. Deleting
    `last.pt` halves the per-run disk footprint — important on Kaggle's
    ~20 GB /kaggle/working/ budget.
    """
    last = run_dir / "last.pt"
    if not keep_last and last.exists():
        last.unlink()


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_loss: float,
    run_dir: Path,
    is_best: bool,
) -> None:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "epoch": epoch,
        "val_loss": val_loss,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
    }
    torch.save(state, run_dir / "last.pt")
    if is_best:
        torch.save(state, run_dir / "best.pt")


def load_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
) -> tuple[int, float]:
    """Carica checkpoint. Restituisce (epoch, val_loss)."""
    state = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state["model_state"])
    optimizer.load_state_dict(state["optimizer_state"])
    return state["epoch"], state["val_loss"]


def append_log(
    run_dir: Path,
    epoch: int,
    train_loss: float,
    val_loss: float,
    bleu4: float,
    elapsed: float,
) -> None:
    log_path = Path(run_dir) / "log.csv"
    write_header = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["epoch", "train_loss", "val_loss", "bleu4", "elapsed_sec"]
        )
        if write_header:
            writer.writeheader()
        writer.writerow(
            dict(epoch=epoch, train_loss=round(train_loss, 6),
                 val_loss=round(val_loss, 6), bleu4=round(bleu4, 6),
                 elapsed_sec=round(elapsed, 1))
        )


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler._LRScheduler,
    tokenizer,
    device: torch.device,
    run_dir: Path,
    config: dict,
    resume: bool = False,
) -> None:
    """Loop di training completo con early stopping e checkpoint."""
    from training.metrics import quick_eval

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Salva config
    with open(run_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    start_epoch = 1
    best_val_loss = float("inf")
    patience_counter = 0
    patience = config.get("early_stopping_patience", 7)
    max_epochs = config.get("epochs", 50)
    pad_id = tokenizer.PAD_ID

    if resume and (run_dir / "last.pt").exists():
        start_epoch, best_val_loss = load_checkpoint(
            run_dir / "last.pt", model, optimizer
        )
        start_epoch += 1
        print(f"Ripreso da epoca {start_epoch}, best_val_loss={best_val_loss:.4f}")

    for epoch in range(start_epoch, max_epochs + 1):
        t0 = time.time()
        train_loss = train_one_epoch(model, train_loader, optimizer, pad_id, device)
        val_metrics = evaluate_epoch(model, val_loader, pad_id, device)
        val_loss = val_metrics["val_loss"]
        bleu4 = quick_eval(model, val_loader, tokenizer, device)
        elapsed = time.time() - t0

        is_best = val_loss < best_val_loss
        if is_best:
            best_val_loss = val_loss
            patience_counter = 0
        else:
            patience_counter += 1

        save_checkpoint(model, optimizer, epoch, val_loss, run_dir, is_best)
        append_log(run_dir, epoch, train_loss, val_loss, bleu4, elapsed)
        scheduler.step()

        print(
            f"Epoca {epoch:3d}/{max_epochs} | "
            f"train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | "
            f"BLEU-4={bleu4:.4f} | {'[BEST]' if is_best else f'patience {patience_counter}/{patience}'} | "
            f"{elapsed:.0f}s"
        )

        if patience_counter >= patience:
            print(f"Early stopping a epoca {epoch}.")
            break

    print(f"Training completato. Best val_loss: {best_val_loss:.4f}")
    print(f"Pesi migliori: {run_dir / 'best.pt'}")

    # Free disk on Kaggle: drop the per-epoch `last.pt` once training has
    # successfully ended. `best.pt` is what eval/inference need.
    if not config.get("keep_last", False):
        cleanup_checkpoints(run_dir)
