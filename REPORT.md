# Trentingrana Captioning Dataset — Findings & Plan

This report consolidates everything we've learned about the dataset and the
pipeline built so far. Written before reading the project description PDF, so
the framing here may need adjustment once the official scope is known.

## 1. Dataset overview

The dataset lives under `data/` and has two parallel parts:

### 1.1 Images — `data/TrentinGrana/`

- 2,745 BMP photographs (1024×768 RGB) of Trentingrana cheese wheels.
- Organized by production year folder, then by tasting-session folder:
  - `2018-2019_Trentingrana/` — 28 sessions, folders named `YYYY-MM-DD`.
  - `2019-2020_Trentingrana/` — 5 sessions, grouped by Roman-numeral
    `bimestre` (`I bimestre`, `II bimestre`, …), then session date.
  - `2020-2021_Trentingrana/` — 7 sessions, same bimester structure; also
    contains `Variazione/Cambio colore grana` subfolders with experimental
    color-variation samples not part of regular panels.
  - `2021-2022_Trentingrana/` — 31 sessions, folders named
    `N° Seduta_DD-MM-YYYY`.
- Filename encodes panel slot, dairy, and view, e.g.
  `P3b_TN306_612_Fetta.bmp`:
  - `P{n}{a|b}` — panel slot; `a` and `b` are duplicate photos of the same wheel.
  - Dairy code — `TN_3xx`, `TN3xx`, or bare `3xx` in 2018.
  - Numeric sample id (when present).
  - View: `Fetta` (slice) or `Grana` (close-up of grain). The `Grana` view
    only starts appearing from 2021-2022 onward.

### 1.2 Captions and codebook — `data/GT commenti liberi/`

- One Excel workbook per campaign year, with one sheet per **sensory attribute**:
  `Profumo`, `Sapore`, `Aroma`, `Texture`, `Spessore della Crosta`,
  `Struttura della Pasta`, `Colore della Pasta`.
- 13,159 raw comment rows total across all years/attributes.
- Each row = one panelist's free-text note about one attribute of one wheel
  in one session, optionally with a numeric score.
- Columns vary by year:
  - 2018 file: `Sogg, Seduta, Prod, <score>, Commenti`. Scores stored as
    Italian decimal strings (`'7,48'`).
  - 2019/2020/2021 files: `Data Seduta, N° Seduta, Bimestre, Data Produzione,
    Panelista, Prodotto, Commenti`. **No score column** — those years' scores
    are aggregated jury means in `codifiche/Risultati_2019-21.xlsx` (not
    panelist-level).
  - 2019 file is mostly `N/A` placeholders; only `Aroma` has real entries.
- Codebook `codifiche/codifica caseifici.xlsx` maps dairy IDs ↔ product
  codes ↔ letters: `TN_302 ↔ C0A ↔ A`, …, `TN_338 ↔ C0R ↔ R` (16 dairies).
- `codifiche/date_sedute_2018.csv` maps the 2018 session number to its date.

## 2. Unified table — `data/unified_dataset.csv`

Built by `build_dataset.py`. Joins each image to its panel comments via
`(session_date, product_code)`, with the dairy ID parsed from the filename
and translated to a product code through the codebook.

- 51,988 rows, 2,745 unique images.
- Each row = one (image, panelist, attribute) pairing — one image typically
  produces ~14 rows (7 attributes × ~2 panelists).
- 83% of images have at least one matching comment row:
  - 2018-2019: 96% — 2019-2020: 80% — 2020-2021: 83% — 2021-2022: 74%.
- Rows with non-empty comment text: 39,510 (76%).
- Rows with a numeric score: 42,880 (panelist-level, **2018 only**).

### 2.1 Schema

| column | source | notes |
|---|---|---|
| `image_path` | filesystem | relative to project root |
| `image_path_flat` | flat-copy dir | also project-relative |
| `image_filename`, `view` | filename | view ∈ {Fetta, Grana} |
| `year_folder`, `session_date`, `session_num`, `bimester` | path + comments | session/bimester optional, filled when parseable |
| `panel_slot`, `panel_replicate` | filename `P{n}{a|b}` | a/b are duplicate photos of one wheel |
| `dairy_id`, `product_code` | filename + codebook | TN_302 ↔ C0A, etc. |
| `panelist`, `attribute`, `score`, `comment` | comment workbooks | one of 7 attributes |
| `production_date`, `comment_source_file` | comment workbooks | provenance |

