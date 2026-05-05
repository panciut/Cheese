"""Add a `caption_sentence` column to captions_final.csv.

Transforms each compact attribute caption into a full Italian sentence
about the cheese, using deterministic regex templates that cover the
common shapes the LLM produces. Captions that don't match any template
are flagged for an LLM pass.

  Profumo di panna.            -> Il formaggio ha un profumo di panna.
  Profumo poco intenso.        -> Il formaggio ha un profumo poco intenso.
  Aroma di latte cotto.        -> Il formaggio ha un aroma di latte cotto.
  Sapore equilibrato.          -> Il formaggio ha un sapore equilibrato.
  Texture asciutta.            -> Il formaggio presenta una texture asciutta.
  Crosta sottile.              -> La crosta del formaggio è sottile.
  Pasta granulosa.             -> La pasta del formaggio è granulosa.
  Pasta di colore omogeneo.    -> La pasta del formaggio è di colore omogeneo.

Reads:  data/captions_final.csv
Writes: data/captions_final.csv  (in place — adds caption_sentence column)
        data/sentence_form_unmatched.csv  (captions to send to LLM)
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"
SRC = ROOT / "final" / "captions_final.csv"
UNMATCHED = ROOT / "intermediate" / "sentence_form_unmatched.csv"


# ---------------------------------------------------------------------------
# Regex templates per attribute. Each entry is (pattern, replacement-template).
# `{x}` in the replacement is the captured group(s). Patterns are tried in
# order; first match wins. The trailing period is matched and re-emitted.
# ---------------------------------------------------------------------------

PUNCT = r"[\.\!]?"  # final punctuation


def make_rules() -> dict[str, list[tuple[re.Pattern, str]]]:
    R: dict[str, list[tuple[re.Pattern, str]]] = {}

    # PROFUMO -------------------------------------------------------------
    R["Profumo"] = [
        # Profumo di panna. / Profumo di latte cotto e burro fresco.
        (re.compile(rf"^Profumo di (.+?){PUNCT}$"),
         "Il formaggio ha un profumo di {x}."),
        # Profumo con leggero accenno di crosta.
        (re.compile(rf"^Profumo con (.+?){PUNCT}$"),
         "Il formaggio ha un profumo con {x}."),
        # Note olfattive di eucalipto.
        (re.compile(rf"^Note olfattive di (.+?){PUNCT}$"),
         "Il formaggio presenta note olfattive di {x}."),
        # Profumo poco intenso.  /  Profumo equilibrato e piacevole.
        (re.compile(rf"^Profumo (.+?){PUNCT}$"),
         "Il formaggio ha un profumo {x}."),
    ]

    # AROMA ---------------------------------------------------------------
    R["Aroma"] = [
        (re.compile(rf"^Aroma di (.+?){PUNCT}$"),
         "Il formaggio ha un aroma di {x}."),
        (re.compile(rf"^Aroma con (.+?){PUNCT}$"),
         "Il formaggio ha un aroma con {x}."),
        (re.compile(rf"^Note aromatiche di (.+?){PUNCT}$"),
         "Il formaggio presenta note aromatiche di {x}."),
        (re.compile(rf"^Aroma (.+?){PUNCT}$"),
         "Il formaggio ha un aroma {x}."),
    ]

    # SAPORE --------------------------------------------------------------
    R["Sapore"] = [
        (re.compile(rf"^Sapore di (.+?){PUNCT}$"),
         "Il formaggio ha un sapore di {x}."),
        (re.compile(rf"^Sapore con (.+?){PUNCT}$"),
         "Il formaggio ha un sapore con {x}."),
        (re.compile(rf"^Al palato,?\s+(.+?){PUNCT}$", re.IGNORECASE),
         "Al palato, il formaggio è {x}."),
        (re.compile(rf"^Sapore non (.+?){PUNCT}$"),
         "Il formaggio ha un sapore non {x}."),
        (re.compile(rf"^Sapore (.+?){PUNCT}$"),
         "Il formaggio ha un sapore {x}."),
    ]

    # TEXTURE -------------------------------------------------------------
    R["Texture"] = [
        (re.compile(rf"^Texture di (.+?){PUNCT}$"),
         "Il formaggio presenta una texture di {x}."),
        (re.compile(rf"^Texture con (.+?){PUNCT}$"),
         "Il formaggio presenta una texture con {x}."),
        (re.compile(rf"^Texture che (.+?){PUNCT}$"),
         "Il formaggio ha una texture che {x}."),
        (re.compile(rf"^Texture dalla (.+?){PUNCT}$"),
         "Il formaggio presenta una texture dalla {x}."),
        (re.compile(rf"^In bocca,?\s+(.+?){PUNCT}$", re.IGNORECASE),
         "In bocca, il formaggio è {x}."),
        (re.compile(rf"^Texture non (.+?){PUNCT}$"),
         "Il formaggio presenta una texture non {x}."),
        (re.compile(rf"^Texture (.+?){PUNCT}$"),
         "Il formaggio presenta una texture {x}."),
    ]

    # SPESSORE DELLA CROSTA ----------------------------------------------
    R["Spessore della Crosta"] = [
        (re.compile(rf"^La crosta presenta (.+?){PUNCT}$"),
         "La crosta del formaggio presenta {x}."),
        (re.compile(rf"^Crosta con (.+?){PUNCT}$"),
         "La crosta del formaggio presenta {x}."),
        (re.compile(rf"^Crosta dalla (.+?){PUNCT}$"),
         "La crosta del formaggio è dalla {x}."),
        (re.compile(rf"^Crosta dal (.+?){PUNCT}$"),
         "La crosta del formaggio è dal {x}."),
        (re.compile(rf"^Crosta di (.+?){PUNCT}$"),
         "La crosta del formaggio è di {x}."),
        (re.compile(rf"^Crosta non (.+?){PUNCT}$"),
         "La crosta del formaggio non è {x}."),
        (re.compile(rf"^Crosta (assente .+?){PUNCT}$"),
         "La crosta del formaggio è {x}."),
        (re.compile(rf"^Crosta (.+?){PUNCT}$"),
         "La crosta del formaggio è {x}."),
    ]

    # STRUTTURA DELLA PASTA ----------------------------------------------
    R["Struttura della Pasta"] = [
        (re.compile(rf"^La pasta presenta (.+?){PUNCT}$"),
         "La pasta del formaggio presenta {x}."),
        (re.compile(rf"^La pasta mostra (.+?){PUNCT}$"),
         "La pasta del formaggio mostra {x}."),
        (re.compile(rf"^Pasta con (.+?){PUNCT}$"),
         "La pasta del formaggio presenta {x}."),
        (re.compile(rf"^Pasta a grana (.+?){PUNCT}$"),
         "La pasta del formaggio è a grana {x}."),
        (re.compile(rf"^Pasta tipo (.+?){PUNCT}$"),
         "La pasta del formaggio è di tipo {x}."),
        (re.compile(rf"^Pasta non (.+?){PUNCT}$"),
         "La pasta del formaggio non è {x}."),
        (re.compile(rf"^Pasta (.+?){PUNCT}$"),
         "La pasta del formaggio è {x}."),
    ]

    # COLORE DELLA PASTA -------------------------------------------------
    R["Colore della Pasta"] = [
        (re.compile(rf"^La pasta presenta (.+?){PUNCT}$"),
         "La pasta del formaggio presenta {x}."),
        (re.compile(rf"^Pasta di colore (.+?){PUNCT}$"),
         "La pasta del formaggio è di colore {x}."),
        (re.compile(rf"^Pasta con (.+?){PUNCT}$"),
         "La pasta del formaggio presenta {x}."),
        (re.compile(rf"^Pasta dal colore (.+?){PUNCT}$"),
         "La pasta del formaggio è dal colore {x}."),
        (re.compile(rf"^Pasta a colori (.+?){PUNCT}$"),
         "La pasta del formaggio è a colori {x}."),
        (re.compile(rf"^Colore della pasta:?\s+(.+?){PUNCT}$", re.IGNORECASE),
         "La pasta del formaggio è di colore {x}."),
        (re.compile(rf"^Pasta non (.+?){PUNCT}$"),
         "La pasta del formaggio non è {x}."),
        (re.compile(rf"^Pasta (.+?){PUNCT}$"),
         "La pasta del formaggio è {x}."),
    ]
    return R


# ---------------------------------------------------------------------------
# Prefix canonicalisation. The LLM occasionally produced captions with a
# different opening than the attribute name (e.g. "Note olfattive vegetali …"
# instead of "Profumo vegetale …"). Rather than handling those with extra
# regex rules, normalise them upfront so the standard "Profumo …" / "Aroma
# di …" rules apply.
# ---------------------------------------------------------------------------

CANONICALISE: dict[str, list[tuple[re.Pattern, str]]] = {
    # Profumo — "Note olfattive vegetali, balsamiche e di X" → "Profumo X"
    "Profumo": [
        (re.compile(r"^Note olfattive vegetali di (.+)$", re.I), r"Profumo vegetale di \1"),
        (re.compile(r"^Note olfattive vegetali,?\s*(.+)$", re.I), r"Profumo vegetale, \1"),
        (re.compile(r"^Note olfattive (.+)$", re.I), r"Profumo \1"),
    ],
    # Aroma — "Note di X" / "Note aromatiche X" → "Aroma di X" / "Aroma X"
    "Aroma": [
        (re.compile(r"^Note aromatiche di (.+)$", re.I), r"Aroma di \1"),
        (re.compile(r"^Note aromatiche (.+)$", re.I), r"Aroma \1"),
        (re.compile(r"^Note di (.+)$", re.I), r"Aroma di \1"),
    ],
}


def canonicalise(caption: str, attribute: str) -> str:
    """Rewrite alternate prefixes to the canonical attribute prefix."""
    if not caption:
        return caption
    for pat, repl in CANONICALISE.get(attribute, []):
        new = pat.sub(repl, caption.strip())
        if new != caption:
            # ensure trailing period
            if not new.endswith((".", "!", "?")):
                new = new + "."
            return new
    return caption


def transform(caption: str, attribute: str, rules: dict) -> str | None:
    """Return sentence-form caption, or None if no rule matched."""
    if not caption:
        return None
    for pat, tmpl in rules.get(attribute, []):
        m = pat.match(caption.strip())
        if m:
            x = m.group(1).strip()
            # avoid double spaces
            return tmpl.format(x=x).replace("  ", " ")
    return None


# ---------------------------------------------------------------------------
# Polish pass — fix grammatical glitches introduced by the regex templates.
# ---------------------------------------------------------------------------

# Italian sensory/structural nouns by gender — SINGULAR forms only.
# Used to inject the indefinite article after "presenta" when the source
# had `<attr> con <bare singular noun>`. Plurals never take an indefinite
# article in Italian, so they go in NOUNS_PLURAL and we leave them alone.
NOUNS_F = {
    "macchia", "zona", "area", "fascia", "striscia", "sfumatura",
    "stiratura", "impugnatura", "fessura", "frattura", "microocchiatura",
    "occhiatura", "spaccatura", "disidratazione", "ossidazione",
    "presenza", "grana", "tirosina", "sottocrosta", "parte", "faccia",
    "granulosità", "struttura", "microstruttura", "scaglia", "rottura",
    "muffa", "tara", "anomalia", "consistenza", "umidità", "porzione",
}
NOUNS_M = {
    "alone", "spessore", "colore", "spacco", "occhio", "sottopiatto",
    "scalzo", "accenno", "sentore", "profilo", "limite", "contrasto",
    "bordo", "ingresso", "taglio", "spigolo", "angolo", "lato",
    "piatto", "aspetto", "difetto", "siero",
}
NOUNS_PLURAL = {
    "macchie", "zone", "aree", "fasce", "strisce", "sfumature",
    "stirature", "fessure", "fratture", "microocchiature", "occhiature",
    "spaccature", "parti", "facce", "scaglie", "rotture", "muffe",
    "anomalie", "porzioni", "consistenze",
    "aloni", "spessori", "colori", "spacchi", "occhi", "sottopiatti",
    "scalzi", "accenni", "sentori", "profili", "limiti", "contrasti",
    "bordi", "ingressi", "tagli", "spigoli", "angoli", "lati", "piatti",
    "aspetti", "difetti", "granuli",
}

# Words that are already a determiner — never inject an article in front
DETERMINERS = {
    "un", "una", "un'", "uno", "il", "lo", "la", "i", "gli", "le",
    "qualche", "molti", "molte", "diversi", "diverse",
    "tanti", "tante", "pochi", "poche", "altri", "altre", "altre",
    "tantissimi", "tantissime", "alcuni", "alcune", "vari", "varie",
}


def _article_for(noun: str) -> str | None:
    n = noun.lower().rstrip(",.;:!?")
    if n in NOUNS_PLURAL:
        return None  # plurals don't take an indefinite article
    if n in NOUNS_F:
        return "un'" if n[:1] in "aeiou" else "una"
    if n in NOUNS_M:
        if n[:1] == "z":
            return "uno"
        if n[:1] == "s" and len(n) > 1 and n[1] not in "aeiou":
            return "uno"
        if n[:1] in "aeiou":
            return "un"
        return "un"
    return None


def _fix_presenta(text: str) -> str:
    """Inject indefinite article after 'presenta ' when followed by a
    bare singular noun (or adjective + noun) without one."""

    def fix_match(m: re.Match) -> str:
        tail = m.group(1)
        words = re.findall(r"\S+", tail)
        if not words:
            return m.group(0)
        first = words[0].lower().rstrip(",.;:")
        if first in DETERMINERS:
            return m.group(0)
        # If first word is a known plural noun, leave it alone — plurals
        # don't take the indefinite article and we shouldn't fall through
        # to look at the second word in this case.
        if first in NOUNS_PLURAL:
            return m.group(0)
        # Try first word as the noun
        art = _article_for(first)
        if art:
            sep = "" if art.endswith("'") else " "
            return f"presenta {art}{sep}{tail}"
        # Try second word as the noun (first looks like an adjective).
        # Only if the FIRST word ends in a typical adjective inflection
        # (-o/-a/-e/-i) AND isn't itself a known noun in any list.
        if len(words) >= 2 and first[-1:] in "oaei":
            second = words[1].lower().rstrip(",.;:")
            if second in DETERMINERS or second in NOUNS_PLURAL:
                return m.group(0)
            art = _article_for(second)
            if art:
                sep = "" if art.endswith("'") else " "
                return f"presenta {art}{sep}{tail}"
        return m.group(0)

    # Match `presenta <X>` where X is everything until end of sentence
    return re.sub(r"\bpresenta\s+(.+?)(?=\.\s*$|$)", fix_match, text)


def polish(sentence: str) -> str:
    """Apply post-template polish fixes."""
    if not sentence:
        return sentence
    s = sentence
    # 1. inject missing article after "presenta"
    s = _fix_presenta(s)
    # 2. "è dal colore X" → "è di colore X"
    s = re.sub(r"\bè dal colore\b", "è di colore", s)
    # 3. "è dalla <noun>" — replace with "presenta una/un' <noun>" by gender,
    #    falling back to leaving alone if noun unknown
    def _fix_dalla(m):
        word = m.group(1).lower().rstrip(",.;:")
        art = _article_for(word)
        if art is None and word.endswith("ità"):
            # Italian -ità nouns are always feminine
            art = "un'" if word[:1] in "aeiou" else "una"
        if art and art in ("una", "un'"):
            sep = "" if art.endswith("'") else " "
            return f"presenta {art}{sep}{m.group(1)}"
        # Last resort: re-frame as "presenta una caratteristica di X"
        # leaving alone for now if unknown
        return m.group(0)
    # Allow optional adjective between "dalla" and the noun
    # ("Pasta dalla buona grandiosità" → polish reach the noun)
    s = re.sub(r"\bè dalla (?:\w+\s+)?(\w+ità\b)", _fix_dalla, s)
    s = re.sub(r"\bè dalla (\w+)", _fix_dalla, s)
    # 4. "è unghia" → "presenta un'unghia"
    s = re.sub(r"\bè unghia\b", "presenta un'unghia", s)
    # 5. Italian elision: any "una <vowel-starting word>" → "un'<word>"
    #    (standard rule; safe because we only inject "una" before known
    #    feminine nouns / their modifiers).
    s = re.sub(r"\buna ([aeiouAEIOU]\w+)", r"un'\1", s)
    # collapse any introduced double spaces
    s = re.sub(r"\s{2,}", " ", s)
    return s


def main() -> None:
    rules = make_rules()
    rows = list(csv.DictReader(SRC.open()))
    in_cols = list(rows[0].keys()) if rows else []

    # Apply transformation per row
    n_matched = n_unmatched = 0
    unmatched_unique: dict[tuple[str, str], int] = {}
    by_attr_match = Counter()
    by_attr_total = Counter()

    n_canonicalised = 0
    for r in rows:
        attr = r["attribute"]
        cap = r["caption"]
        cap_canon = canonicalise(cap, attr)
        if cap_canon != cap:
            r["caption"] = cap_canon
            cap = cap_canon
            n_canonicalised += 1
        by_attr_total[attr] += 1
        sent = transform(cap, attr, rules)
        if sent is None:
            r["caption_sentence"] = ""
            n_unmatched += 1
            unmatched_unique[(attr, cap)] = unmatched_unique.get((attr, cap), 0) + 1
        else:
            r["caption_sentence"] = polish(sent)
            n_matched += 1
            by_attr_match[attr] += 1

    # Write back captions_final.csv with new column
    out_cols = in_cols + ["caption_sentence"] if "caption_sentence" not in in_cols else in_cols
    with SRC.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Save unmatched unique captions for the LLM pass
    with UNMATCHED.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["attribute", "caption", "frequency"])
        w.writeheader()
        for (attr, cap), freq in sorted(unmatched_unique.items(),
                                         key=lambda x: -x[1]):
            w.writerow({"attribute": attr, "caption": cap, "frequency": freq})

    print(f"rows total      : {len(rows)}")
    print(f"prefix-canonicalised: {n_canonicalised}")
    print(f"matched         : {n_matched} ({100*n_matched/len(rows):.1f}%)")
    print(f"unmatched       : {n_unmatched} ({100*n_unmatched/len(rows):.1f}%)")
    print(f"unique unmatched: {len(unmatched_unique)}")
    print()
    print("per-attribute match rate:")
    for a in sorted(by_attr_total):
        m = by_attr_match[a]
        t = by_attr_total[a]
        print(f"  {a:30s} {m:6d}/{t:6d}  ({100*m/t:.1f}%)")
    print()
    print(f"wrote {SRC} (added caption_sentence column)")
    print(f"wrote {UNMATCHED} ({len(unmatched_unique)} unique to LLM-rewrite)")


if __name__ == "__main__":
    main()
