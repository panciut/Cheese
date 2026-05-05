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

## 7. Pre-LLM cleanup pipeline

This section documents the *deterministic* cleanup step that runs between
the prep stage (§4) and the LLM rewrite step (§5). Goal: feed the LLM
clean, deduplicated, attribute-labeled inputs while keeping every
transformation auditable and reversible. The LLM is *not* used in this
phase — it is reserved for the genuinely hard work (rephrasing, dialect
correction, fragment expansion) where regex-style rules cannot give a
faithful answer.

### 7.1 Controlled vocabulary

`build_vocabulary.py` reads `captions_prepared.csv` and emits, per
sensory attribute:

- `data/vocabulary/{attribute}.txt` — top lemmas with their attested
  surface forms and frequencies.
- `data/vocabulary/bigrams_{attribute}.txt` — top multi-word sensory
  expressions (`latte cotto`, `panna cotta`, `frattura regolare`,
  `micro occhiatura`, `bella grana`, …).
- `data/vocabulary/vocabulary.csv` — combined flat list.
- `data/vocabulary/_summary.txt` — overview: tokens per attribute, top-8
  lemmas snapshot.

Italian inflectional collapsing is corpus-driven: a SPECIAL hand-curated
dictionary handles the most ambiguous adjective/noun families
(`cotto/cotta/cotti/cotte` → `cotto`), and a generic merge step joins
plural↔singular pairs when both forms are attested in the data. This
avoids over-collapsing distinct words (`latte` ≠ `lattei`, `carico` ≠
`scarico`).

Tokenization also expands a small map of source-data abbreviations and
typos (`legg./leg.` → `leggermente`, `po'/po` → `poco`,
`microcchiatura` → `microocchiatura`, `granoloso` → `granuloso`,
`equilibrato` typos, `intensita` → `intensità`, …). Pure-numeric and
unit-only tokens (`mm`, `cm`, `km`) are dropped from the vocabulary —
they carry no qualitative signal.

### 7.2 Audit pass

`audit_vocabulary.py` reads the generated vocabulary and flags:

- Quantitative / unit tokens that slipped through.
- Very short tokens that look like abbreviations.
- Probable un-merged inflection pairs in the same attribute.
- Near-duplicate lemmas at edit distance 1.
- Lemmas appearing in many attributes (informational).
- A side-by-side top-30 lemmas table per attribute (style snapshot).

Output: `data/vocabulary/_audit.txt`. The audit drove three rounds of
fixes (broken `-mente` adverb stripping, missing accent restoration,
participle-pattern merging, `-io` masculine nouns, apocopated forms,
preposition+article stopwords). After convergence the audit's
"un-merged inflections" section contains a single false positive
(`latte/lattee` — milk vs the adjective *latteo*, correctly *not*
merged); near-duplicates are all genuine antonym/distinct-word pairs
(`carico/scarico`, `equilibrato/squilibrato`, `gradevole/sgradevole`,
`bella/bolla`, …).

The vocabulary is intended as a *style anchor* for the LLM rewrite
prompt, not a perfect lemmatization — the LLM speaks Italian and
handles morphology naturally. What it needs from the vocabulary is:

1. The grana-specific sensory lexicon (`microocchiatura, paglierino,
   sottocrosta, scalzo, unghia, tirosina, mou, uht, sapidità,
   piccantezza, friabilità, solubilità, cedevole, sabbioso`).
2. The idiomatic multi-word expressions (bigrams).
3. A forbidden-pattern list (units, abbreviations, meta-comments) that
   the prompt will pin separately.

### 7.3 Caption-level deterministic cleanup

`clean_captions.py` reads `captions_prepared.csv` and applies the same
abbreviation/typo expansion used by the vocabulary builder, plus stray
markup removal (`*fermentate*` → `fermentate`, multiple spaces, leading
backticks). Output: `caption_pre` column added alongside `caption_raw`
and `caption_norm` so the source text remains accessible at every
stage.

About 9% of rows are touched by the cleanup (typo/abbreviation
expansion or markup strip).

### 7.4 Bare-number qualitatisation for `Spessore della Crosta`

