"""
Per-cluster empirijska frekvencija po tipu ispita.

Recommender u exam-modu koristi P(cluster | exam_type) da bi težinski
favorizirao klastere koji se češće pojavljuju u tom ispitu. Ciljana ocjena
zatim određuje koliko striktno se drži te raspodjele (visoka ocjena: pokrij
i rijetke klastere; niska ocjena: samo najčešći).
"""

import json
from pathlib import Path
import pandas as pd


def compute_cluster_frequencies(df: pd.DataFrame) -> dict[str, dict[int, float]]:
    """
    Empirijska raspodjela P(cluster | exam_type) iz prošlih ispita.

    Returns: {"MI": {0: 0.12, 1: 0.00, ...}, "ZI": {...}}
    Frekvencije unutar jednog exam_type sumiraju u 1.0; klasteri koji se
    ne pojavljuju u tom tipu ispita imaju 0.
    """
    result: dict[str, dict[int, float]] = {}
    all_clusters = sorted(df["cluster_id"].unique().tolist())

    for exam_type in sorted(df["exam_type"].unique()):
        subset = df[df["exam_type"] == exam_type]
        counts = subset["cluster_id"].value_counts()
        total = float(counts.sum())
        freq = {int(cid): float(counts.get(cid, 0)) / total for cid in all_clusters}
        result[str(exam_type)] = freq

    return result


def save_cluster_frequencies(
    df: pd.DataFrame,
    out_path: Path,
) -> dict[str, dict[int, float]]:
    """Izračunaj frekvencije i serijaliziraj kao JSON."""
    freq = compute_cluster_frequencies(df)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(freq, f, ensure_ascii=False, indent=2)
    return freq
