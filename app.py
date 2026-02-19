import streamlit as st
import pandas as pd
import fitz

st.set_page_config(page_title="ASP MVP", layout="wide")

df = pd.read_csv("data/asp_index_last3_mi_last3_zi.csv")

st.title("MVP za zavrsni rad")

goal = st.selectbox("Cilj", ["prolaz (2)", "petica (5)"], key="goal")
days_left = st.slider("Dana do ispita", 0, 14, 1, key="days_left")
session_minutes = st.slider("Vrijeme za study blok (min/dan)", 30, 240, 120, key="session_minutes")

total_budget = session_minutes * max(1, days_left)

@st.cache_data
def render_pdf_page(pdf_path: str, page_1based: int, dpi: int = 150) -> bytes:
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

def get_weights():
    w_eff = 5.0
    w_points = 2.0
    w_freq = 0.5

    if goal == "prolaz (2)":
        w_detail = -3.0
        w_diff = -1.5
    else:
        w_detail = 1.0
        w_diff = -0.5

    if days_left <= 1:
        w_eff += 2.0
        w_points += 1.0
        w_detail -= 2.0

    return w_eff, w_points, w_detail, w_freq, w_diff

def score_breakdown(row):
    points = float(row["points"])
    time_est = float(row["time_est"])
    eff = points / time_est if time_est > 0 else 0.0
    is_detail = 1.0 if row["type"] == "detail" else 0.0
    freq = float(row.get("frequency_score", 0.0))
    diff = float(row.get("difficulty_guess", 0.0))

    w_eff, w_points, w_detail, w_freq, w_diff = get_weights()

    parts = {
        "efficiency": w_eff * eff,
        "points": w_points * points,
        "detail": w_detail * is_detail,
        "frequency": w_freq * freq,
        "difficulty": w_diff * diff
    }

    total = float(sum(parts.values()))
    return parts, total, {
        "eff": eff,
        "points": points,
        "time_est": time_est,
        "is_detail": is_detail,
        "freq": freq,
        "diff": diff,
        "weights": {
            "w_eff": w_eff,
            "w_points": w_points,
            "w_detail": w_detail,
            "w_freq": w_freq,
            "w_diff": w_diff
        }
    }

def score_task(row) -> float:
    _, total, _ = score_breakdown(row)
    return total

def build_plan(df_in: pd.DataFrame, minutes_budget: int) -> pd.DataFrame:
    df_local = df_in.copy()
    df_local["score"] = df_local.apply(score_task, axis=1)
    df_sorted = df_local.sort_values("score", ascending=False)

    selected_rows = []
    total_time = 0.0

    for _, row in df_sorted.iterrows():
        t = float(row["time_est"])
        if total_time + t <= float(minutes_budget):
            selected_rows.append(row)
            total_time += t

    return pd.DataFrame(selected_rows)

plan_df = build_plan(df, total_budget)

left, right = st.columns([1, 1])

with left:
    st.subheader("Preporuceni zadaci")

    if plan_df.empty:
        st.warning("Nema zadataka koji stanu u ovaj vremenski budzet. Povecaj minute ili provjeri time_est.")
        st.stop()

    st.caption(f"Ukupni budzet: {int(total_budget)} min (session_minutes * max(1, days_left))")

    total_points = float(plan_df["points"].sum())
    total_time = float(plan_df["time_est"].sum())
    avg_eff = (total_points / total_time) if total_time > 0 else 0.0

    m1, m2, m3 = st.columns(3)
    m1.metric("Ukupno bodova", f"{total_points:.0f}")
    m2.metric("Ukupno minuta", f"{total_time:.0f}")
    m3.metric("Prosjecni efficiency", f"{avg_eff:.3f}")

    st.dataframe(
        plan_df[["exam_type", "exam_date", "task_no", "points", "time_est", "type", "frequency_score", "difficulty_guess", "score"]],
        use_container_width=True
    )

with right:
    st.subheader("Pregled zadatka")

    task_labels = plan_df.apply(
        lambda r: f"{r['exam_type']} {r['exam_date']} - Zadatak {r['task_no']} (pts {r['points']}, {r['time_est']} min)",
        axis=1
    ).tolist()

    if "selected_task_label" not in st.session_state or st.session_state.selected_task_label not in task_labels:
        st.session_state.selected_task_label = task_labels[0]

    selected_task_label = st.selectbox(
        "Odaberi zadatak za pregled:",
        task_labels,
        key="selected_task_label"
    )

    idx = task_labels.index(selected_task_label)
    selected_task = plan_df.iloc[idx]

    pdf_path = f"static/{selected_task['pdf']}"
    page = int(selected_task["page"])

    st.write(f"PDF: {selected_task['pdf']}, stranica {page}")

    # Centered preview by using a narrower middle column
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        try:
            img_bytes = render_pdf_page(pdf_path, page)
            st.image(img_bytes, width=700)
        except Exception as e:
            st.error(f"Ne mogu otvoriti PDF stranicu: {e}")

    st.subheader("Zasto je odabran ovaj zadatak")

    parts, total_score, meta = score_breakdown(selected_task)

    for key, value in parts.items():
        if value > 0:
            st.write(f"+ {key}: {value:.2f}")
        elif value < 0:
            st.write(f"- {key}: {value:.2f}")

    st.markdown(f"**Ukupni score: {total_score:.2f}**")

    with st.expander("Detalji (ulazi i tezine)"):
        st.write({
            "inputs": {
                "points": meta["points"],
                "time_est": meta["time_est"],
                "efficiency": meta["eff"],
                "type": "detail" if meta["is_detail"] == 1 else "core",
                "frequency_score": meta["freq"],
                "difficulty_guess": meta["diff"]
            },
            "weights": meta["weights"]
        })
