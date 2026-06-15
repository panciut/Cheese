"""Analisi esaustiva di data/final/captions_final.csv vs requisiti consegna.

Output: reports/caption_quality_full.md
Zero LLM cost. Pattern matching + statistiche.
"""
from __future__ import annotations
import csv, re, sys, json
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

ROOT = Path(__file__).parent.parent
SRC = ROOT / "data" / "final" / "captions_final.csv"
OUT = ROOT / "reports" / "caption_quality_full.md"
OUT.parent.mkdir(exist_ok=True)

# ---------- vocabolari di controllo ----------
NUM_UNIT = re.compile(r"\b\d+\s*(?:mm|cm|%|m)\b", re.I)
ANY_DIGIT = re.compile(r"\d")

# Aggettivi/avverbi valutativi soggettivi (non oggettivi sensoriali)
SUBJECTIVE = [
    r"\bbell[aoie]\b", r"\bbrutt[aoie]\b", r"\bstrano\b", r"\bstrana\b",
    r"\bfastidios[aoie]\b", r"\bnon piacevole\b", r"\bpiacevole\b",
    r"\bpeccato\b", r"\bperò\b", r"\bquasi tropp", r"\btropp[oa]\b",
    r"\bbuon[aoie]\b", r"\bcattiv[aoie]\b", r"\bbanale\b", r"\banonim",
    r"\bsembra\b", r"\bsa di\b", r"\bnon bell", r"\bschif",
]
SUBJECTIVE_RE = re.compile("|".join(SUBJECTIVE), re.I)

# Espressioni colloquiali / idiomatiche / dialettali
COLLOQUIAL = [
    r"\bimpasta la bocca\b", r"\btutt[ao] spaccat", r"\bin bocca\b",
    r"\bsa di\b", r"\bbella struttura\b", r"\bpoco bell",
    r"\bda morire\b", r"\bun po'\b", r"\btipo colpa\b",
    r"\bcomunque\b", r"\binsomma\b", r"\bcosì\b",
    r"\boddio\b", r"\bmagari\b",
]
COLLOQUIAL_RE = re.compile("|".join(COLLOQUIAL), re.I)

# Termini dialettali noti area trentina/veneta + errori comuni
DIALECT = [
    r"\bpien\b", r"\bbon\b", r"\bche bel\b", r"\bxe\b", r"\bgnente\b",
    r"\bmalga\b",  # contesto-specifico, non sempre dialettale
    r"\bbusiollo\b", r"\bsotelo\b", r"\bsbusà",
]
DIALECT_RE = re.compile("|".join(DIALECT), re.I)

# Punteggiatura anomala / artefatti
ARTIFACTS = re.compile(r"(\.{2,}|!+|\?+|\s{2,}|^\s|\s$)")

# Caratteri non-italiani (oltre ASCII + accentate)
NON_ITAL = re.compile(r"[^\w\s,.;:'\-àèéìòùÀÈÉÌÒÙ()\"]")

ATTRIBUTES_EXPECTED = {
    "Profumo", "Aroma", "Sapore", "Texture",
    "Spessore della Crosta", "Struttura della Pasta", "Colore della Pasta",
}

# ---------- raccolta dati ----------
rows = []
with SRC.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

N = len(rows)
print(f"Loaded {N} rows")

# campi attesi
fields = reader.fieldnames or []
TXT_COLS = ["caption_raw", "caption_pre", "caption", "caption_sentence"]
for c in TXT_COLS:
    assert c in fields, f"missing column {c}"

# ---------- analisi ----------
stats = {
    "total_rows": N,
    "unique": {c: len({r[c] for r in rows if r[c]}) for c in TXT_COLS},
    "empty": {c: sum(1 for r in rows if not r[c].strip()) for c in TXT_COLS},
    "len_avg": {c: round(sum(len(r[c]) for r in rows)/N, 1) for c in TXT_COLS},
    "len_max": {c: max(len(r[c]) for r in rows) for c in TXT_COLS},
}

