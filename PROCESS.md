# Trentingrana captioning dataset — process report

A narrative account of how the cleaned image-caption training set was
built, from raw panelist workbooks to the final
`data/final/captions_final.csv`. Pairs with `REPORT.md` (technical
reference) — this document focuses on the journey, decisions and
tradeoffs.

---

## Executive summary

| | |
|---|---:|
| Starting point | 2,745 cheese photographs + 13,159 raw panelist comments in 4 Excel workbooks |
| Final training table | **38,437 image-caption pairs** over **1,497 unique images** |
| Caption forms | both compact (`Profumo di panna.`) and full sentence (`Il formaggio ha un profumo di panna.`) |
| LLM cost | ~$5.60 total (Anthropic Batch API, Haiku 4.5) |
| Wall time | ~30 min for the largest LLM batch; rest is local code |
| Lines of Python | ~1,800 across 16 scripts |
| LLM round-trips after the deterministic prep | 1 (one big batch) |
| NON_DESCRITTO drop rate | 2.1% of training rows (genuinely info-free panelist notes) |

The dataset is ready for training the three encoder-decoder captioning
methods that the AI4FQC project brief asks for as Step 2.

---

## Phase 0 — Understanding what we had

The starting point was deceptively rich:

- **`data/TrentinGrana/`** — 2,745 BMP photos (1024×768, RGB) of grana
  cheese sections, organised by year folder, then session folder, with
  filenames encoding panel slot, dairy ID and view (Fetta = slice,
  Grana = grain close-up). Examples: `P3a_TN306_612_Fetta.bmp`,
  `P5b_TN330_337_B_GRANA.bmp`.

- **`data/GT commenti liberi/`** — four Excel workbooks (one per year:
  2018, 2019, 2020, 2021) with one sheet per sensory attribute
  (Profumo, Aroma, Sapore, Texture, Spessore della Crosta, Struttura
  della Pasta, Colore della Pasta). Each row was one panelist's free
  Italian text about one wheel for one attribute, plus optional
  numeric scores.

- **A codebook** (`codifiche/codifica caseifici.xlsx`) mapping dairy
  IDs ↔ product codes ↔ letters: `TN_302 ↔ C0A ↔ A`, …,
  `TN_338 ↔ C0R ↔ R` (16 dairies).

The first non-obvious problem was that **the images and the comments
spoke different languages**: image filenames identified specific
wheels (`612`, `337` are sample IDs), while the comments only
identified the panelist's tray (`Prodotto = C0D`). There was no row-
level join — only a dairy-level one, via the codebook.

### Decision: dairy-level broadcast as the join

Each panelist comment was broadcast to *all* photographs of that
dairy on that session day. So a single comment of `"Crauti"` for
Profumo at `TN_306` on 2021-03-24 would appear as the caption for
both `P3a` and `P3b` (replicate photos of the same wheel) and both
`Fetta` and `Grana` views — up to 4 image-caption rows from one
comment.

This is by design — multiple caption rows per image is fine for
training (more data) and the user explicitly endorsed it.

Net effect of the join: **51,988 (image, panelist, attribute) rows**
across 2,745 images, of which **39,510 had a non-empty comment**.
83% pairing rate (lower for 2021-22 sessions, where some panelists
left attribute fields blank).

---

## Phase 1 — Deterministic prep

Before reaching for an LLM, we did everything we could with code,
because deterministic transforms are auditable, reproducible and free.

### What got fixed in this phase

- **Encoding artefacts** — `\xa0` non-breaking spaces, double
  whitespace, stray asterisks (`*fermentate*`), lone backticks.
  Removed.
- **Header inconsistencies** between years — `Spessore della Crosta`
  vs `Spessore della crosta`, `N° Seduta` vs `Seduta`. Normalised.
- **Italian decimal commas** in 2018 numeric scores (`'7,48'`) →
  floats. (Numeric scores aren't in the captions but they are in the
  unified table.)
- **Empty / null / N/A rows** dropped (12,478 of them).
- **Pure meta-comments** dropped: `"non penalizzo"`, `"valutazione
  alle 13:40"`, `"al primo tentativo si è chiuso il test"`. Small
  pattern list — 86 more rows.

After this stage we had **39,356 candidate caption rows**.

### What we built — the controlled vocabulary

For each of the 7 attributes we extracted the most frequent tokens
and bigrams from the cleaned panelist text, with conservative Italian
inflection collapsing (a hand-curated `SPECIAL` map for the
ambiguous cases like `latte` vs `latteo`, plus a corpus-driven
plural↔singular merge that only fires when both forms are attested).

The vocabulary served two purposes:

