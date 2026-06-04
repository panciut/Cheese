# Fase 3 — Audit del vocabolario

**Script**: `audit_vocabulary.py`

## Input
- `data/vocabulary/vocabulary.csv` (output Fase 2)

## Output
- `data/vocabulary/_audit.txt`

## Cosa fa la fase

Sanity-check automatico sul vocabolario costruito in Fase 2, per scoprire problemi che il builder potrebbe aver mascherato. Non modifica il vocabolario — produce solo un report ispezionabile dall'umano per guidare i fix.

### Categorie di flag

1. **Pure-numeric / unit tokens** sopravvissuti: `mm`, `cm`, `%`, token con cifre — devono essere stripped/qualitatizzati a monte
2. **Token molto corti** (≤ 3 char): probabili abbreviazioni residue (`leg`, `legg`, `po`, `mc`)
3. **Token contenenti cifre**: pattern `[0-9]` survives
4. **Coppie di flessione non collassate**: stesso lemma in plurale e singolare entrambi presenti (con frequenze comparabili) — heuristic per spotting di merge mancati
5. **Coppie near-duplicate** a edit distance ≤ 1: probabili synonim/typo non riconosciuti dalla `TYPO_MAP`
6. **Lemmi cross-attribute** (stesso lemma in molti attributi): informativo, non necessariamente un errore
7. **Top-30 lemmi per attributo affiancati**: style snapshot per visual inspection del registro

### Algoritmo edit distance

```python
def edit_distance(a: str, b: str) -> int:
    if a == b: return 0
    if abs(len(a) - len(b)) > 2: return 99   # early exit
    # Levenshtein DP O(n*m)
```

Early exit `abs(len(a)-len(b)) > 2` evita il cost quadratico su coppie palesemente diverse — su 1.500 lemmi totali sono ~1.1M coppie senza cutoff.

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Audit automatico, fix manuale** | I flag richiedono giudizio: `latte`/`lattei` sono distinti (latte vs aggettivo `latteo`), `carico`/`scarico` sono antonimi — solo umano decide | Auto-fix avrebbe distrutto antonimi e omografi |
| **Edit distance Levenshtein con early-exit** | Performance: ~1.500 lemmi → coppie O(n²); cutoff `\|len_diff\| > 2` taglia >90% delle coppie senza falsi negativi rilevanti | Sostituire con algoritmo più sofisticato (Damerau-Levenshtein, soundex) avrebbe aumentato falsi positivi |
| **Cross-attribute lemma listing come informativo** | Termini come `omogeneo`, `regolare`, `intenso` legittimamente compaiono in più attributi → non è errore | Flagging come errore avrebbe creato rumore |
| **Three-round iteration audit→fix** | Convergenza progressiva: ogni round scopre pattern che il precedente aveva mascherato | Singolo round avrebbe lasciato issue residui |
| **`KNOWN_ABBREV` esplicito nello script** | Lookup table per spiegare ai reviewer cosa sono i token sospetti (`leg` → `leggermente`) | Senza spiegazione, i flag sembrerebbero arbitrari |

## Problemi evitati

- **Falso senso di completezza dopo un singolo round**: l'audit ha rivelato in tre round successivi:
  - **Round 1**: avverbi `-mente` con stripping rotto (`leggermente` ridotto a `legger`)
  - **Round 2**: accenti finali persi (`intensita` vs `intensità` non uniti)
  - **Round 2**: participi non uniti correttamente (`fermentato`/`fermentata`)
  - **Round 3**: sostantivi maschili in `-io` (es. `taglio`/`tagli`)
  - **Round 3**: forme apocopate (`buon` da `buono`)
  - **Round 3**: preposizioni articolate non in stoplist (`dagli`, `sugli`)

  Ogni iterazione ha richiesto:
  - Aggiungere entry a `SPECIAL` (Fase 2)
  - Estendere `STOP` (Fase 2)
  - Aggiungere typo a `TYPO_MAP` (Fase 2)
  - Estendere `merge_inflections` (Fase 2)
- **Drift tra dataset e prompt**: senza audit, il vocabolario consegnato al prompt LLM avrebbe incluso noise (mm, leg, abbreviazioni) e collasso falso (antonimi uniti) → output LLM rotto.
- **Over-confidence sulla copertura**: l'audit forza esposizione delle coppie ambigue (`latte`/`lattee`) per decisione umana esplicita.

## Risultato dopo convergenza

Dopo tre round di iterazione audit→fix, lo stato di stabilità è:

- **"Un-merged inflections"**: 1 falso positivo residuo (`latte`/`lattee` — nome `latte` vs aggettivo `latteo` declinato `lattee`, correttamente non uniti)
- **"Near-duplicates"**: tutte le coppie restanti sono antonimiche o omografi distinti:
  - `carico` / `scarico`
  - `equilibrato` / `squilibrato`
  - `gradevole` / `sgradevole`
  - `bella` / `bolla`
  - `chiaro` / `chiari` (preservato perché plurale ha valore distinto qui)
- **"Cross-attribute lemmas"**: `omogeneo`, `regolare`, `intenso`, `leggero`, `nota` legittimamente in più attributi

A questo punto il vocabolario è considerato **prompt-ready** per la Fase 6.

## Note operative

- Lo script è non distruttivo: non modifica `vocabulary.csv` né i file per attributo.
- L'output `_audit.txt` è leggibile da umano, sezionato per categoria.
- I top-30 affiancati per attributo permettono visual inspection del "registro" di ogni attributo (`Sapore` dovrebbe essere dominato da `salato`, `dolce`, `amaro`; `Profumo` da `latte`, `burro`, `cotto`).
- Re-runs dell'audit dopo ogni fix sono economici (zero API, zero I/O pesante).
