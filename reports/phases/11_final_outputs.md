# Fase 10 — Broadcast finale + sentence form + deliverables

**Script** (in pipeline):
1. `broadcast_captions.py` — broadcast del caption pulito sul training set
2. `make_sentence_form.py` — aggiunta colonna sentence form
3. `build_final_outputs.py` — generazione deliverables finali

## Input
- `data/intermediate/captions_pre_filtered.csv` (39.280 righe broadcast target, output Fase 5)
- `data/rewrites/rewrites_<attribute>.csv` × 7 (caption pulite + salvage, output Fasi 8-9)

## Output
- `data/final/captions_final.csv` — 38.437 righe, 18 colonne (incluso `caption_sentence`)
- `data/final/image_caption_attribute.csv` — versione semplificata 4 colonne
- `data/final/by_attribute/<Attribute>.csv` × 7 — split per attributo
- `data/final/README.md` — documentation
- `data/intermediate/sentence_form_unmatched.csv` — caption non template-match (zero in pratica)
- `data/reports/captions_final_report.txt`

## Cosa fa la fase

### A. Broadcast (`broadcast_captions.py`)

1. **Costruisce lookup** `dedup_key → caption_clean` unendo i 7 CSV per attributo:
   ```python
   lookup: dict[str, str] = {}
   for attr, fname in ATTR_FILES.items():
       for r in csv.DictReader(open(REWRITES_DIR / fname)):
           lookup[r["dedup_key"]] = r["caption_clean"]
   ```

2. **Walk** del `captions_pre_filtered.csv` (39.280 righe broadcast target)
3. Per ogni riga:
   - Lookup del clean via `dedup_key`
   - **Drop se** `caption_clean == "NON_DESCRITTO"` (post-salvage)
   - Altrimenti scrittura nel CSV finale con tutte le metadata + `caption` aggiunta
4. **Output**: 38.437 righe (97,9% retention; 843 droppate come `NON_DESCRITTO`)

### B. Sentence form (`make_sentence_form.py`)

Aggiunge una colonna `caption_sentence` che trasforma la caption compatta in frase italiana dichiarativa completa.

#### B.1 Prefix canonicalisation

Map per attributo che riscrive prefissi alternativi prodotti occasionalmente dal LLM:

```python
CANONICALISE: dict[str, list[tuple[Pattern, str]]] = {
    "Profumo": [
        (r"^Note olfattive vegetali di (.+)$", r"Profumo vegetale di \1"),
        (r"^Note olfattive vegetali,?\s*(.+)$", r"Profumo vegetale, \1"),
        (r"^Note olfattive (.+)$", r"Profumo \1"),
    ],
    "Aroma": [
        (r"^Note aromatiche di (.+)$", r"Aroma di \1"),
        (r"^Note aromatiche (.+)$", r"Aroma \1"),
        (r"^Note di (.+)$", r"Aroma di \1"),
    ],
}
```

**94 righe** toccate dalla canonicalisation.

#### B.2 Template substitution

Per ogni attributo, lista ordinata di `(pattern, template)`. Esempio Profumo:

```python
(r"^Profumo di (.+?)\.?$", "Il formaggio ha un profumo di {x}.")
(r"^Profumo con (.+?)\.?$", "Il formaggio ha un profumo con {x}.")
(r"^Note olfattive di (.+?)\.?$", "Il formaggio presenta note olfattive di {x}.")
(r"^Profumo (.+?)\.?$", "Il formaggio ha un profumo {x}.")  # fallback
```

Pattern fallback (più generico) sempre ultimo. **First match wins.**

**Risultato**: 100% template match su tutte le 38.437 righe — zero unmatched, zero LLM round-trip necessario.

Esempi per attributo:

| Compact (`caption`) | Sentence (`caption_sentence`) |
|---|---|
| `Profumo di panna.` | `Il formaggio ha un profumo di panna.` |
| `Profumo poco intenso.` | `Il formaggio ha un profumo poco intenso.` |
| `Aroma di latte cotto.` | `Il formaggio ha un aroma di latte cotto.` |
| `Sapore equilibrato.` | `Il formaggio ha un sapore equilibrato.` |
| `Texture asciutta.` | `Il formaggio presenta una texture asciutta.` |
| `Crosta sottile.` | `La crosta del formaggio è sottile.` |
| `Pasta granulosa.` | `La pasta del formaggio è granulosa.` |
| `Pasta di colore omogeneo.` | `La pasta del formaggio è di colore omogeneo.` |

