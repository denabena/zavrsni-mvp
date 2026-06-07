"""
compare_llm_to_corrections.py
-----------------------------
Usporedi LLM klasifikaciju u embeddings/llm_classification/ s korisničkim
ručnim ispravcima. Daje agreement broj i listu slučajeva.
"""

import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


CORRECTIONS = {
    "MI|2023-11-27|4": "stog",
    "MI|2019-11-25|3": "vezana lista",
    "MI|2016-04-26|3": "stog",
    "MI|2014-04-23|2": "rekurzija",
    "MI|2014-04-23|3": "rekurzija",
    "MI|2013-04-23|4": "pretraga",
    "MI|2012-04-25|3": "slozenost",
    "MI|2011-03-21|4": "slozenost",
    "MI|2011-03-21|5": "stog",
    "MI|2011-05-02|1": "stog",
    "MI|2011-05-02|2": "red",
    "MI|2011-05-02|3": "rekurzija",
    "MI|2011-05-02|5": "vezana lista",
    "MI|2011-05-02|6": "slozenost",
    "MI|2010-03-29|4": "slozenost",
    "MI|2010-03-29|6": "stog",
    "MI|2010-05-10|1": "stog",
    "MI|2010-05-10|2": "red",
    "MI|2010-05-10|5": "sortiranje",
    "MI|2010-05-10|6": "stog",
    "MI|2009-05-22|1": "stog or rekurzija",
    "MI|2009-05-22|3": "red",
    "MI|2009-05-22|4": "stog",
    "MI|2009-04-09|3": "slozenost",
    "MI|2008-03-19|1": "stog",
    "MI|2008-03-19|3": "slozenost",
    "MI|2008-05-07|1": "rekurzija",
    "MI|2008-05-07|2": "stog",
    "MI|2008-05-07|4": "red",
    "ZI|2026-02-06|2": "graf",
    "ZI|2025-02-07|2": "graf",
    "ZI|2025-02-07|3": "sortiranje",
    "ZI|2023-02-02|2": "graf",
    "ZI|2023-02-02|3": "sortiranje",
    "ZI|2023-01-27|2": "graf",
    "ZI|2022-01-28|3": "sortiranje",
    "ZI|2022-01-28|4": "graf",
    "ZI|2021-01-29|2": "graf",
    "ZI|2020-01-31|2": "graf",
    "ZI|2020-01-31|3": "sortiranje",
    "ZI|2017-06-13|1": "binarno stablo",
    "ZI|2017-06-13|4": "red",
    "ZI|2016-06-21|1": "graf",
    "ZI|2016-06-21|2": "binarno stablo",
    "ZI|2016-06-21|3": "gomila",
    "ZI|2016-06-21|5": "stog",
    "ZI|2015-06-16|1": "stog",
    "ZI|2015-06-16|2": "slozenost",
    "ZI|2015-06-16|4": "binarno stablo",
    "ZI|2015-06-16|5": "sortiranje",
    "ZI|2014-06-17|2": "red",
    "ZI|2014-06-17|3": "binarno stablo",
    "ZI|2014-06-17|4": "binarno stablo",
    "ZI|2014-06-17|5": "sortiranje",
    "ZI|2013-06-18|1": "red",
    "ZI|2013-06-18|4": "binarno stablo",
    "ZI|2013-06-18|5": "stog",
    "ZI|2012-06-20|1": "vezana lista",
    "ZI|2012-06-20|2": "binarno stablo",
    "ZI|2012-06-20|3": "sortiranje",
    "ZI|2012-06-20|4": "stog",
    "ZI|2011-06-13|2": "binarno stablo",
    "ZI|2011-06-13|3": "sortiranje",
    "ZI|2011-06-13|5": "rekurzija",
    "ZI|2011-06-13|6": "binarno stablo",
    "ZI|2010-07-02|2": "binarno stablo",
    "ZI|2010-07-02|4": "vezana lista",
    "ZI|2010-07-02|5": "binarno stablo",
    "ZI|2009-06-23|2": "binarno stablo",
    "ZI|2008-07-03|1": "binarno stablo",
    "ZI|2008-07-03|3": "gomila",
}


def label_matches(llm_label: str, suggested: str) -> bool | None:
    """Vraća True/False ili None ako se ne može procijeniti (npr. 'misc')."""
    if " or " in suggested:
        parts = [p.strip() for p in suggested.split(" or ")]
        results = [label_matches(llm_label, p) for p in parts]
        if any(r is True for r in results):
            return True
        if all(r is False for r in results):
            return False
        return None

    ll = llm_label.lower()
    s = suggested.lower()

    matchers = {
        "stog": "stog",
        "red": "red",
        "vezana lista": "vezana lista",
        "vezana": "vezana lista",
        "binarno stablo": "binarno stablo",
        "binarno": "binarno stablo",
        "sortir": "sortiranje",
        "rekurz": "rekurzija",
        "slozenost": "složenost",
        "složenost": "složenost",
        "hash": "hash tablica",
        "raspr": "hash tablica",
        "graf": "graf",
        "gomil": "gomila",
        "pretrag": "razno",  # pretraga not in our taxonomy, mark as Razno
        "kmp": "kmp",
        "dinamick": None,  # dropped from taxonomy
    }

    for key, expected_llm in matchers.items():
        if key in s:
            if expected_llm is None:
                return None
            return expected_llm in ll
    return None


def main():
    llm_csv = "embeddings/llm_classification/tasks_with_clusters.csv"
    df = pd.read_csv(llm_csv)
    tid_to_label = dict(zip(df["task_id"], df["cluster_label"]))

    agreed = []
    disagreed = []
    unjudge = []
    for tid, sug in CORRECTIONS.items():
        llm = tid_to_label.get(tid, "MISSING")
        m = label_matches(llm, sug)
        if m is True:
            agreed.append((tid, llm, sug))
        elif m is False:
            disagreed.append((tid, llm, sug))
        else:
            unjudge.append((tid, llm, sug))

    judgable = len(agreed) + len(disagreed)
    print(f"=== LLM klasifikacija vs ručni ispravci ===")
    print(f"Ukupno ispravaka:  {len(CORRECTIONS)}")
    print(f"Judgable cases:    {judgable}")
    print(f"Agreed:            {len(agreed)} ({100*len(agreed)/max(1,judgable):.0f}%)")
    print(f"Disagreed:         {len(disagreed)}")
    print(f"Unclear (misc/N/A): {len(unjudge)}")
    print()
    print("--- DISAGREED ---")
    for tid, llm, sug in disagreed[:40]:
        print(f"  {tid:<22}  LLM={llm:<22}  ti=({sug})")
    print()
    print("--- AGREED (sample) ---")
    for tid, llm, sug in agreed[:20]:
        print(f"  {tid:<22}  LLM={llm:<22}  ti=({sug})")


if __name__ == "__main__":
    main()
