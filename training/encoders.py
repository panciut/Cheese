from __future__ import annotations
import torch
import torch.nn as nn
from torchvision import models
import timm


class CNNEncoderGlobal(nn.Module):
    """ResNet-50 → vettore globale 2048-dim × 2 → proiezione 512. Output: (B,1,512)."""

    d_model: int = 512
    n_visual_tokens: int = 1

    def __init__(self) -> None:
        super().__init__()
        backbone = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        for p in backbone.parameters():
            p.requires_grad = False
        # Rimuovi il classificatore finale (fc layer) e avgpool → estrai fino ad avgpool
        self.backbone = nn.Sequential(*list(backbone.children())[:-1])  # fino ad avgpool incluso
        self.proj = nn.Linear(2048 * 2, self.d_model)
        self._frozen = True

    def unfreeze_encoder(self) -> None:
        for p in self.backbone.parameters():
            p.requires_grad = True
        self._frozen = False

    def forward(self, fetta: torch.Tensor, grana: torch.Tensor) -> torch.Tensor:
        if self._frozen:
            with torch.no_grad():
                f = self.backbone(fetta).flatten(1)   # (B, 2048)
                g = self.backbone(grana).flatten(1)   # (B, 2048)
        else:
            f = self.backbone(fetta).flatten(1)       # (B, 2048)
            g = self.backbone(grana).flatten(1)       # (B, 2048)
        x = torch.cat([f, g], dim=1)          # (B, 4096)
        x = self.proj(x)                       # (B, 512)
        return x.unsqueeze(1)                  # (B, 1, 512)


class CNNEncoderSpatial(nn.Module):
    """ResNet-50 → feature map 7×7 → 49 token × 2 → proiezione 512. Output: (B,98,512)."""

    d_model: int = 512
    n_visual_tokens: int = 98

    def __init__(self) -> None:
        super().__init__()
        backbone = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        for p in backbone.parameters():
            p.requires_grad = False
        # Strati fino all'ultimo layer conv (layer4), senza avgpool
        self.backbone = nn.Sequential(*list(backbone.children())[:-2])
        self.proj = nn.Linear(2048, self.d_model)
        self._frozen = True

    def unfreeze_encoder(self) -> None:
        for p in self.backbone.parameters():
            p.requires_grad = True
        self._frozen = False

    def forward(self, fetta: torch.Tensor, grana: torch.Tensor) -> torch.Tensor:
        if self._frozen:
            with torch.no_grad():
                f = self.backbone(fetta)   # (B, 2048, H, W)
                g = self.backbone(grana)   # (B, 2048, H, W)
        else:
            f = self.backbone(fetta)       # (B, 2048, H, W)
            g = self.backbone(grana)       # (B, 2048, H, W)
        B, C, H, W = f.shape
        f = f.permute(0, 2, 3, 1).reshape(B, H * W, C)  # (B, 49, 2048)
        g = g.permute(0, 2, 3, 1).reshape(B, H * W, C)  # (B, 49, 2048)
        tokens = torch.cat([f, g], dim=1)                # (B, 98, 2048)
        return self.proj(tokens)                          # (B, 98, 512)


class ViTEncoder(nn.Module):
    """ViT-B/16 → 196 patch × 2 → proiezione 512. Output: (B,392,512)."""

    d_model: int = 512
    n_visual_tokens: int = 392
    _TRAINABLE_BLOCKS = {8, 9, 10, 11}  # ultimi 4 dei 12 block ViT-B

    def __init__(self) -> None:
        super().__init__()
        self.vit = timm.create_model(
            "vit_base_patch16_224",
            pretrained=True,
            num_classes=0,       # rimuove il classificatore
            global_pool="",      # restituisce tutti i patch token (no CLS pooling)
        )
        # Congela tutti i parametri
        for p in self.vit.parameters():
            p.requires_grad = False
        # Sblocca gli ultimi 4 block
        for idx in self._TRAINABLE_BLOCKS:
            for p in self.vit.blocks[idx].parameters():
                p.requires_grad = True
        # Sblocca anche la norm finale
        for p in self.vit.norm.parameters():
            p.requires_grad = True

        self.proj = nn.Linear(768, self.d_model)
        self._frozen = True  # partial freeze — blocks 8-11 + norm already unfrozen

    def unfreeze_encoder(self) -> None:
        """Unfreeze all ViT blocks (including blocks 0-7 currently frozen)."""
        for p in self.vit.parameters():
            p.requires_grad = True
        self._frozen = False

    def _extract_patches(self, x: torch.Tensor) -> torch.Tensor:
        """Estrae i 196 patch token (escluso CLS) da un'immagine."""
        out = self.vit.forward_features(x)  # (B, 197, 768) — 1 CLS + 196 patch
        return out[:, 1:, :]               # (B, 196, 768)

    def forward(self, fetta: torch.Tensor, grana: torch.Tensor) -> torch.Tensor:
        f = self._extract_patches(fetta)         # (B, 196, 768)
        g = self._extract_patches(grana)         # (B, 196, 768)
        tokens = torch.cat([f, g], dim=1)        # (B, 392, 768)
        return self.proj(tokens)                 # (B, 392, 512)
