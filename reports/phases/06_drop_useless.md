# Fase 5 — Drop conservativo del rumore

**Script**: `find_useless_captions.py` (survey) + `drop_useless_captions.py` (drop attivo)

## Input
- `data/intermediate/captions_pre.csv` (39.356 righe)
- `data/intermediate/captions_unique.csv` (7.705 uniche)

## Output
- `data/intermediate/captions_to_rewrite.csv` — **7.689 uniche** (input LLM)
- `data/intermediate/captions_pre_filtered.csv` — **39.280 righe** broadcast target
- `data/intermediate/dropped_captions.csv` — audit trail dei drop con motivo
- `data/reports/drop_captions_report.txt`
- `data/reports/useless_caption_candidates.txt` (output del survey)

## Cosa fa la fase

Due script in pipeline.

### A. Survey — `find_useless_captions.py`

Classifica le caption uniche in 7 categorie senza droppare. Genera report ispezionabile.

**Categorie**:

| # | Categoria | Pattern | Drop attivato? |
|---|---|---|:---:|
| 1 | **META** | `non valuto`, `non penalizz`, `non saprei`, `non riesco`, `non ne capisco`, `difficile valutare`, `voto`, `punteggio`, `valutazione`, `dovuto sputarl`, `peccato.` | ✅ |
| 2 | **PURE_EVAL** | Singola parola valutativa: `buono`, `bello`, `brutto`, `ottimo`, `ok`, `mah`, `boh`, `ehm`, `niente`, `sì`, `no`, `passabile` | ✅ |
| 3 | **PURE_INTENSIFIER** | Singolo intensificatore: `leggero`, `intenso`, `forte`, `medio`, `alto`, `basso`, `debole` | ❌ (è informazione) |
| 4 | **UNCERTAINTY** | Esordio con `forse`, `sembra`, `potrebbe`, `credo`, `direi`, `pare` | ❌ (descrittore implicito) |
| 5 | **INTERROGATIVE** | Termina con `?` o esordisce con `ma` | ❌ (LLM trasforma in affermazione) |
| 6 | **NUMBER_ONLY** | Solo cifre (max 3 token) | ✅ (per non-Spessore; Spessore già gestito in Fase 4) |
| 7 | **EMPTY_AFTER_TOKENIZE** | Caption senza alcun token alfanumerico | ✅ |

**Pattern critici note**:
- `non so` con lookbehind/lookahead `(?!\s+come|\s+cosa|\s+se)` — distingue `non so` (abbandono valutativo) da `non so come/cosa/se` (continuazione descrittiva)
- `regolare`, `tipico`, `normale` ESCLUSI da `PURE_EVAL`: sono descrittori sensoriali validi (uniformity, typicality)

### B. Drop attivo — `drop_useless_captions.py`

Drop solo su 3 categorie certe dove l'INTERA caption è info-free:

1. **PURE_EVAL** — single-token judgment senza descrittore (28 entry curate)
2. **NUMBER_ONLY** — solo cifre, max 3 token (Spessore già gestito in Fase 4 quindi qui non hit)
3. **SYSTEM_META** — meta sulla seduta/sistema (8 pattern):
   - `valutazione alle`
   - `al primo tentativo...test`
   - `si è chiuso il test`
   - `schermata dei commenti`
   - `sono ripartito dal`
   - `peccato.` (puro, isolato)
   - `non lo so`
   - `dovuto sputarl`

