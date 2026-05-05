"""Prompt builder for the LLM caption rewrite step.

For each of the 7 sensory attributes we render a system prompt that combines:
  • a fixed style template (so all rewrites converge on a uniform shape)
  • the controlled vocabulary derived from the corpus (top-N lemmas)
  • the most frequent multi-word idioms (top bigrams)
  • the explicit cleaning rules from the project brief
  • few-shot examples drawn from real captions in the dataset

The prompt is written in Italian — the model will be working in Italian
end-to-end, so the instructions match the target language.

Usage:
    from rewrite_prompt import build_system_prompt, build_user_prompt
    sys = build_system_prompt("Profumo")
    usr = build_user_prompt("Profumo", "Crauti")

`render_for_review.py` (next file) writes one rendered prompt per attribute
to disk so they can be eyeballed before any API calls.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese")
VOCAB_DIR = ROOT / "data" / "vocabulary"

# ---------------------------------------------------------------------------
# Per-attribute style templates and few-shot examples.
# Examples were chosen from `data/captions_unique.csv` to cover the hard
# cases: telegraphic single words, negations, hedges, interrogatives, mixed
# meta + descriptor, embedded measurements, and the controlled-vocabulary
# style we want the rewrite to converge on.
# ---------------------------------------------------------------------------

ATTRIBUTE_CONFIG: dict[str, dict] = {
    "Profumo": {
        "intro": "Profumo del formaggio (impressioni olfattive all'apertura/al naso).",
        "template": "Una frase che inizia con \"Profumo …\" o \"Note olfattive di …\".",
        "examples": [
            ("Crauti", "Profumo di crauti."),
            ("burro fresco, note lattiche prevalenti, poco complesso",
             "Profumo di burro fresco con note lattiche prevalenti, poco complesso."),
            ("Non molto intenso", "Profumo poco intenso."),
            ("Eucalipto?", "Note olfattive di eucalipto."),
            ("Lievito pane?", "Note olfattive di lievito e pane."),
            ("leg di stantio", "Profumo leggermente stantio."),
        ],
    },
    "Aroma": {
        "intro": "Aroma del formaggio (impressioni retro-olfattive in bocca).",
        "template": "Una frase che inizia con \"Aroma …\" o \"Note aromatiche …\".",
        "examples": [
            ("Leggero", "Aroma leggero."),
            ("complesso, gradevole, note caratteristiche affiancate a note meno tipiche fermentate",
             "Aroma complesso e gradevole con note caratteristiche e note fermentate atipiche."),
            ("Sa di malga", "Aroma di malga."),
            ("non tipico del grana", "Aroma non tipico del grana."),
            ("Yogurt", "Aroma di yogurt."),
            ("Burro fresco, note lattiche prevalenti, poco complesso",
             "Aroma di burro fresco con note lattiche prevalenti, poco complesso."),
        ],
    },
    "Sapore": {
        "intro": "Sapore del formaggio (impressioni gustative in bocca).",
        "template": "Una frase che inizia con \"Sapore …\" o \"Al palato …\".",
        "examples": [
            ("Leggermente acido", "Sapore leggermente acido."),
            ("Forse troppo sapido....ma anche note dolci",
             "Sapore eccessivamente sapido con note dolci."),
            ("amaro deciso e penalizzante", "Sapore amaro e deciso."),
            ("leg amaro", "Sapore leggermente amaro."),
            ("Non equilibrato salato", "Sapore non equilibrato e salato."),
            ("Bella persistenza", "Sapore con buona persistenza."),
        ],
    },
    "Texture": {
        "intro": "Texture del formaggio (sensazioni tattili in bocca: solubilità, friabilità, umidità, presenza di cristalli).",
        "template": "Una frase che inizia con \"Texture …\" o \"In bocca …\".",
        "examples": [
            ("Tenero", "Texture tenera."),
            ("non molto solubile", "Texture poco solubile."),
            ("Quasi troppi cristalli...", "Texture con cristalli abbondanti."),
            ("granulosa, giustamente umida, solubile",
             "Texture granulosa, giustamente umida e solubile."),
            ("potrebbe essere più friabile", "Texture poco friabile."),
            ("Impasta la bocca", "Texture che impasta la bocca."),
        ],
    },
    "Spessore della Crosta": {
        "intro": "Spessore e regolarità della crosta (zone piatte, scalzo, spigoli, sottocrosta).",
        "template": "Una frase che inizia con \"Crosta …\" o \"La crosta presenta …\".",
        "extra_rules": (
            "TABELLA DI CONVERSIONE MISURA → QUALITATIVO (applicare quando "
            "l'annotazione contiene misurazioni di spessore della crosta):\n"
            "  • < 8 mm  o < 0,8 cm   → \"molto sottile\"\n"
            "  • 8-9 mm  o 0,8-0,9 cm → \"sottile\"\n"
            "  • 10-13 mm o 1,0-1,3 cm → \"mediamente spessa\" / \"spessore medio\"\n"
            "  • 14-17 mm o 1,4-1,7 cm → \"spessa\"\n"
            "  • ≥ 18 mm o ≥ 1,8 cm    → \"molto spessa\"\n"
            "Nota: \"1 cm\" = \"10 mm\" = \"mediamente spessa\". Mantieni la "
            "stessa qualifica per valori equivalenti espressi in mm o cm."
        ),
        "examples": [
            ("Sottile", "Crosta sottile."),
            ("Spigoli sopra 20mm Piatto 10mm circa Media 12mm",
             "Crosta con spigoli pronunciati, parte piatta mediamente spessa e spessore medio."),
            ("1 cm ma di colore molto contrastato",
             "Crosta mediamente spessa, di colore molto contrastato."),
            ("Alto spessore", "Crosta spessa."),
            ("Non regolare", "Crosta irregolare."),
            ("Sottocrosta confonde", "Crosta con sottocrosta poco distinguibile."),
        ],
    },
    "Struttura della Pasta": {
        "intro": "Struttura e omogeneità della pasta (frattura, occhiatura, fessure, granulosità, distribuzione spaziale).",
        "template": "Una frase che inizia con \"Pasta …\" o \"La pasta presenta …\".",
        "examples": [
            ("Fessure enormi", "Pasta con fessure pronunciate."),
            ("1 fessura e un piccolo occhio",
             "Pasta con una fessura e una piccola occhiatura."),
            ("Fine è stirata in centro grossolana verso scalzo",
             "Pasta fine e stirata al centro, grossolana verso lo scalzo."),
            ("Non omogenea ma granulosa", "Pasta non omogenea ma granulosa."),
            ("microocchiatura diffusa centrale",
             "Pasta con microocchiatura diffusa al centro."),
            ("Setata??", "Pasta dall'aspetto setato."),
        ],
    },
    "Colore della Pasta": {
        "intro": "Colore e uniformità della pasta (alone, macchie, omogeneità, sfumature).",
        "template": "Una frase che inizia con \"Pasta di colore …\" o \"Colore della pasta …\".",
        "examples": [
            ("Macchia alone centrale rosato",
             "Pasta con macchia e alone centrale rosato."),
            ("Solo leggero alone...", "Pasta con leggero alone."),
            ("Aree non belle come colore",
             "Pasta con aree di colore non uniforme."),
            ("Forse più chiaro dove è fitta la microocchiatura",
             "Pasta più chiara nelle zone di fitta microocchiatura."),
            ("Giallo carico", "Pasta di colore giallo carico."),
            ("Non paglierino, ma chiaro",
             "Pasta non paglierina ma di colore chiaro."),
        ],
    },
}

# ---------------------------------------------------------------------------
# Vocabulary loaders
# ---------------------------------------------------------------------------

VOCAB_TOP_N = 60
BIGRAM_TOP_N = 20

# Curated multi-word idioms per attribute. Sourced from the bigram files
# but filtered to drop co-occurrence artifacts (e.g. "panna burro" appears
# in the data because panelists comma-separate lists, not because it's a
# fixed expression). Only genuine fixed phrases / idiomatic descriptor
# pairs go here. The unfiltered bigram files remain in the repo for
# reference.
CURATED_BIGRAMS: dict[str, list[str]] = {
    "Profumo": [
        "latte cotto", "panna cotta", "burro fuso", "burro fresco",
        "brodo vegetale", "brodo animale", "frutta secca",
        "burro sciolto", "intensità moderata", "nota lattica",
        "all'apertura", "lattico cotto",
    ],
    "Aroma": [
        "latte cotto", "panna cotta", "burro fuso", "frutta secca",
        "brodo vegetale", "brodo animale", "nota lattica",
        "burro fresco", "frutta fermentata", "lattico cotto",
    ],
    "Sapore": [
        "leggermente piccante", "leggermente salato", "leggermente acido",
        "leggermente amaro", "dolce sapido", "amaro persistente",
        "salato umami", "umami medio", "buona persistenza",
        "salato piccante",
    ],
    "Texture": [
        "leggermente asciutto", "molto solubile", "molto friabile",
        "morbido pastoso", "cristalli abbondanti", "cristalli fini",
        "leggermente sabbioso", "tirosina presente", "lascia bocca",
        "poco solubile", "scioglie bocca",
    ],
    "Spessore della Crosta": [
        "spigoli pronunciati", "spigoli marcati", "crosta sottile",
        "crosta spessa", "crosta regolare", "crosta sfumata",
        "sottocrosta evidente", "spessore medio", "parte piatta",
        "crosta unghia",
    ],
    "Struttura della Pasta": [
        "frattura regolare", "frattura irregolare", "micro occhiatura",
        "microocchiatura diffusa", "bella grana", "grana grossolana",
        "grana fine", "pasta stirata", "zona centrale", "parte centrale",
        "fessure profonde", "leggera stiratura",
    ],
    "Colore della Pasta": [
        "alone centrale", "giallo carico", "giallo paglierino",
        "macchia rosata", "alone rosato", "colore omogeneo",
        "colore uniforme", "fascia chiara", "leggero alone",
        "tendente al giallo",
    ],
}


_VOCAB_BLACKLIST = {"all'apertura"}


def _load_vocab(attr: str) -> list[str]:
    path = VOCAB_DIR / f"{attr.replace(' ', '_')}.txt"
    out: list[str] = []
    with path.open() as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                lemma = parts[1].strip()
                if lemma in _VOCAB_BLACKLIST:
                    continue
                out.append(lemma)
            if len(out) >= VOCAB_TOP_N:
                break
    return out


def _load_bigrams(attr: str) -> list[str]:
    """Return the manually curated idiom list for the attribute.

    The raw bigram files in `data/vocabulary/` contain co-occurrence
    artifacts (e.g. "panna burro" from comma-separated panelist lists)
    that shouldn't be presented to the LLM as fixed expressions. Use the
    hand-picked CURATED_BIGRAMS instead.
    """
    return list(CURATED_BIGRAMS.get(attr, []))


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

RULES_BLOCK = """\
REGOLE OBBLIGATORIE:
1.  CONSERVA tutte le informazioni sensoriali pertinenti all'attributo
    dichiarato: descrittori, intensità, posizione spaziale, eventuali
    negazioni. Se l'annotazione include osservazioni che riguardano un
    altro attributo (es. una nota di profumo dentro un commento sulla
    texture), ignorale.
