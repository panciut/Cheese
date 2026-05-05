"""PyTorch Dataset for paired-view Trentingrana captioning.

Reads `data/final/dataset_captioning.csv` (produced by prepare_data.py)
and yields {fetta, grana, caption_ids, weight} per (sample, panelist,
attribute) row.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from training.vocabulary import ItalianTokenizer

ROOT = Path(__file__).resolve().parent.parent

IMAGENET_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class GranaTrentinoDataset(Dataset):
    def __init__(
        self,
        csv_path: Path,
        tokenizer: ItalianTokenizer,
        splits_path: Path,
        attributo: str | None = None,
        split: str = "train",
        require_both_views: bool = True,
        max_caption_len: int = 50,
        caption_column: str = "caption",
        transform: transforms.Compose | None = None,
    ) -> None:
        self.tokenizer = tokenizer
        self.max_caption_len = max_caption_len
        self.transform = transform or IMAGENET_TRANSFORM
        self.attributo = attributo
        self.caption_column = caption_column

        df = pd.read_csv(csv_path)
        # require at least one image
        df = df[df["has_fetta"] | df["has_grana"]].copy()
        if require_both_views:
            df = df[df["has_both_views"]].copy()

        with open(splits_path, encoding="utf-8") as f:
            splits = json.load(f)
        df = df[df["sample_id"].isin(set(splits[split]))].copy()

        if attributo is not None:
            # Vocabulary uses underscore form for special tokens
            attr_norm = attributo.replace("_", " ")
            df = df[df["attribute"] == attr_norm].copy()

        self.df = df.reset_index(drop=True)

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> dict:
        row = self.df.iloc[idx]

        fetta = self._load_image(row["fetta_path"]) if row["has_fetta"] \
            else torch.zeros(3, 224, 224)
        grana = self._load_image(row["grana_path"]) if row["has_grana"] \
            else torch.zeros(3, 224, 224)

        text = str(row[self.caption_column])
        if self.attributo is None:
            # Global model: prepend attribute token (vocab uses underscore form)
            attr_for_tok = str(row["attribute"]).replace(" ", "_")
            ids = self.tokenizer.encode(text, add_special=True, attribute=attr_for_tok)
        else:
            ids = self.tokenizer.encode(text, add_special=True)

        ids = ids[: self.max_caption_len]
        caption_tensor = torch.tensor(ids, dtype=torch.long)

        return {
            "fetta": fetta,
            "grana": grana,
            "caption": caption_tensor,
            "weight": float(row.get("weight", 1.0)),
        }

    def _load_image(self, rel_path: str) -> torch.Tensor:
        full_path = ROOT / rel_path
        img = Image.open(full_path).convert("RGB")
        return self.transform(img)
