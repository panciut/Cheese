# Fase 7 — Pilot run

**Script**: `pilot_rewrite.py`

## Input
- `data/intermediate/captions_to_rewrite.csv` (7.742 uniche al momento del pilot — versione pre-estensione della qualitatizzazione Spessore; il set fu poi ridotto a 7.689 per il batch, vedi Fase 8)
- `ANTHROPIC_API_KEY` o `CLAUDE_KEY` da `.env` o environment

## Output
- `data/reports/pilot_rewrites.csv` — 105 righe (15 per attributo) con caption raw + clean
- `data/reports/pilot_review.txt` — file side-by-side per review umana

## Modello e configurazione
- `claude-haiku-4-5`
- API: **sync** (non batch)
- Concorrenza: **3 worker** (`MAX_WORKERS = 3`)
- Retry: 6 (`MAX_RETRIES = 6`, exponential backoff via SDK)

## Cosa fa la fase

Esegue una **mini-batch validation** per verificare che il prompt funzioni prima di lanciare il batch grosso (7.689 caption dopo l'estensione della qualitatizzazione Spessore).

### Pipeline interna

1. **Load API key** da `.env` o environment, accettando entrambi i nomi `CLAUDE_KEY` / `ANTHROPIC_API_KEY` (parsing minimale di `.env` senza dipendenze)
2. **Stratified sample** (`stratified_sample`):
   - Per ogni attributo (7), 15 caption totali
   - **Top-N**: 5 caption con frequenza più alta (max broadcast value)
   - **Random tail**: 10 caption random dalle restanti (style-diversity probe)
   - `random.Random(seed=42)` per riproducibilità
3. **Esegue chiamate sync parallele** con `ThreadPoolExecutor(max_workers=3)`
4. **Backoff esponenziale automatico** via SDK (gestisce 429 / 5xx)
5. **Output side-by-side** raw → clean per ispezione manuale

### Stratified sampling — perché

| Strategia | Cosa cattura |
|---|---|
| **Top-frequency** | Caption ad alto broadcast value: 1 errore qui = molte righe sbagliate (es. caption frequente 50× → 50 righe rotte) |
| **Random tail** | Coverage di style/registro raro: dialettali, ellittici, idiosincratici. Bug nascosti che top-frequency non scoprirebbe |

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Pilot prima del batch** | Senza pilot, un prompt sbagliato avrebbe sprecato 7.689 chiamate ($4,50 + tempo) | Skip pilot e correggere ex post = costo doppio |
| **15/attributo (105 totali), non più, non meno** | Coverage sufficiente per pattern detection, costo ~$0,20 | 50/attributo = $0,70 senza information gain proporzionale; 5/attributo = miss dei pattern |
| **Top + random tail** | Top-frequency caption hanno alto broadcast value; random tail copre style diversity | Solo top = blind on rare cases; solo random = miss high-impact bugs |
| **Concorrenza 3, non 8** | Tier API utente: 8 worker triggerano 429 storm con backoff cascade | 1 worker = 5 minuti invece di 90 secondi; 8 worker = crash da rate limit |
| **Sync API per pilot, batch API per full** | Pilot vuole feedback rapido (turnaround < 2 min); batch è async (~30 min) | Batch per pilot = inutile attesa, defeats scopo del pilot |
| **`load_api_key()` con fallback `CLAUDE_KEY`/`ANTHROPIC_API_KEY`** | Compatibilità con setup misti dell'utente | Hard-coded var name = setup fragile, errore a runtime |
| **Parsing minimale di `.env` senza `python-dotenv`** | Zero dipendenze aggiuntive per un task one-off | `python-dotenv` aggiunge un package per 5 righe di logica |
| **`MAX_RETRIES = 6`** | Standard SDK Anthropic; backoff exponential cattura transient 429/5xx | 0 retry = crash ogni 1% di rate limit; 20 retry = mascheramento di problemi sistemici |
| **`seed=42` esplicito** | Pilot riproducibile per debugging; stesso campione tra run | Random seed = comparison difficile tra iterazioni del prompt |
| **Output sia CSV (machine) che TXT (human)** | CSV per re-processing programmatico; TXT side-by-side per review umana veloce | Solo CSV avrebbe richiesto post-processing per review |

## Risultati osservati nel pilot

### Iterazione 1 (prompt initiale)

- **0 errori dopo concorrenza ridotta a 3** (al primo tentativo con 8 worker → 429 cascade)
- **~95% caption pulite al primo pass**
- **2 issue sistematici**:

#### Issue 1: Inconsistenza mm/cm (Spessore della Crosta)

Il LLM bucketizzava in modo incoerente misure equivalenti:
- `1 cm` → `Crosta spessa.` ❌
- `10 mm` → `Crosta sottile.` ❌

Stessa misura fisica (10 mm = 1 cm), output qualitativi opposti. Causa: il LLM applicava intuition diverse a unità diverse, senza una scala condivisa.

**Fix in due punti**:
1. **Prompt** (Fase 6): aggiunta tabella mm/cm in `extra_rules` di Spessore con equivalenza esplicita `1 cm = 10 mm = mediamente spessa`
2. **Pipeline deterministica** (Fase 4): estensione di `qualitatise_spessore_bare()` per gestire forme con unità (precedentemente solo bare numbers). Risultato: caption interamente numeriche → bucket deterministico, il LLM non le vede mai.

#### Issue 2: Format violation su `NON_DESCRITTO`

Su input off-attribute o senza contenuto descrittivo, il LLM "panicava" e produceva output multi-line:
```
Annotazione: "Pessima"
Didascalia : "Mi dispiace, l'annotazione 'Pessima' è un giudizio puro
senza descrittori sensoriali. Non posso produrre una didascalia
descrittiva basata su questa annotazione."
```

Output non parsabile dal post-processing.

**Fix**: aggiunta **regola 11** al prompt — escape valve `NON_DESCRITTO` come single-token output. Caption info-free producono solo quel token, filtrabile post-hoc.

### Iterazione 2 (prompt corretto)

- 0 errori
- 0 multi-line outputs
- Nessuna inconsistenza mm/cm
- Pilot accettato → procede a Fase 8 (batch)

## Problemi evitati

- **$4,50 di batch sprecato**: se il prompt fosse stato lanciato senza pilot, i due bug sopra avrebbero richiesto un secondo batch da $4,50 con prompt corretto.
- **Inconsistenza sistematica mm/cm in 195+ caption Spessore**: senza il fix, il dataset finale avrebbe avuto bucket incoerenti per misure equivalenti — un errore visibile a inspection ma sistematico.
- **Hundreds di multi-line outputs** non parsabili dal post-processing: avrebbero richiesto:
  - Parsing manuale o LLM-based di seconda passata, oppure
  - Drop di tutte le caption affette → data loss
- **Rate-limit cascade**: 429 errors con backoff cascading avrebbero potuto crashare lo script su tier API non infinito; concorrenza 3 evita il problema.
- **Bias di sampling**: stratified sampling cattura sia high-impact (frequenti) che high-diversity (random) — entrambi i bug sopra sono stati scoperti dal mix.

## Output del pilot

### `pilot_review.txt` — formato

```
## Profumo — 15 captions

freq=145  raw : Crauti
          clean: Profumo di crauti.

freq=89   raw : burro fresco, note lattiche prevalenti, poco complesso
          clean: Profumo di burro fresco con note lattiche prevalenti, poco complesso.

freq=23   raw : Eucalipto?
          clean: Note olfattive di eucalipto.

freq=4    raw : Sa di malga
          clean: Profumo di malga.

[...]
```

Ordinato per frequenza desc → review umana parte dalle caption più impattanti.

### Costo del pilot

- 105 chiamate × ~50 token output ≈ ~5.000 token output
- Modello Haiku 4.5 sync: ~$0,20 per il pilot completo
- Wall time: ~90 secondi con 3 worker

## Importanza strategica

Il pilot è il **gate** tra prompt design e batch run. Senza:
- Bug strutturali del prompt (regole mancanti, format violation) sarebbero passati al batch
- Inconsistencies (mm/cm) sarebbero state scoperte solo a posteriori
- Cost overrun: rifare il batch con prompt corretto = doppio costo

Con il pilot:
- Iterazione del prompt economica ($0,20 per round)
- Validation umana del registro/stile/aderenza alle regole
- Confidence per il commit del batch grosso
