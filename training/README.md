# Step 2 — Captioning model training

Three encoder-decoder architectures for image→caption on the
Trentingrana dataset, conceptually as different as the brief asks for.

## Models — six architectures × frozen/fine-tuned + four baselines

The brief asks for **three different methods conceptually as different
as possible**. We run six architectures in two paradigm families, each
in frozen-encoder and fine-tuned-encoder mode, plus four non-trained
baselines. **12 trained model runs + 4 baseline runs = 16 comparison
points.**

### Trained models

**Family A — decoder trained from scratch:**

| ID | encoder | decoder |
|---|---|---|
| **m1** | ResNet-50 (global, 1 token × 2 = 2) | LSTM |
| **m2** | ResNet-50 (spatial 7×7, 49 × 2 = 98) | Transformer |
| **m3** | ViT-B/16 (196 patches × 2 = 392) | Transformer |

**Family B — decoder is pretrained Italian GPT-2 (GePpeTto), prefix-tuned:**

| ID | encoder | decoder |
|---|---|---|
| **m4** | ResNet-50 (global) | GePpeTto |
| **m5** | ResNet-50 (spatial) | GePpeTto |
| **m6** | ViT-B/16 | GePpeTto |

Each architecture in two modes:
- **frozen** (default): only decoder + projection train
- **fine-tune** (`--finetune`): encoder unfrozen with differential LR

So 6 architectures × 2 modes = **12 trained model runs**.

### Baselines (no training)

| name | what it does |
|---|---|
| **random** | random training caption per test row |
| **most_frequent** | always the most common training caption |
| **freq_weighted** | sample training captions weighted by frequency |
| **retrieval** | nearest-neighbor by ResNet-50 visual features (excludes same `sample_id` to avoid panelist leak) |

All take **paired Fetta + Grana** views per sample (98.5% of our
wheel-photo positions have both). For the 1.5% missing one view, the
dataset substitutes a zero tensor.

## Where this trains

**Training runs on Kaggle, not locally.** Local install is not needed.

The training code is fully relative-pathed so the same scripts work on
any machine. On Kaggle, the typical setup is to clone this repo into
`/kaggle/working/cheese/` and symlink `/kaggle/input/<dataset>/data`
to `/kaggle/working/cheese/data`.

`training/kaggle_run.py` automates that — see below.

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

### 2. Train (one model at a time)

```bash
# Train one model — m1 frozen on a single attribute
python -m training.cli --model m1 --attributo Texture

# Train globally across all attributes (uses [Attributo] token)
python -m training.cli --model m3 --attributo all

# Compact caption form instead of full sentence
python -m training.cli --model m3 --attributo Profumo --caption-column caption

# Fine-tune (unfreeze encoder)
python -m training.cli --model m2 --attributo all --finetune

# Resume / eval-only
python -m training.cli --model m1 --attributo Texture --resume
python -m training.cli --model m1 --attributo Texture --eval-only
```

### 2b. Run baselines

```bash
python -m training.run_baselines --attributo all
python -m training.run_baselines --attributo Texture --baselines retrieval
```

### 2c. Run a named chunk on Kaggle

`training/chunks.py` defines named chunks sized to fit one Kaggle GPU
session (12 hours). See available chunks:

```bash
python -m training.kaggle_run --list-chunks
```

Suggested 5-session schedule:

| # | chunk | what it runs | est. hours |
|---|---|---|---:|
| 1 | `A-all` | m1, m2, m3 frozen + ft (6 runs) | ~8.3 |
| 2 | `B-frozen` | m4, m5, m6 frozen (3 runs) | ~7.0 |
| 3 | `B-ft-light` | m4, m5 fine-tuned (2 runs) | ~8.0 |
| 4 | `B-ft-heavy` | m6 fine-tuned (1 run) | ~6.0 |
| 5 | `baselines` | 4 baselines | ~0.5 |
| | | **total: 16 comparison points** | **~30 hr** |

Run a chunk:

