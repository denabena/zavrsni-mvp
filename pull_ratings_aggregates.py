"""
pull_ratings_aggregates.py
--------------------------
Povuci sve redove iz Supabase `ratings` tablice, agregiraj po task_id i
spremi medijan težine + medijan vremena u embeddings/task_aggregates.json.

Recommender (recommender/data.py) automatski merge-a ovaj fajl ako postoji.

Pokretanje:
  python pull_ratings_aggregates.py
"""

import json
import os
import statistics
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ENV_FILE = Path("asp-rate/.env.local")
OUT_JSON = Path("embeddings/task_aggregates.json")
TASKS_JSON = Path("asp-rate/public/tasks.json")
MIGRATION_SQL = Path("data/migration_ratings.sql")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load_migration_map() -> dict[str, str]:
    """Stari task_id -> novi task_id, izvučeno iz data/migration_ratings.sql."""
    out: dict[str, str] = {}
    if not MIGRATION_SQL.exists():
        return out
    import re
    pat = re.compile(
        r"UPDATE ratings SET task_id = '([^']+)' WHERE task_id = '([^']+)'"
    )
    for line in MIGRATION_SQL.read_text(encoding="utf-8").splitlines():
        m = pat.search(line)
        if m:
            out[m.group(2)] = m.group(1)  # old -> new
    return out


def main():
    env = load_env(ENV_FILE)
    url = env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not key:
        print("[ERR] NEXT_PUBLIC_SUPABASE_URL / ANON_KEY not found in .env.local")
        sys.exit(1)

    from supabase import create_client

    print("[1/5] Connecting to Supabase + signing in anonymously...")
    sb = create_client(url, key)
    auth_resp = sb.auth.sign_in_anonymously()
    if not auth_resp or not auth_resp.user:
        print("[ERR] Anonymous sign-in failed.")
        sys.exit(1)
    print(f"      Signed in as anon uid={auth_resp.user.id[:8]}...")

    print("\n[2/5] Pulling all ratings rows...")
    # Paginiraj kroz Supabase default 1000-row limit
    rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.table("ratings")
            .select("task_id, rater_uuid, difficulty, time_est_minutes, created_at")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        chunk = resp.data or []
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size
    print(f"      Pulled {len(rows)} rating rows")

    if not rows:
        print("      (No ratings yet, writing empty aggregates file.)")
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text("[]", encoding="utf-8")
        return

    print("\n[3/5] Loading current tasks.json + migration map...")
    with open(TASKS_JSON, encoding="utf-8") as f:
        tasks_manifest = json.load(f)
    valid_task_ids = {t["task_id"] for t in tasks_manifest["tasks"]}
    migration_map = load_migration_map()
    print(f"      {len(valid_task_ids)} valid task_ids, {len(migration_map)} migration mappings")

    # Apply migration map: if rating has old task_id, remap to new
    remapped = 0
    orphan = 0
    df = pd.DataFrame(rows)
    df["task_id"] = df["task_id"].astype(str)
    def remap(tid):
        nonlocal remapped, orphan
        if tid in valid_task_ids:
            return tid
        if tid in migration_map and migration_map[tid] in valid_task_ids:
            remapped += 1
            return migration_map[tid]
        orphan += 1
        return None
    df["task_id_mapped"] = df["task_id"].map(remap)
    df = df[df["task_id_mapped"].notna()].copy()
    df["task_id"] = df["task_id_mapped"]
    df.drop(columns=["task_id_mapped"], inplace=True)
    print(f"      Remapped (old->new): {remapped}")
    print(f"      Orphaned (no match): {orphan}")
    print(f"      Usable ratings:      {len(df)}")

    print("\n[4/5] Computing per-task aggregates (median difficulty, median time)...")
    agg = (
        df.groupby("task_id")
        .agg(
            n_ratings=("difficulty", "count"),
            median_difficulty=("difficulty", "median"),
            median_time_minutes=("time_est_minutes", lambda s: int(statistics.median([t for t in s if pd.notna(t)])) if any(pd.notna(t) for t in s) else None),
            mean_difficulty=("difficulty", "mean"),
        )
        .reset_index()
    )
    agg["median_difficulty"] = agg["median_difficulty"].astype(float)
    print(f"      {len(agg)} tasks with at least 1 rating")
    print(f"      Average ratings/task: {agg['n_ratings'].mean():.1f}")
    print(f"      Distribution:")
    print(agg["n_ratings"].value_counts().sort_index().to_string())

    print("\n[5/5] Saving aggregates...")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(agg.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"      Saved: {OUT_JSON}  ({len(agg)} task aggregates)")


if __name__ == "__main__":
    main()
