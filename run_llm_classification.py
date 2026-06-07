"""
run_llm_classification.py
-------------------------
Klasificira svih 185 zadataka u fiksnu taksonomiju (pipeline/classify.py)
preko Ollame i sprema rezultate u `embeddings/llm_classification/` kao
test folder. Aktivni `embeddings/` ostaje netaknut.

Outputs:
  embeddings/llm_classification/
    cluster_labels.json            # idx -> ime kategorije
    tasks_with_clusters.csv        # cluster_id, cluster_label = LLM kategorija
    cluster_frequencies.json       # P(category | exam_type)
    task_labels_quickview.csv      # za ručni review
    embeddings.npy                 # kopija aktivnih embeddinga (za outlier centroide)

Pokretanje (Ollama mora biti running):
  python run_llm_classification.py
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.classify import TAXONOMY, classify_all_tasks
from pipeline.clustering import compute_centroid_outlier_scores
from pipeline.frequency import save_cluster_frequencies


SRC_DIR = Path("embeddings")
OUT_DIR = Path("embeddings/llm_classification")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    src_csv = SRC_DIR / "tasks_with_clusters.csv"
    src_emb = SRC_DIR / "embeddings.npy"

    df = pd.read_csv(src_csv)
    embeddings = np.load(src_emb)
    print(f"Učitano: {len(df)} zadataka, embeddings shape={embeddings.shape}")
    print(f"Taksonomija: {len(TAXONOMY)} kategorija")
    print()

    print("[1/4] Klasificiranje preko Ollame...")
    cat_map = classify_all_tasks(df)

    # cluster_id = indeks u TAXONOMY (stabilan)
    name_to_id = {name: i for i, name in enumerate(TAXONOMY)}
    df["cluster_id"] = df["task_id"].map(lambda tid: name_to_id.get(cat_map.get(tid, "Razno"), len(TAXONOMY) - 1))
    df["cluster_label"] = df["task_id"].map(lambda tid: cat_map.get(tid, "Razno"))

    print("\n[2/4] Outlier scoring (centroid u embedding prostoru, po LLM kategoriji)...")
    df["centroid_outlier_score"] = compute_centroid_outlier_scores(
        embeddings, df["cluster_id"].to_numpy()
    )

    # Spremi sve outpute u test folder
    out_csv = OUT_DIR / "tasks_with_clusters.csv"
    df.to_csv(out_csv, index=False)
    print(f"  Saved: {out_csv}")

    labels_path = OUT_DIR / "cluster_labels.json"
    labels_dict = {str(i): name for i, name in enumerate(TAXONOMY)}
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(labels_dict, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {labels_path}")

    print("\n[3/4] Per-cluster frekvencije po exam_type...")
    freq_path = OUT_DIR / "cluster_frequencies.json"
    save_cluster_frequencies(df, freq_path)
    print(f"  Saved: {freq_path}")

    print("\n[4/4] Quick-view CSV...")
    quick = df.drop_duplicates(subset=["task_id"], keep="first")
    quick = quick[["task_id", "exam_type", "exam_date", "task_no", "cluster_id", "cluster_label"]]
    quick = quick.sort_values(["exam_type", "exam_date", "task_no"], kind="stable")
    quick_path = OUT_DIR / "task_labels_quickview.csv"
    quick.to_csv(quick_path, index=False)
    print(f"  Saved: {quick_path}")

    # Kopija embeddings.npy da test folder bude samodostatan
    shutil.copy(src_emb, OUT_DIR / "embeddings.npy")

    # Distribucija
    print("\n--- Distribucija kategorija ---")
    counts = df["cluster_label"].value_counts()
    for cat, n in counts.items():
        print(f"  {cat:<24} {n}")

    print(f"\nTotal: {len(df)} zadataka")
    print(f"Output folder: {OUT_DIR}")


if __name__ == "__main__":
    main()
