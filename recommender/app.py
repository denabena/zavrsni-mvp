"""
Streamlit UI za knapsack recommender.

Pokretanje (iz repo roota):
  streamlit run recommender/app.py

Modovi:
  - Tema (TOPIC): korisnik bira klastere + vrijeme
  - Ispit (EXAM): korisnik bira MI / ZI / oba, ciljanu ocjenu i vrijeme
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Da bi `python` i `streamlit` našli recommender + pipeline kao top-level pakete
# kad se app pokreće iz roota.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import math

import fitz  # PyMuPDF
import streamlit as st

from recommender import recommend, RecommenderConfig, Mode
from recommender.data import load_tasks, load_cluster_frequencies, cluster_label_map


STATIC_DIR = os.getenv("STATIC_DIR", "static")


# ── Page setup ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="ASP recommender", layout="wide")
st.title("ASP recommender")
st.caption(
    "Knapsack preporuka zadataka za vježbu. Diminishing returns po klasteru "
    "osigurava raznolikost tema unutar zadanog vremenskog budžeta."
)


# ── Cached resources ─────────────────────────────────────────────────────────


@st.cache_data
def get_tasks():
    return load_tasks()


@st.cache_data
def get_cluster_freq():
    return load_cluster_frequencies()


@st.cache_data
def get_cluster_labels(_tasks_csv_path: str):
    # cache key je path; ovdje samo da se cache invalidira ako se tasks promijeni
    return cluster_label_map(get_tasks())


@st.cache_data
def render_pdf_page(pdf_path: str, page_1based: int, dpi: int = 130) -> bytes:
    doc = fitz.open(pdf_path)
    page_index = page_1based - 1
    if page_index < 0 or page_index >= len(doc):
        doc.close()
        raise ValueError("Stranica ne postoji u PDF-u.")
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    img = pix.tobytes("png")
    doc.close()
    return img


tasks = get_tasks()
cluster_freq = get_cluster_freq()
labels_map = get_cluster_labels(str(Path("embeddings/tasks_with_clusters.csv")))


# ── Sidebar: konfiguracija ───────────────────────────────────────────────────

with st.sidebar:
    st.header("Konfiguracija")

    mode_label = st.radio(
        "Mod preporuke",
        ["Tema (klasteri)", "Ispit (MI / ZI)"],
        key="mode_label",
    )
    mode = Mode.TOPIC if mode_label.startswith("Tema") else Mode.EXAM

    st.subheader("Vrijeme")
    time_input_mode = st.radio(
        "Unos vremena",
        ["Ukupno (min)", "Min/dan x dana"],
        horizontal=True,
        key="time_input_mode",
    )
    if time_input_mode == "Ukupno (min)":
        time_budget = st.slider("Ukupno minuta", 30, 1200, 180, step=15)
    else:
        per_day = st.slider("Min/dan", 30, 240, 90, step=15)
        days = st.slider("Dana do ispita", 1, 21, 3)
        time_budget = per_day * days
        st.caption(f"Ukupno: {time_budget} min")

    chosen_clusters: list[int] = []
    chosen_exam_types: list[str] = []
    target_grade = 100.0

    if mode == Mode.TOPIC:
        st.subheader("Klasteri")
        all_cluster_ids = sorted(tasks["cluster_id"].unique().tolist())
        cluster_options = [
            (cid, f"{cid}: {labels_map.get(cid, '')}".strip(": "))
            for cid in all_cluster_ids
        ]
        chosen = st.multiselect(
            "Odaberi teme",
            options=[lbl for _, lbl in cluster_options],
            default=[],
            key="topic_clusters",
        )
        chosen_clusters = [cid for cid, lbl in cluster_options if lbl in chosen]

    else:
        st.subheader("Ispit")
        exam_choice = st.radio(
            "Tip ispita", ["MI", "ZI", "MI + ZI"], horizontal=True
        )
        if exam_choice == "MI":
            chosen_exam_types = ["MI"]
        elif exam_choice == "ZI":
            chosen_exam_types = ["ZI"]
        else:
            chosen_exam_types = ["MI", "ZI"]

        target_grade = float(
            st.slider("Ciljana ocjena (%)", 0, 100, 80, step=5)
        )
        st.caption(
            "Niža ciljana ocjena -> izbacuju se outlieri (rijetki tipovi "
            "zadataka). Viša ocjena -> uključuju se i rubni zadaci."
        )


# ── Glavni sadržaj ────────────────────────────────────────────────────────────

cfg = RecommenderConfig(
    mode=mode,
    time_budget_minutes=int(time_budget),
    chosen_clusters=chosen_clusters,
    chosen_exam_types=chosen_exam_types,
    target_grade=target_grade,
)

rec = recommend(tasks, cluster_freq, cfg)

# Sažetak
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Odabrano zadataka", rec.n_tasks)
col_b.metric("Ukupno min", f"{rec.total_time_minutes:.0f}")
col_c.metric("Budžet", f"{time_budget} min")
col_d.metric("Pokrivenih klastera", len(rec.cluster_coverage))

if rec.n_tasks == 0:
    if mode == Mode.TOPIC and not chosen_clusters:
        st.info("Odaberi barem jedan klaster u lijevom panelu.")
    elif mode == Mode.EXAM and not chosen_exam_types:
        st.info("Odaberi tip ispita u lijevom panelu.")
    else:
        st.warning("Nijedan zadatak ne stane u budžet. Probaj veći.")
    st.stop()


# Tablica preporuka
st.subheader("Preporučeni zadaci")
display_cols = [
    "task_id",
    "exam_type",
    "exam_date",
    "task_no",
    "cluster_id",
    "cluster_label",
    "centroid_outlier_score",
]
extra_cols = [
    c
    for c in ("median_difficulty", "median_time_minutes", "n_ratings")
    if c in rec.tasks.columns
]
shown = rec.tasks[display_cols + extra_cols].copy()
shown["centroid_outlier_score"] = shown["centroid_outlier_score"].round(2)
st.dataframe(shown, use_container_width=True, hide_index=True)


# Pokrivenost klastera
with st.expander("Pokrivenost klastera"):
    coverage_rows = []
    for cid, n in sorted(rec.cluster_coverage.items()):
        coverage_rows.append(
            {"cluster_id": cid, "label": labels_map.get(cid, ""), "n_zadataka": n}
        )
    if coverage_rows:
        st.dataframe(coverage_rows, use_container_width=True, hide_index=True)


# Pregled pojedinog zadatka
st.subheader("Pregled zadatka")
labels = rec.tasks.apply(
    lambda r: f"{r['exam_type']} {r['exam_date']} - Zad. {r['task_no']} (cl{int(r['cluster_id'])})",
    axis=1,
).tolist()
if labels:
    sel_idx = st.selectbox(
        "Zadatak", options=list(range(len(labels))), format_func=lambda i: labels[i]
    )
    selected = rec.tasks.iloc[sel_idx]

    left, right = st.columns([3, 2])
    with left:
        page_val = selected.get("page")
        pdf_val = selected.get("pdf")
        if (
            page_val is None
            or (isinstance(page_val, float) and math.isnan(page_val))
            or pdf_val is None
            or (isinstance(pdf_val, float) and math.isnan(pdf_val))
        ):
            st.info("Ovaj zadatak nema mapirani PDF + stranicu (nije bio u izvornom CSV-u).")
        else:
            pdf_path = os.path.join(STATIC_DIR, str(pdf_val))
            try:
                img = render_pdf_page(pdf_path, int(page_val))
                st.image(img, use_container_width=True)
            except Exception as e:
                st.error(f"Ne mogu otvoriti stranicu PDF-a: {e}")

    with right:
        st.markdown(f"**Klaster:** {selected['cluster_id']} - {selected.get('cluster_label', '')}")
        st.markdown(
            f"**Outlier score (rang u klasteru):** "
            f"{float(selected['centroid_outlier_score']):.2f}"
        )
        if "median_difficulty" in selected and selected.get("median_difficulty") is not None:
            st.markdown(
                f"**Medijan težine:** {selected['median_difficulty']} / 5  "
                f"({int(selected.get('n_ratings', 0))} ocjena)"
            )
        if "median_time_minutes" in selected and selected.get("median_time_minutes") is not None:
            st.markdown(f"**Medijan vremena:** {selected['median_time_minutes']} min")
        st.markdown("**Tekst zadatka:**")
        snippet = str(selected.get("task_text") or "")
        st.text(snippet[:1500])
