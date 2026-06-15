# Presentation outline — Trentingrana captioning (target: 30 min)

Detailed slide-by-slide plan. Time budget tilted toward dataset & data
preparation (~55%), then models, then results/observations.

**Time allocation:**

| Section | Time | Slides | Cumulative |
|---|---:|---:|---:|
| 1. Intro & problem | 2 min | 2 | 0-2 |
| 2. Dataset & data preparation | 16 min | 11 | 2-18 |
| 3. Model choices & training | 6 min | 4 | 18-24 |
| 4. Results & observations | 5 min | 4 | 24-29 |
| 5. Conclusions & buffer | 1 min | 1 | 29-30 |
| **Total** | **30 min** | **22 slides** | |

The dataset section is heavy on purpose — for a sensory-captioning project
the dataset is where most of the work was, and where the most useful
context for understanding the results lives. The audience will retain
more by understanding the data well than by seeing many model details.

---

## Section 1 — Introduction & problem (slides 1-2, 2 min)

### Slide 1 — Title slide (30 s)
- **Title**: "Trentingrana Cheese Captioning — Comparing Three Encoder-Decoder Methods"
- **Subtitle**: course / your name / date
- **Optional background**: one nice fetta image from `data/images_flat/`
- **Speaker notes**: name the project, the data source (Trentingrana producers + IRIS analyzer), one sentence on what we're trying to do (turn a cheese section image into a panelist-style sensory description)

### Slide 2 — The assignment, in one slide (90 s)
- **Title**: "The task"
- **Quote the brief directly** (helps frame everything that follows):
  > (1) Clean and pre-process the textual descriptions of the tasters.
  > (2) Apply and compare three different basic encoder-decoder
  >     captioning methods. They should be conceptually as much
  >     different as possible.
- **Two-column layout**:
  - Left: "Input" → cheese section image (fetta + grana view)
  - Right: "Output" → panelist-style Italian sentence
  - With an arrow ⇒ in between
- **Speaker notes**:
  - Note that the brief emphasizes data cleaning as a separate, weighted step
  - Note "conceptually different" — we'll come back to this when motivating the model choices
  - This is not a single-best-model project; it's a *comparison* project

---

## Section 2 — Dataset & data preparation (slides 3-13, 16 min)

### Slide 3 — Source of the data (90 s)
- **Title**: "Where the data comes from"
- **Bullets**:
  - Produced by Trentingrana cheese consortium, scored across **4 years** (2018-2019 to 2021-2022)
  - Images: **IRIS electronic visual analyzer**, controlled lighting + camera setup
  - Each cheese wheel sample provides **two views**:
    - **Fetta** (slice): full cross-section through the wheel
    - **Grana** (close-up): grain-level detail of the paste
  - Sensory annotations from a panel of **20 trained tasters**, scored across 7 sensory attributes
- **Visual**: side-by-side fetta + grana of the same sample (pull from `data/images_flat/`)
- **Speaker note**: the IRIS analyzer detail matters because controlled imaging reduces one source of model confusion — lighting is constant, so the model isn't learning illumination differences

### Slide 4 — Scale of the dataset (60 s)
- **Title**: "The numbers"
- **Stats block**:
  - **979** unique cheese samples
  - **20** panelists
  - **4** years of scoring sessions
  - **7** sensory attributes per sample
  - → **18,427** caption rows total (sample × attribute × panelist)
- **Bullet on splits**:
  - 674 / 143 / 147 samples (train / val / test) — sample-disjoint
  - Same cheese never appears in both train and test
- **Speaker note**: emphasize the sample-disjoint property — important because otherwise different panelists describing the same cheese on both sides of the split would leak

### Slide 5 — The 7 sensory attributes (90 s)
- **Title**: "Seven attributes describing one cheese"
- **Table** (one row per attribute, three columns):

