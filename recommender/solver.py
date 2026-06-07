"""
Knapsack solver za preporuku zadataka za vježbu.

Kraljevski problem: ograničeno vrijeme korisnika, max učenje. Klasični 0/1
knapsack ne hvata želju za raznolikošću tema, pa koristimo greedy-with-state
gdje vrijednost zadatka pada eksponencijalno s brojem već odabranih zadataka
iz istog klastera (diminishing returns). Time se prirodno prvo pokriju različiti
klasteri, a tek onda dubina unutar njih.

Tri komponente vrijednosti (osnovne, prije diminishing returns):
  - frequency_bonus: koliko se klaster pojavljuje u ciljanom exam_type
                     (samo exam-mode; topic-mode koristi uniform 1.0)
  - difficulty_bonus: niža težina -> veća vrijednost (lakše = brže razumiješ)
  - centroid_bonus:   bliže centroidu klastera -> veća vrijednost
                     (tipičniji predstavnik kategorije)

U exam-modu ciljana ocjena određuje hard cutoff za outliere: korisnik koji cilja
prolaz dobiva samo "core" zadatke, korisnik koji cilja peticu dobiva sve, pa i
periferne detalje.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd


class Mode(str, Enum):
    TOPIC = "topic"
    EXAM = "exam"


# Default fallback težine i vremena za zadatke bez dovoljno ratinga.
DEFAULT_DIFFICULTY = 3.0
DEFAULT_TIME_MIN = 30.0

# Diminishing returns: vrijednost k-tog zadatka iz klastera = base * DECAY^(k-1).
# 0.7 znači da drugi zadatak iz istog klastera ima 70% vrijednost, treći 49% itd.
CLUSTER_DECAY = 0.7

# Težinski koeficijenti za bazičnu vrijednost. Mijenjati ako se eksperimentalno
# pokaže da se neka komponenta predoznačuje.
W_FREQ = 1.0
W_DIFFICULTY = 1.0
W_CENTROID = 1.0


@dataclass
class RecommenderConfig:
    """
    Konfiguracija jednog poziva recommendera.

    Polja po modu:
      TOPIC: chosen_clusters + time_budget_minutes
      EXAM:  chosen_exam_types + target_grade + time_budget_minutes
    """

    mode: Mode
    time_budget_minutes: int

    # TOPIC mode
    chosen_clusters: list[int] = field(default_factory=list)

    # EXAM mode
    chosen_exam_types: list[str] = field(default_factory=list)
    target_grade: float = 100.0  # 0..100, viša ocjena -> manje filtriranja outliera

    # Tuning (rijetko se mijenja)
    cluster_decay: float = CLUSTER_DECAY


def _outlier_cutoff(target_grade: float) -> float:
    """
    Mapiranje ciljane ocjene na maksimalni dopušteni centroid_outlier_score.

    grade 0%   -> 0.0  (samo centralni, najtipičniji zadaci po klasteru)
    grade 50%  -> 0.5
    grade 100% -> 1.0  (svi)

    Linearno mapiranje je svjesno jednostavno: paper-friendly i lako objašnjivo.
    """
    g = max(0.0, min(100.0, target_grade))
    return g / 100.0


def _filter_eligible(
    tasks: pd.DataFrame,
    cfg: RecommenderConfig,
) -> pd.DataFrame:
    """Hard filter: samo zadaci koji zadovoljavaju mode + ograničenja."""
    df = tasks.copy()

    if cfg.mode == Mode.TOPIC:
        if not cfg.chosen_clusters:
            return df.iloc[0:0]
        df = df[df["cluster_id"].isin(cfg.chosen_clusters)]

    elif cfg.mode == Mode.EXAM:
        if not cfg.chosen_exam_types:
            return df.iloc[0:0]
        df = df[df["exam_type"].isin(cfg.chosen_exam_types)]
        cutoff = _outlier_cutoff(cfg.target_grade)
        df = df[df["centroid_outlier_score"] <= cutoff]

    return df


def _base_value(
    row: pd.Series,
    cluster_freq: dict[str, dict[int, float]],
    cfg: RecommenderConfig,
) -> float:
    """
    Vrijednost zadatka prije diminishing returns. Tri kombinirana faktora.
    """
    # Frequency: samo exam mode.
    if cfg.mode == Mode.EXAM and cluster_freq:
        cid = int(row["cluster_id"])
        freqs = [
            cluster_freq.get(et, {}).get(cid, 0.0) for et in cfg.chosen_exam_types
        ]
        freq_bonus = sum(freqs) / max(1, len(freqs))
    else:
        freq_bonus = 1.0

    # Difficulty: 1 (najlakše) -> 1.0; 5 (najteže) -> 0.2.
    difficulty = _coerce_float(row.get("median_difficulty"), DEFAULT_DIFFICULTY)
    difficulty = max(1.0, min(5.0, difficulty))
    difficulty_bonus = (6.0 - difficulty) / 5.0

    # Centroid: 0 (centar) -> 1.0; 1 (rub) -> 0.5.
    outlier = _coerce_float(row.get("centroid_outlier_score"), 0.5)
    outlier = max(0.0, min(1.0, outlier))
    centroid_bonus = 1.0 - 0.5 * outlier

    return (
        W_FREQ * freq_bonus
        + W_DIFFICULTY * difficulty_bonus
        + W_CENTROID * centroid_bonus
    )


def _coerce_float(value, default: float) -> float:
    """Helper: pretvori None/NaN/string -> float ili default."""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(f):
        return default
    return f


def _task_time(row: pd.Series) -> float:
    """Vrijeme zadatka u minutama, s fallbackom ako ratinga nema."""
    t = _coerce_float(row.get("median_time_minutes"), float("nan"))
    if math.isnan(t):
        t = _coerce_float(row.get("time_est"), DEFAULT_TIME_MIN)
    return max(1.0, t)


@dataclass
class Recommendation:
    """Rezultat recommendera. Lista zadataka + agregati za prikaz."""

    tasks: pd.DataFrame
    total_time_minutes: float
    cluster_coverage: dict[int, int]  # cluster_id -> koliko zadataka odabrano
    score_total: float

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)


def recommend(
    tasks: pd.DataFrame,
    cluster_freq: dict[str, dict[int, float]],
    cfg: RecommenderConfig,
) -> Recommendation:
    """
    Greedy knapsack s diminishing returns po klasteru.

    Na svakom koraku biramo zadatak s najvećim value/time omjerom, gdje value
    je base_value(task) * decay^(broj već odabranih iz tog klastera).
    Stajemo kad više nijedan eligible zadatak ne stane u preostali budžet.

    Tasks df mora imati stupce:
      task_id, cluster_id, exam_type, centroid_outlier_score,
      median_difficulty (ili fallback time_est+difficulty_guess), median_time_minutes
    """
    eligible = _filter_eligible(tasks, cfg)
    if eligible.empty:
        return Recommendation(
            tasks=eligible,
            total_time_minutes=0.0,
            cluster_coverage={},
            score_total=0.0,
        )

    available_idx = set(eligible.index.tolist())
    picks_per_cluster: dict[int, int] = defaultdict(int)
    selected_idx: list[int] = []
    time_used = 0.0
    score_total = 0.0

    budget = float(cfg.time_budget_minutes)
    decay = cfg.cluster_decay

    while available_idx:
        best_idx: Optional[int] = None
        best_vpm = -math.inf
        best_value = 0.0
        best_time = 0.0

        for idx in available_idx:
            row = eligible.loc[idx]
            t = _task_time(row)
            if time_used + t > budget:
                continue
            cid = int(row["cluster_id"])
            base = _base_value(row, cluster_freq, cfg)
            value = base * (decay ** picks_per_cluster[cid])
            vpm = value / t
            if vpm > best_vpm:
                best_vpm = vpm
                best_idx = idx
                best_value = value
                best_time = t

        if best_idx is None:
            break

        selected_idx.append(best_idx)
        available_idx.remove(best_idx)
        cid = int(eligible.loc[best_idx, "cluster_id"])
        picks_per_cluster[cid] += 1
        time_used += best_time
        score_total += best_value

    selected_df = eligible.loc[selected_idx].copy()
    selected_df["__order"] = range(len(selected_df))

    return Recommendation(
        tasks=selected_df,
        total_time_minutes=time_used,
        cluster_coverage={cid: n for cid, n in picks_per_cluster.items() if n > 0},
        score_total=score_total,
    )
