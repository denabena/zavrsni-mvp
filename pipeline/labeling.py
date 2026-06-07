"""
LLM labeling klastera preko Ollame.

Stari pristup (po-klaster) je davao kolapsne labele jer su isti few-shot
primjeri u promptu sidrili model na "Rasuto adresiranje" za većinu klastera.
Sada se svi klasteri šalju u jednom pozivu uz hard zahtjev za međusobno
različitim labelama; LLM tako vidi kontekst i mora razlučiti teme.
"""

import json
import re

import pandas as pd
import requests

from pipeline.config import OLLAMA_MODEL, OLLAMA_URL


def _build_batch_prompt(samples_per_cluster: dict[int, list[str]]) -> str:
    """Jedan prompt za sve klastere s eksplicitnim "must be distinct" zahtjevom."""
    blocks = []
    for cid in sorted(samples_per_cluster.keys()):
        samples = samples_per_cluster[cid]
        sample_block = "\n".join(
            f"  - {t[:180].strip()}" for t in samples[:3]
        )
        blocks.append(f"Klaster {cid}:\n{sample_block}")

    clusters_text = "\n\n".join(blocks)
    n = len(samples_per_cluster)
    return f"""Imenuj svaki od {n} klastera ispitnih zadataka iz Algoritama i struktura podataka kratkom hrvatskom etiketom (2-4 riječi).

PRAVILA:
- SVAKA etiketa mora biti različita od svih ostalih.
- Ne koristi generika ("Razno", "Mješovito").
- Mogući primjeri tema: Sortiranje, Raspršeno adresiranje, Binarno stablo, Povezana lista, Stog, Red, Graf, Rekurzija, Složenost algoritama, Niz, KMP, Hash tablica, Pretraga, Dinamička alokacija.
- Etikete u nominativu, prvo slovo veliko.

FORMAT: točno {n} redova, svaki oblika "N: Etiketa" gdje je N broj klastera. Bez dodatnog teksta.

PRIMJER FORMATA:
0: Sortiranje
1: Binarno stablo
2: Stog operacije

UZORCI:

{clusters_text}

ODGOVOR ({n} redova, "N: Etiketa"):"""


def _parse_batch_response(raw: str, n_clusters: int) -> dict[int, str]:
    """Izvuci {cid: label} iz LLM line-based odgovora ("N: Label")."""
    result: dict[int, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\**\s*(\d+)\s*[:.\-]\s*(.+?)\s*\**$", line)
        if not m:
            continue
        try:
            cid = int(m.group(1))
        except ValueError:
            continue
        if cid < 0 or cid >= n_clusters:
            continue
        label = m.group(2).strip().strip('"').strip("'").rstrip(".")
        # Otresi sufikse poput "(2-4 riječi)" iz primjera
        label = re.sub(r"\s*\([^)]*\)\s*$", "", label).strip()
        if label and cid not in result:
            result[cid] = label
    return result


def _force_distinct(labels: dict[int, str], n_clusters: int) -> dict[int, str]:
    """
    Post-processing safety net: ako LLM svejedno proizvede duplikate, sufiksiraj
    drugu (i kasnije) pojavu rednim brojem klastera da je svaka labela jedinstvena.
    """
    seen: dict[str, int] = {}
    out: dict[int, str] = {}
    for cid in range(n_clusters):
        label = labels.get(cid)
        if not label:
            out[cid] = f"Klaster {cid}"
            continue
        key = label.lower()
        if key in seen:
            out[cid] = f"{label} (klaster {cid})"
        else:
            seen[key] = cid
            out[cid] = label
    return out


def label_clusters(df: pd.DataFrame, n_clusters: int) -> dict[int, str]:
    """Vraća {cluster_id: label} za sve klastere u jednom batch pozivu Ollame."""
    print(f"  Generiram labele za {n_clusters} klastera u jednom batch pozivu...")

    samples_per_cluster: dict[int, list[str]] = {}
    for cid in range(n_clusters):
        mask = df["cluster_id"] == cid
        texts = df.loc[mask, "task_text"].tolist()
        samples_per_cluster[cid] = texts

    prompt = _build_batch_prompt(samples_per_cluster)

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=180,
        )
        r.raise_for_status()
        raw = r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"    [WARN] Ollama greška: {e}")
        return {cid: f"Klaster {cid}" for cid in range(n_clusters)}

    parsed = _parse_batch_response(raw, n_clusters)
    if len(parsed) < n_clusters // 2:
        print("    [DEBUG] LLM raw output (parsing weak):")
        print(raw[:1500])
        print("    [...]" if len(raw) > 1500 else "")
    labels = _force_distinct(parsed, n_clusters)

    for cid in range(n_clusters):
        n_tasks = int((df["cluster_id"] == cid).sum())
        print(f"    Klaster {cid:2d}: {labels[cid]}  ({n_tasks} zadataka)")

    return labels
