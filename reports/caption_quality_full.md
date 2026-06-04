# Report di Analisi Esaustiva — `captions_final.csv`

Analisi pattern-based eseguita su **tutte le righe** del file. Zero costo LLM.

- File: `data/final/captions_final.csv`
- Righe totali analizzate: **38437**
- Script: `analyze_captions_full.py`

## 1. Statistiche per colonna testuale

| Colonna | Uniche | Vuote | Lunghezza media | Lunghezza max |
|---|---:|---:|---:|---:|
| `caption_raw` | 7674 | 0 | 34.3 | 200 |
| `caption_pre` | 7548 | 0 | 34.5 | 202 |
| `caption` | 6840 | 0 | 43.6 | 173 |
| `caption_sentence` | 6834 | 0 | 64.8 | 199 |

Caption identiche al raw (nessuna trasformazione applicata): **0** (0.0%)

## 2. Requisito 1 — Quantitativo → Qualitativo

Conteggio occorrenze numeriche residue per colonna:

| Colonna | Righe con almeno una cifra | Righe con misura+unità (mm/cm/%/m) |
|---|---:|---:|
| `caption_raw` | 3222 | 2020 |
| `caption_pre` | 2226 | 1380 |
| `caption` | 0 | 0 |
| `caption_sentence` | 0 | 0 |

✅ Nessun numero residuo nella colonna `caption`.

## 3. Requisito 2 — Dialetto / Colloquiale → Italiano standard

- Espressioni colloquiali/idiomatiche in `caption`: **370** righe
- Termini dialettali in `caption`: **8** righe
- Lessico valutativo soggettivo in `caption`: **1519** righe
- Lessico valutativo soggettivo in `caption_sentence`: **1517** righe

**Esempi colloquiali/idiomatici residui:**

| row_id | attribute | caption |
|---|---|---|
| 3 | Texture | Texture che impasta la bocca. |
| 16 | Texture | Texture fastidiosa in bocca. |
| 19 | Struttura della Pasta | Pasta tutta spaccata. |
| 330 | Sapore | Sapore pungente in bocca. |
| 812 | Texture | Texture con bella struttura. |
| 826 | Texture | Texture leggermente tenera con bella struttura. |
| 1010 | Texture | Texture che lega in bocca. |
| 1945 | Struttura della Pasta | Pasta con bella struttura, grana omogenea e frattura netta, microocchiatura diffusa molto fine. |
| 4760 | Struttura della Pasta | Pasta con bella struttura e microocchiatura diffusa. |
| 5492 | Texture | Texture che si scioglie bene in bocca, lasciando granelli piccoli e percettibili. |
| 5569 | Texture | Texture che lascia in bocca residui cremosi con presenza di cristalli. |
| 5571 | Texture | Texture morbida che impasta, con qualche cristallo e residuo in bocca. |
| 5574 | Texture | Texture morbida e cedevole, che impasta la bocca, con cristalli presenti. |
| 5878 | Texture | Texture asciutta, granulosa e poco solubile, con residui in bocca. |
| 5956 | Texture | Texture morbida con qualche cristallo, asciutta, tende ad impastare, poca grana e si scioglie in bocca. |

**Esempi lessico valutativo soggettivo (`caption`):**

| row_id | attribute | caption |
|---|---|---|
| 15 | Sapore | Sapore anonimo, poco intenso. |
| 16 | Texture | Texture fastidiosa in bocca. |
| 30 | Sapore | Sapore con buona persistenza. |
| 35 | Struttura della Pasta | Pasta bella e abbastanza regolare. |
| 43 | Aroma | Aroma non piacevole con persistenza elevata. |
| 44 | Texture | Texture dalla consistenza strana. |
| 206 | Profumo | Profumo di buona intensità. |
| 280 | Texture | Texture buona solubilità, leggermente asciutta. |
| 465 | Profumo | Profumo complesso e piacevole. |
| 515 | Struttura della Pasta | Pasta bella ma disomogenea con una grossa parte microocchiata. |
| 516 | Struttura della Pasta | Pasta granulosa, con una parte dalla bella grana. |
| 724 | Sapore | Sapore non dolce e leggermente troppo salato. |
| 725 | Aroma | Aroma non piacevole e persistente. |
| 812 | Texture | Texture con bella struttura. |
| 826 | Texture | Texture leggermente tenera con bella struttura. |

**Esempi termini dialettali residui:**

- `row_id=42` [Aroma]: Aroma di malga.
- `row_id=51744` [Aroma]: Aroma forte con sentori di malga.

## 4. Requisito 3 — Telegrafico → Frase elegante

- Caption molto corte (<8 caratteri) potenzialmente telegrafiche: **0**

**10 caption più lunghe (verifica eleganza/eccessiva verbosità):**

