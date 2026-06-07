"""
render_task_images.py
---------------------
Renderira jednu PNG po jedinstvenoj (exam_type, pdf_page) kombinaciji u
`asp-rate/public/task-images/`, te ispisuje `asp-rate/public/tasks.json`
manifest koji webapp koristi za seedanje Supabasea.

Pokretanje:
  python render_task_images.py
"""

import sys
import json
import csv
import fitz
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pipeline import parse_exam_file
from pipeline.config import MI_PDF_PATH, ZI_PDF_PATH

DPI = 130
OUT_DIR    = Path("asp-rate/public/task-images")
MANIFEST   = Path("asp-rate/public/tasks.json")

CLUSTERS_CSV    = Path("embeddings/tasks_with_clusters.csv")
CLUSTER_LABELS  = Path("embeddings/cluster_labels.json")
BLACKLIST_JSON  = Path("data/blacklist_solution_pages.json")

PDF_BY_TYPE = {
    "MI": MI_PDF_PATH,
    "ZI": ZI_PDF_PATH,
}


def load_blacklist_pages() -> set[tuple[str, int]]:
    """
    Učitaj (exam_type, pdf_page) parove koje znamo da su samo stranice
    rješenja (ručno identificirane). Te stranice ne renderiramo i ne ulaze
    u manifest, čak i ako parser pronađe "Zadatak N." patterne na njima.
    """
    if not BLACKLIST_JSON.exists():
        return set()
    with open(BLACKLIST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {(p["exam_type"], int(p["pdf_page"])) for p in data.get("solution_pages", [])}


def load_cluster_map() -> dict[str, tuple[int | None, str | None]]:
    """task_id -> (cluster_id, cluster_label). Prazno ako pipeline nije pokrenut."""
    if not CLUSTERS_CSV.exists() or not CLUSTER_LABELS.exists():
        print(f"  (preskačem klastere: {CLUSTERS_CSV} ili {CLUSTER_LABELS} ne postoji)")
        return {}
    with open(CLUSTER_LABELS, encoding="utf-8") as f:
        labels = json.load(f)
    out: dict[str, tuple[int | None, str | None]] = {}
    with open(CLUSTERS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tid = row.get("task_id")
            cid_raw = row.get("cluster_id")
            if not tid or cid_raw in (None, ""):
                continue
            try:
                cid = int(cid_raw)
            except ValueError:
                continue
            out[tid] = (cid, labels.get(str(cid)))
    return out


def render_page(pdf_path: str, page_1based: int, out_path: Path) -> None:
    """Renderira jednu stranicu PDF-a u PNG."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_1based - 1]
        pix = page.get_pixmap(dpi=DPI)
        pix.save(str(out_path))
    finally:
        doc.close()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    print("[1/3] Parsiranje PDF-ova...")
    records  = parse_exam_file(MI_PDF_PATH, "MI")
    records += parse_exam_file(ZI_PDF_PATH, "ZI")
    print(f"  Ukupno: {len(records)} zadataka prije filtra")

    # Filtriraj stranice rješenja (parser ih svejedno ulovi po Zadatak markeru).
    blacklist = load_blacklist_pages()
    if blacklist:
        n_before = len(records)
        records = [r for r in records if (r["exam_type"], r["pdf_page"]) not in blacklist]
        print(f"  Filtrirano stranica rješenja: {n_before - len(records)} (ostalo {len(records)})")

    # Unique (exam_type, pdf_page) -> putanja PNG-a
    unique_pages = sorted({(r["exam_type"], r["pdf_page"]) for r in records})
    print(f"\n[2/3] Renderiram {len(unique_pages)} jedinstvenih stranica @ {DPI} DPI...")

    rendered = skipped = 0
    for exam_type, page in unique_pages:
        out_name = f"{exam_type}_p{page:03d}.png"
        out_path = OUT_DIR / out_name
        if out_path.exists():
            skipped += 1
            continue
        render_page(PDF_BY_TYPE[exam_type], page, out_path)
        rendered += 1
    print(f"  Renderirano: {rendered}, preskočeno (cached): {skipped}")

    print(f"\n[3/3] Pišem manifest u {MANIFEST}...")
    cluster_map = load_cluster_map()
    tasks_out = []
    matched_clusters = 0
    for r in records:
        image_name = f"{r['exam_type']}_p{r['pdf_page']:03d}.png"
        task_id    = f"{r['exam_type']}|{r['exam_date']}|{r['task_no']}"
        cid, clabel = cluster_map.get(task_id, (None, None))
        if cid is not None:
            matched_clusters += 1
        tasks_out.append({
            "task_id":       task_id,
            "exam_type":     r["exam_type"],
            "exam_date":     r["exam_date"],
            "task_no":       r["task_no"],
            "pdf_page":      r["pdf_page"],
            "image_path":    f"/task-images/{image_name}",
            "text_preview":  r["task_text"][:240],
            "cluster_id":    cid,
            "cluster_label": clabel,
        })
    if cluster_map:
        print(f"  Klasteri pridruženi: {matched_clusters}/{len(tasks_out)} zadataka")

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"tasks": tasks_out}, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {MANIFEST} ({len(tasks_out)} zadataka)")

    print("\n✅ Gotovo.")


if __name__ == "__main__":
    main()
