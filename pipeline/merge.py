"""Spajanje parsiranih zadataka s CSV metapodacima."""

import pandas as pd


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

    df_merged["task_id"] = (
        df_merged["exam_type"] + "|" +
        df_merged["exam_date"] + "|" +
        df_merged["task_no"].astype(str)
    )

    n_matched = df_merged["points"].notna().sum()
    n_total   = len(df_merged)
    print(f"  Spajanje: {n_matched}/{n_total} zadataka ima metapodatke iz CSV-a")
    return df_merged
