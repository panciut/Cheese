"""Filter unambiguously info-poor captions before the LLM rewrite step.

Conservative filter — only drops captions where:
  (a) The entire content is a pure evaluative judgment with no descriptor
      ("Buono", "Ottimo", "Brutta", "Ok", "Mah" alone).
  (b) The entire content is a bare number or numeric range with no unit
      and no descriptor ("10", "0,8", "11 12") — too ambiguous to
      qualitatise even for Spessore della Crosta.
  (c) The entire content is system/test meta ("valutazione alle 13:40",
      "Al primo tentativo si è chiuso il test", "Peccato.").

Captions that mix meta with real descriptors are KEPT — the LLM rewrite
will strip the meta clause while preserving the descriptor (e.g.
"amaro deciso e penalizzante" → "Sapore amaro e deciso").

Reads:  data/captions_pre.csv, data/captions_unique.csv
Writes: data/captions_to_rewrite.csv   -- filtered unique (LLM input)
        data/captions_pre_filtered.csv -- filtered full (broadcast target)
        data/dropped_captions.csv      -- audit trail of dropped rows
        data/drop_captions_report.txt
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PRE = ROOT / "data" / "intermediate" / "captions_pre.csv"
SRC_UNIQUE = ROOT / "data" / "intermediate" / "captions_unique.csv"
OUT_REWRITE = ROOT / "data" / "intermediate" / "captions_to_rewrite.csv"
OUT_FULL = ROOT / "data" / "intermediate" / "captions_pre_filtered.csv"
OUT_DROPPED = ROOT / "data" / "intermediate" / "dropped_captions.csv"
OUT_REPORT = ROOT / "data" / "reports" / "drop_captions_report.txt"

# (a) pure evaluatives — judgment without descriptor
PURE_EVAL = {
    "buono", "buona", "buoni", "buone",
    "bello", "bella", "belli", "belle",
    "brutto", "brutta", "brutti", "brutte",
    "ottimo", "ottima", "ottimi", "ottime",
    "scarso", "scarsa", "scarsi", "scarse",
    "ok", "boh", "mah", "ehm", "uhm",
    "niente", "nulla",
    "passabile", "discreto", "discreta",
    "peccato",
}

NUM_RE = re.compile(r"^\d+(?:[,.]\d+)?$")
TOKEN_RE = re.compile(r"[\wàèéìòù']+", re.UNICODE)

# (c) system/test meta — pure noise about the panelist's process or test
SYSTEM_META_PATTERNS = [
    re.compile(r"^\s*valutazione\s+alle\b", re.I),
    re.compile(r"\bal\s+primo\s+tentativo\b.*\btest\b", re.I),
    re.compile(r"\bsi\s+e[\'’]?\s+chius[oa]\s+il\s+test\b", re.I),
    re.compile(r"\bschermata\s+dei\s+commenti\b", re.I),
    re.compile(r"\bsono\s+(ri)?partit[oa]\s+dal\b", re.I),
    re.compile(r"^\s*peccato\s*[\.\!]*\s*$", re.I),
    re.compile(r"^\s*non\s+lo\s+so\b", re.I),
    re.compile(r"\bho\s+dovut[oa]\s+sputarl", re.I),
]


def is_pure_eval(text: str) -> bool:
    tokens = [t.lower() for t in TOKEN_RE.findall(text)]
    return len(tokens) == 1 and tokens[0] in PURE_EVAL


def is_number_only(text: str) -> bool:
    tokens = TOKEN_RE.findall(text)
    if not tokens or len(tokens) > 3:
        return False
    return all(NUM_RE.match(t) for t in tokens)


def is_system_meta(text: str) -> bool:
    return any(p.search(text) for p in SYSTEM_META_PATTERNS)


def drop_reason(text: str) -> str | None:
    if is_pure_eval(text):
        return "PURE_EVAL"
    if is_number_only(text):
        return "NUMBER_ONLY"
    if is_system_meta(text):
        return "SYSTEM_META"
    return None


def main():
    # walk unique first to find which dedup_keys to drop
    dropped_keys: dict[str, str] = {}
    kept_keys: set[str] = set()
    unique_kept: list[dict] = []

    with SRC_UNIQUE.open() as fh:
        reader = csv.DictReader(fh)
        unique_cols = reader.fieldnames or []
        for r in reader:
            reason = drop_reason(r["caption_pre"])
            if reason:
                dropped_keys[r["dedup_key"]] = reason
            else:
                kept_keys.add(r["dedup_key"])
                unique_kept.append(r)

    # write filtered unique (LLM input)
    with OUT_REWRITE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=unique_cols)
        w.writeheader()
        for r in unique_kept:
            w.writerow(r)

    # filter full file accordingly + write audit trail
    n_full_in = 0
    n_full_kept = 0
    n_full_dropped = 0
    drop_by_reason: Counter[str] = Counter()
    with SRC_PRE.open() as fh, \
         OUT_FULL.open("w", newline="") as out_full, \
         OUT_DROPPED.open("w", newline="") as out_drop:
        reader = csv.DictReader(fh)
        full_cols = reader.fieldnames or []
        wf = csv.DictWriter(out_full, fieldnames=full_cols)
        wd = csv.DictWriter(out_drop, fieldnames=full_cols + ["drop_reason"])
        wf.writeheader()
        wd.writeheader()
        for r in reader:
            n_full_in += 1
            if r["dedup_key"] in dropped_keys:
                n_full_dropped += 1
                reason = dropped_keys[r["dedup_key"]]
                drop_by_reason[reason] += 1
                wd.writerow({**r, "drop_reason": reason})
            else:
                n_full_kept += 1
                wf.writerow(r)

    # report
    drop_examples: dict[str, list[tuple[int, str, str]]] = {
        "PURE_EVAL": [], "NUMBER_ONLY": [], "SYSTEM_META": []
    }
    with SRC_UNIQUE.open() as fh:
        for r in csv.DictReader(fh):
            reason = dropped_keys.get(r["dedup_key"])
            if reason:
                drop_examples[reason].append(
                    (int(r["frequency"]), r["attribute"], r["caption_pre"])
                )

    lines = [
        f"unique captions  : input={len(dropped_keys) + len(unique_kept)}, "
        f"kept={len(unique_kept)}, dropped={len(dropped_keys)}",
        f"full rows        : input={n_full_in}, kept={n_full_kept}, "
        f"dropped={n_full_dropped} ({100*n_full_dropped/n_full_in:.2f}%)",
        "",
        "drops by category (full rows):",
    ]
    for reason, c in drop_by_reason.most_common():
        lines.append(f"  {reason:15s} {c} rows")
    lines.append("")
    for reason, items in drop_examples.items():
        if not items:
            continue
        lines.append(f"## {reason} (showing all {len(items)} unique)")
        for freq, attr, txt in sorted(items, reverse=True):
            lines.append(f"  {freq:5d}x  [{attr[:18]:18s}] {txt[:90]}")
        lines.append("")

    OUT_REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {OUT_REWRITE}")
    print(f"wrote {OUT_FULL}")
    print(f"wrote {OUT_DROPPED}")
    print(f"wrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
