"""Env-var-driven config za cijeli pipeline."""

import os
from pathlib import Path

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
N_CLUSTERS   = int(os.getenv("N_CLUSTERS", "15"))
CSV_PATH     = os.getenv("CSV_PATH", "data/asp_index_last3_mi_last3_zi.csv")
MI_PDF_PATH  = os.getenv("MI_PDF",   "static/MI_svi_do_2026.pdf")
ZI_PDF_PATH  = os.getenv("ZI_PDF",   "static/ZI_svi_do_2026.pdf")
OUT_DIR      = Path("embeddings")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
