# Fase 2 — Costruzione vocabolario controllato

**Script**: `build_vocabulary.py`

## Input
- `data/intermediate/captions_prepared.csv` (39.356 righe)

## Output
- `data/vocabulary/<attribute>.txt` × 7 (top-200 lemmi con surface forms e count)
- `data/vocabulary/bigrams_<attribute>.txt` × 7 (top-80 bigrammi)
- `data/vocabulary/vocabulary.csv` (lista flat combinata)
- `data/vocabulary/_summary.txt` (overview)

## Cosa fa la fase

Estrae per ogni attributo sensoriale i lemmi più frequenti e i bigrammi multi-parola, applicando lemmatizzazione italiana custom basata su:
- Mappe deterministiche di abbreviazioni e typo
- Restoration di accenti finali
- Dizionario `SPECIAL` per casi ambigui
- Merge corpus-driven plurale ↔ singolare

### Pipeline interna

1. **Tokenizzazione**: regex `[a-zàèéìòù']+` (preserva accenti italiani e apostrofi)
2. **Espansione abbreviazioni**:
   - `ABBREV_MAP` (18 entry): `po'`/`po` → `poco`, `legg.`/`leg.` → `leggermente`, `abb.` → `abbastanza`, `tend.` → `tendente`, `perchè`/`perche` → `perché`, `piu`/`piu'` → `più`