The brief explicitly requires substituting quantitative descriptions
with qualitative ones. For `Spessore della Crosta`, many captions are
bare numbers without units (`"10"`, `"11 12"`, `"0,8"`, `"1,1"`).
Without context the LLM cannot reliably qualitatise these, so the
cleanup step does it deterministically:

1. Tokens are parsed as numbers; values < 5 are interpreted as cm,
   the rest as mm.
2. The mean mm value is bucketed:
   - < 8 mm → `Molto sottile`
   - 8 – < 10 mm → `Sottile`
   - 10 – < 14 mm → `Media`
   - 14 – < 18 mm → `Spessa`
   - ≥ 18 mm → `Molto spessa`
3. The bare-number caption is replaced with the bucket label.

This applies *only* when the caption is purely numeric. Mixed captions
like `"Spigoli sopra 20mm Piatto 10mm circa Media 12mm"` are left for
the LLM, which can rephrase them in context.

Result: 424 rows that would otherwise be dropped as ambiguous noise
become valid qualitative training data.

| qualitative bucket | broadcast rows |
|---|---:|
| Molto sottile | 30 |
| Sottile | 160 |
| Media | 194 |
| Spessa | 36 |
| Molto spessa | 4 |

### 7.5 Deduplication for the LLM

`clean_captions.py` also computes a `dedup_key = attribute :: text`
(lower-cased, punctuation-folded) and groups rows by key. The dairy-
level join broadcasts the same panelist comment across `a/b` photo
replicates and `Fetta`/`Grana` views, so the same caption text appears
multiple times across rows. Deduplicating before the LLM step is a
cost optimization only — the cleaned caption is broadcast back to
*every* matching row afterwards, so each `(image, attribute)` training
pair retains its original distinct image.

Compression results:

- Input: **39,356** caption rows.
- Unique `(caption_pre, attribute)` pairs: **7,758**.
- Compression: **5.07×** (80.3% saving on LLM rewrite cost).
- Most popular bucket: 4× appearance (6,595 unique captions appear
  exactly four times — the `a/b × Fetta/Grana` broadcast pattern of
  many sessions).

| attribute | total | unique | saving |
|---|---:|---:|---:|
| Aroma | 4,213 | 808 | 80.8% |
| Colore della Pasta | 5,947 | 1,184 | 80.1% |
| Profumo | 5,798 | 1,179 | 79.7% |
| Sapore | 6,350 | 1,127 | 82.3% |
| Spessore della Crosta | 4,071 | 692 | 83.0% |
| Struttura della Pasta | 7,546 | 1,676 | 77.8% |
| Texture | 5,431 | 1,092 | 79.9% |

Outputs: `data/captions_pre.csv` (full), `data/captions_unique.csv`
(one row per dedup key, with `frequency` and `sample_row_id`).

### 7.6 Dropping unambiguous noise

`drop_useless_captions.py` removes only the captions where the *entire*
content is information-free. Three categories, all automatically
detected:

- **PURE_EVAL** — the caption is a single evaluative token without any
  sensory descriptor (`Buono`, `Brutta`, `Ok`, `Ottimo`, `Mah`,
  `Peccato`, `Scarso`, `Bella` alone, `DISCRETA`, …).
- **NUMBER_ONLY** — the caption is only digits/decimals. After §7.4
  this category is empty for `Spessore della Crosta`; in any other
  attribute a bare number is suspect noise.
- **SYSTEM_META** — meta-comments about the panelist's process or the
  test system (`"ValutazIone alle 13:40"`,
  `"Al primo tentativo si è chiuso il test ..."`,
  `"non lo so, ho dovuto sputarlo"`).

Captions that mix meta with real sensory descriptors are *not* dropped
— the LLM rewrite is much better at strip-meta-keep-descriptor surgery
than a regex (`"amaro deciso e penalizzante"` → `"Sapore amaro e
deciso"`, keeping the descriptor and dropping the scoring meta).

