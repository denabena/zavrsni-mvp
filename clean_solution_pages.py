"""
clean_solution_pages.py
-----------------------
Iz parsiranja PDF-ova greškom su ušli i lijepe rješenja kao "zadaci" (stranice
gdje je nastavak rješenja prethodnih zadataka). Ovaj skripta:

1. Definira hard-coded blacklist task_id-ova iz tih stranica.
2. Briše ih iz embeddings/tasks_with_clusters.csv.
3. Briše ih iz asp-rate/public/tasks.json (pa ih buduće osobe ne ocjenjuju).
4. U asp-rate/public/tasks.json ujedno osvježava cluster_label iz najnovije
   verzije embeddings/cluster_labels.json.
5. Snima blacklistu u data/blacklist_solution_pages.json da kasnije možemo
   izbaciti njihove ocjene iz Supabase agregata.
6. Rekompajlira embeddings/cluster_frequencies.json na očišćenom skupu.

Pokretanje:
  python clean_solution_pages.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.config import OUT_DIR
from pipeline.frequency import save_cluster_frequencies


# Lista parova (exam_type, pdf_page) za stranice koje sadrže samo rješenja.
SOLUTION_PAGES: list[tuple[str, int]] = [
    ("MI", 21), ("MI", 22), ("MI", 23),
    ("ZI", 56), ("ZI", 57), ("ZI", 58),
    ("ZI", 61), ("ZI", 62),
    ("ZI", 68), ("ZI", 69),
    ("ZI", 73), ("ZI", 74),
]

BLACKLIST_OUT = Path("data/blacklist_solution_pages.json")
TASKS_JSON = Path("asp-rate/public/tasks.json")
TASKS_CSV = OUT_DIR / "tasks_with_clusters.csv"
LABELS_JSON = OUT_DIR / "cluster_labels.json"


def main():
    # 1. Učitaj tasks.json (jedini izvor s pdf_page po zadatku) da identificiramo bad task_ids.
    with open(TASKS_JSON, encoding="utf-8") as f:
        manifest = json.load(f)
    tasks = manifest["tasks"]

    bad_set = set(SOLUTION_PAGES)
    bad_tasks = [
        t for t in tasks if (t["exam_type"], t["pdf_page"]) in bad_set
    ]
    bad_task_ids = sorted({t["task_id"] for t in bad_tasks})
    print(f"Pronađeno {len(bad_task_ids)} loših task_id-ova (na {len(bad_set)} stranica rješenja):")
    for tid in bad_task_ids:
        print(f"  {tid}")

    # 2. Snimi blacklistu.
    BLACKLIST_OUT.parent.mkdir(parents=True, exist_ok=True)
    blacklist_payload = {
        "reason": "PDF parser je stranice samih rješenja (bez teksta zadatka) "
                  "uzeo kao zadatke. Ovi task_id-ovi nisu legitimni i njihove "
                  "ocjene treba izuzeti pri agregaciji iz Supabasea.",
        "solution_pages": [
            {"exam_type": et, "pdf_page": pg} for et, pg in SOLUTION_PAGES
        ],
        "task_ids": bad_task_ids,
    }
    with open(BLACKLIST_OUT, "w", encoding="utf-8") as f:
        json.dump(blacklist_payload, f, ensure_ascii=False, indent=2)
    print(f"\nSnimljeno: {BLACKLIST_OUT}")

    # 3. Filtriraj tasks_with_clusters.csv.
    df = pd.read_csv(TASKS_CSV)
    n_before = len(df)
    df = df[~df["task_id"].isin(bad_task_ids)].reset_index(drop=True)
    df.to_csv(TASKS_CSV, index=False)
    print(f"Filtriran {TASKS_CSV}: {n_before} -> {len(df)} zadataka")

    # 4. Filtriraj tasks.json + osvježi cluster_label iz najnovijih labela.
    with open(LABELS_JSON, encoding="utf-8") as f:
        latest_labels = json.load(f)
    latest_labels_int = {int(k): v for k, v in latest_labels.items()}

    clean_tasks = []
    for t in tasks:
        if t["task_id"] in set(bad_task_ids):
            continue
        # update cluster_label iz najnovije verzije
        cid = int(t["cluster_id"])
        if cid in latest_labels_int:
            t["cluster_label"] = latest_labels_int[cid]
        clean_tasks.append(t)

    manifest["tasks"] = clean_tasks
    with open(TASKS_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Filtriran {TASKS_JSON}: {len(tasks)} -> {len(clean_tasks)} zadataka, cluster_label osvježen")

    # 5. Re-izračunaj per-cluster frekvencije na očišćenom skupu.
    freq = save_cluster_frequencies(df, OUT_DIR / "cluster_frequencies.json")
    print(f"Rekompajliran {OUT_DIR / 'cluster_frequencies.json'}")

    print("\nGotovo. Filtrirano je {} loših zadataka.".format(len(bad_task_ids)))


if __name__ == "__main__":
    main()
