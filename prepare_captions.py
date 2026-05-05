"""Deterministic prep step before LLM caption rewriting.

Reads:  data/unified_dataset.csv
Writes: data/captions_prepared.csv
        data/captions_prep_report.txt

Each output row corresponds to one (image, attribute, panelist) caption that
survived filtering. We do NOT rephrase here — that is the LLM step. We only:

  * drop rows with no usable comment text
  * drop rows whose comment is a meta-note (not describing the cheese)
  * normalize whitespace / Unicode / non-breaking spaces
  * keep `caption_raw` (post-normalize) verbatim alongside the original

The cleaned text becomes the input to the LLM rewrite pass.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese")
SRC = ROOT / "data" / "unified_dataset.csv"
OUT_CSV = ROOT / "data" / "captions_prepared.csv"
OUT_REPORT = ROOT / "data" / "captions_prep_report.txt"

# Meta-comment patterns: phrases panelists used to talk about *grading*
# rather than describing the cheese. Tune as we inspect output.
META_PATTERNS = [
    re.compile(r"^\s*n[/.]?a\s*$", re.IGNORECASE),
    re.compile(r"non\s+penaliz", re.IGNORECASE),
    re.compile(r"non\s+valuto", re.IGNORECASE),
    re.compile(r"^\s*-+\s*$"),
    re.compile(r"^\s*[\.\,;:\*]+\s*$"),
]

WS_RE = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\xa0", " ").replace("​", "")
    s = s.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    s = WS_RE.sub(" ", s).strip()
    # strip stray surrounding quotes/punct that aren't sentence-final
    s = s.strip(" \t\"'`")
    return s


def is_meta(s: str) -> bool:
    return any(p.search(s) for p in META_PATTERNS)


def main():
    rows_in = 0
    rows_out = 0
    drop_empty = 0
    drop_meta = 0
    drop_short = 0
    by_attr: Counter[str] = Counter()
    len_chars: dict[str, list[int]] = defaultdict(list)
    len_tokens: dict[str, list[int]] = defaultdict(list)
    samples: dict[str, list[tuple[str, str]]] = defaultdict(list)
    token_freq: dict[str, Counter[str]] = defaultdict(Counter)

    with SRC.open() as fin, OUT_CSV.open("w", newline="") as fout:
        reader = csv.DictReader(fin)
        out_cols = [
            "row_id",
            "image_path_flat",
            "image_path",
            "attribute",
            "caption_raw",
            "caption_norm",
            "panelist",
            "session_date",
            "year_folder",
            "session_num",
            "bimester",
            "view",
            "panel_slot",
            "panel_replicate",
            "dairy_id",
            "product_code",
        ]
        writer = csv.DictWriter(fout, fieldnames=out_cols)
        writer.writeheader()

        for i, row in enumerate(reader):
            rows_in += 1
            raw = (row.get("comment") or "").strip()
            if not raw:
                drop_empty += 1
                continue
            norm = normalize_text(raw)
            if not norm:
                drop_empty += 1
                continue
            if is_meta(norm):
                drop_meta += 1
                continue
            # drop pure punctuation / single-char garbage
            if len(re.sub(r"[^\w]", "", norm, flags=re.UNICODE)) < 2:
                drop_short += 1
                continue

            attr = row["attribute"]
            by_attr[attr] += 1
            len_chars[attr].append(len(norm))
            tokens = norm.lower().split()
            len_tokens[attr].append(len(tokens))
            for t in tokens:
                t2 = re.sub(r"[^\wàèéìòù]", "", t, flags=re.UNICODE)
                if t2:
                    token_freq[attr][t2] += 1
            if len(samples[attr]) < 8:
                samples[attr].append((raw, norm))

            writer.writerow({
                "row_id": i,
                "image_path_flat": row["image_path_flat"],
                "image_path": row["image_path"],
                "attribute": attr,
                "caption_raw": raw,
                "caption_norm": norm,
                "panelist": row["panelist"],
                "session_date": row["session_date"],
                "year_folder": row["year_folder"],
                "session_num": row["session_num"],
                "bimester": row["bimester"],
                "view": row["view"],
                "panel_slot": row["panel_slot"],
                "panel_replicate": row["panel_replicate"],
                "dairy_id": row["dairy_id"],
                "product_code": row["product_code"],
            })
            rows_out += 1

    # report
    def pct(n, d):
        return f"{100 * n / d:.1f}%" if d else "0.0%"

    def stats(xs):
        if not xs:
            return "n=0"
        s = sorted(xs)
        n = len(s)
        return f"n={n} min={s[0]} p25={s[n // 4]} med={s[n // 2]} p75={s[3 * n // 4]} max={s[-1]} mean={sum(s) / n:.1f}"

    lines = []
    lines.append(f"input rows  : {rows_in}")
    lines.append(f"output rows : {rows_out}  ({pct(rows_out, rows_in)})")
    lines.append(f"dropped empty/null  : {drop_empty}")
    lines.append(f"dropped meta-notes  : {drop_meta}")
    lines.append(f"dropped too-short   : {drop_short}")
    lines.append("")
    lines.append("per-attribute counts:")
    for a, n in sorted(by_attr.items(), key=lambda x: -x[1]):
        lines.append(f"  {a:30s} {n:6d}")
    lines.append("")
    lines.append("length stats (chars) per attribute:")
    for a in sorted(by_attr):
        lines.append(f"  {a:30s} {stats(len_chars[a])}")
    lines.append("")
    lines.append("length stats (tokens) per attribute:")
    for a in sorted(by_attr):
        lines.append(f"  {a:30s} {stats(len_tokens[a])}")
    lines.append("")
    lines.append("top 25 tokens per attribute (lowercased, alpha-only):")
    STOP = {
        "di", "e", "la", "il", "un", "una", "con", "in", "a", "al", "ai", "del",
        "della", "dei", "delle", "che", "non", "ma", "ed", "lo", "le", "da",
        "su", "per", "si", "è", "ha", "i", "o", "anche", "molto", "poco",
        "più", "meno", "alla", "alle", "allo", "agli", "dal", "dalla",
    }
    for a in sorted(by_attr):
        toks = [(t, c) for t, c in token_freq[a].most_common(60) if t not in STOP][:25]
        lines.append(f"  {a}:")
        for t, c in toks:
            lines.append(f"    {c:5d}  {t}")
    lines.append("")
    lines.append("samples per attribute (raw -> normalized):")
    for a in sorted(by_attr):
        lines.append(f"  --- {a} ---")
        for raw, nor in samples[a]:
            lines.append(f"    raw : {raw[:160]!r}")
            lines.append(f"    norm: {nor[:160]!r}")

    OUT_REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {OUT_CSV}")
    print(f"wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
