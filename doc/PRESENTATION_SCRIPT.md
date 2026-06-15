# Presentation script — expanded version

Per-slide narrative for the 30-minute talk. Each slide section includes:

- **On screen** — what's visually displayed
- **What to say** — the actual talk track, written in plain spoken language
- **Numbers to know cold** — figures you should not have to look up
- **Transition** — how to bridge to the next slide
- **If asked** — anticipated questions and short answers ready

Spoken text is roughly the length of what fits in the time budget at a
calm pace (about 130-150 words per minute).

---

## SECTION 1 — Introduction & problem (slides 1-2, 2 minutes)

### Slide 1 — Title (30 s)

**On screen**: Project title, your name, course/date. Background: one
nice fetta image (cheese cross-section).

**What to say**:

"Good morning everyone. Today I'm going to walk you through a captioning
project on Trentingrana cheese — specifically, a comparison of three
different image-to-text models trained to produce panelist-style sensory
descriptions of cheese-wheel section images. The work was structured
around two questions the assignment asked: first, how to clean a messy
real-world dataset of taster annotations, and second, how three
architecturally very different captioning models compare on this data.
I want to spend most of the time on the dataset itself, because that's
where most of the interesting work lives in a project like this, and
where the results we'll see later actually come from."

**Transition**: "Let me start with what the task actually is."

---

### Slide 2 — The assignment (90 s)

**On screen**: Direct quote from the brief, side-by-side input/output
diagram (cheese image ⇒ Italian sentence).

**What to say**:

"The brief was specific about two steps. Step one — clean and pre-process
the textual descriptions of the tasters. Things like substituting
quantitative descriptions with qualitative ones, rephrasing dialect
sentences, turning telegraphic comments into elegant sentences, reducing
synonyms. Step two — apply and compare three different encoder-decoder
captioning methods, and the brief explicitly says they should be
conceptually as much different as possible.

A few things to call out about this framing. First, step one is
weighted as a separately-evaluated piece of work — the brief specifically
notes that cleaning has to be done in an accurate manner to avoid
hurting the captioning models that come after. Second, this is a
*comparison* project. There's no single best model we're trying to find
— the goal is to understand how three different architectures behave on
this data. We'll come back to 'conceptually different' when I motivate
the three architectures we picked.

What the model has to do — concretely — is take a cheese image like the
one on screen, and produce a fluent Italian sentence describing one of
seven sensory attributes."

**Numbers to know cold**:
- 7 sensory attributes
- Two steps in the brief: cleaning + comparison

**Transition**: "Before any of that — let me show you the dataset, which
is more substantial than it might first appear."

---

## SECTION 2 — Dataset & data preparation (slides 3-13, 16 minutes)

### Slide 3 — Source of the data (90 s)

**On screen**: A side-by-side fetta + grana of the same cheese.
Labels: "fetta" and "grana".

**What to say**:

"The cheese itself comes from the Trentingrana consortium, which is the
PDO grana cheese produced in Trentino. The data spans four scoring
years — from 2018 through 2022 — and the actual images were taken with
something called an IRIS electronic visual analyzer. This is important
because IRIS has controlled lighting and a controlled camera setup, so
the images are visually consistent: the same camera, same illumination,
same background, across all 979 samples. That removes one common source
of confusion for image models — illumination drift.

For each cheese sample we get two views. The fetta is the full
cross-section — basically the cheese cut in half. The grana is a
close-up of a small region of the cheese paste, giving grain-level
detail. Every model in this project takes both views as input — they're
passed through the encoder together.

The labels come from a panel of 20 trained tasters, each scoring across
seven sensory attributes. I'll show you the attributes in a moment."

**Numbers to know cold**:
- 4 years
- 20 panelists
- 979 cheese samples
- IRIS analyzer

**If asked**: "What's an electronic visual analyzer?" → "It's a closed
imaging cabinet — fixed camera position, controlled LED lighting,
known geometry. The point is reproducibility — every image is taken
under the same conditions."

**Transition**: "Let me give you the actual scale."

---

### Slide 4 — Scale of the dataset (60 s)

**On screen**: Big numbers — 979 / 20 / 4 / 7 / 18,427. Splits table.

**What to say**:

