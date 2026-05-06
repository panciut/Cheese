"""Kaggle entrypoint — runs the full training pipeline on a Kaggle GPU kernel.

Expected Kaggle dataset layout (uploaded as `panciut/cheese-trentingrana`):
    /kaggle/input/<dataset-slug>/
        data/
            final/
                captions_final.csv
                dataset_captioning.csv   (optional — re-generated if missing)
                splits.json              (optional — re-generated if missing)
            images_flat/                  (the deduplicated image tree)

Working directory layout when this script runs:
    /kaggle/working/
        cheese/                          (this repo, copied or cloned)
            data/                        symlink to the Kaggle input
            training/                    code

Outputs (`training/runs/<model>/<attribute>/`) end up under
`/kaggle/working/cheese/training/runs/`. Kaggle will package them
in the kernel output zip.

Usage from a Kaggle notebook:

    !cp -r /kaggle/working/<copied-repo>/cheese /kaggle/working/
    !ln -s /kaggle/input/<dataset-slug>/data /kaggle/working/cheese/data
    %cd /kaggle/working/cheese
    !python -m training.kaggle_run --models m1 m2 m3 --attributo all

Or, if you prefer a notebook cell, just call `run_all()` after setting
the environment up.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def detect_paths() -> tuple[Path, Path]:
    """Return (project_root, data_root). Works on Kaggle and locally."""
    here = Path(__file__).resolve().parent.parent  # cheese/

    # If we're on Kaggle and data is symlinked, this is the same as local.
    data_root = here / "data"
    if not (data_root / "final").exists():
        # Try direct Kaggle input — find the first directory with `data/final/`
        for inp in Path("/kaggle/input").glob("*"):
            if (inp / "data" / "final").exists():
                data_root = inp / "data"
                break
            for sub in inp.rglob("data/final"):
                data_root = sub.parent
                break
    return here, data_root


def ensure_dataset(here: Path) -> None:
    """Run prepare_data if the dataset_captioning.csv / splits.json are
    missing."""
    final = here / "data" / "final"
    needed = [final / "dataset_captioning.csv", final / "splits.json"]
    if all(p.exists() for p in needed):
        print("Dataset CSV and splits already exist — skipping prepare_data.")
        return
    print("Running training.prepare_data ...")
    subprocess.run(
        [sys.executable, "-m", "training.prepare_data"],
        cwd=here, check=True,
    )


def run_one_model(here: Path, model: str, attributo: str, **overrides) -> None:
    """Run a single training job through the CLI."""
    cmd = [
        sys.executable, "-m", "training.cli",
        "--model", model,
        "--attributo", attributo,
    ]
    for k, v in overrides.items():
        if v is None:
            continue
        cmd += [f"--{k.replace('_','-')}", str(v)]
    print("\n" + "=" * 70)
    print("  ".join(cmd))
    print("=" * 70)
    sys.stdout.flush()
    subprocess.run(cmd, cwd=here, check=False)


from training.chunks import CHUNKS, list_chunks

ALL_MODELS = ["m1", "m2", "m3", "m4", "m5", "m6"]
ALL_BASELINES = ["random", "most_frequent", "freq_weighted", "retrieval"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--chunk", default=None,
        help="Run a named chunk (preferred for Kaggle session planning). "
             "Use --list-chunks to see options.",
    )
    p.add_argument(
        "--list-chunks", action="store_true",
        help="Print the predefined chunks and exit.",
    )
    p.add_argument(
        "--models", nargs="+", default=ALL_MODELS,
        choices=ALL_MODELS + ["none"],
        help="Models to train. Ignored if --chunk is set.",
    )
    p.add_argument(
        "--baselines", nargs="*", default=ALL_BASELINES,
        choices=ALL_BASELINES + ["none"],
        help="Baselines to evaluate. Default: all 4. Ignored if --chunk is set "
             "(except for chunk='baselines').",
    )
    p.add_argument(
        "--matrix", choices=["frozen", "ft", "both"], default="both",
        help="Train frozen-encoder, fine-tuned, or both. Ignored if --chunk is set.",
    )
    p.add_argument("--attributo", default="all")
    p.add_argument("--caption-column", default="caption_sentence",
                   choices=["caption", "caption_sentence"])
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--keep-last", action="store_true",
                   help="Keep last.pt checkpoints (default: deleted to save Kaggle disk)")
    args = p.parse_args()

    if args.list_chunks:
        print(list_chunks())
        return

    if args.chunk:
        if args.chunk not in CHUNKS:
            print(f"Unknown chunk: {args.chunk!r}. Available:")
            print(list_chunks())
            sys.exit(1)
        chunk = CHUNKS[args.chunk]
        args.models = chunk["models"] or ["none"]
        if chunk["modes"] == ["frozen"]:
            args.matrix = "frozen"
        elif chunk["modes"] == ["ft"]:
            args.matrix = "ft"
        elif chunk["modes"] == ["frozen", "ft"]:
            args.matrix = "both"
        else:
            args.matrix = "both"
        if chunk.get("baselines_only"):
            args.baselines = ALL_BASELINES
            args.models = ["none"]
        elif chunk.get("include_baselines"):
            args.baselines = ALL_BASELINES
        else:
            args.baselines = ["none"]
        print(f"Running chunk: {args.chunk}  ({chunk['description']})  "
              f"~{chunk['estimate_hr']:.1f}h estimated")

    here, data_root = detect_paths()
    print(f"Project root: {here}")
    print(f"Data root   : {data_root}")
    if data_root != here / "data":
        # Make the data accessible at the canonical project location.
        target = here / "data"
        if target.exists() or target.is_symlink():
            print(f"WARN: {target} already exists; not symlinking.")
        else:
            target.symlink_to(data_root)
            print(f"Symlinked {target} -> {data_root}")

    ensure_dataset(here)

    base_overrides = {
        "caption_column": args.caption_column,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
    }
    if args.keep_last:
        base_overrides["keep_last"] = ""
    base_overrides = {k: v for k, v in base_overrides.items() if v is not None}

    # Determine which passes to run (frozen / fine-tuned / both)
    if args.matrix == "frozen":
        ft_modes = [False]
    elif args.matrix == "ft":
        ft_modes = [True]
    else:
        ft_modes = [False, True]

    if args.models != ["none"]:
        print(f"\n=== TRAINED MODELS — {len(args.models)} arch × {len(ft_modes)} mode(s) "
              f"= {len(args.models) * len(ft_modes)} runs ===")
        for ft in ft_modes:
            for model in args.models:
                kwargs = dict(base_overrides)
                if ft:
                    kwargs["finetune"] = ""
                try:
                    run_one_model(here, model, args.attributo, **kwargs)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"ERROR in {model}{'-ft' if ft else ''}: {e}")

    if args.baselines and args.baselines != ["none"]:
        print(f"\n=== BASELINES — {len(args.baselines)} ===")
        cmd = [
            sys.executable, "-m", "training.run_baselines",
            "--attributo", args.attributo,
            "--caption-column", args.caption_column,
            "--baselines", *args.baselines,
        ]
        print("  ".join(cmd))
        sys.stdout.flush()
        subprocess.run(cmd, cwd=here, check=False)


if __name__ == "__main__":
    main()
