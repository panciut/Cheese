"""Run the full LLM rewrite for one sensory attribute, synchronously.

Use this to validate (or finalize) one attribute end-to-end before
committing to the full Batch API run. Concurrency is 3 workers + 6 SDK
retries — proven safe for the user's tier on Haiku 4.5.

Usage:
    python3 rewrite_attribute.py "Spessore della Crosta"
    python3 rewrite_attribute.py Aroma --workers 3

Outputs:
    data/rewrites_<attribute>.csv     full row-per-unique-caption output
    data/review_<attribute>.txt       sorted side-by-side raw -> clean
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

from pilot_rewrite import load_api_key, rewrite_one
from rewrite_prompt import ATTRIBUTE_CONFIG

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese")
SRC = ROOT / "data" / "captions_to_rewrite.csv"

MODEL = "claude-haiku-4-5"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("attribute", help="exact attribute name, e.g. 'Spessore della Crosta'")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--max-retries", type=int, default=6)
    p.add_argument("--limit", type=int, default=None,
                   help="cap number of captions (for a smaller run)")
    args = p.parse_args()

    if args.attribute not in ATTRIBUTE_CONFIG:
        print(f"unknown attribute: {args.attribute}")
        print("available:")
        for a in ATTRIBUTE_CONFIG:
            print(f"  - {a}")
        sys.exit(1)

    api_key = load_api_key()

    with SRC.open() as fh:
        captions = [r for r in csv.DictReader(fh) if r["attribute"] == args.attribute]
    print(f"attribute: {args.attribute}")
    print(f"unique captions to rewrite: {len(captions)}")
    if args.limit:
        captions = captions[: args.limit]
        print(f"limiting to first {len(captions)} for this run")

    # sort highest frequency first so the most-broadcast captions land in the
    # CSV/review at the top — easier to spot-check the high-impact ones.
    captions.sort(key=lambda r: -int(r["frequency"]))

    client = anthropic.Anthropic(api_key=api_key, max_retries=args.max_retries)

    n_ok = n_err = 0
    results: list[dict] = []
    t0 = time.monotonic()

    def task(row: dict) -> dict:
        out, err = rewrite_one(client, row["attribute"], row["caption_pre"])
        return {**row, "caption_clean": out or "", "error": err or ""}

    with ThreadPoolExecutor(max_workers=args.workers) as exe:
        futs = [exe.submit(task, r) for r in captions]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            if r["error"]:
                n_err += 1
            else:
                n_ok += 1
            if i % 25 == 0 or i == len(captions):
                dt = time.monotonic() - t0
                rate = i / dt if dt else 0
                eta = (len(captions) - i) / rate if rate else 0
                print(f"  {i}/{len(captions)}  ok={n_ok} err={n_err}  "
                      f"({rate:.1f} req/s, eta {eta:.0f}s)")

    slug = args.attribute.replace(" ", "_")
    out_csv = ROOT / "data" / f"rewrites_{slug}.csv"
    out_review = ROOT / "data" / f"review_{slug}.txt"

    cols = [
        "dedup_key", "attribute", "caption_pre", "caption_clean",
        "frequency", "sample_row_id", "error",
    ]
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in cols})

    results.sort(key=lambda r: -int(r["frequency"]))
    lines = [
        f"## {args.attribute}",
        f"unique captions: {len(results)}, ok={n_ok}, errors={n_err}",
        f"model: {MODEL}",
        "",
        "(sorted by descending broadcast frequency)",
        "",
    ]
    for r in results:
        suffix = f"   [{r['error']}]" if r["error"] else ""
        lines.append(f"  freq={r['frequency']:>4s}  raw : {r['caption_pre']}")
        lines.append(f"             clean: {r['caption_clean']}{suffix}")
    out_review.write_text("\n".join(lines) + "\n")

    elapsed = time.monotonic() - t0
    print(f"\nelapsed: {elapsed:.1f}s")
    print(f"wrote {out_csv}")
    print(f"wrote {out_review}")
    if n_err:
        print(f"warning: {n_err} errors — inspect the review file")


if __name__ == "__main__":
    main()
