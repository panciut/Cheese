"""Pre-LLM cleanup pass: abbreviation/typo expansion + dedup.

For every row of `data/captions_prepared.csv` we apply two deterministic
fixes, then group by (caption_pre_lowercased, attribute) so the LLM rewrite
step processes each unique text once and the result is broadcast back to
all original (image, panelist, replicate, view) rows.

Outputs:
  data/captions_pre.csv      -- all 39,356 rows + caption_pre + dedup_key
  data/captions_unique.csv   -- one row per unique (caption_pre, attribute)
                                with frequency and a sample row_id, for the
                                LLM rewrite step
  data/clean_captions_report.txt

A/B replicates and Fetta/Grana views remain as separate rows in
captions_pre.csv (same caption text, different images) — dedup only
collapses for LLM cost saving, not for training data.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from build_vocabulary import ABBREV_MAP, TYPO_MAP

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese")
SRC = ROOT / "data" / "captions_prepared.csv"
OUT_FULL = ROOT / "data" / "captions_pre.csv"
OUT_UNIQUE = ROOT / "data" / "captions_unique.csv"
OUT_REPORT = ROOT / "data" / "clean_captions_report.txt"

# Strip stray markup like *fermentate*, leading/trailing punctuation noise.
ASTERISK_RE = re.compile(r"\*+")
BACKTICK_RE = re.compile(r"`+")
MULTISPACE_RE = re.compile(r"\s+")
WORD_BOUNDARY_RE = re.compile(r"\b[\w'àèéìòù]+\b", re.IGNORECASE | re.UNICODE)
TRAIL_PUNCT_RE = re.compile(r"^[\s\.\,;:\-\*`\"']+|[\s\*`\"']+$")

# Bare-number captions for Spessore della Crosta — convert to qualitative.
# Pattern matches one or more numeric tokens (possibly with comma-decimal),
# optionally interleaved with whitespace or hyphens.
BARE_NUM_TOKEN = re.compile(r"^\d+(?:[,.]\d+)?$")
NUM_TOKEN_RE = re.compile(r"\d+(?:[,.]\d+)?")

# Measurement-only Spessore captions: numbers ± mm/cm units with optional
# qualifier prefixes (Mediamente, Media, Più di, Quasi, Circa, Sotto/Sopra,
# Tra, Da, A) and connectors. We qualitatise these deterministically so the
# LLM doesn't see inconsistent mm vs cm values.
SPESSORE_FILLER_PREFIX = re.compile(
    r"^\s*(?:mediamente|media|circa|quasi|sotto|sopra|sopra a|sotto a|"
    r"più di|piu di|meno di|tra|da|a|fino a|oltre|attorno a|intorno a)\b\s*",
    re.IGNORECASE,
)
SPESSORE_NUM_UNIT_RE = re.compile(
    r"\d+(?:[,.]\d+)?\s*(?:mm|cm)?\b", re.IGNORECASE
)
SPESSORE_CONNECTOR_RE = re.compile(
    r"\s*(?:[\-/–—]|e|o|a|fino a|oltre)\s*", re.IGNORECASE
)


def _to_mm(value: float) -> float:
    """Heuristic: tiny decimals are cm (0,8 cm = 8 mm); the rest are mm."""
    return value * 10 if value < 5 else value


def _bucket(mm: float) -> str:
    if mm < 8:
        return "molto sottile"
    if mm < 10:
        return "sottile"
    if mm < 14:
        return "media"
    if mm < 18:
        return "spessa"
    return "molto spessa"


def qualitatise_spessore_bare(text: str) -> str | None:
    """Qualitatise Spessore captions that are pure measurements.

    Handles bare numbers ("10", "0,8", "9 10"), unit-suffixed numbers
    ("10 mm", "1 cm", "1,1cm"), and these forms preceded by short
    qualifiers ("Mediamente 9 mm", "Più di 1 cm", "Sotto 10mm",
    "8-10 mm"). Returns the qualitative bucket label, or None when
    the caption has any non-measurement descriptor that the LLM should
    rewrite.
    """
    if not text:
        return None
    s = text.strip()
    # strip a leading qualifier prefix (we keep the bucket label only —
    # "Mediamente 10 mm" → "Media", since that's the same information)
    s = SPESSORE_FILLER_PREFIX.sub("", s)

    # walk through, expecting alternating number(unit) and connectors.
    # if anything other than these tokens remains, bail out.
    pos = 0
    values_mm: list[float] = []
    while pos < len(s):
        # eat optional connector
        m = SPESSORE_CONNECTOR_RE.match(s, pos)
        if m and m.end() > pos:
            pos = m.end()
            if pos >= len(s):
                break
        # try a number
        m = SPESSORE_NUM_UNIT_RE.match(s, pos)
        if not m or m.end() == pos:
            return None  # found something that isn't a number
        token = m.group(0)
        # parse number + unit
        num_match = re.match(r"^(\d+(?:[,.]\d+)?)\s*(mm|cm)?", token, re.IGNORECASE)
        if not num_match:
            return None
        val = float(num_match.group(1).replace(",", "."))
        unit = (num_match.group(2) or "").lower()
        if unit == "cm":
            mm = val * 10
        elif unit == "mm":
            mm = val
        else:
            mm = _to_mm(val)
        values_mm.append(mm)
        pos = m.end()
        # eat trailing whitespace
        while pos < len(s) and s[pos] in " \t":
            pos += 1

    if not values_mm:
        return None
    avg = sum(values_mm) / len(values_mm)
    return _bucket(avg).capitalize()


def expand_word(w: str) -> str:
    """Return the canonical form for a word if it's a known abbrev/typo,
    preserving original first-letter casing."""
    lo = w.lower()
    if lo in ABBREV_MAP:
        target = ABBREV_MAP[lo]
        return target.capitalize() if w[:1].isupper() else target
    if lo in TYPO_MAP:
        target = TYPO_MAP[lo]
        return target.capitalize() if w[:1].isupper() else target
    # apostrophe-truncated -ità family that survives in mid-sentence
    if lo.endswith("it'") and len(lo) > 4:
        target = lo[:-1] + "à"
        return target.capitalize() if w[:1].isupper() else target
    return w


def preprocess(text: str, attribute: str = "") -> str:
    s = unicodedata.normalize("NFC", text)
    s = ASTERISK_RE.sub("", s)
    s = BACKTICK_RE.sub("", s)
    # apply abbrev/typo expansion word-by-word (preserves spacing/punctuation)
    s = WORD_BOUNDARY_RE.sub(lambda m: expand_word(m.group(0)), s)
    s = MULTISPACE_RE.sub(" ", s)
    s = TRAIL_PUNCT_RE.sub("", s)
    s = s.strip()
    # Spessore della Crosta only: bare numeric crust thickness -> qualitative
    if attribute == "Spessore della Crosta":
        q = qualitatise_spessore_bare(s)
        if q is not None:
            s = q
    return s


def dedup_key(caption_pre: str, attribute: str) -> str:
    """Key for grouping identical pre-cleaned captions per attribute.

    Lowercased + punctuation-folded so trivially different surface forms
    collapse for the LLM step (the original-cased caption_pre is what we
    actually send)."""
    s = caption_pre.lower()
    s = re.sub(r"[\.\,;:!\?\-]+", " ", s)
    s = MULTISPACE_RE.sub(" ", s).strip()
    return f"{attribute}::{s}"


def main():
    rows: list[dict] = []
    n_changed = 0

    with SRC.open() as fh:
        reader = csv.DictReader(fh)
        in_cols = reader.fieldnames or []
        for row in reader:
            pre = preprocess(row["caption_norm"], row["attribute"])
            if pre != row["caption_norm"]:
                n_changed += 1
            row["caption_pre"] = pre
            row["dedup_key"] = dedup_key(pre, row["attribute"])
            rows.append(row)

    # full output (39,356 rows)
    out_cols = list(in_cols) + ["caption_pre", "dedup_key"]
    with OUT_FULL.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # group by dedup_key
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["dedup_key"]].append(r)

    # write unique file
    with OUT_UNIQUE.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["dedup_key", "attribute", "caption_pre", "frequency", "sample_row_id"],
        )
        w.writeheader()
        for key, members in groups.items():
            r0 = members[0]
            w.writerow({
                "dedup_key": key,
                "attribute": r0["attribute"],
                "caption_pre": r0["caption_pre"],
                "frequency": len(members),
                "sample_row_id": r0["row_id"],
            })

    # report
    by_attr_total: Counter[str] = Counter()
    by_attr_unique: Counter[str] = Counter()
    for r in rows:
        by_attr_total[r["attribute"]] += 1
    for key, members in groups.items():
        by_attr_unique[members[0]["attribute"]] += 1

    freq_counts = Counter(len(m) for m in groups.values())
    top_repeats = sorted(
        ((len(m), m[0]["attribute"], m[0]["caption_pre"]) for m in groups.values()),
        reverse=True,
    )[:25]

    lines = [
        f"input rows               : {len(rows)}",
        f"unique (caption_pre, attr): {len(groups)}",
        f"compression ratio         : {len(rows) / len(groups):.2f}x  "
        f"({100 - 100 * len(groups) / len(rows):.1f}% saving)",
        f"rows changed by preprocess: {n_changed}  "
        f"({100 * n_changed / len(rows):.1f}%)",
        "",
        "per-attribute totals vs unique:",
    ]
    for a in sorted(by_attr_total):
        t = by_attr_total[a]
        u = by_attr_unique[a]
        lines.append(f"  {a:30s} total={t:6d}  unique={u:5d}  "
                     f"({100 - 100 * u / t:.1f}% saving)")

    lines.append("")
    lines.append("frequency distribution (how many captions appear N times):")
    for n in sorted(freq_counts):
        lines.append(f"  appearing {n:4d}x : {freq_counts[n]:5d} unique captions")

    lines.append("")
    lines.append("top 25 most-broadcast captions (LLM only sees these once):")
    for n, attr, txt in top_repeats:
        lines.append(f"  {n:4d}x  [{attr[:18]:18s}] {txt[:90]}")

    OUT_REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {OUT_FULL}")
    print(f"wrote {OUT_UNIQUE}")
    print(f"wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
