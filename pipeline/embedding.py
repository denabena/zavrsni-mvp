"""Računanje vector embeddinga za task tekstove."""

import numpy as np

from pipeline.config import EMBEDDING_MODEL


def compute_embeddings(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    print(f"  Učitavam model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"  Računam embeddings za {len(texts)} zadataka...")
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=32
    )
    return embeddings  # shape: (N, 384)
