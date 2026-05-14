"""
embed_pipeline.py
-----------------
Jednokratna skripta koja:
  1. Parsira MI_svi_do_2026.pdf i ZI_svi_do_2026.pdf (plain-text format)
  2. Segmentira zadatke po markeru "Zadatak N."
  3. Čisti tekst (makni zaglavlja, JMBAG, opće upute)
  4. Spaja s metapodacima iz CSV-a (points, time_est, type, itd.)
  5. Generira embeddinге (paraphrase-multilingual-MiniLM-L12-v2)
  6. Klasterira (KMeans, k=10)
  7. Za svaki klaster poziva lokalni Ollama da generira human-readable label
  8. Sprema:  embeddings/embeddings.npy
              embeddings/tasks_with_clusters.csv

Pokretanje:
  pip install sentence-transformers scikit-learn numpy pandas requests
  python embed_pipeline.py

Env varijable (opcionalno):
  OLLAMA_URL   = http://localhost:11434/api/chat   (default)
  OLLAMA_MODEL = llama3.1                          (default)
  N_CLUSTERS   = 10                                (default)
  CSV_PATH     = data/asp_index_last3_mi_last3_zi.csv
  MI_PDF       = static/MI_svi_do_2026.pdf
  ZI_PDF       = static/ZI_svi_do_2026.pdf
"""

import os
import re
import json
import requests
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
N_CLUSTERS   = int(os.getenv("N_CLUSTERS", "10"))
CSV_PATH     = os.getenv("CSV_PATH", "data/asp_index_last3_mi_last3_zi.csv")
MI_PDF_PATH  = os.getenv("MI_PDF",   "static/MI_svi_do_2026.pdf")
ZI_PDF_PATH  = os.getenv("ZI_PDF",   "static/ZI_svi_do_2026.pdf")
OUT_DIR      = Path("embeddings")


# ══════════════════════════════════════════════════════════════════════════════
# 1.  PARSIRANJE I SEGMENTACIJA
# ══════════════════════════════════════════════════════════════════════════════

# Zaglavlje koje se pojavljuje na svakom ispitu — makni ga iz task teksta
_HEADER_PATTERN = re.compile(
    r"JMBAG IME I PREZIME.*?(?=Zadatak \d+\.)",
    re.DOTALL
)

# Marker koji označava početak zadatka
_TASK_MARKER = re.compile(r"(Zadatak \d+\.\s*\(\d+ bod[^\)]*\)[^\n]*)", re.IGNORECASE)

# Marker koji označava početak novog ispita
_EXAM_HEADER = re.compile(
    r"Algoritmi i strukture podataka\s*[–-]\s*(međuispit|završni ispit)\s*\r?\n([^\r\n]+)",
    re.IGNORECASE
)

# Hrvatska imena mjeseci → broj
_MONTH_MAP = {
    "siječnja": 1,  "veljače": 2,  "ožujka": 3,   "travnja": 4,
    "svibnja":  5,  "lipnja":  6,  "srpnja": 7,   "kolovoza": 8,
    "rujna":    9,  "listopada": 10, "studenoga": 11, "prosinca": 12
}

def _parse_date(raw: str) -> str:
    """'28. studenoga 2025.' → '2025-11-28'"""
    m = re.match(r"(\d+)\.\s+(\w+)\s+(\d{4})", raw.strip())
    if not m:
        return raw.strip().rstrip(".")
    day, month_hr, year = m.group(1), m.group(2).lower(), m.group(3)
    month = _MONTH_MAP.get(month_hr, 0)
    return f"{year}-{month:02d}-{int(day):02d}"


