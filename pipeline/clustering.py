"""
K-means klasteriranje + outlier scoring.

UMAP → low-D → K-means daje znatno stabilnije rezultate na sparse
sentence-embedding prostorima (196 točaka u 384D je rijetko).
"""

import numpy as np


# Default hiperparametri za UMAP redukciju prije K-meansa.
UMAP_N_COMPONENTS = 10
UMAP_N_NEIGHBORS  = 15
UMAP_MIN_DIST     = 0.0
UMAP_METRIC       = "cosine"


def reduce_with_umap(
    embeddings: np.ndarray,
    n_components: int = UMAP_N_COMPONENTS,
    random_state: int = 42,
) -> np.ndarray:
    """UMAP projekcija s fiksiranim seedom za reproduktibilnost."""
    import umap

    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=UMAP_N_NEIGHBORS,
        min_dist=UMAP_MIN_DIST,
        metric=UMAP_METRIC,
        random_state=random_state,
    )
    return reducer.fit_transform(embeddings)


def cluster_embeddings(
    embeddings: np.ndarray,
    n_clusters: int,
    use_umap: bool = True,
    random_state: int = 42,
) -> np.ndarray:
    """
    K-means na UMAP-reduciranom prostoru.
    `use_umap=False` vraća stari ponašaj (K-means direktno na 384D).
    """
    from sklearn.cluster import KMeans

    X = reduce_with_umap(embeddings, random_state=random_state) if use_umap else embeddings
    print(f"  KMeans klasteriranje (k={n_clusters}, prostor={X.shape[1]}D, UMAP={use_umap})...")
    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=50)
    return km.fit_predict(X)


def compute_outlier_scores(embeddings: np.ndarray) -> np.ndarray:
    """Prosječna cosine udaljenost do 5 najbližih susjeda — viša = outlier."""
    from sklearn.neighbors import NearestNeighbors

    nn = NearestNeighbors(n_neighbors=6, metric="cosine")
    nn.fit(embeddings)
    distances, _ = nn.kneighbors(embeddings)
    return distances[:, 1:].mean(axis=1)


# ── Stability analiza ─────────────────────────────────────────────────────────

def kmeans_stability_score(
    X: np.ndarray,
    n_clusters: int,
    n_runs: int = 10,
    base_seed: int = 0,
) -> tuple[float, float, np.ndarray]:
    """
    Mjera stabilnosti K-meansa: pokreni n_runs puta s različitim seedovima
    i izračunaj prosječni Adjusted Rand Index između svih parova rezultata.

    Vraća: (mean_ari, mean_silhouette, best_labels)
      - mean_ari ∈ [-1, 1] — viši = stabilnije (1.0 = identični rezultati)
      - mean_silhouette ∈ [-1, 1] — viši = bolja separacija klastera
      - best_labels = labele iz najnižeg-inertia run-a
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score, silhouette_score

    labels_runs: list[np.ndarray] = []
    inertias: list[float] = []
    sils: list[float] = []

    for i in range(n_runs):
        km = KMeans(n_clusters=n_clusters, random_state=base_seed + i, n_init=10)
        labels = km.fit_predict(X)
        labels_runs.append(labels)
        inertias.append(km.inertia_)
        try:
            sils.append(silhouette_score(X, labels))
        except Exception:
            sils.append(float("nan"))

    aris = []
    for i in range(len(labels_runs)):
        for j in range(i + 1, len(labels_runs)):
            aris.append(adjusted_rand_score(labels_runs[i], labels_runs[j]))

    best_idx = int(np.argmin(inertias))
    return (
        float(np.mean(aris)) if aris else 1.0,
        float(np.nanmean(sils)),
        labels_runs[best_idx],
    )


def sweep_k(
    embeddings: np.ndarray,
    k_min: int = 5,
    k_max: int = 25,
    n_runs: int = 10,
    use_umap: bool = True,
    random_state: int = 42,
) -> dict:
    """
    Za svaki k u [k_min, k_max]: pokreni K-means n_runs puta i izračunaj
    inercu, silhouette i ARI stabilnost.

    Vraća dict s listama jednake duljine: ks, inertias, silhouettes, aris.
    """
    from sklearn.cluster import KMeans

    X = reduce_with_umap(embeddings, random_state=random_state) if use_umap else embeddings

    ks, inertias, silhouettes, aris = [], [], [], []
    for k in range(k_min, k_max + 1):
        # Inercija s najboljim od 50 inicijalizacija (kao u glavnom pipelineu)
        km = KMeans(n_clusters=k, random_state=random_state, n_init=50)
        km.fit(X)
        ari, sil, _ = kmeans_stability_score(X, k, n_runs=n_runs, base_seed=0)

        ks.append(k)
        inertias.append(km.inertia_)
        silhouettes.append(sil)
        aris.append(ari)
        print(f"    k={k:2d}  inertia={km.inertia_:8.2f}  silhouette={sil:+.3f}  ARI={ari:+.3f}")

    return {
        "ks": ks,
        "inertias": inertias,
        "silhouettes": silhouettes,
        "aris": aris,
        "X": X,  # UMAP-reducirano za daljnju upotrebu
    }