"In total: 979 unique cheese samples, scored by 20 panelists across 4
years and 7 sensory attributes. Each (cheese, attribute, panelist)
combination is one row in the dataset. That gives us 18,427 caption
rows total. So a lot of label noise, because the same cheese is often
described by multiple panelists — and they don't always agree.

We split at the *cheese sample* level — not at the row level. So if
sample number 305 is in the training set, every panelist's annotation
of that cheese is in training; no panelist annotation of cheese 305
appears in test. This prevents the kind of subtle leakage where one
panelist describes a cheese in training and a different panelist
describes the same cheese in test — which would let the model memorize
cheese identity rather than learning a real mapping.

Sample-level split: 674 train, 143 validation, 147 test."

**Numbers to know cold**:
- 18,427 total rows
- 674 / 143 / 147 sample split

**If asked**: "How were the splits chosen?" → "Random at the sample
level — fixed seed for reproducibility, no stratification by year or
panelist."

**Transition**: "Each sample gets scored on these seven attributes."

---

### Slide 5 — The 7 sensory attributes (90 s)

**On screen**: Table of 7 attributes with what each describes and a
typical caption start.

**What to say**:

"Here are the seven attributes. I want you to look at this table
carefully because some of what we'll see later depends on it.

Aroma is the smell on tasting. Profumo is the smell on opening — so
both are olfactory but at different moments. Sapore is the taste.
Texture is the mouthfeel. Then we have three structural attributes —
Spessore della Crosta is the rind thickness; Colore della Pasta is
the interior color of the paste; and Struttura della Pasta is the
interior structure, the grain, the fracture pattern.

Here's the important observation. Some of these attributes describe
things that are visible in the image — color, structure, crust
thickness, partly texture. Some of them describe things that have
nothing to do with the image — aroma, profumo, sapore. You cannot
tell what something smells like from a photograph of it.

Now, the panelists tasted the cheese physically and then wrote captions
that were paired with the image. But the model only ever sees the
image. So already we should expect that captioning for color will be
easier than captioning for smell — because color is in the pixels and
smell is not. We'll come back to this when we get to results."

**Numbers to know cold**:
- 7 attributes; 3 visible, 3 sensory, 1 mixed (Texture)

**If asked**: "Why include the smell attributes if the image can't help?"
→ "The brief specifies all seven. And it's an interesting research
question — even an image-conditioned prior over caption distributions
might capture *some* signal if certain visual cues correlate with
certain smells across the dataset."

**Transition**: "Now — what do the panelist captions actually look
like before cleaning?"

---

### Slide 6 — Raw captions are messy (90 s)

**On screen**: 3-4 real raw caption examples, ideally showing
telegraphic / dialectal / inconsistent-synonyms problems.

**What to say**:

"The first thing that hits you when you open the raw dataset is that
the panelist captions are genuinely messy. Let me show you a few
real examples.

Here's one — 'aroma fresco fieno tagliato.' That's not even a
sentence — it's three nouns telegraphic-style. 'Fresh aroma cut hay.'
Another — 'salatozzo' — that's a dialect-flavored word for slightly
salted, not standard Italian. Inconsistent punctuation everywhere,
inconsistent capitalization, sometimes captions of one word, sometimes
captions of a paragraph.

But the most consequential mess is in synonyms. Look at how panelists
describe a light aroma intensity: 'leggero,' 'lieve,' 'fievole,' 'poco
intenso,' 'molto leggero.' These are five different ways to say
essentially the same thing. If a model learns to predict 'leggero' but
the reference for a test sample happens to be 'lieve,' it gets zero
credit on every standard captioning metric — even though the prediction
is semantically correct.

So if we train directly on this raw text, the model would learn the
noise as much as the structure. That's exactly what the brief is
warning about — step 1 has to be done well, or step 2 inherits the
mess."

**Numbers to know cold**: at least one specific example of synonym
chaos to keep in your head ("five synonyms for 'light aroma'")

**Transition**: "So that's the setup for step 1 — caption cleaning."

---

### Slide 7 — Caption cleaning pipeline (2 minutes) — IMPORTANT

**On screen**: A flow-chart diagram of the preprocessing pipeline (raw
→ LLM rewrite → manual review → two normalized output forms).

**What to say**:

"Step 1 of the brief is the caption cleaning pipeline. Here's what we
actually did.

