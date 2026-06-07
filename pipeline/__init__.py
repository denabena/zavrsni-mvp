"""
pipeline
--------
Embedding + clustering pipeline za ASP exam zadatke.

Glavni modul (`embed_pipeline.py`) je tanak CLI driver koji
orkestrira korake iz ovog paketa.
"""

from pipeline.parsing import parse_exam_file
from pipeline.merge import load_and_merge
from pipeline.embedding import compute_embeddings
from pipeline.clustering import (
    cluster_embeddings,
    compute_outlier_scores,
    compute_centroid_outlier_scores,
)
from pipeline.labeling import label_clusters
from pipeline.frequency import (
    compute_cluster_frequencies,
    save_cluster_frequencies,
)

__all__ = [
    "parse_exam_file",
    "load_and_merge",
    "compute_embeddings",
    "cluster_embeddings",
    "compute_outlier_scores",
    "compute_centroid_outlier_scores",
    "label_clusters",
    "compute_cluster_frequencies",
    "save_cluster_frequencies",
]
