"""Submit a Batch API job for one or more sensory attributes.

Submits all unique captions for the chosen attributes as one batch
(50% off, async, no rate limits). Saves the request mapping locally
before submission so the script can be re-run to resume polling /
fetching even if it crashes between submit and retrieve.

Usage:
    python3 rewrite_batch.py "Aroma" "Spessore della Crosta"
    python3 rewrite_batch.py --status   # show all known batches
    python3 rewrite_batch.py --resume <batch_id>

Outputs (per attribute):
    data/rewrites_<attribute>.csv     row-per-unique-caption with caption_clean
    data/review_<attribute>.txt       sorted side-by-side raw -> clean

Bookkeeping:
    data/batches/<batch_id>.json      request-id -> dedup_key mapping
                                       + submission metadata
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from pilot_rewrite import load_api_key
from rewrite_prompt import ATTRIBUTE_CONFIG, build_system_prompt, build_user_prompt

MODEL = "claude-haiku-4-5"
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data" / "intermediate" / "captions_to_rewrite.csv"
REWRITES_DIR = ROOT / "data" / "rewrites"
BATCH_DIR = ROOT / "data" / "batches"


def custom_id_for(idx: int) -> str:
    return f"row{idx:05d}"


def submit(client: anthropic.Anthropic, attributes: list[str]) -> str:
    with SRC.open() as fh:
        all_rows = [r for r in csv.DictReader(fh) if r["attribute"] in attributes]
    print(f"loaded {len(all_rows)} unique captions across attributes:")
    by_attr = defaultdict(int)
    for r in all_rows:
        by_attr[r["attribute"]] += 1
    for a, n in by_attr.items():
        print(f"  {a:30s} {n:5d}")

    requests: list[Request] = []
    mapping: dict[str, dict] = {}
    for i, r in enumerate(all_rows):
        cid = custom_id_for(i)
        mapping[cid] = {
            "dedup_key": r["dedup_key"],
            "attribute": r["attribute"],
            "caption_pre": r["caption_pre"],
            "frequency": r["frequency"],
            "sample_row_id": r["sample_row_id"],
        }
        requests.append(Request(
            custom_id=cid,
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=200,
                system=build_system_prompt(r["attribute"]),
                messages=[{
                    "role": "user",
                    "content": build_user_prompt(r["attribute"], r["caption_pre"]),
                }],
            ),
        ))

    print(f"\nsubmitting batch ({len(requests)} requests)...")
    batch = client.messages.batches.create(requests=requests)
    print(f"batch id : {batch.id}")
    print(f"status   : {batch.processing_status}")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    side = BATCH_DIR / f"{batch.id}.json"
    side.write_text(json.dumps({
        "batch_id": batch.id,
        "submitted_at": time.time(),
        "model": MODEL,
        "attributes": attributes,
        "n_requests": len(requests),
        "mapping": mapping,
    }, indent=2))
    print(f"saved mapping to {side}")
    return batch.id


def poll_until_done(client: anthropic.Anthropic, batch_id: str) -> object:
    print(f"polling {batch_id} ...")
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        c = batch.request_counts
        status = batch.processing_status
        print(f"  status={status}  succeeded={c.succeeded} "
              f"errored={c.errored} processing={c.processing} "
              f"canceled={c.canceled} expired={c.expired}", flush=True)
        if status == "ended":
            return batch
        time.sleep(30)


def fetch_and_write(client: anthropic.Anthropic, batch_id: str) -> None:
    side_path = BATCH_DIR / f"{batch_id}.json"
    if not side_path.exists():
        sys.exit(f"no mapping found for batch {batch_id} at {side_path}")
    side = json.loads(side_path.read_text())
    mapping: dict[str, dict] = side["mapping"]

    print(f"fetching results for {batch_id} ...")
    by_attr_rows: dict[str, list[dict]] = defaultdict(list)
    n_ok = n_err = 0

    for result in client.messages.batches.results(batch_id):
        cid = result.custom_id
        meta = mapping.get(cid)
        if meta is None:
            print(f"warning: no mapping for {cid}")
            continue

        clean = ""
        err = ""
        if result.result.type == "succeeded":
            msg = result.result.message
            text = next((b.text for b in msg.content if b.type == "text"), None)
            if text:
                clean = text.strip().strip('"')
                n_ok += 1
            else:
                err = "empty text"
                n_err += 1
        elif result.result.type == "errored":
            err_obj = result.result.error
            err = f"{err_obj.type}: {err_obj.message}" if hasattr(err_obj, "message") else str(err_obj)
            n_err += 1
        elif result.result.type in ("canceled", "expired"):
            err = result.result.type
            n_err += 1
        else:
            err = f"unknown type: {result.result.type}"
            n_err += 1

        row = {**meta, "caption_clean": clean, "error": err}
        by_attr_rows[meta["attribute"]].append(row)

    print(f"total: ok={n_ok} err={n_err}")

    cols = [
        "dedup_key", "attribute", "caption_pre", "caption_clean",
        "frequency", "sample_row_id", "error",
    ]
    for attr, rows in by_attr_rows.items():
        slug = attr.replace(" ", "_")
        out_csv = REWRITES_DIR / f"rewrites_{slug}.csv"
        out_review = REWRITES_DIR / f"review_{slug}.txt"

        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in cols})

        rows.sort(key=lambda r: -int(r["frequency"]))
        lines = [
            f"## {attr}",
            f"unique captions: {len(rows)}",
            f"model: {side['model']}",
            f"batch_id: {batch_id}",
            "",
            "(sorted by descending broadcast frequency)",
            "",
        ]
        for r in rows:
            suffix = f"   [{r['error']}]" if r["error"] else ""
            lines.append(f"  freq={r['frequency']:>4s}  raw : {r['caption_pre']}")
            lines.append(f"             clean: {r['caption_clean']}{suffix}")
        out_review.write_text("\n".join(lines) + "\n")

        print(f"wrote {out_csv}  ({len(rows)} rows)")
        print(f"wrote {out_review}")


def status() -> None:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BATCH_DIR.glob("*.json"))
    if not files:
        print("no batches recorded.")
        return
    for f in files:
        side = json.loads(f.read_text())
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(side["submitted_at"]))
        attrs = ", ".join(side["attributes"])
        print(f"  {side['batch_id']}  {ts}  n={side['n_requests']}  attrs={attrs}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("attributes", nargs="*", help="one or more attributes")
    p.add_argument("--status", action="store_true",
                   help="list locally recorded batch IDs")
    p.add_argument("--resume", metavar="BATCH_ID",
                   help="poll an existing batch and write outputs")
    p.add_argument("--no-wait", action="store_true",
                   help="submit and exit; resume later with --resume")
    args = p.parse_args()

    if args.status:
        status()
        return

    api_key = load_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    if args.resume:
        batch_id = args.resume
        batch = poll_until_done(client, batch_id)
        fetch_and_write(client, batch_id)
        return

    if not args.attributes:
        sys.exit("usage: rewrite_batch.py <attribute> [<attribute> ...]  "
                 "(or --status / --resume <id>)")
    unknown = [a for a in args.attributes if a not in ATTRIBUTE_CONFIG]
    if unknown:
        sys.exit(f"unknown attribute(s): {unknown}\n"
                 f"available: {list(ATTRIBUTE_CONFIG)}")

    batch_id = submit(client, args.attributes)
    if args.no_wait:
        print(f"\nresume later with:  python3 rewrite_batch.py --resume {batch_id}")
        return
    poll_until_done(client, batch_id)
    fetch_and_write(client, batch_id)


if __name__ == "__main__":
    main()