### 2.2 Flat image copy — `data/images_flat/`

All 2,745 BMPs copied (not moved) into a single directory with paths encoded
as filenames using `__` separators, so collisions are impossible. Two source
files in the same folder differing only by space vs underscore are preserved
as distinct names. Both `image_path` (original) and `image_path_flat` (copy)
appear in the unified CSV.

### 2.3 Caveats of the unified table

- **Join is dairy-level, not wheel-level.** Image filenames identify the
  specific wheel (e.g. `P3a_TN306_612_…` — `612` is a wheel id), but
  comments only identify the panelist's tray as `Prodotto = C0D`. Multiple
  wheels of the same dairy in one session inherit each other's comments.
- **`a`/`b` replicates and `Fetta`/`Grana` views are not distinguished by
  comments** — they share the same caption set per (date, dairy).
- **2019 comment workbook is mostly empty.**
- **`production_date`** is a real date in 2019, but a free-text bimester
  string in 2020-2021 (`'NOV-DIC'`, `'SET-OTT'`).
- **460 orphan images** with no matching comment row:
  - ~100 in special color-variation experiment subfolders, with
    non-standard filenames (no dairy ID).
  - ~340 with valid date+dairy but no comment row exists for that
    (date, product_code) — sessions where free comments weren't recorded.
- **Header inconsistencies** across files (`Spessore della Crosta` vs
  `Spessore della crosta`, etc.) are normalized in code; `\xa0` non-breaking
  spaces in 2021 comments are converted to regular spaces.

## 3. Goal — image → caption

The user has stated the objective is to train a model that, given an image,
produces a caption. Multiple captions per image are desirable (more data),
each attribute is treated as a separate caption, and other metadata can be
backtracked from the unified CSV when needed. Only the captions need
normalization; images and metadata stay as they are.

## 4. Caption preparation — `prepare_captions.py` → `data/captions_prepared.csv`

Deterministic prep step run before any LLM rewrite. Does not rephrase; only
filters and normalizes.

### 4.1 What it does

1. **Filter** rows where `comment` is empty / `N/A` / pure whitespace.
2. **Normalize text**: Unicode NFC; replace `\xa0` and zero-width characters
   with spaces; collapse runs of whitespace; strip; remove stray surrounding
   quotes/ticks.
3. **Drop meta-comments** — small regex blacklist: `non penalizz…`,
   `non valuto`, pure punctuation lines.
4. **Drop near-empty noise** — fewer than 2 word characters after stripping.
5. **Keep both** the original `caption_raw` and the normalized
   `caption_norm` so anything is reversible.

### 4.2 Output stats

- 51,988 input rows → **39,356 output rows** (75.7% kept).
- Drops: 12,478 empty, 86 meta-notes, 68 too-short.
- Per-attribute counts:

  | attribute | rows |
  |---|---:|
  | Struttura della Pasta | 7,546 |
  | Sapore | 6,350 |
  | Colore della Pasta | 5,947 |
  | Profumo | 5,798 |
  | Texture | 5,431 |
  | Aroma | 4,213 |
  | Spessore della Crosta | 4,071 |

### 4.3 Caption shape

- Captions are **very short fragments**. Median 3-6 tokens, often single
  words: `"Crauti"`, `"Forte"`, `"Brutta"`, `"Yogurt"`, `"Tenero"`.
  About 25% are ≤2 tokens; max ~200 chars.
