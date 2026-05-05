"""Six captioning architectures across two paradigms (from-scratch vs
pretrained Italian LM as decoder), each runnable frozen or fine-tuned.

  Family A — decoder trained from scratch:
    m1   ResNet-50 (global pooled) + LSTM         classical RNN baseline
    m2   ResNet-50 (spatial)       + Transformer  modern attention decoder
    m3   ViT-B/16                  + Transformer  transformer-everywhere

  Family B — decoder = pretrained Italian GPT-2 (GePpeTto), prefix tuning:
    m4   ResNet-50 (global pooled) + GePpeTto
    m5   ResNet-50 (spatial)       + GePpeTto
    m6   ViT-B/16                  + GePpeTto

Each takes paired Fetta + Grana views; encoders concatenate visual tokens
along the sequence dimension before passing to the decoder.

Each architecture can be trained two ways via `--finetune`:
  - frozen encoder (default): only the decoder + projection train
  - end-to-end fine-tune: encoder unfrozen with differential LR

So 6 architectures × 2 modes = 12 model runs total.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from training.encoders import CNNEncoderGlobal, CNNEncoderSpatial, ViTEncoder
from training.decoders import LSTMDecoder, TransformerDecoder, GePpeTtoDecoder


class CnnLstm(nn.Module):
    """M1: CNN encoder globale + LSTM decoder."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        self.encoder = CNNEncoderGlobal()
        self.decoder = LSTMDecoder(vocab_size=vocab_size)

    def unfreeze_encoder(self) -> None:
        self.encoder.unfreeze_encoder()

    def forward(self, fetta, grana, captions):
        visual = self.encoder(fetta, grana)
        return self.decoder(visual, captions)


class CnnTransformer(nn.Module):
    """M2: CNN encoder spaziale + Transformer decoder."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        self.encoder = CNNEncoderSpatial()
        self.decoder = TransformerDecoder(vocab_size=vocab_size, n_visual_tokens=98)

    def unfreeze_encoder(self) -> None:
        self.encoder.unfreeze_encoder()

    def forward(self, fetta, grana, captions):
        visual = self.encoder(fetta, grana)
        return self.decoder(visual, captions)


class ViTTransformer(nn.Module):
    """M3: ViT encoder + Transformer decoder."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        self.encoder = ViTEncoder()
        self.decoder = TransformerDecoder(vocab_size=vocab_size, n_visual_tokens=392)

    def unfreeze_encoder(self) -> None:
        self.encoder.unfreeze_encoder()

    def forward(self, fetta, grana, captions):
        visual = self.encoder(fetta, grana)
        return self.decoder(visual, captions)


class CnnGpt(nn.Module):
    """m4: CNN encoder globale + GePpeTto (Italian GPT-2) prefix tuning."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        self.encoder = CNNEncoderGlobal()
        self.decoder = GePpeTtoDecoder(vocab_size=vocab_size)

    def unfreeze_encoder(self) -> None:
        self.encoder.unfreeze_encoder()

    def forward(self, fetta, grana, captions):
        visual = self.encoder(fetta, grana)
        return self.decoder(visual, captions)


class CnnSpatialGpt(nn.Module):
    """m5: CNN encoder spaziale + GePpeTto."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        self.encoder = CNNEncoderSpatial()
        self.decoder = GePpeTtoDecoder(vocab_size=vocab_size)

    def unfreeze_encoder(self) -> None:
        self.encoder.unfreeze_encoder()

    def forward(self, fetta, grana, captions):
        visual = self.encoder(fetta, grana)
        return self.decoder(visual, captions)


class ViTGpt(nn.Module):
    """m6: ViT encoder + GePpeTto."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        self.encoder = ViTEncoder()
        self.decoder = GePpeTtoDecoder(vocab_size=vocab_size)

    def unfreeze_encoder(self) -> None:
        self.encoder.unfreeze_encoder()

    def forward(self, fetta, grana, captions):
        visual = self.encoder(fetta, grana)
        return self.decoder(visual, captions)


def build_model(model_name: str, vocab_size: int, device: torch.device) -> nn.Module:
    mapping = {
        "m1": CnnLstm,
        "m2": CnnTransformer,
        "m3": ViTTransformer,
        "m4": CnnGpt,
        "m5": CnnSpatialGpt,
        "m6": ViTGpt,
    }
    if model_name not in mapping:
        raise ValueError(f"Unknown model {model_name!r}; choose from {list(mapping)}")
    return mapping[model_name](vocab_size=vocab_size).to(device)
