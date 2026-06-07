"""
Heuristički cleaner za task_text prije embeddinga.

Embedding model uhvati C/C++ sintaksu jako jako, što razvodnjava semantički
signal o čemu zadatak zapravo PRIČA. Ako iz teksta uklonimo blokove koda i
prototipove funkcija, embedding bolje hvata prirodno-jezični opis problema.

Strategija: gledamo linije pojedinačno. Linija je "kod" ako:
  - sadrži C/C++ tipove kao prvu riječ (int/void/char/...)
  - sadrži vitičaste zagrade { ili }
  - završava sa ;
  - počinje s #include, if (, for (, while (, return
  - izgleda kao prototip (sadrži "(" i ");" ili "()")
  - sastoji se samo od koda u zagradama i operatora

Čistimo i C-style komentare oblika /* ... */, i sekcije "Prototipovi
navedenih funkcija su:" do prvog praznog reda.
"""

from __future__ import annotations

import re


_C_KEYWORDS = (
    "int", "void", "char", "float", "double", "bool", "long", "short",
    "unsigned", "signed", "static", "const", "struct", "class", "template",
    "typedef", "auto", "size_t",
)

_CODE_LINE_PATTERNS = [
    re.compile(r"^\s*#\s*include\b"),
    re.compile(r"^\s*(?:if|for|while|switch|else|do|return|break|continue)\b[\s(]"),
    re.compile(r"^\s*(?:" + "|".join(_C_KEYWORDS) + r")\s+\w"),
    re.compile(r"^\s*\w+\s*\([^)]*\)\s*\{?\s*$"),  # function signature line
    re.compile(r"^\s*\}\s*;?\s*$"),                # closing brace line
    re.compile(r"^\s*\{\s*$"),                     # opening brace line
    re.compile(r";\s*$"),                          # ends with ;
]

_PROTOTYPE_HEADER = re.compile(
    r"(?:Prototip(?:ovi)?|Funkcij[ae])\s*[A-Za-z\s]*\s*[:\.]?\s*$",
    re.IGNORECASE,
)

_C_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_INLINE_COMMENT = re.compile(r"//[^\n]*")


def _is_code_line(line: str) -> bool:
    s = line.rstrip()
    if not s.strip():
        return False
    # Lots of curly braces or semicolons - clear code
    if "{" in s or "}" in s:
        return True
    if any(pat.search(s) for pat in _CODE_LINE_PATTERNS):
        return True
    # Heavy use of operators / parentheses with no Croatian words - probably code
    non_alpha = sum(1 for ch in s if ch in "{}();=<>+-*/&|!^[]")
    alpha = sum(1 for ch in s if ch.isalpha())
    if alpha > 0 and non_alpha / max(1, alpha) > 0.4:
        return True
    return False


def strip_code(text: str) -> str:
    """
    Vrati samo prirodno-jezični dio task_text-a, bez code blokova i prototipova.
    Ako rezultat ostane prekratak (< 50 chars), vrati cijeli izvorni text kao
    fallback da ne bismo embedirali prazno.
    """
    if not text:
        return ""

    # Ukloni /* ... */ i // komentare
    cleaned = _C_COMMENT.sub(" ", text)
    cleaned = _INLINE_COMMENT.sub(" ", cleaned)

    lines = cleaned.split("\n")
    out: list[str] = []
    skip_until_blank = False
    for line in lines:
        if skip_until_blank:
            if not line.strip():
                skip_until_blank = False
            continue
        if _PROTOTYPE_HEADER.search(line):
            # Prototypes section: skip until next blank line
            skip_until_blank = True
            continue
        if _is_code_line(line):
            continue
        out.append(line)

    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    if len(result) < 50:
        return text.strip()
    return result
