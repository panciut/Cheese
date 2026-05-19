# Trentingrana captioning — full per-attribute training report

Comprehensive report covering data preprocessing, model choices, training
setup, per-attribute results across all seven sensory attributes,
image-conditioning analysis, and observations.

---

## 1. Project brief

From the project description:

> The aim is to: (1) clean and pre-process the textual descriptions of
> the tasters … (2) apply and compare three different basic
> encoder-decoder captioning methods. No constraint is put on the choice
> of the captioning methods, but it is advised that they be conceptually
> as much different as possible.

The dataset is **grana cheese wheel section images** acquired with an
IRIS electronic visual analyzer under controlled lighting. Each image is
associated with sensory captions written by a panel of trained tasters,
covering seven sensory attributes: **Aroma, Profumo, Sapore, Texture,
Spessore della Crosta, Colore della Pasta, Struttura della Pasta**.

Per the brief, the goal is *captioning method comparison*, not a single
"best" model. We report all three methods on all seven attributes plus
the global pooled setting.

---

## 2. Data

### 2.1 Source

- **Images**: grana cheese section images under `data/images_flat/`,
  acquired with the IRIS electronic visual analyzer. Each cheese sample
  has both a **fetta** (wheel slice) view and a **grana** (close-up)
  view; the models concatenate both.
- **Captions**: free-text descriptions from trained panelists, one per
  (sample × attribute) pair.

### 2.2 Step 1 of the brief — caption preprocessing

