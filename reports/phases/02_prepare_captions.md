# Fase 1 — Preparazione caption deterministica

**Script**: `prepare_captions.py`

## Input
- `data/intermediate/unified_dataset.csv` (51.988 righe)

## Output
- `data/intermediate/captions_prepared.csv` (39.356 righe)
- `data/reports/captions_prep_report.txt`

## Cosa fa la fase

Step deterministico pre-LLM. Filtra e normalizza, **non riformula**.

1. **Filtra righe** con `comment` vuoto, `N/A`, solo whitespace
2. **Normalizza testo** (`normalize_text`):
   - Unicode NFC
   - `\xa0` → spazio normale
   - Zero-width chars rimossi (`​`)
   - `\t`, `\r`, `\n` → spazio
   - Run di whitespace collassati con regex `\s+`
   - Strip di virgolette/backtick spuri ai bordi (` \t"'\``)
3. **Drop meta-comments** via blacklist regex (5 pattern):
   - `^\s*n[/.]?a\s*$` (varianti di N/A)
   - `non\s+penaliz`
   - `non\s+valuto`
   - `^\s*-+\s*$` (solo trattini)
   - `^\s*[\.\,;:\*]+\s*$` (solo punteggiatura)
4. **Drop near-empty noise**: meno di 2 caratteri alfanumerici dopo la pulizia (`re.sub(r"[^\w]", "", norm)`)
5. **Doppia colonna**: mantiene sia `caption_raw` (originale post-strip) che `caption_norm` (normalizzato) per reversibilità completa

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **NFC, non NFKD** | Conserva caratteri composti italiani (`è`, `à`) come single code-point | NFKD avrebbe spezzato accenti in due code-point, rompendo i tokenizer downstream |
| **Mantenere `caption_raw` E `caption_norm`** | Audit: ogni trasformazione deve essere reversibile e diffabile in qualsiasi momento | Tenere solo la versione pulita avrebbe reso impossibile spiegare ex post le scelte |
| **Drop "near-empty" con soglia 2 caratteri alfanumerici** | Cattura `"."`, `"-"`, `"a"`, ma preserva fragment validi come `"ok"` (gestito poi nel drop selettivo di Fase 5) | Soglia più alta (es. 5 char) avrebbe perso fragment veri come `"sì"`, `"no"`, `"forte"` |
| **Blacklist regex piccola e conservativa** | Drop a questo stadio deve essere **certo** — il LLM gestirà meglio le ambiguità in Fase 8 | Blacklist aggressiva avrebbe scartato commenti misti meta+descrittore (`"non penalizzo, ma sa di stalla"`) |
| **Stop list custom nel report** | Le lib NLP italiane (nltk, spaCy) caricano centinaia di stopword incluse parole con valore sensoriale (`molto`, `poco`, `leggermente`) | Stop list standard avrebbe scartato intensificatori importanti |
| **Tokenizzazione Italian-aware** (`r"[^\wàèéìòù]"`) | Preserva accenti italiani durante il counting | `\w` Python di default include accenti, ma esplicitare evita locale-dependency |
| **`csv.DictReader/DictWriter`** | Header-based, robusto a riordinamento colonne | Index-based parsing fragile ai cambi di schema upstream |

## Problemi evitati

- **Perdita di caption con caratteri unicode strani**: la normalizzazione cattura zero-width joiner (`​`), NBSP (`\xa0`), soft hyphen — tutti presenti silenziosamente nei workbook 2021.
- **Drop prematuro di descrittori validi**: la blacklist non include `peccato`, `bello`, `buono` perché possono essere parte di frasi descrittive (`peccato per irregolarità` → contiene il descrittore `irregolarità`). Il drop di queste parole singole avviene solo in Fase 5 (`drop_useless_captions.py`).
- **Bug di encoding nei CSV**: usa `csv` standard library con escape e quoting predefiniti, niente parsing manuale via `split(",")` che esploderebbe su caption con virgole.
- **Drift di lunghezza vs registro**: la fase non taglia caption lunghe né estende corte; quello è compito della Fase 8 (LLM).
- **Loss di provenance**: tutte le metadata (panelist, session_date, dairy_id, ecc.) sono propagate verso valle.

## Statistiche output

- **39.356 righe** (75,7% di retention dal `unified_dataset.csv`)
- **Drop totali**: 12.632
  - 12.478 vuoti/null
  - 86 meta-notes
  - 68 near-empty

### Distribuzione per attributo

| Attributo | Righe |
|---|---:|
| Struttura della Pasta | 7.546 |
| Sapore | 6.350 |
| Colore della Pasta | 5.947 |
| Profumo | 5.798 |
| Texture | 5.431 |
| Aroma | 4.213 |
| Spessore della Crosta | 4.071 |

### Caption shape

- Mediana: 3-6 token, spesso single word (`"Crauti"`, `"Forte"`, `"Yogurt"`, `"Brutta"`)
- ~25% sono ≤2 token
- Casing inconsistente (`"Leggermente Acido amaro"`)
- Max ~200 char

### Schema output

```
row_id, image_path_flat, image_path, attribute,
caption_raw, caption_norm,
panelist, session_date, year_folder, session_num, bimester,
view, panel_slot, panel_replicate, dairy_id, product_code
```
