import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

EMBEDDINGS_PATH = os.getenv("EMBEDDINGS_PATH", "embeddings/embeddings.npy")
CLUSTERS_CSV    = os.getenv("CLUSTERS_CSV",    "embeddings/tasks_with_clusters.csv")
K_MAX           = int(os.getenv("K_MAX", "15"))

# ── Čiste labele (overridaj loše LLM labele ovdje) ───────────────────────────
CLEAN_LABELS = {
    0: "Analiza složenosti",
    1: "Liste, stog, rekurzija",
    2: "Binarno stablo (BST)",
    3: "Sortiranje polja",
    4: "Grafovi i napredni alg.",
    5: "Red i implementacija klasa",
    6: "BST (stariji ispiti)",
    7: "Stog i sučelja",
    8: "Raspršeno adresiranje",
    9: "Rekurzivne funkcije",
}

# ── Boje po klasteru ──────────────────────────────────────────────────────────
COLORS = [
    "#7F77DD", "#1D9E75", "#378ADD", "#D85A30", "#BA7517",
    "#639922", "#D4537E", "#5F5E5A", "#E24B4A", "#0F6E56",
]


def load_data():
    print("Učitavam embeddings i CSV...")
    emb = np.load(EMBEDDINGS_PATH)
    emb = normalize(emb)  # L2 normalizacija, kosinusna sličnost
    df  = pd.read_csv(CLUSTERS_CSV, encoding="utf-8")
    print(f"  Embeddings: {emb.shape}")
    print(f"  Zadataka:   {len(df)}")
    return emb, df


def reduce_umap(emb):
    try:
        from umap import UMAP
        print("Reduciram dimenzije s UMAP...")
        reducer = UMAP(n_components=2, random_state=42, n_neighbors=10, min_dist=0.1)
        return reducer.fit_transform(emb)
    except ImportError:
        print("UMAP nije instaliran, koristim t-SNE...")
        from sklearn.manifold import TSNE
        return TSNE(n_components=2, random_state=42, perplexity=15).fit_transform(emb)


def compute_elbow_silhouette(emb, k_max):
    print(f"Računam elbow i silhouette za k=2..{k_max}...")
    inertias    = []
    silhouettes = []
    ks = range(2, k_max + 1)
    for k in ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(emb)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(emb, labels))
        print(f"  k={k:2d}  inertia={km.inertia_:.1f}  silhouette={silhouettes[-1]:.3f}")
    return list(ks), inertias, silhouettes


