"""Run the four non-trained baselines on the test set.

Baselines:
  1. random           — random training caption per test row
  2. most_frequent    — always the most common training caption
  3. freq_weighted    — sample training captions weighted by frequency
  4. retrieval        — nearest-neighbor by ResNet-50 visual features
                        (excludes same sample_id to avoid panelist leak)

Reads:  data/final/dataset_captioning.csv, data/final/splits.json
Writes: training/runs/baselines/<baseline>/<attribute>/predictions.csv
        training/runs/baselines/<baseline>/<attribute>/metrics.json

Usage:
    python -m training.run_baselines --attributo all
    python -m training.run_baselines --attributo Texture --caption-column caption
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.vocabulary import ItalianTokenizer
from training.baselines import (
    random_baseline, most_frequent_baseline,
    frequency_weighted_baseline, retrieval_baseline,
    compute_baseline_metrics,
)

DATASET_CSV = ROOT / "data" / "final" / "dataset_captioning.csv"
SPLITS_JSON = ROOT / "data" / "final" / "splits.json"
OUT_DIR = ROOT / "training" / "runs" / "baselines"


def load_split(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATASET_CSV)
    splits = json.loads(SPLITS_JSON.read_text())
    sample_ids = set(splits[name])
    return df[df["sample_id"].isin(sample_ids)].copy()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--attributo", default="all",
                   help="Attribute name (with spaces, e.g. 'Struttura della Pasta') or 'all'")
    p.add_argument("--caption-column", default="caption_sentence",
                   choices=["caption", "caption_sentence"])
    p.add_argument("--baselines", nargs="+",
                   default=["random", "most_frequent", "freq_weighted", "retrieval"],
                   choices=["random", "most_frequent", "freq_weighted", "retrieval"])
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if not DATASET_CSV.exists() or not SPLITS_JSON.exists():
        sys.exit("ERROR: missing dataset/splits — run training.prepare_data first.")

    print(f"Loading data...")

    def _prep(name: str) -> pd.DataFrame:
        df = load_split(name)
        if args.caption_column != "caption":
            # Drop the original short `caption` column to avoid duplicate-column
            # collisions when renaming caption_sentence → caption.
            if "caption" in df.columns:
                df = df.drop(columns=["caption"])
            df = df.rename(columns={args.caption_column: "caption"})
        return df

    train_df = _prep("train")
    test_df = _prep("test")
    print(f"  train: {len(train_df)} rows  |  test: {len(test_df)} rows")

    print("Loading tokenizer...")
    tokenizer = ItalianTokenizer()

    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    attributo = None if args.attributo == "all" else args.attributo
    attr_dir = "global" if attributo is None else attributo.replace(" ", "_")

    BASELINE_FNS = {
        "random": lambda: random_baseline(train_df, test_df, attributo, tokenizer, seed=args.seed),
        "most_frequent": lambda: most_frequent_baseline(train_df, test_df, attributo, tokenizer),
        "freq_weighted": lambda: frequency_weighted_baseline(train_df, test_df, attributo, tokenizer, seed=args.seed),
        "retrieval": lambda: retrieval_baseline(train_df, test_df, attributo, tokenizer, device),
    }

    for name in args.baselines:
        print(f"\n--- baseline: {name} ---")
        try:
            preds, refs = BASELINE_FNS[name]()
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue
        out_dir = OUT_DIR / name / attr_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # write predictions.csv
        with (out_dir / "predictions.csv").open("w") as fh:
            fh.write("pred,ref\n")
            for p, r in zip(preds, refs):
                p = p.replace('"', '""')
                r = r.replace('"', '""')
                fh.write(f'"{p}","{r}"\n')

        metrics = compute_baseline_metrics(preds, refs)
        (out_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False)
        )
        print("  metrics:")
        for k, v in metrics.items():
            print(f"    {k}: {v:.4f}")
        print(f"  wrote {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