| Attribute | What panelists describe | Typical caption start |
|---|---|---|
| **Aroma** | Smell on tasting | "Il formaggio ha un aroma di…" |
| **Profumo** | Smell on opening | "Il formaggio ha un profumo…" |
| **Sapore** | Taste | "Il formaggio ha un sapore…" |
| **Texture** | Mouthfeel | "Il formaggio presenta una texture…" |
| **Spessore della Crosta** | Rind thickness | "La crosta del formaggio è…" |
| **Colore della Pasta** | Interior color | "La pasta del formaggio è di colore…" |
| **Struttura della Pasta** | Interior structure / grain / fracture | "La pasta del formaggio…" |

- **Speaker note**: point out that some attributes describe the *image*
  (color, structure, crust thickness, grain) and some describe things
  the panelist *tasted* (aroma, profumo, sapore) — neither is visible
  in the image! This already sets up the difficulty of the task.

### Slide 6 — What raw panelist captions look like (90 s)
- **Title**: "The raw captions are messy"
- **Show ~4 real raw examples** from `data/intermediate/captions_pre.csv` or `captions_pre_filtered.csv`. Pick examples that illustrate:
  - **Telegraphic** ("aroma fresco fieno tagliato")
  - **Dialectal / informal** ("salatozzo")
  - **Inconsistent punctuation / capitalization**
  - **Synonyms used inconsistently** ("leggero" vs "lieve" vs "fievole" vs "poco intenso" — all mean essentially the same)
- **Bottom line caption**: "Trained models would learn this noise instead of the structure."
- **Speaker note**: this motivates Step 1 of the brief. The brief specifically called out cleaning as a separately-weighted step.

### Slide 7 — Caption cleaning pipeline (Step 1 of brief) (2 min) — IMPORTANT
- **Title**: "Step 1 — caption cleaning pipeline"
- **Diagram (flow chart)** of the preprocessing pipeline:
  ```
  Raw panelist caption
      ↓
  LLM-assisted rewriting (per-attribute prompts in data/rewrites/)
      ↓
  Manual review file per attribute (review_<Attr>.txt)
      ↓
  Synonym normalization, sentence form, dialect → standard Italian
      ↓
  Two output forms:
      • caption          (telegraphic, normalized)
      • caption_sentence (full Italian sentence) ← used for training
  ```
- **Speaker note**:
  - Use one attribute as the example (e.g. Aroma) — say there's a per-attribute rewrites CSV and a manual review TXT for each of the 7
  - Per-attribute is more accurate than one global cleanup pass because each attribute's vocabulary and rephrasing rules differ
  - Don't claim it's perfect — some residual variation remains

### Slide 8 — Before/after example (60 s)
- **Title**: "Before → after"
- **Three side-by-side examples** of (raw, normalized, full-sentence) for the same panelist + cheese. Pick examples that show:
  1. A short telegraphic input → fluent sentence
  2. A dialectal/colloquial input → standard Italian
  3. A long, comma-soup input → cleanly punctuated
- **Bottom line**: "All training and evaluation in this work uses `caption_sentence`."

### Slide 9 — Per-attribute caption statistics (2 min) — IMPORTANT
- **Title**: "Per-attribute caption diversity"
- **Big table**:

| Attribute | Total rows | Unique captions | Modal-caption share | Avg caption length (words) |
|---|---:|---:|---:|---:|
| Struttura della Pasta | 3,413 | 1,559 | 0.9% | 11.8 |
| Sapore | 2,994 | 953 | 4.3% | 9.2 |
| Colore della Pasta | 2,850 | 1,062 | 2.4% | 11.4 |
| Profumo | 2,677 | 1,071 | 1.6% | 10.7 |
| Texture | 2,593 | 983 | 2.5% | 10.6 |
| Aroma | 1,961 | 713 | 3.7% | 9.8 |
| **Spessore della Crosta** | **1,939** | **494** | **18.4%** | 9.4 |

- **Speaker note**:
  - **Spessore della Crosta is an outlier** — one caption ("La crosta del formaggio è mediamente spessa.") covers almost 1/5 of all rows.
  - Struttura della Pasta is the opposite — 1,559 unique captions across 3,413 rows means most are unique.
  - This will explain a lot of the results later — the most-frequent baseline does best where the modal-caption share is highest.

### Slide 10 — The modal caption per attribute (60 s)
- **Title**: "What the most common caption looks like"
- **Table** showing the modal caption per attribute:

