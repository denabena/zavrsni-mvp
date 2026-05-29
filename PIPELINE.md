# Pipeline workflow

Kratki overview kako PDF -> embeddings -> klasteri -> asp-rate vizualizacija
funkcionira u ovom projektu. Cilj: brzo se podsjetiti što-radi-što bez čitanja
koda.

---

## Layout

```
zavrsni-mvp/
├── static/                       # ULAZ: PDF-ovi ispita (MI, ZI)
├── data/                         # ULAZ: CSV s metapodacima (points, type, ...)
├── pipeline/                     # Python paket s logikom
│   ├── config.py                 # env-var-driven config
│   ├── parsing.py                # PDF -> tekst -> segmentirani zadaci
│   ├── merge.py                  # spajanje zadataka s CSV-om
│   ├── embedding.py              # sentence-transformers -> vektori
│   ├── clustering.py             # UMAP + K-means + outlier scoring
│   └── labeling.py               # Ollama imenuje klastere
├── embed_pipeline.py             # CLI: orkestrira sve korake
├── analyze_clusters.py           # CLI: dijagnostika + preporuka k
├── render_task_images.py         # CLI: PDF stranice -> PNG-ovi za asp-rate
├── embeddings/                   # IZLAZ: .npy, .csv, .json, plotovi
└── asp-rate/                     # Next.js webapp (zasebni dio)
```

---

## Workflow (korak po korak)

### 1. Parsing: `pipeline/parsing.py`
- `fitz` (PyMuPDF) izvlači tekst po stranicama.
- Cijeli PDF se spaja u jedan string + tablica offseta za svaku stranicu
  (omogućava da svaki zadatak zna iz koje je stranice došao -> `pdf_page`).
- Regex `_EXAM_HEADER` dijeli na ispite (jedan PDF = više ispita).
- Regex `_TASK_MARKER` dijeli ispit na zadatke.
- `_clean_task_text` makne "JMBAG", "IME I PREZIME", napomene o bodovima itd.
- Output: `list[dict]` s `{exam_type, exam_date, task_no, task_text, pdf_page}`.

### 2. Merge: `pipeline/merge.py`
- Učitava `data/asp_index_last3_mi_last3_zi.csv` (`points`, `time_est`, `type`, ...).
- Left-join s parsiranim zadacima po `(exam_type, exam_date, task_no)`.
- Konstruira `task_id` u obliku `MI|2025-11-28|1`.
- Trenutno se podudara samo ~28/196 zadataka. CSV nije potpun, ostali zadaci
  jednostavno nemaju metapodatke (ne kvari ostatak pipelinea).

### 3. Embedding: `pipeline/embedding.py`
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (multilingual, 384D, podržava hrvatski).
- `normalize_embeddings=True` -> vektori su L2-normalizirani (cosine ≈ euclidean).
- Sprema u `embeddings/embeddings.npy`, shape `(N, 384)`.

### 4. Clustering: `pipeline/clustering.py`
- **Bitno**: prvo UMAP redukcija u 10D (`reduce_with_umap`), pa K-means.
  Sirovi 384D prostor je previše rijedak za stabilan K-means. UMAP zgusne
  klastere i daje znatno bolje silhouette + ARI rezultate.
- `n_init=50` -> svaki K-means uzima najbolji od 50 inicijalizacija.
- `compute_outlier_scores`: prosječna cosine udaljenost do 5 najbližih susjeda.
  Visok score = task ne pripada nigdje -> kandidat za reviziju klastera.

### 5. Labeling: `pipeline/labeling.py`
- Za svaki klaster uzima 5 uzoraka i šalje ih lokalnom Ollami (`llama3.1`).
- Prompt s few-shot primjerima traži 2-4 riječi.
- `_clean_label` post-processira (makne navodnike, numeriranje, parenteze).
- Ako Ollama nije dostupan -> fallback `Klaster N`.

---

## Choosing k (`analyze_clusters.py`)

Pokreni **prije** `embed_pipeline.py` da odlučiš koliko klastera koristiti:

```bash
python analyze_clusters.py
```

Što radi:
- Sweepa `k = 5..25` u UMAP-reduciranom prostoru.
- Za svaki k pokreće K-means 10 puta s različitim seedovima.
- Mjeri:
  - **silhouette**: koliko su klasteri dobro separirani
  - **ARI** (Adjusted Rand Index) između parova runova: koliko je rezultat
    stabilan između različitih inicijalizacija
  - **inertia**: za elbow plot
- Spremaa: `embeddings/cluster_sweep.{png,csv}` + `cluster_umap_2d.png`.
- Ispiše preporučeni k (max z-score(silhouette) + z-score(ARI), s rubnim
  penaltyjem).

Trenutna preporuka: **k = 15** (silhouette 0.61, ARI 0.98).

---

## Pokretanje

### Sve odjednom (s preporučenim k)
```bash
N_CLUSTERS=15 python embed_pipeline.py
```

### Samo dijagnostika (bez Ollame)
```bash
python analyze_clusters.py
```

### Samo task images za webapp (bez embeddinga)
```bash
python render_task_images.py
```

---

## Env vars (sve opcionalne)

| Variable     | Default                                          | Opis                          |
|--------------|--------------------------------------------------|-------------------------------|
| `N_CLUSTERS` | `15`                                             | broj K-means klastera         |
| `OLLAMA_URL` | `http://localhost:11434/api/chat`                | Ollama API endpoint           |
| `OLLAMA_MODEL` | `llama3.1`                                     | naziv modela                  |
| `CSV_PATH`   | `data/asp_index_last3_mi_last3_zi.csv`           | metadata CSV                  |
| `MI_PDF`     | `static/MI_svi_do_2026.pdf`                      | međuispiti PDF                |
| `ZI_PDF`     | `static/ZI_svi_do_2026.pdf`                      | završni ispiti PDF            |

---

## Outputs

| File                                       | Generated by              |
|--------------------------------------------|---------------------------|
| `embeddings/embeddings.npy`                | `embed_pipeline.py`       |
| `embeddings/tasks_with_clusters.csv`       | `embed_pipeline.py`       |
| `embeddings/cluster_labels.json`           | `embed_pipeline.py`       |
| `embeddings/cluster_sweep.{png,csv}`       | `analyze_clusters.py`     |
| `embeddings/cluster_umap_2d.png`           | `analyze_clusters.py`     |
| `asp-rate/public/task-images/*.png`        | `render_task_images.py`   |
| `asp-rate/public/tasks.json`               | `render_task_images.py`   |

---

## Gdje se širi / mijenja

- **Drugi clustering algoritam**: zamijeni implementaciju
  `pipeline/clustering.py:cluster_embeddings` (npr. HDBSCAN). Sweep
  utility (`sweep_k`, `kmeans_stability_score`) ostaje koristan dok god
  algoritam ima koncept "k".
- **Drugi embedding model**: promijeni `EMBEDDING_MODEL` u `pipeline/config.py`.
- **Drugi LLM za labele**: postavi env `OLLAMA_MODEL=<naziv>`.
- **Novi PDF**: dodaj ga u `static/`, parser će automatski pohvatati ispitne
  blokove iz `_EXAM_HEADER` regexa.
