"""
Calcola tutte le metriche di valutazione su predictions.csv scaricati da Kaggle.

Metriche:
  - BLEU-1, BLEU-4
  - METEOR
  - ROUGE-L
  - CIDEr  (implementazione standalone, niente Java)
  - BERTScore-F  (modello italiano, --no-bertscore per saltare)
  - VocabConformance  (% token nel vocabolario controllato)
  - CLIPScore  (richiede colonna 'image_path' nel CSV + --no-clipscore per saltare)

Formato CSV atteso (da full_eval in training/metrics.py):
    caption_pred, caption_ref

Colonna opzionale per CLIPScore:
    image_path   (path relativo alla root del progetto)

Uso:
    python eval_metrics/compute_metrics.py predictions_m1.csv
    python eval_metrics/compute_metrics.py pred_m1.csv pred_m3.csv pred_m6.csv
    python eval_metrics/compute_metrics.py pred_m1.csv --images-root . --no-bertscore
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Tokenizzazione condivisa
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", "", text.lower()).split()


# ---------------------------------------------------------------------------
# CIDEr (implementazione standalone — TF-IDF pesato, no Java)
# ---------------------------------------------------------------------------

def compute_cider(predictions: list[str], references: list[str], n_max: int = 4) -> float:
    """CIDEr-D: cosine similarity TF-IDF su n-gram, media su ordini 1..n_max, scala x10."""
    doc_freq: dict = defaultdict(int)
    n_docs = len(references)

    # IDF corpus-level calcolato sulle references
    for ref in references:
        tokens = _tokenize(ref)
        for n in range(1, n_max + 1):
            seen: set = set()
            for i in range(len(tokens) - n + 1):
                ng = tuple(tokens[i : i + n])
                if ng not in seen:
                    doc_freq[ng] += 1
                    seen.add(ng)

    def idf(ng: tuple) -> float:
        return math.log((n_docs + 1.0) / (doc_freq.get(ng, 0) + 1.0))

    def ngrams(tokens: list[str], n: int) -> dict:
        d: dict = defaultdict(int)
        for i in range(len(tokens) - n + 1):
            d[tuple(tokens[i : i + n])] += 1
        return d

    scores = []
    for pred, ref in zip(predictions, references):
        pred_tok = _tokenize(pred)
        ref_tok  = _tokenize(ref)
        order_scores = []

        for n in range(1, n_max + 1):
            pred_ng = ngrams(pred_tok, n)
            ref_ng  = ngrams(ref_tok, n)
            all_ng  = set(pred_ng) | set(ref_ng)

            if not all_ng:
                order_scores.append(0.0)
                continue

            pred_vec = {ng: pred_ng.get(ng, 0) * idf(ng) for ng in all_ng}
            ref_vec  = {ng: ref_ng.get(ng, 0)  * idf(ng) for ng in all_ng}

            dot       = sum(pred_vec[ng] * ref_vec[ng] for ng in all_ng)
            pred_norm = math.sqrt(sum(v ** 2 for v in pred_vec.values())) + 1e-10
            ref_norm  = math.sqrt(sum(v ** 2 for v in ref_vec.values()))  + 1e-10
            order_scores.append(dot / (pred_norm * ref_norm))

        scores.append(float(np.mean(order_scores)) * 10.0)

    return float(np.mean(scores)) if scores else 0.0


# ---------------------------------------------------------------------------
# BERTScore
# ---------------------------------------------------------------------------

def compute_bertscore(predictions: list[str], references: list[str], lang: str = "it") -> dict[str, float]:
    from bert_score import score as bs_score  # lazy import — richiede torch

    P, R, F = bs_score(predictions, references, lang=lang, verbose=False)
    return {
        "bertscore_p": float(P.mean()),
        "bertscore_r": float(R.mean()),
        "bertscore_f": float(F.mean()),
    }


# ---------------------------------------------------------------------------
# CLIPScore (multilingue via open_clip)
# ---------------------------------------------------------------------------

def compute_clipscore(
    predictions: list[str],
    image_paths: list[str],
    images_root: Path | None = None,
    model_name: str = "xlm-roberta-base-ViT-B-32",
    pretrained: str = "laion5b_s13b_b90k",
) -> float:
    import torch
    import open_clip
    from PIL import Image

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  CLIPScore: carico modello su {device} ...")
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    tokenizer = open_clip.get_tokenizer(model_name)
    model = model.to(device).eval()

    # Cache feature immagine per path: le stesse immagini si ripetono molto
    # (più panelisti/attributi per la stessa fetta) → encode una volta sola.
    img_feat_cache: dict[str, "torch.Tensor"] = {}

    def get_img_feat(full_path: Path):
        key = str(full_path)
        if key not in img_feat_cache:
            img = preprocess(Image.open(full_path).convert("RGB")).unsqueeze(0).to(device)
            with torch.no_grad():
                f = model.encode_image(img)
                f = f / f.norm(dim=-1, keepdim=True)
            img_feat_cache[key] = f
        return img_feat_cache[key]

    scores = []
    missing = 0
    for pred, img_rel in tqdm(zip(predictions, image_paths), total=len(predictions), desc="CLIPScore"):
        full_path = Path(img_rel) if images_root is None else images_root / img_rel
        if not full_path.exists():
            missing += 1
            continue
        try:
            img_feat = get_img_feat(full_path)
            txt = tokenizer([pred]).to(device)
            with torch.no_grad():
                txt_feat = model.encode_text(txt)
                txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)
                scores.append((img_feat * txt_feat).sum().item())
        except Exception as e:
            print(f"  WARNING: {full_path}: {e}")
            continue

    if missing:
        print(f"  WARNING: {missing}/{len(predictions)} immagini non trovate")
    return float(np.mean(scores)) if scores else float("nan")


# ---------------------------------------------------------------------------
# Conformità vocabolario
# ---------------------------------------------------------------------------

def load_vocab_surfaces(vocab_csv: Path) -> set[str]:
    df = pd.read_csv(vocab_csv)
    surfaces: set[str] = set()
    for cell in df["surfaces"].dropna():
        for s in str(cell).split(","):
            surfaces.add(s.strip().lower())
    return surfaces


def compute_vocab_conformance(predictions: list[str], vocab_surfaces: set[str]) -> float:
    scores = []
    for pred in predictions:
        tokens = _tokenize(pred)
        if tokens:
            scores.append(sum(t in vocab_surfaces for t in tokens) / len(tokens))
    return float(np.mean(scores)) if scores else float("nan")


# ---------------------------------------------------------------------------
# Metriche standard (BLEU / METEOR / ROUGE) via HuggingFace evaluate
# ---------------------------------------------------------------------------

def compute_standard_metrics(predictions: list[str], references: list[str]) -> dict[str, float]:
    import evaluate as hf_evaluate

    bleu_m   = hf_evaluate.load("bleu",   module_type="metric")
    meteor_m = hf_evaluate.load("meteor", module_type="metric")
    rouge_m  = hf_evaluate.load("rouge",  module_type="metric")

    refs_bleu = [[r] for r in references]
    out: dict[str, float] = {}

    try:
        b = bleu_m.compute(predictions=predictions, references=refs_bleu)
        prec = b.get("precisions", [0.0, 0.0, 0.0, 0.0])
        out["bleu1"] = round(float(prec[0]) if prec else 0.0, 4)
        out["bleu4"] = round(float(b.get("bleu", 0.0)), 4)
    except Exception:
        out["bleu1"] = out["bleu4"] = 0.0

    try:
        m = meteor_m.compute(predictions=predictions, references=references)
        out["meteor"] = round(float(m.get("meteor", 0.0)), 4)
    except Exception:
        out["meteor"] = 0.0

    try:
        r = rouge_m.compute(predictions=predictions, references=references)
        out["rouge_l"] = round(float(r.get("rougeL", 0.0)), 4)
    except Exception:
        out["rouge_l"] = 0.0

    return out


# ---------------------------------------------------------------------------
# Valuta un singolo file
# ---------------------------------------------------------------------------

def evaluate_file(
    csv_path: Path,
    vocab_surfaces: set[str] | None,
    lang: str,
    images_root: Path | None,
    skip_bertscore: bool,
    skip_clipscore: bool,
    label: str | None = None,
) -> dict:
    df = pd.read_csv(csv_path)

    # Alias colonne: alcuni CSV usano pred/ref invece di caption_pred/caption_ref
    pred_col = next((c for c in ("caption_pred", "pred") if c in df.columns), None)
    ref_col  = next((c for c in ("caption_ref", "ref") if c in df.columns), None)
    if pred_col is None or ref_col is None:
        print(f"  SKIP: {csv_path.name} non ha colonne (pred, ref) riconoscibili "
              f"(trovate: {list(df.columns)})")
        return None

    preds = df[pred_col].fillna("").tolist()
    refs  = df[ref_col].fillna("").tolist()
    n     = len(preds)

    if n == 0:
        print(f"  SKIP: {csv_path.name} è vuoto")
        return None

    label = label or csv_path.name
    print(f"\n{'='*60}")
    print(f"File: {label}  ({n} campioni)")
    print(f"{'='*60}")

    # Standard
    results = compute_standard_metrics(preds, refs)
    print(f"  BLEU-1   = {results['bleu1']:.4f}")
    print(f"  BLEU-4   = {results['bleu4']:.4f}")
    print(f"  METEOR   = {results['meteor']:.4f}")
    print(f"  ROUGE-L  = {results['rouge_l']:.4f}")

    # CIDEr
    results["cider"] = round(compute_cider(preds, refs), 4)
    print(f"  CIDEr    = {results['cider']:.4f}")

    # BERTScore
    if not skip_bertscore:
        bs = compute_bertscore(preds, refs, lang=lang)
        results.update({k: round(v, 4) for k, v in bs.items()})
        print(f"  BERTScore-P = {results['bertscore_p']:.4f}")
        print(f"  BERTScore-R = {results['bertscore_r']:.4f}")
        print(f"  BERTScore-F = {results['bertscore_f']:.4f}")
    else:
        results.update({"bertscore_p": float("nan"), "bertscore_r": float("nan"), "bertscore_f": float("nan")})

    # Conformità vocabolario
    if vocab_surfaces is not None:
        results["vocab_conf"] = round(compute_vocab_conformance(preds, vocab_surfaces), 4)
        print(f"  VocabConf  = {results['vocab_conf']:.4f}")
    else:
        results["vocab_conf"] = float("nan")

    # CLIPScore
    if not skip_clipscore:
        if "image_path" in df.columns:
            results["clip_score"] = round(
                compute_clipscore(preds, df["image_path"].tolist(), images_root=images_root), 4
            )
            print(f"  CLIPScore  = {results['clip_score']:.4f}")
        else:
            print("  CLIPScore  = N/A (aggiungi colonna 'image_path' al CSV)")
            results["clip_score"] = float("nan")
    else:
        results["clip_score"] = float("nan")

    results["file"] = label
    results["n_samples"] = n
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcola metriche di captioning su predictions.csv da Kaggle"
    )
    parser.add_argument("files", nargs="+", type=Path, metavar="PATH",
                        help="predictions.csv o cartelle (ricorsivo su predictions.csv)")
    parser.add_argument("--lang", default="it",
                        help="Lingua per BERTScore (default: it)")
    parser.add_argument("--vocab", type=Path, default=None,
                        help="Path a vocabulary.csv (default: auto-detect)")
    parser.add_argument("--images-root", type=Path, default=None,
                        help="Root per i path immagine nel CSV (default: CWD)")
    parser.add_argument("--no-bertscore", action="store_true",
                        help="Salta BERTScore (veloce, niente download BERT)")
    parser.add_argument("--no-clipscore", action="store_true",
                        help="Salta CLIPScore (niente download CLIP)")
    parser.add_argument("--out", type=Path, default=Path("metrics_summary.csv"),
                        help="File output summary (default: metrics_summary.csv)")
    args = parser.parse_args()

    # Auto-detect vocabulary.csv
    vocab_surfaces = None
    vocab_path = args.vocab
    if vocab_path is None:
        candidates = [
            Path(__file__).parent.parent / "data" / "vocabulary" / "vocabulary.csv",
            Path("data/vocabulary/vocabulary.csv"),
        ]
        for c in candidates:
            if c.exists():
                vocab_path = c
                break

    if vocab_path and vocab_path.exists():
        vocab_surfaces = load_vocab_surfaces(vocab_path)
        print(f"Vocabolario: {len(vocab_surfaces)} forme superficiali da {vocab_path}")
    else:
        print("Vocabolario: non trovato, VocabConformance saltata")
        print("  Usa --vocab path/to/vocabulary.csv per specificarlo")

    # Espande cartelle in lista di (csv_path, label)
    jobs: list[tuple[Path, str]] = []
    for f in args.files:
        if not f.exists():
            print(f"\nWARNING: {f} non trovato, saltato")
            continue
        if f.is_dir():
            found = sorted(f.rglob("predictions.csv"))
            if not found:
                print(f"\nWARNING: nessun predictions.csv in {f}")
            for csv in found:
                # Label = path relativo alla cartella passata, senza /predictions.csv
                rel = csv.relative_to(f).parent
                label = f"{f.name}/{rel}".replace("\\", "/").rstrip("/.")
                jobs.append((csv, label))
        else:
            # Label distintiva dai dir genitori (evita collisioni "predictions")
            parts = [p for p in f.parent.parts[-2:] if p not in (".", "..")]
            label = "/".join(parts) if parts else f.stem
            jobs.append((f, label))

    all_results = []
    for csv, label in jobs:
        r = evaluate_file(
            csv_path=csv,
            vocab_surfaces=vocab_surfaces,
            lang=args.lang,
            images_root=args.images_root,
            skip_bertscore=args.no_bertscore,
            skip_clipscore=args.no_clipscore,
            label=label,
        )
        if r is not None:
            all_results.append(r)

    if not all_results:
        print("\nNessun file valido trovato.")
        return

    summary = pd.DataFrame(all_results).set_index("file")
    cols_order = [
        "n_samples", "bleu1", "bleu4", "meteor", "rouge_l",
        "cider", "bertscore_f", "vocab_conf", "clip_score",
    ]
    summary = summary[[c for c in cols_order if c in summary.columns]]

    print(f"\n{'='*60}")
    print("RIEPILOGO")
    print(f"{'='*60}")
    print(summary.to_string())

    summary.to_csv(args.out)
    print(f"\nSalvato in {args.out}")


if __name__ == "__main__":
    main()