| Attribute | Most common caption |
|---|---|
| Aroma | Il formaggio ha un aroma di panna. |
| Profumo | Il formaggio ha un profumo leggero. |
| Sapore | Il formaggio ha un sapore salato. |
| Texture | Il formaggio presenta una texture asciutta. |
| Spessore della Crosta | La crosta del formaggio è mediamente spessa. |
| Colore della Pasta | La pasta del formaggio è di colore omogeneo. |
| Struttura della Pasta | La pasta del formaggio è stirata. |

- **Speaker note**: these modal captions appear in the test set as "the right answer" for a meaningful fraction of cheeses. We'll see later that a model that *just emits the modal caption every time* is hard to beat on Spessore della Crosta — exactly because 18% of test references are word-for-word that sentence.

### Slide 11 — Train/val/test split (60 s)
- **Title**: "Split"
- **Bullets**:
  - Split done at the **sample (cheese) level**, not at the row level
  - Same cheese sample never crosses the train/test boundary
  - Sample counts: 674 / 143 / 147
  - But row counts depend on attribute (because not every cheese was scored on every attribute by every panelist)
- **Table** of test-row counts per attribute (the numbers used in the report):

| Attribute | Test rows | Train rows |
|---|---:|---:|
| Struttura della Pasta | 490 | 2,333 |
| Sapore | 443 | 2,020 |
| Colore della Pasta | 421 | 1,948 |
| Profumo | 405 | 1,810 |
| Texture | 394 | 1,736 |
| Aroma | 307 | 1,312 |
| Spessore della Crosta | 291 | 1,293 |

- **Speaker note**: small variation — Struttura has 1.8× more training data than Spessore. This matters later when we compare results.

### Slide 12 — The image inputs (90 s)
- **Title**: "What the model actually sees"
- **Visual**: 4 fetta+grana pairs side by side from `data/images_flat/`, with labels (e.g., "young cheese", "mature cheese", "with eyes", "stretched paste")
- **Bullets**:
  - All images are RGB, single-cheese-section, controlled lighting
  - Fetta and grana of the same sample are paired and fed as a **two-image input** to every model
  - Image size is uniform (224×224 after preprocessing for ResNet / ViT)
- **Speaker note**: the audience doesn't know what a Trentingrana wheel section looks like, and showing real samples here pays dividends for the rest of the talk

### Slide 13 — Why each attribute has a *different* image-language relationship (90 s) — IMPORTANT for setting up results
- **Title**: "Some attributes are visible. Some aren't."
- **Two-column slide**:
  - **Visible from the image** (in principle):
    - Colore della Pasta — color is literally in pixels
    - Struttura della Pasta — fracture, grain, holes are visible
    - Spessore della Crosta — crust thickness is measurable
    - Texture — partly visible (smooth vs grainy)
  - **Not visible from the image**:
    - Aroma, Profumo — these are smells; the image can't tell you what something smells like
    - Sapore — taste; same problem
- **Bottom line**: "We should expect different model behavior on these two groups."
- **Speaker note**: this is a setup for the shuffle-test results later — the attributes where models *do* use the image are mostly in the visible group; the attribute that's hardest is Aroma, which is also where you'd expect a vision model to fail.

---

## Section 3 — Model choices & training (slides 14-17, 6 min)

### Slide 14 — Three architectures, three axes (2 min)
- **Title**: "Three conceptually different methods"
- **Quote the brief**: "...conceptually as much different as possible."
- **Table**:

| Model | Encoder | Decoder | Decoder pretraining | Axis isolated |
|---|---|---|---|---|
| **m1** | ResNet-50 (CNN, frozen) | LSTM (RNN) | none | classical CNN+RNN |
| **m3** | ViT-B/16 (frozen) | Transformer | none | ViT vs CNN encoder |
| **m6** | ViT-B/16 (frozen) | GePpeTto (Italian GPT-2) | yes — Italian LM | pretrained-LM decoder |

- **Speaker note**: the three pairwise comparisons each isolate one axis:
  - m1 vs m3 → encoder family (CNN vs ViT)
  - m3 vs m6 → decoder pretraining (scratch vs Italian LM)
  - m1 vs m6 → both axes flip

