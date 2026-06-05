# -*- coding: utf-8 -*-
"""Genera tutte le figure matplotlib del report LaTeX.
Dati reali verificati dai phase report e dai training report del repo.
Output: report_latex/figures/*.pdf (vettoriali)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

# ---------- stile globale ----------
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

# palette coerente
C_PRIM = "#2C5F8A"   # blu primario
C_M1   = "#E07A5F"   # terracotta
C_M3   = "#3D7068"   # teal
C_M6   = "#8A5082"   # viola
C_BASE = "#9AA0A6"   # grigio baseline
C_GOLD = "#E0A458"   # oro accento
C_GREEN= "#5B8C5A"
C_RED  = "#C1492E"

ATTRS = ["Profumo", "Aroma", "Sapore", "Texture",
         "Spessore\ndella Crosta", "Struttura\ndella Pasta", "Colore\ndella Pasta"]
ATTRS_SHORT = ["Profumo", "Aroma", "Sapore", "Texture", "Spessore", "Struttura", "Colore"]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("scritto", name)


# ============================================================
# F1 — Funnel della pipeline (conteggi righe)
# ============================================================
def fig_funnel():
    stages = [
        ("Righe unificate\n(immagine x panelista x attributo)", 51988, C_PRIM),
        ("Dopo prep deterministica\n(drop vuoti/meta/short)", 39356, C_PRIM),
        ("Target broadcast\n(dopo drop rumore)", 39280, C_GOLD),
        ("Righe finali training\n(captions_final.csv)", 38437, C_GREEN),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    maxv = stages[0][1]
    y = np.arange(len(stages))[::-1]
    for yi, (lab, val, col) in zip(y, stages):
        w = val / maxv
        ax.barh(yi, w, height=0.62, color=col, alpha=0.9)
        ax.text(w + 0.012, yi, f"{val:,}".replace(",", "."), va="center",
                ha="left", fontsize=9.5, fontweight="bold")
        ax.text(0.008, yi, lab, va="center", ha="left", fontsize=8.5, color="white")
    ax.set_xlim(0, 1.18)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.grid(False)
    ax.set_title("Flusso delle righe attraverso la pipeline (livello broadcast)")
    save(fig, "fig_funnel")


# ============================================================
# F2 — Funnel delle caption UNICHE (costo LLM)
# ============================================================
def fig_funnel_unique():
    stages = [
        ("Caption uniche\n(dedup per attributo)", 7705, C_PRIM),
        ("Inviate al LLM\n(dopo drop 16 rumore)", 7689, C_GOLD),
        ("NON_DESCRITTO post-batch", 360, C_RED),
        ("NON_DESCRITTO post-salvage", 184, C_GREEN),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    maxv = stages[0][1]
    y = np.arange(len(stages))[::-1]
    for yi, (lab, val, col) in zip(y, stages):
        w = val / maxv
        ax.barh(yi, w, height=0.6, color=col, alpha=0.9)
        ax.text(w + 0.012, yi, f"{val:,}".replace(",", "."), va="center",
                ha="left", fontsize=9.5, fontweight="bold")
        ax.text(0.008, yi, lab, va="center", ha="left", fontsize=8.5,
                color="white" if w > 0.18 else "black")
    ax.set_xlim(0, 1.15)
    ax.set_yticks([]); ax.set_xticks([]); ax.grid(False)
    ax.set_title("Compressione del lavoro LLM: dedup e gestione NON_DESCRITTO")
    save(fig, "fig_funnel_unique")


# ============================================================
# F3 — Righe preparate vs uniche per attributo (compressione dedup)
# ============================================================
def fig_dedup():
    prepared = [5798, 4213, 6350, 5431, 4071, 7546, 5947]
    unique   = [1179, 808, 1127, 1092, 639, 1676, 1184]
    x = np.arange(len(ATTRS))
    w = 0.4
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.bar(x - w/2, prepared, w, label="Righe preparate", color=C_PRIM, alpha=0.85)
    ax.bar(x + w/2, unique, w, label="Caption uniche", color=C_GOLD, alpha=0.95)
    for xi, (p, u) in enumerate(zip(prepared, unique)):
        ax.text(xi + w/2, u + 80, f"{u}", ha="center", fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(ATTRS, fontsize=8)
    ax.set_ylabel("Conteggio righe")
    ax.set_title("Deduplicazione per attributo (compressione media 5,1x)")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig_dedup")


# ============================================================
# F4 — Distribuzione bucket Spessore (qualitatizzazione misure)
# ============================================================
def fig_spessore():
    buckets = ["Molto\nsottile", "Sottile", "Media", "Spessa", "Molto\nspessa"]
    vals = [30, 160, 194, 36, 4]
    cols = ["#A7C7E7", "#6FA8DC", C_PRIM, "#1F4E6B", "#0E2D40"]
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    bars = ax.bar(buckets, vals, color=cols, alpha=0.92, width=0.66)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 3, str(v), ha="center", fontsize=9, fontweight="bold")
    ax.set_ylabel("Righe broadcast")
    ax.set_title("Qualitatizzazione misure crosta\n(424 righe numeriche -> 5 bucket)")
    ax.set_ylim(0, 215)
    save(fig, "fig_spessore")


# ============================================================
# F5 — Dimensione vocabolario controllato per attributo
# ============================================================
def fig_vocab():
    tokens = [24600, 15186, 23296, 24652, 11275, 41676, 26285]
    lemmas = [636, 506, 469, 504, 252, 777, 401]
    x = np.arange(len(ATTRS))
    fig, ax1 = plt.subplots(figsize=(7.4, 3.6))
    b = ax1.bar(x, tokens, 0.6, color=C_PRIM, alpha=0.55, label="Token totali")
    ax1.set_ylabel("Token totali", color=C_PRIM)
    ax1.tick_params(axis="y", labelcolor=C_PRIM)
    ax1.set_xticks(x); ax1.set_xticklabels(ATTRS, fontsize=8)
    ax2 = ax1.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.plot(x, lemmas, "o-", color=C_RED, lw=2, ms=6, label="Lemmi unici (count>=3)")
    for xi, l in zip(x, lemmas):
        ax2.text(xi, l + 22, str(l), ha="center", fontsize=8, color=C_RED, fontweight="bold")
    ax2.set_ylabel("Lemmi unici (count>=3)", color=C_RED)
    ax2.tick_params(axis="y", labelcolor=C_RED)
    ax2.grid(False)
    ax2.set_ylim(0, 900)
    ax1.set_title("Vocabolario controllato: ampiezza per attributo")
    fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.95), frameon=False, fontsize=8.5)
    save(fig, "fig_vocab")


# ============================================================
# F6 — Costo LLM: scelta del modello + breakdown
# ============================================================
def fig_cost():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 3.3))
    # modelli a confronto (stesso lavoro)
    models = ["Haiku 4.5\n(scelto)", "Sonnet 4.6", "Opus 4.7"]
    costs = [5.60, 13.50, 67.0]
    cols = [C_GREEN, C_GOLD, C_RED]
    b = a1.bar(models, costs, color=cols, alpha=0.9, width=0.6)
    for bi, c in zip(b, costs):
        a1.text(bi.get_x()+bi.get_width()/2, c+1.2, f"${c:.2f}", ha="center", fontsize=9, fontweight="bold")
    a1.set_ylabel("Costo stimato (USD)")
    a1.set_title("Costo dello stesso lavoro\nper modello LLM")
    a1.set_ylim(0, 76)
    # breakdown Haiku
    parts = ["Pilot", "Batch\nparziale", "Batch\ncompleto"]
    pv = [0.20, 0.87, 4.50]
    b2 = a2.bar(parts, pv, color=C_PRIM, alpha=0.85, width=0.6)
    for bi, c in zip(b2, pv):
        a2.text(bi.get_x()+bi.get_width()/2, c+0.06, f"${c:.2f}", ha="center", fontsize=9, fontweight="bold")
    a2.set_ylabel("Costo (USD)")
    a2.set_title("Breakdown spesa effettiva\n(Haiku 4.5, totale $5,60)")
    a2.set_ylim(0, 5.2)
    save(fig, "fig_cost")


# ============================================================
# F7 — NON_DESCRITTO prima/dopo salvage per attributo
# ============================================================
def fig_salvage():
    before = [64, 56, 58, 30, 66, 54, 32]   # pre-salvage (batch)
    after  = [31, 35, 24, 23, 22, 30, 19]   # post-salvage
    x = np.arange(len(ATTRS_SHORT))
    w = 0.4
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    ax.bar(x - w/2, before, w, label="Post-batch (360 tot)", color=C_RED, alpha=0.8)
    ax.bar(x + w/2, after, w, label="Post-salvage (184 tot)", color=C_GREEN, alpha=0.9)
    ax.set_xticks(x); ax.set_xticklabels(ATTRS_SHORT, fontsize=8.5)
    ax.set_ylabel("Caption NON_DESCRITTO")
    ax.set_title("Salvage manuale: recupero di 178 caption uniche (916 righe training)")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig_salvage")


# ============================================================
# F8 — BLEU-4 per attributo: m1/m3/m6 vs most_frequent
# ============================================================
def fig_bleu_attr():
    order = ["Aroma", "Profumo", "Sapore", "Texture", "Spessore", "Colore", "Struttura"]
    m1 = [0.4737, 0.4161, 0.4553, 0.3780, 0.4272, 0.4144, 0.3269]
    m3 = [0.4855, 0.4036, 0.4542, 0.3796, 0.4238, 0.4755, 0.3297]
    m6 = [0.4830, 0.4114, 0.4561, 0.3863, 0.4449, 0.4591, 0.3480]
    mf = [0.4856, 0.3540, 0.4424, 0.3413, 0.4624, 0.4428, 0.2200]
    x = np.arange(len(order))
    w = 0.2
    fig, ax = plt.subplots(figsize=(7.6, 3.7))
    ax.bar(x - 1.5*w, m1, w, label="m1 (CNN+LSTM)", color=C_M1)
    ax.bar(x - 0.5*w, m3, w, label="m3 (ViT+Transf.)", color=C_M3)
    ax.bar(x + 0.5*w, m6, w, label="m6 (ViT+GePpeTto)", color=C_M6)
    ax.bar(x + 1.5*w, mf, w, label="most_frequent", color=C_BASE)
    ax.set_xticks(x); ax.set_xticklabels(order, fontsize=8.5)
    ax.set_ylabel("BLEU-4")
    ax.set_title("BLEU-4 per attributo: modelli addestrati vs baseline costante")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    ax.set_ylim(0, 0.58)
    save(fig, "fig_bleu_attr")


# ============================================================
# F9 — Metriche modello globale (tutti gli attributi insieme)
# ============================================================
def fig_global():
    metrics = ["BLEU-4", "BLEU-1", "METEOR", "ROUGE-L"]
    m1 = [0.1283, 0.3501, 0.2938, 0.2950]
    m3 = [0.1237, 0.3649, 0.2875, 0.2977]
    m6 = [0.1307, 0.3657, 0.2928, 0.3009]
    rnd= [0.1238, 0.3467, 0.2901, 0.2910]
    mf = [0.0782, 0.4191, 0.2361, 0.2665]
    x = np.arange(len(metrics))
    w = 0.16
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    ax.bar(x - 2*w, m1, w, label="m1", color=C_M1)
    ax.bar(x - 1*w, m3, w, label="m3", color=C_M3)
    ax.bar(x + 0*w, m6, w, label="m6", color=C_M6)
    ax.bar(x + 1*w, rnd, w, label="random", color=C_BASE)
    ax.bar(x + 2*w, mf, w, label="most_freq", color="#5C616B")
    ax.set_xticks(x); ax.set_xticklabels(metrics)
    ax.set_ylabel("Punteggio")
    ax.set_title("Modello globale (7 attributi insieme, test N=2.751)")
    ax.legend(frameon=False, fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.0))
    ax.set_ylim(0, 0.48)
    save(fig, "fig_global")


# ============================================================
# F10 — Shuffle test: heatmap z-score (image-conditioning)
# ============================================================
def fig_shuffle():
    order = ["Aroma", "Profumo", "Sapore", "Texture", "Spessore", "Colore", "Struttura"]
    data = np.array([
        [0.4, 0.2, 1.2],
        [0.6, 4.9, 5.0],
        [0.2, 2.7, -0.3],
        [-1.0, 0.9, 2.8],
        [0.0, 3.2, 3.4],
        [0.0, 8.5, 6.5],
        [-0.2, 4.6, 6.5],
    ])
    fig, ax = plt.subplots(figsize=(5.0, 4.2))
    im = ax.imshow(data, cmap="RdYlGn", vmin=-2, vmax=8, aspect="auto")
    ax.set_xticks(range(3)); ax.set_xticklabels(["m1\n(ResNet)", "m3\n(ViT)", "m6\n(ViT)"], fontsize=9)
    ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=9)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data[i, j]
            ax.text(j, i, f"{v:+.1f}", ha="center", va="center",
                    fontsize=9, fontweight="bold",
                    color="black" if -1 < v < 6 else "white")
    ax.set_title("Shuffle test: z-score di image-conditioning\n(z>3 = usa l'immagine, p<0,001)")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("z-score", fontsize=8)
    # linea soglia in colorbar
    save(fig, "fig_shuffle")


# ============================================================
# F11 — Per-attributo vs globale (perche i numeri differiscono)
# ============================================================
def fig_perattr_vs_global():
    fig, ax = plt.subplots(figsize=(7.0, 3.3))
    labels = ["m1", "m3", "m6"]
    glob = [0.1283, 0.1237, 0.1307]
    pa_best = [0.4737, 0.4855, 0.4830]
    x = np.arange(len(labels))
    w = 0.34
    ax.bar(x - w/2, glob, w, label="Globale (BLEU-4)", color=C_BASE)
    ax.bar(x + w/2, pa_best, w, label="Miglior per-attributo (BLEU-4)", color=C_PRIM)
    for xi, (g, p) in enumerate(zip(glob, pa_best)):
        ax.text(xi - w/2, g + 0.008, f"{g:.3f}", ha="center", fontsize=8)
        ax.text(xi + w/2, p + 0.008, f"{p:.3f}", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("BLEU-4")
    ax.set_title("Globale vs per-attributo: distribuzioni di valutazione diverse,\nnon modelli migliori")
    ax.legend(frameon=False, fontsize=9)
    ax.set_ylim(0, 0.56)
    save(fig, "fig_perattr_vs_global")


# ============================================================
# F12 — Righe finali training per attributo
# ============================================================
def fig_final_rows():
    order = ["Struttura", "Sapore", "Colore", "Profumo", "Texture", "Aroma", "Spessore"]
    rows = [7400, 6244, 5844, 5660, 5309, 4019, 3961]
    fig, ax = plt.subplots(figsize=(7.0, 3.3))
    bars = ax.barh(order[::-1], rows[::-1], color=C_PRIM, alpha=0.88, height=0.62)
    for b, v in zip(bars, rows[::-1]):
        ax.text(v + 60, b.get_y()+b.get_height()/2, f"{v:,}".replace(",", "."),
                va="center", fontsize=8.5, fontweight="bold")
    ax.set_xlabel("Righe training (image-caption)")
    ax.set_title("Dataset finale: 38.437 righe su 1.497 immagini uniche")
    ax.set_xlim(0, 8200)
    save(fig, "fig_final_rows")


if __name__ == "__main__":
    fig_funnel()
    fig_funnel_unique()
    fig_dedup()
    fig_spessore()
    fig_vocab()
    fig_cost()
    fig_salvage()
    fig_bleu_attr()
    fig_global()
    fig_shuffle()
    fig_perattr_vs_global()
    fig_final_rows()
    print("TUTTE le figure generate in", OUT)
