"""
analyze_clusters.py
-------------------
Diagnostic sweep za K-means: za k=5..25 izračuna inerciju, silhouette i
ARI stabilnost između više inicijalizacija, te generira plotove u
`embeddings/`.

Pokretanje:
  python analyze_clusters.py

Output:
  embeddings/cluster_sweep.png       : elbow + silhouette + ARI vs k
  embeddings/cluster_umap_2d.png     : UMAP scatter colored by best clustering
  embeddings/cluster_sweep.csv       : raw numbers za paper
  + ispis preporučenog k na stdout
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import OUT_DIR, MI_PDF_PATH, ZI_PDF_PATH, CSV_PATH
from pipeline.clustering import sweep_k, reduce_with_umap


K_MIN = 5
K_MAX = 25
N_RUNS_PER_K = 10


def load_or_compute_embeddings() -> tuple[np.ndarray, pd.DataFrame]:
    """Pokušaj učitati cached embeddings; inače ih izračunaj."""
    npy = OUT_DIR / "embeddings.npy"
    csv = OUT_DIR / "tasks_with_clusters.csv"

    if npy.exists() and csv.exists():
        print(f"  Učitavam cached embeddings iz {npy}")
        embeddings = np.load(npy)
        df = pd.read_csv(csv)
        if len(df) == embeddings.shape[0]:
            return embeddings, df
        print("  [WARN] Cache neusklađen, recomputeam...")

    from pipeline import parse_exam_file, load_and_merge, compute_embeddings

    print("  Parsiram PDF-ove...")
    records  = parse_exam_file(MI_PDF_PATH, "MI")
    records += parse_exam_file(ZI_PDF_PATH, "ZI")
    df = load_and_merge(records, CSV_PATH)

    print("  Računam embeddinge...")
    embeddings = compute_embeddings(df["task_text"].fillna("").tolist())
    OUT_DIR.mkdir(exist_ok=True)
    np.save(npy, embeddings)
    return embeddings, df


def plot_sweep(result: dict, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ks      = result["ks"]
    inert   = result["inertias"]
    sils    = result["silhouettes"]
    aris    = result["aris"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    axes[0].plot(ks, inert, "o-")
    axes[0].set_title("Elbow (inertia)")
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("inertia")
    axes[0].grid(alpha=0.3)

    axes[1].plot(ks, sils, "o-", color="tab:green")
    axes[1].set_title("Silhouette score")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("silhouette")
    axes[1].axhline(0, color="gray", linewidth=0.5)
    axes[1].grid(alpha=0.3)

    axes[2].plot(ks, aris, "o-", color="tab:red")
    axes[2].set_title("ARI stability (mean pairwise)")
    axes[2].set_xlabel("k")
    axes[2].set_ylabel("ARI")
    axes[2].axhline(1.0, color="gray", linewidth=0.5, linestyle="--")
    axes[2].grid(alpha=0.3)

    fig.suptitle(f"K-means sweep (UMAP→{result['X'].shape[1]}D, {N_RUNS_PER_K} runs/k)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_umap_2d(embeddings: np.ndarray, labels: np.ndarray, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    coords = reduce_with_umap(embeddings, n_components=2, random_state=42)

    fig, ax = plt.subplots(figsize=(8, 7))
    scatter = ax.scatter(
        coords[:, 0], coords[:, 1], c=labels, cmap="tab20", s=30, alpha=0.85
    )
    ax.set_title(f"UMAP 2D projekcija (k={len(set(labels))})")
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    plt.colorbar(scatter, label="cluster_id")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def recommend_k(result: dict) -> int:
    """
    Heuristika: standardiziraj silhouette i ARI, zbroji, pa pick argmax.
    Penaliziraj k ≤ 5 i k ≥ 22 lagano (rubovi).
    """
    sils = np.array(result["silhouettes"])
    aris = np.array(result["aris"])
    ks   = np.array(result["ks"])

    def zscore(x):
        std = x.std()
        return (x - x.mean()) / (std if std > 1e-9 else 1.0)

    score = zscore(sils) + zscore(aris)
    edge_penalty = np.where((ks <= 6) | (ks >= 23), -0.5, 0.0)
    score += edge_penalty

    best_i = int(np.argmax(score))
    return int(ks[best_i])


def main():
    OUT_DIR.mkdir(exist_ok=True)

    print(f"\n[1/4] Učitavam embeddinge...")
    embeddings, df = load_or_compute_embeddings()
    print(f"  shape={embeddings.shape}")

    print(f"\n[2/4] Sweep k={K_MIN}..{K_MAX} ({N_RUNS_PER_K} runs po k)...")
    result = sweep_k(
        embeddings,
        k_min=K_MIN,
        k_max=K_MAX,
        n_runs=N_RUNS_PER_K,
        use_umap=True,
    )

    print(f"\n[3/4] Spremam plotove i CSV...")
    pd.DataFrame({
        "k":          result["ks"],
        "inertia":    result["inertias"],
        "silhouette": result["silhouettes"],
        "ari":        result["aris"],
    }).to_csv(OUT_DIR / "cluster_sweep.csv", index=False)
    plot_sweep(result, OUT_DIR / "cluster_sweep.png")
    print(f"  Saved: embeddings/cluster_sweep.csv, embeddings/cluster_sweep.png")

    best_k = recommend_k(result)
    print(f"\n[4/4] Preporučeni k = {best_k}")
    print(f"  (max silhouette: k={result['ks'][int(np.argmax(result['silhouettes']))]}, "
          f"max ARI: k={result['ks'][int(np.argmax(result['aris']))]})")

    # 2D UMAP s labelama iz preporučenog k
    from pipeline.clustering import cluster_embeddings
    labels = cluster_embeddings(embeddings, n_clusters=best_k, use_umap=True, random_state=42)
    plot_umap_2d(embeddings, labels, OUT_DIR / "cluster_umap_2d.png")
    print(f"  Saved: embeddings/cluster_umap_2d.png")

    print(f"\nℹ️  Pokreni `N_CLUSTERS={best_k} python embed_pipeline.py` da koristiš preporučeni k.")


if __name__ == "__main__":
    main()
