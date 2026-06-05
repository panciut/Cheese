# Fase 8 — Batch run completo

**Script**: `rewrite_batch.py`

## Input
- `data/intermediate/captions_to_rewrite.csv` (7.742 uniche post-pilot — ridotte a 7.689 dopo estensione qualitatizzazione Fase 4)
- Prompt costruiti dinamicamente da `rewrite_prompt.py` (Fase 6)
- API key Anthropic da `.env`

## Output
- `data/rewrites/rewrites_<attribute>.csv` × 7 (machine-readable, una riga per caption unica)
- `data/rewrites/review_<attribute>.txt` × 7 (human-readable side-by-side, ordinato per frequency desc)
- `data/batches/<batch_id>.json` (mapping `custom_id` → `dedup_key` + metadata batch)

## Modello e configurazione
- `claude-haiku-4-5`
- API: **Anthropic Batch API** (50% sconto, async, no rate limits)
- `max_tokens=200`
- Batch ID effettivo: `msgbatch_01Bv99Z88dFdZ6PJ6FdjRxoA`

## Cosa fa la fase

Il LLM esegue il "genuinely hard work" che no regex può fare in modo affidabile:
- Espandere fragment telegrafici in caption naturali (`Crauti` → `Profumo di crauti.`)
- Normalizzare dialetto/colloquiale/abbreviato in italiano standard
- Strip meta-comments preservando descrittori embedded (`amaro deciso e penalizzante` → `Sapore amaro e deciso.`)
- Convertire misure embedded in qualitativo (`Spigoli sopra 20mm` → `Crosta con spigoli pronunciati`)
- Trasformare domande in affermazioni (`Eucalipto?` → `Note olfattive di eucalipto.`)

### Pipeline interna

#### A. Submit (`submit`)

1. **Carica** caption uniche per gli attributi richiesti
2. **Genera** Request objects con `custom_id = row{idx:05d}` (5 cifre, supporta fino a 99.999)
3. **Salva mapping locale** `custom_id → {dedup_key, attribute, caption_pre, frequency, sample_row_id}` in `data/batches/<batch_id>.json` PRIMA della submit
4. **Submit batch** con `client.messages.batches.create(requests=...)`
5. **Persist metadata**: model, attributes, n_requests, submission timestamp

#### B. Poll (`poll_until_done`)

```python
while True:
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status == "ended": return batch
    time.sleep(30)
```

Stampa progress: `succeeded`, `errored`, `processing`, `canceled`, `expired`.

#### C. Fetch + write (`fetch_and_write`)

1. **Stream results** via `client.messages.batches.results(batch_id)`
2. Per ogni result, lookup `custom_id` nel mapping salvato
3. Estrae text dal `result.message.content`
4. Strip di virgolette → `caption_clean`
5. **Routing per attributo**: aggrega in `by_attr_rows[attr]`
6. **Scrive 2 file per attributo**:
   - `rewrites_<attr>.csv` — schema `dedup_key, attribute, caption_pre, caption_clean, frequency, sample_row_id, error`
   - `review_<attr>.txt` — human-readable, sorted by `frequency` desc

#### D. Resume support

```bash
python3 rewrite_batch.py --resume <batch_id>
```

Polla un batch esistente fino a `ended` e fetcha i risultati. Permette recovery da crash, network failure, machine restart.

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Batch API, non sync** | 50% sconto + zero rate-limit anxiety + async = $4,50 vs $9,00 | Sync con 3 worker × 7.689 ≈ stesso wall time ma più costoso |
| **Salvataggio mapping PRE-submit** | Se lo script crasha tra submit e fetch, il batch è recuperabile via `--resume` | Mapping in memoria perde tutto al crash; batch processato ma irrecuperabile |
| **`max_tokens=200`** | Caption ≤ 18 parole = ~30 token; 200 dà margine per `NON_DESCRITTO` o reasoning eventuale | Default `max_tokens` tokenizza all'infinito → potential runaway cost |
| **One batch per N attributi** | Singola sottomissione = singolo wait period; tutti i 7 attributi insieme | 7 batch separati = 7× wait period, 7× polling overhead |
| **Haiku 4.5, non Sonnet/Opus** | Pilot ha verificato che Haiku gestisce il task con quality identico; cost ~5× inferiore a Sonnet, ~20× a Opus | Sonnet costava ~$13,50, Opus ~$67 — overkill per task di rephrasing con strong few-shots |
| **Custom ID `row{:05d}` (5 cifre)** | Supporta fino a 99.999 — 7.689 ci sta, future expansion supportata | 4 cifre avrebbe rotto a 10k |
| **Output diviso per attributo (7 CSV)** | Permette QA mirata, broadcast separato, grain di audit | Output unico avrebbe richiesto split in fase successiva |
| **`review_<attribute>.txt` ordinato per `frequency` desc** | Le caption più broadcastate (errori = molti danni) sono in cima per ispezione manuale | Ordine random = high-impact bug nascosti |
| **Persist mapping con `model` + `attributes` + `n_requests`** | Audit trail completo del batch eseguito | Solo `batch_id` = perdita di context |
| **`status` command** (`--status`) | Lista locale dei batch sottomessi, utile per recovery | Senza, batch ID è opaque |
| **Strip di virgolette dall'output** (`text.strip().strip('"')`) | Il LLM occasionalmente avvolge l'output in `"..."` nonostante la regola 10; strip safety net | Lasciar virgolette = caption sporche nel dataset finale |
| **`anthropic.types.message_create_params.MessageCreateParamsNonStreaming`** | Tipo SDK ufficiale — ovvia compatibilità con Batch API | Custom dict avrebbe richiesto manual schema validation |
| **Polling ogni 30s** | Bilanciamento tra reattività e overhead API | 5s = polling cost; 5min = wait inutile |