Hedged descriptors (`"Forse pochi cristalli"`), negations
(`"Non paglierino"`, `"Non granulosa"`), and interrogative descriptors
(`"Eucalipto?"`, `"Lievito pane?"`) are also kept — they carry real
information that the LLM can frame correctly.

Drop totals:

- 16 unique captions dropped (out of 7,758, **0.21%**)
- 76 training rows dropped (out of 39,356, **0.19%**)
- 64 PURE_EVAL rows + 12 SYSTEM_META rows + 0 NUMBER_ONLY rows.

Outputs:
- `data/captions_to_rewrite.csv` — **7,742 unique** captions for the
  LLM. This is the file the rewrite step consumes.
- `data/captions_pre_filtered.csv` — 39,280 broadcast-target rows.
- `data/dropped_captions.csv` — full audit trail of dropped rows with
  reason.
- `data/drop_captions_report.txt` — summary + every dropped unique
  caption.

### 7.7 Pipeline overview

```
unified_dataset.csv (51,988)
        │ prepare_captions.py
        ▼
captions_prepared.csv (39,356)
        │ clean_captions.py
        │   • abbreviation / typo expansion
        │   • stray-markup strip
        │   • Spessore bare-number → qualitative bucket
        │   • dedup by (caption_pre, attribute)
        ▼
captions_pre.csv (39,356) + captions_unique.csv (7,758 unique)
        │ drop_useless_captions.py
        ▼
captions_pre_filtered.csv (39,280) + captions_to_rewrite.csv (7,742 unique)
        │ rewrite_captions.py [NEXT]
        ▼
captions_rewritten.csv (7,742 cleaned)
        │ broadcast back via dedup_key
        ▼
captions_final.csv (39,280 cleaned training pairs)
```

### 7.8 What is intentionally *not* done in this phase

- **Quantitative → qualitative for non-trivial captions.** Mixed
  captions with embedded measurements need contextual rewriting
  (`"Spigoli sopra 20mm"` ≠ `"Piatto 10mm"`), so the LLM does it.
- **Dialect or register normalization.** LLM territory.
- **Synonym reduction across distinct words** (e.g.
  `regolare` ↔ `uniforme`). The vocabulary suggests preferences; the
  LLM applies them in context.
- **Hedge or interrogative removal.** Hedged descriptors carry real
  information; the LLM unpacks them faithfully.
- **Meta+descriptor surgery.** LLM strips the meta clause and keeps
  the descriptor.

### 7.9 What goes into the rewrite prompt

The rewrite prompt (drafted in the next phase) will combine, per
attribute:

1. A **style template** (e.g. `Profumo …`, `Al sapore, …`,
   `La crosta presenta …`) so output style is uniform across all
   captioning-method comparisons in Step 2.
2. The **controlled vocabulary** as a "prefer these terms" list,
   plus key bigrams as multi-word idioms to preserve.
3. The **forbidden-pattern rules**: no measurement values, no
   abbreviations, no meta-comments, faithfulness to source.
4. **Few-shot examples drawn from the real data**: fragment →
   cleaned caption, with deliberate coverage of negations,
   interrogatives, hedges, and mixed meta+descriptor.

The LLM (Haiku 4.5) will be called once per unique caption, then the
output is broadcast back to all matching rows in
`captions_pre_filtered.csv` via the `dedup_key`.

## 8. LLM rewrite phase — `rewrite_prompt.py`, `rewrite_batch.py`

The cleaned 7,742 unique captions from §7 were rewritten by Claude Haiku 4.5
through the Anthropic Batch API, producing per-attribute training tables.

### 8.1 Prompt design — `rewrite_prompt.py`

One system prompt is generated per attribute, combining:

1. **Role + dataset framing** — "esperto di analisi sensoriale del
   Trentingrana".
2. **ATTRIBUTE label** with a one-line description of what the attribute
   covers.
3. **STYLE template** anchoring output shape: `Profumo …`, `Aroma …`,
   `Sapore …`, `Texture …` / `In bocca …`, `Crosta …`, `Pasta …`,
   `Pasta di colore …`.
4. **11 numbered cleaning rules** (see below).
5. **Optional per-attribute extra rules** (e.g. the mm/cm thickness
   table for Spessore della Crosta).
