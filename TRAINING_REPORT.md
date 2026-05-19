# Trentingrana captioning — training results (Path A subset, frozen encoders)

Reports the first wave of trained models and baselines run on the Kaggle
T4 setup. All numbers are on the held-out test split (2,751 rows), with
`caption_sentence` (full Italian sentence) as the training/target form.

Three trained model architectures (frozen encoder, decoder trained from
scratch / fine-tuned on top of a frozen LM):

- **m1** — ResNet-50 (frozen) + LSTM
- **m3** — ViT-B/16 (frozen) + Transformer decoder from scratch
- **m6** — ViT-B/16 (frozen) + GePpeTto Italian GPT-2

Plus four baselines:

- **random** — sample a random training caption per test row
- **most_frequent** — always emit the single most common training caption
- **freq_weighted** — sample training captions weighted by frequency
- **retrieval** — nearest-neighbour by ResNet-50 features (pending; failed
  in the current baselines kernel — see "Open items")

## Test-set metrics

| System | BLEU-4 | BLEU-1 | METEOR | ROUGE-L |
|---|---:|---:|---:|---:|
| **m1** (CNN+LSTM) | 0.1283 | 0.3501 | **0.2938** | 0.2950 |
| **m3** (ViT+Tr) | 0.1237 | 0.3649 | 0.2875 | 0.2977 |
| **m6** (ViT+GePpeTto) | **0.1307** | **0.3657** | 0.2928 | **0.3009** |
| random | 0.1238 | 0.3467 | 0.2901 | 0.2910 |
| most_frequent | 0.0782 | **0.4191** | 0.2361 | 0.2665 |
| freq_weighted | 0.1207 | 0.3383 | 0.2814 | 0.2840 |
| retrieval | _pending_ | _pending_ | _pending_ | _pending_ |

m6 test eval completed 2026-05-18 via a separate Kaggle kernel
(`marcopanciera/cheese-trentingrana-m6-eval`). The original training kernel
hit the 12h cap during eval; the eval-only kernel uses nucleus sampling
(top-p=0.9, temperature=0.7) — matching the per-attribute m6 runs for
consistency. Beam search was tried first but stalled past the 30-60 min
budget (likely no KV cache in the decoder), so was switched to nucleus.

**m6 narrowly wins on BLEU-4** (0.1307 vs m1 0.1283 vs m3 0.1237) and on
BLEU-1 and ROUGE-L. All three models cluster very tightly though — gap
between best and worst is 0.007 BLEU-4. See `TRAINING_REPORT_per_attribute.md`
for the per-attribute breakdown and the shuffle-test image-conditioning
analysis.

## Key observations

1. **Trained models barely beat the random baseline.** m1 vs random is
   +0.005 BLEU-4 / +0.004 METEOR. m3 vs random is essentially tied. This
   strongly suggests the captioning task is closer to a *language-model
   prior* problem than an *image-conditioning* one — the panelists tend to
   reuse a small set of phrasings, so emitting any plausible caption from
   the training distribution already gets you most of the score.

2. **most_frequent has the highest BLEU-1** (0.419) but the worst BLEU-4
   (0.078). It always emits the same caption — high unigram overlap with
   any sample whose reference uses the same opening words, no n-gram
   diversity. This is the classic "always predict the majority class"
   degenerate behaviour and tells us the scoring is sensitive to phrase
   variety, not just word-level match.

3. **m1 vs m3 is essentially a tie.** ViT+Transformer doesn't measurably
   beat CNN+LSTM in the frozen-encoder regime. Likely because both
   encoders are pre-trained on ImageNet, neither has been specialised to
   cheese, and the decoders are trained on the same (small) caption pool.
   The fine-tuning runs (S-2a/b) should be the more revealing comparison.

4. **Training curves are healthy.** m1 trained 50/50 epochs with steady
   val_loss decrease (1.84 → 1.04). m3 early-stopped at epoch 16/30
   (patience 5). m6 trained 20/20, best val_loss 1.06 at epoch 16, no
   collapse. No overfitting signatures, no NaNs.

## Are the captions sensible?

Yes — the generations are grammatical Italian and on-domain. They use the
right vocabulary (texture, aroma, profumo, crosta, pasta, occhiatura,
microocchiatura, frattura, etc.). The mismatch with references is mostly
that the model commits to *one* attribute while the reference talks about
*another* — both sides of the row are valid cheese descriptions, just
about different sensory dimensions.

Sample predictions vs references (m1):

```
pred: Il formaggio ha un profumo di latte cotto con intensità leggera.
ref:  Il formaggio ha un profumo poco intenso.

pred: Il formaggio ha un profumo di brodo di carne, latte cotto, burro fuso, nocciola e tostato.
ref:  Il formaggio ha un profumo leggero.

pred: Il formaggio ha un sapore piccante e amarognolo, salato.
ref:  La pasta del formaggio è disidratata.

pred: La pasta del formaggio è ruvida.
ref:  Il formaggio ha un aroma di dado, molto concentrato.
```

Sample predictions (m3):

```
pred: La pasta del formaggio è compromessa da fessurazioni profonde.
ref:  Il formaggio ha un profumo poco intenso.

pred: La pasta del formaggio presenta una microocchiatura abbondante.
ref:  Il formaggio ha un profumo leggero.

pred: Il formaggio ha un profumo di leggera fermentazione.
ref:  Il formaggio ha un aroma molto leggero.

pred: Il formaggio ha un profumo di intensità moderata.
ref:  Il formaggio ha un aroma di dado, molto concentrato.
```

Sample predictions (random baseline, for comparison — same images, but
caption drawn at random from the training pool):

```
pred: Il formaggio presenta una texture compatta, adesiva, poco solubile e poco friabile, poco granulosa, con pochi cristalli.
ref:  Il formaggio ha un profumo poco intenso.

pred: La pasta del formaggio non è omogenea ma granulosa, con frattura irregolare.
ref:  Il formaggio ha un sapore poco saporito ma equilibrato.
```

The trained-model captions and the random baseline are *qualitatively
similar in shape*. The trained model is slightly more attribute-coherent
(it picks something it then describes consistently), but it's not
visibly grounded to the specific cheese image.

## Open items

- **m6 test metrics** — eval kernel pushed to Kaggle; ~30 min run once
  GPU is enabled. Will add to the table when results land.
- **retrieval baseline** — missing output; the baselines kernel produced
  random / most_frequent / freq_weighted but no retrieval directory.
  Need to check the kernel log to see if it crashed or wrote elsewhere.
- **S-2a / S-2b (fine-tuning)** — not yet run. This is the regime where
  the image signal could actually matter. Expect to see a clearer
  separation from the random baseline if fine-tuning helps.

## Reproducibility

- Frozen-encoder runs: chunk `S-1` (which ran m1+m3 to completion, then
  timed out mid-m6) + chunk `S-1v2` (m6 to completion, eval interrupted).
- Baselines: chunk `baselines` on Kaggle.
- m6 eval-only: kernel `cheese-trentingrana-m6-eval` loads best.pt from
  the `cheese-trentingrana-m6-weights` dataset and re-runs the test eval.
- Decoding: nucleus sampling (top_p=0.9, T=0.7) for all trained runs
  (S-1, S-1v2, and the m6 eval-only kernel after the beam-3 attempt
  stalled past the 30-60 min budget — likely no KV cache in the
  decoder).