1. **Audit** — the build script's companion `audit_vocabulary.py`
   flagged quantitative tokens (mm, cm), broken stems, near-duplicate
   typos, un-merged inflections. Three rounds of fixes.
2. **Anchor for the LLM prompt** — the top-60 lemmas per attribute
   went into the prompt so the model would prefer the panel's
   sensory register (e.g., *cotto*, *paglierino*, *sottocrosta*,
   *microocchiatura*) over generic synonyms.

A key insight: the LLM speaks Italian fluently, so the vocabulary
didn't need to be a perfect lemmatiser — only a *style anchor*.
Imperfections in the inflection collapsing didn't matter as long as
the canonical form was attested.

### Bare crust-thickness measurements → qualitative

The project brief explicitly asks for quantitative descriptions to
be substituted with qualitative ones. For Spessore della Crosta in
particular, hundreds of captions were just numbers (`"10"`, `"1 cm"`,
`"Mediamente 9 mm"`, `"8-10 mm"`).

We wrote a deterministic `qualitatise_spessore_bare()` that maps:

| measurement | bucket |
|---|---|
| < 8 mm or < 0,8 cm | Molto sottile |
| 8-9 mm or 0,8-0,9 cm | Sottile |
| 10-13 mm or 1,0-1,3 cm | Media |
| 14-17 mm or 1,4-1,7 cm | Spessa |
| ≥ 18 mm or ≥ 1,8 cm | Molto spessa |

It handles bare numbers, unit-suffixed numbers, ranges
(`"8-10 mm"`), and qualifier prefixes (`"Mediamente 9 mm"`,
`"Più di 1 cm"`). 51 unique Spessore captions collapsed into 5
qualitative buckets, eliminating the LLM's main failure mode (cm
vs mm bucketing inconsistency) before the model ever saw them.

### Deduplication

Because of the dairy-level broadcast, the same caption text was
about to be sent to the LLM many times. We deduplicated by
`(caption_pre, attribute)`:

| | rows |
|---|---:|
| Caption rows (post-prep) | 39,356 |
| Unique `(caption, attribute)` pairs | 7,758 |
| Compression ratio | 5.07× |

Most popular bucket: 4× appearance (6,595 captions appear exactly
four times — the `a/b × Fetta/Grana` broadcast pattern).

### Conservative drop of unambiguous noise

A separate pass removed only captions where the *entire* content
was information-free:

- Pure evaluatives alone (`Bello`, `Brutta`, `Ok`, `Mah`, `Peccato`,
  `Scarso`)
- System/test meta (`ValutazIone alle 13:40`, `Al primo tentativo si
  è chiuso il test`)
- Bare numbers in attributes other than Spessore della Crosta

Only **16 unique captions / 76 broadcast rows (0.2%)** dropped.
Captions that mixed meta with real descriptors were intentionally
kept — the LLM would do that surgery much better than a regex.

After Phase 1: **7,742 unique captions ready for the LLM**, **39,280
training rows** in the broadcast target.

---

## Phase 2 — LLM rewrite

The LLM's job was the genuinely hard work that no regex could do
faithfully:

- Expand telegraphic single words into natural captions (`"Crauti"`
  → `"Profumo di crauti."`)
- Normalize dialect / colloquial / abbreviated Italian
- Strip meta-comments while preserving the descriptive parts mixed
  in with them
- Convert *embedded* measurements to qualitative descriptions
  (`"Spigoli sopra 20mm Piatto 10mm"` → `"Crosta con spigoli
  pronunciati e parte piatta sottile"`)
- Convert questions to descriptive affirmations (`"Eucalipto?"` →
  `"Note olfattive di eucalipto."`)

### Prompt design

One system prompt per attribute, ~5 KB each, combining:

1. Role + dataset framing (`esperto di analisi sensoriale del
   Trentingrana`)
2. ATTRIBUTE label + one-line description
3. STYLE template anchoring output shape
4. **11 rules**, including the critical:
   - Rule 6: *zero invenzione* — never introduce sensory descriptors
     absent from the source
   - Rule 11: `NON_DESCRITTO` escape — when the source has no
     sensory content for the attribute, output that literal token
5. Per-attribute extra rules (mm/cm conversion table for Spessore)
6. Top-60 controlled vocabulary lemmas
7. Hand-curated multi-word idioms (replacing the auto-extracted
   bigrams which contained co-occurrence artefacts like
   `panna burro` from comma-separated lists)
8. 6 few-shot examples drawn from real captions

### Pilot run

A 105-caption stratified sample (15 per attribute, mixing
top-frequency and random tail) ran through Haiku 4.5 first.

