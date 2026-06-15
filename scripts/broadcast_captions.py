"""Broadcast the cleaned captions back to the full training table.

Joins captions_pre_filtered.csv (39,280 image-attribute-panelist rows)
with the per-attribute rewrites_<attribute>.csv files via the
dedup_key column. Drops rows where the cleaned caption is
NON_DESCRITTO.

Reads:
    data/captions_pre_filtered.csv     # one row per (image, panelist, attribute)
    data/rewrites_<attribute>.csv      # cleaned caption per dedup_key

Writes:
    data/captions_final.csv            # final training set
    data/captions_final_report.txt
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_FULL = ROOT / "data" / "intermediate" / "captions_pre_filtered.csv"
REWRITES_DIR = ROOT / "data" / "rewrites"
OUT_CSV = ROOT / "data" / "final" / "captions_final.csv"
OUT_REPORT = ROOT / "data" / "reports" / "captions_final_report.txt"

ATTR_FILES = {
    "Profumo": "rewrites_Profumo.csv",
    "Aroma": "rewrites_Aroma.csv",
    "Sapore": "rewrites_Sapore.csv",
    "Texture": "rewrites_Texture.csv",
    "Spessore della Crosta": "rewrites_Spessore_della_Crosta.csv",
    "Struttura della Pasta": "rewrites_Struttura_della_Pasta.csv",
    "Colore della Pasta": "rewrites_Colore_della_Pasta.csv",
}


def main() -> None:
    # 1. Build dedup_key -> caption_clean lookup from per-attribute rewrites
    lookup: dict[str, str] = {}
    for attr, fname in ATTR_FILES.items():
        path = REWRITES_DIR / fname
        for r in csv.DictReader(path.open()):
            lookup[r["dedup_key"]] = r["caption_clean"]
    print(f"loaded {len(lookup)} cleaned captions across {len(ATTR_FILES)} attributes")

    # 2. Walk the full filtered table, broadcast the clean caption
    out_cols = [
        "row_id", "image_path_flat", "image_path",
        "year_folder", "session_date", "session_num", "bimester",
        "view", "panel_slot", "panel_replicate",
        "dairy_id", "product_code",
        "panelist", "attribute",
        "caption_raw", "caption_pre", "caption",
    ]

    n_in = n_out = n_dropped_nondesc = n_missing_lookup = 0
    drop_by_attr: Counter[str] = Counter()
    keep_by_attr: Counter[str] = Counter()

    with SRC_FULL.open() as fh, OUT_CSV.open("w", newline="") as out:
        reader = csv.DictReader(fh)
        writer = csv.DictWriter(out, fieldnames=out_cols)
        writer.writeheader()
        for row in reader:
            n_in += 1
            clean = lookup.get(row["dedup_key"])
            if clean is None:
                n_missing_lookup += 1
                continue
            if clean == "NON_DESCRITTO":
                n_dropped_nondesc += 1
                drop_by_attr[row["attribute"]] += 1
                continue
            writer.writerow({
                "row_id": row["row_id"],
                "image_path_flat": row["image_path_flat"],
                "image_path": row["image_path"],
                "year_folder": row["year_folder"],
                "session_date": row["session_date"],
                "session_num": row["session_num"],
                "bimester": row["bimester"],
                "view": row["view"],
                "panel_slot": row["panel_slot"],
                "panel_replicate": row["panel_replicate"],
                "dairy_id": row["dairy_id"],
                "product_code": row["product_code"],
                "panelist": row["panelist"],
                "attribute": row["attribute"],
                "caption_raw": row["caption_raw"],
                "caption_pre": row["caption_pre"],
                "caption": clean,
            })
            n_out += 1
            keep_by_attr[row["attribute"]] += 1

    # 3. Report
    lines: list[str] = []
    lines.append(f"input rows                : {n_in}")
    lines.append(f"output rows               : {n_out}  ({100 * n_out / n_in:.1f}%)")
    lines.append(f"dropped NON_DESCRITTO     : {n_dropped_nondesc}")
    lines.append(f"missing-lookup (skipped)  : {n_missing_lookup}")
    lines.append("")
    lines.append("per-attribute training rows (cleaned):")
    lines.append(f"  {'attribute':30s} {'kept':>6s} {'dropped':>8s} {'images':>8s}")
    lines.append("  " + "-" * 60)
    # also count unique images per attribute
    image_keys: dict[str, set[str]] = {}
    with OUT_CSV.open() as fh:
        for r in csv.DictReader(fh):
            image_keys.setdefault(r["attribute"], set()).add(r["image_path_flat"])

    for attr in sorted(keep_by_attr):
        kept = keep_by_attr[attr]
        dropped = drop_by_attr.get(attr, 0)
        n_images = len(image_keys.get(attr, set()))
        lines.append(f"  {attr:30s} {kept:6d} {dropped:8d} {n_images:8d}")

    OUT_REPORT.write_text("\n".join(lines) + "\n")
    print()
    print("\n".join(lines))
    print()
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