6. **Top-60 controlled vocabulary** lemmas from `data/vocabulary/`,
   presented as "preferisci questi termini quando applicabili".
7. **Hand-curated multi-word idioms** (`CURATED_BIGRAMS` in
   `rewrite_prompt.py`) — replaces the auto-extracted bigram files
   which contained co-occurrence artifacts (e.g. `panna burro` from
   comma-separated panelist lists).
8. **6 few-shot examples per attribute**, drawn from real captions in
   the dataset, deliberately covering: single-word fragments,
   telegraphic notes, negations, interrogatives, mixed
   meta+descriptor, abbreviations, embedded measurements (Spessore
   only).

The 11 rules:

1. Conserve all sensory information **pertinent to the declared
   attribute**; ignore observations about other attributes.
2. Convert quantitative descriptions (mm, cm, %, numeric ranges) to
   qualitative descriptors. The output must contain no digits or
   units.
3. Expand abbreviations: `leg./legg.` → `leggermente`, `po'/po` →
   `poco`, `abb.` → `abbastanza`, `tend.` → `tendente`.
4. Reformulate dialect/colloquial/telegraphic phrasing into neutral
   standard Italian.
5. Reduce synonyms to the controlled vocabulary when the source has
   an equivalent term.
6. **Zero invention.** Never introduce sensory descriptors absent
   from the source — including qualifiers like *tipico*,
   *caratteristico*, *presente*, *evidente*. Reformulate the
   existing; do not invent new content.
7. Strip judgments of pleasantness (*buono*, *brutto*, *ottimo*),
   scoring/voto references, and meta-comments about the panelist or
   the test session. **Keep descriptive negations** (*Non
   paglierino* → *non paglierina*).
8. Transform questions into descriptive affirmations (*Eucalipto?*
   → *Note di eucalipto.*); flatten exclamations.
9. Length: a single Italian sentence, calibrated to the source —
   single-word inputs → 2-4 word captions, richer inputs → up to
   ~18 words.
10. Output is **only the rewritten sentence** — no quotes, no
    prefixes, no explanations.
11. **NON_DESCRITTO escape.** When the source has no sensory
    descriptor at all — pure scoring meta, system glitch report,
    incomplete fragment, or content entirely about another
    attribute — output the literal token `NON_DESCRITTO` (no
    sentence, no explanation). The post-processing step filters
    these out.