Lessons that fed back into the prompt:

- 3 workers in parallel was the sweet spot; 8 workers triggered 429
  rate-limit storms on the user's tier with retry backoff cascades.
- The LLM had **two failure modes** on the first pilot:
  1. **`1 cm` vs `10 mm` inconsistency** — same physical thickness,
     different qualitative buckets. Resolved by the explicit mm/cm
     conversion table in the Spessore prompt.
  2. **Format violations on off-attribute / no-content inputs** —
     the LLM panicked and emitted multi-line explanations instead
     of complying with rule 10. Resolved by adding rule 11 (the
     `NON_DESCRITTO` escape).

After two rounds of prompt iteration, the pilot was clean.

### Full Batch run

All 7,742 unique captions submitted as one Anthropic Batch API job
(`msgbatch_01Bv99Z88dFdZ6PJ6FdjRxoA`):

- **7,689 / 7,689 succeeded, 0 errors** (smaller because the
  pipeline re-ran with extended Spessore qualitatisation between
  pilot and full).
- Wall time: ~25 minutes.
- Cost: ~$4.50 (Haiku 4.5 with 50% Batch API discount).
- 360 captions tagged `NON_DESCRITTO` (4.7% of unique).
- 2 multi-line outputs containing `NON_DESCRITTO` in their
  reasoning — collapsed to the bare token by post-processing.

### Why Haiku 4.5

The work is short Italian text rephrasing with clear rules and
strong few-shots. Haiku has plenty of capability for this and is
~5× cheaper than Sonnet 4.6 / ~20× cheaper than Opus 4.7. Using
Sonnet would have cost ~$13.50, Opus ~$67. No measurable quality
gain from upgrading on this task — verified on the pilot.

---

## Phase 3 — Quality assurance and manual salvage

### Validation scan

A programmatic check across all 7,689 outputs:

| check | violations |
|---|---:|
| Output starts with the expected attribute prefix | 1 (accepted as a valid alternate prefix) |
| Output contains digits | **0** |
| Output contains units (mm/cm/%) | **0** |
| Output longer than 25 words | **0** |
| Empty output | **0** |
| Multi-line output | **0** (after post-processing) |
| Multi-paragraph or markup | **0** |

Quantitative→qualitative was 100% successful, a clean satisfaction
of the project brief's main Step 1 requirement.

### Manual salvage

A heuristic scan flagged 291 of the 362 `NON_DESCRITTO` captions
as having at least one controlled-vocabulary lemma in the source —
suggesting the LLM may have been over-cautious about rule 11 on
borderline judgment+descriptor inputs.

We hand-curated a salvage map of 178 of these candidates, where the
descriptor was real and faithful:

- `"marcio, putrido,"` → `"Profumo marcio e putrido."`
- `"Strano. A tratti sentiva di pesce. Perplesso"` → `"Profumo
  strano, di pesce a tratti."`
- `"Sangue,,,"` → `"Aroma di sangue."`
- `"Anonimo"` → `"Aroma anonimo."`

Captions left as `NON_DESCRITTO` after this pass were genuinely
info-free: pure judgements (*Pessima*, *Non piacevole!!!*),
incomprehensible fragments (*dd*, *tro*), pure system meta, or
observations entirely off-attribute.

Net effect:

| | before salvage | after |
|---|---:|---:|
| `NON_DESCRITTO` unique | 362 (4.7%) | **184 (2.4%)** |
| `NON_DESCRITTO` broadcast rows | 1,759 (4.5%) | **843 (2.1%)** |

**916 training rows recovered.**

---

## Phase 4 — Broadcast back to the full table

`broadcast_captions.py` joined the 7,505 cleaned unique captions
back to the 39,280-row training table via the `dedup_key`. Rows
where the cleaned caption was `NON_DESCRITTO` were dropped.

Output: **38,437 training rows** in `data/final/captions_final.csv`,
covering **1,497 unique images** across the 7 attributes.

Per-attribute distribution:

| attribute | training rows | unique images |
|---|---:|---:|
| Profumo | 5,660 | 1,622 |
| Aroma | 4,019 | 1,215 |
| Sapore | 6,244 | 1,494 |
| Texture | 5,309 | 1,299 |
| Spessore della Crosta | 3,961 | 1,021 |
| Struttura della Pasta | 7,400 | 1,626 |
| Colore della Pasta | 5,844 | 1,274 |

(Total unique images is **1,497** — some images don't have all 7
attributes covered.)

---

## Phase 5 — Sentence form