### Slide 15 — Architecture schematics (90 s)
- **Title**: "Architectures at a glance"
- **Three small block diagrams side by side**, one per model. Each:
  - Top: encoder block (ResNet-50 or ViT-B/16)
  - Middle: "frozen" label
  - Bottom: decoder block (LSTM / Transformer / GePpeTto)
  - Sides: fetta + grana inputs going into the encoder
- **Speaker note**: all three encoders are **frozen** (only the decoder + projection trains) — this keeps the comparison fair.

### Slide 16 — Training setup, briefly (90 s)
- **Title**: "How they were trained"
- **Bullets**:
  - All trained on Kaggle (free T4 / P100 GPU)
  - Identical splits, identical preprocessing
  - Hyperparameters chosen per architecture (not tuned), summary table:

| Model | Epochs | Batch | LR | Scheduler |
|---|---:|---:|---:|---|
| m1 | 50 | 32 | 3e-4 | StepLR |
| m3 | 30 | 16 | 1e-4 | cosine |
| m6 | 20 | 8 | 5e-5 | cosine |

  - Early stopping with patience 5-7
  - Decoding: nucleus sampling (top-p=0.9, T=0.7)
- **Speaker note**: m6 has the smallest batch / lowest LR because GePpeTto is ~125M params. We did NOT do hyperparameter sweeps — these are reasonable defaults. The comparison still works because all three got the *same training discipline*.

### Slide 17 — Two settings: global vs per-attribute (60 s)
- **Title**: "Two ways to set up the captioning task"
- **Two-column**:
  - **Global**: one model handles all 7 attributes pooled. Model must also figure out *which attribute* to talk about. 18,427 training rows.
  - **Per-attribute**: one model per attribute. Smaller vocabulary, narrower distribution. ~1,300-2,300 training rows each.
- **Bullets**:
  - Per-attribute is what the supervisor explicitly asked for
  - Global was already done in an earlier wave (Path-A subset)
  - Both are reported below; per-attribute is the focus

---

## Section 4 — Results & observations (slides 18-21, 5 min)

### Slide 18 — Per-attribute results, BLEU-4 (90 s)
- **Title**: "BLEU-4 per attribute"
- **Grouped bar chart**: 7 attribute groups × 4 systems each (m1, m3, m6, most_frequent baseline). Y-axis: BLEU-4 (0-0.5 range). Color-code by system.
- **Annotations** on the chart:
  - Highlight Struttura della Pasta (biggest gap m6 over most_frequent)
  - Highlight Spessore della Crosta (most_frequent slightly wins)
- **Speaker bullet (just one line)**: "**Trained models beat the modal-caption baseline on 4 of 7 attributes** — biggest win on Struttura della Pasta (+0.13 BLEU-4)."
- **Speaker note**: this is the standard "comparison" slide. Don't dwell on individual numbers — give the bar chart and the one-line takeaway.

### Slide 19 — The shuffle test: does the model use the image? (2 min) — CENTERPIECE
- **Title**: "The interesting question: is the model using the image at all?"
- **Top half — explain the test (in plain language)**:
  - For each model + attribute, take the predictions and the references
  - Compute the paired token-overlap (the normal way)
  - Then randomly shuffle the predictions across rows and recompute
  - Repeat 100 times → get a "shuffled" distribution
  - **If the paired score is no better than the shuffled score, the model is producing captions from the marginal — it's not using the image.**
- **Bottom half — the result chart**: grouped bar chart, 7 attribute groups × 3 models (m1, m3, m6), Y-axis = z-score (paired vs shuffled mean). Horizontal red line at z=3 ("strongly image-conditioned").
- **Speaker note**: this is the analysis to spend time on. The audience should walk away remembering this chart.

### Slide 20 — The architectural finding (90 s) — TAKEAWAY
- **Title**: "What the shuffle test tells us"
- **Three bullets**:
  - **m1 (CNN+LSTM) never uses the image** — z ≈ 0 on every single attribute
  - **m3 and m6 (both ViT-based) use the image on most attributes** — strong (z > 5) on Colore, Struttura, Profumo, Spessore; marginal on Sapore and Texture; never on Aroma
  - **The encoder, not the decoder, is the binary gate.** Frozen ResNet-50 features aren't informative enough; frozen ViT features are.
