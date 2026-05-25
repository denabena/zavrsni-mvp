"""LLM labeling klastera preko Ollama."""

import re
import requests
import pandas as pd

from pipeline.config import OLLAMA_URL, OLLAMA_MODEL


def _clean_label(raw: str, cluster_id: int) -> str:
    """Izvuci čistu etiketu iz LLM odgovora."""
    raw = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", raw)
    raw = re.sub(r'["`‘’]', "", raw)
    raw = re.sub(r"\s*\(.*?\)", "", raw)
    raw = re.sub(r"(?i)^(label|etiketa|klaster\s*\d*)\s*[:–-]\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"^\s*\d+\.\s*", "", raw, flags=re.MULTILINE)

    lines = [l.strip().rstrip(".") for l in raw.splitlines() if l.strip()]
    skip = ("note", "zadatak", "ovdje", "ovo", "here", "klaster oznac")

    candidates = []
    for line in lines:
        words = line.split()
        if 2 <= len(words) <= 6 and not any(line.lower().startswith(p) for p in skip):
            line = re.split(r"[,;]", line)[0].strip()
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