# digits / units leakage
digit_hits = {c: [] for c in TXT_COLS}
unit_hits = {c: [] for c in TXT_COLS}
for r in rows:
    for c in TXT_COLS:
        v = r[c]
        if ANY_DIGIT.search(v):
            digit_hits[c].append((r["row_id"], v))
        if NUM_UNIT.search(v):
            unit_hits[c].append((r["row_id"], v))

# subjective lexicon hits
subj_hits = {c: [] for c in ("caption", "caption_sentence")}
for r in rows:
    for c in subj_hits:
        if SUBJECTIVE_RE.search(r[c]):
            subj_hits[c].append((r["row_id"], r["attribute"], r[c]))

# colloquial / dialect / artifacts
colloq_hits = []
dialect_hits = []
artifact_hits = []
for r in rows:
    cap = r["caption"]
    if COLLOQUIAL_RE.search(cap):
        colloq_hits.append((r["row_id"], r["attribute"], cap))
    if DIALECT_RE.search(cap):
        dialect_hits.append((r["row_id"], r["attribute"], cap))
    if ARTIFACTS.search(cap):
        artifact_hits.append((r["row_id"], cap))

# coerenza caption vs caption_sentence (sentence dovrebbe contenere informazione di caption)
inconsistent = []
for r in rows:
    cap = r["caption"].rstrip(".").lower().strip()
    sent = r["caption_sentence"].lower()
    # heuristic: parole significative (>3 char) di caption presenti in sentence?
    words = [w for w in re.findall(r"\w+", cap) if len(w) > 3]
    if words:
        missing = [w for w in words if w not in sent]
        if len(missing) / len(words) > 0.5:
            inconsistent.append((r["row_id"], r["caption"], r["caption_sentence"]))

# distribuzione per attributo
by_attr = Counter(r["attribute"] for r in rows)
unexpected_attrs = set(by_attr) - ATTRIBUTES_EXPECTED

# top sinonimi residui per attributo (caption uniche per attributo)
unique_per_attr = defaultdict(set)
for r in rows:
    unique_per_attr[r["attribute"]].add(r["caption"])

# top caption globali
top_captions = Counter(r["caption"] for r in rows).most_common(30)

# raw → final stesso testo (nessuna trasformazione)
unchanged = sum(1 for r in rows if r["caption_raw"].strip() == r["caption"].strip())

# caption molto corte (potenzialmente telegrafiche residue) o molto lunghe
short_caps = [(r["row_id"], r["caption"]) for r in rows if 0 < len(r["caption"]) < 8]
long_caps = sorted(rows, key=lambda r: len(r["caption"]), reverse=True)[:10]

# caratteri non-italiani sospetti
non_ital_hits = []
for r in rows:
    m = NON_ITAL.findall(r["caption"])
    if m:
        non_ital_hits.append((r["row_id"], r["caption"], "".join(set(m))))

# ---------- report ----------
def fmt_examples(items, n=10):
    out = []
    seen = set()
    for tup in items:
        key = tup[-1] if isinstance(tup[-1], str) else str(tup)
        if key in seen:
            continue
        seen.add(key)
        out.append(tup)
        if len(out) >= n:
            break
    return out

lines = []
A = lines.append

A("# Report di Analisi Esaustiva — `captions_final.csv`")
A("")
A("Analisi pattern-based eseguita su **tutte le righe** del file. Zero costo LLM.")
A("")
A(f"- File: `data/final/captions_final.csv`")
A(f"- Righe totali analizzate: **{N}**")
A(f"- Script: `analyze_captions_full.py`")
A("")

A("## 1. Statistiche per colonna testuale")
A("")
A("| Colonna | Uniche | Vuote | Lunghezza media | Lunghezza max |")
A("|---|---:|---:|---:|---:|")
for c in TXT_COLS:
    A(f"| `{c}` | {stats['unique'][c]} | {stats['empty'][c]} | {stats['len_avg'][c]} | {stats['len_max'][c]} |")
