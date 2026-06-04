# Fase 0 — Costruzione tabella unificata immagine ↔ commento

**Script**: `build_dataset.py`

## Input
- `data/TrentinGrana/` — 2.745 immagini BMP (1024×768) organizzate in cartelle anno → seduta
- `data/GT commenti liberi/Commenti TOT_2018.xlsx`
- `data/GT commenti liberi/Commenti liberi_QTG_2019.xlsx`
- `data/GT commenti liberi/Commenti liberi_QTG_2020.xlsx`
- `data/GT commenti liberi/Commenti liberi_TEST_2021.xlsx`
- `data/GT commenti liberi/codifiche/codifica caseifici.xlsx` (mappa caseifici ↔ codici prodotto)
- `data/GT commenti liberi/codifiche/date_sedute_2018.csv`

## Output
- `data/intermediate/unified_dataset.csv` (51.988 righe)
- `data/images_flat/` (copia flat delle BMP, gitignorata)

## Cosa fa la fase

1. **Carica il codebook** che mappa `dairy_id` (TN_302) ↔ `product_code` (C0A) ↔ lettera (A). 16 caseifici totali. Triplica le chiavi per accettare anche le forme `TN302` e `302` che compaiono nei filename del 2018:
   ```
   m["TN_302"] = "C0A"
   m["TN302"] = "C0A"
   m["302"] = "C0A"
   ```

2. **Carica i commenti** da 4 workbook Excel, ognuno con una sheet per attributo sensoriale. Schema diverso tra anni:
   - **2018**: `Sogg, Seduta, Prod, score, Commenti` con punteggi panel-level (decimal italiano `'7,48'` parsato come float)
   - **2019/2020/2021**: `Data Seduta, N° Seduta, Bimestre, Data Produzione, Panelista, Prodotto, Commenti` senza score column

3. **Walk** ricorsivo delle BMP, parse dei filename con 5 regex distinte:
   - 2 pattern data (`2018-08-29` e `04-09-2019` / `03_02_2021`)
   - bimestre romano (I-X) via `\b(I|II|III|...)\b\s*bimestre`
   - n° seduta via `(\d+)\s*°?\s*Seduta`
   - panel slot `P{n}{a|b}` via `^P(\d+)([ab])`
   - dairy ID con varianti (`TN_3xx`, `TN3xx`, bare `3xx` con lookbehind/lookahead)

4. **Join dairy-level**: chiave `(session_date, product_code)`. Ogni immagine eredita TUTTI i commenti del caseificio in quella seduta (left join — le immagini orfane sopravvivono con campi commento vuoti).

5. **Copia flat** delle immagini in `data/images_flat/` con nomi codificati `cartella__sottocartella__file.bmp` per evitare collisioni. Skip della copia se file di stessa size già presente.

## Scelte chiave e motivazione

| Scelta | Motivazione | Alternativa scartata |
|---|---|---|
| **Join dairy-level, non wheel-level** | I dati non supportano il join per ruota: le immagini codificano l'ID specifico (`612`), i commenti solo il vassoio panelista (`Prodotto = C0D`). Non esiste mappa wheel→Prodotto | Forzare un join 1:1 avrebbe scartato l'80% dei dati |
| **Broadcast a tutte le repliche `a/b` × `Fetta/Grana`** | Più caption per immagine = più dati di training; l'utente lo ha esplicitamente approvato | Aggregare in una caption sola per immagine avrebbe perso variabilità |
| **Left join (orfani inclusi)** | Distinguere orfani veri (sessioni senza commenti) da bug del parser | Inner join nascondeva 460 immagini orfane |
| **Triplice indicizzazione del dairy** (`TN_302`, `TN302`, `302`) | I filename del 2018 usano la forma bare `302` mentre il codebook usa `TN_302` | Senza tripla indicizzazione, il pairing rate del 2018-2019 sarebbe crollato dal 96% allo 0% |
| **Cartella `images_flat/` con encoding `__`** | Filename diversi solo per spazio vs underscore esistono nel dataset originale; flat encoding permette di distinguerli senza collisioni | `os.path.basename` avrebbe fatto collidere file distinti |
| **Replace `\xa0` con spazio normale** | I commenti 2021 contengono non-breaking spaces che rompono i tokenizer downstream | Lasciarli avrebbe causato errori silenziosi nei tokenizer |
| **Parse dei date pattern in due formati** | `2018-08-29` (ISO) e `04-09-2019` (DD-MM-YYYY) coesistono nel naming | Un solo pattern avrebbe perso ~30% delle date |
| **Date scan da deepest path component upward** | I path hanno la data spesso a livello cartella seduta, non sempre nel filename | Scan flat avrebbe pescato date sbagliate da nomi cartelle anno |
| **`read_only=True` su `openpyxl`** | I workbook sono >5 MB; lettura streaming evita OOM | Carica completo richiede 200+ MB RAM |
| **Skip incrementale della copia flat** | Re-run dello script non ricopia 6 GB di BMP se già presenti | Copia ogni volta = 6 GB I/O ripetuto |
| **Detection collisioni flat name** | `if flat in seen_flat: raise` — fail-fast su duplicati invece di sovrascrittura silenziosa | Sovrascrittura silenziosa = data loss |

## Problemi evitati

- **False corrispondenze tra anni diversi**: il join è strict su `(date, product_code)` — un commento del 2018 non può finire su un'immagine del 2021 anche se il caseificio è lo stesso.
- **Perdita di immagini con dairy parsing fallito**: pattern `DAIRY_BARE_RE = (?<![A-Za-z0-9])(\d{3})(?![A-Za-z0-9])` con lookbehind/lookahead per evitare di matchare numeri dentro altre stringhe (es. `TN_305_512` matcherebbe sia `305` che `512` senza il lookaround).
- **Doppia copia delle BMP**: check `dst.exists() and dst.stat().st_size == src.stat().st_size` evita copia ripetuta in re-run incrementali.
- **Dipendenza da path assoluti**: `Path(__file__).resolve().parent` rende lo script portabile tra macchine.
- **Data loss su collisioni flat name**: detection esplicita con `RuntimeError`.
- **Confusione tra session_num parseato dal filename vs dal commento**: la pipeline preferisce quello dal filename (più affidabile, data parsata direttamente) e fallback al commento solo se mancante.

## Statistiche output

- **51.988 righe** totali (immagine, panelista, attributo)
- **2.745 immagini uniche** processate
- **39.510 righe con commento non vuoto** (76%)
- **42.880 righe con score numerico** (panel-level, solo 2018)
- **460 immagini orfane** senza commento corrispondente:
  - ~100 in cartelle "Variazione/Cambio colore grana" sperimentali (filename non standard)
  - ~340 con valid date+dairy ma sessione senza commenti registrati

### Pairing rate per anno

| Anno | Pairing |
|---|---:|
| 2018-2019 | 96% |
| 2019-2020 | 80% |
| 2020-2021 | 83% |
| 2021-2022 | 74% |

### Schema output

```
image_path, image_path_flat, image_filename, view,
year_folder, session_date, session_num, bimester,
panel_slot, panel_replicate, dairy_id, product_code,
panelist, attribute, score, comment,
production_date, comment_source_file
```
