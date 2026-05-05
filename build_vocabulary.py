"""Build per-attribute controlled vocabulary from cleaned captions.

For each of the 7 sensory attributes, collect all caption tokens, group
inflectional variants by a simple Italian suffix-based stem, and output the
most frequent terms (canonical forms + surface variants + counts).

Also extracts the most frequent bigrams (multi-word sensory terms like
"latte cotto", "alone centrale", "frutta secca") since these matter for
synonym reduction across the dataset.

Reads:  data/captions_prepared.csv
Writes: data/vocabulary/{attribute}.txt          one human-readable file per attribute
        data/vocabulary/vocabulary.csv            combined flat list (attribute, lemma, count, surfaces)
        data/vocabulary/bigrams_{attribute}.txt   top bigrams per attribute
        data/vocabulary/_summary.txt              overview
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese")
SRC = ROOT / "data" / "captions_prepared.csv"
OUT_DIR = ROOT / "data" / "vocabulary"
TOP_N = 200          # top lemmas per attribute
TOP_BIGRAMS = 80
MIN_LEMMA_COUNT = 3   # drop noise

# Italian stopwords + dataset-noise tokens
STOP = set("""
a ad ai al alla alle agli allo anche ancora avere c che chi ci circa
co coi col come con contro cui da dai dal dalla dalle dallo dei del della
delle dello di e ed essere fare fra gli ha hai han hanno ho i il in io
la le lei lo loro ma me mi mia mie miei mio nei nel nella nelle nello
non nostra nostre nostri nostro o per più poco poi può quale quali quando
quasi quel quella quelle quelli quello questa queste questi questo se
senza si sia sono su sua sue sugli sui sul sulla sulle sullo suo suoi
te tra troppo tu tua tue tuoi tuo un una uno vi voi voi vostre vostri
abbastanza appena giusto leggermente molto poco un'
sembra punto fine media tutto tutta tutti tutte
qua qui là lì sotto sopra dietro davanti dentro fuori fino verso
oppure piuttosto soprattutto solo solamente assai certamente forse magari
sempre mai talvolta spesso raramente
sa è era erano stato stata stati state
ce ne lì già senza ovviamente ovvio quindi cioè dunque allora
""".split())

# extra noise / single-letter / digits handled by min length filter
WORD_RE = re.compile(r"[a-zàèéìòù']+", re.IGNORECASE)


def normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower()


def tokenize(s: str) -> list[str]:
    return [t for t in WORD_RE.findall(normalize(s)) if len(t) > 1]


# ---------- Italian suffix-based lemmatizer (deliberately simple) ----------
# Goal: collapse the most common inflectional variants without a real NLP lib.
# We strip common Italian endings only when the remaining stem is long enough
# to plausibly be the same lemma.
_PLURAL_F = ("e",)
_PLURAL_M = ("i",)
_FEM_SG = ("a",)
_MASC_SG = ("o",)
_VERB_PART = ("ato", "ata", "ati", "ate", "uto", "uta", "uti", "ute", "ito", "ita", "iti", "ite")
_ADV = ("mente",)
_DIM = ("etto", "etta", "etti", "ette", "ino", "ina", "ini", "ine")
_AUG = ("one", "ona", "oni", "oni")  # last is repeated harmlessly

# Hand-crafted exceptions where naive stripping yields wrong stems.
SPECIAL = {
    # surface : stem
    "occhi": "occhio", "occhio": "occhio",
    "occhiatura": "occhiatura", "occhiature": "occhiatura",
    "occhiato": "occhiato", "occhiata": "occhiato", "occhiati": "occhiato", "occhiate": "occhiato",
    "fessura": "fessura", "fessure": "fessura",
    "frattura": "frattura", "fratture": "frattura",
    "macchia": "macchia", "macchie": "macchia",
    "alone": "alone", "aloni": "alone",
    "crosta": "crosta", "croste": "crosta",
    "pasta": "pasta", "paste": "pasta",
    "nota": "nota", "note": "nota",
    "sentore": "sentore", "sentori": "sentore",
    "aroma": "aroma", "aromi": "aroma",
    "profumo": "profumo", "profumi": "profumo",
    "sapore": "sapore", "sapori": "sapore",
    "colore": "colore", "colori": "colore",
    "spessore": "spessore", "spessori": "spessore",
    "scaglia": "scaglia", "scaglie": "scaglia",
    "cristallo": "cristallo", "cristalli": "cristallo",
    "cotto": "cotto", "cotta": "cotto", "cotti": "cotto", "cotte": "cotto",
    "tostato": "tostato", "tostata": "tostato", "tostati": "tostato", "tostate": "tostato",
    "fermentato": "fermentato", "fermentata": "fermentato",
    "fermentati": "fermentato", "fermentate": "fermentato",
    "lattico": "lattico", "lattica": "lattico", "lattici": "lattico", "lattiche": "lattico",
    "intenso": "intenso", "intensa": "intenso", "intensi": "intenso", "intense": "intenso",
    "leggero": "leggero", "leggera": "leggero", "leggeri": "leggero", "leggere": "leggero",
    "tenero": "tenero", "tenera": "tenero", "teneri": "tenero", "tenere": "tenero",
    "duro": "duro", "dura": "duro", "duri": "duro", "dure": "duro",
    "secco": "secco", "secca": "secco", "secchi": "secco", "secche": "secco",
    "umido": "umido", "umida": "umido", "umidi": "umido", "umide": "umido",
    "carico": "carico", "carica": "carico", "carichi": "carico", "cariche": "carico",
    "chiaro": "chiaro", "chiara": "chiaro", "chiari": "chiaro", "chiare": "chiaro",
    "scuro": "scuro", "scura": "scuro", "scuri": "scuro", "scure": "scuro",
    "uniforme": "uniforme", "uniformi": "uniforme",
    "omogeneo": "omogeneo", "omogenea": "omogeneo", "omogenei": "omogeneo", "omogenee": "omogeneo",
    "regolare": "regolare", "regolari": "regolare",
    "irregolare": "irregolare", "irregolari": "irregolare",
    "granuloso": "granuloso", "granulosa": "granuloso", "granulosi": "granuloso", "granulose": "granuloso",
    "grossolano": "grossolano", "grossolana": "grossolano",
    "grossolani": "grossolano", "grossolane": "grossolano",
    "piccante": "piccante", "piccanti": "piccante",
    "amaro": "amaro", "amara": "amaro", "amari": "amaro", "amare": "amaro",
    "salato": "salato", "salata": "salato", "salati": "salato", "salate": "salato",
    "acido": "acido", "acida": "acido", "acidi": "acido", "acide": "acido",
    "dolce": "dolce", "dolci": "dolce",
    "fresco": "fresco", "fresca": "fresco", "freschi": "fresco", "fresche": "fresco",
    "pungente": "pungente", "pungenti": "pungente",
    "persistente": "persistente", "persistenti": "persistente",
    "persistenza": "persistenza",
    "armonioso": "armonioso", "armoniosa": "armonioso",
    "armoniosi": "armonioso", "armoniose": "armonioso",
    "complesso": "complesso", "complessa": "complesso",
    "complessi": "complesso", "complesse": "complesso",
}


def base_stem(tok: str) -> str:
    """First-pass stem: only SPECIAL + adverb -mente. Conservative.

    Italian generic suffix stripping is unreliable (panna→panno, latte→latto)
    so we leave non-SPECIAL tokens as-is here. The merge_inflections step
    below joins plural↔singular only when both surface forms are attested.
    """
    if tok in SPECIAL:
        return SPECIAL[tok]
    if tok.endswith("mente") and len(tok) > 6:
        return tok[:-5] + "e"
    return tok


def merge_inflections(counts: Counter[str]) -> tuple[Counter[str], dict[str, list[str]]]:
    """Merge plural↔singular pairs when both are attested in the corpus.

    Rules (only when both forms exist, neither in SPECIAL):
      - tok ending in -i  : try tok[:-1]+"o" and tok[:-1]+"e"
      - tok ending in -e  : try tok[:-1]+"a"  (fem plural -e of -a sg)
                            -- only if the -a form is attested AND more
                               frequent (heuristic to avoid false merges
                               like 'crosta'<-'croste' which is correct,
                               but 'note'->'nota' which is also correct)
      - tok ending in -a  : try tok[:-1]+"o"  (gendered adj pair)
    Always pick the more-frequent attested form as canonical.
    """
    surfaces: dict[str, list[str]] = {k: [k] for k in counts}
    canon: dict[str, str] = {k: k for k in counts}

    def union(a: str, b: str) -> None:
        if a == b:
            return
        winner, loser = (a, b) if counts[a] >= counts[b] else (b, a)
        # remap loser -> winner
        for s in surfaces.get(loser, []):
            canon[s] = winner
            if s not in surfaces[winner]:
                surfaces[winner].append(s)
        surfaces.pop(loser, None)

    for tok in list(counts.keys()):
        if tok in SPECIAL or tok != canon[tok]:
            continue
        candidates: list[str] = []
        if tok.endswith("i") and len(tok) > 4:
            candidates += [tok[:-1] + "o", tok[:-1] + "e"]
        if tok.endswith("e") and len(tok) > 4:
            candidates += [tok[:-1] + "a"]
        if tok.endswith("a") and len(tok) > 4:
            candidates += [tok[:-1] + "o"]
        for cand in candidates:
            if cand in canon and cand != tok:
                union(canon[tok], canon[cand])
                break

    new_counts: Counter[str] = Counter()
    for surf, c in counts.items():
        new_counts[canon[surf]] += c
    return new_counts, surfaces


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_attr_uni: dict[str, list[str]] = defaultdict(list)
    by_attr_cap: dict[str, list[list[str]]] = defaultdict(list)

    with SRC.open() as fh:
        for row in csv.DictReader(fh):
            attr = row["attribute"]
            toks = tokenize(row["caption_norm"])
            by_attr_uni[attr].extend(toks)
            by_attr_cap[attr].append(toks)

    summary_lines: list[str] = []
    flat_rows: list[dict] = []

    for attr in sorted(by_attr_uni):
        toks = by_attr_uni[attr]
        # surface counts after SPECIAL/-mente normalization
        surface_count: Counter[str] = Counter()
        original_for: dict[str, Counter[str]] = defaultdict(Counter)
        for t in toks:
            if t in STOP:
                continue
            s = base_stem(t)
            if s in STOP:
                continue
            surface_count[s] += 1
            original_for[s][t] += 1
        # corpus-driven plural↔singular merging
        lemma_count, surfaces_map = merge_inflections(surface_count)
        # build (lemma -> all original surface forms), preserving frequency order
        lemma_surfaces: dict[str, Counter[str]] = defaultdict(Counter)
        for surf, members in surfaces_map.items():
            for m in members:
                for orig, c in original_for.get(m, {m: surface_count[m]}).items():
                    lemma_surfaces[surf][orig] += c

        # bigrams: use post-normalization stems for both tokens
        bigram_count: Counter[tuple[str, str]] = Counter()
        for caption_toks in by_attr_cap[attr]:
            stems = [base_stem(t) for t in caption_toks]
            for a, b in zip(stems, stems[1:]):
                if a in STOP or b in STOP:
                    continue
                bigram_count[(a, b)] += 1

        # write per-attribute file
        attr_safe = attr.replace(" ", "_")
        f = OUT_DIR / f"{attr_safe}.txt"
        with f.open("w") as out:
            out.write(f"# Controlled vocabulary — {attr}\n")
            out.write(f"# total tokens (incl stopwords): {len(toks)}\n")
            out.write(f"# unique lemmas (>= {MIN_LEMMA_COUNT}): "
                      f"{sum(1 for c in lemma_count.values() if c >= MIN_LEMMA_COUNT)}\n")
            out.write("# format: <count>\t<canonical>\t<surface forms (most frequent first)>\n")
            out.write("\n")
            for lemma, c in lemma_count.most_common(TOP_N):
                if c < MIN_LEMMA_COUNT:
                    break
                surfaces = ", ".join(s for s, _ in lemma_surfaces[lemma].most_common())
                out.write(f"{c}\t{lemma}\t{surfaces}\n")
                flat_rows.append({
                    "attribute": attr,
                    "lemma": lemma,
                    "count": c,
                    "surfaces": surfaces,
                })

        # bigrams file
        bf = OUT_DIR / f"bigrams_{attr_safe}.txt"
        with bf.open("w") as out:
            out.write(f"# Top bigrams — {attr}\n\n")
            for (a, b), c in bigram_count.most_common(TOP_BIGRAMS):
                if c < MIN_LEMMA_COUNT:
                    break
                out.write(f"{c}\t{a} {b}\n")

        n_kept = sum(1 for c in lemma_count.values() if c >= MIN_LEMMA_COUNT)
        summary_lines.append(
            f"{attr:30s}  tokens={len(toks):7d}  unique-lemmas>={MIN_LEMMA_COUNT}: {n_kept:5d}  "
            f"top: {[w for w, _ in lemma_count.most_common(8)]}"
        )

    # combined CSV
    with (OUT_DIR / "vocabulary.csv").open("w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=["attribute", "lemma", "count", "surfaces"])
        w.writeheader()
        for r in flat_rows:
            w.writerow(r)

    # summary
    summary = "\n".join(summary_lines) + "\n"
    (OUT_DIR / "_summary.txt").write_text(summary)
    print(summary)
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