- `row_id=12901` (173 char): Pasta con grana leggermente grossolana, frattura irregolare con gobbe e avvallamenti, microocchiatura diffusa in una zona, qualche occhiatura più grande e piccoli cristalli.
- `row_id=13041` (173 char): Pasta con grana leggermente grossolana, frattura irregolare con gobbe e avvallamenti, microocchiatura diffusa in una zona, qualche occhiatura più grande e piccoli cristalli.
- `row_id=13391` (173 char): Pasta con grana leggermente grossolana, frattura irregolare con gobbe e avvallamenti, microocchiatura diffusa in una zona, qualche occhiatura più grande e piccoli cristalli.
- `row_id=13531` (173 char): Pasta con grana leggermente grossolana, frattura irregolare con gobbe e avvallamenti, microocchiatura diffusa in una zona, qualche occhiatura più grande e piccoli cristalli.
- `row_id=25635` (151 char): Pasta con frattura regolare, microocchiatura inferiore, struttura irregolare al centro con stiratura, zona spugnosa sotto lo scalzo e qualche frattura.
- `row_id=25943` (151 char): Pasta con frattura regolare, microocchiatura inferiore, struttura irregolare al centro con stiratura, zona spugnosa sotto lo scalzo e qualche frattura.
- `row_id=26559` (151 char): Pasta con frattura regolare, microocchiatura inferiore, struttura irregolare al centro con stiratura, zona spugnosa sotto lo scalzo e qualche frattura.
- `row_id=26713` (151 char): Pasta con frattura regolare, microocchiatura inferiore, struttura irregolare al centro con stiratura, zona spugnosa sotto lo scalzo e qualche frattura.
- `row_id=4743` (148 char): Pasta con un'occhiatura di medie dimensioni contenente siero e cristalli, accompagnata da un insieme di piccole occhiature unite al taglio centrale.
- `row_id=4791` (148 char): Pasta con un'occhiatura di medie dimensioni contenente siero e cristalli, accompagnata da un insieme di piccole occhiature unite al taglio centrale.

## 5. Requisito 4 — Riduzione sinonimi

- Caption uniche globali: **6840** su 38437 righe
- Rapporto unicità: **17.80%**

**Caption uniche per attributo:**

| Attribute | Righe | Caption uniche | Rapporto |
|---|---:|---:|---:|
| Struttura della Pasta | 7400 | 1566 | 21.2% |
| Sapore | 6244 | 954 | 15.3% |
| Colore della Pasta | 5844 | 1062 | 18.2% |
| Profumo | 5660 | 1071 | 18.9% |
| Texture | 5309 | 983 | 18.5% |
| Aroma | 4019 | 713 | 17.7% |
| Spessore della Crosta | 3961 | 494 | 12.5% |

**Top 30 caption più frequenti:**

| # | Conteggio | Caption |
|---:|---:|---|
| 1 | 702 | Crosta mediamente spessa. |
| 2 | 466 | Crosta sottile. |
| 3 | 252 | Sapore salato. |
| 4 | 146 | Crosta spessa. |
| 5 | 142 | Aroma di panna. |
| 6 | 140 | Sapore equilibrato. |
| 7 | 134 | Pasta di colore omogeneo. |
| 8 | 128 | Texture asciutta. |
| 9 | 122 | Sapore leggermente salato. |
| 10 | 110 | Sapore piccante. |
| 11 | 108 | Sapore leggermente amaro. |
| 12 | 104 | Sapore amaro. |
| 13 | 104 | Crosta molto sottile. |
| 14 | 100 | Texture leggermente asciutta. |
| 15 | 92 | Aroma cotto. |
| 16 | 90 | Profumo leggero. |
| 17 | 90 | Texture compatta. |
| 18 | 84 | Sapore leggermente acido. |
| 19 | 84 | Pasta con alone centrale. |
| 20 | 82 | Sapore eccessivamente salato. |
| 21 | 76 | Sapore acido. |
| 22 | 74 | Texture pastosa. |
| 23 | 72 | Profumo poco intenso. |
| 24 | 72 | Profumo di panna. |
| 25 | 68 | Crosta regolare. |
| 26 | 64 | Texture con pochi cristalli. |
| 27 | 64 | Aroma di latte cotto. |
| 28 | 62 | Sapore leggermente piccante. |
| 29 | 62 | Pasta stirata. |
| 30 | 62 | Sapore salato e leggermente piccante. |

## 6. Coerenza `caption` ↔ `caption_sentence`

- Righe con possibile incoerenza (>50% parole-chiave caption assenti in sentence): **0**

## 7. Distribuzione per attributo

Attributi attesi: ['Aroma', 'Colore della Pasta', 'Profumo', 'Sapore', 'Spessore della Crosta', 'Struttura della Pasta', 'Texture']
✅ Solo attributi attesi presenti.

## 8. Artefatti / pulizia testuale

- Righe in `caption` con artefatti (.. !! ?? doppi spazi, leading/trailing space): **0**

- Righe con caratteri non-italiani sospetti in `caption`: **0**

## 9. Sintesi finale

| Requisito | Stato | Evidenza |
|---|:---:|---|
| Quantitativo → Qualitativo | ✅ | 0 cifre, 0 unità in `caption` |
| Dialetto/Colloquiale → Standard | ⚠️ | 370 colloquiali, 8 dialettali, 1519 valutativi |
| Telegrafico → Elegante | ✅ | 0 caption < 8 char |
| Riduzione sinonimi | ✅ | 17.8% unicità |
