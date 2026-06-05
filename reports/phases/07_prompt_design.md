# Fase 6 — Design del prompt LLM

**Script**:
- `rewrite_prompt.py` (builder programmatico del prompt)
- `render_prompts_for_review.py` (rendering offline per review umana)

## Input
- `data/vocabulary/<attribute>.txt` × 7 (top-200 lemmi per attributo, output Fase 2-3)
- `CURATED_BIGRAMS` hard-coded in `rewrite_prompt.py` (filtrati a mano dai bigrammi auto-estratti)
- `ATTRIBUTE_CONFIG` hard-coded in `rewrite_prompt.py` (template + intro + few-shot examples)

## Output
- `data/prompts/<attribute>.md` × 7 (prompt completi resi su disco per ispezione)
- Funzioni Python `build_system_prompt(attr)`, `build_user_prompt(attr, caption)` consumate dalla Fase 7-8

## Cosa fa la fase

Costruisce un **system prompt distinto per ognuno dei 7 attributi sensoriali** (~5 KB ognuno) componendo dinamicamente:

### Componenti del prompt

1. **Role + framing** (italiano):
   ```
   Sei un esperto di analisi sensoriale del Trentingrana, formaggio grana
   stagionato del Trentino. Il tuo compito è riscrivere brevi annotazioni di
   panelisti italiani in didascalie chiare, naturali e di stile uniforme,
   adatte a descrivere un'immagine di una sezione del formaggio.
   ```

2. **ATTRIBUTO + descrizione one-line**:
   - Profumo: "impressioni olfattive all'apertura/al naso"
   - Aroma: "impressioni retro-olfattive in bocca"
   - Sapore: "impressioni gustative in bocca"
   - Texture: "sensazioni tattili in bocca: solubilità, friabilità, umidità, presenza di cristalli"
   - Spessore della Crosta: "spessore e regolarità della crosta (zone piatte, scalzo, spigoli, sottocrosta)"
   - Struttura della Pasta: "struttura e omogeneità della pasta (frattura, occhiatura, fessure, granulosità, distribuzione spaziale)"
   - Colore della Pasta: "colore e uniformità della pasta (alone, macchie, omogeneità, sfumature)"

3. **STILE template**: ancora la forma dell'output:
   - Profumo → `Profumo …` / `Note olfattive di …`
   - Aroma → `Aroma …` / `Note aromatiche …`
   - Sapore → `Sapore …` / `Al palato …`
   - Texture → `Texture …` / `In bocca …`
   - Spessore → `Crosta …` / `La crosta presenta …`
   - Struttura → `Pasta …` / `La pasta presenta …`
   - Colore → `Pasta di colore …` / `Colore della pasta …`