We didn't do this globally — one pass over the whole dataset. We did
it *per attribute*. There are seven separate cleaning pipelines, one
for each sensory attribute, because the vocabulary and the conventions
differ across them. Aroma captions look different from color captions
which look different from structure captions, and they need different
synonym mappings, different sentence forms, different rephrasing
rules.

The pipeline goes like this. The raw panelist text goes through an
LLM-assisted rewriting step, with attribute-specific prompts. For each
attribute, we wrote a prompt that handles the kinds of rewriting that
attribute needed — telegraphic → sentence, dialect → standard Italian,
synonym normalization, etc. That gives us an automated first-pass
rewrite.

Then we did manual review. For each attribute there's a review file
in `data/rewrites/review_<attribute>.txt` where we caught cases the
LLM got wrong and edited them by hand. This is a meaningful amount of
work — not just a stamp on automation.

The output is two caption forms per row. The first is `caption` —
telegraphic but normalized. The second is `caption_sentence` — a full
Italian sentence with consistent form. Every model in this work was
trained and evaluated on `caption_sentence`, because the brief
specifically asks for elegant sentences, and because a full-sentence
target makes evaluation more meaningful — telegraphic captions don't
have enough words to make BLEU-4 informative.

This step is per-attribute, not global, and it's by far the most
work-intensive part of the project."

**Numbers to know cold**:
- 7 separate per-attribute pipelines
- Two output forms: `caption` and `caption_sentence`
- Manual review files exist per attribute

**If asked**: "Why per-attribute rather than one big cleanup?" →
"Because the rules differ. The rewriting prompt for Profumo has to
handle olfactory terminology specifically — 'di liquirizia,' 'di
panna,' 'di latte cotto.' The rewriting prompt for Spessore needs
quantitative-to-qualitative conversion — '2 mm' → 'sottile.' A single
global prompt either does both badly or has to be enormous."

**If asked**: "Which LLM did you use?" → "[Whatever you actually used —
honest answer.]"

**Transition**: "Let me show you what one of these rewrites actually
looks like, before and after."

---

### Slide 8 — Before / after (60 s)

**On screen**: 3 side-by-side rewrite examples. For each: (a) raw
caption, (b) cleaned `caption`, (c) full-sentence `caption_sentence`.

**What to say**:

"Three examples of the cleaning pipeline in action.

The first row — a telegraphic input gets turned into a fluent
sentence. The second — a dialect-flavored input becomes standard
Italian without losing meaning. The third — a comma-soup input gets
cleanly punctuated and re-ordered.

All training and all evaluation in the rest of this talk uses the
right-most column — the full Italian sentence."

**Transition**: "Now — here's where the data really splits into
attributes with very different characters."

---

### Slide 9 — Per-attribute diversity (2 minutes) — IMPORTANT

**On screen**: The 7-row diversity table — rows / unique captions /
modal-caption share / avg length per attribute.

**What to say**:

"This is the most important slide in the data section. It shows that
the seven attributes are not equally hard, and the panelists do not
treat them the same way.

Look at the modal-caption share column — that's the percentage of all
captions for an attribute that are word-for-word the most common one.

For Struttura della Pasta, it's 0.9%. Out of 3,413 captions, the most
common one appears fewer than one percent of the time. That means
panelists describe interior structure in highly varied ways — over
1,500 unique captions across 3,413 rows.

For Spessore della Crosta — it's 18.4%. Out of 1,939 captions for
rind thickness, almost one in five is literally the same sentence:
'La crosta del formaggio è mediamente spessa.' That's the dominant
template. The panelists don't have a lot to say about rind thickness,
so they fall back to the same phrase over and over.

The others sit in between. Sapore is 4.3% — moderately repetitive.
Aroma is 3.7%. Profumo is 1.6% — very diverse, lots of different
smells described in lots of different ways.

This single column predicts most of the BLEU-4 results we'll see
later. When the modal caption covers 18% of the data, a model that
just emits that one caption for everything is going to score very
well on BLEU. When the modal caption covers 0.9%, that strategy gets
crushed. We'll see exactly this pattern."

**Numbers to know cold**:
- Spessore 18.4% (the high outlier)
- Struttura 0.9% (the low outlier)
- Everyone else is between 1.6% and 4.3%

**Transition**: "Let me actually show you the modal captions."

---

### Slide 10 — Modal caption per attribute (60 s)

**On screen**: 7-row table — attribute and the most common caption.

