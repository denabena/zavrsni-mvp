"""
Učitavanje ulaznih artefakata za recommender. Single source of truth da
solver i Streamlit UI dijele istu pripremu podataka.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.config import OUT_DIR


TASKS_CSV = OUT_DIR / "tasks_with_clusters.csv"
CLUSTER_FREQ_JSON = OUT_DIR / "cluster_frequencies.json"
AGGREGATES_JSON = OUT_DIR / "task_aggregates.json"


def load_tasks() -> pd.DataFrame:
    """
    Učitaj tasks_with_clusters.csv i ako postoji task_aggregates.json,
    merge-aj median_difficulty i median_time_minutes u DataFrame.
    Inače ostavi te stupce prazne (solver će fallbackat na heuristiku).
    """
    df = pd.read_csv(TASKS_CSV)
    if AGGREGATES_JSON.exists():
        with open(AGGREGATES_JSON, encoding="utf-8") as f:
            agg = json.load(f)
        agg_df = pd.DataFrame(agg)
        df = df.merge(agg_df, on="task_id", how="left")
    else:
        df["median_difficulty"] = None
        df["median_time_minutes"] = None
        df["n_ratings"] = 0
    return df


def load_cluster_frequencies() -> dict[str, dict[int, float]]:
    """Učitaj P(cluster | exam_type) iz cluster_frequencies.json."""
    if not CLUSTER_FREQ_JSON.exists():
        return {}
    with open(CLUSTER_FREQ_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    return {et: {int(cid): float(p) for cid, p in d.items()} for et, d in raw.items()}


def cluster_label_map(tasks: pd.DataFrame) -> dict[int, str]:
    """Mapping cluster_id -> najčešći cluster_label u DataFrameu."""
    if "cluster_label" not in tasks.columns:
        return {}
    return (
        tasks.groupby("cluster_id")["cluster_label"]
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")
        .to_dict()
    )
