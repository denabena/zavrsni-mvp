import os
import time
import streamlit as st
import pandas as pd
import fitz  # PyMuPDF


st.set_page_config(page_title="Završni rad - MVP", layout="wide")

# Ako želiš prebaciti na apsolutnu putanju, stavi npr. u env var:
# INDEX_CSV=/mnt/data/asp_index_last3_mi_last3_zi.csv
INDEX_CSV = os.getenv("INDEX_CSV", "data/asp_index_last3_mi_last3_zi.csv")
STATIC_DIR = os.getenv("STATIC_DIR", "static")

df = pd.read_csv(INDEX_CSV)

st.title("Završni rad - MVP")

# ---------------------------
# PDF render + text extraction
# ---------------------------

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

@st.cache_data
def extract_pdf_page_text(pdf_path: str, page_1based: int) -> str:
    doc = fitz.open(pdf_path)
    page_index = page_1based - 1
    if page_index < 0 or page_index >= len(doc):
        doc.close()
        raise ValueError("Stranica ne postoji u PDF-u.")
    page = doc[page_index]
    text = page.get_text("text") or ""
    doc.close()

    # Minimalno čišćenje, bez agresivnog hardkodiranja.
    text = text.replace("\u00a0", " ")
    text = "\n".join([ln.rstrip() for ln in text.splitlines()])
    text = text.strip()
    return text

# ---------------------------
# Scoring (tvoje, minimalno dirano)
# ---------------------------

goal = st.selectbox("Cilj", ["prolaz (2)", "petica (5)"], key="goal")
days_left = st.slider("Dana do ispita", 0, 14, 1, key="days_left")
session_minutes = st.slider("Vrijeme u danu (min/dan)", 30, 240, 120, key="session_minutes")

total_budget = session_minutes * max(1, days_left)

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

if plan_df.empty:
    st.warning("Nema zadataka koji stanu u ovaj vremenski budžet. Skuhan si.")
    st.stop()

# ---------------------------
# Task picker (shared)
# ---------------------------

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

pdf_path = os.path.join(STATIC_DIR, str(selected_task["pdf"]))
page_1based = int(selected_task["page"])

# ---------------------------
# LLM client (ollama ili llama.cpp), bez hardkodiranja
# ---------------------------

def build_explain_prompt(task_text: str) -> str:
    # Namjerno fiksan prompt, jer user nema chat input.
    # Fokus: razumijevanje + rješenje + provjere tipičnih zamki.
    return f"""
Ti si asistent za ucenje predmeta "Algoritmi i strukture podataka".
Korisnik je kliknuo da ne razumije zadatak. Objasni zadatak i napravi rjesenje.

Pravila odgovora:
- Prvo objasni sto se trazi, u par tocaka.
- Zatim izvedi rjesenje korak po korak.
- Ako je zadatak programski: daj cisti C++ kod (ili pseudokod ako je prikladnije) i objasni ga.
- Na kraju navedi najcesce pogreske i kratku provjeru tocnosti.
- Ne spominji da si model, ne spominji prompt, ne postavljaj pitanja korisniku.

TEKST ZADATKA (iz PDF-a):
{task_text}
""".strip()

def stream_from_ollama(prompt: str):
    # pip install ollama
    import ollama
    model = os.getenv("OLLAMA_MODEL", "llama3.1")

    # chat API radi stabilnije za streaming
    stream = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        # chunk je dict, najcesce chunk["message"]["content"]
        msg = chunk.get("message", {})
        content = msg.get("content", "")
        if content:
            yield content

def stream_from_llamacpp(prompt: str):
    # pip install llama-cpp-python
    from llama_cpp import Llama

    model_path = os.getenv("LLAMA_CPP_MODEL_PATH", "")
    if not model_path:
        raise RuntimeError("Nedostaje LLAMA_CPP_MODEL_PATH env var (putanja do .gguf modela).")

    n_ctx = int(os.getenv("LLAMA_CPP_N_CTX", "4096"))
    n_threads = int(os.getenv("LLAMA_CPP_THREADS", str(os.cpu_count() or 4)))

    llm = Llama(
        model_path=model_path,
        n_ctx=n_ctx,
        n_threads=n_threads,
        # po potrebi: n_gpu_layers=int(os.getenv("LLAMA_CPP_GPU_LAYERS", "0"))
    )

    # create_completion streaming
    for out in llm.create_completion(
        prompt=prompt,
        max_tokens=int(os.getenv("LLAMA_MAX_TOKENS", "900")),
        temperature=float(os.getenv("LLAMA_TEMPERATURE", "0.2")),
        stream=True,
    ):
        choice = (out.get("choices") or [{}])[0]
        text = choice.get("text", "")
        if text:
            yield text

def stream_llm_answer(task_text: str):
    backend = os.getenv("LLM_BACKEND", "ollama").strip().lower()
    prompt = build_explain_prompt(task_text)

    if backend == "ollama":
        yield from stream_from_ollama(prompt)
    elif backend == "llamacpp":
        yield from stream_from_llamacpp(prompt)
    else:
        raise RuntimeError("Nepoznat LLM_BACKEND. Koristi 'ollama' ili 'llamacpp'.")

# ---------------------------
# 3-column layout
# ---------------------------

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.subheader("Preporučeni zadaci")

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

with col2:
    st.subheader("PDF pregled")
    st.write(f"PDF: {selected_task['pdf']}, stranica {page_1based}")

    # Centered preview
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        try:
            img_bytes = render_pdf_page(pdf_path, page_1based)
            st.image(img_bytes, width=850)
        except Exception as e:
            st.error(f"Ne mogu otvoriti PDF stranicu: {e}")

    st.subheader("Zašto je odabran ovaj zadatak")
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

with col3:
    st.subheader("Pomoć")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": "Klikni 'Ne razumijem zadatak' i objasnit cu zadatak i rjesenje."
        })

    # Render chat history
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    clicked = st.button("Ne razumijem zadatak", use_container_width=True)

    if clicked:
        # Extract task text from PDF page
        try:
            task_text = extract_pdf_page_text(pdf_path, page_1based)
        except Exception as e:
            st.error(f"Ne mogu izvuci tekst zadatka iz PDF-a: {e}")
            st.stop()

        # Optional: ako je tekst prazan, daj fallback poruku
        if not task_text.strip():
            st.error("Izvuceni tekst je prazan. Moguce je da je stranica skenirana slika bez teksta.")
            st.stop()

        # Add a synthetic user event to chat for clarity
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Ne razumijem zadatak. Objasni mi ga i rijesi."
        })

        with st.chat_message("user"):
            st.markdown("Ne razumijem zadatak. Objasni mi ga i rijesi.")

        # Stream assistant answer
        with st.chat_message("assistant"):
            placeholder = st.empty()
            acc = ""

            # Brzi "kick" da se odmah nesto prikaze, i prije prvog tokena
            placeholder.markdown("Krecem s objasnjenjem...")

            try:
                for chunk in stream_llm_answer(task_text):
                    acc += chunk
                    placeholder.markdown(acc)
                    # Malo uspori ako zelis "typing" osjecaj i kad LLM salje vece chunkove
                    # time.sleep(0.01)
            except Exception as e:
                placeholder.markdown("")
                st.error(f"LLM greska: {e}")
                st.stop()

        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": acc
        })