**What to say**:

"Here are the most common captions per attribute, so you can see
concretely what 'modal caption' means.

For Aroma — 'Il formaggio ha un aroma di panna.' Cream-like aroma.
For Profumo — 'Il formaggio ha un profumo leggero.' Light smell.
For Sapore — salty. Texture — dry. Spessore della Crosta — medium
thick. Colore della Pasta — uniform color. Struttura della Pasta —
stretched paste.

Two things to notice. First, the captions are quite generic — these
are catch-all descriptions, not detailed ones. Second, you can
imagine a model that learns the modal caption for each attribute and
just emits that one. It would be wrong most of the time, but in any
specific case where the panelist *did* write the modal caption, it
would score perfectly on BLEU. That's the 'most-frequent baseline' we
compare against later."

**Transition**: "Quick word on the splits."

---

### Slide 11 — Train / val / test split (60 s)

**On screen**: Splits table — test rows and train rows per attribute.

**What to say**:

"The split is at the cheese-sample level, not the caption-row level —
I mentioned this earlier but it's worth re-emphasizing. The same
cheese never crosses the train/test boundary, even when scored by
multiple panelists.

In terms of how many training rows each attribute has, there's
meaningful variation. Struttura della Pasta has the most training
data — about 2,330 rows. Spessore della Crosta has the least — about
1,290. So there's a 1.8× difference between the largest and smallest
attribute's training set. That matters when we compare results
across attributes."

**Transition**: "Now the actual images."

---

### Slide 12 — Image inputs (90 s)

**On screen**: 4 fetta + grana pairs from `data/images_flat/`. Pick
visually different cheeses — e.g., one with a stretched paste, one
with eye holes, one young-looking, one well-aged.

**What to say**:

"This is what the model actually sees. Each input is a pair — fetta
and grana of the same cheese. All images are 224 by 224, RGB,
controlled lighting.

You can already see by eye that there's a lot of structural variation
between cheeses. Some have a uniform paste, some have eye holes,
some look more yellowed and aged, some have visible texture
differences. So in principle, there's enough visual signal here for a
vision model to discriminate. Whether the models we trained actually
use that signal is exactly the question we'll get to."

**Transition**: "Before I move to the models, there's one observation
that's worth setting up explicitly."

---

### Slide 13 — Visible vs not visible attributes (90 s) — IMPORTANT

**On screen**: Two-column slide listing 'visible from the image' vs
'not visible from the image' attributes.

**What to say**:

"Here's the framing for the rest of the talk.

Some attributes describe things that are in the image. Color is
literally in the pixels. Interior structure — grain, holes,
stretching — is visible. Crust thickness is measurable. Texture is
partly visible — you can see whether a paste looks smooth or grainy.

Some attributes describe things that aren't in the image. Aroma —
the smell — is not in the picture. Profumo — also smell — same thing.
Sapore — taste — same. The image gives a model essentially no
information about these.

So we should expect a model that genuinely learns from the image to
do better on the visible attributes than the non-visible ones. A
model that doesn't learn from the image — that just memorizes the
distribution of captions — will do roughly equally well or equally
badly across the board.

When we get to the results, this exact pattern will appear. It's
worth keeping this slide in mind."

**Numbers to know cold**:
- Visible: Colore, Struttura, Spessore, partly Texture
- Not visible: Aroma, Profumo, Sapore

**Transition**: "OK — that's the data. Now let me talk about the
three models."

---

## SECTION 3 — Model choices & training (slides 14-17, 6 minutes)

### Slide 14 — Three architectures, three axes (2 minutes)

**On screen**: Architecture comparison table — m1, m3, m6 with their
encoder, decoder, pretraining, and the conceptual axis each pair
isolates.

**What to say**:

"The brief says — and I'll quote it again — 'three captioning methods,
conceptually as much different as possible.' That's the design
constraint. So we picked three architectures that span the three
main axes of variation in image captioning.

m1 — ResNet-50 as the encoder, LSTM as the decoder. Both trained
from scratch on the captioning objective. This is the classical
CNN-plus-RNN baseline — it's the kind of model that was state of the
art for image captioning around 2015.

m3 — same general structure but with ViT-B/16 instead of ResNet, and
a from-scratch Transformer decoder instead of an LSTM. This is the
modern attention-everywhere version — both encoder and decoder are
transformers.