2.  CONVERTI ogni descrizione QUANTITATIVA (mm, cm, percentuali, valori
    numerici, intervalli) nella corrispondente forma QUALITATIVA. Le
    didascalie finali NON devono mai contenere numeri o unità di misura.
3.  ESPANDI le abbreviazioni: leg./legg. = leggermente; po'/po = poco;
    abb. = abbastanza; tend. = tendente.
4.  RIFORMULA in italiano standard frasi telegrafiche, dialettali o di
    registro colloquiale, mantenendo lo stile naturale e compatto.
5.  RIDUCI i sinonimi al lessico tipico dell'attributo (vedi sotto):
    quando una parola del testo originale ha un equivalente nel lessico,
    preferisci quest'ultimo.
6.  ZERO INVENZIONE. Vietato introdurre descrittori sensoriali assenti
    dall'annotazione originale: niente giudizi, niente intensità, niente
    aggettivi di tipicità ("tipico", "caratteristico"), niente
    qualificatori ("presente", "evidente") che non compaiano nella
    sorgente. È ammesso solo riformulare ciò che è già presente. Se non
    c'è alcun descrittore valido, applica la regola 11.
7.  RIMUOVI tutto ciò che non descrive il formaggio: giudizi di
    gradimento puri ("buono", "brutto", "ottimo"), riferimenti al voto o
    al punteggio, commenti meta sul panelista o sulla seduta. Mantieni
    invece le negazioni descrittive ("Non paglierino" → "non paglierina").
