# -*- coding: utf-8 -*-
"""Genera le figure del report sulle metriche di valutazione.
Legge i dati reali da eval_metrics/metrics_summary.csv.
Output: report_latex/figures/metrics/*.pdf (vettoriali)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "eval_metrics" / "metrics_summary.csv"
OUT = Path(__file__).parent / "figures" / "metrics"
OUT.mkdir(parents=True, exist_ok=True)

# ---------- stile coerente con figures.py ----------
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "figure.dpi": 150,
})

C_PRIM = "#2C5F8A"
C_M1   = "#E07A5F"
C_M3   = "#3D7068"
C_M6   = "#8A5082"
C_BASE = "#9AA0A6"
C_GOLD = "#E0A458"
C_GREEN= "#5B8C5A"
C_RED  = "#C1492E"

ATTR_SHORT = {
    "Aroma": "Aroma", "Profumo": "Profumo", "Sapore": "Sapore",
    "Texture": "Texture", "Colore_della_Pasta": "Colore",
    "Struttura_della_Pasta": "Struttura", "Spessore_della_Crosta": "Spessore",
}
# Attributi visibili dall'immagine vs non visibili (olfatto/gusto)
VISIBLE = {"Texture", "Colore_della_Pasta", "Struttura_della_Pasta"}
PARTIAL = {"Spessore_della_Crosta"}
PERATTR = list(ATTR_SHORT.keys())


def load():
    df = pd.read_csv(CSV)
    parts = df["file"].str.split("/")
    df["model"] = parts.apply(lambda p: p[2] if p[1] == "baselines" else p[1])
    df["attr"] = parts.apply(lambda p: p[-1])
    return df


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("scritto", name)


# ============================================================
# M1 — CLIPScore medio per modello (il finding "trained ~ baseline")
# ============================================================
def fig_clip_models(df):
    order = ["most_frequent", "freq_weighted", "m1_cnn_lstm",
             "m3_vit_transformer", "m6_vit_gpt"]
    labels = ["most_frequent\n(costante)", "freq_weighted", "m1\n(CNN+LSTM)",
              "m3\n(ViT+Transf.)", "m6\n(ViT+GePpeTto)"]
    cols = [C_BASE, "#B5BBC2", C_M1, C_M3, C_M6]
    pa = df[df["attr"].isin(PERATTR)]
    means = [pa[pa["model"] == m]["clip_score"].mean() for m in order]

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bars = ax.bar(labels, means, color=cols, alpha=0.92, width=0.62)
    for b, v in zip(bars, means):
        ax.text(b.get_x() + b.get_width()/2, v + 0.0008, f"{v:.4f}",
                ha="center", fontsize=9, fontweight="bold")
    # banda di rumore attorno alla media generale
    gm = np.mean(means)
    ax.axhline(gm, color=C_RED, lw=1.2, ls="--", alpha=0.8)
    ax.text(4.4, gm + 0.0006, f"media {gm:.3f}", color=C_RED, fontsize=8, ha="right")
    ax.set_ylabel("CLIPScore medio (7 attributi)")
    ax.set_title("CLIPScore: i modelli addestrati NON battono la baseline costante")
    ax.set_ylim(0.185, 0.196)
    save(fig, "m_clip_models")


# ============================================================
# M2 — CLIPScore per attributo: visibile vs non visibile
# ============================================================
def fig_clip_attr(df):
    # media su tutti i modelli/baseline per ciascun attributo
    vals = {a: df[df["attr"] == a]["clip_score"].mean() for a in PERATTR}
    order = sorted(PERATTR, key=lambda a: vals[a], reverse=True)
    labels = [ATTR_SHORT[a] for a in order]
    heights = [vals[a] for a in order]
    cols = []
    for a in order:
        if a in VISIBLE:
            cols.append(C_GREEN)
        elif a in PARTIAL:
            cols.append(C_GOLD)
        else:
            cols.append(C_BASE)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bars = ax.bar(labels, heights, color=cols, alpha=0.92, width=0.64)
    for b, v in zip(bars, heights):
        ax.text(b.get_x() + b.get_width()/2, v + 0.0008, f"{v:.3f}",
                ha="center", fontsize=8.5, fontweight="bold")
    # legenda manuale
    from matplotlib.patches import Patch
    leg = [Patch(facecolor=C_GREEN, label="Visibile (aspetto pasta)"),
           Patch(facecolor=C_GOLD, label="Parz. visibile (crosta)"),
           Patch(facecolor=C_BASE, label="Non visibile (olfatto/gusto)")]
    ax.legend(handles=leg, frameon=False, fontsize=8, loc="upper right")
    ax.set_ylabel("CLIPScore medio")
    ax.set_title("CLIPScore separa attributi visibili da non visibili")
    ax.set_ylim(0.17, 0.215)
    save(fig, "m_clip_attr")


# ============================================================
# M3 — CIDEr per attributo: dove BLEU appiattisce, CIDEr separa
# ============================================================
def fig_cider_attr(df):
    order = ["Aroma", "Profumo", "Sapore", "Texture",
             "Spessore_della_Crosta", "Struttura_della_Pasta", "Colore_della_Pasta"]
    labels = [ATTR_SHORT[a] for a in order]
    models = [("m1_cnn_lstm", C_M1, "m1"), ("m3_vit_transformer", C_M3, "m3"),
              ("m6_vit_gpt", C_M6, "m6"), ("most_frequent", C_BASE, "most_frequent")]
    x = np.arange(len(order))
    w = 0.2
    fig, ax = plt.subplots(figsize=(7.6, 3.7))
    for i, (m, c, lab) in enumerate(models):
        vals = [df[(df["model"] == m) & (df["attr"] == a)]["cider"].mean() for a in order]
        ax.bar(x + (i - 1.5) * w, vals, w, label=lab, color=c)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("CIDEr")
    ax.set_title("CIDEr per attributo: discrimina i modelli (vs BLEU-4 piatto)")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left")
    save(fig, "m_cider_attr")


# ============================================================
# M4 — Il tranello di BLEU: BLEU-1 alto, CLIPScore piatto (most_frequent vs m6)
# ============================================================
def fig_bleu_trap(df):
    order = ["Aroma", "Profumo", "Sapore", "Texture",
             "Spessore_della_Crosta", "Struttura_della_Pasta", "Colore_della_Pasta"]
    labels = [ATTR_SHORT[a] for a in order]
    x = np.arange(len(order))
    mf_b1 = [df[(df["model"] == "most_frequent") & (df["attr"] == a)]["bleu1"].mean() for a in order]
    m6_b1 = [df[(df["model"] == "m6_vit_gpt") & (df["attr"] == a)]["bleu1"].mean() for a in order]
    mf_cl = [df[(df["model"] == "most_frequent") & (df["attr"] == a)]["clip_score"].mean() for a in order]
    m6_cl = [df[(df["model"] == "m6_vit_gpt") & (df["attr"] == a)]["clip_score"].mean() for a in order]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.8, 3.4))
    w = 0.38
    a1.bar(x - w/2, mf_b1, w, label="most_frequent", color=C_BASE)
    a1.bar(x + w/2, m6_b1, w, label="m6", color=C_M6)
    a1.set_xticks(x); a1.set_xticklabels(labels, fontsize=7, rotation=35, ha="right")
    a1.set_ylabel("BLEU-1"); a1.set_title("BLEU-1: la costante VINCE")
    a1.legend(frameon=False, fontsize=8)
    a1.set_ylim(0, 1.0)

    a2.bar(x - w/2, mf_cl, w, label="most_frequent", color=C_BASE)
    a2.bar(x + w/2, m6_cl, w, label="m6", color=C_M6)
    a2.set_xticks(x); a2.set_xticklabels(labels, fontsize=7, rotation=35, ha="right")
    a2.set_ylabel("CLIPScore"); a2.set_title("CLIPScore: praticamente UGUALI")
    a2.legend(frameon=False, fontsize=8)
    a2.set_ylim(0, 0.24)
    save(fig, "m_bleu_trap")


# ============================================================
# M5 — Heatmap fingerprint: tutte le metriche per m6, per attributo
# ============================================================
def fig_heatmap(df):
    order = ["Aroma", "Profumo", "Sapore", "Spessore_della_Crosta",
             "Texture", "Struttura_della_Pasta", "Colore_della_Pasta"]
    labels = [ATTR_SHORT[a] for a in order]
    cols = ["bleu1", "bleu4", "meteor", "rouge_l", "cider", "bertscore_f",
            "vocab_conf", "clip_score"]
    col_lab = ["BLEU-1", "BLEU-4", "METEOR", "ROUGE-L", "CIDEr",
               "BERT-F", "Vocab", "CLIP"]
    m6 = df[df["model"] == "m6_vit_gpt"].set_index("attr")
    raw = np.array([[m6.loc[a, c] for c in cols] for a in order])
    # normalizzazione per colonna (min-max) per rendere comparabili le scale
    norm = (raw - raw.min(0)) / (raw.max(0) - raw.min(0) + 1e-9)

    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    im = ax.imshow(norm, cmap="YlGnBu", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(col_lab, fontsize=8.5)
    ax.set_yticks(range(len(order))); ax.set_yticklabels(labels, fontsize=9)
    for i in range(raw.shape[0]):
        for j in range(raw.shape[1]):
            ax.text(j, i, f"{raw[i, j]:.2f}", ha="center", va="center",
                    fontsize=7.5,
                    color="white" if norm[i, j] > 0.55 else "black")
    ax.set_title("Profilo di m6 per attributo (valori grezzi; colore = normalizz. per colonna)")
    ax.grid(False)
    save(fig, "m_heatmap")


if __name__ == "__main__":
    df = load()
    fig_clip_models(df)
    fig_clip_attr(df)
    fig_cider_attr(df)
    fig_bleu_trap(df)
    fig_heatmap(df)
    print("TUTTE le figure metriche generate in", OUT)
