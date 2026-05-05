"""Survey captions_unique.csv for captions that carry no cheese-describing
information. Goal: identify what to filter out before the LLM rewrite step.

Categories surveyed:
  A. META — panelist talks about scoring/themselves, not the cheese
     ("non valuto", "non penalizzo", "non so", "difficile valutare", ...)
  B. PURE EVALUATIVE — only a quality judgment, no descriptor
     ("Brutta", "Bello", "Ok", "Buono" alone)
  C. UNCERTAINTY / DISCLAIMER — panelist hedging, no description
     ("forse", "sembra ma", "potrebbe essere")
  D. INTERROGATIVE / OFF-TOPIC — questions, notes about the form, etc.
  E. NUMBER-ONLY in non-Spessore attribute (already filtered for the
     measurement-heavy attribute, but flag elsewhere)

Output: data/useless_caption_candidates.txt — list of unique captions to
review, with frequency and attribute. The user decides whether to drop.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data" / "intermediate" / "captions_unique.csv"
OUT = ROOT / "data" / "reports" / "useless_caption_candidates.txt"

META_PATTERNS = [
    # panelist refers to scoring/themselves, not the cheese
    re.compile(r"\bnon\s+valuto\b", re.I),
    re.compile(r"\bnon\s+penaliz", re.I),
    re.compile(r"\bnon\s+so\b(?!\s+come|\s+cosa|\s+se)", re.I),
    re.compile(r"\bnon\s+riesco\b", re.I),
    re.compile(r"\bnon\s+ne\s+capisco\b", re.I),
    re.compile(r"\bdifficile\s+da?\s*valut", re.I),
    re.compile(r"\bnon\s+saprei\b", re.I),
    re.compile(r"\bnon\s+considero\b", re.I),
    re.compile(r"\bnon\s+do\s+troppo\s+peso\b", re.I),
    re.compile(r"\bnon\s+lo\s+so\b", re.I),
    re.compile(r"\bdovuto\s+sputarl", re.I),
    re.compile(r"\bvalutazione\s+", re.I),
    re.compile(r"\bpunteggio\b", re.I),
    re.compile(r"\bpenalizz", re.I),
    re.compile(r"\bil\s+voto\b", re.I),
    re.compile(r"\bvoto\s+(troppo|alto|basso|dato)", re.I),
    re.compile(r"\bdiminuito\s+di\b", re.I),
    re.compile(r"\bsenza\s+valutar", re.I),
    re.compile(r"^\s*peccato\s*[\.\!]*\s*$", re.I),
]

UNCERTAINTY_PATTERNS = [
    re.compile(r"^\s*forse\b", re.I),
    re.compile(r"^\s*sembra\b", re.I),
    re.compile(r"^\s*potrebbe\b", re.I),
    re.compile(r"^\s*credo\b", re.I),
    re.compile(r"^\s*direi\b", re.I),
    re.compile(r"^\s*pare\b", re.I),
]

INTERROGATIVE_PATTERNS = [
    re.compile(r"\?$"),
    re.compile(r"^\s*ma\s+", re.I),
]

# pure evaluative single tokens — judgment without sensory descriptor.
# `regolare`, `tipico`, `normale` removed: they ARE sensory descriptors
# meaning "uniform/typical/standard" depending on attribute.
PURE_EVAL = {
    "buono", "buona", "buoni", "buone", "bello", "bella", "belli", "belle",
    "brutto", "brutta", "brutti", "brutte",
    "ottimo", "ottima", "ottimi", "ottime",
    "scarso", "scarsa", "scarsi", "scarse",
    "ok", "boh", "mah", "ehm", "uhm",
    "niente", "nulla",
    "sì", "no",
    "passabile",
}

# Single-word intensifier alone — these ARE dimensional info (intensity),
# even if not specific descriptors. Kept as-is; the LLM rewrite will frame
# them naturally ("Profumo leggero" etc.). This set is no longer auto-flagged
# for dropping — kept here only for inspection in the report.
PURE_INTENSIFIER = {
    "leggero", "leggera", "leggermente",
    "intenso", "intensa", "intensi", "intense",
    "forte", "forti",
    "debole", "deboli",
    "medio", "media", "medi", "medie",
    "alto", "alta", "alti", "alte",
    "basso", "bassa", "bassi", "basse",
}


def categorize(text: str, attribute: str) -> list[str]:
    cats: list[str] = []
    t = text.strip()
    low = t.lower()

    if any(p.search(t) for p in META_PATTERNS):
        cats.append("META")
    if any(p.search(t) for p in UNCERTAINTY_PATTERNS):
        cats.append("UNCERTAINTY")
    if any(p.search(t) for p in INTERROGATIVE_PATTERNS):
        cats.append("INTERROGATIVE")

    tokens = re.findall(r"[\wàèéìòù']+", low)
    if len(tokens) == 1 and tokens[0] in PURE_EVAL:
        cats.append("PURE_EVAL")
    if len(tokens) == 1 and tokens[0] in PURE_INTENSIFIER:
        cats.append("PURE_INTENSIFIER")
    if not tokens:
        cats.append("EMPTY_AFTER_TOKENIZE")
    # bare-number captions: every token is digits, possibly with a comma
    # like "0,8" or "1,1" (Italian decimal). Up to 3 such tokens.
    num_re = re.compile(r"^\d+(?:[,.]\d+)?$")
    if 0 < len(tokens) <= 3 and all(num_re.match(t) for t in tokens):
        cats.append("NUMBER_ONLY")

    return cats


def main():
    by_cat: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    total = 0
    flagged_keys: set[str] = set()

    with SRC.open() as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            total += 1
            cats = categorize(r["caption_pre"], r["attribute"])
            for c in cats:
                by_cat[c].append((int(r["frequency"]), r["attribute"], r["caption_pre"]))
            if cats:
                flagged_keys.add(r["dedup_key"])

    lines = [f"Total unique captions: {total}",
             f"Unique captions with ≥1 flag: {len(flagged_keys)} "
             f"({100*len(flagged_keys)/total:.1f}%)",
             ""]

    for cat in ["META", "UNCERTAINTY", "INTERROGATIVE",
                "PURE_EVAL", "PURE_INTENSIFIER",
                "NUMBER_ONLY", "EMPTY_AFTER_TOKENIZE"]:
        items = sorted(by_cat.get(cat, []), reverse=True)
        if not items:
            continue
        impact = sum(f for f, _, _ in items)
        lines.append(f"## {cat}  ({len(items)} unique, "
                     f"would drop {impact} training rows)")
        for freq, attr, txt in items[:40]:
            lines.append(f"  {freq:5d}x  [{attr[:18]:18s}] {txt[:100]}")
        if len(items) > 40:
            lines.append(f"  ... and {len(items) - 40} more")
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
