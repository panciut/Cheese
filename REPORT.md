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

## 6. Reconciliation with the official project scope

Source: `AI4FQC-Project Description Template_07_GRANA_Captioning.docx (2).pdf`.

### 6.1 Project framing

- **Project 07 — GRANA_Captioning**, part of the AI4FQC programme.
- **Dataset** as described by the brief: images of grana cheese wheel
  sections, acquired with the **IRIS electronic visual analyzer** under
  controlled lighting and imaging conditions. This matches what we have on
  disk (1024×768 BMPs across 2018-2022). Because acquisition is controlled,
  cross-session lighting normalization is likely a minor concern compared
  with content-level cleaning.
- **Two-step task**:
  1. Clean and pre-process the textual descriptions from tasters.
  2. Apply and compare **three different basic encoder-decoder captioning
     methods**, chosen to be conceptually as different as possible.
- The brief explicitly stresses that Step 1 quality drives Step 2 success.

### 6.2 Step 1 requirements — what the brief asks for

Verbatim cleaning examples from the brief:

- **Substitute quantitative descriptions with qualitative ones.**
  Example in our data: `"Spigoli sopra 20mm Piatto 10mm circa Media 12mm"`
  → a qualitative paraphrase such as
  `"Crosta di spessore irregolare, mediamente sottile."`. Numbers, ranges,
  and units (`mm`, `cm`, `%`) should disappear in favour of qualitative
  Italian descriptors.
- **Rephrase dialect sentences.** Some panelist notes use regional or
  colloquial Italian. These need to be brought to a neutral standard
  Italian register.
- **Enrich telegraphic comments** into elegant, full sentences. This is
  exactly the single-token-fragment problem ("Crauti", "Forte", "Yogurt")
  observed in §4.3.
- **Reduce synonyms** to a controlled vocabulary, so different panelists'
  near-synonymous wording converges on the same surface form.

### 6.3 Step 2 requirements — captioning methods

- Three encoder-decoder captioning methods, conceptually different.
  Out of scope for the current preparation phase, but the captions we
  produce must be suitable training data for all three. Practical
  implications for Step 1:
  - **Stable vocabulary** is doubly important — three different decoders
    will all benefit from a small, controlled output lexicon.
  - **Per-attribute style consistency** keeps the comparison between the
    three methods honest (style variance does not bleed into the
    architecture comparison).
  - **Multiple captions per image are explicitly allowed** by our task
    framing and useful for training; this is consistent with the brief.

### 6.4 Image-side caveat from the brief

> *"In some images, colored spots may be found. They were used to refer
> left/right sides of the form. They may thus need to be removed in order
> not to influence the encoder block."*

These are reference colour stickers/markers placed on the wheel section to
distinguish left from right. They are an **image-side preprocessing concern
for Step 2**, not a captioning concern, but we should plan for it:

- Locate examples in the dataset and confirm what the markers look like.
- Add an image-cleaning pass before encoder training (mask or inpaint).
- Not blocking for the current caption preparation work, but listed here so
  it is not forgotten.

### 6.5 Adjustments to the Step 1 plan from §5

The strategy in §5 stands, with these explicit additions driven by the
brief:

1. **Quantitative → qualitative conversion is a hard requirement, not a
   stylistic choice.** The faithfulness rule from §5.2.4 must therefore be
   *amended*: removing measurement values is **expected** (it does not
   count as information loss). The qualitative term used must remain
   faithful to the magnitude implied by the source (e.g. "20mm" in a crust
   context is "spessa", not "sottile").
2. **Dialect/register normalization** added to the prompt: rewrite into
   neutral standard Italian without changing the descriptor content.
3. **Synonym reduction** is upgraded from "consistency lever" to "explicit
   deliverable". The controlled vocabulary in §5.2.2 should be derived
   from the data per attribute, frozen as a list, and the prompt must
   require the rewrite to use *only* terms from the union of (vocabulary,
   exact source words). A vocabulary-conformance check should be part of
   §5.5 validation.
4. **Few-shot examples** in the prompt should be drawn from the *real
   data*, not invented, so the rewrites stay in distribution.
5. **Output deliverable** for Step 1 should include not just the cleaned
   captions but also: the controlled vocabulary per attribute, the prompt
   used, and a quality report (vocabulary conformance rate, length
   distribution, hallucination flags).

### 6.6 Revised execution plan

1. Build the **per-attribute controlled vocabulary** from
   `captions_prepared.csv` (top-N tokens after stopword removal, plus
   manual review to merge obvious synonyms — *cotto/cotta/cotti*,
   *occhio/occhiatura/occhiature*, etc.).
2. Draft the **rewrite prompt** with: per-attribute template, vocabulary
   constraint, quantitative→qualitative rule, dialect→standard rule, length
   target, few-shot examples sampled from the data per attribute.
3. **Pilot 100 rows** stratified across attributes through Haiku 4.5;
   inspect for hallucination, vocabulary conformance, and naturalness;
   iterate prompt.
4. Submit full ~39k rows as a single Anthropic **Batch API** job.
5. Write `data/captions.csv` with `caption_raw`, `caption_norm`,
   `caption_clean`, plus metadata.
6. Generate Step 1 deliverable bundle: vocabulary, prompt, quality report.
7. *(Step 2, later)* Plan colored-spot removal on the image side, then
   train and compare three encoder-decoder captioning methods.

## 7. Repo state

- Pushed to `panciut/Cheese` (private GitHub repo).
- Tracked: `build_dataset.py`, `prepare_captions.py`, `.gitignore`,
  `data/GT commenti liberi/` (raw workbooks + codebook),
  `data/unified_dataset.csv`, `data/captions_prepared.csv`,
  `data/captions_prep_report.txt`, this report.
- Gitignored: `data/TrentinGrana/`, `data/images_flat/`, `__pycache__/`,
  `.DS_Store`.