A("")
A(f"Caption identiche al raw (nessuna trasformazione applicata): **{unchanged}** ({unchanged/N*100:.1f}%)")
A("")

A("## 2. Requisito 1 — Quantitativo → Qualitativo")
A("")
A("Conteggio occorrenze numeriche residue per colonna:")
A("")
A("| Colonna | Righe con almeno una cifra | Righe con misura+unità (mm/cm/%/m) |")
A("|---|---:|---:|")
for c in TXT_COLS:
    A(f"| `{c}` | {len(digit_hits[c])} | {len(unit_hits[c])} |")
A("")

if digit_hits["caption"]:
    A("**Esempi residui in `caption`:**")
    A("")
    for rid, v in fmt_examples(digit_hits["caption"], 10):
        A(f"- `row_id={rid}`: {v}")
    A("")
else:
    A("✅ Nessun numero residuo nella colonna `caption`.")
    A("")

if digit_hits["caption_sentence"]:
    A(f"**Cifre residue in `caption_sentence`: {len(digit_hits['caption_sentence'])}**")
    for rid, v in fmt_examples(digit_hits["caption_sentence"], 5):
        A(f"- `row_id={rid}`: {v}")
    A("")

A("## 3. Requisito 2 — Dialetto / Colloquiale → Italiano standard")
A("")
A(f"- Espressioni colloquiali/idiomatiche in `caption`: **{len(colloq_hits)}** righe")
A(f"- Termini dialettali in `caption`: **{len(dialect_hits)}** righe")
A(f"- Lessico valutativo soggettivo in `caption`: **{len(subj_hits['caption'])}** righe")
A(f"- Lessico valutativo soggettivo in `caption_sentence`: **{len(subj_hits['caption_sentence'])}** righe")
A("")

A("**Esempi colloquiali/idiomatici residui:**")
A("")
A("| row_id | attribute | caption |")
A("|---|---|---|")
for rid, attr, cap in fmt_examples(colloq_hits, 15):
    A(f"| {rid} | {attr} | {cap} |")
A("")

A("**Esempi lessico valutativo soggettivo (`caption`):**")
A("")
A("| row_id | attribute | caption |")
A("|---|---|---|")
for rid, attr, cap in fmt_examples(subj_hits["caption"], 15):
    A(f"| {rid} | {attr} | {cap} |")
A("")

if dialect_hits:
    A("**Esempi termini dialettali residui:**")
    A("")
    for rid, attr, cap in fmt_examples(dialect_hits, 10):
        A(f"- `row_id={rid}` [{attr}]: {cap}")
    A("")

A("## 4. Requisito 3 — Telegrafico → Frase elegante")
A("")
A(f"- Caption molto corte (<8 caratteri) potenzialmente telegrafiche: **{len(short_caps)}**")
if short_caps:
    A("")
    for rid, cap in fmt_examples(short_caps, 10):
        A(f"- `row_id={rid}`: `{cap}`")
A("")
A("**10 caption più lunghe (verifica eleganza/eccessiva verbosità):**")
A("")
for r in long_caps:
    A(f"- `row_id={r['row_id']}` ({len(r['caption'])} char): {r['caption'][:200]}")
A("")

A("## 5. Requisito 4 — Riduzione sinonimi")
A("")
A(f"- Caption uniche globali: **{stats['unique']['caption']}** su {N} righe")
A(f"- Rapporto unicità: **{stats['unique']['caption']/N*100:.2f}%**")
A("")
A("**Caption uniche per attributo:**")
A("")
A("| Attribute | Righe | Caption uniche | Rapporto |")
A("|---|---:|---:|---:|")
for attr, count in sorted(by_attr.items(), key=lambda x: -x[1]):
    uniq = len(unique_per_attr[attr])
    A(f"| {attr} | {count} | {uniq} | {uniq/count*100:.1f}% |")
A("")