8.  TRASFORMA le domande in affermazioni descrittive: "Eucalipto?" →
    "Note di eucalipto." Le esclamazioni vanno appiattite ("!!!" non
    devono comparire).
9.  LUNGHEZZA: una sola frase, naturalmente in italiano, il più concisa
    possibile rispetto al contenuto dell'annotazione (annotazioni di una
    sola parola → didascalie di 2-4 parole; annotazioni più ricche →
    fino a circa 18 parole). Inizia con maiuscola, termina con punto.
10. NON aggiungere virgolette, prefissi, suffissi né spiegazioni: l'output
    è SOLO la frase riscritta (oppure il singolo token NON_DESCRITTO,
    vedi regola 11).
11. ESCAPE PER ANNOTAZIONI VUOTE. Output ESATTAMENTE la stringa
    "NON_DESCRITTO" (tutta maiuscola, senza punto, senza virgolette)
    SOLO se l'annotazione, dopo le regole 1 e 7, non contiene ALCUN
    descrittore sensoriale: nessun aggettivo qualitativo (es. marcio,
    putrido, anonimo, elegante, scarno, difettoso, complesso, piacevole,
    sgradevole, intenso, leggero, debole, persistente, aromatico,
    fruttato, vegetale, ecc.), nessun riferimento a una sostanza/nota
    olfattivo-gustativa (es. sangue, polvere, plastica, fieno, carne,
    formaggio, latte, ecc.), nessuna intensità, nessun cenno di posizione.
    REGOLA OPERATIVA: se anche UNA sola parola della sorgente è un
    descrittore valido — anche mescolata con giudizi puri o meta —
    NON usare l'escape: estrai quel descrittore e scrivi la didascalia
    su quello, ignorando il resto. Esempi:
      "marcio, putrido,"           → "Profumo marcio e putrido."
      "Strano. Sentiva di pesce."  → "Profumo strano, di pesce."
      "Sangue,,,"                  → "Aroma di sangue."
      "Anonimo"                    → "Aroma anonimo."
    Usa NON_DESCRITTO solo per: commenti puri sulla seduta/sistema,
    note di scoring senza descrittori, frasi incomplete senza alcuna
    parola sensoriale, o annotazioni interamente su un altro attributo.
