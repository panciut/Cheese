"""
Aggiunge la colonna `image_path` ai predictions.csv esistenti, ricostruendo
l'ordine del test-split dal dataset. Abilita CLIPScore offline.

Logica validata:
  - I modelli (full_eval) e i baseline iterano il test-split nello stesso ordine
    (stesso dataset_captioning.csv, stessi filtri boolean che preservano l'ordine;
    il filtro has_both_views è un no-op sul test-split).
  - Aggancio per ORDINE di riga, con gate sul conteggio: se il numero di righe
    non combacia, il file viene saltato (nessun disallineamento silenzioso).

Remap path: i CSV puntano a `data/images_flat/...` ma i file sono in
`data/data/images_flat/...` → prefisso riscritto.

Uso:
    python eval_metrics/add_image_paths.py
    python eval_metrics/add_image_paths.py --root predictions --view fetta
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATASET_CSV = ROOT / "data" / "final" / "dataset_captioning.csv"
SPLITS_JSON = ROOT / "data" / "final" / "splits.json"

# Attributi noti → nome cartella ↔ valore colonna 'attribute'
ATTR_FOLDER_TO_NAME = {
    "Aroma": "Aroma",
    "Colore_della_Pasta": "Colore della Pasta",
    "Profumo": "Profumo",
    "Sapore": "Sapore",
    "Spessore_della_Crosta": "Spessore della Crosta",
    "Struttura_della_Pasta": "Struttura della Pasta",
    "Texture": "Texture",
}


def reconstruct_test_order(attribute: str | None) -> pd.DataFrame:
    """Ricostruisce il test-split nello stesso ordine di full_eval / baselines."""
    df = pd.read_csv(DATASET_CSV)
    df = df[df["has_fetta"] | df["has_grana"]].copy()
    df = df[df["has_both_views"]].copy()
    with open(SPLITS_JSON, encoding="utf-8") as f:
        splits = json.load(f)
    df = df[df["sample_id"].isin(set(splits["test"]))].copy()
    if attribute is not None:
        df = df[df["attribute"] == attribute].copy()
    return df.reset_index(drop=True)


def remap_path(rel: str, prefix_from: str, prefix_to: str) -> str:
    rel = str(rel).replace("\\", "/")
    if rel.startswith(prefix_from):
        rel = prefix_to + rel[len(prefix_from):]
    return rel


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggiunge image_path ai predictions.csv")
    ap.add_argument("--root", type=Path, default=ROOT / "predictions",
                    help="Cartella radice dei predictions.csv")
    ap.add_argument("--view", default="fetta", choices=["fetta", "grana"],
                    help="Quale vista usare come image_path (default: fetta)")
    ap.add_argument("--prefix-from", default="data/images_flat/")
    ap.add_argument("--prefix-to", default="data/data/images_flat/")
    args = ap.parse_args()

    path_col = f"{args.view}_path"

    if not DATASET_CSV.exists() or not SPLITS_JSON.exists():
        sys.exit("ERRORE: dataset_captioning.csv o splits.json mancanti")

    # Cache delle ricostruzioni per attributo (riusate da modelli e baseline)
    cache: dict[str | None, pd.DataFrame] = {}

    def get_order(attribute: str | None) -> pd.DataFrame:
        if attribute not in cache:
            cache[attribute] = reconstruct_test_order(attribute)
        return cache[attribute]

    files = sorted(args.root.rglob("predictions.csv"))
    print(f"Trovati {len(files)} predictions.csv sotto {args.root}\n")

    n_ok = n_skip = n_missing_img = 0
    for csv_path in files:
        attr_folder = csv_path.parent.name
        rel_label = csv_path.relative_to(args.root.parent)

        if attr_folder == "global":
            attribute = None
        elif attr_folder in ATTR_FOLDER_TO_NAME:
            attribute = ATTR_FOLDER_TO_NAME[attr_folder]
        else:
            print(f"SKIP {rel_label}: cartella attributo non riconosciuta '{attr_folder}'")
            n_skip += 1
            continue

        pred_df = pd.read_csv(csv_path)
        if len(pred_df) == 0:
            print(f"SKIP {rel_label}: vuoto")
            n_skip += 1
            continue

        order = get_order(attribute)
        if len(order) != len(pred_df):
            print(f"SKIP {rel_label}: conteggio righe diverso "
                  f"(pred={len(pred_df)} vs test={len(order)}) — niente join")
            n_skip += 1
            continue

        # Validazione opzionale: per i modelli i ref combaciano con caption_sentence
        ref_col = next((c for c in ("caption_ref", "ref") if c in pred_df.columns), None)
        match_note = ""
        if ref_col is not None:
            sample_n = min(50, len(pred_df))
            matches = sum(
                str(pred_df[ref_col].iloc[i]).strip().lower()[:25]
                == str(order["caption_sentence"].iloc[i]).strip().lower()[:25]
                for i in range(sample_n)
            )
            rate = matches / sample_n
            match_note = f"ref-match {rate:.0%}"
            # I baseline normalizzano i ref → match basso è atteso, non un errore.

        image_paths = [
            remap_path(order[path_col].iloc[i], args.prefix_from, args.prefix_to)
            for i in range(len(pred_df))
        ]
        pred_df["image_path"] = image_paths

        # Controllo esistenza prima immagine
        first_full = ROOT / image_paths[0]
        if not first_full.exists():
            n_missing_img += 1
            img_note = f"  ATTENZIONE: img[0] non trovata: {image_paths[0]}"
        else:
            img_note = "img ok"

        pred_df.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"OK   {rel_label}: +image_path ({len(pred_df)} righe) [{match_note}] {img_note}")
        n_ok += 1

    print(f"\nFatto. OK={n_ok}, skip={n_skip}, file con img[0] mancante={n_missing_img}")


if __name__ == "__main__":
    main()
