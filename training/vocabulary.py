from __future__ import annotations
from transformers import AutoTokenizer

ATTRIBUTI = [
    "Texture", "Sapore", "Aroma", "Profumo",
    "Struttura_della_Pasta", "Colore_della_Pasta", "Spessore_della_Crosta",
]
_SPECIAL = ["<SOS>", "<EOS>", "<PAD>"] + [f"[{a}]" for a in ATTRIBUTI]


class ItalianTokenizer:
    """Wrapper su GePpeTto (GPT-2 italiano) con token speciali per il captioning."""

    MODEL_NAME = "LorenzoDeMattei/GePpeTto"
    SPECIAL_TOKENS: list[str] = _SPECIAL

    def __init__(self) -> None:
        self._tok = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self._tok.add_special_tokens({"additional_special_tokens": _SPECIAL})
        self.SOS_ID: int = self._tok.convert_tokens_to_ids("<SOS>")
        self.EOS_ID: int = self._tok.convert_tokens_to_ids("<EOS>")
        self.PAD_ID: int = self._tok.convert_tokens_to_ids("<PAD>")
        self.ATTR_TOKENS: dict[str, int] = {
            f"[{a}]": self._tok.convert_tokens_to_ids(f"[{a}]") for a in ATTRIBUTI
        }

    def encode(self, text: str, add_special: bool = True, attribute: str | None = None) -> list[int]:
        ids = self._tok.encode(text, add_special_tokens=False)
        if attribute is not None:
            attr_key = f"[{attribute}]"
            if attr_key not in self.ATTR_TOKENS:
                raise ValueError(f"Attributo sconosciuto: {attribute!r}. Scegli tra {list(self.ATTR_TOKENS)}")
            ids = [self.ATTR_TOKENS[attr_key]] + ids
        if add_special:
            ids = [self.SOS_ID] + ids + [self.EOS_ID]
        return ids

    def decode(self, ids: list[int], skip_special: bool = True) -> str:
        return self._tok.decode(ids, skip_special_tokens=skip_special)

    def __len__(self) -> int:
        return len(self._tok)
