# Fase 9 — Salvage manuale dei NON_DESCRITTO

**Script**: `manual_salvage.py`

## Input
- `data/rewrites/rewrites_<attribute>.csv` × 7 (output Fase 8)
- `data/reports/non_descritto_salvage.txt` (heuristic-flagged candidates)

## Output
- `data/rewrites/rewrites_<attribute>.csv` × 7 (in-place update con caption salvate)
- `data/rewrites/review_<attribute>.txt` × 7 (rigenerati post-salvage)
- `data/reports/non_descritto_table.txt` (inventory dei NON_DESCRITTO sopravvissuti)

## Cosa fa la fase

Recupera caption che il LLM ha conservativamente classificato come `NON_DESCRITTO` ma che hanno descrittori sensoriali genuini.

### Background

Su 7.689 caption processate dal LLM (Fase 8), 360 sono state taggate `NON_DESCRITTO` — il 4,7%. Una scansione euristica ha mostrato che **291 di queste 362** (80%) contengono almeno un lemma del vocabolario controllato nella sorgente. Suggerisce che il LLM è stato over-cautious sull'applicazione della regola 11.

### Pipeline interna

1. **Carica** la salvage map hard-coded in `manual_salvage.py`:
   ```python
   SALVAGE: dict[str, dict[str, str]] = {
       "Profumo": {
           "marcio, putrido,": "Profumo marcio e putrido.",
           "Anonimo": "Profumo anonimo.",
           ...  # ~30 entry per attributo
       },
       "Aroma": { ... },
       ...
   }
   ```

2. **Per ogni attributo**, walk del `rewrites_<attr>.csv`
3. Per ogni riga con `caption_clean == "NON_DESCRITTO"`:
   - Lookup `caption_pre` nella `SALVAGE[attribute]`
   - Se presente → sostituisci `caption_clean` con il valore curato
   - Altrimenti → mantieni `NON_DESCRITTO`
4. **Scrivi in-place** il CSV aggiornato
5. **Rigenera** il review TXT side-by-side

### Esempi di salvage

| `caption_pre` | LLM output | Salvage manuale |
|---|---|---|
| `marcio, putrido,` | NON_DESCRITTO | `Profumo marcio e putrido.` |
| `Strano. A tratti sentiva di pesce. Perplesso` | NON_DESCRITTO | `Profumo strano, di pesce a tratti.` |
| `Sangue,,,` | NON_DESCRITTO | `Aroma di sangue.` |
| `Anonimo` | NON_DESCRITTO | `Aroma anonimo.` |
| `Nostrano` | NON_DESCRITTO | `Sapore nostrano.` |
| `chiuso` | NON_DESCRITTO | `Profumo chiuso.` |
| `Molto elegante` | NON_DESCRITTO | `Profumo molto elegante.` |
| `12 km più netta su 1 piatto` | NON_DESCRITTO | `Crosta più netta su un piatto.` |
| `non percettibile. senza odore` | NON_DESCRITTO | `Profumo impercettibile, senza odore.` |
| `Putrido, trremendo` | NON_DESCRITTO | `Profumo putrido.` |
| `solvente ___(` | NON_DESCRITTO | `Profumo di solvente.` |
| `note poco tipiche e caratteristiche` | NON_DESCRITTO | `Profumo poco tipico.` |
| `Pessima` | NON_DESCRITTO | (nessun salvage — giudizio puro) |
| `dd` | NON_DESCRITTO | (nessun salvage — fragment incomprensibile) |

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Salvage manuale, non secondo round LLM** | 178 entry sono review-able in ~1 ora di lavoro umano; secondo batch LLM costava ~$2 + non-determinismo + rischio di nuovi NON_DESCRITTO con prompt diverso | Secondo round LLM = costo + no garanzia di qualità superiore |
| **Solo 178 su 291 candidati** | I rimanenti 113 sono genuini judgment puri (`Pessima`, `Non piacevole!!!`), fragment incomprensibili (`dd`, `tro`), o off-attribute | Salvage al 100% avrebbe forzato descrittori falsi su input genuinamente vuoti |
| **Update IN-PLACE dei rewrites** | Mantiene il singolo `dedup_key → caption_clean` pulito per la fase di broadcast | File separato avrebbe richiesto merge logic in Fase 10 |
| **Caption assenti dalla salvage map mantengono `NON_DESCRITTO`** | Default safe: in dubbio, drop | Default "salvage" avrebbe richiesto controllo per ogni caso non listato |
| **Salvage map come dict hard-coded nello script** | Versionabile, diff-abile su git, leggibile in code review | File esterno (CSV/JSON) avrebbe disconnesso decisione dal contesto |
| **Salvage rispetta il template attributo** (`Profumo X.`, `Aroma X.`) | Mantiene uniformità di stile con LLM output | Caption libere avrebbero introdotto drift |
| **Numero entry per attributo bilanciato** | Salvage proporzionale al numero di NON_DESCRITTO per attributo | Skew avrebbe creato bias di copertura |

