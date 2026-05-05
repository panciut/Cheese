# Step 2 — Captioning model training

Three encoder-decoder architectures for image→caption on the
Trentingrana dataset, conceptually as different as the brief asks for.

## Models

| ID | encoder | decoder | output style |
|---|---|---|---|
| **m1** | ResNet-50 (global pooled, 1 token × 2 = 2 tokens) | LSTM | classical RNN baseline |
| **m2** | ResNet-50 (spatial 7×7, 49 tokens × 2 = 98 tokens) | Transformer | spatial attention decoder |
| **m3** | ViT-B/16 (196 patches × 2 = 392 tokens) | Transformer | transformer-everywhere |

All three take **paired Fetta + Grana** views per sample (98.5% of
our wheel-photo positions have both). For the 1.5% missing one view,
the dataset substitutes a zero tensor.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r training/requirements.txt
```

## Pipeline

### 1. Prepare training data (one-time)

```bash
python -m training.prepare_data
```

Reads `data/final/captions_final.csv` and produces:

- `data/final/dataset_captioning.csv` — one row per
  (sample, panelist, attribute) with paired image paths.
- `data/final/splits.json` — train/val/test by `sample_id`,
  stratified by year (70/15/15).

### 2. Train

```bash
# Train M1 on a single attribute
python -m training.cli --model m1 --attributo Texture

# Train a global model across all attributes (uses [Attributo] token)
python -m training.cli --model m2 --attributo all

# Use the compact caption form instead of full sentence
python -m training.cli --model m3 --attributo Profumo --caption-column caption

# Fine-tune the encoder end-to-end (slower, higher quality)
python -m training.cli --model m2 --attributo all --finetune

# Resume an interrupted run
python -m training.cli --model m1 --attributo Texture --resume

# Eval an already-trained model
python -m training.cli --model m1 --attributo Texture --eval-only
```

Output goes to `training/runs/<model_dir>/<attribute>/`:

- `best.pt` — best checkpoint by val loss
- `last.pt` — most recent checkpoint
- `predictions.csv` — test-set predictions
- `train_log.csv` — per-epoch metrics

### 3. Compare across models

The natural three-way comparison the brief asks for is to train
**m1, m2, m3 on the same attribute** (or on `all`) with the same
caption column, then compare:

- Test BLEU-4 / METEOR / CIDEr (in `predictions.csv` and printed at the
  end of training)
- Per-attribute breakdown if trained globally
- Inference speed per sample

Caption column choice (`caption_sentence` is default):

- `caption` — compact attribute-anchored form (`"Profumo di panna."`).
  Lower BLEU expected but better per-attribute focus.
- `caption_sentence` — full Italian sentence (`"Il formaggio ha un
  profumo di panna."`). Standard BLEU-friendly form.

### Optional 4th: GePpeTto-prefix variants

Three additional GPT-2-based variants exist in the previous version
(`../CheeseCaptioningAIFQC/src/models/models.py` — M5a, M5b, M5c).
They use a pretrained Italian GPT-2 as the decoder with prefix-
tuning. Not included in this slim pipeline; can be brought in if the
3-way comparison wants a 4th data point. Add `decoders.GePpeTtoDecoder`
import (already in `training/decoders.py`) and an analogous wrapper
class.

## Defaults

| | from-scratch | fine-tune (`--finetune`) |
|---|---|---|
| m1 | 50 epochs, batch 32, lr 3e-4 | 30 epochs, batch 8, lr 1e-4 |
| m2 | 50 epochs, batch 32, lr 3e-4 | 30 epochs, batch 8, lr 1e-4 |
| m3 | 30 epochs, batch 16, lr 1e-4 | 20 epochs, batch 4, lr 5e-5 |

All defaults can be overridden via `--epochs`, `--batch-size`, `--lr`.

## Notes on the data

- 979 unique wheel-photo samples (`sample_id` =
  `<dairy>__<session_date>__P<slot><a/b>`).
- 964 with both views, 14 fetta-only, 1 grana-only.
- 18,427 training rows after bundling fetta+grana paths into one row
  per (sample, panelist, attribute).
- Splits stratified by year so 2018-2019 / 2019-2020 / 2020-2021 /
  2021-2022 are proportionally represented in train/val/test.
