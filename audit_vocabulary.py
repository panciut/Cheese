"""Sanity-check the vocabulary before drafting the rewrite prompt.

Flags:
  - pure-numeric / unit tokens (mm, cm, %, digits) → must be stripped/qualitatised
  - very short tokens still surviving (likely abbreviations: leg, legg, po, mc)
  - tokens containing digits
  - probable inflection pairs that should have merged but did not
  - probable synonym pairs (small edit distance) for manual review
  - cross-attribute lemmas (same lemma in many attributes) — informative,
    not necessarily wrong
  - the top 30 lemmas in each attribute, side-by-side, so style of each
    attribute is visible at a glance

Reads:  data/vocabulary/vocabulary.csv
Writes: data/vocabulary/_audit.txt
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data" / "vocabulary" / "vocabulary.csv"
OUT = ROOT / "data" / "vocabulary" / "_audit.txt"

UNITS = {"mm", "cm", "m", "kg", "g", "%", "°", "ml"}
KNOWN_ABBREV = {
    "leg": "leggermente",
    "legg": "leggermente",
    "po": "poco",
    "po'": "poco",
    "mc": "molto",   # speculative
    "mm": "(misura — convertire in qualitativo)",
    "cm": "(misura — convertire in qualitativo)",
}


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 2:
        return 99
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            cur = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    return dp[m]


def main():
    by_attr: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    with SRC.open() as fh:
        for r in csv.DictReader(fh):
            by_attr[r["attribute"]].append((r["lemma"], int(r["count"]), r["surfaces"]))

    # also compute global lemma -> set(attributes) for cross-attribute view
    in_attrs: dict[str, set[str]] = defaultdict(set)
    for a, rows in by_attr.items():
        for lemma, _, _ in rows:
            in_attrs[lemma].add(a)

    out: list[str] = []
    out.append("# Vocabulary audit\n")

    # ---- 1. quantitative & unit tokens ----
    out.append("## 1. Quantitative / unit tokens (must be stripped or qualitatised)\n")
    for attr in sorted(by_attr):
        flagged = []
        for lemma, c, surf in by_attr[attr]:
            if lemma in UNITS or re.fullmatch(r"\d+", lemma) or re.search(r"\d", lemma):
                flagged.append((c, lemma, surf))
        if flagged:
            out.append(f"### {attr}")
            for c, lemma, surf in flagged[:30]:
                out.append(f"  {c:6d}  {lemma:20s}  surfaces: {surf}")
            out.append("")

    # ---- 2. very short / abbreviation candidates ----
    out.append("\n## 2. Very short tokens (≤3 chars) — likely abbreviations\n")
    for attr in sorted(by_attr):
        flagged = []
        for lemma, c, surf in by_attr[attr]:
            if len(lemma) <= 3 and lemma not in UNITS and not re.search(r"\d", lemma):
                flagged.append((c, lemma, surf))
        if flagged:
            out.append(f"### {attr}")
            for c, lemma, surf in flagged[:25]:
                expand = KNOWN_ABBREV.get(lemma, "")
                tag = f"-> {expand}" if expand else ""
                out.append(f"  {c:6d}  {lemma:8s}  {tag:35s}  surfaces: {surf}")
            out.append("")

    # ---- 3. probable un-merged inflection pairs ----
    out.append("\n## 3. Probable un-merged inflection pairs (same attribute)")
    out.append("    suggests the corpus-merge heuristic missed them.\n")
    for attr in sorted(by_attr):
        rows = by_attr[attr]
        lemmas = [r[0] for r in rows]
        c_by = {l: c for l, c, _ in rows}
        seen: set[tuple[str, str]] = set()
        flags: list[tuple[int, str, str]] = []
        lemset = set(lemmas)
        for l in lemmas:
            for cand in (
                l + "i", l + "e", l + "o", l + "a",
                l[:-1] + "o" if l.endswith(("a", "e", "i")) else None,
                l[:-1] + "a" if l.endswith(("o", "e", "i")) else None,
                l[:-1] + "e" if l.endswith(("a", "o", "i")) else None,
                l[:-1] + "i" if l.endswith(("a", "e", "o")) else None,
            ):
                if not cand or cand == l or cand not in lemset:
                    continue
                key = tuple(sorted([l, cand]))
                if key in seen:
                    continue
                seen.add(key)
                flags.append((c_by[l] + c_by[cand], l, cand))
        if flags:
            flags.sort(reverse=True)
            out.append(f"### {attr}")
            for total, a, b in flags[:25]:
                out.append(f"  {total:6d}  {a:20s} <-> {b:20s}")
            out.append("")

    # ---- 4. near-duplicates (edit distance 1) ----
    out.append("\n## 4. Near-duplicate lemmas (edit distance 1) — typos or sg/pl missed\n")
    for attr in sorted(by_attr):
        rows = by_attr[attr][:120]   # only top 120 per attr to keep it tractable
        lemmas = [r[0] for r in rows]
        c_by = {l: c for l, c, _ in rows}
        flagged: list[tuple[int, str, str]] = []
        for i, a in enumerate(lemmas):
            for b in lemmas[i + 1 :]:
                if abs(len(a) - len(b)) > 1:
                    continue
                if edit_distance(a, b) == 1:
                    flagged.append((c_by[a] + c_by[b], a, b))
        if flagged:
            flagged.sort(reverse=True)
            out.append(f"### {attr}")
            for total, a, b in flagged[:20]:
                out.append(f"  {total:6d}  {a:20s} ≈ {b:20s}")
            out.append("")

    # ---- 5. cross-attribute lemmas (same word in many attributes) ----
    out.append("\n## 5. Lemmas appearing in many attributes (informational)\n")
    multi = sorted(((len(s), l, sorted(s)) for l, s in in_attrs.items() if len(s) >= 4),
                   reverse=True)
    for n, l, sset in multi[:40]:
        out.append(f"  {n}× {l:20s} attrs: {', '.join(sset)}")

    # ---- 6. side-by-side top 30 per attribute ----
    out.append("\n\n## 6. Top 30 lemmas per attribute (style snapshot)\n")
    rank_n = 30
    cols = sorted(by_attr)
    rows_top: list[list[str]] = []
    for i in range(rank_n):
        row = []
        for a in cols:
            if i < len(by_attr[a]):
                lemma, c, _ = by_attr[a][i]
                row.append(f"{lemma}({c})")
            else:
                row.append("")
        rows_top.append(row)
    # render
    widths = [max(len(a), max(len(r[i]) for r in rows_top)) for i, a in enumerate(cols)]
    out.append(" | ".join(f"{a:{widths[i]}s}" for i, a in enumerate(cols)))
    out.append("-+-".join("-" * w for w in widths))
    for r in rows_top:
        out.append(" | ".join(f"{r[i]:{widths[i]}s}" for i in range(len(cols))))
    out.append("")

    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT}")
    print(f"size: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