Il drop è **conservativo**: caption miste (meta + descrittore) NON droppate, lasciate al LLM (che fa surgery meglio di una regex).

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Survey + drop come fasi separate** | Il survey produce un report ispezionabile da umano; il drop attivo è conservativo basato sull'analisi del survey | Drop diretto sarebbe stato non auditabile, no human-in-the-loop |
| **Drop solo 3 categorie certe** | Solo dove l'INTERA caption è info-free; caption miste lasciate al LLM | Drop aggressivo avrebbe perso descrittori veri (`amaro deciso e penalizzante` → contiene `amaro deciso`) |
| **`PURE_INTENSIFIER` NON droppato** | `Leggero` (single word) è informazione: il LLM lo trasforma in `Profumo leggero.` | Droppare avrebbe perso 100+ caption legittime |
| **`UNCERTAINTY` NON droppato** | `Forse pochi cristalli` ha descrittore reale (`pochi cristalli`); il LLM riformula come `Texture con pochi cristalli` | Droppare avrebbe scartato hedging legittimo, parte naturale del registro panelista |
| **`INTERROGATIVE` NON droppato** | `Eucalipto?`, `Lievito pane?` sono fragment descrittivi, non vere domande. Regola 8 del prompt LLM: `Eucalipto?` → `Note olfattive di eucalipto.` | Droppare avrebbe perso descrittori utili |
| **Negazioni descrittive preservate** | `Non paglierino` ha valore descrittivo (= "non giallo paglia"); regex `non so` evita di confonderle con `non valuto` | Droppare tutte le frasi con `non` avrebbe perso 200+ caption |
| **Pattern `non so` con lookahead negativi** | `non so come/cosa/se` = continuazione descrittiva legittima; `non so.` isolato = abbandono valutativo. Lookahead `(?!\s+come\|\s+cosa\|\s+se)` distingue | Pattern semplice avrebbe scartato troppo |
| **Audit trail in `dropped_captions.csv`** | Ogni riga droppata ha motivo annotato → reversibilità totale | Drop silenzioso = data loss non recuperabile |
| **`PURE_EVAL` curato a mano (28 entry)** | Lista chiusa, deterministica, esposta nel codice | Auto-detection via lessico avrebbe creato falsi positivi su `regolare`, `omogeneo` |

## Problemi evitati

- **Drop di descrittori sensoriali genuini** mascherati da hedging:
  - `forse troppo sapido` → LLM lo riformula come `Sapore eccessivamente sapido` (descrittore reale)
  - `quasi troppi cristalli...` → `Texture con cristalli abbondanti`
  - `potrebbe essere più friabile` → `Texture poco friabile`
- **Drop di interrogativi**: `Eucalipto?`, `Lievito pane?`, `Setata??` sono in realtà fragment descrittivi.
- **Drop di negazioni descrittive**: `Non paglierino` (= "non giallo paglia"), `Non granulosa` (= "non con grana"), `Non equilibrato salato` (= sapore squilibrato salato).
- **Bias di registro linguistico**: panelisti più colloquiali avrebbero perso più caption rispetto a quelli formali — il drop neutrale rispetto al registro.
- **Drop su PURE_EVAL borderline**: parole come `discreta`, `passabile` sono giudizi puri ma `regolare` non lo è — la lista esplicita evita decisioni arbitrarie su token ambigui.
- **Information loss su `peccato`**: `Peccato.` (isolato) = abbandono valutativo (drop); `Peccato per irregolarità di frattura` = contiene descrittore (`irregolarità`) → keep, LLM fa surgery.

## Statistiche output

### Drop totali

- **16 uniche droppate** (su 7.705 = **0,21%**)
- **76 righe training droppate** (su 39.356 = **0,19%**)

### Breakdown per categoria

| Categoria | Righe broadcast droppate |
|---|---:|
| PURE_EVAL | 64 |
| SYSTEM_META | 12 |
| NUMBER_ONLY | 0 (tutte già gestite in Fase 4) |
| **Totale** | **76** |

### Output finale per LLM

- **7.689 caption uniche** → input batch LLM (Fase 7-8)
- **39.280 righe** broadcast target (per il join finale di Fase 10)

## Esempi di caption preservate (non droppate)

| Caption | Categoria flag | Motivo preservazione |
|---|---|---|
| `Forse pochi cristalli` | UNCERTAINTY | Contiene descrittore `pochi cristalli` |
| `Eucalipto?` | INTERROGATIVE | Descrittore `eucalipto`; LLM trasforma in affermazione |
| `Non paglierino` | (negazione) | Descrittore valido (= "non giallo paglia") |
| `Leggero` | PURE_INTENSIFIER | Intensità è informazione |
| `amaro deciso e penalizzante` | (mixed META + descrittore) | Contiene `amaro deciso`; LLM strip del meta |
| `Quasi troppi cristalli...` | UNCERTAINTY + INTENSIFIER | Descrittore quantitativo |

## Esempi di caption droppate

| Caption | Categoria | Motivo |
|---|---|---|
| `Buono` | PURE_EVAL | Giudizio puro senza descrittore |
| `Ok` | PURE_EVAL | Approvazione senza contenuto |
| `Mah` | PURE_EVAL | Esitazione vuota |
| `Peccato.` | PURE_EVAL / SYSTEM_META | Abbandono valutativo |
| `Valutazione alle 13:40` | SYSTEM_META | Meta sul timing della seduta |
| `Al primo tentativo si è chiuso il test` | SYSTEM_META | Meta sul sistema, non sul formaggio |
