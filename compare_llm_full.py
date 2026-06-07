"""
compare_llm_full.py
-------------------
Provjera LLM klasifikacije protiv svih 185 zadataka:
  - 71 ručnih ispravaka -> eksplicitna istina
  - 22 ručnih oznaka oblika "(not X)" / "(misc)" -> djelomično, koristimo
    kao "anything BUT X" pravilo
  - ostali (~92) -> baseline K-means labela mapirana u taksonomiju kao
    implicitna istina (jer ih korisnik nije označio kao pogrešne)

Output: agreement rate na cijelom skupu + breakdown po razlozima.
"""

import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# Eksplicitne ispravke (pozitivne oznake)
CORRECTIONS_POSITIVE = {
    "MI|2023-11-27|4": "stog",
    "MI|2019-11-25|3": "vezana lista",
    "MI|2016-04-26|3": "stog",
    "MI|2014-04-23|2": "rekurzija",
    "MI|2014-04-23|3": "rekurzija",
    "MI|2013-04-23|4": "pretraga",  # not in taxonomy, treat as ambiguous
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
    "MI|2009-05-22|1": "stog",  # "stog or rekurzija" → either accepted
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

# Negativne ispravke ("(not X)") - znamo samo što NIJE
CORRECTIONS_NEGATIVE = {
    "MI|2016-04-26|5": "rekurzija",
    "MI|2015-04-21|2": "rekurzija",
    "MI|2015-04-21|4": "pretraga",
    "MI|2014-04-23|4": "rekurzija",
    "MI|2010-03-29|3": "rekurzija",
    "MI|2010-03-29|5": "graf",
    "MI|2010-05-10|4": "graf",
    "MI|2009-04-09|4": "rekurzija",
    "MI|2008-03-19|2": "rekurzija",
    "MI|2021-11-29|2": "pretraga",
}

# "misc" ili "moze biti izbacen" - ne računamo
SKIP_TASKS = {
    "MI|2019-11-25|1",
    "ZI|2026-02-06|4",
    "ZI|2026-02-06|5",
    "ZI|2025-02-07|5",
    "ZI|2023-02-02|5",
    "ZI|2023-01-27|5",
    "ZI|2022-01-28|5",
    "ZI|2021-01-29|3",
    "ZI|2020-01-31|6",
    "ZI|2011-06-13|4",
    "ZI|2009-06-23|4",
    "ZI|2008-07-03|4",
}

# Baseline -> taksonomija mapping
BASELINE_TO_TAXONOMY = {
    "Sortiranje": "Sortiranje",
    "Uzlazno sortiranje": "Sortiranje",
    "Stog operacije": "Stog",
    "Stog": "Stog",
    "Red": "Red",
    "Povezana lista": "Vezana lista",
    "Vezana lista": "Vezana lista",
    "Binarno stablo": "Binarno stablo",
    "Gomila": "Gomila",
    "Hash tablica": "Hash tablica",
    "Raspršeno adresiranje": "Hash tablica",
    "Graf": "Graf",
    "Rekurzija": "Rekurzija",
    "Složenost algoritama": "Složenost algoritama",
    "KMP": "KMP",
    # Ovi nemaju jasan ekvivalent - tretiramo kao ambiguous
    "Pretraga": None,
    "Dinamička alokacija": None,
}

# Pozitivni korisnički input -> taksonomija
USER_TO_TAXONOMY = {
    "stog": "Stog",
    "red": "Red",
    "vezana lista": "Vezana lista",
    "binarno stablo": "Binarno stablo",
    "sortiranje": "Sortiranje",
    "rekurzija": "Rekurzija",
    "slozenost": "Složenost algoritama",
    "hash": "Hash tablica",
    "graf": "Graf",
    "gomila": "Gomila",
    "kmp": "KMP",
    "pretraga": None,  # not in taxonomy
}


def user_to_taxonomy(s: str) -> str | None:
    s = s.lower().strip()
    return USER_TO_TAXONOMY.get(s)


def main():
    llm_df = pd.read_csv("embeddings/llm_classification/tasks_with_clusters.csv")
    base_df = pd.read_csv("embeddings/baseline_kmeans/task_labels_quickview.csv")

    llm_map = dict(zip(llm_df["task_id"], llm_df["cluster_label"]))
    base_map = dict(zip(base_df["task_id"], base_df["cluster_label"]))

    all_tids = sorted(set(llm_df["task_id"]) & set(base_df["task_id"]))
    print(f"Tasks in both LLM + baseline: {len(all_tids)}")
    print()

    pos_agree = pos_disagree = 0
    neg_agree = neg_disagree = 0  # neg = "not X" rule
    base_agree = base_disagree = 0
    skipped_explicit = 0  # SKIP_TASKS
    skipped_ambig = 0  # baseline label has no taxonomy mapping
    pos_disagree_list = []
    neg_disagree_list = []
    base_disagree_list = []

    for tid in all_tids:
        if tid in SKIP_TASKS:
            skipped_explicit += 1
            continue

        llm_label = llm_map.get(tid)

        if tid in CORRECTIONS_POSITIVE:
            truth = user_to_taxonomy(CORRECTIONS_POSITIVE[tid])
            if truth is None:
                skipped_ambig += 1
                continue
            if llm_label == truth:
                pos_agree += 1
            else:
                pos_disagree += 1
                pos_disagree_list.append((tid, llm_label, truth))
            continue

        if tid in CORRECTIONS_NEGATIVE:
            bad_label = user_to_taxonomy(CORRECTIONS_NEGATIVE[tid])
            if bad_label is None:
                # user said "not X" where X isn't in taxonomy; can't score
                skipped_ambig += 1
                continue
            # Pass if LLM didn't pick the forbidden category
            if llm_label != bad_label:
                neg_agree += 1
            else:
                neg_disagree += 1
                neg_disagree_list.append((tid, llm_label, f"NOT {bad_label}"))
            continue

        # Implicit truth = baseline label mapped to taxonomy
        base_label = base_map.get(tid)
        truth = BASELINE_TO_TAXONOMY.get(base_label) if base_label else None
        if truth is None:
            skipped_ambig += 1
            continue
        if llm_label == truth:
            base_agree += 1
        else:
            base_disagree += 1
            base_disagree_list.append((tid, llm_label, truth, base_label))

    total_pos = pos_agree + pos_disagree
    total_neg = neg_agree + neg_disagree
    total_base = base_agree + base_disagree
    total_scored = total_pos + total_neg + total_base

    print("=== Agreement rates ===")
    print(f"Positive corrections:  {pos_agree}/{total_pos} ({100*pos_agree/max(1,total_pos):.0f}%)")
    print(f"Negative corrections:  {neg_agree}/{total_neg} ({100*neg_agree/max(1,total_neg):.0f}%)")
    print(f"Baseline (implicit):   {base_agree}/{total_base} ({100*base_agree/max(1,total_base):.0f}%)")
    print(f"---")
    print(f"OVERALL:               {pos_agree + neg_agree + base_agree}/{total_scored} ({100*(pos_agree + neg_agree + base_agree)/max(1,total_scored):.0f}%)")
    print(f"Skipped (misc/ambig):  {skipped_explicit + skipped_ambig}")
    print()

    print("=== Disagreements where you explicitly said X ===")
    for tid, llm, truth in pos_disagree_list:
        print(f"  {tid:<22}  LLM={llm:<22}  you={truth}")
    print()

    print("=== Disagreements where you said NOT X (LLM still picked X) ===")
    for tid, llm, marker in neg_disagree_list:
        print(f"  {tid:<22}  LLM={llm:<22}  rule={marker}")
    print()

    print("=== Disagreements vs baseline (implicit) ===")
    for tid, llm, truth, base in base_disagree_list[:30]:
        print(f"  {tid:<22}  LLM={llm:<22}  baseline={base} -> mapped={truth}")
    if len(base_disagree_list) > 30:
        print(f"  ... +{len(base_disagree_list)-30} more")


if __name__ == "__main__":
    main()
