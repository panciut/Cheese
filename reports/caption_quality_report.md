# Report di Analisi Qualitativa — `captions_final.csv`

**Data**: 2026-05-06
**Progetto**: AI4FQC — Project 07 GRANA_Captioning
**File analizzato**: `data/final/captions_final.csv`
**Riferimento consegna**: `AI4FQC-Project Description Template_07_GRANA_Captioning.pdf`

---

## 1. Obiettivo

Verificare la conformità delle caption finali ai requisiti di Step 1 della consegna:

> *"clean and pre-process the textual descriptions of the tasters (e.g., substitute quantitative descriptions with qualitative descriptions, rephrase dialect sentences, enrich telegraphic comments in a more elegant sentence formulation, reduce synonyms, etc)"*

I quattro requisiti analizzati sono:

1. Sostituzione descrizioni quantitative con qualitative
2. Riformulazione di espressioni dialettali/colloquiali
3. Trasformazione di commenti telegrafici in frasi eleganti
4. Riduzione sinonimi e canonicalizzazione del vocabolario

---

## 2. Statistiche generali del dataset

| Metrica | Valore |
|---|---|
| Righe totali | 38.437 |
| Caption uniche (campo `caption`) | 6.095 |
| Rapporto unicità | ~15,8% |
| Colonne testuali della pipeline | 4 (`caption_raw` → `caption_pre` → `caption` → `caption_sentence`) |

La pipeline produce due varianti complementari:

- **`caption`**: forma compatta nominalizzata (es. *"Profumo di crauti."*)
- **`caption_sentence`**: forma estesa con soggetto esplicito (es. *"Il formaggio ha un profumo di crauti."*)

---

## 3. Valutazione per requisito

### 3.1 Quantitativo → Qualitativo — **CONFORME**

La trasformazione delle misure numeriche (mm, cm) in descrittori qualitativi è stata eseguita in modo sistematico e coerente.

**Verifica empirica**: applicando una regex `[0-9]+` sul campo `caption`, **nessuna occorrenza** è stata trovata. Tutti i numeri sono stati rimossi.

**Esempi rappresentativi**:

| `caption_raw` | `caption` |
|---|---|
| Occhio da 8 mm e 3 mm | occhiature di media e piccola dimensione |
| Fessura di 2 cm | fessura pronunciata |
| Due piccole fessure da 1 cm | due piccole fessure |
| Fessura centrale di 3 cm | fessura centrale pronunciata |
| Presenza di un occhio da 5 mm | un occhio di medie dimensioni |
| Un singolo occhio di circa 5mm | un singolo occhio di piccole dimensioni |

La mappatura dimensionale appare coerente:

- **piccolo** → ≤ ~3 mm
- **medio** → ~5 mm
- **grande / pronunciato** → ≥ ~2 cm

### 3.2 Dialetto / Colloquiale → Italiano standard — **PARZIALMENTE CONFORME**

Il filtro su espressioni regionali ha funzionato in alcuni casi, ma sopravvivono espressioni idiomatiche e termini valutativi soggettivi che andrebbero normalizzati.

**Trasformazioni riuscite**:

| `caption_raw` | `caption` |
|---|---|
| Sa di malga | Aroma di malga |
| Peccato per irregolarità di frattura | Pasta con irregolarità di frattura |
| Però crosta fine | Crosta sottile |
| Aree non belle come colore | aree di colore non uniforme |

**Residui problematici**:

| `caption_raw` | `caption` | Problema |
|---|---|---|
| Impasta la bocca | Texture che impasta la bocca | Idiom non normalizzato |
| Tutta spaccata | Pasta tutta spaccata | Registro colloquiale |
| Bella anche abbastanza regolare | Pasta bella e abbastanza regolare | Aggettivo valutativo soggettivo |
| Bella struttura | Texture con bella struttura | Aggettivo valutativo soggettivo |
| Fastidioso in bocca | Texture fastidiosa in bocca | Giudizio soggettivo |
| Consistenza strana | Texture dalla consistenza strana | Descrittore vago |
| Non piacevole con persistenza elevata | Aroma non piacevole con persistenza elevata | Giudizio soggettivo |

**Implicazione per il captioning**: il decoder addestrato su queste etichette imparerà a riprodurre giudizi di valore (*bella*, *strana*, *fastidiosa*) non ancorati a feature visive verificabili. Questo rumore può degradare le metriche BLEU/CIDEr e ridurre l'utilità descrittiva del modello.

### 3.3 Telegrafico → Frase elegante — **CONFORME**

La pipeline a due livelli (`caption` + `caption_sentence`) soddisfa pienamente il requisito di "more elegant sentence formulation".

**Esempi**:

