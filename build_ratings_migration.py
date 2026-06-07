"""
build_ratings_migration.py
--------------------------
Generira SQL skriptu za migraciju ratinga iz starih (kolidirajući task_id-ovi
iz slomljenog parsera) u nove (post-fix task_id-ovi).

Logika:
  - Učitaj snapshot stari tasks.old.json (pre-fix) i novi tasks.json (post-fix).
  - Za svaki *stari* task_id koji više ne postoji u novom:
      a. Nađi PRVU pojavu u tasks.old.json (deterministički poredak, isti kao
         picker u webappu - svi rateri su uvijek bili pokazani prvi entry).
      b. Iz tog entryja izvuci image_path.
      c. Nađi novi task_id koji ima isti image_path.
      d. Generiraj UPDATE ratings SET task_id = '<new>' WHERE task_id = '<old>'.
  - Za task_id-ove koji postoje i u starom i u novom: nema migracije, ratings
    su već ispravno vezani.
  - Za task_id-ove samo u novom (recovered old exams): nema postojećih ratinga.

Output: data/migration_ratings.sql

Pokretanje:
  python build_ratings_migration.py
"""

import json
import sys
from collections import OrderedDict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


OLD_JSON = Path("asp-rate/public/tasks.old.json")
NEW_JSON = Path("asp-rate/public/tasks.json")
OUT_SQL = Path("data/migration_ratings.sql")


def main():
    with open(OLD_JSON, encoding="utf-8") as f:
        old_tasks = json.load(f)["tasks"]
    with open(NEW_JSON, encoding="utf-8") as f:
        new_tasks = json.load(f)["tasks"]

    # Stari task_ids u redoslijedu pojave (first-occurrence wins per picker).
    old_first: OrderedDict[str, dict] = OrderedDict()
    for t in old_tasks:
        if t["task_id"] not in old_first:
            old_first[t["task_id"]] = t

    # Novi task_id po (exam_type, pdf_page, task_no). Ovaj triple je invariant
    # između parsera jer task_no izvlači iz "Zadatak N." markera u istom PDF
    # tekstu, neovisno o exam_date detekciji. Image_path nije dovoljan jer više
    # zadataka može biti na istoj stranici.
    new_by_etk: dict[tuple[str, int, int], str] = {}
    for t in new_tasks:
        key = (t["exam_type"], int(t["pdf_page"]), int(t["task_no"]))
        new_by_etk[key] = t["task_id"]
    new_ids = {t["task_id"] for t in new_tasks}

    # Klasifikacija
    unchanged: list[str] = []
    migrate: list[tuple[str, str]] = []  # (old_tid, new_tid)
    orphan: list[str] = []

    for old_tid, t in old_first.items():
        if old_tid in new_ids:
            unchanged.append(old_tid)
            continue
        key = (t["exam_type"], int(t["pdf_page"]), int(t["task_no"]))
        new_tid = new_by_etk.get(key)
        if new_tid is None:
            orphan.append(old_tid)
        else:
            migrate.append((old_tid, new_tid))

    # Generiraj SQL
    OUT_SQL.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "-- Migracija ratinga: stari task_id -> novi task_id.",
        "-- Generirano iz tasks.old.json + tasks.json poredanog po picker-pravilu",
        "-- (prvi entry s tim task_id-om u tasks.old.json odlučuje image_path).",
        "--",
        f"-- Stari unique task_ids: {len(old_first)}",
        f"-- Nepromijenjeni:        {len(unchanged)}  (nema SQL-a, ratings već OK)",
        f"-- Za migraciju:           {len(migrate)}",
        f"-- Orphan (drop ratings):  {len(orphan)}",
        "",
        "begin;",
        "",
    ]

    if migrate:
        lines.append("-- 1) Update task_id na novi format.")
        # Da se ne udaramo u unique (task_id, rater_uuid) constraint: ako rater
        # već ima rating na novom task_id-u (nemoguće u praksi jer novi task_id
        # nije bio servirana raterima dosad), ON CONFLICT bi nas spasio. Koristimo
        # DELETE pa INSERT za sigurnost? Ne, jednostavni UPDATE radi: stari je
        # bio rated, novi je nov, kolizija nemoguća.
        for old_tid, new_tid in migrate:
            lines.append(
                f"UPDATE ratings SET task_id = '{new_tid}' WHERE task_id = '{old_tid}';"
            )
        lines.append("")

    if orphan:
        lines.append(
            "-- 2) Orphan ratings: stari task_id koji nema odgovarajući novi (image"
        )
        lines.append(
            "--    više nije u manifestu, ili je bio na blacklisted solution page-u)."
        )
        lines.append("--    Ove redove brišemo da ne ostanu pod mrtvim ID-em.")
        for old_tid in orphan:
            lines.append(f"DELETE FROM ratings WHERE task_id = '{old_tid}';")
        lines.append("")

    lines.append("commit;")

    OUT_SQL.write_text("\n".join(lines), encoding="utf-8")
    print(f"Snimljeno: {OUT_SQL}")
    print(f"  Nepromijenjeni: {len(unchanged)}")
    print(f"  Za migraciju:   {len(migrate)}")
    print(f"  Orphan (DELETE): {len(orphan)}")
    print()
    print("Sample migrations (prvih 10):")
    for old_tid, new_tid in migrate[:10]:
        print(f"  {old_tid}  ->  {new_tid}")
    if orphan:
        print()
        print("Orphans (prvih 10):")
        for tid in orphan[:10]:
            print(f"  {tid}")


if __name__ == "__main__":
    main()
