# src/models/metrics.py
from __future__ import annotations
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
import evaluate as hf_evaluate
from torch.utils.data import DataLoader


def generate_caption(
    model: nn.Module,
    fetta: torch.Tensor,
    grana: torch.Tensor,
    tokenizer,
    device: torch.device,
    beam_size: int = 1,
    max_len: int = 50,
    strategy: str = "beam",
    top_p: float = 0.9,
    temperature: float = 0.7,
) -> str:
    """Genera una caption.

    strategy:
      - "beam": beam search (beam_size=1 → greedy)
      - "nucleus": nucleus (top-p) sampling con temperature
    """
    model.eval()
    fetta = fetta.to(device)
    grana = grana.to(device)

    with torch.no_grad():
        if strategy == "nucleus":
            return _nucleus_decode(model, fetta, grana, tokenizer, device,
                                   max_len, top_p, temperature)
        if beam_size == 1:
            return _greedy_decode(model, fetta, grana, tokenizer, device, max_len)
        return _beam_search(model, fetta, grana, tokenizer, device, beam_size, max_len)


def _nucleus_decode(model, fetta, grana, tokenizer, device, max_len,
                    top_p, temperature):
    generated = [tokenizer.SOS_ID]
    for _ in range(max_len):
        inp = torch.tensor([generated], dtype=torch.long, device=device)
        logits = model(fetta, grana, inp)               # (1, t, vocab)
        logits = logits[0, -1] / temperature            # (vocab,)
        sorted_logits, sorted_idx = logits.sort(descending=True)
        cumulative_probs = sorted_logits.softmax(dim=-1).cumsum(dim=-1)
        # Remove tokens with cumulative prob above top_p (keep at least 1)
        remove_mask = cumulative_probs > top_p
        remove_mask[1:] = remove_mask[:-1].clone()
        remove_mask[0] = False
        sorted_logits[remove_mask] = float("-inf")
        probs = sorted_logits.softmax(dim=-1)
        sampled = sorted_idx[torch.multinomial(probs, 1).item()].item()
        if sampled == tokenizer.EOS_ID:
            break
        generated.append(sampled)
    return tokenizer.decode(generated[1:], skip_special=True)


def _greedy_decode(model, fetta, grana, tokenizer, device, max_len):
    generated = [tokenizer.SOS_ID]
    for _ in range(max_len):
        inp = torch.tensor([generated], dtype=torch.long, device=device)
        logits = model(fetta, grana, inp)       # (1, t, vocab)
        next_id = logits[0, -1].argmax().item()
        if next_id == tokenizer.EOS_ID:
            break
        generated.append(next_id)
    return tokenizer.decode(generated[1:], skip_special=True)


def _beam_search(model, fetta, grana, tokenizer, device, beam_size, max_len):
    # Beam search: lista di (score, token_sequence)
    beams = [(0.0, [tokenizer.SOS_ID])]
    completed = []

    for _ in range(max_len):
        candidates = []
        for score, seq in beams:
            inp = torch.tensor([seq], dtype=torch.long, device=device)
            logits = model(fetta, grana, inp)    # (1, t, vocab)
            log_probs = torch.log_softmax(logits[0, -1], dim=-1)
            topk = log_probs.topk(beam_size)
            for prob, token_id in zip(topk.values.tolist(), topk.indices.tolist()):
                new_score = score + prob
                new_seq = seq + [token_id]
                if token_id == tokenizer.EOS_ID:
                    completed.append((new_score, new_seq))
                else:
                    candidates.append((new_score, new_seq))
        if not candidates:
            break
        beams = sorted(candidates, key=lambda x: x[0], reverse=True)[:beam_size]

    if completed:
        best = max(completed, key=lambda x: x[0])
    elif beams:
        best = max(beams, key=lambda x: x[0])
    else:
        return ""

    return tokenizer.decode(best[1][1:], skip_special=True)


def quick_eval(
    model: nn.Module,
    loader: DataLoader,
    tokenizer,
    device: torch.device,
    max_samples: int = 100,
) -> float:
    """BLEU-4 rapido su un sottoinsieme del loader. Usato ogni epoca."""
    bleu_metric = hf_evaluate.load("bleu", module_type="metric")
    preds, refs = [], []
    n = 0

    model.eval()
    for batch in loader:
        fetta, grana, caps, _weights = [b.to(device) for b in batch]
        for i in range(fetta.size(0)):
            pred = generate_caption(
                model, fetta[i: i + 1], grana[i: i + 1], tokenizer, device,
                beam_size=1, max_len=50,
            )
            ref_ids = caps[i].tolist()
            ref = tokenizer.decode(ref_ids, skip_special=True)
            preds.append(pred)
            refs.append([ref])
            n += 1
            if n >= max_samples:
                break
        if n >= max_samples:
            break

    if not preds:
        return 0.0
    try:
        result = bleu_metric.compute(predictions=preds, references=refs)
        return float(result.get("bleu", 0.0))
    except Exception:
        return 0.0


def full_eval(
    model: nn.Module,
    loader: DataLoader,
    tokenizer,
    device: torch.device,
    predictions_path: Path | None = None,
    beam_size: int = 3,
    strategy: str = "beam",
    top_p: float = 0.9,
    temperature: float = 0.7,
) -> dict[str, float]:
    """BLEU-1/4, METEOR, ROUGE-L su tutto il loader. Salva predictions.csv."""
    bleu_metric = hf_evaluate.load("bleu", module_type="metric")
    meteor_metric = hf_evaluate.load("meteor", module_type="metric")
    rouge_metric = hf_evaluate.load("rouge", module_type="metric")

    preds, refs = [], []
    model.eval()

    for batch in loader:
        fetta, grana, caps, _weights = [b.to(device) for b in batch]
        for i in range(fetta.size(0)):
            pred = generate_caption(
                model, fetta[i: i + 1], grana[i: i + 1], tokenizer, device,
                beam_size=beam_size, max_len=50,
                strategy=strategy, top_p=top_p, temperature=temperature,
            )
            ref_ids = caps[i].tolist()
            ref = tokenizer.decode(ref_ids, skip_special=True)
            preds.append(pred)
            refs.append(ref)

    refs_for_bleu = [[r] for r in refs]

    results: dict[str, float] = {}
    try:
        b = bleu_metric.compute(predictions=preds, references=refs_for_bleu)
        results["bleu4"] = float(b.get("bleu", 0.0))
        precisions = b.get("precisions", [0.0, 0.0, 0.0, 0.0])
        results["bleu1"] = float(precisions[0]) if precisions else 0.0
    except Exception:
        results["bleu1"] = results["bleu4"] = 0.0

    try:
        m = meteor_metric.compute(predictions=preds, references=refs)
        results["meteor"] = float(m.get("meteor", 0.0))
    except Exception:
        results["meteor"] = 0.0

    try:
        r = rouge_metric.compute(predictions=preds, references=refs)
        results["rouge_l"] = float(r.get("rougeL", 0.0))
    except Exception:
        results["rouge_l"] = 0.0

    if predictions_path is not None:
        predictions_path = Path(predictions_path)
        predictions_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"caption_pred": preds, "caption_ref": refs}).to_csv(
            predictions_path, index=False, encoding="utf-8"
        )

    return results
