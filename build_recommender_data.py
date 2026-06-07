"""
build_recommender_data.py
-------------------------
Iz postojećih artefakata (embeddings.npy + tasks_with_clusters.csv) izračunaj
ulaze za recommender:
  - centroid_outlier_score (per-cluster percentile rank distance to centroid)
  - cluster_frequencies.json (P(cluster | exam_type))

Ne pokreće parsiranje PDF-ova ni novi embedding sweep, ne treba Ollamu.

Pokretanje:
  python build_recommender_data.py
"""

import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import OUT_DIR
from pipeline import (
    compute_centroid_outlier_scores,
    save_cluster_frequencies,
)


def main():
    csv_path = OUT_DIR / "tasks_with_clusters.csv"
    emb_path = OUT_DIR / "embeddings.npy"

    df = pd.read_csv(csv_path)
    embeddings = np.load(emb_path)
    print(f"Učitano {len(df)} zadataka, embeddings shape={embeddings.shape}")

    print("\n[1/2] Centroid outlier scoring (per-cluster percentile rank)...")
    df["centroid_outlier_score"] = compute_centroid_outlier_scores(
        embeddings, df["cluster_id"].to_numpy()
    )
    top = df.nlargest(10, "centroid_outlier_score")[
        ["task_id", "cluster_id", "cluster_label", "centroid_outlier_score"]
    ]
    print("  Top 10 outliera (najdalje od centroida svojeg klastera):")
    for _, row in top.iterrows():
        label = str(row.get("cluster_label", ""))[:40]
        print(
            f"    [{row['centroid_outlier_score']:.3f}] "
            f"cl={row['cluster_id']:2d} {row['task_id']}  ({label})"
        )

    df.to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}")

    print("\n[2/2] Per-cluster frekvencije po exam_type...")
    freq_path = OUT_DIR / "cluster_frequencies.json"
    freq = save_cluster_frequencies(df, freq_path)
    for exam_type, dist in freq.items():
        top3 = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[:3]
        readable = ", ".join(f"cl{cid}={p:.2f}" for cid, p in top3)
        print(f"  {exam_type}: top3 -> {readable}")
    print(f"  Saved: {freq_path}")

    print("\nGotovo.")


if __name__ == "__main__":
    main()
