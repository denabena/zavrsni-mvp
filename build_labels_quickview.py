"""
build_labels_quickview.py
-------------------------
Iz tasks_with_clusters.csv generira tanki CSV samo s onim što treba za brzo
ručno provjeravanje točnosti klasterskih labela:

  task_id, exam_type, exam_date, task_no, cluster_id, cluster_label

Deduplicira po task_id (zadrži prvi), sortira po (exam_type, exam_date, task_no).
Output: embeddings/task_labels_quickview.csv
"""

import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import OUT_DIR


def main():
    src = OUT_DIR / "tasks_with_clusters.csv"
    out = OUT_DIR / "task_labels_quickview.csv"

    df = pd.read_csv(src)
    n_before = len(df)
    df = df.drop_duplicates(subset=["task_id"], keep="first")
    n_after = len(df)

    cols = ["task_id", "exam_type", "exam_date", "task_no", "cluster_id", "cluster_label"]
    df = df[cols].copy()
    df = df.sort_values(["exam_type", "exam_date", "task_no"], kind="stable")
    df.to_csv(out, index=False)

    print(f"Snimljeno: {out}")
    print(f"  redaka: {n_after}  (dedup s {n_before})")


if __name__ == "__main__":
    main()