m6 — ViT-B/16 again as the encoder, but the decoder is GePpeTto, which
is a pretrained Italian GPT-2. So m6 is the only model that brings in
external linguistic knowledge — it doesn't have to learn Italian from
scratch.

These three pairwise comparisons each isolate one axis. m1 versus m3
isolates the encoder — CNN versus ViT. m3 versus m6 isolates the
decoder pretraining — same encoder, scratch decoder versus pretrained.
m1 versus m6 differs on both. That's about as conceptually distant as
three captioning models can plausibly be while still all being
encoder-decoder architectures.

One more thing — all three encoders are frozen. We do not fine-tune
the encoder weights on the captioning task. Only the decoder and the
projection layer between encoder and decoder train. This keeps the
comparison clean — same visual features available to all three
decoders. Fine-tuning would be a separate, additional dimension to
explore."

**Numbers to know cold**:
- m1 = ResNet+LSTM, m3 = ViT+Transformer, m6 = ViT+GePpeTto
- All encoders frozen

**If asked**: "Why frozen?" → "Three reasons. Comparison fairness —
same encoder features for all decoders. Compute — Kaggle's free tier
caps us at 12 hours per kernel; fine-tuning would multiply that.
Risk — small dataset, large encoders; fine-tuning ResNet on 18,000
captions is a recipe for overfitting."

**If asked**: "GePpeTto — what is it?" → "It's an Italian GPT-2,
released by Lorenzo De Mattei. It's a 117 million parameter language
model pretrained on a large Italian corpus. Using it gives our decoder
a head start — it already knows Italian grammar, vocabulary, common
sentence structures."

**Transition**: "Briefly, here are the architectures visually."

---

### Slide 15 — Architecture schematics (90 s)

**On screen**: Three small block diagrams side-by-side. Each shows
encoder + decoder, with snowflake icons on frozen blocks.

**What to say**:

"The structure is the same for all three. Two images come in — fetta
and grana. They go through the frozen encoder. The encoder produces
visual features. Those features get projected — that's the only
trainable interface between encoder and decoder. Then the decoder
generates the caption token by token.

The differences are inside the blocks. m1's encoder is ResNet, which
outputs a single global feature vector per image. m3 and m6 use ViT,
which outputs patch-level features — 196 tokens for a 224×224 image
at patch size 16. That difference in feature granularity is going to
matter a lot in the results.

m1 and m3's decoders are trained from scratch. m6's decoder is
GePpeTto, with weights initialized from the public checkpoint."

**Transition**: "Training was identical across the three — same data,
same setup."

---

### Slide 16 — Training setup (90 s)

**On screen**: Training hyperparameter table — epochs / batch / LR per
model.

**What to say**:

"Each model trained with its own hyperparameters but the same
training discipline — same data, same splits, same evaluation, same
metrics, same early stopping rule.

m1 — 50 epochs, batch 32, learning rate 3e-4, StepLR schedule. It's
the smallest model so it can afford larger batches.

m3 — 30 epochs, batch 16, LR 1e-4, cosine schedule. Smaller batch
because the Transformer decoder needs more memory.

m6 — 20 epochs, batch 8, LR 5e-5, cosine schedule. GePpeTto is 117M
parameters, so we use the smallest batch and lowest learning rate to
avoid disrupting the pretrained weights.

Early stopping with patience 5 to 7 on validation loss. Decoding at
inference is nucleus sampling — top-p 0.9, temperature 0.7 — chosen
because beam search on small datasets tends to collapse onto the
modal caption, which inflates BLEU but hides the model's actual
behavior.

We didn't do hyperparameter sweeps. These are reasonable defaults
appropriate to each architecture's capacity. The point of the project
is the comparison, not the absolute numbers."

**Numbers to know cold**:
- Nucleus sampling, p=0.9, T=0.7
- No hyperparameter tuning

**Transition**: "One last thing about how the experiments were set up."

---

### Slide 17 — Global vs per-attribute (60 s)

**On screen**: Two columns — global setup vs per-attribute setup.

**What to say**:

"There are two natural ways to set up this captioning task. You can
train one *global* model that handles all seven attributes pooled
together — the model gets a cheese image and an attribute name as
input and has to produce a caption. Or you can train one *per-attribute*
model — a separate model for each of the seven attributes.

