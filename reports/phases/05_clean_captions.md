# Fase 4 — Pulizia caption + qualitatizzazione misure crosta

**Script**: `clean_captions.py`

## Input
- `data/intermediate/captions_prepared.csv` (39.356 righe, output Fase 1)
- Importa `ABBREV_MAP` e `TYPO_MAP` da `build_vocabulary.py` (Fase 2)

## Output
- `data/intermediate/captions_pre.csv` — 39.356 righe + colonne `caption_pre`, `dedup_key`
- `data/intermediate/captions_unique.csv` — 7.705 righe (uniche per `(caption_pre, attribute)`)
- `data/reports/clean_captions_report.txt`

## Cosa fa la fase

Step deterministico finale prima del LLM. Tre operazioni:

### A. Pulizia testuale word-by-word

1. **NFC unicode**
2. **Strip markup spurio**: `*fermentate*` → `fermentate`, backtick rimossi
3. **Espansione abbreviazioni/typo word-by-word**:
   - Pattern: `r"\b[\w'àèéìòù]+\b"` matcha le parole, ognuna passata a `expand_word()`
   - `expand_word(w)` cerca `w.lower()` in `ABBREV_MAP` poi `TYPO_MAP`, restituisce target preservando il casing della prima lettera
   - Caso speciale: forme tronche `-it'` (`intensit'`) → `-ità` (`intensità`)
4. **Multi-spazio collassato** + **trailing punctuation strip**

### B. Qualitatizzazione misure crosta (solo `Spessore della Crosta`)

Funzione `qualitatise_spessore_bare()` riconosce caption che contengono SOLO numeri (con/senza unità) ± qualifier prefix.

**Pattern accettati**:
- Bare numbers: `"10"`, `"0,8"`, `"11 12"`, `"8 10"`
- Unit-suffixed: `"10 mm"`, `"1 cm"`, `"1,1cm"`
- Range: `"8-10 mm"`, `"9 e 11 mm"`, `"da 10 a 13 mm"`
- Con prefix: `"Mediamente 9 mm"`, `"Più di 1 cm"`, `"Sotto 10 mm"`, `"Quasi 12 mm"`, `"Circa 11 mm"`, `"Sopra 15 mm"`, `"Tra 8 e 10 mm"`, `"Fino a 12 mm"`

**Pipeline interna**:
1. Strip del prefix qualifier (`SPESSORE_FILLER_PREFIX`)
2. Walk del resto, alternando connettori (`SPESSORE_CONNECTOR_RE`: `-`, `/`, `–`, `e`, `o`, `a`, `fino a`, `oltre`) e numeri+unità (`SPESSORE_NUM_UNIT_RE`)
3. Se trova qualcosa che non è numero o connettore → bail out (None) → caption resta per il LLM
4. Conversione unità:
   - `cm` → `val × 10`
   - `mm` → `val`
   - Senza unità: `val < 5` → cm (×10), altrimenti mm
5. Mean dei valori → bucket

**Bucket**:
| Soglia mm | Bucket |
|---|---|
| `< 8` | Molto sottile |
| `8 ≤ x < 10` | Sottile |
| `10 ≤ x < 14` | Media |
| `14 ≤ x < 18` | Spessa |
| `≥ 18` | Molto spessa |

### C. Deduplicazione

`dedup_key = "{attribute} :: {lowercase + punct-folded(caption_pre)}"` → grouping per LLM.

```python
s = caption_pre.lower()
s = re.sub(r"[\.\,;:!\?\-]+", " ", s)
s = re.sub(r"\s+", " ", s).strip()
return f"{attribute}::{s}"
```

