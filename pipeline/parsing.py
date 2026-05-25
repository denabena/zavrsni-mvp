"""Parsiranje PDF-ova ispita i segmentacija na zadatke."""

import re
import bisect
import fitz  # PyMuPDF


_HEADER_PATTERN = re.compile(
    r"JMBAG IME I PREZIME.*?(?=Zadatak \d+\.)",
    re.DOTALL
)

_TASK_MARKER = re.compile(r"(Zadatak \d+\.\s*\(\d+ bod[^\)]*\)[^\n]*)", re.IGNORECASE)

_EXAM_HEADER = re.compile(
    r"Algoritmi i strukture podataka\s*[–-]\s*(međuispit|završni ispit)\s*\r?\n([^\r\n]+)",
    re.IGNORECASE
)

_MONTH_MAP = {
    "siječnja": 1,  "veljače": 2,  "ožujka": 3,   "travnja": 4,
    "svibnja":  5,  "lipnja":  6,  "srpnja": 7,   "kolovoza": 8,
    "rujna":    9,  "listopada": 10, "studenoga": 11, "prosinca": 12
}


def _parse_date(raw: str) -> str:
    """'28. studenoga 2025.' -> '2025-11-28'"""
    m = re.match(r"(\d+)\.\s+(\w+)\s+(\d{4})", raw.strip())
    if not m:
        return raw.strip().rstrip(".")
    day, month_hr, year = m.group(1), m.group(2).lower(), m.group(3)
    month = _MONTH_MAP.get(month_hr, 0)
    return f"{year}-{month:02d}-{int(day):02d}"


def _clean_task_text(text: str) -> str:
    """Ukloni šum koji nije dio zadatka."""
    text = re.sub(r"Ispit donosi maksimalno.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(r"JMBAG[^\n]*\n?", "", text)
    text = re.sub(r"IME I PREZIME[^\n]*\n?", "", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"^Zadatak\s+\d+\.\s*\(\d+\s+bod[^\)]*\)\s*[–-]?\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _extract_pdf_pages(path: str) -> tuple[str, list[int]]:
    """
    Vraća (joined_text, page_offsets) gdje je page_offsets[i] char-offset
    početka stranice i unutar joined_text (0-indexed). Stranice spojene s '\\n'.
    nbsp -> space ne mijenja duljinu pa offseti ostaju valjani.
    """
    doc = fitz.open(path)
    try:
        pages = [(page.get_text("text") or "") for page in doc]
    finally:
        doc.close()

    offsets: list[int] = []
    running = 0
    for p in pages:
        offsets.append(running)
        running += len(p) + 1  # +1 za '\n' separator

    raw = "\n".join(pages).replace(" ", " ")
    return raw, offsets


def _page_for_offset(offsets: list[int], char_pos: int) -> int:
    """1-indexed broj stranice u kojoj se nalazi char_pos."""
    return bisect.bisect_right(offsets, char_pos)


def parse_exam_file(path: str, exam_type: str) -> list[dict]:
    """
    Parsira jedan PDF ispita i vraća listu rječnika:
      {exam_type, exam_date, task_no, task_text, pdf_page}
    pdf_page je 1-indexed broj stranice u izvornom PDF-u.
    """
    raw, page_offsets = _extract_pdf_pages(path)

    records = []

    exam_splits = list(_EXAM_HEADER.finditer(raw))
    if not exam_splits:
        print(f"  [WARN] Nisam pronašao exam headere u {path}")
        exam_blocks = [(0, "unknown", raw)]  # (block_start_abs, date, text)
    else:
        exam_blocks = []
        for i, m in enumerate(exam_splits):
            date_raw = m.group(2).strip()
            date_str = _parse_date(date_raw)
            start    = m.start()
            end      = exam_splits[i + 1].start() if i + 1 < len(exam_splits) else len(raw)
            exam_blocks.append((start, date_str, raw[start:end]))

    for block_start_abs, exam_date, block in exam_blocks:
        task_splits = list(_TASK_MARKER.finditer(block))
        if not task_splits:
            continue

        for j, tm in enumerate(task_splits):
            task_no_m = re.search(r"Zadatak (\d+)\.", tm.group(1))
            task_no   = int(task_no_m.group(1)) if task_no_m else j + 1

            t_start = tm.end()
            t_end   = task_splits[j + 1].start() if j + 1 < len(task_splits) else len(block)
            body    = block[t_start:t_end]

            full_text = tm.group(1) + "\n" + body
            cleaned   = _clean_task_text(full_text)

            # Apsolutni offset početka zadatka u joined `raw` -> page
            task_abs_start = block_start_abs + tm.start()
            pdf_page = _page_for_offset(page_offsets, task_abs_start)

            records.append({
                "exam_type": exam_type,
                "exam_date": exam_date,
                "task_no":   task_no,
                "task_text": cleaned,
                "pdf_page":  pdf_page,
            })

    print(f"  Pronađeno {len(records)} zadataka u {path}")
    return records
