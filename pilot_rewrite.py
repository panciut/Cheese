"""Pilot run: rewrite ~100 captions through Haiku 4.5 for prompt review.

Stratifies across the 7 sensory attributes, mixing high-frequency captions
(maximum broadcast value) with random samples (style-diversity probe).
Writes a side-by-side raw → clean review file so the prompt can be tuned
before launching the full ~7,742-row Batch API job.

Usage:
    export ANTHROPIC_API_KEY=...
    python3 pilot_rewrite.py [--n 15] [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

from rewrite_prompt import ATTRIBUTE_CONFIG, build_system_prompt, build_user_prompt

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese")
SRC = ROOT / "data" / "captions_to_rewrite.csv"
OUT_CSV = ROOT / "data" / "pilot_rewrites.csv"
OUT_REVIEW = ROOT / "data" / "pilot_review.txt"

MODEL = "claude-haiku-4-5"
MAX_WORKERS = 8


def stratified_sample(rows: list[dict], n_per_attr: int, seed: int) -> list[dict]:
    """Per attribute: pick top-frequency captions + a random tail for diversity."""
    by_attr: dict[str, list[dict]] = {}
    for r in rows:
        by_attr.setdefault(r["attribute"], []).append(r)
    rng = random.Random(seed)
    out: list[dict] = []
    for attr, attr_rows in by_attr.items():
        attr_rows.sort(key=lambda r: -int(r["frequency"]))
        top_n = max(1, n_per_attr // 3)
        top = attr_rows[:top_n]
        tail = attr_rows[top_n:]
        random_pick = rng.sample(tail, min(n_per_attr - len(top), len(tail)))
        out.extend(top + random_pick)
    return out


def rewrite_one(
    client: anthropic.Anthropic, attribute: str, caption: str
) -> tuple[str | None, str | None]:
    """Return (clean_text, error). One of the two is non-None."""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=build_system_prompt(attribute),
            messages=[{"role": "user", "content": build_user_prompt(attribute, caption)}],
        )
    except anthropic.RateLimitError as e:
        return None, f"rate_limit: {e}"
    except anthropic.APIStatusError as e:
        return None, f"api_error_{e.status_code}: {e.message}"
    except Exception as e:
        return None, f"error: {type(e).__name__}: {e}"

    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        return None, "empty response"
    return text.strip().strip('"'), None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=15, help="captions per attribute (~7×n total)")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("error: set ANTHROPIC_API_KEY")

    with SRC.open() as fh:
        unique = list(csv.DictReader(fh))
    print(f"loaded {len(unique)} unique captions")

    sampled = stratified_sample(unique, args.n, args.seed)
    print(f"sampled {len(sampled)} captions across {len(ATTRIBUTE_CONFIG)} attributes")

    client = anthropic.Anthropic()

    n_ok = n_err = 0
    results: list[dict] = []

    def task(row: dict) -> dict:
        out, err = rewrite_one(client, row["attribute"], row["caption_pre"])
        return {**row, "caption_clean": out or "", "error": err or ""}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futs = [exe.submit(task, r) for r in sampled]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            if r["error"]:
                n_err += 1
            else:
                n_ok += 1
            if i % 10 == 0 or i == len(sampled):
                print(f"  {i}/{len(sampled)}  ok={n_ok}  err={n_err}")

    cols = [
        "dedup_key", "attribute", "caption_pre", "caption_clean",
        "frequency", "sample_row_id", "error",
    ]
    with OUT_CSV.open("w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in cols})

    results.sort(key=lambda r: (r["attribute"], -int(r.get("frequency", 0))))
    lines = [
        f"pilot rewrite review — {len(results)} captions, ok={n_ok}, errors={n_err}",
        f"model={MODEL}",
        "",
    ]
    cur_attr: str | None = None
    for r in results:
        if r["attribute"] != cur_attr:
            cur_attr = r["attribute"]
            lines.append(f"\n## {cur_attr}\n")
        lines.append(f"  freq={r['frequency']:>4s}  raw : {r['caption_pre']}")
        suffix = f"   [{r['error']}]" if r["error"] else ""
        lines.append(f"             clean: {r['caption_clean']}{suffix}")
    OUT_REVIEW.write_text("\n".join(lines) + "\n")

    print(f"\nwrote {OUT_CSV}")
    print(f"wrote {OUT_REVIEW}")
    if n_err:
        print(f"warning: {n_err} errors — inspect the review file")


if __name__ == "__main__":
    main()