Per-attribute is what the supervisor asked us to focus on, and it's
where most of the analysis is. But we also have global numbers from
an earlier wave of the project. Both will appear in the results — I'll
show you the per-attribute table first because it's the main
deliverable, and then briefly compare to global at the end."

**Transition**: "OK — results."

---

## SECTION 4 — Results & observations (slides 18-21, 5 minutes)

### Slide 18 — BLEU-4 per attribute (90 s)

**On screen**: Grouped bar chart — 7 attribute groups along the
x-axis, 4 bars per group (m1, m3, m6, most-frequent baseline). Y-axis
BLEU-4 in 0 to 0.5 range.

**What to say**:

"This is BLEU-4 per attribute — the standard captioning metric. Each
group on the x-axis is one of the seven attributes. The first three
bars in each group are the three trained models — m1, m3, m6. The
fourth bar is the most-frequent baseline — that's the model I
mentioned that just emits the modal caption every time.

Two things to look at.

First — the trained models clearly beat the modal baseline on four
attributes. Look at Struttura della Pasta on the right — the trained
models are up around 0.34, the baseline is down at 0.22. That's a
gap of more than 0.12 BLEU-4. Profumo, Texture, and Colore della
Pasta also show clear gains.

Second — on three attributes, the trained models tie or slightly lose
to the modal baseline. Aroma, Sapore, Spessore della Crosta. These
are exactly the attributes where the modal-caption share is high — go
back to the diversity table I showed earlier — Spessore was 18.4%.
On those attributes, the modal-caption strategy is essentially
impossible to beat on BLEU, because the metric rewards repeating
short common phrases.

So already, BLEU is doing two things at once — measuring whether the
model produces captioning-like output, and measuring whether the
output happens to match the modal answer. That conflation is going
to bite us. Let me show the more interesting analysis."

**Numbers to know cold**:
- Trained models beat baseline on 4 of 7 attributes
- Biggest gap: Struttura della Pasta, +0.128 BLEU-4
- Spessore is the attribute where baseline wins

**Transition**: "So we needed a different question. Not 'is the model
caption similar to the reference?' but 'does the model use the image at
all?'"

---

### Slide 19 — Shuffle test (2 minutes) — CENTERPIECE

**On screen**: Top half — text explanation of the shuffle test in 4
lines. Bottom half — grouped bar chart of z-scores, 7 attribute
groups × 3 models, with a horizontal red line at z=3.

**What to say**:

"Here's the question I actually wanted to answer. Is the model using
the image, or is it just producing captions from the distribution
without looking at the input?

The test is simple. For each model and each attribute, I have a list
of (prediction, reference) pairs from the test set. Compute the
token-overlap score between paired predictions and references. Then
randomly shuffle the predictions across the test rows — destroying
the alignment between prediction-for-image-i and reference-for-image-i.
Recompute the overlap. Repeat the shuffle 100 times to get a
distribution.

If the model is image-conditioned, the paired score should be much
higher than the shuffle distribution. If the model is just producing
captions from the marginal distribution, paired and shuffled scores
should be indistinguishable. The z-score on this chart is the
paired-versus-shuffled-mean difference in standard deviations.
A z above 3 means strong evidence the image is being used. A z near
zero means the image doesn't matter.

Now look at the chart. The pattern is striking.

m1 — the CNN-plus-LSTM model — has z near zero on every single
attribute. It's not using the image. Anywhere. The first model — the
classical captioning baseline — is, on this dataset, a pure language
model. It produces captions from the marginal distribution and
ignores the visual encoder.

m3 and m6 — both ViT-based — have z above 3 on four out of seven
attributes. Strong image-conditioning. Marginal on a couple more.
And both of them fail on Aroma — exactly the attribute where the
image can't possibly help, because it describes a smell.

So we have a clean architectural finding. The encoder choice is what
determines whether the model uses the image. The decoder choice
doesn't seem to matter — m3 with a from-scratch Transformer and m6
with a pretrained Italian GPT-2 behave essentially the same way. The
ResNet versus ViT switch is the binary gate."

**Numbers to know cold**:
- m1 z near 0 everywhere
- m3 / m6 z > 3 on 4 of 7 attributes
- Both ViT models fail on Aroma — the attribute where image can't help
- z > 3 ≈ p < 0.001

