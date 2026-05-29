"""
embed_pipeline.py
-----------------
CLI driver: parsira PDF-ove, embedding, klasteriranje, LLM labeling.
Logika je u `pipeline/` paketu, ovaj fajl samo orkestrira.

Pokretanje:
  pip install sentence-transformers scikit-learn numpy pandas requests pymupdf umap-learn
  python embed_pipeline.py

Env varijable (opcionalno):
  OLLAMA_URL   = http://localhost:11434/api/chat   (default)
  OLLAMA_MODEL = llama3.1                          (default)
  N_CLUSTERS   = 15                                (default)
  CSV_PATH     = data/asp_index_last3_mi_last3_zi.csv
  MI_PDF       = static/MI_svi_do_2026.pdf
  ZI_PDF       = static/ZI_svi_do_2026.pdf
"""

import sys
import json
import numpy as np

# Windows konzola (cp1252) ne može printati hrvatske znakove, forsiraj UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import (
    N_CLUSTERS, CSV_PATH, MI_PDF_PATH, ZI_PDF_PATH, OUT_DIR
)
from pipeline import (
    parse_exam_file, load_and_merge, compute_embeddings,
    cluster_embeddings, compute_outlier_scores, label_clusters,
)


def main():
    OUT_DIR.mkdir(exist_ok=True)

    print("\n[1/6] Parsiranje PDF-ova...")
    records  = parse_exam_file(MI_PDF_PATH, "MI")
    records += parse_exam_file(ZI_PDF_PATH, "ZI")
    print(f"  Ukupno: {len(records)} zadataka")

    print("\n[2/6] Spajanje s CSV metapodacima...")
    df = load_and_merge(records, CSV_PATH)

    print("\n[3/6] Računanje embeddings...")
    texts      = df["task_text"].fillna("").tolist()
    embeddings = compute_embeddings(texts)
    np.save(OUT_DIR / "embeddings.npy", embeddings)
    print(f"  Saved: embeddings/embeddings.npy  shape={embeddings.shape}")

    print("\n[4/6] Klasteriranje...")
    df["cluster_id"] = cluster_embeddings(embeddings, N_CLUSTERS)

    print("\n[5/6] Outlier scoring...")
    df["outlier_score"] = compute_outlier_scores(embeddings)
    top_outliers = df.nlargest(10, "outlier_score")[["task_id", "task_text", "outlier_score"]]
    print("  Top 10 outliera:")
    for _, row in top_outliers.iterrows():
        preview = row["task_text"][:60].replace("\n", " ")
        print(f"    [{row['outlier_score']:.3f}] {row['task_id']}: {preview}")

    print("\n[6/6] LLM labeling klastera...")
    cluster_labels = label_clusters(df, N_CLUSTERS)
    df["cluster_label"] = df["cluster_id"].map(cluster_labels)

    out_csv = OUT_DIR / "tasks_with_clusters.csv"
    cols_to_save = [
        "task_id", "exam_type", "exam_date", "task_no",
        "task_text", "cluster_id", "cluster_label", "outlier_score",
        "pdf", "page", "points", "time_est", "efficiency",
        "difficulty_guess", "type", "frequency_score", "concepts", "snippet"
    ]
    cols_present = [c for c in cols_to_save if c in df.columns]
    df[cols_present].to_csv(out_csv, index=False)
    print(f"\n  Saved: {out_csv}  ({len(df)} zadataka)")

    labels_path = OUT_DIR / "cluster_labels.json"
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(cluster_labels, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {labels_path}")

    print("\n✅ embed_pipeline.py završen.")
    print(f"   Klasteri: {N_CLUSTERS}")
    print(f"   Zadataka: {len(df)}")
    print(f"   Matched s CSV: {df['points'].notna().sum()}")


if __name__ == "__main__":
    main()
