"""
LLM klasifikacija zadataka u fiksnu taksonomiju.

Za svaki zadatak šaljemo task_text + listu kategorija Ollami i tražimo da
izabere TOČNO jednu. Bez K-means koraka između. Direktna kategorizacija.
"""

from __future__ import annotations

import re

import pandas as pd
import requests

from pipeline.config import OLLAMA_MODEL, OLLAMA_URL


TAXONOMY: list[str] = [
    "Sortiranje",
    "Stog",
    "Red",
    "Vezana lista",
    "Binarno stablo",
    "Gomila",
    "Hash tablica",
    "Graf",
    "Rekurzija",
    "Složenost algoritama",
    "KMP",
    "Razno",
]


def _build_prompt(task_text: str, taxonomy: list[str]) -> str:
    cats = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(taxonomy))
    return f"""Klasificiraj sljedeći zadatak iz kolegija "Algoritmi i strukture podataka" u TOČNO JEDNU od ovih kategorija. Pažljivo pročitaj tekst i odluči koja struktura podataka ili algoritam je glavni FOKUS zadatka.

KATEGORIJE:
{cats}

UPUTE:
- Ako zadatak traži implementaciju funkcije NAD strukturom podataka (npr. funkcija nad stogom, redom, povezanom listom, binarnim stablom), kategorija je TA struktura, čak i ako se koristi rekurzija.
- Rekurzija se bira SAMO kad je rekurzivni algoritam glavna tema, a ne struktura (npr. rekurzivno brojanje, rekurzivna analiza).
- Složenost algoritama: zadaci koji traže analizu vremena izvođenja (O, Ω, Θ notacija) ili apriornu/asimptotsku analizu.
- Sortiranje: ilustracije sortirajućih algoritama (quicksort, shellsort, bubble, insertion, heapsort itd.) ILI implementacija sortiranja. Heapsort koji koristi gomilu i dalje je Sortiranje, osim ako je fokus na izgradnji gomile.
- Gomila: zadaci o izgradnji ili svojstvima min/max heap-a.
- Hash tablica: raspršeno adresiranje, hash funkcije, raspršeno adresiranje datoteka - sve je Hash tablica.
- Vezana lista: jednostruko/dvostruko povezane liste, atomi, čvorovi.
- KMP: zadaci o KMP algoritmu, LPS polju, traženju uzorka u nizu.
- Razno koristi SAMO ako zadatak ne odgovara nijednoj drugoj kategoriji (npr. AI/heuristički algoritmi, sasvim atipični zadaci).

TEKST ZADATKA:
\"\"\"
{task_text}
\"\"\"

Odgovori SAMO imenom JEDNE kategorije s popisa iznad. Bez navodnika, bez objašnjenja, bez brojeva, bez ikakvog dodatnog teksta. Primjer ispravnog odgovora:
Stog"""


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _extract_category(raw: str, taxonomy: list[str]) -> str:
    """Pokušaj izvući ime kategorije iz LLM odgovora."""
    # Uzmi prvi neprazan red, očisti.
    candidate = ""
    for line in raw.splitlines():
        line = line.strip().strip("*").strip('"').strip("'").rstrip(".:")
        # Skini eventualni vodeći broj "1." ili "1)"
        line = re.sub(r"^\d+\s*[.\)]\s*", "", line).strip()
        if line:
            candidate = line
            break
    if not candidate:
        return "Razno"

    norm = _normalize(candidate)

    # Egzaktni match
    for cat in taxonomy:
        if _normalize(cat) == norm:
            return cat

    # Sadržan u kategoriji ili kategorija sadržana u odgovoru
    for cat in taxonomy:
        cn = _normalize(cat)
        if cn in norm or norm in cn:
            return cat

    # Heuristika: stem-prefix match (prvih 5 znakova)
    for cat in taxonomy:
        if len(cat) >= 5 and _normalize(cat)[:5] in norm:
            return cat

    return "Razno"


def classify_task(task_text: str, taxonomy: list[str] | None = None) -> str:
    """Klasificiraj jedan zadatak. Vrati ime kategorije iz taksonomije."""
    tax = taxonomy or TAXONOMY
    prompt = _build_prompt(task_text[:2200], tax)

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=120,
        )
        r.raise_for_status()
        raw = r.json()["message"]["content"].strip()
        return _extract_category(raw, tax)
    except Exception as e:
        print(f"    [WARN] LLM greška: {e}")
        return "Razno"


def classify_all_tasks(
    df: pd.DataFrame,
    taxonomy: list[str] | None = None,
) -> dict[str, str]:
    """Klasificiraj sve zadatke u df-u. Vrati {task_id: category_name}."""
    tax = taxonomy or TAXONOMY
    results: dict[str, str] = {}
    total = len(df)
    for i, row in enumerate(df.itertuples(index=False), 1):
        tid = getattr(row, "task_id")
        text = getattr(row, "task_text") or ""
        if isinstance(text, float):  # NaN
            text = ""
        cat = classify_task(str(text), tax)
        results[tid] = cat
        if i % 10 == 0 or i == total:
            print(f"    [{i}/{total}] {tid}: {cat}")
    return results