```bash
python -m training.kaggle_run --chunk A-all --attributo all
```

Or run a custom subset (ignoring chunks):

```bash
python -m training.kaggle_run --models m3 m6 --matrix frozen --baselines none
```

## Disk hygiene on Kaggle

Kaggle's `/kaggle/working/` is ~20 GB and the kernel output gets zipped
from there. To stay under budget:

- **`last.pt` is deleted by default after each successful run.** Only
  `best.pt` is needed for evaluation; `last.pt` exists only for resuming
  an *interrupted* training. Pass `--keep-last` to keep it (e.g. you
  plan to resume in a later session).
- Per-run checkpoint sizes (just `best.pt`):
  - m1 ~30 MB
  - m2 ~80 MB
  - m3 ~360 MB
  - m4 ~480 MB
  - m5 ~480 MB
  - m6 ~810 MB
  - All 12 runs × 1 checkpoint ≈ 5 GB. Fits comfortably.
- Predictions / logs / metrics are tiny (<1 MB per run).

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

| | frozen | fine-tune (`--finetune`) |
|---|---|---|
| m1 | 50 epochs, batch 32, lr 3e-4 | 30 epochs, batch 8, lr 1e-4 |
| m2 | 50 epochs, batch 32, lr 3e-4 | 30 epochs, batch 8, lr 1e-4 |
| m3 | 30 epochs, batch 16, lr 1e-4 | 20 epochs, batch 4, lr 5e-5 |
| m4 | 30 epochs, batch 16, lr 1e-4 | 20 epochs, batch 8, lr 5e-5 |
| m5 | 30 epochs, batch 16, lr 1e-4 | 20 epochs, batch 4, lr 5e-5 |
| m6 | 20 epochs, batch 8,  lr 5e-5 | 15 epochs, batch 4, lr 2e-5 |

All defaults can be overridden via `--epochs`, `--batch-size`, `--lr`.

m4-m6 (GePpeTto variants) use **3 LR groups** (encoder slow,
GPT-2 backbone slow, projection full LR). m3 and all fine-tunes use
**2 LR groups** (encoder slow, decoder full).

## Kaggle workflow

Quick recipe for running on a Kaggle GPU kernel (T4 or better):

1. **Upload the dataset.** Treat `data/final/` and `data/images_flat/`
   as the Kaggle dataset payload. The JSON metadata is in
   `training/kaggle_dataset_metadata.json` (slug:
   `panciut/cheese-trentingrana`).

   ```bash
   # Locally, from the repo root:
   kaggle datasets create -p data/ -m "initial release"
   # or for updates:
   kaggle datasets version -p data/ -m "rerun"
   ```

2. **Add the dataset and a copy of this repo** to the Kaggle notebook.
   Either clone via `git clone https://github.com/panciut/Cheese`
   or upload the repo as a second utility dataset.

3. **In the Kaggle notebook**:

   ```python
   !cp -r /kaggle/working/Cheese /kaggle/working/cheese
   !python /kaggle/working/cheese/training/kaggle_run.py \
       --models m1 m2 m3 \
       --attributo all \
       --caption-column caption_sentence
   ```

   `kaggle_run.py` will:
   - Auto-detect the dataset under `/kaggle/input/`
   - Symlink `data/` into the project so paths resolve
   - Run `prepare_data` if the dataset CSV / splits aren't there yet
   - Train each model in turn

4. **Output**: `training/runs/<model>/<attribute>/` is written to
   `/kaggle/working/`, so it ends up in the kernel output zip
   automatically.

## Notes on the data

- 979 unique wheel-photo samples (`sample_id` =
  `<dairy>__<session_date>__P<slot><a/b>`).
- 964 with both views, 14 fetta-only, 1 grana-only.
- 18,427 training rows after bundling fetta+grana paths into one row
  per (sample, panelist, attribute).
- Splits stratified by year so 2018-2019 / 2019-2020 / 2020-2021 /
  2021-2022 are proportionally represented in train/val/test.