**If asked**: "Why is ViT better than ResNet here?" → "Two hypotheses.
One — ViT outputs patch-level features (196 tokens), while ResNet-50
outputs a single global pooled vector — so the decoder gets much
finer-grained spatial information. Two — ViT was pretrained on a
larger and more diverse dataset (JFT-300M for some checkpoints), so
its features may transfer better to non-ImageNet domains like cheese
surfaces. We didn't disambiguate these in this work."

**If asked**: "Would fine-tuning ResNet make m1 image-conditioned?" →
"Plausible, and we recommended this as the single most informative
follow-up experiment. If fine-tuning the ResNet encoder is enough to
move m1's z-score off zero, that confirms the bottleneck is in the
features, not in the LSTM decoder."

**Transition**: "Let me show you what the captions actually look
like, so the numbers have some qualitative texture."

---

### Slide 20 — Architectural takeaway (90 s)

**On screen**: Three big bullets:
1. **The encoder, not the decoder, is the binary gate.**
2. **m1 never uses the image. m3 and m6 use it on most attributes.**
3. **Aroma is the only attribute everyone fails on — consistent with smell not being in pixels.**

**What to say**:

"So the three-line summary of this comparison.

One — the encoder is the binary gate for whether the model learns
image-conditional generation on this dataset. ResNet-50 features are
not informative enough; ViT features are. The decoder doesn't change
that — m3 with a from-scratch Transformer and m6 with a pretrained
Italian LM both behave the same way on this axis.

Two — m1 never uses the image. m3 and m6 do use it, strongly, on
about four of the seven attributes.

Three — the only attribute where every model fails is Aroma — and
that's exactly the attribute where the image can't possibly help. So
the failures align with the structure of the data, which is a good
sanity check.

This is the substantive finding from the project. Not 'model X is the
best by 0.02 BLEU-4' — that's noise — but 'here are three
architecturally diverse models, and here is what each of them
actually learns to do.'"

**Transition**: "Quick look at the captions themselves."

---

### Slide 21 — Sample predictions (60 s)

**On screen**: 4-6 prediction/reference pairs picked from the report
§8. Mix of exact-match, reasonable-but-wrong, mode-collapse.

**What to say**:

"Three quick examples of what the model output actually looks like.

Top — for a Spessore della Crosta sample, the model predicts 'La
crosta del formaggio è mediamente spessa' and the panelist wrote the
same thing. Exact match.

Middle — for Colore della Pasta, the model predicts 'di colore giallo
carico omogeneo' and the reference is 'di colore giallo troppo
carico.' Similar but not identical — the model is in the right space
but didn't pick the exact word.

Bottom — for Aroma, the model predicts 'di sapone' multiple times
across different cheeses. Mode collapse. The Aroma model has fallen
back to a few favorite descriptors that it emits regardless of input
— which makes sense given the shuffle test told us this model isn't
image-conditioned.

So the captions are fluent — that's the Italian language model doing
its job. The failure mode is not 'broken language.' It's
'reasonable-looking caption but not the right one.'"

**Transition**: "Final slide."

---

## SECTION 5 — Conclusions (slide 22, 1 minute)

### Slide 22 — Takeaways (60 s)

