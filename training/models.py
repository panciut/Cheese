"""Three captioning architectures, conceptually different (per the brief).

  M1: ResNet-50 (global pooled) + LSTM            — classical RNN baseline
  M2: ResNet-50 (spatial) + Transformer            — modern attention decoder
  M3: ViT-B/16 + Transformer                       — transformer-everywhere

Each takes paired Fetta + Grana views; encoders concatenate visual tokens
along the sequence dimension before passing to the decoder.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from training.encoders import CNNEncoderGlobal, CNNEncoderSpatial, ViTEncoder
from training.decoders import LSTMDecoder, TransformerDecoder


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


def build_model(model_name: str, vocab_size: int, device: torch.device) -> nn.Module:
    mapping = {
        "m1": CnnLstm,
        "m2": CnnTransformer,
        "m3": ViTTransformer,
    }
    if model_name not in mapping:
        raise ValueError(f"Unknown model {model_name!r}; choose from {list(mapping)}")
    return mapping[model_name](vocab_size=vocab_size).to(device)
