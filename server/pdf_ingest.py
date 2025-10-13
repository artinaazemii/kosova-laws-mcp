from io import StringIO
import re, json, os
from typing import Dict, List, Any, Optional
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams


try:
   
    from pdfminer.high_level import extract_text_to_fp as _extract_text_to_fp
    extract_text_to_fp = _extract_text_to_fp
except Exception:
    pass

from pdfminer.layout import LAParams
from .index_utils import download_pdf, read_text_cache, write_text_cache, INDEX_PATH, soup_for

ARTICLE_PATTERNS = [
    r"(?mi)^Neni\s+\d+[\.:]?",
    r"(?mi)^Article\s+\d+[\.:]?",
    r"(?mi)^Član\s+\d+[\.:]?",
]

def pdf_to_text_cached(pdf_url: str) -> str:
    cached = read_text_cache(pdf_url)
    if cached is not None:
        return cached
    path = download_pdf(pdf_url)
    if not path:
        return ""
    buf = StringIO()
    with open(path, "rb") as f:
        extract_text_to_fp(f, buf, laparams=LAParams(), output_type="text", codec=None)
    text = buf.getvalue()
    write_text_cache(pdf_url, text)
    return text

def split_articles(text: str) -> List[Dict[str, str]]:
    if not text:
        return []

    matches = []
    for pat in ARTICLE_PATTERNS:
        for m in re.finditer(pat, text):
            matches.append((m.start(), m.group(0)))
    if not matches:
   
        return [{"article_no": "Teksti", "body": text.strip()}]
    matches.sort()
    chunks = []
    for i, (start, heading) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
      
        mnum = re.search(r"(Neni|Article|Član)\s+(\d+)", heading, flags=re.I)
        art_no = f"{heading}" if not mnum else f"Neni {mnum.group(2)}"
        chunks.append({"article_no": art_no, "body": body})
    return chunks

def build_snippet(s: str, maxlen: int = 450) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= maxlen else s[: maxlen - 3] + "..."

def add_to_index(records: List[Dict[str, Any]]) -> int:
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def detail_html_to_text(detail_url: str) -> str:

    try:
        soup = soup_for(detail_url)
        div = soup.select_one("#MainContent_divContent")
        if not div:
            
            return soup.get_text("\n", strip=True)
        text = div.get_text("\n", strip=True)
        return text
    except Exception:
        return ""
