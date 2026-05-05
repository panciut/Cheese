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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=["m1", "m2", "m3"])
    p.add_argument("--attributo", default="all")
    p.add_argument("--caption-column", default="caption_sentence",
                   choices=["caption", "caption_sentence"])
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--finetune", action="store_true")
    args = p.parse_args()

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

    overrides = {
        "caption_column": args.caption_column,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "finetune": "" if args.finetune else None,  # flag — empty string means present
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}

    for model in args.models:
        try:
            run_one_model(here, model, args.attributo, **overrides)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERROR in {model}: {e}")


if __name__ == "__main__":
    main()