A("**Top 30 caption più frequenti:**")
A("")
A("| # | Conteggio | Caption |")
A("|---:|---:|---|")
for i, (cap, n) in enumerate(top_captions, 1):
    A(f"| {i} | {n} | {cap[:120]} |")
A("")

A("## 6. Coerenza `caption` ↔ `caption_sentence`")
A("")
A(f"- Righe con possibile incoerenza (>50% parole-chiave caption assenti in sentence): **{len(inconsistent)}**")
if inconsistent:
    A("")
    A("Esempi:")
    A("")
    for rid, cap, sent in inconsistent[:8]:
        A(f"- `row_id={rid}`")
        A(f"  - caption: {cap}")
        A(f"  - sentence: {sent}")
A("")

A("## 7. Distribuzione per attributo")
A("")
A(f"Attributi attesi: {sorted(ATTRIBUTES_EXPECTED)}")
if unexpected_attrs:
    A(f"⚠️ **Attributi inattesi presenti**: {sorted(unexpected_attrs)}")
else:
    A("✅ Solo attributi attesi presenti.")
A("")

A("## 8. Artefatti / pulizia testuale")
A("")
A(f"- Righe in `caption` con artefatti (.. !! ?? doppi spazi, leading/trailing space): **{len(artifact_hits)}**")
if artifact_hits:
    A("")
    for rid, cap in fmt_examples(artifact_hits, 8):
        A(f"- `row_id={rid}`: `{cap!r}`")
A("")
A(f"- Righe con caratteri non-italiani sospetti in `caption`: **{len(non_ital_hits)}**")
if non_ital_hits:
    for rid, cap, chars in non_ital_hits[:8]:
        A(f"- `row_id={rid}`: caratteri `{chars}` in `{cap[:80]}`")
A("")

A("## 9. Sintesi finale")
A("")
A("| Requisito | Stato | Evidenza |")
A("|---|:---:|---|")
status_q = "✅" if len(unit_hits["caption"]) == 0 and len(digit_hits["caption"]) == 0 else "⚠️"
A(f"| Quantitativo → Qualitativo | {status_q} | {len(digit_hits['caption'])} cifre, {len(unit_hits['caption'])} unità in `caption` |")
status_d = "⚠️" if (len(colloq_hits) + len(dialect_hits) + len(subj_hits['caption'])) > 50 else "✅"
A(f"| Dialetto/Colloquiale → Standard | {status_d} | {len(colloq_hits)} colloquiali, {len(dialect_hits)} dialettali, {len(subj_hits['caption'])} valutativi |")
status_t = "✅" if len(short_caps) < 50 else "⚠️"
A(f"| Telegrafico → Elegante | {status_t} | {len(short_caps)} caption < 8 char |")
status_s = "✅" if stats["unique"]["caption"]/N < 0.30 else "⚠️"
A(f"| Riduzione sinonimi | {status_s} | {stats['unique']['caption']/N*100:.1f}% unicità |")
A("")

# salva metriche json
metrics = {
    "total_rows": N,
    "stats": stats,
    "digit_hits": {c: len(v) for c, v in digit_hits.items()},
    "unit_hits": {c: len(v) for c, v in unit_hits.items()},
    "colloquial": len(colloq_hits),
    "dialect": len(dialect_hits),
    "subjective_caption": len(subj_hits["caption"]),
    "subjective_sentence": len(subj_hits["caption_sentence"]),
    "short_caps": len(short_caps),
    "inconsistent_sentence": len(inconsistent),
    "artifacts": len(artifact_hits),
    "non_italian_chars": len(non_ital_hits),
    "unchanged_from_raw": unchanged,
    "by_attribute": dict(by_attr),
    "unique_per_attribute": {k: len(v) for k, v in unique_per_attr.items()},
}
(ROOT / "reports" / "caption_quality_metrics.json").write_text(
    json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
)

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Wrote {ROOT/'reports'/'caption_quality_metrics.json'}")