"""


def build_system_prompt(attribute: str) -> str:
    cfg = ATTRIBUTE_CONFIG[attribute]
    vocab = _load_vocab(attribute)
    bigrams = _load_bigrams(attribute)
    extra = cfg.get("extra_rules")

    examples_block = "\n".join(
        f'  Annotazione: "{src}"\n  Didascalia : "{tgt}"'
        for src, tgt in cfg["examples"]
    )

    extra_block = f"\n{extra}\n" if extra else ""

    return f"""\
Sei un esperto di analisi sensoriale del Trentingrana, formaggio grana
stagionato del Trentino. Il tuo compito è riscrivere brevi annotazioni di
panelisti italiani in didascalie chiare, naturali e di stile uniforme,
adatte a descrivere un'immagine di una sezione del formaggio.

ATTRIBUTO: {attribute} — {cfg['intro']}

STILE: {cfg['template']}

{RULES_BLOCK}{extra_block}
LESSICO TIPICO PER QUESTO ATTRIBUTO (preferisci questi termini quando
applicabili, ma non forzarli se l'annotazione non li suggerisce):
  {", ".join(vocab)}

ESPRESSIONI MULTI-PAROLA TIPICHE (mantieni invariate quando presenti):
  {", ".join(bigrams)}

ESEMPI ({len(cfg['examples'])} casi reali del dataset):
{examples_block}
"""


def build_user_prompt(attribute: str, caption: str) -> str:
    return (
        f'Riscrivi questa annotazione in una didascalia per il tag "{attribute}", '
        f"seguendo le regole.\n"
        f'ANNOTAZIONE: "{caption}"\n'
        f"DIDASCALIA:"
    )


if __name__ == "__main__":
    # quick sanity render to stdout
    import sys
    attr = sys.argv[1] if len(sys.argv) > 1 else "Profumo"
    print(build_system_prompt(attr))
    print("---")
    print(build_user_prompt(attr, "Crauti"))
