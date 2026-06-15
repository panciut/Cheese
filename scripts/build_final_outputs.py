"""Build the final deliverable files from data/captions_final.csv.

Produces:
  data/final/captions_final.csv                    full table (copy)
  data/final/image_caption_attribute.csv           simple image, attribute, caption(s)
  data/final/by_attribute/<Attribute>.csv          per-attribute split (simple)
  data/final/by_attribute/<Attribute>_sentence.csv per-attribute split (sentence form)
  data/final/README.md                             explainer for the deliverable
"""

from __future__ import annotations

import csv
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data"
SRC = ROOT / "final" / "captions_final.csv"
OUT_DIR = ROOT / "final"
BY_ATTR_DIR = OUT_DIR / "by_attribute"


SIMPLE_COLS = ["image_path", "attribute", "caption", "caption_sentence"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BY_ATTR_DIR.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(SRC.open()))
    print(f"loaded {len(rows)} rows from {SRC.name}")

    # captions_final.csv already lives at data/final/ after reorganization,
    # so no copy step is needed.
    print(f"using full table at {SRC.relative_to(ROOT)}")

    # 2) Simple image -> caption table (both compact and sentence forms)
    simple_path = OUT_DIR / "image_caption_attribute.csv"
    with simple_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SIMPLE_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({
                "image_path": r["image_path_flat"],
                "attribute": r["attribute"],
                "caption": r["caption"],
                "caption_sentence": r["caption_sentence"],
            })
    print(f"wrote   -> {simple_path.relative_to(ROOT)}  ({len(rows)} rows)")

    # 3) Per-attribute splits — simple form
    by_attr: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_attr[r["attribute"]].append(r)

    counts = Counter()
    for attr, attr_rows in by_attr.items():
        slug = attr.replace(" ", "_")
        path = BY_ATTR_DIR / f"{slug}.csv"
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=SIMPLE_COLS)
            w.writeheader()
            for r in attr_rows:
                w.writerow({
                    "image_path": r["image_path_flat"],
                    "attribute": r["attribute"],
                    "caption": r["caption"],
                    "caption_sentence": r["caption_sentence"],
                })
        counts[attr] = len(attr_rows)

    # 4) README
    readme = OUT_DIR / "README.md"
    lines = [
        "# Step 1 deliverables — cleaned image-caption training data",
        "",
        "Final outputs of the data preparation pipeline described in the",
        "main `REPORT.md`. Each row is one (image, attribute, panelist)",
        "training pair with both a compact and a sentence-form caption.",
        "",
        "## Files",
        "",
        "- **`captions_final.csv`** — full table with all metadata (18 columns).",
        "  Includes panelist ID, session date, dairy code, year folder,",
        "  view (Fetta/Grana), panel slot, etc. Use this when you need",
        "  audit/traceability or to build custom train/val/test splits.",
        "",
        "- **`image_caption_attribute.csv`** — simplified 4-column table:",
        "  `image_path, attribute, caption, caption_sentence`. Use this",
        "  for plain image→caption training.",
        "",
        "- **`by_attribute/<Attribute>.csv`** — per-attribute splits of",
        "  the simplified table, one CSV per sensory attribute. Use these",
        "  when training one model per attribute.",
        "",
        "## Caption columns explained",
        "",
        "- `caption` — compact attribute-anchored form, e.g.",
        '  `"Profumo di panna."`, `"Crosta sottile."`. Direct LLM output',
        "  after manual salvage. ~4-8 words. Best for per-attribute models.",
        "",
        "- `caption_sentence` — full Italian declarative form, e.g.",
        '  `"Il formaggio ha un profumo di panna."`, `"La crosta del formaggio',
        '  è sottile."`. Deterministic regex transform from `caption` (100%',
        "  template-matched). ~7-15 words. Better for general-purpose decoders",
        "  (BLEU/METEOR/CIDEr behave better on full sentences).",
        "",
        "## Row counts",
        "",
        "| attribute | training rows |",
        "|---|---:|",
    ]
    for attr in sorted(counts):
        lines.append(f"| {attr} | {counts[attr]:,} |")
    lines.append(f"| **total** | **{sum(counts.values()):,}** |")
    lines.append("")
    lines.append("## Image paths")
    lines.append("")
    lines.append("`image_path` is project-relative, pointing into")
    lines.append("`data/images_flat/` — the deduplicated copy of the original")
    lines.append("BMP images. The flat directory is gitignored (~6 GB) but")
    lines.append("can be regenerated by re-running `build_dataset.py` over")
    lines.append("the raw `data/TrentinGrana/` tree.")
    lines.append("")
    lines.append("Multiple training rows can share the same image — the")
    lines.append("dairy-level join in the unified table broadcasts each")
    lines.append("panelist's comment to all wheel-of-the-day photographs")
    lines.append("(a/b replicates × Fetta/Grana views).")
    readme.write_text("\n".join(lines) + "\n")

    print(f"wrote   -> {readme.relative_to(ROOT)}")
    print()
    print(f"per-attribute training rows:")
    for a in sorted(counts):
        print(f"  {a:30s} {counts[a]:>6d}  -> by_attribute/{a.replace(' ','_')}.csv")
    print(f"  {'total':30s} {sum(counts.values()):>6d}")


if __name__ == "__main__":
    main()