def _clean_task_text(text: str) -> str:
    """Ukloni šum koji nije dio zadatka."""
    # makni opće ispitne napomene koje se ponavljaju
    text = re.sub(r"Ispit donosi maksimalno.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(r"JMBAG[^\n]*\n?", "", text)
    text = re.sub(r"IME I PREZIME[^\n]*\n?", "", text)
    # normaliziraj whitespace
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"^Zadatak\s+\d+\.\s*\(\d+\s+bod[^\)]*\)\s*[–-]?\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def parse_exam_file(path: str, exam_type: str) -> list[dict]:
    """
    Parsira jedan plain-text 'PDF' i vraća listu rječnika:
      {exam_type, exam_date, task_no, task_text, raw_header}
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    records = []
    current_date = "unknown"

    # Podijeli po ispitima
    exam_splits = list(_EXAM_HEADER.finditer(raw))
    if not exam_splits:
        print(f"  [WARN] Nisam pronašao exam headere u {path}")
        exam_blocks = [("unknown", raw)]
    else:
        exam_blocks = []
        for i, m in enumerate(exam_splits):
            date_raw = m.group(2).strip()
            date_str = _parse_date(date_raw)
            start    = m.start()
            end      = exam_splits[i + 1].start() if i + 1 < len(exam_splits) else len(raw)
            exam_blocks.append((date_str, raw[start:end]))

    for exam_date, block in exam_blocks:
        # Unutar bloka podijeli po zadacima
        task_splits = list(_TASK_MARKER.finditer(block))
        if not task_splits:
            continue

        for j, tm in enumerate(task_splits):
            task_no_m = re.search(r"Zadatak (\d+)\.", tm.group(1))
            task_no   = int(task_no_m.group(1)) if task_no_m else j + 1

            t_start = tm.end()
            t_end   = task_splits[j + 1].start() if j + 1 < len(task_splits) else len(block)
            body    = block[t_start:t_end]

            full_text = tm.group(1) + "\n" + body
            cleaned   = _clean_task_text(full_text)

            records.append({
                "exam_type": exam_type,
                "exam_date": exam_date,
                "task_no":   task_no,
                "task_text": cleaned,
            })

    print(f"  Pronađeno {len(records)} zadataka u {path}")
    return records


# ══════════════════════════════════════════════════════════════════════════════
# 2.  SPAJANJE S CSV METAPODACIMA
# ══════════════════════════════════════════════════════════════════════════════

def load_and_merge(records: list[dict], csv_path: str) -> pd.DataFrame:
    df_tasks = pd.DataFrame(records)

    df_csv = pd.read_csv(csv_path, encoding="utf-8")
    df_csv["exam_type"] = df_csv["exam_type"].str.upper().str.strip()
    df_csv["exam_date"] = df_csv["exam_date"].astype(str).str.strip()
    df_csv["task_no"]   = df_csv["task_no"].astype(int)

    df_merged = df_tasks.merge(
        df_csv,
        on=["exam_type", "exam_date", "task_no"],
        how="left"
    )

    # task_id koji će koristiti memory.db
    df_merged["task_id"] = (
        df_merged["exam_type"] + "|" +
        df_merged["exam_date"] + "|" +
        df_merged["task_no"].astype(str)
    )

    n_matched = df_merged["points"].notna().sum()
    n_total   = len(df_merged)
    print(f"  Spajanje: {n_matched}/{n_total} zadataka ima metapodatke iz CSV-a")
    return df_merged


# ══════════════════════════════════════════════════════════════════════════════
# 3.  EMBEDDING
# ══════════════════════════════════════════════════════════════════════════════

def compute_embeddings(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    print(f"  Učitavam model: {model_name}")
    model = SentenceTransformer(model_name)

    print(f"  Računam embeddings za {len(texts)} zadataka...")
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=32
    )
    return embeddings  # shape: (N, 384)


# ══════════════════════════════════════════════════════════════════════════════
# 4.  KLASTERIRANJE
# ══════════════════════════════════════════════════════════════════════════════

def cluster_embeddings(embeddings: np.ndarray, n_clusters: int) -> np.ndarray:
    from sklearn.cluster import KMeans

    print(f"  KMeans klasteriranje (k={n_clusters})...")
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(embeddings)
    return labels


def compute_outlier_scores(embeddings: np.ndarray) -> np.ndarray:
    """Prosječna cosine udaljenost do 5 najbližih susjeda — viša = outlier."""
    from sklearn.neighbors import NearestNeighbors

    nn = NearestNeighbors(n_neighbors=6, metric="cosine")
    nn.fit(embeddings)
    distances, _ = nn.kneighbors(embeddings)
    # distances[:,0] je sam zadatak (0.0), uzimamo 1:
    return distances[:, 1:].mean(axis=1)


# ══════════════════════════════════════════════════════════════════════════════
# 5.  LLM LABELING KLASTERA
# ══════════════════════════════════════════════════════════════════════════════

def _clean_label(raw: str, cluster_id: int) -> str:
    """Izvuci čistu etiketu iz LLM odgovora."""
    import re as _re

    raw = _re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", raw)
    raw = _re.sub(r'["`\u2018\u2019]', "", raw)
    raw = _re.sub(r"\s*\(.*?\)", "", raw)
    raw = _re.sub(r"(?i)^(label|etiketa|klaster\s*\d*)\s*[:–-]\s*", "", raw, flags=_re.MULTILINE)
    raw = _re.sub(r"^\s*\d+\.\s*", "", raw, flags=_re.MULTILINE)

    lines = [l.strip().rstrip(".") for l in raw.splitlines() if l.strip()]
    skip = ("note", "zadatak", "ovdje", "ovo", "here", "klaster oznac")

    candidates = []
    for line in lines:
        words = line.split()
        if 2 <= len(words) <= 6 and not any(line.lower().startswith(p) for p in skip):
            line = _re.split(r"[,;]", line)[0].strip()
            candidates.append(line)

    if candidates:
        candidates.sort(key=lambda x: len(x.split()))
        return candidates[0]

    if lines:
        words = lines[0].split()
        return " ".join(words[:4]) if len(words) > 4 else lines[0]

    return f"Klaster {cluster_id}"


def _ollama_label(cluster_id: int, sample_texts: list[str]) -> str:
    """Poziva Ollamu da imenuje klaster na temelju 5 uzoraka zadataka."""
    samples_fmt = "\n\n".join(
        f"Zadatak {i+1}:\n{t[:300]}" for i, t in enumerate(sample_texts[:5])
    )
    # Stroži prompt: few-shot primjeri pokazuju točno što se očekuje
    prompt = f"""Ti si asistent koji imenuje grupe zadataka s ispita iz algoritama i struktura podataka.
Tvoj jedini zadatak je napisati kratku etiketu od 2 do 4 hrvatske riječi koja opisuje što ovi zadaci imaju zajedničko.

PRAVILA (obavezna):
- Odgovori ISKLJUČIVO etiketom — ništa drugo
- 2 do 4 riječi, bez točke na kraju
- Bez navodnika, bez boldiranja, bez numeriranja
- Bez objašnjenja, bez uvoda, bez napomena

PRIMJERI ispravnih odgovora:
Rasuto adresiranje
Implementacija binarnog stabla
Analiza složenosti funkcija
Rekurzivni algoritmi na stablima
Operacije nad stogom

Evo zadataka za koje trebaš napisati etiketu:
{samples_fmt}

Etiketa (samo 2-4 riječi):"""

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0}
            },
            timeout=60
        )
        r.raise_for_status()
        raw = r.json()["message"]["content"].strip()
        label = _clean_label(raw, cluster_id)
        return label or f"Klaster {cluster_id}"
    except Exception as e:
        print(f"    [WARN] Ollama greška za klaster {cluster_id}: {e}")
        return f"Klaster {cluster_id}"


def label_clusters(df: pd.DataFrame, n_clusters: int) -> dict[int, str]:
    """Vraća {cluster_id: label} za sve klastere."""
    print(f"  Generiram labele za {n_clusters} klastera via Ollama...")
    labels = {}
    for cid in range(n_clusters):
        mask    = df["cluster_id"] == cid
        samples = df.loc[mask, "task_text"].tolist()
        label   = _ollama_label(cid, samples)
        labels[cid] = label
        print(f"    Klaster {cid:2d}: {label}  ({mask.sum()} zadataka)")
    return labels


# ══════════════════════════════════════════════════════════════════════════════
# 6.  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(exist_ok=True)

    # 1. Parsiraj
    print("\n[1/6] Parsiranje PDF-ova...")
    records = []
    records += parse_exam_file(MI_PDF_PATH, "MI")
    records += parse_exam_file(ZI_PDF_PATH, "ZI")
    print(f"  Ukupno: {len(records)} zadataka")

    # 2. Spoji s CSV
    print("\n[2/6] Spajanje s CSV metapodacima...")
    df = load_and_merge(records, CSV_PATH)

    # 3. Embedding
    print("\n[3/6] Računanje embeddings...")
    texts      = df["task_text"].fillna("").tolist()
    embeddings = compute_embeddings(texts)
    np.save(OUT_DIR / "embeddings.npy", embeddings)
    print(f"  Saved: embeddings/embeddings.npy  shape={embeddings.shape}")

    # 4. Klasteriranje
    print("\n[4/6] Klasteriranje...")
    cluster_ids = cluster_embeddings(embeddings, N_CLUSTERS)
    df["cluster_id"] = cluster_ids

    # 5. Outlier score
    print("\n[5/6] Outlier scoring...")
    df["outlier_score"] = compute_outlier_scores(embeddings)
    top_outliers = df.nlargest(10, "outlier_score")[["task_id", "task_text", "outlier_score"]]
    print("  Top 10 outliera:")
    for _, row in top_outliers.iterrows():
        preview = row["task_text"][:60].replace("\n", " ")
        print(f"    [{row['outlier_score']:.3f}] {row['task_id']} — {preview}")

    # 6. LLM labeling
    print("\n[6/6] LLM labeling klastera...")
    cluster_labels = label_clusters(df, N_CLUSTERS)
    df["cluster_label"] = df["cluster_id"].map(cluster_labels)

    # Spremi
    out_csv = OUT_DIR / "tasks_with_clusters.csv"
    cols_to_save = [
        "task_id", "exam_type", "exam_date", "task_no",
        "task_text", "cluster_id", "cluster_label", "outlier_score",
        # metapodaci iz originalnog CSV-a (ako postoje)
        "pdf", "page", "points", "time_est", "efficiency",
        "difficulty_guess", "type", "frequency_score", "concepts", "snippet"
    ]
    cols_present = [c for c in cols_to_save if c in df.columns]
    df[cols_present].to_csv(out_csv, index=False)
    print(f"\n  Saved: {out_csv}  ({len(df)} zadataka)")

    # Spremi i cluster_labels kao JSON (korisno za UI)
    labels_path = OUT_DIR / "cluster_labels.json"
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(cluster_labels, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {labels_path}")

    print("\n✅ embed_pipeline.py završen.")
    print(f"   Klasteri: {N_CLUSTERS}")
    print(f"   Zadataka: {len(df)}")
    print(f"   Matched s CSV: {df['points'].notna().sum()}")


if __name__ == "__main__":
    main()