#### B.3 Polish pass

Fix grammaticali post-template:

1. **Article injection dopo `presenta`**: `presenta alone` → `presenta un alone`
   - Mappe sostantivi sensoriali con genere:
     - `NOUNS_F` (~30 femminili): `macchia`, `zona`, `area`, `fascia`, `striscia`, `sfumatura`, `fessura`, `frattura`, `microocchiatura`, ecc.
     - `NOUNS_M` (~25 maschili): `alone`, `spessore`, `colore`, `occhio`, `scalzo`, `accenno`, `sentore`, ecc.
     - `NOUNS_PLURAL` (~40 plurali): `macchie`, `zone`, `fessure`, `occhi`, ecc. — non prendono articolo indefinito in italiano
   - `DETERMINERS` set per evitare doppio articolo
2. **`è dal colore X`** → **`è di colore X`** (forma più naturale)
3. **`è dalla X`** → **`presenta una X`** / **`presenta un'X`** per nomi femminili (incluso famiglia `-ità` sempre femminile)
4. **`è unghia`** → **`presenta un'unghia`** (case-specific)
5. **Elisione italiana**: `una <vowel>` → `un'<vowel>` ovunque (regola standard)
6. **Collapse doppi spazi** introdotti da regex

### C. Build final outputs (`build_final_outputs.py`)

Produce 4 deliverables:

1. **`captions_final.csv`** — full table (38.437 × 18 colonne)
2. **`image_caption_attribute.csv`** — simplified 4 colonne (`image_path, attribute, caption, caption_sentence`)
3. **`by_attribute/<Attribute>.csv`** × 7 — split per attributo (formato simplified)
4. **`README.md`** — explainer per downstream users

## Scelte chiave e motivazione

### Broadcast

| Scelta | Motivazione |
|---|---|
| **Lookup dict da 7 CSV separati** | Allinea con la struttura per-attributo del Fase 8; merge esplicito traccia provenance |
| **Drop `NON_DESCRITTO` al broadcast (non prima)** | Permette audit completo del dataset post-LLM e post-salvage prima di applicare il drop finale |
| **Schema output con `caption_raw`, `caption_pre`, `caption`** | Mantiene 4 livelli di provenance per ogni riga: raw → pre → caption (compact) → sentence (full) |

### Sentence form

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Sentence form via regex deterministica, non LLM** | 100% template match → costo $0; auditabile; idempotente; nessun rischio di hallucination | Secondo round LLM = $5+ + non-determinismo + rischio di drift |
| **Doppia colonna `caption` + `caption_sentence`** | Compatto per per-attribute models; sentence per BLEU/METEOR/CIDEr (metriche standard captioning lavorano meglio su frasi naturali che su noun phrases) | Solo sentence avrebbe perso flessibilità |
| **Prefix canonicalisation come step separato** | Permette regole di template più semplici e uniformi a valle | Pattern complessi nel template avrebbero esploso il set |
| **First-match-wins ordering** | Pattern specifici (`Profumo di X`, `Profumo con X`) prima di generici (`Profumo X`) | Reverse order avrebbe matchato sempre il generico, perdendo specificità |
| **Mappe NOUNS_F/M/PLURAL hand-crafted** | Italian gender rules sono complesse; lista chiusa con ~50 nomi è esaustiva per il dominio sensoriale | Generic gender detection (es. `-a` → femminile) sbaglia su `tema`, `problema`, `aroma` |
| **Polish pass come funzioni separate** (`_fix_presenta`, `_fix_dalla`, `_fix_unghia`, ecc.) | Ogni fix è auditabile, testabile, reversibile | Single regex monstre = unmaintainable |
| **Famiglia `-ità` hard-coded come femminile** | Tutti i sostantivi italiani in `-ità` sono femminili, sempre | Lookup a runtime = overhead inutile |
| **Salva `sentence_form_unmatched.csv`** | Anche se 100% match ora, future caption potrebbero non match → audit trail per regression detection | Senza file, regression detection diventa impossibile |
| **Elisione `una <vowel>` → `un'<vowel>` come regola finale** | Standard italiano; safe perché `una` è iniettato solo prima di femminili noti | Manuale prima di ogni vocale = 50+ casi |
| **`è` polish manuale per `dalla`/`dal`** | Forme awkward del LLM (`è dalla microocchiatura`) richiedono ristrutturazione (`presenta una microocchiatura`) | Lasciare le forme awkward = output sgrammaticato |

### Build outputs

