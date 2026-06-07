"""
Parsiranje PDF-ova ispita i segmentacija na zadatke.

Stari pristup je tražio strogo "Algoritmi i strukture podataka – međuispit\\n<datum>"
i propuštao starije formate gdje:
  - separator je hyphen-minus, soft hyphen ili nema ničega
  - tip ispita je "1./2. međuispit" ili nema te linije uopće
  - OCR je đ pretvorio u ñ ("meñuispit")
  - datum je u DD.MM.YYYY ili "DD.month YYYY" bez razmaka

Novi pristup: nađi sve pojave "Algoritmi i strukture podataka" u tekstu, za
svaku pogledaj sljedećih ~350 znakova; ako se unutar tog prozora prepozna
datum (jedan od dva formata), to je header. Dvije bliske pojave (npr. "1.
međuispit iz predmeta Algoritmi i strukture podataka") tretiraju se kao jedna.
"""

import bisect
import re

import fitz  # PyMuPDF


_TASK_MARKER = re.compile(
    r"(Zadatak\s+\d+\.\s*\(\s*\d+\s+bod[^\)]*\)[^\n]*)",
    re.IGNORECASE,
)

_HEADER_LEAD = re.compile(r"Algoritmi i strukture podataka")

# DD. month YYYY (Croatian month name, may have ñ from OCR). Razmak optional
# između broja-dana i točke i mjeseca, da uhvatimo i "25.travnja 2012.".
_DATE_WORDS = re.compile(
    r"(\d{1,2})\.\s*([a-zšđčćžñ]+)\s+(\d{4})\.?",
    re.IGNORECASE,
)

# DD.MM.YYYY (numeričko, dozvoli i D.M.YYYY).
_DATE_NUMS = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.?")

_HEADER_WINDOW = 350  # koliko chars od "Algoritmi ..." gledamo unaprijed
_HEADER_DEDUP_GAP = 120  # bliže od ovoga = ista glava ispita

_MONTH_MAP = {
    "siječnja": 1,  "veljače": 2,  "ožujka": 3,   "travnja": 4,
    "svibnja":  5,  "lipnja":  6,  "srpnja": 7,   "kolovoza": 8,
    "rujna":    9,  "listopada": 10, "studenoga": 11, "prosinca": 12,
}


def _parse_date_from_window(window: str) -> str | None:
    """Pronađi prvi datum (word ili num) u prozoru. Vrati ISO YYYY-MM-DD ili None."""
    m_words = _DATE_WORDS.search(window)
    m_nums = _DATE_NUMS.search(window)

    candidates: list[tuple[int, str, re.Match]] = []
    if m_words:
        candidates.append((m_words.start(), "words", m_words))
    if m_nums:
        candidates.append((m_nums.start(), "nums", m_nums))
    if not candidates:
        return None
    candidates.sort()
    _, kind, m = candidates[0]

    if kind == "words":
        month = _MONTH_MAP.get(m.group(2).lower(), 0)
        if month == 0:
            return None
        try:
            day = int(m.group(1))
            year = int(m.group(3))
        except ValueError:
            return None
        return f"{year:04d}-{month:02d}-{day:02d}"

    try:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
    except ValueError:
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _clean_task_text(text: str) -> str:
    """Ukloni šum koji nije dio zadatka."""
    text = re.sub(r"Ispit donosi maksimalno.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(r"JMBAG[^\n]*\n?", "", text)
    text = re.sub(r"IME I PREZIME[^\n]*\n?", "", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"^Zadatak\s+\d+\.\s*\(\s*\d+\s+bod[^\)]*\)\s*[–-]?\s*", "", text, flags=re.MULTILINE)
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


def _find_exam_blocks(raw: str) -> list[tuple[int, str]]:
    """
    Nađi pozicije svih validnih exam headera u textu.
    Vraća listu (block_start_abs, exam_date_iso), sortiranu po poziciji.

    Heuristika:
      - Za svaku pojavu 'Algoritmi i strukture podataka' pogledaj prozor od
        _HEADER_WINDOW chars unaprijed
      - Ako u tom prozoru ima validan datum, ta pozicija je kandidat
      - Bliske kandidate (< _HEADER_DEDUP_GAP) zadrži samo prvi
        (rješava self-reference u 2008 headerima)
    """
    candidates: list[tuple[int, str]] = []
    for m in _HEADER_LEAD.finditer(raw):
        window_end = min(m.end() + _HEADER_WINDOW, len(raw))
        window = raw[m.end():window_end]
        date = _parse_date_from_window(window)
        if date is not None:
            candidates.append((m.start(), date))

    if not candidates:
        return []

    deduped: list[tuple[int, str]] = [candidates[0]]
    for pos, date in candidates[1:]:
        if pos - deduped[-1][0] < _HEADER_DEDUP_GAP:
            continue
        deduped.append((pos, date))
    return deduped


def parse_exam_file(path: str, exam_type: str) -> list[dict]:
    """
    Parsira jedan PDF ispita i vraća listu rječnika:
      {exam_type, exam_date, task_no, task_text, pdf_page}
    pdf_page je 1-indexed broj stranice u izvornom PDF-u.
    """
    raw, page_offsets = _extract_pdf_pages(path)

    records = []

    header_positions = _find_exam_blocks(raw)
    if not header_positions:
        print(f"  [WARN] Nisam pronašao exam headere u {path}")
        exam_blocks = [(0, "unknown", raw)]
    else:
        exam_blocks = []
        for i, (start, date_str) in enumerate(header_positions):
            end = header_positions[i + 1][0] if i + 1 < len(header_positions) else len(raw)
            exam_blocks.append((start, date_str, raw[start:end]))
        print(f"  Detektirano {len(exam_blocks)} ispita u {path}")

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
