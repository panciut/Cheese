"""Named chunks for Kaggle session planning.

Kaggle GPU sessions cap at 12 hours and the working dir at ~20 GB.
Splitting the 12-model matrix across multiple sessions limits the
blast radius of a session timeout / OOM / crash to one chunk.

Each chunk is `(models, modes)` — `models` is a list of architecture
IDs, `modes` is a list of {"frozen", "ft"}. A chunk evaluates as
len(models) × len(modes) trained-model runs.

Estimated wall-time on a Kaggle T4 GPU (single attribute = 'all'):

    m1 frozen ≈ 30 min      m1 ft ≈ 60 min
    m2 frozen ≈ 45 min      m2 ft ≈ 90 min
    m3 frozen ≈ 90 min      m3 ft ≈ 180 min
    m4 frozen ≈ 120 min     m4 ft ≈ 240 min
    m5 frozen ≈ 120 min     m5 ft ≈ 240 min
    m6 frozen ≈ 180 min     m6 ft ≈ 360 min

Numbers are rough — actual time depends on attribute, batch size,
early-stopping behaviour. Add a 10-20% safety margin.
"""
from __future__ import annotations

CHUNKS: dict[str, dict] = {
    # ---- Subset (6 trained + 4 baselines) — RECOMMENDED for the brief ----
    # m1 / m3 / m6 cover the three conceptual axes (CNN+LSTM,
    # ViT+from-scratch-Tr, ViT+pretrained-LM). Both modes (frozen + ft).
    # Split into 2 sessions for error containment.
    "S-1": {
        "models": ["m1", "m3", "m6"],
        "modes": ["frozen"],
        "include_baselines": True,
        "estimate_hr": 5.5,
        "description": "Subset session 1 (legacy): m1+m3+m6 frozen + 4 baselines. "
                       "TIMED OUT in practice; split into S-1a + S-1v2.",
    },
    # Actual split used after S-1 hit the 12h Kaggle cap with m6 mid-training.
    "S-1a": {
        "models": ["m1", "m3"],
        "modes": ["frozen"],
        "estimate_hr": 4.5,
        "description": "Subset session 1a: m1+m3 frozen. (Already completed via S-1.)",
    },
    "S-1v2": {
        "models": ["m6"],
        "modes": ["frozen"],
        "include_baselines": True,
        "estimate_hr": 6.0,
        "description": "Subset session 1v2: m6 frozen + 4 baselines. "
                       "Re-run after S-1 timed out before m6 finished.",
    },
    "S-2": {
        "models": ["m1", "m3", "m6"],
        "modes": ["ft"],
        "estimate_hr": 10.0,
        "description": "Subset session 2 (legacy): m1+m3+m6 fine-tuned. "
                       "Tight on 12h; split into S-2a + S-2b.",
    },
    "S-2a": {
        "models": ["m1", "m3"],
        "modes": ["ft"],
        "estimate_hr": 4.0,
        "description": "Subset session 2a: m1+m3 fine-tuned.",
    },
    "S-2b": {
        "models": ["m6"],
        "modes": ["ft"],
        "estimate_hr": 7.0,
        "description": "Subset session 2b: m6 fine-tuned (heavy).",
    },

    # ---- Path A 3-session split (full 12 trained + 4 baselines) ----
    "A-1": {
        "models": ["m1", "m2", "m3", "m4", "m5", "m6"],
        "modes": ["frozen"],
        "include_baselines": True,
        "estimate_hr": 10.5,
        "description": "Path A session 1: all 6 frozen + 4 baselines.",
    },
    "A-2": {
        "models": ["m1", "m2", "m3", "m4"],
        "modes": ["ft"],
        "estimate_hr": 9.5,
        "description": "Path A session 2: m1+m2+m3+m4 fine-tuned.",
    },
    "A-3": {
        "models": ["m5", "m6"],
        "modes": ["ft"],
        "estimate_hr": 10.0,
        "description": "Path A session 3: m5+m6 fine-tuned (heavy).",
    },

    # ---- Family A — decoder from scratch ----
    "A-frozen": {
        "models": ["m1", "m2", "m3"],
        "modes": ["frozen"],
        "estimate_hr": 2.75,
        "description": "Family A frozen-encoder (m1+m2+m3). Fast.",
    },
    "A-ft": {
        "models": ["m1", "m2", "m3"],
        "modes": ["ft"],
        "estimate_hr": 5.5,
        "description": "Family A fine-tuned. Half a Kaggle session.",
    },
    "A-all": {
        "models": ["m1", "m2", "m3"],
        "modes": ["frozen", "ft"],
        "estimate_hr": 8.25,
        "description": "Family A frozen + ft (6 runs). Fits in one session.",
    },

    # ---- Family B — pretrained Italian LM ----
    "B-frozen": {
        "models": ["m4", "m5", "m6"],
        "modes": ["frozen"],
        "estimate_hr": 7.0,
        "description": "Family B frozen-encoder (m4+m5+m6). One session.",
    },
    "B-ft-light": {
        "models": ["m4", "m5"],
        "modes": ["ft"],
        "estimate_hr": 8.0,
        "description": "Family B fine-tuned, CNN-encoder variants only. One session.",
    },
    "B-ft-heavy": {
        "models": ["m6"],
        "modes": ["ft"],
        "estimate_hr": 6.0,
        "description": "Family B fine-tuned, ViT encoder. One session.",
    },

    # ---- Convenience: each architecture in isolation ----
    "m1": {"models": ["m1"], "modes": ["frozen", "ft"], "estimate_hr": 1.5,
           "description": "m1 frozen + ft."},
    "m2": {"models": ["m2"], "modes": ["frozen", "ft"], "estimate_hr": 2.25,
           "description": "m2 frozen + ft."},
    "m3": {"models": ["m3"], "modes": ["frozen", "ft"], "estimate_hr": 4.5,
           "description": "m3 frozen + ft."},
    "m4": {"models": ["m4"], "modes": ["frozen", "ft"], "estimate_hr": 6.0,
           "description": "m4 frozen + ft."},
    "m5": {"models": ["m5"], "modes": ["frozen", "ft"], "estimate_hr": 6.0,
           "description": "m5 frozen + ft."},
    "m6": {"models": ["m6"], "modes": ["frozen", "ft"], "estimate_hr": 9.0,
           "description": "m6 frozen + ft. Tight on a 12-hr session."},

    # ---- Frozen-only and ft-only sweeps ----
    "frozen-all": {
        "models": ["m1", "m2", "m3", "m4", "m5", "m6"],
        "modes": ["frozen"],
        "estimate_hr": 9.75,
        "description": "All 6 archs frozen-encoder. ~10 hrs, one Kaggle session.",
    },
    "ft-all": {
        "models": ["m1", "m2", "m3", "m4", "m5", "m6"],
        "modes": ["ft"],
        "estimate_hr": 19.5,
        "description": "All 6 archs fine-tuned. WILL exceed one session — split.",
    },

    # ---- Baselines (no GPU needed but keep in matrix for completeness) ----
    "baselines": {
        "models": [],
        "modes": [],
        "baselines_only": True,
        "estimate_hr": 0.5,
        "description": "Random / most_frequent / freq_weighted / retrieval baselines.",
    },
}


SUGGESTED_SCHEDULE = [
    "S-1a",  # session 1a (~4.5h): m1+m3 frozen — completed via S-1
    "S-1v2", # session 1v2 (~6h): m6 frozen + 4 baselines — re-run after S-1 timeout
    "S-2a",  # session 2a (~4h): m1+m3 fine-tuned
    "S-2b",  # session 2b (~7h): m6 fine-tuned
]


def list_chunks() -> str:
    lines = [
        f"{'chunk':18s}  {'models':35s}  {'modes':17s}  {'est':>6s}  description",
        "-" * 95,
    ]
    for name, c in CHUNKS.items():
        models = ",".join(c["models"]) or "(none)"
        modes = ",".join(c["modes"]) or "(none)"
        est = f"{c['estimate_hr']:.1f}h"
        lines.append(f"{name:18s}  {models:35s}  {modes:17s}  {est:>6s}  {c['description']}")
    lines.append("")
    lines.append("Suggested schedule (5 Kaggle sessions):")
    for i, name in enumerate(SUGGESTED_SCHEDULE, 1):
        c = CHUNKS[name]
        lines.append(f"  {i}. {name:14s} (~{c['estimate_hr']:.1f}h) — {c['description']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(list_chunks())
