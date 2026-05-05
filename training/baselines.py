# src/models/baselines.py
"""
Baseline evaluation functions for Grana Trentino image captioning.

Four baselines:
  1. random_baseline          — random training caption per test row
  2. most_frequent_baseline   — always the most common training caption
  3. frequency_weighted_baseline — sample captions weighted by frequency
  4. retrieval_baseline       — nearest-neighbor by ResNet-50 visual features
                                (excludes same sample_id to avoid panelist leak)

All return (preds, refs) as plain string lists, same format as full_eval().
Use compute_baseline_metrics() to score them.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms

PROJECT_ROOT = Path(__file__).parents[2]

IMAGENET_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def _normalise_caption(text: str, tokenizer) -> str:
    """Round-trip through tokenizer to match text normalisation used by models."""
    ids = tokenizer.encode(str(text), add_special=False)
    return tokenizer.decode(ids, skip_special=True)


def _filter_df(df: pd.DataFrame, attributo: str | None) -> pd.DataFrame:
    if attributo is not None:
        df = df[df["attribute"] == attributo]
    return df.copy()


# ---------------------------------------------------------------------------
# 1. Random baseline
# ---------------------------------------------------------------------------

def random_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    attributo: str | None,
    tokenizer,
    seed: int = 42,
) -> tuple[list[str], list[str]]:
    """For each test row, randomly pick a training caption."""
    train = _filter_df(train_df, attributo)
    test = _filter_df(test_df, attributo)
    rng = np.random.default_rng(seed)
    train_caps = train["caption"].tolist()
    preds = [_normalise_caption(train_caps[i], tokenizer)
             for i in rng.integers(0, len(train_caps), size=len(test))]
    refs = [_normalise_caption(r, tokenizer) for r in test["caption"].tolist()]
    return preds, refs


# ---------------------------------------------------------------------------
# 2. Most-frequent baseline
# ---------------------------------------------------------------------------

def most_frequent_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    attributo: str | None,
    tokenizer,
) -> tuple[list[str], list[str]]:
    """Always predict the most common training caption."""
    train = _filter_df(train_df, attributo)
    test = _filter_df(test_df, attributo)
    most_freq = train["caption"].value_counts().index[0]
    pred = _normalise_caption(most_freq, tokenizer)
    preds = [pred] * len(test)
    refs = [_normalise_caption(r, tokenizer) for r in test["caption"].tolist()]
    return preds, refs


# ---------------------------------------------------------------------------
# 3. Frequency-weighted sampling baseline
# ---------------------------------------------------------------------------

def frequency_weighted_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    attributo: str | None,
    tokenizer,
    seed: int = 42,
) -> tuple[list[str], list[str]]:
    """Sample complete training captions weighted by frequency.

    Unlike most_frequent (always the same caption) or random (uniform),
    this samples proportionally to how often each caption appears.
    Tests whether models use visual information or just exploit language priors.
    """
    train = _filter_df(train_df, attributo)
    test = _filter_df(test_df, attributo)
    rng = np.random.default_rng(seed)

    counts = train["caption"].value_counts()
    captions = counts.index.tolist()
    weights = counts.values.astype(float)
    weights /= weights.sum()

    chosen = rng.choice(captions, size=len(test), p=weights)
    preds = [_normalise_caption(c, tokenizer) for c in chosen]
    refs = [_normalise_caption(r, tokenizer) for r in test["caption"].tolist()]
    return preds, refs


# ---------------------------------------------------------------------------
# 4. Nearest-neighbor retrieval baseline
# ---------------------------------------------------------------------------

def _load_image_tensor(rel_path: str) -> torch.Tensor:
    full_path = PROJECT_ROOT / rel_path
    img = Image.open(full_path).convert("RGB")
    return IMAGENET_TRANSFORM(img)


def _extract_features(
    df: pd.DataFrame,
    backbone: torch.nn.Module,
    device: torch.device,
    batch_size: int = 32,
) -> torch.Tensor:
    """Extract (N, 4096) feature vectors: fetta + grana concatenated."""
    backbone.eval()
    all_feats = []
    rows = df.reset_index(drop=True)

    for start in range(0, len(rows), batch_size):
        batch_rows = rows.iloc[start: start + batch_size]
        fette, grane = [], []
        for _, row in batch_rows.iterrows():
            fette.append(_load_image_tensor(row["fetta_path"]))
            grana_path = row.get("grana_path")
            if pd.notna(grana_path):
                grane.append(_load_image_tensor(grana_path))
            else:
                grane.append(torch.zeros(3, 224, 224))

        fette_t = torch.stack(fette).to(device)   # (B, 3, 224, 224)
        grane_t = torch.stack(grane).to(device)

        with torch.no_grad():
            f = backbone(fette_t).flatten(1)   # (B, 2048)
            g = backbone(grane_t).flatten(1)   # (B, 2048)

        feats = torch.cat([f, g], dim=1)       # (B, 4096)
        all_feats.append(feats.cpu())

    return torch.cat(all_feats, dim=0)  # (N, 4096)


def retrieval_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    attributo: str | None,
    tokenizer,
    device: torch.device,
) -> tuple[list[str], list[str]]:
    """For each test image, find the nearest training image (cosine similarity)
    and copy its caption.

    Critical: excludes training rows with the same sample_id as the test row
    to avoid panelist leakage (same cheese, different annotator).
    """
    train = _filter_df(train_df, attributo).reset_index(drop=True)
    test = _filter_df(test_df, attributo).reset_index(drop=True)

    # Build frozen ResNet-50 backbone (up to avgpool, same as CNNEncoderGlobal)
    resnet = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    backbone = torch.nn.Sequential(*list(resnet.children())[:-1])
    backbone = backbone.to(device)
    for p in backbone.parameters():
        p.requires_grad = False

    print("  Extracting train features...")
    train_feats = _extract_features(train, backbone, device)  # (N_train, 4096)
    print("  Extracting test features...")
    test_feats = _extract_features(test, backbone, device)    # (N_test, 4096)

    # Normalise for cosine similarity
    train_norm = F.normalize(train_feats, dim=1)
    test_norm = F.normalize(test_feats, dim=1)

    train_sample_ids = train["sample_id"].tolist()
    train_captions = train["caption"].tolist()

    preds, refs = [], []
    for i, (_, test_row) in enumerate(test.iterrows()):
        test_sid = test_row["sample_id"]

        # Mask out same sample_id (panelist leak)
        mask = torch.tensor(
            [sid != test_sid for sid in train_sample_ids], dtype=torch.bool
        )
        if not mask.any():
            # Fallback: no same-sid restriction (shouldn't happen)
            mask = torch.ones(len(train_sample_ids), dtype=torch.bool)

        sims = (test_norm[i] @ train_norm.T)  # (N_train,)
        sims[~mask] = -1.0                    # exclude same sample_id
        best_idx = sims.argmax().item()

        pred = _normalise_caption(train_captions[best_idx], tokenizer)
        ref = _normalise_caption(str(test_row["caption"]), tokenizer)
        preds.append(pred)
        refs.append(ref)

    return preds, refs


# ---------------------------------------------------------------------------
# Metric computation (mirrors full_eval in metrics.py)
# ---------------------------------------------------------------------------

def compute_baseline_metrics(
    preds: list[str],
    refs: list[str],
    predictions_path: Path | None = None,
) -> dict[str, float]:
    """Compute BLEU-1/4, METEOR, ROUGE-L. Optionally save predictions.csv."""
    import evaluate as hf_evaluate

    refs_for_bleu = [[r] for r in refs]
    results: dict[str, float] = {}

    try:
        b = hf_evaluate.load("bleu", module_type="metric").compute(
            predictions=preds, references=refs_for_bleu
        )
        results["bleu4"] = round(float(b.get("bleu", 0.0)), 4)
        precisions = b.get("precisions", [0.0, 0.0, 0.0, 0.0])
        results["bleu1"] = round(float(precisions[0]) if precisions else 0.0, 4)
    except Exception:
        results["bleu1"] = results["bleu4"] = 0.0

    try:
        m = hf_evaluate.load("meteor", module_type="metric").compute(
            predictions=preds, references=refs
        )
        results["meteor"] = round(float(m.get("meteor", 0.0)), 4)
    except Exception:
        results["meteor"] = 0.0

    try:
        r = hf_evaluate.load("rouge", module_type="metric").compute(
            predictions=preds, references=refs
        )
        results["rouge_l"] = round(float(r.get("rougeL", 0.0)), 4)
    except Exception:
        results["rouge_l"] = 0.0

    if predictions_path is not None:
        predictions_path = Path(predictions_path)
        predictions_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"caption_pred": preds, "caption_ref": refs}).to_csv(
            predictions_path, index=False, encoding="utf-8"
        )

    return results