- **Speaker note**: link back to slide 13 — Aroma is "not visible from the image" anyway, so it's the only attribute that's hard for everyone. The pattern is clean and architectural.

### Slide 21 — Sample predictions (60 s)
- **Title**: "What the captions actually look like"
- **2 side-by-side prediction-vs-truth examples** per row (3 rows total = 6 examples). Pick illustrative pairs from the report §8:
  - One exact match (e.g., Spessore "mediamente spessa")
  - One reasonable-but-wrong (e.g., m6 Colore "carico omogeneo" vs "leggermente carico ma uniforme")
  - One mode-collapse case (Aroma "di sapone" repeated)
- **Speaker note**: this gives the audience qualitative texture for the BLEU numbers. The captions look fluent — the structural failure is descriptor-axis mismatch, not language errors.

---

## Section 5 — Conclusions (slide 22, 1 min)

### Slide 22 — Takeaways (60 s)
- **Title**: "What we learned"
- **Three bullets**, big text:
  1. **Encoder choice gates image-conditioned captioning** on this dataset (ResNet-50 doesn't; ViT-B/16 does). This holds across architectural variations of the decoder.
  2. **Trained models beat the most-frequent baseline on 4 of 7 attributes** — biggest gains on attributes with diverse caption distributions (Struttura della Pasta, Profumo).
  3. **BLEU is a poor metric for this dataset** because the captions are template-heavy. The shuffle test is the most informative single result.
- **Footer line**: "Assignment Steps 1 (caption cleaning) and 2 (compare 3 conceptually-different methods) are both fully satisfied."
- **Speaker note**: don't read the bullets verbatim — paraphrase. Pause for questions.

---

## Cheat-sheet: assets to prepare before the presentation

In priority order (the first three are critical, the rest are nice-to-have):

1. **One sample fetta + grana pair** picked from `data/images_flat/` — used on slides 1, 3, 12 (just save 2-3 .bmp files locally and embed)
2. **The BLEU-4 grouped bar chart** (slide 18) — matplotlib, ~30 lines. Data: trained models + most_frequent baseline from the per-attribute results in `TRAINING_REPORT_per_attribute.md` §5
3. **The shuffle-test z-score grouped bar chart** (slide 19) — matplotlib, ~30 lines. Data: z-scores from the report §7.2 table
4. **Three architecture mini-diagrams** (slide 15) — `draw.io` or Keynote/PowerPoint shapes. Each is roughly:
   - encoder block (rectangle, labelled) + frozen-snowflake icon
   - decoder block (rectangle, labelled) + Italian-flag icon for m6
   - small fetta + grana icons feeding in from the left
5. **Caption preprocessing flow chart** (slide 7) — 4-5 boxes connected by arrows, can be done in PowerPoint
6. **4 sample fetta+grana pairs with labels** for slide 12 — pick samples that look visually different (young/aged/eyes/stretched)
7. **3 before/after caption examples** (slide 8) — copy-paste from `data/rewrites/rewrites_<Attribute>.csv` files

The bar charts can be scripted in ~30 lines of matplotlib each — I can generate them now if you want.

---

## Notes on delivery

- **Where to slow down**: slides 7 (preprocessing pipeline), 9 (per-attribute diversity table), 13 (visible-vs-not-visible), 19 (shuffle test). These are the high-information density slides.
- **Where to move fast**: slides 4, 11, 14, 15, 16, 17 — bullets only, ~45-60 seconds each, no need to belabor.
- **The talk's emotional arc**: "here's a real dataset with real noise" (data section) → "here's three principled architectures" (model section) → "here's an unexpected finding about which models actually use the image, not just the language" (results section).
- **Q&A buffer**: target finishing 28-29 min in to leave 1-2 min for questions; questions will likely focus on (a) why ResNet fails / what would fix it (fine-tuning), (b) the colored-spots issue if anyone read the brief, (c) why BLEU is bad / what would be better (CLIPScore).
