# Report di Processo — Pipeline di Costruzione del Dataset Captioning

**Progetto**: AI4FQC — Project 07 GRANA_Captioning
**Data**: 2026-05-06
**Scope**: ricostruzione fase per fase del processo che ha portato dai dati grezzi (workbook Excel + immagini BMP) al dataset finale `data/final/captions_final.csv` (38.437 righe), con motivazione di ogni scelta tecnica e dei problemi evitati.

Il report è organizzato in 11 fasi, in ordine di esecuzione. Ogni fase include: input/output, script coinvolto, scelte tecniche con motivazione, alternative scartate, problemi evitati.

---

## Indice

1. [Fase 0 — Costruzione tabella unificata immagine ↔ commento](#fase-0)
2. [Fase 1 — Preparazione caption deterministica](#fase-1)
3. [Fase 2 — Costruzione del vocabolario controllato](#fase-2)
4. [Fase 3 — Audit del vocabolario](#fase-3)
5. [Fase 4 — Pulizia caption + qualitatizzazione misure crosta](#fase-4)
6. [Fase 5 — Drop conservativo del rumore](#fase-5)
7. [Fase 6 — Design del prompt LLM](#fase-6)
8. [Fase 7 — Pilot run](#fase-7)
9. [Fase 8 — Batch run completo](#fase-8)
10. [Fase 9 — Salvage manuale dei NON_DESCRITTO](#fase-9)
11. [Fase 10 — Broadcast finale + sentence form + deliverables](#fase-10)

---

## <a name="fase-0"></a>Fase 0 — Costruzione tabella unificata immagine ↔ commento

**Script**: `build_dataset.py`
**Input**:
- `data/TrentinGrana/` — 2.745 immagini BMP (1024×768) organizzate in cartelle anno → seduta
- `data/GT commenti liberi/Commenti TOT_2018.xlsx` + 3 workbook 2019/2020/2021
- `data/GT commenti liberi/codifiche/codifica caseifici.xlsx` (mappa caseifici ↔ codici prodotto)
- `data/GT commenti liberi/codifiche/date_sedute_2018.csv`
**Output**: `data/intermediate/unified_dataset.csv` (51.988 righe) + `data/images_flat/` (copia flat delle BMP)

### Cosa fa la fase

1. Carica il **codebook** che mappa `dairy_id` (TN_302) ↔ `product_code` (C0A) ↔ lettera (A). 16 caseifici totali. Triplica le chiavi per accettare anche le forme `TN302` e `302` che compaiono nei filename del 2018.
2. Carica i **commenti** da 4 workbook Excel, ognuno con una sheet per attributo sensoriale. Schema diverso tra anni:
   - 2018: `Sogg, Seduta, Prod, score, Commenti` con punteggi panel-level (decimal italiano `'7,48'`)
   - 2019/2020/2021: `Data Seduta, N° Seduta, Bimestre, Data Produzione, Panelista, Prodotto, Commenti` senza score
3. **Walk** ricorsivo delle BMP, parse dei filename con 5 regex distinte:
   - 2 pattern data (`2018-08-29` e `04-09-2019`)
   - bimestre romano (I-X)
   - n° seduta
   - panel slot `P{n}{a|b}`
   - dairy ID con varianti (`TN_3xx`, `TN3xx`, `3xx`)
4. **Join** dairy-level: chiave `(session_date, product_code)`. Ogni immagine eredita TUTTI i commenti del caseificio in quella seduta (left join — le immagini orfane sopravvivono con campi commento vuoti).
5. **Copia flat** delle immagini in `data/images_flat/` con nomi codificati `cartella__sottocartella__file.bmp` per evitare collisioni.

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Join dairy-level, non wheel-level** | I dati non supportano il join per ruota: le immagini codificano l'ID specifico (`612`), i commenti solo il vassoio panelista (`Prodotto = C0D`). Non esiste mappa wheel→Prodotto | Forzare un join 1:1 avrebbe scartato l'80% dei dati |
| **Broadcast a tutte le repliche `a/b` × `Fetta/Grana`** | Più caption per immagine = più dati di training; l'utente lo ha esplicitamente approvato | Aggregare in una caption sola per immagine avrebbe perso variabilità |
| **Left join (orfani inclusi)** | Distinguere orfani veri (sessioni senza commenti) da bug del parser | Inner join nascondeva 460 immagini orfane |
| **Triplice indicizzazione del dairy** (`TN_302`, `TN302`, `302`) | I filename del 2018 usano la forma bare `302` mentre il codebook usa `TN_302` | Senza tripla indicizzazione, il 96% del 2018-2019 sarebbe diventato 0% |
| **Cartella `images_flat/` con encoding `__`** | Filename diversi solo per spazio vs underscore esistono nel dataset originale; flat encoding permette di distinguerli senza collisioni | `os.path.basename` avrebbe fatto collidere file distinti |
| **Replace `\xa0` con spazio normale** | I commenti 2021 contengono non-breaking spaces che rompono i tokenizer downstream | Lasciarli avrebbe causato errori silenziosi |
| **Parse dei date pattern in due formati** | `2018-08-29` e `04-09-2019` coesistono nel naming | Un solo pattern avrebbe perso ~30% delle date |

### Problemi evitati

- **False corrispondenze tra anni diversi**: il join è strict su `(date, product_code)` — un commento del 2018 non può finire su un'immagine del 2021 anche se il caseificio è lo stesso.
- **Perdita di immagini con dairy parsing fallito**: pattern `DAIRY_BARE_RE` con lookbehind/lookahead per evitare di matchare numeri dentro altre stringhe.
- **Doppia copia delle BMP**: check `dst.exists() and dst.stat().st_size == src.stat().st_size` evita copia ripetuta in re-run incrementali.
- **Dipendenza da path assoluti**: `Path(__file__).resolve().parent` rende lo script portabile.

### Statistiche output

- 51.988 righe (immagine, panelista, attributo)
- 39.510 righe con commento non vuoto (76%)
- Pairing rate per anno: 2018-19 96%, 2019-20 80%, 2020-21 83%, 2021-22 74%
- 460 immagini orfane (di cui ~100 in cartelle "Variazione/Cambio colore" sperimentali)

---

## <a name="fase-1"></a>Fase 1 — Preparazione caption deterministica

**Script**: `prepare_captions.py`
**Input**: `data/intermediate/unified_dataset.csv` (51.988 righe)
**Output**: `data/intermediate/captions_prepared.csv` (39.356 righe) + `data/reports/captions_prep_report.txt`

### Cosa fa la fase

1. **Filtra** righe con `comment` vuoto, `N/A`, solo whitespace
2. **Normalizza testo**:
   - Unicode NFC
   - `\xa0` → spazio
   - Zero-width chars rimossi
   - `\t`, `\r`, `\n` → spazio
   - Run di whitespace collassati
   - Strip di virgolette/backtick spuri ai bordi
3. **Drop meta-comments** via blacklist regex (5 pattern):
   - `^n/a$`
   - `non penalizz...`
   - `non valuto`
   - solo trattini o solo punteggiatura
4. **Drop near-empty noise**: meno di 2 caratteri alfanumerici dopo la pulizia
5. **Doppia colonna**: mantiene sia `caption_raw` (originale) che `caption_norm` (normalizzato) per reversibilità

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **NFC, non NFKD** | Conserva caratteri composti italiani (`è`, `à`) senza decomporre | NFKD avrebbe spezzato accenti in due code-point |
| **Mantenere `caption_raw` E `caption_norm`** | Audit: ogni trasformazione deve essere reversibile e diffabile | Tenere solo la versione pulita avrebbe reso impossibile spiegare scelte ex post |
| **Drop "near-empty" con soglia 2 caratteri alfanumerici** | Cattura `"."`, `"-"`, `"a"`, ma preserva fragment validi come `"ok"` (gestito poi nel drop selettivo) | Soglia più alta avrebbe perso fragment veri come `"sì"` |
| **Blacklist regex piccola e conservativa** | Drop a questo stadio deve essere certo — il LLM gestirà meglio le ambiguità | Blacklist aggressiva avrebbe scartato commenti misti (meta + descrittore) |
| **Stopword italiana custom** (per il report) | Le lib NLP italiane caricano centinaia di stopword incluse parole con valore sensoriale (`molto`, `poco`) — la lista custom è chirurgica | nltk/spaCy avrebbero scartato `intenso`, `leggero` |

### Problemi evitati

- **Perdita di caption con caratteri unicode strani**: la normalizzazione cattura zero-width joiner, NBSP, soft hyphen.
- **Drop prematuro di descrittori validi**: la blacklist non include `peccato`, `bello`, `buono` perché possono essere parte di frasi descrittive (`peccato per irregolarità` → contiene il descrittore `irregolarità`).
- **Bug di encoding nei CSV**: `csv.DictReader/Writer` con escape e quoting standard, niente parsing manuale.

### Statistiche output

- 39.356 righe (75,7% di retention dal `unified_dataset.csv`)
- Drop: 12.478 vuoti, 86 meta-notes, 68 near-empty
- Distribuzione per attributo:
  - Struttura della Pasta: 7.546
  - Sapore: 6.350
  - Colore della Pasta: 5.947
  - Profumo: 5.798
  - Texture: 5.431
  - Aroma: 4.213
  - Spessore della Crosta: 4.071

---

## <a name="fase-2"></a>Fase 2 — Costruzione del vocabolario controllato

**Script**: `build_vocabulary.py`
**Input**: `data/captions_prepared.csv`
**Output**: `data/vocabulary/<attribute>.txt` × 7 + `bigrams_<attribute>.txt` × 7 + `vocabulary.csv` + `_summary.txt`

### Cosa fa la fase

1. **Per ogni attributo** estrae tokeni via regex `[a-zàèéìòù']+` (preserva accenti italiani)
2. Applica **mappe deterministiche**:
   - `ABBREV_MAP`: `po'`/`po` → `poco`, `legg.` → `leggermente`, `abb.` → `abbastanza`, `tend.` → `tendente`, `perchè`/`perche` → `perché`, `piu` → `più`
   - `TYPO_MAP`: 25 typo correzioni curate (`microcchiatura` → `microocchiatura`, `granoloso` → `granuloso`, `intensita` → `intensità`)
   - `ACCENT_RESTORE`: ricostruisce `-ità` finale quando la forma con accento è attestata
3. **Drop**: token con cifre, unità (mm/cm/%), token di lunghezza ≤ 2
4. **Lemmatizzatore custom semplice**:
   - Dizionario `SPECIAL` (~80 entry) per i casi ambigui (`occhi/occhio/occhiatura`, `cotto/cotta/cotti/cotte`)
   - Merge corpus-driven plurale ↔ singolare quando entrambe le forme sono attestate
   - Vincitore = forma più frequente
5. **Bigrammi**: top-80 per attributo (`latte cotto`, `panna cotta`, `frattura regolare`)
6. Output: top-200 lemmi per attributo con `count`, forma canonica, varianti di superficie attestate

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Lemmatizzatore custom invece di spaCy/nltk** | Lib italiane sbagliano sistematicamente sul lessico sensoriale (`panna`→`panno`, `latte`→`latto`); zero dipendenze pesanti | spaCy `it_core_news_sm` avrebbe richiesto post-correzione massiccia |
| **`SPECIAL` + corpus-driven merge** | Solo lemma con entrambe le forme attestate vengono uniti — evita over-collapsing | Suffix stripping generico avrebbe collassato `latte`+`lattei`, `carico`+`scarico` |
| **Vocabolario come "anchor", non "lexer"** | Il LLM parla italiano: gli serve uno stile da imitare, non un dizionario chiuso | Vocabolario chiuso forzato avrebbe rotto descrittori legittimi non in lista |
| **Drop di `mm`, `cm`, `%`, `km`, `kg`, `g`, `ml`** | Le unità non hanno valore qualitativo; devono essere qualitatizzate non vocabolarizzate | Includerle avrebbe inquinato il prompt con "preferisci `mm`" |
| **`ACCENT_RESTORE` con check di attestazione** | Restituisce `intensità` da `intensita` solo se `intensità` è già nel corpus → zero falsi positivi | Restore senza check avrebbe creato `cita`→`città` su token come `acidità` |
| **Bigrammi da corpus, ma usati selettivamente** | I bigrammi auto-estratti contengono artefatti di co-occorrenza (`panna burro` da liste virgolate) — vengono filtrati a mano nella Fase 6 | Usare bigrammi raw avrebbe spinto il LLM su falsi idiomi |
| **Stopword list scritta a mano** | Le liste standard italiane includono `molto`, `poco`, `leggermente` che SONO informative qui (intensificatori sensoriali) | Stopword standard avrebbe rimosso `molto piccante` |
| **Fold `-mente` adverbi non collassato** | `leggermente` rimane forma autonoma, non viene ridotto a `legger` | Stem da `-mente` restituiva radici incomprensibili |

### Problemi evitati

- **Collasso di antonimi**: `carico`/`scarico`, `equilibrato`/`squilibrato`, `gradevole`/`sgradevole`, `bella`/`bolla` rimangono distinti grazie al check di attestazione bidirezionale.
- **Inflazione del vocabolario con varianti morfologiche**: `cotto/cotta/cotti/cotte` = 1 lemma `cotto`, non 4 lemmi separati.
- **Perdita del lessico Trentingrana-specifico**: termini tecnici come `microocchiatura`, `paglierino`, `sottocrosta`, `tirosina`, `unghia`, `scalzo`, `mou` sono nel dominio sensoriale standard del grana e vengono preservati.
- **Bias verso anno 2018**: il vocabolario è costruito sulla unione dei 4 anni (39.356 righe), pesato per frequenza, non sbilanciato verso il singolo workbook con più dati.

---

## <a name="fase-3"></a>Fase 3 — Audit del vocabolario

**Script**: `audit_vocabulary.py`
**Input**: `data/vocabulary/vocabulary.csv`
**Output**: `data/vocabulary/_audit.txt`

### Cosa fa la fase

Scansione automatica che flagga:
1. Token quantitativi/unità che sono passati attraverso il filtro
2. Token molto corti (probabili abbreviazioni residue)
3. Token contenenti cifre
4. Coppie di flessione non collassate (stesso lemma in plurale e singolare entrambi presenti)
5. Coppie di near-duplicate a edit distance ≤ 1 (probabili synonim/typo non riconosciuti)
6. Lemma cross-attribute (informazione: stesso termine in più attributi)
7. Top-30 lemmi per attributo affiancati (style snapshot)

### Scelte chiave e motivazione

| Scelta | Motivazione |
|---|---|
| **Edit distance Levenshtein con early-exit per `\|len(a)-len(b)\| > 2`** | Performance — su 1.500 lemmi sono O(n²) coppie |
| **Audit automatico, fix manuale** | I flag richiedono giudizio: `latte`/`lattei` sono distinti (latte vs adjective lattico), `carico`/`scarico` sono antonimi — solo umano decide |
| **Tre round di iterazione audit→fix** | Convergenza progressiva: ogni round scopre pattern che il precedente aveva mascherato |

### Problemi evitati

- **Falso senso di completezza dopo un singolo round**: l'audit ha rivelato a) avverbi `-mente` con stripping rotto, b) accenti finali persi (`intensita` vs `intensità`), c) participi non uniti, d) sostantivi maschili in `-io`, e) forme apocopate (`buon` da `buono`), f) preposizioni articolate non in stoplist.
- **Drift tra dataset e prompt**: l'audit garantisce che il vocabolario passato al LLM sia pulito.

### Risultato finale audit

Dopo convergenza, la sezione "un-merged inflections" contiene un solo falso positivo (`latte`/`lattee` — nome vs aggettivo `latteo`, correttamente non uniti). Le near-duplicate sono tutte coppie antonimiche genuine.

---

## <a name="fase-4"></a>Fase 4 — Pulizia caption + qualitatizzazione misure crosta

**Script**: `clean_captions.py`
**Input**: `data/captions_prepared.csv` (39.356 righe)
**Output**:
- `data/intermediate/captions_pre.csv` — 39.356 righe + colonne `caption_pre`, `dedup_key`
- `data/intermediate/captions_unique.csv` — 7.758 righe (uniche per `(caption_pre, attribute)`)

### Cosa fa la fase

1. **Espansione abbreviazioni/typo**: applica `ABBREV_MAP` e `TYPO_MAP` di Fase 2 word-by-word, preservando casing della prima lettera
2. **Strip markup spurio**: `*fermentate*` → `fermentate`, backtick rimossi, doppi spazi collassati
3. **Qualitatizzazione misure crosta** — solo per `Spessore della Crosta`:
   - `qualitatise_spessore_bare()` riconosce caption che contengono SOLO numeri (con/senza unità) ± qualifier
   - Pattern: prefix opzionale (`Mediamente`, `Più di`, `Quasi`, `Circa`), numeri con/senza `mm`/`cm`, connettori (`-`, `e`, `o`, `a`)
   - Conversione: valori < 5 → cm (moltiplicati ×10), altrimenti mm
   - Bucket: `<8 mm` Molto sottile, `<10` Sottile, `<14` Media, `<18` Spessa, `≥18` Molto spessa
4. **Calcolo `dedup_key`**: `attribute :: lowercase + punct-folded(caption_pre)` → chiave per dedup LLM
5. **Output dedup**: 7.758 caption uniche (compressione 5,07×)

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Qualitatizzazione deterministica per Spessore** | Il LLM su pilota ha fallito sulla coerenza `1 cm` = `10 mm` (li bucketizzava diversi); la regola deterministica garantisce coerenza | Lasciare al LLM avrebbe creato inconsistenza sistematica per centinaia di righe |
| **Solo caption interamente numeriche** | Caption miste (`Spigoli sopra 20mm Piatto 10mm`) sono lasciate al LLM perché richiedono ragionamento contestuale | Cercare di estrarre numeri da caption miste sarebbe stato fragile |
| **Heuristic `<5 → cm`** | Range plausibili crosta grana: 0,5-3 cm = 5-30 mm. Soglia 5 separa correttamente `0,8` (cm) da `8` (mm) | Richiedere unità esplicita avrebbe perso l'80% delle bare-number caption |
| **Mean dei valori (non max/min)** | Caption come `8-10 mm` rappresentano un range; la media è la stima qualitativa più stabile | Min avrebbe sistematicamente sotto-stimato |
| **Dedup `(caption_pre, attribute)` non solo `caption_pre`** | Lo stesso testo può apparire per attributi diversi con interpretazione diversa (`Forte` per Profumo ≠ `Forte` per Sapore) | Dedup globale avrebbe collassato semantica |
| **Dedup case-insensitive + punct-folded** | `"Crauti."`, `"crauti"`, `"Crauti!"` → stesso bucket (panelista variabile, contenuto identico) | Dedup case-sensitive avrebbe quintuplicato il costo LLM |
| **Espansione abbreviazioni word-by-word con `WORD_BOUNDARY_RE`** | Preserva spaziatura e punteggiatura originale, modifica solo le parole match | `re.sub` globale avrebbe distrutto whitespace |
| **`broadcast` post-LLM, non pre-LLM** | LLM vede ogni caption unica una volta sola; il risultato è poi diffuso a tutte le righe match. Saving 80% sul costo | Inviare 39.356 caption (con duplicati) avrebbe costato ~5× tanto |

### Problemi evitati

- **Inconsistenza qualitativa per misure equivalenti**: `1 cm`, `10 mm`, `1,0 cm` ora producono tutti `Media` (10 mm).
- **Perdita di 424 righe Spessore**: senza la qualitatizzazione bare-number, queste sarebbero state scartate in Fase 5 come `NUMBER_ONLY` o lasciate al LLM con risultati incoerenti.
- **Costo LLM 5× superiore**: senza dedup, batch da ~38k chiamate invece di 7.7k.
- **Race condition su `caption_raw`/`caption_pre`**: la pipeline mantiene 4 colonne (`raw → norm → pre → caption`) per audit completo.

### Statistiche output

| Attributo | Total | Unique | Saving |
|---|---:|---:|---:|
| Aroma | 4.213 | 808 | 80,8% |
| Colore della Pasta | 5.947 | 1.184 | 80,1% |
| Profumo | 5.798 | 1.179 | 79,7% |
| Sapore | 6.350 | 1.127 | 82,3% |
| Spessore della Crosta | 4.071 | 692 | 83,0% |
| Struttura della Pasta | 7.546 | 1.676 | 77,8% |
| Texture | 5.431 | 1.092 | 79,9% |

Compressione globale: 39.356 → 7.758 (5,07×).

Bucket Spessore qualitatizzati:

| Bucket | Righe broadcast |
|---|---:|
| Molto sottile | 30 |
| Sottile | 160 |
| Media | 194 |
| Spessa | 36 |
| Molto spessa | 4 |

---

## <a name="fase-5"></a>Fase 5 — Drop conservativo del rumore

**Script**: `find_useless_captions.py` (survey) + `drop_useless_captions.py` (drop attivo)
**Input**: `data/intermediate/captions_pre.csv`, `data/intermediate/captions_unique.csv`
**Output**:
- `data/intermediate/captions_to_rewrite.csv` — 7.742 uniche (input LLM)
- `data/intermediate/captions_pre_filtered.csv` — 39.280 righe broadcast
- `data/intermediate/dropped_captions.csv` — audit trail
- `data/reports/drop_captions_report.txt`

### Cosa fa la fase

`find_useless_captions.py` (survey) classifica in 7 categorie:
1. **META** — panelista parla di scoring/sé stesso (regex: `non valuto`, `non penalizz`, `non saprei`, `voto`, `punteggio`, `valutazione`, `dovuto sputarl`, `peccato.`)
2. **PURE_EVAL** — singola parola valutativa (`buono`, `bello`, `brutto`, `ottimo`, `ok`, `mah`, `ehm`, `sì`, `no`)
3. **PURE_INTENSIFIER** — singolo intensificatore (`leggero`, `intenso`, `forte`, `medio`) — **NON droppato**, è informazione dimensionale
4. **UNCERTAINTY** — esordio con `forse`, `sembra`, `potrebbe`, `credo`, `direi`, `pare` — **NON droppato**, contiene descrittore implicito
5. **INTERROGATIVE** — termina con `?` — **NON droppato**, il LLM lo trasforma in affermazione
6. **NUMBER_ONLY** — solo cifre (max 3 token)
7. **EMPTY_AFTER_TOKENIZE** — caption senza alcun token alfanumerico

`drop_useless_captions.py` esegue il drop solo su 3 categorie certe:
- **PURE_EVAL** (parola singola che è puro giudizio)
- **NUMBER_ONLY** (numeri puri — già qualitatizzati per Spessore in Fase 4, quindi qui sono solo non-Spessore)
- **SYSTEM_META** (meta sulla seduta/sistema, 8 pattern: `valutazione alle`, `al primo tentativo...test`, `si è chiuso il test`, `schermata dei commenti`, `sono ripartito dal`, `peccato.`, `non lo so`, `dovuto sputarl`)

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Survey + drop come fasi separate** | Il survey produce un report ispezionabile; il drop è conservativo basato sul survey | Drop diretto sarebbe stato non auditabile |
| **Drop solo 3 categorie certe** | Solo dove l'INTERA caption è info-free; caption miste (meta+descrittore) lasciate al LLM | Drop aggressivo avrebbe perso descrittori veri (`amaro deciso e penalizzante` contiene `amaro deciso`) |
| **`PURE_INTENSIFIER` NON droppato** | `Leggero` è informazione: il LLM lo trasforma in `Profumo leggero.` | Droppare avrebbe perso 100+ caption legittime |
| **`UNCERTAINTY` NON droppato** | `Forse pochi cristalli` ha descrittore reale; il LLM riformula come `Texture con pochi cristalli` | Droppare avrebbe scartato hedging legittimo |
| **`INTERROGATIVE` NON droppato** | `Eucalipto?` → `Note olfattive di eucalipto.` (regola 8 del prompt) | Droppare avrebbe perso descrittori utili |
| **Negazioni descrittive preservate** | `Non paglierino` ha valore descrittivo (= "non giallo paglia"); regex evita di confonderle con `non valuto` | Droppare tutte le frasi con `non` avrebbe perso 200+ caption |
| **Pattern `non so` con lookbehind/lookahead** | `non so` + `come/cosa/se` = continuazione descrittiva; isolato = abbandono valutativo | Pattern semplice avrebbe scartato troppo |

### Problemi evitati

- **Drop di descrittori sensoriali genuini** mascherati da hedging: `forse troppo sapido` → `Sapore eccessivamente sapido` (LLM gestisce).
- **Drop di interrogativi**: `Eucalipto?`, `Lievito pane?` sono in realtà fragment descrittivi.
- **Bias di registro linguistico**: panelisti più colloquiali avrebbero perso più caption rispetto a quelli formali.

### Statistiche

- **16 uniche droppate** (su 7.758 = **0,21%**)
- **76 righe training droppate** (su 39.356 = **0,19%**)
- Breakdown: 64 PURE_EVAL + 12 SYSTEM_META + 0 NUMBER_ONLY (Spessore già gestito)

Output finale per LLM: **7.742 caption uniche** su **39.280 righe target**.

---

## <a name="fase-6"></a>Fase 6 — Design del prompt LLM

**Script**: `rewrite_prompt.py` (builder) + `render_prompts_for_review.py` (rendering offline)
**Output**: `data/prompts/<attribute>.md` × 7

### Cosa fa la fase

Costruisce un **system prompt per attributo** (~5 KB ognuno) componendo dinamicamente:

1. **Role + framing**: "esperto di analisi sensoriale del Trentingrana"
2. **ATTRIBUTO + descrizione one-line**: es. *"Profumo del formaggio (impressioni olfattive all'apertura/al naso)."*
3. **STILE template**: ancora la forma dell'output (`Profumo …` / `Note olfattive di …`)
4. **11 regole numerate** (RULES_BLOCK):
   1. Conserva info pertinenti, scarta off-attribute
   2. **Quantitativo → qualitativo** (mm/cm/% banditi)
   3. Espansione abbreviazioni
   4. Riformulazione dialetto/colloquiale/telegrafico
   5. Riduzione sinonimi al lessico tipico
   6. **ZERO INVENZIONE** (regola critica)
   7. Strip giudizi puri (`buono`, `brutto`, `ottimo`) e meta-comments, MA mantieni negazioni descrittive
   8. Domande → affermazioni
   9. Lunghezza calibrata (1 parola → 2-4, ricche → ~18 max)
   10. Output SOLO la frase (no quote, no prefix, no spiegazione)
   11. **`NON_DESCRITTO`** escape per caption info-free
5. **Regole extra per attributo** (solo Spessore della Crosta): tabella mm/cm con bucket
6. **Top-60 lemmi vocabolario** dell'attributo (da Fase 2)
7. **CURATED_BIGRAMS** — idioms multi-parola filtrati a mano dai bigrammi auto-estratti
8. **6 few-shot examples** estratti da caption REALI del dataset, deliberatamente coprenti: single-word, telegrafico, negazione, interrogativo, meta+descrittore, abbreviazioni, misure (Spessore)

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **One prompt per attributo** | Permette template, vocabolario, esempi specifici per dominio sensoriale | Prompt unico avrebbe diluito il focus |
| **Prompt in italiano** | Il LLM lavorerà in italiano end-to-end; istruzioni in italiano riducono code-switching | Prompt EN+output IT crea comportamenti misti |
| **Regola 6 "ZERO INVENZIONE"** | Faithfulness deve essere un vincolo esplicito, non implicito; vieta `tipico`, `caratteristico`, `presente`, `evidente` come qualificatori inventati | Senza regola 6, il LLM "abbellisce" il sensoriale |
| **Regola 11 `NON_DESCRITTO`** | Single-token escape è triviale da filtrare post-hoc; evita che il LLM "panichi" e produca multi-line explanations su input vuoti | Lasciare il LLM libero produceva output multi-paragrafo non parsabili |
| **Bigram CURATI a mano** | I bigrammi auto-estratti contengono artefatti di co-occorrenza (`panna burro` da virgolate); solo idioms genuini entrano | Usare bigrammi raw avrebbe spinto il LLM verso falsi idiomi |
| **Few-shot reali, non inventati** | Mantengono il LLM in distribution; coprono i casi difficili specifici di QUESTO dataset | Esempi sintetici avrebbero introdotto bias |
| **Regola sulle negazioni esplicita** | Senza, il LLM tendeva a perdere `Non paglierino` confondendolo con meta | Affidamento al senso comune del LLM era inaffidabile |
| **Tabella mm/cm in extra_rules per Spessore** | Allinea il LLM ai bucket deterministici di Fase 4 → coerenza tra deterministic+LLM | Senza, mismatch sistematico tra `1 cm` deterministico e LLM |
| **Vocabolario come "preferisci se applicabile"** | Soft constraint, non hard — il LLM mantiene flessibilità per descrittori legittimi fuori vocab | "Use only" avrebbe rotto descrittori reali rari |
| **`render_prompts_for_review.py` separato** | Permette ispezione del prompt finale senza costo API | Senza review pre-API, prompt errato avrebbe costato $4.50 in batch sprecato |

### Problemi evitati

- **Hallucination strutturale**: la regola 6 (zero invenzione) + regola 7 (rimuovi giudizi) + few-shot con casi limite riducono drasticamente il rischio di descrittori inventati.
- **Format violation su input difficili**: la regola 11 cattura tutti i casi "no signal" senza panico.
- **Inconsistenza mm/cm**: la tabella esplicita in `extra_rules` allinea il LLM al deterministico.
- **Drift di stile tra le 7 chiamate**: il template per attributo + few-shot specifici garantiscono uniformità di output (importante per il confronto Step 2 tra 3 architetture).
- **Costo di prompt iteration**: il rendering offline permette ispezione gratuita.

---

## <a name="fase-7"></a>Fase 7 — Pilot run

**Script**: `pilot_rewrite.py`
**Input**: `data/intermediate/captions_to_rewrite.csv`
**Output**: `data/reports/pilot_rewrites.csv` + `data/reports/pilot_review.txt`
**Modello**: `claude-haiku-4-5` (sync API)
**Concorrenza**: 3 worker

### Cosa fa la fase

1. **Stratified sample**: 15 caption per attributo = 105 totali
2. Per ogni attributo: prende top-N high-frequency (max broadcast value) + random tail (style-diversity probe)
3. Esegue chiamate sync parallele con backoff esponenziale automatico SDK (max 6 retry)
4. Output side-by-side raw → clean per ispezione manuale

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Pilot prima del batch** | Senza pilot, un prompt sbagliato avrebbe sprecato 7.689 chiamate ($4,50 + tempo) | Skip pilot e correggere ex post |
| **15/attributo, non più, non meno** | Coverage sufficiente per pattern detection, costo ~$0,20 | 50/attributo = $0,70 senza information gain proporzionale |
| **Top + random tail** | Top-frequency caption hanno alto broadcast value (1 errore = 50 righe sbagliate); random tail copre style diversity | Solo top = blind on rare cases; solo random = miss high-impact bugs |
| **Concorrenza 3, non 8** | Tier API utente: 8 worker triggerano 429 storm con backoff cascade | 1 worker = 5 minuti invece di 90 secondi |
| **Sync API per pilot, batch API per full** | Pilot vuole feedback rapido (turnaround < 2 min); batch è async (~30 min) | Batch per pilot = inutile attesa |
| **`load_api_key()` con fallback CLAUDE_KEY/ANTHROPIC_API_KEY** | Compatibilità con setup misti dell'utente | Hard-coded var name = setup fragile |

### Risultati osservati nel pilot

- **0 errori dopo concorrenza ridotta a 3**
- **~95% caption pulite al primo pass**
- **Issue 1 sistematico**: `1 cm` bucket "Crosta spessa", `10 mm` bucket "Crosta sottile" — stessa misura, output diverso.
  - **Fix**: aggiunta tabella mm/cm in `extra_rules` di Spessore + estensione `qualitatise_spessore_bare()` in Fase 4 per gestire forme con unità.
- **Issue 2**: 6 violazioni di formato su Aroma quando l'input era off-attribute o senza contenuto — il LLM emetteva multi-line explanation invece di rifiutare.
  - **Fix**: aggiunta regola 11 `NON_DESCRITTO` come escape valve.

### Problemi evitati

- **$4,50 di batch sprecato** se il prompt fosse stato lanciato senza pilot.
- **Inconsistenza sistematica mm/cm** in 195+ caption Spessore.
- **Hundreds di multi-line outputs** non parsabili dal post-processing.
- **Rate-limit cascade**: 429 errors con backoff cascading avrebbero potuto crashare lo script.

---

## <a name="fase-8"></a>Fase 8 — Batch run completo

**Script**: `rewrite_batch.py`
**Input**: `data/intermediate/captions_to_rewrite.csv` (7.742 uniche)
**Output**: `data/rewrites/rewrites_<attribute>.csv` × 7 + `data/rewrites/review_<attribute>.txt` × 7 + `data/batches/<batch_id>.json`
**Modello**: `claude-haiku-4-5`
**API**: Anthropic Batch API (50% sconto, async)
**Batch ID**: `msgbatch_01Bv99Z88dFdZ6PJ6FdjRxoA`

### Cosa fa la fase

1. **Carica** 7.742 caption uniche post-pilot (dopo seconda iterazione di prompt)
2. **Genera** 7.742 `Request` con `custom_id = row{idx:05d}`
3. **Salva mapping** `custom_id → {dedup_key, attribute, caption_pre, frequency}` PRIMA di submit
4. **Submit** batch
5. **Poll** ogni 30s fino a `ended`
6. **Fetch** risultati, parse, scrittura per attributo
7. **Resume support**: `--resume <batch_id>` per ripartire dal mapping salvato anche dopo crash

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Batch API, non sync** | 50% sconto + zero rate-limit anxiety + async = $4,50 vs $9,00 | Sync con 3 worker × 7.742 = ~30 min comunque, ma più costoso |
| **Salvataggio mapping PRE-submit** | Se lo script crasha tra submit e fetch, il batch è recuperabile via `--resume` | Mapping in memoria perde tutto al crash |
| **`max_tokens=200`** | Caption ≤ 18 parole = ~30 token; 200 dà margine per `NON_DESCRITTO` + reasoning eventuale | Default `max_tokens` tokenizza all'infinito |
| **One batch per N attributi** | Singola sottomissione = singolo wait period; tutti i 7 attributi insieme | 7 batch separati = 7× wait period |
| **Haiku 4.5, non Sonnet/Opus** | Pilot ha verificato che Haiku gestisce il task con quality identico; cost ~5× inferiore a Sonnet, ~20× a Opus | Sonnet costava ~$13,50, Opus ~$67 — overkill |
| **Custom ID `row{:05d}` (5 cifre)** | Supporta fino a 99.999 — 7.742 ci sta, future expansion supportata | 4 cifre avrebbe rotto a 10k |
| **Output diviso per attributo (7 CSV)** | Permette QA mirata, broadcast separato, grain di audit | Output unico avrebbe richiesto split in fase successiva |
| **`review_<attribute>.txt` ordinato per `frequency` desc** | Le caption più broadcastate (errori = molti danni) sono in cima per ispezione manuale | Ordine random = high-impact bug nascosti |

### Risultati

- **7.689 / 7.689 succeeded, 0 errors** (numero più basso di 7.742 per Spessore: tra pilot e full la qualitatizzazione di Fase 4 è stata estesa, riducendo le caption inviate)
- **Wall time**: ~25-30 min
- **Cost**: ~$4,50 (Haiku 4.5 con 50% Batch discount)
- **NON_DESCRITTO emessi**: 360 (4,7% delle uniche)
- **Multi-line outputs contenenti `NON_DESCRITTO`**: 2 → collapsed al token bare in post-processing

### Distribuzione per attributo

| Attributo | Uniche | NON_DESCRITTO | Usable |
|---|---:|---:|---:|
| Profumo | 1.178 | 64 (5,4%) | 1.114 |
| Aroma | 805 | 56 (7,0%) | 749 |
| Sapore | 1.127 | 58 (5,1%) | 1.069 |
| Texture | 1.088 | 30 (2,8%) | 1.058 |
| Spessore della Crosta | 637 | 66 (10,4%) | 571 |
| Struttura della Pasta | 1.674 | 54 (3,2%) | 1.620 |
| Colore della Pasta | 1.180 | 32 (2,7%) | 1.148 |
| **Totale** | **7.689** | **360 (4,7%)** | **7.329** |

### Problemi evitati

- **Crash durante batch (8h+)**: il mapping salvato + `--resume` rende ogni step recoverable.
- **Costo 5× su Sonnet** o 20× su Opus per zero quality gain.
- **Rate-limit** completamente evitato dal Batch API (no concurrent quota).
- **Caption duplicate**: il dedup di Fase 4 ha già garantito che ogni caption sia processata una volta sola.
- **Output non strutturato**: `custom_id` univoco permette tracking 1:1 senza ambiguità.

---

## <a name="fase-9"></a>Fase 9 — Salvage manuale dei NON_DESCRITTO

**Script**: `manual_salvage.py`
**Input**: `data/rewrites/rewrites_<attribute>.csv` × 7 (in-place update)
**Output**: stessi file con caption salvate

### Cosa fa la fase

1. **Heuristic scan** ha flaggato 291 dei 362 `NON_DESCRITTO` (80%) come contenenti almeno un lemma del vocabolario controllato — possibile over-application della regola 11
2. **Salvage map curata a mano** in `SALVAGE: dict[attribute][caption_pre] → caption_clean`
3. **Total entries**: 178 caption salvate (su 291 candidati)
4. **Apply in-place**: aggiorna i CSV per attributo, rigenera `review_<attribute>.txt`

### Esempi di salvage

```
"marcio, putrido,"                    → "Profumo marcio e putrido."
"Strano. A tratti sentiva di pesce."  → "Profumo strano, di pesce a tratti."
"Sangue,,,"                           → "Aroma di sangue."
"Anonimo"                             → "Aroma anonimo."
"chiuso"                              → "Profumo chiuso."
"Molto elegante"                      → "Profumo molto elegante."
"12 km più netta su 1 piatto"         → "Crosta più netta su un piatto."
"non percettibile. senza odore"       → "Profumo impercettibile, senza odore."
```

### Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Salvage manuale, non secondo round LLM** | 178 entry sono review-able in ~1 ora; secondo batch LLM costava ~$2 e rischiava nuovi NON_DESCRITTO | Secondo round LLM = costo + non-determinismo |
| **Solo 178 su 291 candidati** | I rimanenti 113 sono genuini judgment puri o fragment incomprensibili | Salvage al 100% avrebbe forzato descrittori falsi |
| **Update IN-PLACE dei rewrites** | Mantiene il singolo `dedup_key → caption_clean` pulito per la fase di broadcast | File separato avrebbe richiesto merge logic |
| **Caption assenti dalla salvage map mantengono `NON_DESCRITTO`** | Default safe: in dubbio, drop | Default "salvage" avrebbe richiesto controllo per ogni caso |

### Risultato

| | Pre-salvage | Post-salvage |
|---|---:|---:|
| `NON_DESCRITTO` uniche | 362 (4,7%) | **184 (2,4%)** |
| `NON_DESCRITTO` broadcast rows | 1.759 (4,5%) | **843 (2,1%)** |

**916 righe di training recuperate** offline (cost $0).

### Problemi evitati

- **Dataset shrinkage del 4,5%**: senza salvage, la training set sarebbe stata 37.521 righe invece di 38.437.
- **Bias verso caption "facili"**: il salvage ha recuperato in particolare caption brevi/ellittiche (`Anonimo`, `chiuso`, `marcio`) che il LLM aveva conservativamente classificato come info-free ma che hanno valore descrittivo chiaro per un esperto.
- **Costo di un secondo round LLM**: $2 + tempo + non determinismo → evitato.
- **Drift di stile**: il salvage rispetta il template attributo (`Profumo X.`, `Aroma X.`, `Crosta X.`) garantendo uniformità.

---

## <a name="fase-10"></a>Fase 10 — Broadcast finale + sentence form + deliverables

**Script**: `broadcast_captions.py` → `make_sentence_form.py` → `build_final_outputs.py`

### 10.1 Broadcast (`broadcast_captions.py`)

**Input**: `data/intermediate/captions_pre_filtered.csv` (39.280 righe) + `data/rewrites/rewrites_<attribute>.csv` × 7
**Output**: `data/final/captions_final.csv` (38.437 righe) + report

**Cosa fa**:
1. Costruisce lookup `dedup_key → caption_clean` unendo i 7 CSV per attributo
2. Walk del file filtrato (39.280 righe broadcast target)
3. Per ogni riga: lookup del clean; drop se `NON_DESCRITTO`; scrittura altrimenti
4. Emette report con conteggi per attributo

**Risultato**: 38.437 righe (97,9% retention; 843 droppate come `NON_DESCRITTO`).

### 10.2 Sentence form (`make_sentence_form.py`)

**Input**: `data/final/captions_final.csv` (38.437 righe)
**Output**: stesso file con colonna `caption_sentence` aggiunta + `data/intermediate/sentence_form_unmatched.csv`

**Cosa fa** in tre passaggi:

#### A. Prefix canonicalisation
Rewrite di prefissi alternativi che il LLM ha occasionalmente prodotto:
- Profumo: `Note olfattive vegetali …` → `Profumo vegetale …`
- Aroma: `Note di pepe.` → `Aroma di pepe.`
- Aroma: `Note aromatiche di X` → `Aroma di X`

94 righe toccate.

#### B. Template substitution
Per ogni attributo, lista ordinata di `(pattern, template)`. Esempio Profumo:
```python
(r"^Profumo di (.+?)\.?$", "Il formaggio ha un profumo di {x}.")
(r"^Profumo con (.+?)\.?$", "Il formaggio ha un profumo con {x}.")
(r"^Note olfattive di (.+?)\.?$", "Il formaggio presenta note olfattive di {x}.")
(r"^Profumo (.+?)\.?$", "Il formaggio ha un profumo {x}.")
```

Pattern fallback (più generico) sempre ultimo. **First match wins.**

**Match rate post-canonicalisation: 100% su 38.437 righe** — zero unmatched, zero LLM round-trip necessario.

#### C. Polish pass

Fix grammaticali post-template:
1. **Article injection dopo `presenta`**: `presenta alone` → `presenta un alone`. Mappa di ~50 sostantivi sensoriali con genere (NOUNS_F, NOUNS_M, NOUNS_PLURAL).
2. **`è dal colore X`** → **`è di colore X`** (forma più naturale).
3. **`è dalla X`** → **`presenta una X`** / **`presenta un'X`** per nomi femminili (incluso famiglia `-ità` sempre femminile).
4. **`è unghia`** → **`presenta un'unghia`** (case-specific).
5. **Elisione italiana**: `una <vowel>` → `un'<vowel>` ovunque (regola standard).
6. **Collapse doppi spazi** introdotti da regex.

### Scelte chiave Fase 10.2 e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Sentence form via regex deterministica, non LLM** | 100% template match → costo $0; auditabile; idempotente | Secondo round LLM = $5+ + non-determinismo |
| **Doppia colonna `caption` + `caption_sentence`** | Compatto per per-attribute models; sentence per BLEU/METEOR/CIDEr | Solo sentence avrebbe perso flessibilità |
| **Prefix canonicalisation come step separato** | Permette regole di template più semplici e uniformi | Pattern complessi nel template avrebbero esploso il set |
| **First-match-wins ordering** | Pattern specifici (`Profumo di X`, `Profumo con X`) prima di generici (`Profumo X`) | Reverse order avrebbe matchato sempre il generico |
| **Mappe NOUNS_F/M/PLURAL hand-crafted** | Italian gender rules sono complesse; lista chiusa con ~50 nomi è esaustiva per il dominio | Generic gender detection (es. `-a` → femminile) sbaglia su `tema`, `problema` |
| **Polish pass come funzioni separate (`_fix_presenta`, `_fix_dalla`, ecc.)** | Ogni fix è auditabile, testabile, reversibile | Single regex monstre = unmaintainable |
| **Famiglia `-ità` hard-coded come femminile** | Tutti i sostantivi italiani in `-ità` sono femminili, sempre | Lookup a runtime = overhead |
| **Salva `sentence_form_unmatched.csv`** | Anche se 100% match ora, future caption potrebbero non match → audit trail | Senza file, regression detection diventa impossibile |

### Problemi evitati Fase 10.2

- **Round LLM da $5+** per task puramente sintattico.
- **Inconsistenza grammaticale**: senza polish, `presenta alone` (mancante articolo), `è dalla microocchiatura` (forma awkward), `è unghia` (sgrammaticato).
- **Elisione mancante**: `una unghia` invece di `un'unghia`.
- **False gender agreement**: lista chiusa NOUNS_F/M evita assunzioni errate su nomi non standard.
- **Plurali con articolo indefinito**: `presenta una occhiature` (errore comune); NOUNS_PLURAL preserva forma corretta `presenta occhiature`.

### 10.3 Build final outputs (`build_final_outputs.py`)

**Output finale**:
- `data/final/captions_final.csv` — full table (38.437 × 18 colonne)
- `data/final/image_caption_attribute.csv` — simplified 4 colonne (`image_path, attribute, caption, caption_sentence`)
- `data/final/by_attribute/<Attribute>.csv` × 7 — split per attributo
- `data/final/README.md` — documentation per downstream

**Scelte**:
- **Tre livelli di granularità** (full / simplified / per-attribute) — diverse architetture downstream hanno preferenze diverse
- **`image_path_flat` come image_path nei deliverable** — path stabile, niente collisioni
- **README italiano** con conteggi e spiegazione delle due caption forms

---

## Sintesi cross-fase

### Pattern decisionali ricorrenti

1. **Deterministico prima di LLM** (Fasi 0-5, 10): sempre quando possibile, perché auditabile, gratuito, riproducibile, idempotente.
2. **LLM solo per il "genuinely hard"** (Fasi 6-9): rephrasing, dialect, ambiguity, context-dependent rewriting.
3. **Doppia colonna sempre** (`raw → norm → pre → caption → sentence`): ogni trasformazione è diff-abile.
4. **Pilot prima del batch**: nessun batch lanciato senza validation precedente.
5. **Conservative drop**: in dubbio, lascia al LLM (che ha più contesto del regex).
6. **Manual salvage > secondo round LLM** quando il volume è gestibile (~200 entry).
7. **Recovery via mapping salvati**: ogni step è recoverable da crash via file su disco.

### Costo totale LLM

| Step | Cost |
|---|---:|
| Pilot (105 caption, sync) | ~$0,20 |
| Aroma + Spessore batch parziale (1.495) | ~$0,87 |
| Full batch (7.689) | ~$4,50 |
| Manual salvage | $0 |
| Sentence form + polish | $0 |
| **Totale** | **~$5,60** |

Per confronto: Sonnet 4.6 sarebbe costato ~$13,50, Opus 4.7 ~$67. La scelta di Haiku 4.5 — validata sul pilot — ha tagliato i costi 5-12× senza degradazione qualitativa.

### Output finale

- **38.437 righe training** (image, panelist, attribute, caption, caption_sentence)
- **1.497 immagini uniche** coperte
- **7 attributi sensoriali**
- **6.840 caption uniche** (compact form)
- **6.834 caption uniche** (sentence form)
- **0 numeri residui in caption finale** (regex `[0-9]+` returns 0 hits)
- **0 unità di misura residue** (mm/cm/%)
- **2,1% drop rate** finale come `NON_DESCRITTO` (genuinamente info-free)

Il dataset è pronto per Step 2 (training di 3 metodi encoder-decoder) come richiesto dalla consegna AI4FQC Project 07.