| Scelta | Motivazione |
|---|---|
| **Tre livelli di granularità** (full / simplified / per-attribute) | Diverse architetture downstream hanno preferenze diverse |
| **`image_path_flat` come `image_path` nei deliverable** | Path stabile, niente collisioni, consumabile direttamente |
| **README italiano** | Lingua del progetto e del dataset |
| **Tabella per-attribute counts** in README | Informazione critica per chi usa il dataset |

## Problemi evitati

### Broadcast

- **Caption non joinable**: ogni `dedup_key` deve avere lookup; il check `if clean is None: skip` previene crash su mancati match
- **Drift tra `pre_filtered` e `rewrites`**: il `dedup_key` è la chiave canonica calcolata in Fase 4 → garantisce join coerente

### Sentence form

- **Round LLM da $5+** per task puramente sintattico
- **Inconsistenza grammaticale**: senza polish, `presenta alone` (manca articolo), `è dalla microocchiatura` (forma awkward), `è unghia` (sgrammaticato)
- **Elisione mancante**: `una unghia` invece di `un'unghia`
- **False gender agreement**: lista chiusa `NOUNS_F`/`NOUNS_M` evita assunzioni errate su nomi non standard
- **Plurali con articolo indefinito**: `presenta una occhiature` (errore comune); `NOUNS_PLURAL` preserva la forma corretta `presenta occhiature`
- **Loss di provenance**: `caption` resta nel CSV insieme a `caption_sentence`; nessuna sostituzione

### Final outputs

- **Path inconsistencies**: tutti gli script usano `Path(__file__).resolve().parent` → portabilità tra macchine
- **Hard-coded paths**: nessuno; tutto relativo a `data/`
- **Incompletezza dei deliverable**: README esplicita schema, conteggi, location, intended use

## Statistiche output

### Broadcast

- **Input**: 39.280 righe (Fase 5 filtrato)
- **Output**: 38.437 righe (97,9%)
- **Drop**: 843 righe come `NON_DESCRITTO` (2,1%)

### Sentence form

- **Input**: 38.437 righe
- **Prefix-canonicalised**: 94 righe
- **Template-matched**: 38.437 (100%)
- **Unmatched**: 0
- **Polish-touched**: ~5.000 righe (article injection, elisione, fix dalla/dal)

### Per-attribute training rows finali

| Attributo | Rows | Unique images |
|---|---:|---:|
| Profumo | 5.660 | 1.622 |
| Aroma | 4.019 | 1.215 |
| Sapore | 6.244 | 1.494 |
| Texture | 5.309 | 1.299 |
| Spessore della Crosta | 3.961 | 1.021 |
| Struttura della Pasta | 7.400 | 1.626 |
| Colore della Pasta | 5.844 | 1.274 |
| **Totale** | **38.437** | **1.497** unique |

(Total unique images è 1.497 — alcune immagini non hanno tutti i 7 attributi coperti.)

### Schema output `captions_final.csv`

```
row_id, image_path_flat, image_path,
year_folder, session_date, session_num, bimester,
view, panel_slot, panel_replicate, dairy_id, product_code,
panelist, attribute,
caption_raw,        # original panelist text
caption_pre,        # after deterministic preprocessing
caption,            # cleaned compact form (LLM + manual salvage)
caption_sentence,   # full Italian declarative sentence (regex transform)
```

### Quality assurance finale

Validazione post-sentence-form su tutte le 6.834 sentence uniche:

| Check | Violazioni |
|---|---:|
| `presenta` + bare singular noun (no article) | 0 |
| `presenta una/un'` + plural | 0 |
| Missing `una`→`un'` elision before vowel | 0 |
| `è dal colore` / `è dalla` | 0 |
| `è unghia` | 0 |
| Double spaces | 0 |
| `un' ` with extra space | 0 |
| Article doubling | 0 |
| Trailing punctuation issues | 0 |

**Tutti i check passano.** Il dataset è pronto per Step 2 (training di 3 metodi encoder-decoder come da consegna AI4FQC Project 07).

## Layout finale `data/final/`

```
data/final/
├── captions_final.csv                 # full table 38,437 × 18
├── image_caption_attribute.csv        # simplified 4 col
├── by_attribute/
│   ├── Aroma.csv
│   ├── Colore_della_Pasta.csv
│   ├── Profumo.csv
│   ├── Sapore.csv
│   ├── Spessore_della_Crosta.csv
│   ├── Struttura_della_Pasta.csv
│   └── Texture.csv
└── README.md
```