3. **Correzione typo**:
   - `TYPO_MAP` (28 entry curate dall'audit): `microcchiatura` → `microocchiatura`, `granoloso` → `granuloso`, `intensita` → `intensità`, `florale` → `floreale`, `crosts` → `crosta`, ecc.
4. **Drop**:
   - Token con cifre
   - `UNIT_TOKENS` (11 entry): `mm`, `cm`, `m`, `kg`, `g`, `%`, `ml`, `km`, `mt`, `mts`, `cms`
   - Token di lunghezza ≤ 2
5. **Restoration accenti** (`ACCENT_RESTORE`): `intensita` → `intensità` solo se la forma accentata è già attestata nel corpus
6. **Lemmatizzazione**:
   - `SPECIAL` dictionary (~80 entry) per casi ambigui dove suffix stripping naive sbaglia (`occhi/occhio/occhiatura`, `cotto/cotta/cotti/cotte` → tutti `cotto`)
   - Merge corpus-driven (`merge_inflections`):
     - Tok in `-i`: prova `-o` e `-e` come singolare
     - Tok in `-e`: prova `-a` come singolare femminile
     - Tok in `-a`: prova `-o` come maschile (per coppie aggettivali)
     - Forme apocopate: `buon` + vocale → `buono/buona`
     - Participi: famiglie `-ato/-ata/-ati/-ate`, `-uto`, `-ito`
     - Vincitore = forma più frequente (heuristic stabile)
   - Second pass: cluster per stem (vocale finale rimossa) per famiglie senza singolare maschile attestato
7. **Bigrammi**: estratti dopo lemmatizzazione, escludendo coppie con stopword
8. **Output filtrato**: top-200 lemmi per attributo con `count ≥ 3` (`MIN_LEMMA_COUNT`)

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Lemmatizzatore custom invece di spaCy/nltk** | Lib italiane sbagliano sistematicamente sul lessico sensoriale: `panna`→`panno`, `latte`→`latto`, `leggermente`→`legger`. Zero dipendenze pesanti | spaCy `it_core_news_sm` avrebbe richiesto post-correzione massiccia |
| **`SPECIAL` + corpus-driven merge** | Solo lemma con entrambe le forme attestate vengono uniti — evita over-collapsing di antonimi | Suffix stripping generico avrebbe collassato `latte`+`lattei`, `carico`+`scarico`, `bella`+`bolla` |
| **Vocabolario come "anchor", non "lexer"** | Il LLM parla italiano: gli serve uno stile da imitare, non un dizionario chiuso da rispettare | Vocabolario chiuso forzato avrebbe rotto descrittori legittimi non in lista |
| **Drop di unità di misura dal vocabolario** | Le unità non hanno valore qualitativo; devono essere qualitatizzate non vocabolarizzate | Includerle avrebbe inquinato il prompt con "preferisci `mm`" |
| **`ACCENT_RESTORE` con check di attestazione** | Restituisce `intensità` da `intensita` solo se `intensità` è già nel corpus → zero falsi positivi | Restore senza check avrebbe creato `cita`→`città` su token come `acidità` (rotti) |
| **Bigrammi da corpus, ma poi filtrati a mano in Fase 6** | I bigrammi auto-estratti contengono artefatti di co-occorrenza (`panna burro` da liste virgolate dei panelisti) | Usare bigrammi raw avrebbe spinto il LLM su falsi idiomi |
| **Stopword list scritta a mano** | Le liste standard italiane includono `molto`, `poco`, `leggermente` che SONO informative qui (intensificatori sensoriali) | Stopword standard avrebbe rimosso `molto piccante` |
| **Adverbi `-mente` non collassati** | `leggermente` rimane forma autonoma, non viene ridotto a `legger` | Stem da `-mente` restituiva radici incomprensibili e perdeva il marker avverbiale |
| **Vincitore = forma più frequente** | Heuristic stabile e deterministica per merge | Forma più "canonica" linguisticamente richiederebbe lookup in dizionario esterno |
| **`MIN_LEMMA_COUNT = 3`** | Cut-off contro hapax legomena e typo idiosincratici | Includere tutto avrebbe inflato il vocabolario con noise |
| **`TOP_N = 200` per attributo** | Top-200 cattura ~95% del segnale; il prompt usa solo i top-60 | Più alto = noise, più basso = miss del lessico tecnico raro ma rilevante |

## Problemi evitati

- **Collasso di antonimi**: `carico`/`scarico`, `equilibrato`/`squilibrato`, `gradevole`/`sgradevole`, `bella`/`bolla` rimangono distinti grazie al check di attestazione bidirezionale.
- **Inflazione del vocabolario con varianti morfologiche**: `cotto/cotta/cotti/cotte` = 1 lemma `cotto`, non 4 lemmi separati. Stessa logica per `tostato`, `fermentato`, `lattico`, `regolare`, `omogeneo`, `granuloso`, `piccante`, `amaro`, `salato`, `acido`, `dolce`, `intenso`, `leggero`.
- **Perdita del lessico Trentingrana-specifico**: termini tecnici come `microocchiatura`, `paglierino`, `sottocrosta`, `tirosina`, `unghia`, `scalzo`, `mou`, `friabilità`, `solubilità` sono nel dominio sensoriale standard del grana e vengono preservati nel `SPECIAL` o emergono naturalmente con count ≥ 3.
- **Bias verso anno 2018**: il vocabolario è costruito sull'unione dei 4 anni (39.356 righe), pesato per frequenza, non sbilanciato verso il singolo workbook con più dati.
- **Drift di accenti**: `intensita` → `intensità` solo se `intensità` esiste; altrimenti il token resta scartato (lunghezza ≤ 2 dopo strip dell'apostrofo, oppure caduto come typo non gestito).
- **Errori sui plurali in `-i`**: i nomi maschili in `-io` (es. `taglio` → `tagli`) vengono gestiti correttamente sia dalla regola `tok+"o"` (`tagli` → `taglio`) sia dalla regola `tok[:-1]+"e"` (per casi tipo `latti` → `latte`).

## Statistiche output

### Token totali per attributo (post-stopword)

| Attributo | Token totali | Lemmi unici (count≥3) | Top lemmi |
|---|---:|---:|---|
| Profumo | 24.600 | 636 | `cotto`, `burro`, `latte`, `nota`, `leggero`, `panna`, `intenso`, `intensità` |
| Aroma | 15.186 | 506 | `cotto`, `burro`, `formaggio`, `crosta`, `nota`, `latte`, `lattico`, `panna` |
| Sapore | 23.296 | 469 | `piccante`, `salato`, `amaro`, `dolce`, `umami`, `acido`, `equilibrato`, `sapido` |
| Texture | 24.652 | 504 | `cristallo`, `solubile`, `asciutto`, `granuloso`, `friabile`, `morbido`, `pastoso`, `grana` |
| Spessore della Crosta | 11.275 | 252 | `piatto`, `scalzo`, `spessa`, `colore`, `crosta`, `spigoli`, `sottile`, `sfumata` |
| Struttura della Pasta | 41.676 | 777 | `frattura`, `grana`, `stirata`, `microocchiatura`, `regolare`, `centrale`, `omogeneo`, `struttura` |
| Colore della Pasta | 26.285 | 401 | `carico`, `chiaro`, `alone`, `omogeneo`, `giallo`, `centrale`, `centro`, `colore` |

(Valori esatti da `data/vocabulary/_summary.txt`.)

### Esempi di bigrammi estratti

- Profumo: `latte cotto`, `panna cotta`, `burro fuso`, `burro fresco`, `nota lattica`
- Aroma: `latte cotto`, `frutta secca`, `brodo vegetale`, `lattico cotto`
- Sapore: `leggermente salato`, `leggermente piccante`, `buona persistenza`
- Texture: `cristalli abbondanti`, `molto solubile`, `leggermente sabbioso`
- Spessore: `crosta sottile`, `spigoli pronunciati`, `parte piatta`
- Struttura: `frattura regolare`, `microocchiatura diffusa`, `bella grana`
- Colore: `alone centrale`, `giallo paglierino`, `colore omogeneo`