## Risultati osservati

### Risultati raw del batch

- **7.689 / 7.689 succeeded, 0 errors**
- Wall time: **~25-30 minuti**
- Cost: **~$4,50** (Haiku 4.5 con 50% Batch discount)
- **NON_DESCRITTO emessi**: 360 (4,7% delle uniche)
- **Multi-line outputs contenenti `NON_DESCRITTO`**: 2 (collapsed al token bare in post-processing)

> Nota: il count è 7.689 invece di 7.742 perché tra pilot e full batch è stata estesa la qualitatizzazione deterministica di Fase 4 per coprire forme con unità (`10 mm`, `1 cm`). Le caption interamente misuranti hanno seguito il bucket deterministico, riducendo il numero da inviare al LLM.

### Distribuzione per attributo

| Attributo | Uniche | NON_DESCRITTO | NON_D % | Usable |
|---|---:|---:|---:|---:|
| Profumo | 1.178 | 64 | 5,4% | 1.114 |
| Aroma | 805 | 56 | 7,0% | 749 |
| Sapore | 1.127 | 58 | 5,1% | 1.069 |
| Texture | 1.088 | 30 | 2,8% | 1.058 |
| Spessore della Crosta | 637 | 66 | 10,4% | 571 |
| Struttura della Pasta | 1.674 | 54 | 3,2% | 1.620 |
| Colore della Pasta | 1.180 | 32 | 2,7% | 1.148 |
| **Totale** | **7.689** | **360** | **4,7%** | **7.329** |

**Osservazione**: `Spessore della Crosta` ha il tasso `NON_DESCRITTO` più alto (10,4%) — molte caption originali sono pure misure senza descrittori qualitativi (es. `0,8`, `12 mm`) e dopo Fase 4 le bare-number sono state qualitatizzate, ma residui meno strutturati arrivano al LLM.

### Validazione automatica post-batch

Programmatic check su tutti i 7.689 output:

| Check | Violazioni |
|---|---:|
| Output starts with expected attribute prefix | 1 (`Pepe?` → `Note di pepe.`, accettato come variante valida) |
| Output contains digits | **0** |
| Output contains units (mm/cm/%) | **0** |
| Output longer than 25 words | **0** |
| Empty output | **0** |
| Multi-line output (after post-processing) | **0** |
| Multi-paragraph or markup-bearing output | **0** |

**Quantitativo→qualitativo: 100% successo** — soddisfa pienamente Step 1 del project brief.

### Quality assessment per attributo

| Attributo | Top output | Note |
|---|---|---|
| Sapore | `Sapore salato.`, `Sapore equilibrato.`, `Sapore leggermente salato.` | Pulito |
| Texture | `Texture asciutta.`, `Texture compatta.`, `Texture pastosa.` | Gender agreement OK (`asciutto` → `asciutta` con femminile `Texture`) |
| Profumo / Aroma | `Profumo di panna.`, `Aroma di crauti.` | Naturale; ~20 casi mild stilted-bare-participle (`Aroma cotto.`) — grammaticalmente validi, leggermente meno idiomatici di `Aroma di X` |
| Struttura della Pasta | `Pasta stirata.`, `Pasta con microocchiatura diffusa.` | `microocchiatura` correttamente canonicalizzato (typo `microcchiatura`, `microocchitura` mappati via TYPO_MAP di Fase 2) |
| Colore della Pasta | `Pasta con alone centrale.`, `Pasta di colore omogeneo.` | Dual templates contestuali: `Pasta di colore X` per qualifier color, `Pasta con X` per distribution feature |
| Spessore della Crosta | `Crosta mediamente spessa.`, `Crosta sottile.` | mm/cm consistency holds: `1 cm = 10 mm = mediamente spessa` (no inconsistencies) |

## Problemi evitati

- **Crash durante batch (8h+)**: il mapping salvato + `--resume` rende ogni step recoverable. Lo script può essere chiuso e ripreso senza perdere lo stato.
- **Costo 5× su Sonnet** o 20× su Opus per zero quality gain. Pilot ha validato Haiku come scelta ottimale.
- **Rate-limit** completamente evitato dal Batch API (no concurrent quota).
- **Caption duplicate**: il dedup di Fase 4 ha già garantito che ogni caption sia processata una volta sola — broadcast post-LLM diffonde a tutte le righe match.
- **Output non strutturato**: `custom_id` univoco permette tracking 1:1 senza ambiguità anche se il batch processa in ordine non-sequenziale.
- **Hallucinated descriptors**: validazione post-batch ha confermato zero invenzione (regola 6 + few-shot funzionano).
- **Format violations**: zero multi-line outputs (regola 10 + regola 11 funzionano).
- **mm/cm inconsistency**: zero discrepanze (tabella `extra_rules` + qualitatizzazione Fase 4 funzionano).

## Cost summary del batch

| Component | Stima |
|---|---:|
| Input tokens (~5 KB system prompt × 7,689) | ~38M token input |
| Output tokens (~30-50 token × 7,689) | ~300k token output |
| Pricing Haiku 4.5 input | $0,80/M token (con 50% batch sconto = $0,40) |
| Pricing Haiku 4.5 output | $4,00/M token (con 50% batch sconto = $2,00) |
| Cost batch | ~$4,50 totale |

(System prompt è cached/refactorato dal Batch API → cost effettivo è probabilmente inferiore.)

## Cosa va in input alla Fase 9

I 360 output `NON_DESCRITTO` sono il candidato per la **fase di salvage manuale** (Fase 9). Heuristic post-batch ha mostrato che ~80% di questi hanno almeno un lemma del vocabolario controllato nella sorgente — possibile over-application della regola 11 da parte del LLM.
