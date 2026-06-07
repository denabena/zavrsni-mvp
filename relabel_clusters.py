"""
relabel_clusters.py
-------------------
Re-run LLM labelinga na postojećim klasterima bez ponovnog parsiranja
PDF-ova i izračuna embeddinga. Učita `embeddings/tasks_with_clusters.csv`,
pozove novi batch labeler i prepiše stupac cluster_label + cluster_labels.json.

Pokretanje (uz pokrenutu Ollamu):
  python relabel_clusters.py
"""

import json
import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import N_CLUSTERS, OUT_DIR
from pipeline.labeling import label_clusters


def main():
    csv_path = OUT_DIR / "tasks_with_clusters.csv"
    df = pd.read_csv(csv_path)
    print(f"Učitano {len(df)} zadataka, {df['cluster_id'].nunique()} klastera.\n")

    labels = label_clusters(df, N_CLUSTERS)

    df["cluster_label"] = df["cluster_id"].map(labels)
    df.to_csv(csv_path, index=False)
    print(f"\n  Saved: {csv_path}")

    labels_path = OUT_DIR / "cluster_labels.json"
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {labels_path}")


if __name__ == "__main__":
    main()