- Casing is inconsistent (`"Leggermente Acido amaro"`).
- Each attribute already has a recognizable lexicon — there is a stable
  sensory vocabulary to anchor consistency to:
  - **Aroma**: cotto, burro, formaggio, crosta, latte, panna, brodo, grana,
    note, lattico, fuso, tostato, vegetale, animale, fermentato, frutta…
  - **Colore della Pasta**: carico, alone, chiaro, omogeneo, giallo,
    paglierino, rosa, scuro, uniforme, macchia, fascia…
  - **Profumo**: burro, cotto, latte, …
  - **Sapore / Texture / Struttura della Pasta / Spessore della Crosta**:
    similar attribute-specific lexicons (full lists in
    `data/captions_prep_report.txt`).

### 4.4 Output columns

```
row_id, image_path_flat, image_path, attribute,
caption_raw, caption_norm,
panelist, session_date, year_folder, session_num, bimester,
view, panel_slot, panel_replicate, dairy_id, product_code
```

## 5. Proposed rewrite plan (pending user confirmation)

Goal: convert the 39,356 short, fragmentary panelist notes into uniformly
phrased Italian captions while preserving exactly the sensory information
present, so a captioning model trains on consistent text.

### 5.1 Strategy

LLM rewrite, **one call per non-empty comment**, attribute-conditioned and
faithfulness-constrained. Per-comment (not per-image-aggregated) keeps audit
trivial — one input row, one output row, easy to diff.

### 5.2 Consistency levers

1. **Per-attribute style templates.** Each attribute gets a fixed framing so
   captions across the dataset converge on a uniform shape:
   - Profumo → `Al profumo, …` / `Profumo di …`
   - Aroma → `Aroma …`
   - Sapore → `Al sapore, …`
   - Texture → `In bocca, …` / `Texture …`
   - Colore della Pasta → `La pasta presenta …`
   - Struttura della Pasta → `La pasta mostra …`
   - Spessore della Crosta → `La crosta presenta …`
2. **Controlled vocabulary.** Top-N tokens per attribute extracted from the
   data and pinned in the prompt: *"prefer these terms when applicable, do
   not introduce synonyms not in this list."* Stops drift like
   *cotto* ↔ *cucinato*.
3. **Length target.** One short sentence, roughly 6-15 words. Pad
   too-short fragments minimally (`"Yogurt"` → `"Aroma di yogurt."`);
   compress overly long rambles.
4. **Faithfulness rule.** No new sensory descriptors, no severity grading,
   no positive/negative judgments unless present in source. Source
   ambiguity → preserve the ambiguity.

### 5.3 User decisions captured

- **Language**: Italian only.
- **Templates**: prefix templates are accepted.
- **Phrasing tone**: should still feel natural, not robotic.

### 5.4 Execution plan

1. Draft the prompt with per-attribute template + few-shot fragment →
   caption examples for each of the 7 attributes.
2. **100-row pilot** through Haiku 4.5 stratified across attributes,
   inspect for hallucination and consistency, iterate prompt.
3. Once approved, submit the full ~39k rows as a single Anthropic
   **Batch API** job (50% cost discount, async).
4. Write `data/captions.csv` with at least:
   `image_path_flat, attribute, caption_raw, caption_norm, caption_clean,
    panelist, session_date, …`

### 5.5 Validation harness

- Spot-check N random rows per attribute for hallucinated content (terms in
  the rewrite not derivable from the source).
- Lightweight automatic check: for each row, every "content lemma" in
  `caption_clean` should be either in `caption_norm` or in the controlled
  vocabulary for that attribute.
- Length sanity: flag rewrites with token count > 20 or < 3.

## 6. What this report does NOT yet cover

- The official project scope (PDF in repo root) — not yet read at the time
  of writing this section. Sections above may need to be reconciled with
  the official deliverables, evaluation criteria, and constraints once
  that PDF is reviewed.

## 7. Repo state

- Pushed to `panciut/Cheese` (private GitHub repo).
- Tracked: `build_dataset.py`, `prepare_captions.py`, `.gitignore`,
  `data/GT commenti liberi/` (raw workbooks + codebook),
  `data/unified_dataset.csv`, `data/captions_prepared.csv`,
  `data/captions_prep_report.txt`, this report.
- Gitignored: `data/TrentinGrana/`, `data/images_flat/`, `__pycache__/`,
  `.DS_Store`.
