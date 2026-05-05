"""Bridge our cleaned captions to the training pipeline format.

Reads:  data/final/captions_final.csv
Writes: data/final/dataset_captioning.csv  — one row per (sample, panelist, attribute)
        data/final/splits.json               — train/val/test by sample_id, stratified by year

Schema produced for the training pipeline:
    sample_id, attribute, caption, caption_sentence,
    panelist, dairy_id, product_code, year, session_date,
    fetta_path, grana_path, has_fetta, has_grana, has_both_views,
    weight, classe

Where:
- sample_id = "<dairy_id>__<session_date>__P<panel_slot><panel_replicate>"
  (one wheel-photo position per session)
- fetta_path / grana_path are absolute project-relative image paths
- has_fetta/has_grana/has_both_views are booleans for training-time filtering
- weight defaults to 1.0
- classe = "OK" (we already filtered NON_DESCRITTO upstream)
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "final" / "captions_final.csv"
OUT_CSV = ROOT / "data" / "final" / "dataset_captioning.csv"
OUT_SPLITS = ROOT / "data" / "final" / "splits.json"


def make_sample_id(row: dict) -> str:
    """One wheel-photo position per session — paired fetta+grana share this id."""
    parts = [
        row["dairy_id"] or "",
        row["session_date"] or "",
        f"P{row['panel_slot'] or ''}{row['panel_replicate'] or ''}",
    ]
    return "__".join(parts).strip("_") or "unknown"


def main() -> None:
    rows = list(csv.DictReader(SRC.open()))
    print(f"loaded {len(rows)} rows from {SRC.relative_to(ROOT)}")

    # 1. Group rows by sample (one wheel-photo position).
    #    For each sample, collect Fetta and Grana image paths + the caption-rows
    #    indexed by (panelist, attribute).
    samples: dict[str, dict] = {}
    for r in rows:
        sid = make_sample_id(r)
        if sid not in samples:
            samples[sid] = {
                "sample_id": sid,
                "year": r["year_folder"],
                "session_date": r["session_date"],
                "dairy_id": r["dairy_id"],
                "product_code": r["product_code"],
                "fetta_path": "",
                "grana_path": "",
                "captions": {},  # (panelist, attribute) -> caption row
            }
        s = samples[sid]
        if r["view"] == "Fetta" and not s["fetta_path"]:
            s["fetta_path"] = r["image_path_flat"]
        elif r["view"] == "Grana" and not s["grana_path"]:
            s["grana_path"] = r["image_path_flat"]

        key = (r["panelist"], r["attribute"])
        if key not in s["captions"]:
            s["captions"][key] = r

    # 2. Emit one training row per (sample, panelist, attribute) where we have
    #    at least one image and a caption.
    out_rows = []
    n_both = n_fetta_only = n_grana_only = 0
    for sid, s in samples.items():
        has_fetta = bool(s["fetta_path"])
        has_grana = bool(s["grana_path"])
        if not (has_fetta or has_grana):
            continue
        has_both = has_fetta and has_grana
        if has_both:
            n_both += 1
        elif has_fetta:
            n_fetta_only += 1
        elif has_grana:
            n_grana_only += 1

        for (panelist, attribute), r in s["captions"].items():
            out_rows.append({
                "sample_id": sid,
                "attribute": attribute,
                "caption": r["caption"],
                "caption_sentence": r["caption_sentence"],
                "panelist": panelist,
                "dairy_id": s["dairy_id"],
                "product_code": s["product_code"],
                "year": s["year"],
                "session_date": s["session_date"],
                "fetta_path": s["fetta_path"],
                "grana_path": s["grana_path"],
                "has_fetta": has_fetta,
                "has_grana": has_grana,
                "has_both_views": has_both,
                "weight": "1.0",
                "classe": "OK",
            })

    cols = list(out_rows[0].keys())
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"wrote {OUT_CSV.relative_to(ROOT)}  ({len(out_rows)} training rows)")
    print(f"  unique samples: {len(samples)}  "
          f"(both: {n_both}, fetta-only: {n_fetta_only}, grana-only: {n_grana_only})")

    # 3. Generate stratified splits by year.
    rng_seed = 42
    train_ratio, val_ratio = 0.70, 0.15

    # Use only samples with both views for splits — the rare fetta/grana-only
    # samples are training-only via the dataset's zero-tensor fallback.
    sample_year: dict[str, str] = {}
    for s in samples.values():
        if s["fetta_path"] and s["grana_path"]:
            year = (s["year"] or "unknown").strip()
            sample_year[s["sample_id"]] = year

    import random
    rng = random.Random(rng_seed)
    by_year: dict[str, list[str]] = defaultdict(list)
    for sid, year in sample_year.items():
        by_year[year].append(sid)

    train_ids: list[str] = []
    val_ids: list[str] = []
    test_ids: list[str] = []
    for year, ids in by_year.items():
        ids = sorted(ids)
        rng.shuffle(ids)
        n = len(ids)
        n_train = max(1, int(n * train_ratio))
        n_val = int(n * val_ratio)
        train_ids.extend(ids[:n_train])
        val_ids.extend(ids[n_train: n_train + n_val])
        test_ids.extend(ids[n_train + n_val:])

    splits = {"train": train_ids, "val": val_ids, "test": test_ids}
    OUT_SPLITS.write_text(json.dumps(splits, indent=2, ensure_ascii=False))
    print(f"wrote {OUT_SPLITS.relative_to(ROOT)}  "
          f"(train={len(train_ids)}, val={len(val_ids)}, test={len(test_ids)})")


if __name__ == "__main__":
    main()
