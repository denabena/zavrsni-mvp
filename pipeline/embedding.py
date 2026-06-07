"""Računanje vector embeddinga za task tekstove."""

import numpy as np

from pipeline.config import EMBEDDING_MODEL


def compute_embeddings(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    print(f"  Učitavam model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # e5 familija zahtijeva "passage: " prefix za dokumente (i "query: " za
    # upite). Bez prefixa rezultati su znatno slabiji.
    is_e5 = "e5" in EMBEDDING_MODEL.lower()
    if is_e5:
        prepared = [f"passage: {t}" for t in texts]
    else:
        prepared = texts

    print(f"  Računam embeddings za {len(texts)} zadataka (e5_prefix={is_e5})...")
    embeddings = model.encode(
        prepared,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=8 if is_e5 else 32,  # e5-large troši više VRAM/RAM
    )
    return embeddings