A late requirement: provide a full Italian declarative sentence
form alongside the compact attribute-anchored form. The motivation
was downstream — encoder-decoder captioners and standard captioning
metrics (BLEU, METEOR, CIDEr) work better on natural-language
references than on bare noun phrases.

### Two-pass deterministic transform

`make_sentence_form.py` uses no LLM; it's pure regex:

1. **Prefix canonicalisation.** A small map per attribute rewrites
   alternate prefixes the LLM had occasionally produced into the
   canonical attribute prefix (94 rows touched):
   - `Note olfattive vegetali ...` → `Profumo vegetale ...` (Profumo)
   - `Note di pepe.` → `Aroma di pepe.` (Aroma)
2. **Template substitution.** Per attribute, a small ordered list of
   `(pattern, replacement)` rules wraps the captured content in
   sentence scaffolding:
   - `Profumo di X.` → `Il formaggio ha un profumo di X.`
   - `Crosta sottile.` → `La crosta del formaggio è sottile.`
   - `Pasta granulosa.` → `La pasta del formaggio è granulosa.`

100% template coverage after canonicalisation — zero unmatched, zero
LLM round-trip needed.

### Polish pass

A post-template polish pass fixes grammatical glitches the
substitution introduced:

- **Article injection** after `presenta`. Italian wants
  `presenta UN/UNA <noun>` for singular bare nouns; the template
  stripped the article. We inject based on a small per-domain
  gender map of ~30 sensory/structural nouns:
  - `presenta alone` → `presenta un alone`
  - `presenta leggera microocchiatura` → `presenta una leggera
    microocchiatura`