def plot_all(emb_2d, df, ks, inertias, silhouettes):
    n_clusters = df["cluster_id"].nunique()
    best_k_sil = ks[silhouettes.index(max(silhouettes))]

    fig = plt.figure(figsize=(18, 6))
    fig.patch.set_facecolor("#fafafa")

    # ── Plot 1: UMAP scatter ─────────────────────────────────────────────────
    ax1 = fig.add_subplot(1, 3, 1)
    ax1.set_facecolor("#f5f5f5")

    cluster_ids = df["cluster_id"].astype(int).values
    exam_types  = df["exam_type"].values if "exam_type" in df.columns else ["?"] * len(df)

    for cid in sorted(set(cluster_ids)):
        mask = cluster_ids == cid
        color = COLORS[cid % len(COLORS)]
        label = CLEAN_LABELS.get(cid, f"Klaster {cid}")

        # MI = krug, ZI = trokut
        mi_mask = mask & (exam_types == "MI")
        zi_mask = mask & (exam_types == "ZI")

        ax1.scatter(
            emb_2d[mi_mask, 0], emb_2d[mi_mask, 1],
            c=color, s=55, alpha=0.82, marker="o", zorder=3,
            label=label
        )
        ax1.scatter(
            emb_2d[zi_mask, 0], emb_2d[zi_mask, 1],
            c=color, s=65, alpha=0.82, marker="^", zorder=3
        )

    # Hover tooltip s task_id
    annot = ax1.annotate(
        "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#ccc", lw=0.8),
        fontsize=8, color="#333"
    )
    annot.set_visible(False)

    scatter_data = list(zip(emb_2d[:, 0], emb_2d[:, 1],
                            df["task_id"].values if "task_id" in df.columns
                            else [f"zadatak {i}" for i in range(len(df))]))

    def on_move(event):
        if event.inaxes != ax1:
            annot.set_visible(False)
            fig.canvas.draw_idle()
            return
        dist = [(abs(event.xdata - x) + abs(event.ydata - y), tid)
                for x, y, tid in scatter_data]
        dist.sort()
        if dist[0][0] < 0.3:
            annot.xy = (dist[0][1], dist[0][1])
            tid = dist[0][1]
            # Pronađi red
            row = df[df["task_id"] == tid].iloc[0] if "task_id" in df.columns else None
            if row is not None:
                pts  = row.get("points", "?") or "?"
                cid  = int(row.get("cluster_id", -1))
                clbl = CLEAN_LABELS.get(cid, f"K{cid}")
                text = f"{tid}\n{clbl}\n{pts} bod."
            else:
                text = str(tid)
            annot.set_text(text)
            # Pozicioniraj kraj točke
            px, py = event.xdata, event.ydata
            annot.xy = (px, py)
            annot.set_visible(True)
        else:
            annot.set_visible(False)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)

    # Legenda — samo klastere, ne MI/ZI
    handles = [mpatches.Patch(color=COLORS[i % len(COLORS)],
                               label=CLEAN_LABELS.get(i, f"K{i}"))
               for i in sorted(set(cluster_ids))]
    ax1.legend(handles=handles, fontsize=7, loc="lower right",
               framealpha=0.85, edgecolor="#ddd")

    # MI / ZI legenda
    mi_handle = plt.scatter([], [], c="#555", s=45, marker="o", label="MI")
    zi_handle = plt.scatter([], [], c="#555", s=55, marker="^", label="ZI")
    ax1.legend(handles=handles + [mi_handle, zi_handle],
               fontsize=7, loc="lower right", framealpha=0.85, edgecolor="#ddd")

    ax1.set_title("Raspored zadataka (UMAP/t-SNE)", fontsize=11, pad=10)
    ax1.set_xlabel("Dimenzija 1", fontsize=9)
    ax1.set_ylabel("Dimenzija 2", fontsize=9)
    ax1.tick_params(labelsize=8)
    ax1.grid(True, alpha=0.3, lw=0.5)

    # ── Plot 2: Elbow curve ───────────────────────────────────────────────────
    ax2 = fig.add_subplot(1, 3, 2)
    ax2.set_facecolor("#f5f5f5")
    ax2.plot(ks, inertias, "o-", color="#7F77DD", lw=2, ms=5)
    ax2.axvline(x=n_clusters, color="#D85A30", lw=1.5, ls="--",
                label=f"trenutni k={n_clusters}")
    ax2.set_title("Elbow metoda (inercija)", fontsize=11, pad=10)
    ax2.set_xlabel("Broj klastera k", fontsize=9)
    ax2.set_ylabel("Inercija (WCSS)", fontsize=9)
    ax2.legend(fontsize=8)
    ax2.tick_params(labelsize=8)
    ax2.grid(True, alpha=0.3, lw=0.5)

    # ── Plot 3: Silhouette scores ─────────────────────────────────────────────
    ax3 = fig.add_subplot(1, 3, 3)
    ax3.set_facecolor("#f5f5f5")
    bar_colors = ["#D85A30" if k == best_k_sil else "#7F77DD" for k in ks]
    ax3.bar(ks, silhouettes, color=bar_colors, alpha=0.85, width=0.7)
    ax3.axvline(x=n_clusters, color="#1D9E75", lw=1.5, ls="--",
                label=f"trenutni k={n_clusters}")
    ax3.set_title(f"Silhouette score  (best k={best_k_sil})", fontsize=11, pad=10)
    ax3.set_xlabel("Broj klastera k", fontsize=9)
    ax3.set_ylabel("Silhouette score", fontsize=9)
    ax3.legend(fontsize=8)
    ax3.tick_params(labelsize=8)
    ax3.grid(True, alpha=0.3, lw=0.5, axis="y")
    ax3.set_ylim(0, max(silhouettes) * 1.15)

    # Anotacija najboljeg k
    best_sil = max(silhouettes)
    ax3.annotate(
        f"  {best_sil:.3f}",
        xy=(best_k_sil, best_sil),
        fontsize=9, color="#D85A30", fontweight="bold"
    )

    plt.suptitle("ASP — Analiza klastera zadataka", fontsize=13, fontweight="500", y=1.01)
    plt.tight_layout()

    print(f"\nRezultat:")
    print(f"  Trenutni k         : {n_clusters}")
    print(f"  Optimalni k (sil.) : {best_k_sil}  (score={max(silhouettes):.3f})")
    print(f"  Preporuka: {'k je OK' if abs(n_clusters - best_k_sil) <= 1 else f'pokušaj k={best_k_sil}'}")

    plt.savefig("cluster_analysis.png", dpi=150, bbox_inches="tight",
                facecolor="#fafafa")
    print("\nSpremljeno: cluster_analysis.png")
    plt.show()


def main():
    emb, df = load_data()
    emb_2d   = reduce_umap(emb)
    ks, inertias, silhouettes = compute_elbow_silhouette(emb, K_MAX)
    plot_all(emb_2d, df, ks, inertias, silhouettes)


if __name__ == "__main__":
    main()