## Salvage per attributo

| Attributo | NON_DESCRITTO pre-salvage | Salvati | NON_DESCRITTO post-salvage |
|---|---:|---:|---:|
| Profumo | 64 | 33 | 31 |
| Aroma | 56 | 21 | 35 |
| Sapore | 58 | 34 | 24 |
| Texture | 30 | 7 | 23 |
| Spessore della Crosta | 66 | 46 | 22 |
| Struttura della Pasta | 54 | 24 | 30 |
| Colore della Pasta | 32 | 13 | 19 |
| **Totale** | **362** | **178** | **184** |

## Effetto netto sul dataset

| Metrica | Pre-salvage | Post-salvage |
|---|---:|---:|
| `NON_DESCRITTO` uniche | 362 (4,7%) | **184 (2,4%)** |
| `NON_DESCRITTO` broadcast rows | 1.759 (4,5%) | **843 (2,1%)** |
| Training rows recuperate | — | **916 righe** |

**916 righe di training recuperate** offline a costo $0.

## Problemi evitati

- **Dataset shrinkage del 4,5%**: senza salvage, la training set sarebbe stata 37.521 righe invece di 38.437 (loss del 2,4%).
- **Bias verso caption "facili"**: il salvage ha recuperato in particolare caption brevi/ellittiche (`Anonimo`, `chiuso`, `marcio`, `Sangue`) che il LLM aveva conservativamente classificato come info-free ma che hanno valore descrittivo chiaro per un esperto del dominio.
- **Costo di un secondo round LLM**: ~$2 + tempo + non determinismo → evitato.
- **Drift di stile**: il salvage rispetta il template attributo (`Profumo X.`, `Aroma X.`, `Crosta X.`) garantendo uniformità con l'output del LLM.
- **Loss di descrittori specifici del dominio Trentingrana**: `nostrano`, `marcio`, `putrido`, `sangue`, `solvente`, `clostridium` sono descrittori legittimi del registro panel test che il LLM ha trattato con eccesso di cautela.
- **Information loss su misure embedded**: `12 km più netta su 1 piatto` (Spessore) → `Crosta più netta su un piatto.` — il `12 km` era artefatto del panelista (errore tipo per `mm`?), il salvage manuale lo strip preservando il descrittore `più netta`.
- **Non-determinismo dei secondi round LLM**: stesso prompt + stesse caption potrebbe produrre diverse classificazioni `NON_DESCRITTO` in run successive. La salvage manuale è deterministica e versionata.

## Caption che restano `NON_DESCRITTO` post-salvage

I 184 sopravvissuti sono **genuinamente info-free**:

### Categorie

1. **Pure judgments**: `Pessima`, `Non piacevole!!!`, `Brutto sapore`
2. **Incomprehensible fragments**: `dd`, `tro`, `xx`, single letters
3. **System meta non catturato in Fase 5**: `Valutato durante foto`, `Oggi sono raffreddato`
4. **Off-attribute**: osservazioni interamente su un altro attributo (es. nota di crosta dentro un commento Sapore)
5. **Annotazioni vuote dopo strip dei meta**: caption che dopo applicazione delle regole sono effettivamente vuote

Output: `data/reports/non_descritto_table.txt` — full inventory dei 184 caption sopravvissuti, sortita per attributo e frequency desc, per eventuale review futura.

## Filosofia del salvage

> "Cleaning data ≠ throwing it away."

Il salvage manuale è un investimento di ~1 ora per recuperare 916 righe di training. Trade-off:

| Approach | Costo | Recupero |
|---|---|---|
| **No salvage** | $0 | 0 righe (37.521 final) |
| **Salvage manuale** | 1h umano + $0 | 916 righe (38.437 final) |
| **Secondo round LLM** | $2 + 1h umano per QA | ~700-900 righe (incerto, non determinato) |
| **Round LLM con prompt v2** | $5 + iteration | Possibile peggioramento |

Salvage manuale è il Pareto-ottimo per questo volume (~200 entry).

## Esempi del file `data/reports/non_descritto_table.txt` (post-salvage)

```
## Profumo (31 NON_DESCRITTO sopravvissuti)
  freq=12  caption_pre = Pessima
  freq=8   caption_pre = Non piacevole!!!
  freq=6   caption_pre = Bruttissimo
  freq=4   caption_pre = dd
  ...

## Aroma (35 NON_DESCRITTO sopravvissuti)
  ...
```