4. **11 regole numerate** (`RULES_BLOCK`):

   1. **Conserva** info pertinenti, scarta off-attribute
   2. **Quantitativo → qualitativo** (mm/cm/% banditi nell'output)
   3. **Espansione abbreviazioni**: `leg./legg.` = leggermente; `po'/po` = poco; `abb.` = abbastanza; `tend.` = tendente
   4. **Riformula** dialetto/colloquiale/telegrafico in italiano standard
   5. **Riduci sinonimi** al lessico tipico (vocabolario controllato)
   6. **ZERO INVENZIONE** — vieta `tipico`, `caratteristico`, `presente`, `evidente` come qualificatori inventati
   7. **Strip giudizi puri** (`buono`, `brutto`, `ottimo`) e meta-comments, MA mantieni negazioni descrittive (`Non paglierino` → `non paglierina`)
   8. **Domande → affermazioni**: `Eucalipto?` → `Note di eucalipto.`
   9. **Lunghezza calibrata**: 1 parola → 2-4 parole output; ricche → ~18 max
   10. **Output SOLO la frase** (no quote, no prefix, no spiegazione)
   11. **`NON_DESCRITTO` escape** per caption info-free: pure scoring meta, fragment incomprensibili, off-attribute

5. **Regole extra per attributo** (solo Spessore della Crosta): tabella mm/cm con bucket, allineata alla qualitatizzazione deterministica di Fase 4:
   ```
   < 8 mm  o < 0,8 cm   → "molto sottile"
   8-9 mm  o 0,8-0,9 cm → "sottile"
   10-13 mm o 1,0-1,3 cm → "mediamente spessa" / "spessore medio"
   14-17 mm o 1,4-1,7 cm → "spessa"
   ≥ 18 mm o ≥ 1,8 cm    → "molto spessa"
   ```
   Nota esplicita: `1 cm = 10 mm = mediamente spessa`.

6. **Top-60 lemmi vocabolario** dell'attributo (estratti da `data/vocabulary/<attr>.txt`), presentati come *"preferisci questi termini quando applicabili, ma non forzarli"*

7. **CURATED_BIGRAMS** — idiom multi-parola filtrati a mano (10-12 per attributo). Esempi:
   - Profumo: `latte cotto`, `panna cotta`, `burro fuso`, `burro fresco`, `nota lattica`
   - Sapore: `leggermente piccante`, `buona persistenza`, `dolce sapido`
   - Texture: `cristalli abbondanti`, `molto solubile`, `lascia bocca`
   - Struttura: `frattura regolare`, `microocchiatura diffusa`, `bella grana`

8. **6 few-shot examples per attributo**, estratti da caption REALI del dataset, deliberatamente coprenti:
   - Single-word fragment (`Crauti` → `Profumo di crauti.`)
   - Telegrafico (`Sa di malga` → `Aroma di malga.`)
   - Negazione (`Non equilibrato salato` → `Sapore non equilibrato e salato.`)
   - Interrogativo (`Eucalipto?` → `Note olfattive di eucalipto.`)
   - Mixed meta+descrittore (`amaro deciso e penalizzante` → `Sapore amaro e deciso.`)
   - Abbreviazioni (`leg amaro` → `Sapore leggermente amaro.`)
   - Embedded measurements (Spessore: `Spigoli sopra 20mm Piatto 10mm circa Media 12mm` → `Crosta con spigoli pronunciati, parte piatta mediamente spessa e spessore medio.`)

### User prompt

```
Riscrivi questa annotazione in una didascalia per il tag "{attribute}",
seguendo le regole.
ANNOTAZIONE: "{caption}"
DIDASCALIA:
```

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **One prompt per attributo** | Permette template, vocabolario, esempi specifici per ogni dominio sensoriale; cattura registro distintivo | Prompt unico avrebbe diluito il focus e mescolato lessici |
| **Prompt in italiano** | Il LLM lavorerà in italiano end-to-end; istruzioni in italiano riducono code-switching nell'output | Prompt EN + output IT crea comportamenti misti, occasionali italianismi anglicizzati |
| **Regola 6 "ZERO INVENZIONE"** | Faithfulness deve essere un vincolo esplicito, non implicito; vieta `tipico`, `caratteristico`, `presente`, `evidente` come qualificatori non presenti nella sorgente | Senza regola 6, il LLM "abbellisce" il sensoriale con qualificatori inventati |
| **Regola 11 `NON_DESCRITTO`** | Single-token escape è triviale da filtrare post-hoc; evita che il LLM "panichi" e produca multi-line explanations su input vuoti | Lasciare il LLM libero produceva output multi-paragrafo non parsabili (osservato nel pilot) |
| **Bigram CURATI a mano** | I bigrammi auto-estratti contengono artefatti di co-occorrenza (`panna burro` da liste virgolate); solo idiom genuini entrano nella lista presentata al LLM | Usare bigrammi raw avrebbe spinto il LLM verso falsi idiomi |
| **Few-shot reali, non inventati** | Mantengono il LLM in distribution; coprono i casi difficili specifici di QUESTO dataset | Esempi sintetici avrebbero introdotto bias e rotto la naturalezza |
| **Regola sulle negazioni esplicita** | Senza, il LLM tendeva a perdere `Non paglierino` confondendolo con meta. Esplicitare = `Non paglierino → non paglierina` (esempio dentro la regola 7) | Affidamento al senso comune del LLM era inaffidabile |
| **Tabella mm/cm in `extra_rules` per Spessore** | Allinea il LLM ai bucket deterministici di Fase 4 → coerenza tra deterministic+LLM. Equivalenza esplicita `1 cm = 10 mm = mediamente spessa` | Senza, mismatch sistematico tra `1 cm` deterministico e LLM (osservato nel pilot) |
| **Vocabolario come "preferisci se applicabile"** | Soft constraint, non hard — il LLM mantiene flessibilità per descrittori legittimi fuori vocab | "Use only" avrebbe rotto descrittori reali rari come `colpa`, `solvente`, `sangue` |
| **Top-60, non top-200** | 60 è il "core" del lessico, abbastanza per ancorare lo stile; 200 sarebbe stato rumore in prompt | Top-200 avrebbe gonfiato il prompt a ~10 KB senza guadagno |
| **`render_prompts_for_review.py` separato** | Permette ispezione del prompt finale senza costo API; supporta regression testing del prompt | Senza review pre-API, prompt errato avrebbe costato $4,50 in batch sprecato |
| **`_VOCAB_BLACKLIST = {"all'apertura"}`** | Esclude lemma fuorvianti che il bigram-extraction ha catturato come singolo token (apostrofo come word boundary) | Includere = LLM tratta come parola sola |
| **Esempio "marcio, putrido," → "Profumo marcio e putrido."** dentro la regola 11 | Mostra esplicitamente al LLM che caption con descrittore + meta NON deve usare `NON_DESCRITTO` | Senza esempio, il LLM era over-cautious (4,7% NON_DESCRITTO al primo round) |

## Problemi evitati

- **Hallucination strutturale**: la regola 6 (zero invenzione) + regola 7 (rimuovi giudizi) + few-shot con casi limite riducono drasticamente il rischio di descrittori inventati. Validazione post-batch (Fase 8): zero descrittori inventati rilevabili in 7.689 output.
- **Format violation su input difficili**: la regola 11 cattura tutti i casi "no signal" senza panico. Validazione: zero multi-line outputs dopo post-processing.
- **Inconsistenza mm/cm**: la tabella esplicita in `extra_rules` allinea il LLM al deterministico. Validazione: zero discrepanze `1 cm` vs `10 mm` nell'output finale.
- **Drift di stile tra le 7 chiamate**: il template per attributo + few-shot specifici garantiscono uniformità di output. Importante per il confronto Step 2 tra 3 architetture diverse (lo stile non deve diventare un confounder).
- **Costo di prompt iteration**: il rendering offline permette ispezione gratuita prima di ogni nuovo round.
- **Loss di descrittori legittimi su negazioni**: la regola 7 esplicita protegge le 200+ caption con `non` descrittivo.
- **Off-attribute leakage**: la regola 1 ("ignora osservazioni che riguardano un altro attributo") forza separation pulita tra i 7 attributi anche quando i panelisti mescolano.

## Esempio di prompt completo (Profumo)

Lunghezza ~5 KB. Struttura:

```
[Role + framing — 5 righe]

ATTRIBUTO: Profumo — Profumo del formaggio (impressioni olfattive...)

STILE: Una frase che inizia con "Profumo …" o "Note olfattive di …".

REGOLE OBBLIGATORIE: [11 regole numerate, ~80 righe]

LESSICO TIPICO PER QUESTO ATTRIBUTO (preferisci questi termini quando
applicabili, ma non forzarli se l'annotazione non li suggerisce):
  latte, cotto, burro, formaggio, crosta, panna, fresco, nota, ...
  [60 lemmi]

ESPRESSIONI MULTI-PAROLA TIPICHE (mantieni invariate quando presenti):
  latte cotto, panna cotta, burro fuso, burro fresco, brodo vegetale,
  brodo animale, frutta secca, burro sciolto, intensità moderata,
  nota lattica, all'apertura, lattico cotto

ESEMPI (6 casi reali del dataset):
  Annotazione: "Crauti"
  Didascalia : "Profumo di crauti."

  Annotazione: "burro fresco, note lattiche prevalenti, poco complesso"
  Didascalia : "Profumo di burro fresco con note lattiche prevalenti, poco complesso."

  Annotazione: "Non molto intenso"
  Didascalia : "Profumo poco intenso."

  Annotazione: "Eucalipto?"
  Didascalia : "Note olfattive di eucalipto."

  Annotazione: "Lievito pane?"
  Didascalia : "Note olfattive di lievito e pane."

  Annotazione: "leg di stantio"
  Didascalia : "Profumo leggermente stantio."
```