Output dedup: 7.705 caption uniche (compressione 5,11× su 39.356).

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Qualitatizzazione deterministica per Spessore** | Il pilot (Fase 7) ha mostrato che il LLM bucketizza inconsistentemente: `1 cm` = "Crosta spessa", `10 mm` = "Crosta sottile" (stessa misura fisica, output diverso). La regola deterministica garantisce coerenza assoluta | Lasciare al LLM avrebbe creato inconsistenza sistematica per centinaia di righe |
| **Solo caption interamente numeriche** | Caption miste (`Spigoli sopra 20mm Piatto 10mm`) sono lasciate al LLM perché richiedono ragionamento contestuale (spigoli vs piatto sono parti diverse della crosta) | Cercare di estrarre numeri da caption miste sarebbe stato fragile, perdita di info contestuale |
| **Heuristic `<5 → cm`** | Range plausibili crosta grana: 0,5-3 cm = 5-30 mm. Soglia 5 separa correttamente `0,8` (cm) da `8` (mm) | Richiedere unità esplicita avrebbe perso l'80% delle bare-number caption |
| **Mean dei valori (non max/min)** | Caption come `8-10 mm` rappresentano un range; la media è la stima qualitativa più stabile | Min avrebbe sistematicamente sotto-stimato; max avrebbe sovra-stimato |
| **Bail-out su token non riconosciuti** | Funzione torna None → caption va al LLM. Conservativa: non forza una qualitatizzazione su input ambiguo | Best-effort interpretation avrebbe introdotto bias silenzioso |
| **Dedup `(caption_pre, attribute)` non solo `caption_pre`** | Lo stesso testo può apparire per attributi diversi con interpretazione diversa (`Forte` per Profumo ≠ `Forte` per Sapore) | Dedup globale avrebbe collassato semantica diversa |
| **Dedup case-insensitive + punct-folded** | `"Crauti."`, `"crauti"`, `"Crauti!"` → stesso bucket (panelista variabile, contenuto identico) | Dedup case-sensitive avrebbe quintuplicato il costo LLM |
| **Espansione abbreviazioni word-by-word con `WORD_BOUNDARY_RE`** | Preserva spaziatura e punteggiatura originale, modifica solo le parole match | `re.sub` globale avrebbe distrutto whitespace |
| **Preservazione del casing della prima lettera** | `Leg.` → `Leggermente` (non `leggermente`); `legg.` → `leggermente` | Lower-casing globale avrebbe rotto la naturalezza dell'output |
| **Broadcast post-LLM, non pre-LLM** | LLM vede ogni caption unica una volta sola; il risultato è poi diffuso a tutte le righe match. Saving 80% sul costo | Inviare 39.356 caption (con duplicati) avrebbe costato ~5× tanto |
| **Output sia full che unique** | `captions_pre.csv` mantiene tutte le righe per la fase di broadcast finale; `captions_unique.csv` è l'input compatto del LLM | File singolo avrebbe richiesto re-grouping in fase 8 |

## Problemi evitati

- **Inconsistenza qualitativa per misure equivalenti**: `1 cm`, `10 mm`, `1,0 cm`, `Mediamente 10 mm` ora producono tutti `Media`. Pre-fix il LLM produceva 4 output diversi.
- **Perdita di 424 righe Spessore**: senza la qualitatizzazione bare-number, queste sarebbero state scartate in Fase 5 come `NUMBER_ONLY` (la regola di drop). Con qualitatizzazione, sopravvivono come righe valide con bucket qualitativo.
- **Costo LLM 5× superiore**: senza dedup, batch da ~38k chiamate invece di 7,7k. A pricing Haiku 4.5 batch, ~$22 invece di $4,50.
- **Race condition su `caption_raw`/`caption_pre`**: la pipeline mantiene 4 colonne (`raw → norm → pre → caption`) per audit completo. Ogni colonna è la trasformazione della precedente, nessuna perdita di provenance.
- **Errori di matching su edge cases Spessore**: la pipeline regex testa esplicitamente prefix, connettori, numeri, unità in sequenza — caption che non rispetta lo schema bail-out invece di essere mis-qualitatizzata.
- **Distruzione del casing**: l'espansione preserva il casing iniziale; output naturale ("Leggermente acido", non "leggermente acido").
- **Decimal italiano vs inglese**: `0,8` è correttamente parsato come `0.8` via `replace(",", ".")`.

## Statistiche output

### Compressione per attributo

| Attributo | Total | Unique | Saving |
|---|---:|---:|---:|
| Aroma | 4.213 | 808 | 80,8% |
| Colore della Pasta | 5.947 | 1.184 | 80,1% |
| Profumo | 5.798 | 1.179 | 79,7% |
| Sapore | 6.350 | 1.127 | 82,3% |
| Spessore della Crosta | 4.071 | 639 | 84,3% |
| Struttura della Pasta | 7.546 | 1.676 | 77,8% |
| Texture | 5.431 | 1.092 | 79,9% |
| **Totale** | **39.356** | **7.705** | **80,4%** |

### Bucket Spessore qualitatizzati

| Bucket | Righe broadcast |
|---|---:|
| Molto sottile | 30 |
| Sottile | 160 |
| Media | 194 |
| Spessa | 36 |
| Molto spessa | 4 |
| **Totale** | **424** |

### Cambio applicato

- ~9% delle righe (~3.500) toccate dalla pipeline (typo/abbrev expansion o markup strip)

### Frequenza distribution (broadcast)

Pattern dominante: 6.595 caption uniche compaiono esattamente 4 volte ognuna — corrisponde al pattern broadcast `a/b × Fetta/Grana` di molte sedute.

### Schema output

`captions_pre.csv`:
```
row_id, image_path_flat, image_path, attribute,
caption_raw, caption_norm, caption_pre, dedup_key,
panelist, session_date, year_folder, session_num, bimester,
view, panel_slot, panel_replicate, dairy_id, product_code
```

`captions_unique.csv`:
```
dedup_key, attribute, caption_pre, frequency, sample_row_id
```
