
import os, json, re, time
from typing import List, Dict, Any, Optional, Tuple
from fastmcp import FastMCP
from rapidfuzz import process, fuzz

from .index_utils import BASE, INDEX_PATH
from .gzk_category import crawl_category
from .pdf_ingest import pdf_to_text_cached, split_articles, build_snippet, add_to_index


mcp = FastMCP("kosovo-laws-mcp")
SEED_TEMPLATE = BASE + "/ActsByCategoryInst.aspx?Index=3&InstID={inst_id}&CatID={cat_id}"


def _read_index() -> List[Dict[str, Any]]:
    if not os.path.exists(INDEX_PATH):
        return []
    rows = []
    with open(INDEX_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _index_size() -> int:
    try:
        with open(INDEX_PATH, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def _parse_years(prompt: str) -> Tuple[Optional[int], Optional[int]]:
    txt = prompt.lower()
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", txt)]
    if len(years) >= 2:
        return (min(years[0], years[1]), max(years[0], years[1]))
    if len(years) == 1:
        return (years[0], years[0])
    m = re.search(r"nga\s+(?:19|20)\d{2}\s+(?:deri|–|-|—)\s+(?:19|20)\d{2}", txt)
    if m:
        yrs = [int(y) for y in re.findall(r"(?:19|20)\d{2}", m.group(0))]
        if len(yrs) >= 2:
            return (min(yrs[0], yrs[1]), max(yrs[0], yrs[1]))
    return (None, None)


def _looks_like_listing(prompt: str) -> bool:
    kw = [
        "cilat janë ligjet", "lista e ligjeve", "ligjet e publikuara",
        "ligjet e vitit", "të gjitha ligjet", "listo ligjet", "ligjet në"
    ]
    t = prompt.lower()
    return any(k in t for k in kw)


def _list_category_pdfs_core(inst_id: int = 1, cat_id: int = 6,
                             from_year: Optional[int] = None, to_year: Optional[int] = None,
                             limit: int = 200) -> List[Dict[str, Any]]:
    seed = SEED_TEMPLATE.format(inst_id=inst_id, cat_id=cat_id)
    rows = crawl_category(seed, from_year=from_year, to_year=to_year)
    return sorted(rows, key=lambda r: (r.get("year") or 0, r.get("published_on") or ""), reverse=True)[:limit]


def _ingest_rows(rows: List[Dict[str, Any]]) -> int:
    indexed = 0
    total = len(rows)
    for i, r in enumerate(rows, start=1):
        pdf = r.get("pdf_url")
        if not pdf:
            continue
        print(f"📘 [{i}/{total}] Po indeksohet: {r.get('title', 'Pa titull')} ({r.get('year')})")
        text = pdf_to_text_cached(pdf)
        arts = split_articles(text)
        records = []
        for a in arts:
            records.append({
                "act_id": r.get("act_id"),
                "title": r.get("title"),
                "article_no": a["article_no"],
                "snippet": build_snippet(a["body"]),
                "url": r.get("detail_url") or pdf,
                "year": r.get("year"),
                "pdf_url": pdf
            })
        indexed += add_to_index(records)
    print(f"✅ U përfundua ingestion-i ({indexed} nene të shtuara).")
    return indexed


def _ingest_pdfs_core(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    added = _ingest_rows(rows)
    return {"indexed": added, "index_path": INDEX_PATH}


_LOCK_PATH = os.path.join(os.path.dirname(INDEX_PATH), ".ingest.lock")

def _with_lock(fn):
    def wrapper(*args, **kwargs):
        start = time.time()
        while True:
            try:
                fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                os.close(fd)
                break
            except FileExistsError:
                if time.time() - start > 60:
                    break
                time.sleep(0.25)
        try:
            return fn(*args, **kwargs)
        finally:
            try:
                if os.path.exists(_LOCK_PATH):
                    os.remove(_LOCK_PATH)
            except Exception:
                pass
    return wrapper

@_with_lock
def _ensure_index_years(inst_id: int = 1, cat_id: int = 6,
                        from_year: int = 2020, to_year: int = 2025,
                        max_rows: int = 250) -> Dict[str, Any]:
    if _index_size() > 0:
        return {"indexed": 0, "index_path": INDEX_PATH, "skipped": True}
    rows = _list_category_pdfs_core(inst_id=inst_id, cat_id=cat_id,
                                    from_year=from_year, to_year=to_year, limit=max_rows)
    added = _ingest_rows(rows)
    return {"indexed": added, "index_path": INDEX_PATH, "skipped": False}

@_with_lock
def _ingest_targeted_for_query(query: str,
                               inst_id: int = 1, cat_id: int = 6,
                               horizon_from: int = 2018, horizon_to: int = 2025,
                               k_pick: int = 60) -> int:
    """Ingestion i shpejtë për aktet që lidhen me pyetjen."""
    rows = _list_category_pdfs_core(inst_id=inst_id, cat_id=cat_id,
                                    from_year=horizon_from, to_year=horizon_to, limit=500)
    if not rows:
        return 0
    corpus = [r["title"] for r in rows]
    matches = process.extract(query, corpus, scorer=fuzz.WRatio, limit=k_pick)
    chosen = []
    for m in matches:
        score, idx = (m[1], m[2]) if isinstance(m, tuple) else (m.score, m.index)
        if 0 <= idx < len(rows):
            chosen.append(rows[idx])
    return _ingest_rows(chosen)


def _search_articles_core(query: str, k: int = 8) -> List[Dict[str, Any]]:
    rows = _read_index()
    if not rows:
        return []
    corpus = [f"{r['title']} {r['article_no']} {r['snippet']}" for r in rows]
    results = process.extract(query, corpus, scorer=fuzz.WRatio, limit=k)
    out = []
    for r in results:
        score, idx = (r[1], r[2]) if isinstance(r, tuple) else (r.score, r.index)
        item = dict(rows[idx])
        item["score"] = int(score)
        out.append(item)
    return out

def _search_acts_core(query: str, inst_id: int = 1, cat_id: int = 6,
                      from_year: Optional[int] = None, to_year: Optional[int] = None,
                      k: int = 20) -> List[Dict[str, Any]]:
    rows = _list_category_pdfs_core(inst_id=inst_id, cat_id=cat_id,
                                    from_year=from_year, to_year=to_year, limit=500)
    if not rows:
        return []
    corpus = [r["title"] for r in rows]
    results = process.extract(query, corpus, scorer=fuzz.WRatio, limit=k)
    out = []
    for r in results:
        score, idx = (r[1], r[2]) if isinstance(r, tuple) else (r.score, r.index)
        item = dict(rows[idx])
        item["score"] = int(score)
        out.append(item)
    return out


def _bootstrap_index_if_needed(query_hint: Optional[str] = None) -> None:
    MIN_ROWS = 50
    if _index_size() >= MIN_ROWS:
        return
    _ensure_index_years(from_year=2020, to_year=2025, max_rows=300)
    if _index_size() >= MIN_ROWS:
        return
    if query_hint:
        _ingest_targeted_for_query(query_hint, horizon_from=2015, horizon_to=2025, k_pick=80)


@mcp.tool("list_category_pdfs")
def list_category_pdfs(inst_id: int = 1, cat_id: int = 6,
                       from_year: Optional[int] = None, to_year: Optional[int] = None,
                       limit: int = 200) -> List[Dict[str, Any]]:
    return _list_category_pdfs_core(inst_id, cat_id, from_year, to_year, limit)

@mcp.tool("ingest_pdfs")
def ingest_pdfs(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _ingest_pdfs_core(rows)

@mcp.tool("index_stats")
def index_stats() -> Dict[str, Any]:
    return {"index_rows": _index_size(), "index_path": INDEX_PATH}

@mcp.tool("ensure_index")
def ensure_index(inst_id: int = 1, cat_id: int = 6,
                 from_year: int = 2020, to_year: int = 2025,
                 max_rows: int = 250) -> Dict[str, Any]:
    return _ensure_index_years(inst_id, cat_id, from_year, to_year, max_rows)

@mcp.tool("search_articles")
def search_articles(query: str, k: int = 8) -> List[Dict[str, Any]]:
    return _search_articles_core(query, k)

@mcp.tool("which_law_applies")
def which_law_applies(prompt: str, k: int = 8) -> Dict[str, Any]:
    _bootstrap_index_if_needed(prompt)
    hits = _search_articles_core(prompt, k)
    if not hits:
        alt = _search_acts_core(prompt, k)
        hits = [{"title": r["title"], "article_no": "(titull akti)",
                 "snippet": r.get("title", ""), "url": r.get("detail_url"),
                 "pdf_url": r.get("pdf_url"), "year": r.get("year"), "score": r.get("score", 0)} for r in alt]
    return {"candidates": hits,
            "disclaimer": "Ky rezultat është informues dhe NUK përbën këshillë ligjore. Verifiko në Gazetën Zyrtare."}

@mcp.tool("ask")
def ask(prompt: str) -> Dict[str, Any]:
    fy, ty = _parse_years(prompt)
    try:
        if fy or ty or _looks_like_listing(prompt):
            result = _list_category_pdfs_core(inst_id=1, cat_id=6,
                                              from_year=fy, to_year=ty,
                                              limit=200 if (fy or ty) else 50)
        else:
            _bootstrap_index_if_needed(prompt)
            result = which_law_applies.fn(prompt)
        return {"ok": True, "prompt": prompt, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e), "prompt": prompt}

@mcp.tool("debug_category")
def debug_category(inst_id: int = 1, cat_id: int = 6) -> Dict[str, Any]:
    from .index_utils import http_get_cached
    from bs4 import BeautifulSoup
    from .gzk_category import extract_year_links
    seed = SEED_TEMPLATE.format(inst_id=inst_id, cat_id=cat_id)
    html = http_get_cached(seed)
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "")[:120]
    anchors = len(soup.select("a[href*='ActsByCategoryInst.aspx'][href*='InstID='][href*='CatID=']"))
    years = extract_year_links(seed)
    return {"seed": seed, "page_title": title, "html_len": len(html),
            "year_anchor_candidates": anchors,
            "years_found": [y.get("year") for y in years][:12],
            "years_count": len(years)}


LOG_DIR = os.path.join(os.path.dirname(INDEX_PATH), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "requests.log")

def _log_request(tool: str, payload: Any):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {tool}: {json.dumps(payload, ensure_ascii=False)}\n")


if __name__ == "__main__":
    print("🚀 Running Kosovo Laws MCP (Stable) – tools: list_category_pdfs, ingest_pdfs, index_stats, "
          "ensure_index, search_articles, which_law_applies, ask, debug_category")
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