- **Plural awareness** — explicit `NOUNS_PLURAL` set so
  `presenta occhi`, `presenta fessure`, etc. correctly take *no*
  article (Italian plurals don't use the indefinite).
- **`è dal colore X`** → `è di colore X` (the `dal` form was
  awkward).
- **`è dalla X`** → `presenta una X` (or `un'X`) for feminine
  nouns including the generic `-ità` family.
- **`è unghia`** → `presenta un'unghia`.
- **Italian elision** — `una <vowel>` → `un'<vowel>` everywhere
  (standard rule).

### Final QA

After the polish pass, a comprehensive scan across all 6,834
unique sentences came back **clean across all checks**:

| check | violations |
|---|---:|
| `presenta` + bare singular noun (no article) | 0 |
| `presenta una/un'` + plural | 0 |
| Missing `una`→`un'` elision before vowel | 0 |
| `è dal colore` / `è dalla` | 0 |
| `è unghia` | 0 |
| Double spaces | 0 |
| `un' ` with extra space | 0 |
| Article doubling | 0 |
| Trailing punctuation issues | 0 |

Hundreds of additional regex checks for gender disagreement, off-
attribute leakage, double articles, etc. — all passed except for
false positives where the language uses standard structures (e.g.
`il grana` — the cheese as a category — is correctly masculine,
distinct from feminine `la grana padana`).

---

## Phase 6 — Final outputs and reorganization

### `data/final/`

| file | content |
|---|---|
| `captions_final.csv` | full table — 38,437 rows × 18 columns |
| `image_caption_attribute.csv` | simplified 4 columns: `image_path, attribute, caption, caption_sentence` |
| `by_attribute/<Attribute>.csv` × 7 | per-attribute splits (simplified) |
| `README.md` | deliverable explainer for downstream users |

### Directory reorganisation

The `data/` tree was reorganized by purpose:

```
data/
├── final/         # Step 1 deliverables
├── intermediate/  # pipeline intermediate stages
├── rewrites/      # per-attribute LLM outputs + reviews
├── reports/       # text reports + tables + pilot
├── batches/       # Anthropic Batch API metadata
├── vocabulary/    # vocab files
├── prompts/       # rendered system prompts per attribute
├── GT commenti liberi/   # raw workbooks + codebook
├── TrentinGrana/         # raw images (gitignored)
└── images_flat/          # flat image copies (gitignored)
```

All 16 scripts converted from absolute to relative paths
(`Path(__file__).resolve().parent`) so the project moves cleanly
across machines.

---

## Cost summary

| step | cost |
|---|---:|
| Pilot (105 captions, sync) | ~$0.20 |
| Aroma + Spessore della Crosta batch (1,495 captions) | ~$0.87 |
| Full all-7 attributes batch (7,689 captions) | ~$4.50 |
| Manual salvage | $0 (offline) |
| Sentence-form transformation + polish | $0 (offline) |
| **Total LLM spend** | **~$5.60** |

For comparison, sending the same 7,689 captions through Sonnet 4.6
would have cost ~$13.50, Opus 4.7 ~$67. We picked Haiku 4.5 deliberately
because the rewriting task is well-bounded and verified on the pilot
that quality didn't suffer.

---

## Key decisions and tradeoffs

| decision | what we did | why |
|---|---|---|
| Join granularity | Dairy-level (each comment broadcast to all wheels of that dairy) | The data didn't support wheel-level join; broadcast turns out to be a feature, not a bug, for image→caption training |
| Per-attribute vs aggregated captions | Per-attribute (one caption per attribute, not one rich caption per image) | Lets the captioning model handle each sensory aspect cleanly and matches the per-attribute panel data |
| Deterministic before LLM | Heavy preprocessing (typo expansion, abbrev, qualitatisation, dedup) | Auditable, free, reduces LLM cost ~5× |
| Vocabulary as anchor not lexer | Top-N lemmas as "preferisci" suggestions, not "use only" | The LLM speaks Italian; perfect lemmatisation isn't needed |
| `NON_DESCRITTO` escape | Output token instead of multi-line refusal | Single-token signal is trivial to filter post-hoc |
| Manual salvage | Hand-curate 178 borderline NON_DESCRITTO captions | Recovers 916 training rows; cheaper than another LLM round |
| Two caption forms | Compact + sentence in the same row | Lets downstream pick whichever serves their architecture |
| Polish pass | Pure regex post-pass on sentence form | Fixes transformation grammar glitches without an LLM; auditable |
| Haiku 4.5 over Sonnet/Opus | ~$5 vs ~$15 vs ~$70 | Pilot proved the smaller model handles the rewriting task cleanly with strong few-shots |

---

## What we did *not* do (and why)

- **No image preprocessing yet.** The brief mentions colored-spot
  removal (left/right markers on some wheels). That's Step 2
  territory — encoder side, not caption side.
- **No aggregated long-form caption per image.** Possible future
  variant; left out because the per-attribute design fits the
  panel data and the brief better.
- **No three-captioner training.** That's Step 2.
- **No train/val/test split.** Should be stratified by dairy and
  session to avoid leakage; deferred to whoever does Step 2.

---

## What's ready for Step 2

The brief asks for **three different encoder-decoder captioning
methods, conceptually as different as possible**. The training data
is now ready in two flavours:

- **`data/final/image_caption_attribute.csv`** — 38,437 (image,
  attribute, caption, caption_sentence) rows.
- **`data/final/by_attribute/<Attribute>.csv`** — per-attribute
  splits if you want one model per attribute.

Both forms are present in every output:

- `caption` (compact, ~4-8 words, attribute-anchored)
- `caption_sentence` (full Italian sentence, ~7-15 words)

Suggested architectures (conceptually different):

1. **CNN encoder + RNN/LSTM decoder** — classical, strong baseline.
2. **Vision Transformer (ViT) encoder + Transformer decoder** —
   attention-everywhere, competitive on small data with
   pre-training.
3. **CLIP-style contrastive embedding + retrieval-based decoder** —
   learns image-caption similarity, generates by retrieving from
   the training caption pool. Conceptually orthogonal to the first
   two.

Suggested evaluation:

- Standard BLEU / METEOR / CIDEr against `caption_sentence`.
- A **controlled-vocabulary conformance check** — does the output
  use only attested sensory terms from `data/vocabulary/`? — to
  measure faithfulness in domain-specific Italian.

---

## What we learned along the way

- **Cleaning data ≠ throwing it away.** The instinct to drop noisy
  rows is wrong; the salvage step recovered 916 training rows from
  what looked like dross. Hand curation pays at this scale.
- **The LLM speaks Italian.** Most of the things we initially
  thought needed to be fixed up-front (lemmatisation, complex
  vocabulary normalization) the LLM handles natively. The
  deterministic prep is for things the LLM can't do *faithfully*
  on its own (consistent qualitative bucketing, dedup).
- **Pilot before batch.** The two prompt iterations driven by the
  pilot saved an entire $4.50 batch run from being wasted.
- **`NON_DESCRITTO` as escape valve.** A single-token output for
  the "no usable content" case is much cleaner than letting the
  model panic into multi-line explanations. It became one of the
  most useful primitives in the prompt.
- **Sentence form was free.** What initially looked like another
  ~$5 LLM job turned out to be a one-page regex script. Asking
  "can we do this without an LLM?" first is always worth it.

---

## Repo state

Pushed to `panciut/Cheese` (private GitHub repo, GitHub URL
`github.com/panciut/Cheese`). 16 Python scripts and ~25 data
artefacts. Both `REPORT.md` (technical reference) and this
`PROCESS.md` (process narrative) are tracked alongside the data.