**On screen**: Three big bullets:
1. **Encoder choice gates image-conditioning** (ResNet doesn't, ViT does).
2. **Trained models beat the most-frequent baseline on 4 of 7 attributes**, biggest gain on the most diverse attribute (Struttura).
3. **BLEU is misleading on this dataset** — the shuffle test is the more informative measurement.

Footer: "Both steps of the assignment — Step 1 cleaning, Step 2 method
comparison — are fully satisfied."

**What to say**:

"To summarize. Three things to take away.

First, the substantive finding — on this dataset, the encoder choice
gates whether the model learns image-conditional generation. ResNet-50
features don't carry enough signal; ViT features do. The decoder
choice matters much less.

Second, on the practical comparison — trained models clearly beat the
most-frequent baseline on four out of seven attributes. The biggest
gain is on the attribute with the most diverse caption distribution
— Struttura della Pasta. The attributes where models *don't* beat the
baseline are exactly the attributes where the most-frequent caption
covers a large share of the test set — so BLEU's preference for
common phrases swamps the model's actual contribution.

Third, methodologically — BLEU is a poor metric for this dataset.
The shuffle test is the more informative single result, because it
asks whether the model uses the image rather than whether the output
string matches one panelist's specific words. We recommend including
both for any follow-up work.

Both steps of the assignment are addressed — step 1, the caption
cleaning pipeline, is documented; step 2, the comparison of three
conceptually-different methods, is reported across all seven
attributes plus the global pooled setting.

Thanks. Questions?"

**Numbers to keep ready for Q&A**:
- 0.128 BLEU-4 gap on Struttura della Pasta
- z > 3 threshold for image-conditioning
- 4 of 7 attributes where trained models beat baseline
- 4 of 7 attributes where ViT-based models are image-conditioned

---

## Q&A — anticipated questions and short answers

**Q: Why didn't you fine-tune the encoders?**
A: Three reasons. One — comparison fairness; same encoder features for
all decoders makes the comparison clean. Two — Kaggle's free tier
caps us at 12 hours per kernel; fine-tuning multiplies that. Three —
small dataset, large encoders; fine-tuning a ResNet on 18,000
captions is a recipe for overfitting. That said, fine-tuning ResNet
in m1 would be the single most informative follow-up — if it shifts
m1's shuffle z off zero, the bottleneck is the features, not the
decoder.

**Q: BLEU isn't a great metric — did you try anything else?**
A: We computed METEOR and ROUGE-L as well; they tell a similar story.
The really right metric for this task would be CLIPScore — measure
cosine similarity between prediction and image in a CLIP embedding
space. That bypasses the single-reference-BLEU problem. We didn't
implement it for this report; it's the single most useful follow-up
we'd recommend.

**Q: How do you know the shuffle test isn't just noise?**
A: We computed 100 shuffles per (model, attribute) and took the
z-score. A z above 3 corresponds to p < 0.001 one-tailed. The
attributes where m3 and m6 score z > 5 — Colore, Struttura — are
well past any reasonable noise threshold.

**Q: Why does m1 fail and m3 succeed even though both use
from-scratch decoders?**
A: The only difference between m1 and m3 is the encoder — ResNet-50
versus ViT-B/16. So the answer has to be in the encoder. ResNet-50
outputs a single global feature vector; ViT outputs 196 patch-level
features. The decoder in m1 has less information to work with. Also,
ViT was trained on a more diverse dataset, so its features may
transfer better to a domain like cheese surfaces.

**Q: How much manual work went into the caption cleaning?**
A: For each of the seven attributes, we have an LLM-assisted rewrite
pass and a manual review file. The review files contain hand-edits
where the LLM got something wrong — proper nouns, ambiguous synonyms,
panelist-specific terminology.

**Q: Why didn't you address the colored-spots issue from the brief?**
A: Time constraint — the per-attribute training and analysis took
priority. It's listed in the report as a known limitation. Removing
spots would be a half-day preprocessing pass.

**Q: What would you do with another month?**
A: Three things, in order. One — fine-tune the m1 encoder to test
the encoder-is-the-bottleneck hypothesis directly. Two — add CLIPScore
so we can score predictions against images, not just one panelist's
caption. Three — go back to the brief's colored-spots concern with a
proper masking pass and re-run on one or two attributes to check
whether spots were a confound.

---

## Notes on delivery

- **Pace**: aim for around 130-140 words per minute on the dense
  slides, 100-110 on the high-information ones (slides 9, 19).
  The script above is sized for that.
- **Eye contact**: the data section (slides 3-13) is where you can
  spend the most eye-contact time with the audience — there are few
  numbers to read off the slides and lots of context to convey.
  Slide 14 onward gets denser, you can look at the screen more.
- **The two most important transitions**:
  - End of slide 13 → "OK, that's the data. Now the models." — pause
    here to let the audience digest the visible-vs-not-visible
    distinction before introducing architectures.
  - End of slide 18 → "So we needed a different question." — this is
    where you pivot from BLEU to the shuffle test. The pivot is the
    intellectual move that makes the rest of the talk work.
- **If you run long**: cut slide 11 (split details) and the second
  half of slide 12 (the talk-track about images you can see). Don't
  cut anything in slides 7, 9, 13, 18, 19, 20 — those are
  load-bearing.
- **If you run short**: spend more time on slide 19 (the shuffle test
  chart) explaining the method, or take one more pass through slide
  9's diversity table. Both can absorb 60-90 extra seconds without
  feeling padded.