| `caption_raw` | `caption` | `caption_sentence` |
|---|---|---|
| Crauti | Profumo di crauti. | Il formaggio ha un profumo di crauti. |
| Yogurt | Aroma di yogurt. | Il formaggio ha un aroma di yogurt. |
| Forte | Profumo forte. | Il formaggio ha un profumo forte. |
| Polvere | Profumo di polvere. | Il formaggio ha un profumo di polvere. |
| Omogeneo | Crosta omogenea. | La crosta del formaggio è omogenea. |

Il pattern adottato è uniforme: `[soggetto: formaggio/pasta/crosta] + [copula/verbo descrittivo] + [attributo]`. La punteggiatura è normalizzata (un solo punto finale, niente *!* o *...*).

### 3.4 Riduzione sinonimi — **CONFORME**

La canonicalizzazione del vocabolario è efficace. Le 25 caption più frequenti coprono cluster semantici ben definiti:

| Frequenza | Caption canonica |
|---|---|
| 702 | Crosta mediamente spessa. |
| 466 | Crosta sottile. |
| 252 | Sapore salato. |
| 146 | Crosta spessa. |
| 142 | Aroma di panna. |
| 140 | Sapore equilibrato. |
| 134 | Pasta di colore omogeneo. |
| 128 | Texture asciutta. |
| 122 | Sapore leggermente salato. |
| 110 | Sapore piccante. |
| 108 | Sapore leggermente amaro. |
| 104 | Sapore amaro. |
| 104 | Crosta molto sottile. |

I cluster sono coerenti per attributo:

- **Spessore crosta**: `molto sottile / sottile / mediamente spessa / spessa` (4 livelli)
- **Sapore**: `equilibrato / salato / piccante / amaro / acido` con modificatore `leggermente`
- **Texture**: `asciutta / leggermente asciutta / morbida / compatta`

Il rapporto 6.095 caption uniche / 38.437 righe (~15,8%) è coerente con un vocabolario chiuso e standardizzato.

---

## 4. Sintesi del verdetto

| Requisito | Stato | Note |
|---|:---:|---|
| Quantitativo → Qualitativo | ✅ Conforme | Zero numeri residui in `caption` |
| Dialetto → Standard | ⚠️ Parziale | Idiom e aggettivi valutativi sopravvivono |
| Telegrafico → Elegante | ✅ Conforme | Doppia variante `caption` / `caption_sentence` |
| Riduzione sinonimi | ✅ Conforme | Vocabolario chiuso, ~16% unicità |

---

## 5. Problemi minori riscontrati

- **Quoting CSV**: alcune righe (es. linee 124-128 del file) mostrano caption multi-linea con virgolette mal-escapate del tipo `"La pasta...presenta una frattura regolare`. Verificare il quoting CSV prima dell'ingestion nel training pipeline per evitare misinterpretazioni del parser.
- **Discrepanza tra varianti**: in alcuni casi `caption` mantiene un'espressione che `caption_sentence` riformula meglio (e viceversa). Coerenza non sempre garantita.

---

## 6. Raccomandazioni operative

### Priorità ALTA — Secondo passaggio di normalizzazione lessicale

Eseguire un pass LLM mirato sulle ~50-100 caption che contengono lessico valutativo soggettivo. Mappa proposta:

| Termine residuo | Sostituzione oggettiva proposta |
|---|---|
| bella struttura / pasta bella | struttura regolare / pasta regolare |
| consistenza strana | consistenza atipica / consistenza non standard |
| fastidiosa in bocca | astringente / pastosa |
| impasta la bocca | pastosa al palato |
| tutta spaccata | con fessure diffuse |
| non piacevole | con note off-flavour |

### Priorità MEDIA — Validazione del vocabolario

Costruire e versionare un *vocabolario di riferimento* per attributo (Sapore, Aroma, Texture, Crosta, Pasta, Profumo) con i descrittori canonici accettati. Verificare che ogni `caption` finale appartenga al vocabolario.

### Priorità BASSA — Pulizia CSV

Validare il file con un parser CSV strict (es. `pandas.read_csv` con `quoting=csv.QUOTE_ALL`) e correggere righe con escaping anomalo.

---

## 7. Conclusione

Lo Step 1 della consegna è stato eseguito a un livello complessivamente buono. Tre requisiti su quattro sono pienamente conformi; il requisito di normalizzazione del registro linguistico è invece soddisfatto solo parzialmente.

Il principale rischio residuo è la presenza di **giudizi valutativi soggettivi** (*bella*, *strana*, *fastidiosa*, *non piacevole*) che non sono ancorati a feature visive osservabili nelle immagini IRIS. Senza un secondo passaggio mirato, il modello di captioning rischia di apprendere associazioni tra pattern visivi e giudizi soggettivi non riproducibili — un problema noto di *label noise* in dataset sensoriali.

Si raccomanda quindi un secondo round di pulizia lessicale **prima** dell'addestramento dei tre metodi encoder-decoder previsti dal punto 2 della consegna.