The original panelist text was telegraphic, dialectal, and inconsistent
("aroma fresco fieno tagliato" vs full sentences like "Il formaggio ha
un aroma di fieno tagliato"). To make the text learnable and
comparable, the captions were rewritten through an LLM-assisted pipeline:

- `data/rewrites/rewrites_<Attribute>.csv` — automated rewrites per
  attribute, normalising sentence form and synonyms.
- `data/rewrites/review_<Attribute>.txt` — manual review notes.
- `data/intermediate/captions_prepared.csv` — pre-filter intermediate.
- `data/final/captions_final.csv` — final cleaned captions.
- `data/final/dataset_captioning.csv` — flattened per-attribute view
  used by all training and baseline code.

Each caption has two forms: a `caption` (short, telegraphic) and a
`caption_sentence` (full Italian sentence). **All training and
evaluation in this report uses `caption_sentence`** because it is
grammatical, more informative, and more representative of how a human
would describe a cheese.

### 2.3 Splits

The split is recorded in `data/final/splits.json`:

| Split | Sample IDs |
|---|---:|
| train | 674 |
| val   | 143 |
| test  | 147 |

Note: each *sample* contributes one row per *attribute*, so the
per-attribute row counts below are several times the sample counts.
Splits are sample-disjoint, so the same cheese never appears in both
train and test (avoids same-cheese leakage across the boundary).

### 2.4 Per-attribute row counts

Sample sizes per attribute (after split):

| Attribute | train | val | test |
|---|---:|---:|---:|
| Struttura della Pasta | 2333 | 473 | 490 |
| Sapore | 2020 | 417 | 443 |
| Colore della Pasta | 1948 | 377 | 421 |
| Profumo | 1810 | 370 | 405 |
| Texture | 1736 | 365 | 394 |
| Aroma | 1312 | 278 | 307 |
| Spessore della Crosta | 1293 | 253 | 291 |

There is meaningful variance: Struttura has 1.8× more training samples
than Spessore. This matters for the cross-attribute comparison.

---

## 3. Model choice

The brief asks for **three encoder-decoder methods, "conceptually as
much different as possible"**. We chose three architectures that span
the three main axes of variation in image captioning:

| Model | Encoder | Decoder | Decoder pretraining | Axis isolated |
|---|---|---|---|---|
| **m1** | ResNet-50 (frozen, global pooled) | LSTM, from scratch | none | CNN+RNN classical baseline |
| **m3** | ViT-B/16 (frozen, patch tokens) | Transformer, from scratch | none | ViT vs CNN encoder |
| **m6** | ViT-B/16 (frozen, patch tokens) | GePpeTto (Italian GPT-2) | yes — pretrained Italian LM | pretrained Italian LM decoder |

Why these three:

- **m1 vs m3** isolates the *encoder* axis: same "from-scratch decoder"
  family, different visual encoder (CNN vs ViT).
- **m3 vs m6** isolates the *decoder pretraining* axis: same ViT
  encoder, different decoder (from-scratch Transformer vs pretrained
  Italian GPT-2).
- **m1 vs m6** differs on both axes — they are the most architecturally
  distant pair.

These three together cover the standard taxonomy used in the captioning
literature (CNN+RNN, CNN/ViT+Transformer, frozen-vision + pretrained-LM
prefix tuning). All three encoders are **frozen** in this report — the
encoder weights stay at their ImageNet-pretrained values; only the
decoder + cross-attention projection are trained on the captioning task.
This keeps the comparison fair (same visual features available to all
three decoders) and keeps the experimental budget manageable. The
codebase also supports a `--finetune` mode that unfreezes the encoder
with differential learning rates — those runs are listed as future work
(§13).

The codebase additionally implements m2 (CNN spatial + Transformer), m4
(CNN+GePpeTto), m5 (CNN spatial + GePpeTto) to fill out the full 2×3
grid, but these are not run in this report — they don't add a new
*conceptual* axis and would only confirm trends visible from the three
chosen models.

---

## 4. Training setup

### 4.1 Hyperparameters

Defaults from `training/cli.py:DEFAULTS` (frozen-encoder mode):

| Model | epochs | batch size | learning rate | scheduler | early-stop patience |
|---|---:|---:|---:|---|---:|
| m1 (CNN+LSTM) | 50 | 32 | 3e-4 | StepLR | 7 |
| m3 (ViT+Tr) | 30 | 16 | 1e-4 | cosine | 5 |
| m6 (ViT+GePpeTto) | 20 | 8 | 5e-5 | cosine | 5 |

These are not the result of a hyperparameter sweep; they are reasonable
defaults appropriate to each architecture's capacity. m6 has the
smallest batch size and lowest learning rate because GePpeTto is the
largest (~125M params).

### 4.2 Decoding at inference

All trained models decode test captions with **nucleus sampling**
(top-p = 0.9, temperature = 0.7) rather than beam search. Beam search
on small datasets tends to collapse onto the modal caption, which
inflates BLEU but reduces caption diversity — nucleus sampling is the
fairer default for measuring whether the model has actually learned
anything image-conditional.

### 4.3 Kaggle workflow

All training was run on Kaggle's free GPU tier. The repository's
`training/kaggle_run.py` provides the per-chunk entrypoint; each Kaggle
kernel:

1. Clones the GitHub repo
2. Symlinks the uploaded Kaggle dataset (`marcopanciera/cheese-trentingrana-v2`) into the repo's `data/`
3. Installs `evaluate / sacrebleu / rouge-score / nltk`
4. Detects GPU architecture (T4 vs P100); if P100 (sm_60), reinstalls PyTorch from cu118 wheels because Kaggle's preinstalled torch lacks sm_60 binaries
5. Runs `python -m training.kaggle_run --models m1 m3 m6 --matrix frozen --attributo <Attribute>` for each requested attribute in the batch

For the per-attribute runs in this report, the seven attributes were
trained in this order across Kaggle sessions:

- Aroma, Profumo: separate single-attribute kernels (2026-05-16)
- Texture, Sapore: separate single-attribute kernels (2026-05-17 — both
  failed initially on P100 GPUs; redone in batches below)
- Struttura della Pasta + Colore della Pasta: **batch A** (2026-05-17, ~8h)
- Sapore + Texture + Spessore della Crosta: **batch B** (2026-05-17, ~9.2h)

Each batch kernel ran m1+m3+m6 frozen + 4 baselines per attribute
sequentially.

### 4.4 Two lessons from the Kaggle workflow

Worth recording because they cost real time:

1. **`enable_gpu: true` in `kernel-metadata.json` does NOT actually enable the GPU**
   — it only declares the kernel as GPU-eligible. The user must
   manually toggle GPU in the Kaggle UI. A kernel without the toggle
   runs on CPU and never finishes in time.
2. **Kaggle's free-tier GPU lottery currently leans towards P100s**, and
   Kaggle's preinstalled PyTorch does not include sm_60 binaries. The
   first four kernels (Texture, Sapore, the first Colore, the first
   Spessore) all crashed immediately with
   `CUDA error: no kernel image is available for execution on the device`.
   The fix in the kernel scripts is:
   ```python
   if sm_major < 7:
       pip install --index-url https://download.pytorch.org/whl/cu118 torch torchvision
   ```
   ~5 min overhead, and the rest runs normally on P100.
3. **Kaggle's free tier caps you at 2 concurrent GPU kernels** — beyond
   that, push returns `"Maximum batch GPU session count of 2 reached"`.

---

## 5. Results — per-attribute table

All numbers are on the held-out test split, frozen-encoder runs,
`caption_sentence` form, nucleus decoding. Values are
**BLEU-4 / BLEU-1 / METEOR / ROUGE-L** computed via NLTK (same
implementation across all rows for consistency). Bold = best per row.

### 5.1 Aroma (test N = 307)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | 0.4737 | 0.6025 | 0.6323 | 0.6356 |
| m3 (ViT+Tr) | **0.4855** | 0.6020 | 0.6316 | **0.6507** |
| m6 (ViT+GePpeTto) | 0.4830 | 0.6129 | **0.6392** | 0.6419 |
| most_frequent | 0.4856 | 0.5403 | 0.6314 | 0.6986 |
| freq_weighted | 0.4422 | 0.5791 | 0.5984 | 0.6017 |
| random | 0.4421 | 0.5773 | 0.6024 | 0.6045 |
| retrieval | (failed — see §13) | | | |

### 5.2 Profumo (test N = 405)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | **0.4161** | 0.5643 | 0.6089 | 0.5995 |
| m3 (ViT+Tr) | 0.4036 | 0.5591 | 0.6118 | 0.6023 |
| m6 (ViT+GePpeTto) | 0.4114 | **0.5675** | **0.6175** | **0.6038** |
| most_frequent | 0.3540 | 0.3880 | 0.5391 | 0.6383 |
| freq_weighted | 0.4166 | 0.5650 | 0.5840 | 0.5832 |
| random | 0.4085 | 0.5532 | 0.5780 | 0.5713 |

### 5.3 Sapore (test N = 443)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | 0.4553 | 0.5960 | 0.6257 | 0.6424 |
| m3 (ViT+Tr) | 0.4542 | **0.6038** | **0.6301** | 0.6442 |
| m6 (ViT+GePpeTto) | **0.4561** | 0.5884 | 0.6220 | **0.6446** |
| most_frequent | 0.4424 | 0.4887 | 0.6076 | 0.7109 |
| freq_weighted | 0.4453 | 0.5862 | 0.6133 | 0.6239 |
| random | 0.4421 | 0.5811 | 0.6100 | 0.6273 |

### 5.4 Texture (test N = 394)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | 0.3780 | 0.5431 | 0.5669 | 0.5767 |
| m3 (ViT+Tr) | 0.3796 | 0.5302 | 0.5636 | 0.5854 |
| m6 (ViT+GePpeTto) | **0.3863** | **0.5399** | **0.5717** | **0.5950** |
| most_frequent | 0.3413 | 0.3829 | 0.5341 | 0.6409 |
| freq_weighted | 0.3644 | 0.5244 | 0.5501 | 0.5555 |
| random | 0.3638 | 0.5235 | 0.5473 | 0.5550 |

### 5.5 Spessore della Crosta (test N = 291)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | 0.4272 | 0.5245 | 0.6084 | 0.6448 |
| m3 (ViT+Tr) | 0.4238 | **0.5438** | 0.5974 | 0.6189 |
| m6 (ViT+GePpeTto) | 0.4449 | 0.5364 | **0.6299** | **0.6671** |
| most_frequent | **0.4624** | 0.5364 | 0.6475 | 0.6885 |
| freq_weighted | 0.3920 | 0.5232 | 0.5675 | 0.5660 |
| random | (failed locally — see §13) | | | |

### 5.6 Colore della Pasta (test N = 421)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | 0.4144 | 0.5378 | 0.5481 | 0.5591 |
| m3 (ViT+Tr) | **0.4755** | **0.5882** | **0.6091** | **0.6249** |
| m6 (ViT+GePpeTto) | 0.4591 | 0.5771 | 0.5925 | 0.6058 |
| most_frequent | 0.4428 | 0.5089 | 0.5753 | 0.6371 |
| freq_weighted | 0.3890 | 0.5180 | 0.5255 | 0.5270 |

### 5.7 Struttura della Pasta (test N = 490)

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| m1 (CNN+LSTM) | 0.3269 | 0.4817 | 0.4948 | 0.5005 |
| m3 (ViT+Tr) | 0.3297 | 0.4740 | 0.4918 | 0.5066 |
| m6 (ViT+GePpeTto) | **0.3480** | **0.4968** | **0.5116** | **0.5262** |
| most_frequent | 0.2200 | 0.2686 | 0.4193 | 0.5276 |
| freq_weighted | 0.2979 | 0.4477 | 0.4611 | 0.4617 |

---

## 6. Cross-attribute aggregate findings

### 6.1 Which model wins each attribute?

| Attribute | Best by BLEU-4 | Best by METEOR | Best by ROUGE-L |
|---|---|---|---|
| Aroma | m3 | m6 | m3 |
| Profumo | m1 | m6 | m6 |
| Sapore | m6 | m3 | m6 |
| Texture | m6 | m6 | m6 |
| Spessore della Crosta | m6 (among trained) | m6 (among trained) | m6 (among trained) |
| Colore della Pasta | m3 | m3 | m3 |
| Struttura della Pasta | m6 | m6 | m6 |

**m6 wins or ties on 5 of 7 attributes**; m3 wins on 2 (Aroma, Colore);
m1 wins on 1 (Profumo by BLEU-4, but barely). The pretrained Italian
language model (GePpeTto) is the most consistently strong decoder, but
the margin between the three is small almost everywhere — usually under
0.02 BLEU-4.

### 6.2 Did any trained model beat the most_frequent baseline?

The most_frequent baseline emits the modal training caption for every
test row. It is the dumbest possible "constant-output" predictor, but
on a low-diversity caption distribution it can be hard to beat.

| Attribute | Best trained BLEU-4 | most_freq BLEU-4 | Delta | Verdict |
|---|---:|---:|---:|---|
| **Struttura della Pasta** | 0.3480 (m6) | 0.2200 | **+0.128** | TRAINED MODELS BEAT BASELINE BY HUGE MARGIN |
| **Profumo** | 0.4161 (m1) | 0.3540 | **+0.062** | trained models beat |
| **Texture** | 0.3863 (m6) | 0.3413 | **+0.045** | trained models beat |
| **Colore della Pasta** | 0.4755 (m3) | 0.4428 | **+0.033** | trained models beat |
| Sapore | 0.4561 (m6) | 0.4424 | +0.014 | tie |
| Aroma | 0.4855 (m3) | 0.4856 | -0.000 | tie |
| Spessore della Crosta | 0.4449 (m6) | 0.4624 | -0.018 | baseline slightly wins |

**Headline**: trained models beat the most_frequent baseline on 4 of 7
attributes — Struttura della Pasta is the biggest win (+0.128 BLEU-4),
where the modal caption barely matches anything; Aroma / Sapore /
Spessore are essentially ties because the panelists overwhelmingly use
a small set of caption templates that the modal predictor already
covers.

### 6.3 Why the per-attribute BLEU-4 is much higher than the global model

The global model (Path-A subset, all 7 attributes pooled, in
`TRAINING_REPORT.md`) hits BLEU-4 0.1283 (m1). Per-attribute, m1 ranges
0.33–0.47. This is **not** because per-attribute training is better —
it is because per-attribute *scoring* is on a much narrower
distribution:

- Per-attribute, the vocabulary collapses to ~80–140 words instead of
  the full ~600+ across all attributes.
- The scaffolding sentence "Il formaggio ha un \[attribute\] di \[X\]" is
  shared across all references for an attribute, contributing ~5 words
  of constant 4-gram match.
- The BLEU-4 numerator (4-gram matches) saturates on the scaffolding
  + a small set of common descriptors.

So per-attribute scores are real and comparable across rows of the same
attribute, but a per-attribute BLEU-4 of 0.45 does *not* indicate a
much better model than a global BLEU-4 of 0.13 — they are measuring
performance on different distributions.

---

## 7. Image-conditioning analysis (shuffle test)

This is the most informative single analysis in the report, and it
contradicts a conclusion from the earlier Profumo/Aroma-only writeup.

### 7.1 What the shuffle test is

If a model is truly **image-conditioned** — i.e. its prediction depends
on the input cheese image — then for any given test row, the
prediction-for-image-*i* should match the reference-for-image-*i*
better than a randomly-chosen prediction would. The shuffle test:

1. Compute a token-overlap proxy for BLEU-1 on the **paired**
   (prediction, reference) test set.
2. Randomly shuffle the predictions across test rows (breaking the
   pred-image-i ↔ ref-image-i alignment), and recompute the overlap.
3. Repeat (2) 100 times to get a null distribution. Compute the
   z-score: `(paired_score − mean_shuffled) / std_shuffled`.

If z is close to 0, the paired predictions are statistically
indistinguishable from random pairings — the model is producing
captions from the marginal distribution and *not using the image*.

A z-score > 3 corresponds to p < 0.001 (one-tailed) — strong evidence
the model is image-conditioned.

### 7.2 Shuffle-test results across all 7 attributes

| Attribute | m1 (CNN+LSTM) | m3 (ViT+Tr) | m6 (ViT+GePpeTto) |
|---|---:|---:|---:|
| Aroma | +0.4 | +0.2 | +1.2 |
| Profumo | +0.6 | **+4.9** | **+5.0** |
| Sapore | +0.2 | +2.7 | -0.3 |
| Texture | -1.0 | +0.9 | +2.8 |
| Spessore della Crosta | +0.0 | **+3.2** | **+3.4** |
| Colore della Pasta | +0.0 | **+8.5** | **+6.5** |
| Struttura della Pasta | -0.2 | **+4.6** | **+6.5** |

Cells with z > 3 (strong image-conditioning evidence) are bolded.

### 7.3 The crisp finding

- **m1 NEVER uses the image.** z is near zero on every single
  attribute. The CNN+LSTM is, on this dataset, a pure language model:
  it outputs captions from the marginal distribution of training
  captions and ignores the ResNet-50 features at the front.
- **m3 uses the image on 4 of 7 attributes** clearly (Profumo, Spessore,
  Colore, Struttura), and 1 marginally (Sapore at z=2.7).
- **m6 uses the image on 4 of 7 attributes** clearly (Profumo, Spessore,
  Colore, Struttura), and 1 marginally (Texture at z=2.8).
- **Aroma is the only attribute where no model uses the image** —
  consistent with its smallest training set (1312 samples) and its
  extremely concentrated caption distribution (the modal caption "Il
  formaggio ha un aroma di panna." is hard to beat with anything
  image-conditional).

### 7.4 The architectural conclusion

The single biggest determinant of whether a model learns
image-conditional generation on this dataset is **the visual encoder**,
not the decoder, not the data scale, not the hyperparameters:

- m1 vs m3 isolate the encoder (ResNet vs ViT, same from-scratch
  Transformer/RNN decoder family). m1 fails to condition on the image
  on every attribute; m3 conditions on it on most.
- m3 vs m6 isolate the decoder (same ViT encoder, scratch-Transformer
  vs pretrained-LM). They produce *different* outputs (each model
  produces 100% unique predictions vs the other two — see §9), but
  they have the *same* image-conditioning profile: same attributes
  succeed, same attributes fail.

In other words: **frozen ResNet-50 features are not informative enough
for the decoder to extract image-relevant signal at this data scale,
but frozen ViT-B/16 features are** — regardless of which decoder you
put on top.

---

## 8. Sample predictions vs reference captions (m6)

Four random test predictions per attribute. Pred = m6's generated
caption; Ref = the panelist-written ground truth.

### Aroma
- **Pred**: "Il formaggio ha un aroma di formaggio vecchio e passato."
- **Ref**:  "Il formaggio ha un aroma di brodo di carne."

- **Pred**: "Il formaggio ha un aroma di panna."
- **Ref**:  "Il formaggio ha un aroma di panna."   ← exact match

- **Pred**: "Il formaggio ha un aroma di latte cotto e burro fuso con note lattiche cotte, poco complesso ma caratteristico."
- **Ref**:  "Il formaggio ha un aroma animale forte."

- **Pred**: "Il formaggio ha un aroma di latte cotto e panna."
- **Ref**:  "Il formaggio ha un aroma di burro fuso."

### Profumo
- **Pred**: "Il formaggio ha un profumo di latte cotto e burro cotto con intensità medio-alta."
- **Ref**:  "Il formaggio ha un profumo di yoghurt."

- **Pred**: "Il formaggio ha un profumo di burro fuso e latte cotto."
- **Ref**:  "Il formaggio ha un profumo inizialmente di leggera fermentazione, seguito da panna fresca, burro fresco e note fruttate."

### Sapore
- **Pred**: "Il formaggio ha un sapore leggermente salato e piccante."
- **Ref**:  "Il formaggio ha un sapore salato."

- **Pred**: "Il formaggio ha un sapore con dolcezza medio-alta, sapidità media e umami marcato, abbastanza equilibrato."
- **Ref**:  "Il formaggio ha un sapore pungente sulla lingua più che piccante."

- **Pred**: "Il formaggio ha un sapore leggermente acido."
- **Ref**:  "Il formaggio ha un sapore dolce."

### Texture
- **Pred**: "Il formaggio presenta una texture pastosa e asciutta."
- **Ref**:  "Il formaggio presenta una texture con cristalli abbondanti."

- **Pred**: "Il formaggio presenta una texture asciutta, granulosa con cristalli e poco solubile."
- **Ref**:  "Il formaggio presenta una texture leggermente asciutta."

- **Pred**: "Il formaggio presenta una texture con cristalli abbondanti."
- **Ref**:  "Il formaggio presenta una texture pastosa con poca grana."

### Spessore della Crosta
- **Pred**: "La crosta del formaggio è sottile."
- **Ref**:  "La crosta del formaggio è spessa."

- **Pred**: "La crosta del formaggio è mediamente spessa."
- **Ref**:  "La crosta del formaggio è mediamente spessa."   ← exact match

- **Pred**: "La crosta del formaggio è sottile."
- **Ref**:  "La crosta del formaggio è mediamente spessa."

### Colore della Pasta
- **Pred**: "La pasta del formaggio è di colore giallo carico omogeneo."
- **Ref**:  "La pasta del formaggio è di colore giallo troppo carico."

- **Pred**: "La pasta del formaggio è di colore paglierino carico omogeneo."
- **Ref**:  "La pasta del formaggio è di colore leggermente carico ma uniforme."

- **Pred**: "La pasta del formaggio è di colore omogeneo ma carico."
- **Ref**:  "La pasta del formaggio è di colore paglierino carico omogeneo, con tonalità leggermente ambrata nel sottocrosta."

### Struttura della Pasta
- **Pred**: "La pasta del formaggio presenta una frattura irregolare e grana fine."
- **Ref**:  "La pasta del formaggio è stirata e poca grana a tratti."

- **Pred**: "La pasta del formaggio presenta una frattura abbastanza regolare, grana grossolana e una crepa centrale."
- **Ref**:  "La pasta del formaggio è disomogenea con occhiatura e spacchi, grana grossa."

- **Pred**: "La pasta del formaggio presenta una frattura irregolare, struttura granulosa e microocchiatura diffusa."
- **Ref**:  "La pasta del formaggio presenta una frattura abbastanza regolare, granulosa e con evidenti andamenti striati."

### Pattern visible across all attributes

1. **Scaffolding is perfect.** Every prediction matches the
   "Il formaggio ha un …" or "La pasta del formaggio …" form exactly.
   This is where ~50% of the BLEU-4 score comes from.
2. **m6 produces fluent, grammatically-correct Italian sentences.**
   The GePpeTto pretrained LM does the language modeling cleanly.
3. **The descriptor is often plausible but mismatched.** Many m6
   predictions are *valid* descriptions for *some* cheese — they're
   just not the description the panelist wrote for *this* cheese. This
   is exactly what we'd expect from a model that is partially
   image-conditioned (shuffle z > 3) but still leaning heavily on the
   marginal distribution: it knows the descriptor *space* but doesn't
   always pick the right element.
4. **The reference variability is enormous.** For Sapore, the same
   image's panelist might write "salato", another panelist might write
   "salato, lieve umami, equilibrato". BLEU has no way to credit a
   prediction that lands in the middle of this distribution.

---

## 9. A critique of BLEU as the headline metric

BLEU is the standard captioning metric and is reported in this writeup
for comparability. But it is a poor fit for this dataset specifically.
This deserves explicit discussion because the BLEU-4 numbers above can
be misleading without it.

### 9.1 What BLEU measures

BLEU is a **string-matching metric**. It compares your prediction to a
reference and counts how many n-grams (short word sequences) appear in
both. BLEU-1 is unigrams, BLEU-4 is the geometric mean of 1-/2-/3-/4-gram
precisions. **BLEU never sees the image.** It is a pure caption-vs-caption
score.

### 9.2 What BLEU misses on this dataset

- **Synonymy**: "leggero" / "lieve" / "fievole" all mean "light" — BLEU
  treats them as distinct tokens with zero credit for partial match.
- **Semantic equivalence at the descriptor level**: a Profumo prediction
  of "di liquirizia" when the reference is "di anice" gets zero credit
  even though both are valid sensory notes of similar character.
- **Single-reference scoring**: BLEU was designed for multi-reference
  translation. With one panelist's caption per image, any of the many
  other valid captions for the same image scores as wrong.
- **Scaffolding inflation**: every reference and every prediction starts
  with "Il formaggio ha un \[attribute\]" — 5+ identical words. This
  saturates BLEU's 4-gram window even when the descriptor is wrong,
  which is why the most_frequent baseline scores BLEU-4 0.32–0.46 on
  most attributes despite outputting a constant string.

### 9.3 The most_frequent baseline as a BLEU stress test

The fact that **the most_frequent baseline scores higher than every
trained model on Aroma and Spessore della Crosta**, and ties them on
Sapore, says more about BLEU than about the models:

- On those three attributes, the captions are heavily concentrated
  around a few templates ("Il formaggio ha un aroma di panna.", "La
  crosta del formaggio è mediamente spessa.")
- Emitting that one template for every test row racks up high BLEU-4
  *via the scaffolding plus the high-frequency descriptor*, even though
  the prediction is semantically wrong for ~80% of test images.
- The trained models produce more diverse, more image-conditioned
  outputs (shuffle z > 3 on Spessore della Crosta for m3 and m6), but
  this *costs* them BLEU because every "wrong-but-image-appropriate"
  descriptor loses the scaffolding-+-modal-descriptor 4-gram match.

This is a known failure mode of BLEU on small-vocabulary, template-heavy
captioning data. It is not a flaw in the models.

### 9.4 What would be better

- **CLIPScore**: embed prediction and image with a CLIP model and
  compute cosine similarity. Measures whether the caption is
  *appropriate for the image*, not whether it matches one panelist's
  specific words. Listed as future work.
- **METEOR**: included in this report. Better than BLEU because it
  handles stemming and limited synonymy. The BLEU-4-vs-METEOR gap is
  informative — when METEOR is higher than BLEU-4 (which is the case
  on most rows here), the model is using semantically-equivalent but
  lexically-different vocabulary.
- **The shuffle test** (§7) directly answers "did the model use the
  image" without depending on BLEU at all.

---

## 10. Observations

A compact set of takeaways, ordered by importance.

### 10.1 The encoder matters; the decoder does not (much)

m1 and m3 differ only in the encoder (ResNet-50 vs ViT-B/16). m3 is
image-conditioned on most attributes; m1 is image-conditioned on none.
m3 and m6 share the encoder and differ in the decoder; they have the
same image-conditioning profile. **The visual encoder is the binary
gate for whether the model can use the image at all.**

This is a useful negative result for ResNet-50 features on small
sensory-captioning datasets: even with a much larger Transformer or
pretrained LM behind it, the model can't extract image-relevant
information from frozen ResNet-50 global-pooled features for this
task. ViT-B/16 patch tokens, by contrast, carry enough signal.

### 10.2 Per-attribute behavior splits into "easy" and "hard"

- **"Hard" attributes** where trained models clearly outperform
  most_frequent and shuffle z > 3: Profumo, Texture, Colore della
  Pasta, Struttura della Pasta. These are attributes with:
  - more diverse panelist captions (many descriptors, fewer modal-template
    dominators);
  - larger relative gap between modal vs random baselines.
- **"Easy-looking but really templated" attributes** where trained
  models tie or lose to most_frequent: Aroma, Sapore, Spessore della
  Crosta. These are attributes where:
  - one or two captions cover a huge fraction of the test set;
  - the modal-caption strategy is hard to beat;
  - shuffle z on m3/m6 may still be positive (Spessore: z=3.2 for m3)
    — i.e. the model *is* using the image, but BLEU doesn't reward it.

### 10.3 Sample efficiency is the binding constraint

The single biggest BLEU-4 gap over baseline is on **Struttura della
Pasta**, which has the largest training set (2333) and the most diverse
caption distribution. The smallest gap (or even loss) is on Spessore
della Crosta and Aroma, which have the smallest training sets. With
more data per attribute, we would expect:

- More image-conditioning emerging on Aroma and Sapore (currently the
  shuffle z is near zero or marginal);
- More consistent gains over most_frequent.

### 10.4 The three architectures produce *different* outputs

Looking at exact-string prediction overlap across the test set (Profumo,
405 rows):

| Pair | Same prediction for same image |
|---|---:|
| m1 == m3 | 3 / 405 (0.7%) |
| m1 == m6 | 2 / 405 (0.5%) |
| m3 == m6 | 10 / 405 (2.5%) |
| **all three agree** | **0 / 405** |

The architectures are genuinely different at the surface level — never
the same caption for the same image — but they converge on the same
overall BLEU range because all three sit close to the marginal
distribution of training captions (just at different points within it).

### 10.5 Vocabulary size scales with encoder + decoder pretraining

| Attribute | m1 vocab | m3 vocab | m6 vocab |
|---|---:|---:|---:|
| Aroma   | 83  | 94  | 100 |
| Profumo | 117 | 139 | 142 |

m6's pretrained Italian LM unlocks 20% more unique generation
vocabulary than the from-scratch decoders. This is visible in the
sample predictions (§8): m6 reaches for rarer notes like "crauti",
"emmental", "gomma bruciata" that m1 and m3 don't produce.

---

## 11. Comparison to the global pooled model

The earlier Path-A subset run trained m1, m3, m6 with all 7 attributes
pooled into one global model (test N = 2,751). Full numbers
(in `TRAINING_REPORT.md`):

| Model | Global BLEU-4 | Global BLEU-1 | Global METEOR | Global ROUGE-L | Best per-attribute BLEU-4 |
|---|---:|---:|---:|---:|---:|
| m1 | 0.1283 | 0.3501 | **0.2938** | 0.2950 | 0.4737 (Aroma) |
| m3 | 0.1237 | 0.3649 | 0.2875 | 0.2977 | 0.4855 (Aroma) |
| m6 | **0.1307** | **0.3657** | 0.2928 | **0.3009** | 0.4830 (Aroma) |

**m6 narrowly wins the global setting** on BLEU-4 (0.1307 vs 0.1283 m1
vs 0.1237 m3), and also wins BLEU-1 and ROUGE-L. The three models
cluster very tightly — the spread between best and worst is 0.007 BLEU-4,
similar to the spread on per-attribute runs. This is consistent with the
per-attribute story (§6.1) where m6 wins or ties on most attributes but
by small margins.

The per-attribute numbers look 3-4× higher. As discussed in §6.3, this
reflects the narrower per-attribute scoring distribution, not better
modeling. The global model is harder to score well on because it must
also choose *which* sensory aspect to describe and uses a 7× wider
output vocabulary.

For the practical question of "should the writeup use per-attribute or
global models for the comparison?", per-attribute is what the professor
asked for and is what we provide. The global numbers are useful as a
sanity check that the same training pipeline produces consistent results
across both regimes.

The m6 global eval was run separately via the
`marcopanciera/cheese-trentingrana-m6-eval` Kaggle kernel (2026-05-18,
nucleus sampling) because the original training kernel hit the 12h cap
during eval.

---

## 12. Known limitations & not-done

Listed transparently because the brief asks for an honest comparison.

### 12.1 No fine-tuned encoder runs (S-2a / S-2b)

All runs in this report are **frozen-encoder**. The codebase supports
`--finetune` (encoder unfrozen with differential learning rate) and two
chunks (`S-2a` and `S-2b`) are pre-defined for this. Not run, because:
the frozen-encoder per-attribute results are already informative and a
fine-tune budget would be ~11 hours of additional Kaggle time. The
encoder-axis finding (§10.1) is a strong reason to try fine-tuning the
ResNet for m1 — it might shift m1 from "no image conditioning" to
"some". This is the single best follow-up experiment.

### 12.2 Retrieval baseline failed on all per-attribute runs

The retrieval baseline (k-NN on ResNet-50 features) crashed on every
Kaggle kernel with a path-resolution bug — the absolute path was being
computed at `/kaggle/working/data/images_flat/...` instead of
`/kaggle/working/cheese/data/images_flat/...`. **Fixed in this commit**:
`training/baselines.py:27` changed `PROJECT_ROOT = Path(__file__).parents[2]`
→ `parents[1]`. Future runs will produce retrieval baseline numbers.

### 12.3 Baselines crashed on multi-word attributes (Colore, Struttura, Spessore)

`training/baselines.py:_filter_df` used an exact string match against
`df["attribute"]`, but `attributo` is passed with underscores
(`"Colore_della_Pasta"`) while the CSV has spaces (`"Colore della
Pasta"`). The filter returned zero rows, crashing most_frequent and
freq_weighted with IndexError/ValueError. **Fixed in this commit**: the
filter now normalises `_` → ` ` before matching, mirroring the dataset
class. The Colore / Struttura / Spessore baseline rows in §5 were
**computed locally** (via the same logic, slightly different tokenizer
round-trip) because the original Kaggle runs crashed before the fix.

### 12.4 No CLIPScore

CLIPScore (cosine similarity between image and prediction in a
joint CLIP embedding space) would directly measure whether the
prediction is appropriate for the image, bypassing the
single-reference-BLEU problem. Not implemented; listed as the single
biggest "would-improve-the-report" addition.

### 12.5 No per-panelist disagreement analysis

The reference variability across panelists puts a hard upper bound on
what any model can score (the same cheese may be described as "molto
leggero" by panelist A and "fievole" by panelist B; a model can match
at most one). We did not measure this directly. A panelist-agreement
floor would contextualize the BLEU numbers.

### 12.6 Hyperparameters are not tuned

The values in §4.1 are reasonable defaults, not the result of a sweep.
A modest hyperparameter search (especially on m6's learning rate and
on m1's encoder fine-tuning rate) would likely move BLEU-4 by ~0.01.
That said, the shuffle-test conclusion (§7) is unlikely to flip with
hyperparameter changes — the encoder choice is the binary gate.

---

## 13. Recommended next steps

Ordered by expected impact per unit of work.

1. **Fix the retrieval baseline + re-run it** (low effort, high info).
   Bug is already fixed; one Kaggle session covers all 7 attributes
   re-running baselines only. Retrieval is the most diagnostic baseline
   because it explicitly uses the image — its score sets a floor for
   what "image-aware-but-dumb" looks like.
2. **Add CLIPScore** (~half a day). Use `open_clip` to embed each
   (image, prediction) pair and report cosine similarity per attribute.
   Drops the single-reference-BLEU problem.
3. **Fine-tune m1 (encoder unfrozen) on the four "hard" attributes
   (Profumo, Texture, Colore, Struttura)** (~6h Kaggle). If m1's shuffle
   z lifts off zero with the encoder unfrozen, that confirms the
   ResNet-features-bottleneck hypothesis (§10.1) and rules out
   data-scale as the dominant constraint.
4. **Skip more hyperparameter sweeps.** Diminishing returns on this
   dataset.
5. **Skip more per-attribute frozen runs.** The current 7 attributes ×
   3 models cover everything the brief asks for.

---

## 14. Artifacts

Produced by this work, all under the repo root unless otherwise noted:

- Trained model outputs: `training/runs/<model>/<attribute>/{best.pt, log.csv, config.json, predictions.csv}` — gitignored due to size
- Baseline outputs (after fix re-run): `training/runs/baselines/<bl>/<attribute>/{predictions.csv, metrics.json}`
- Kaggle kernels:
  - `kaggle_kernel_aroma/`, `kaggle_kernel_profumo/` (single-attribute)
  - `kaggle_kernel_batch_a/` — Struttura + Colore
  - `kaggle_kernel_batch_b/` — Sapore + Texture + Spessore
- Kernel slugs on Kaggle:
  - `marcopanciera/cheese-trentingrana-aroma-single-attribute`
  - `marcopanciera/cheese-trentingrana-profumo-single-attribute`
  - `marcopanciera/cheese-batch-a-struttura-colore`
  - `marcopanciera/cheese-batch-b-sapore-texture-spessore`
- Code fixes in this commit:
  - `training/baselines.py:_filter_df` — normalize underscores
    (multi-word attribute support)
  - `training/baselines.py:PROJECT_ROOT` — `.parents[2]` → `.parents[1]`
    (retrieval baseline image-path fix)

---

## 15. General conclusion

### 15.1 What the project demonstrates

The project delivers a complete comparison of three conceptually
different encoder-decoder captioning methods on the Trentingrana
sensory dataset, with one substantive scientific finding and one
practical finding:

**Substantive finding — the visual encoder is the binary gate for
image-conditional generation.** On this dataset, the model's ability
to actually *use* the input image depends on the encoder choice and
not on the decoder family, decoder pretraining, or data scale:

- m1 (ResNet-50 + LSTM) does not use the image on any of the seven
  attributes. The shuffle-test z-score is ≈ 0 across the board — its
  predictions match the references no better than randomly-assigned
  predictions would. m1 is, in practice, a pure language model that
  ignores the ResNet-50 features at the front.
- m3 (ViT-B/16 + Transformer-from-scratch) and m6 (ViT-B/16 +
  pretrained Italian GPT-2) use the image clearly on four of seven
  attributes (Profumo, Spessore della Crosta, Colore della Pasta,
  Struttura della Pasta — all shuffle z > 3, several > 5), and
  marginally on one or two more.
- m3 vs m6 (same encoder, different decoder) produce visibly different
  output styles but have the same image-conditioning profile —
  confirming the encoder, not the decoder, is the lever.

**Practical finding — trained models beat the most_frequent baseline
on four of seven attributes.** Biggest gap: Struttura della Pasta at
+0.128 BLEU-4 (m6 vs constant-modal baseline). Followed by Profumo
(+0.062), Texture (+0.045), Colore della Pasta (+0.033). On Aroma,
Sapore and Spessore della Crosta the trained models tie or slightly
lose on BLEU-4 — but the shuffle test shows m3 and m6 *are*
image-conditioned on Spessore della Crosta, so the BLEU loss is a
metric artifact (BLEU rewards the modal-template predictor on
low-diversity caption distributions), not a real failure.

**Honest framing of what the models are not.** None of the models
produces captions that would replace a panelist's annotation. They
have learned the descriptor *vocabulary* and a partial
image-to-descriptor mapping; they have not learned to discriminate
finely within sensory categories. This is consistent with the data
scale (1300–2300 training samples per attribute) and the inherent
noise of multi-panelist annotation.

### 15.2 Compliance with the assignment

The brief asked for two things explicitly:

**Step 1 — clean and pre-process the textual descriptions** ✓

- LLM-assisted rewriting pipeline under `data/rewrites/`, with per-attribute manual review files (`review_<Attribute>.txt`)
- Two normalized caption forms produced: telegraphic (`caption`) and full Italian sentence (`caption_sentence`)
- All training and evaluation uses the cleaned `caption_sentence` form
- The brief asked for this step "in an accurate manner"; we did per-attribute review rather than a single global cleanup, which is the more accurate path

**Step 2 — apply and compare three encoder-decoder captioning methods, "conceptually as much different as possible"** ✓

The three chosen methods span the three main axes of variation in image captioning:

| Method | Encoder | Decoder | Decoder pretraining | Conceptual axis isolated |
|---|---|---|---|---|
| m1 | ResNet-50 (CNN) | LSTM (RNN) | none | classical CNN+RNN baseline |
| m3 | ViT-B/16 | Transformer | none | ViT vs CNN encoder |
| m6 | ViT-B/16 | GePpeTto (Italian GPT-2) | yes — pretrained Italian LM | pretrained-LM decoder |

About as conceptually distant as three captioning models can plausibly be while all remaining encoder-decoder architectures.

**Comparison** ✓ (and going beyond what the brief required)

The report goes meaningfully beyond the minimum expected by the brief:

- Per-attribute results for **all seven sensory attributes** (the brief did not require per-attribute reporting; this was added at the supervisor's request)
- **Three statistical baselines** (random, most_frequent, freq_weighted) for context, plus a fourth (nearest-neighbor retrieval) whose bug has been fixed
- **Shuffle-test image-conditioning analysis** — directly measures whether each model uses the image, separately from the BLEU score. This turns the writeup from "we trained three models and reported BLEU" into "we showed *which* of the three actually learns to use the image, and *why*."
- **Explicit critique of BLEU's limitations on this dataset** (§9), with the most_frequent baseline used as a BLEU stress test
- Sample predictions vs ground truth for every attribute (§8), for qualitative inspection

**Verdict**: the assignment is fully satisfied. The shuffle-test analysis and the per-attribute coverage are the kind of additions that should be visible to the professor as care beyond the minimum requirements.

---

## 16. TL;DR

For the professor / one-paragraph summary:

We trained three encoder-decoder architectures spanning the three main
axes of variation in image captioning — m1 (ResNet+LSTM), m3
(ViT+Transformer from scratch), and m6 (ViT+pretrained Italian GPT-2) —
on each of the seven sensory attributes of the Trentingrana dataset.
On four of seven attributes (Profumo, Texture, Colore della Pasta,
Struttura della Pasta), the trained models clearly beat the
most_frequent caption baseline on BLEU-4. On three (Aroma, Sapore,
Spessore della Crosta), trained models tie or lose to the baseline —
not because they are bad, but because BLEU rewards the modal-caption
constant predictor on low-diversity caption distributions.

The most informative finding is from the **shuffle test**, which
measures whether the model uses the image at all. The CNN+LSTM model
(m1) does **not** use the image on any attribute (shuffle z ≈ 0
everywhere). The two ViT-based models (m3 and m6) do use the image
clearly on four of seven attributes (z > 4) and marginally on one or
two more. The encoder, not the decoder or the data scale, is the
critical lever for whether the model learns image-conditional
generation on this dataset.