For Spessore della Crosta, an `extra_rules` block adds an explicit
mm/cm conversion table aligned with the deterministic preprocessing
buckets (§7.4), so the ~195 measurement+descriptor captions get
consistent qualitative output (`1 cm` = `10 mm` = "mediamente
spessa").

`render_prompts_for_review.py` writes the fully resolved system prompt
for each attribute under `data/prompts/<attribute>.md` so the prompt
can be inspected without making any API calls.

### 8.2 Pilot — `pilot_rewrite.py`

Stratified pilot (15 captions per attribute = 105 total) run through
Haiku 4.5 to validate the prompt before launching the full batch.
Mixes top-frequency captions (high broadcast value) with a random
tail (style-diversity probe). Output: `data/pilot_rewrites.csv` and
`data/pilot_review.txt`.

Key findings from the pilot:

- 0 errors after concurrency was reduced to 3 workers (8 workers
  caused 429 rate-limit storms on the user's tier).
- ~95% of captions cleanly rewritten on first pass.
- One systematic issue: the LLM bucketed `1 cm` as "Crosta spessa"
  inconsistently with `10 mm` → "Crosta sottile". Resolved by
  introducing the mm/cm table in §8.1 + extending the deterministic
  qualitatise function in §7.4 to handle unit-suffixed forms.
- Six format violations in the first Aroma-only run: when the input
  was off-attribute or content-free, the LLM panicked and emitted
  multi-line explanations. Resolved by adding rule 11
  (`NON_DESCRITTO` escape).

### 8.3 Full Batch run — `rewrite_batch.py`

All 7 attributes submitted as a single Anthropic Batch API job
(`msgbatch_01Bv99Z88dFdZ6PJ6FdjRxoA`):

- **7,689 / 7,689 succeeded, 0 errors**.
- Wall time: ~25-30 minutes.
- Cost: ~$4.50 (Haiku 4.5 with 50% Batch discount).
- 360 captions tagged `NON_DESCRITTO` on first pass (4.7% of unique).
- 2 multi-line outputs that *contained* `NON_DESCRITTO` after
  reasoning — collapsed to the bare token in post-processing.

`rewrite_batch.py` saves the request-id → caption mapping locally
under `data/batches/<batch_id>.json` before submission, so the script
can be re-run with `--resume <batch_id>` to fetch results later if
needed.

Per-attribute outputs:

| attribute | unique | NON_DESCRITTO | usable |
|---|---:|---:|---:|
| Profumo | 1,178 | 64 (5.4%) | 1,114 |
| Aroma | 805 | 56 (7.0%) | 749 |
| Sapore | 1,127 | 58 (5.1%) | 1,069 |
| Texture | 1,088 | 30 (2.8%) | 1,058 |
| Spessore della Crosta | 637 | 66 (10.4%) | 571 |
| Struttura della Pasta | 1,674 | 54 (3.2%) | 1,620 |
| Colore della Pasta | 1,180 | 32 (2.7%) | 1,148 |
| **total** | **7,689** | **360 (4.7%)** | **7,329** |

Outputs: `data/rewrites_<attribute>.csv` (machine-readable) and
`data/review_<attribute>.txt` (human-readable, sorted by descending
broadcast frequency).

### 8.4 Manual salvage — `manual_salvage.py`

A heuristic scan flagged 291 of the 362 `NON_DESCRITTO` captions
(80%) as having at least one controlled-vocabulary lemma in the
source — i.e., the LLM may have over-applied rule 11 on borderline
captions where a real descriptor was buried under judgment or meta.

Hand-curated salvage of 178 of these candidates was committed in
`manual_salvage.py`'s `SALVAGE` dict — an in-place update to the
`rewrites_<attribute>.csv` files. Captions absent from the salvage
map kept the `NON_DESCRITTO` tag.

Examples of salvageable cases:

- `"marcio, putrido,"` → `"Profumo marcio e putrido."`
- `"Strano. A tratti sentiva di pesce. Perplesso"` →
  `"Profumo strano, di pesce a tratti."`
- `"Sangue,,,"` → `"Aroma di sangue."`
- `"Anonimo"` → `"Aroma anonimo."`
- `"Nostrano"` → `"Sapore nostrano."`
- `"12 km più netta su 1 piatto"` → `"Crosta più netta su un piatto."`

Per-attribute salvage counts:

| attribute | salvaged | remaining NON_DESCRITTO |
|---|---:|---:|
| Profumo | 33 | 31 |
| Aroma | 21 | 35 |
| Sapore | 34 | 24 |
| Texture | 7 | 23 |
| Spessore della Crosta | 46 | 22 |
| Struttura della Pasta | 24 | 30 |
| Colore della Pasta | 13 | 19 |
| **total** | **178** | **184** |

Net effect:

- `NON_DESCRITTO` unique captions: **362 → 184** (4.7% → 2.4%).
- `NON_DESCRITTO` broadcast rows: **1,759 → 843** (4.5% → 2.1% of
  the 39,280-row training set).
- 916 training rows recovered.

The remaining 184 `NON_DESCRITTO` captions are genuinely info-free:
pure judgments (*Pessima*, *Non piacevole!!!*), incomprehensible
fragments (*dd*, *tro*), pure system meta (*Valutato durante foto…*,
*Oggi sono raffreddato*), and observations entirely off-attribute.
These are filtered out at the broadcast step.

`data/non_descritto_table.txt` — full inventory of the 184 captions
that survive as `NON_DESCRITTO` after salvage, sorted by attribute
and descending frequency, for downstream review.

### 8.5 Validation scan

Programmatic checks across all 7,689 rewritten captions:

| check | violations |
|---|---:|
| Output starts with the expected attribute prefix | 1 (`Pepe?` → `Note di pepe.`, accepted) |
| Output contains digits | **0** |
| Output contains units (mm/cm/%) | **0** |
| Output longer than 25 words | **0** |
| Empty output | **0** |
| Multi-line output | **0** (after post-processing) |
| Multi-paragraph or markup-bearing output | **0** |

Quality assessment per attribute:

| attribute | top-frequency outputs | observations |
|---|---|---|
| Sapore | `Sapore salato.`, `Sapore equilibrato.`, `Sapore leggermente salato.` | clean |
| Texture | `Texture asciutta.`, `Texture compatta.`, `Texture pastosa.` | gender-agreement correct (*asciutto* → *asciutta* with feminine *Texture*) |
| Profumo / Aroma | `Profumo di panna.`, `Aroma di crauti.` | natural; ~20 mild stilted-bare-participle cases (*Aroma cotto.*) — grammatically valid, slightly less idiomatic than *Aroma di X* |
| Struttura della Pasta | `Pasta stirata.`, `Pasta con microocchiatura diffusa.` | `microocchiatura` canonicalized correctly (typos `microcchiatura`, `microocchitura` already mapped to canonical form via the TYPO_MAP in §7.1) |
| Colore della Pasta | `Pasta con alone centrale.`, `Pasta di colore omogeneo.` | dual templates used contextually: `Pasta di colore X` for color qualifiers, `Pasta con X` for distribution features |
| Spessore della Crosta | `Crosta mediamente spessa.`, `Crosta sottile.` | mm/cm consistency holds: `1 cm = 10 mm = mediamente spessa` |

## 9. Final training table — `data/captions_final.csv`

`broadcast_captions.py` joins `captions_pre_filtered.csv` (39,280
image-attribute-panelist rows) with the per-attribute
`rewrites_<attribute>.csv` files via the `dedup_key` column and drops
rows where the cleaned caption is `NON_DESCRITTO`.

### 9.1 Output stats

- **38,437 training rows** (97.9% retention from
  `captions_pre_filtered.csv`).
- **1,497 unique images** covered (Fetta + Grana views, a/b
  replicates).
- 843 rows dropped as `NON_DESCRITTO` (2.1%).

Per-attribute breakdown:

| attribute | training rows | unique images |
|---|---:|---:|
| Profumo | 5,660 | 1,622 |
| Aroma | 4,019 | 1,215 |
| Sapore | 6,244 | 1,494 |
| Texture | 5,309 | 1,299 |
| Spessore della Crosta | 3,961 | 1,021 |
| Struttura della Pasta | 7,400 | 1,626 |
| Colore della Pasta | 5,844 | 1,274 |
| **total** | **38,437** | — |

### 9.2 Schema

```
row_id, image_path_flat, image_path,
year_folder, session_date, session_num, bimester,
view, panel_slot, panel_replicate, dairy_id, product_code,
panelist, attribute,
caption_raw,    # original panelist text
caption_pre,    # after deterministic preprocessing
caption,        # final cleaned Italian caption (LLM + manual salvage)
```

`caption_raw` and `caption_pre` are kept alongside `caption` for
traceability — any cleaned caption can be diffed against its
original source for audit.

### 9.3 End-to-end pipeline

```
data/unified_dataset.csv (51,988)
  │ prepare_captions.py
  ▼
data/captions_prepared.csv (39,356)
  │ clean_captions.py
  │   • abbreviation/typo expansion
  │   • stray-markup strip
  │   • Spessore bare-number → qualitative bucket
  │   • Spessore unit-suffixed measurement → qualitative bucket
  │   • dedup by (caption_pre, attribute)
  ▼
data/captions_pre.csv (39,356) + data/captions_unique.csv (7,758)
  │ drop_useless_captions.py
  ▼
data/captions_pre_filtered.csv (39,280) +
data/captions_to_rewrite.csv (7,742)
  │ rewrite_batch.py (Anthropic Batch API, Haiku 4.5)
  ▼
data/rewrites_<attribute>.csv × 7
  │ manual_salvage.py (178 hand-curated NON_DESCRITTO recoveries)
  ▼
data/rewrites_<attribute>.csv × 7  (updated in place)
  │ broadcast_captions.py
  ▼
data/captions_final.csv (38,437 training rows)
```

### 9.4 Cost summary

| step | cost |
|---|---:|
| Pilot (105 captions, sync) | ~$0.20 |
| Aroma + Spessore batch (1,495 captions, batch) | ~$0.87 |
| Full all-7 batch (7,689 captions, batch) | ~$4.50 |
| Manual salvage | $0 (offline) |
| **total** | **~$5.60** |

Wall time: ~30 min for the largest batch; the rest fits inside
single-iteration sessions.

## 10. Repo state

- Pushed to `panciut/Cheese` (private GitHub repo).
- Tracked scripts:
  - `build_dataset.py` — unified table builder (§2)
  - `prepare_captions.py` — caption preparation (§4)
  - `build_vocabulary.py`, `audit_vocabulary.py` — vocabulary (§7.1-7.2)
  - `clean_captions.py` — abbrev/typo/Spessore qualitatisation + dedup (§7.3-7.5)
  - `find_useless_captions.py`, `drop_useless_captions.py` — drop step (§7.6)
  - `rewrite_prompt.py`, `render_prompts_for_review.py` — LLM prompt builder (§8.1)
  - `pilot_rewrite.py` — pilot run (§8.2)
  - `rewrite_batch.py` — Batch API runner (§8.3)
  - `rewrite_attribute.py` — sync per-attribute runner (alternative)
  - `manual_salvage.py` — NON_DESCRITTO salvage (§8.4)
  - `broadcast_captions.py` — final training table (§9)
- Tracked data:
  - `data/GT commenti liberi/` (raw workbooks + codebook)
  - `data/unified_dataset.csv` (joined image+caption rows)
  - `data/captions_prepared.csv`, `data/captions_pre.csv`,
    `data/captions_unique.csv`, `data/captions_pre_filtered.csv`,
    `data/captions_to_rewrite.csv` (intermediate cleaning stages)
  - `data/dropped_captions.csv` (audit of dropped captions)
  - `data/vocabulary/` (per-attribute vocabularies + bigrams + audit)
  - `data/prompts/` (rendered system prompts per attribute)
  - `data/batches/` (Batch API request-id mappings)
  - `data/rewrites_<attribute>.csv` × 7 (LLM-rewritten + salvaged captions)
  - `data/review_<attribute>.txt` × 7 (side-by-side raw → clean review)
  - `data/captions_final.csv` (**Step 1 deliverable** — 38,437 training rows)
  - `data/captions_final_report.txt`, `data/non_descritto_table.txt`,
    `data/non_descritto_salvage.txt`, `data/captions_prep_report.txt`,
    `data/clean_captions_report.txt`, `data/drop_captions_report.txt`,
    `data/useless_caption_candidates.txt`
  - This report
- Gitignored: `data/TrentinGrana/`, `data/images_flat/`, `__pycache__/`,
  `.DS_Store`, `.env`.

## 11. Step 2 outlook (not yet started)

The brief asks for **three different encoder-decoder captioning
methods, conceptually as different as possible**. Step 1 of this
report has produced the training data. Step 2 is downstream work,
not yet started. Expected components:

- **Image preprocessing** — colored-spot removal mentioned in §6.4.
  The IRIS analyzer markers used to indicate left/right need to be
  masked or inpainted so they don't drive encoder learning.
- **Train/val/test split** — stratified by dairy and session date so
  no wheel appears in two splits. Current dataset has 1,497 unique
  images, which is small for deep encoders without strong
  augmentation.
- **Encoder-decoder candidates** that satisfy the
  "conceptually-different" requirement, e.g.:
  - CNN encoder + RNN/LSTM decoder (classical)
  - Vision Transformer (ViT) encoder + Transformer decoder
  - CLIP-style contrastive image embedding + retrieval-based or
    autoregressive decoder
- **Evaluation** — BLEU / METEOR / CIDEr against the cleaned
  captions, plus the controlled-vocabulary conformance check
  pioneered in §7.1 (does the output use only attested sensory
  terms?).
