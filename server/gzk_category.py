from typing import Any, Dict, List, Optional, Tuple
import re, os, hashlib, time, urllib.parse as _u
from bs4 import BeautifulSoup
from .index_utils import SESS, HEADERS, http_get_cached, urljoin, HTML_DIR

SEED_URL = "https://gzk.rks-gov.net/ActsByCategoryInst.aspx?Index=3&InstID={inst_id}&CatID={cat_id}"



def _hidden_fields(soup: BeautifulSoup) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for inp in soup.select("input[type='hidden']"):
        n = inp.get("name")
        if not n:
            continue
        v = inp.get("value", "")
        data[n] = v
    data.setdefault("__EVENTTARGET", "")
    data.setdefault("__EVENTARGUMENT", "")
    return data

def _parse_postback_href(href: str) -> Optional[Tuple[str, str]]:
    if not href:
        return None
    m = re.search(r"__doPostBack\('([^']+)'\s*,\s*'([^']*)'\)", href)
    return (m.group(1), m.group(2)) if m else None

def _cache_write(key: str, html: str) -> None:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    p = os.path.join(HTML_DIR, f"{h}.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)

def _cache_read(key: str) -> Optional[str]:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    p = os.path.join(HTML_DIR, f"{h}.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return None



_SERB_KEYWORDS = ("zakon", "promenjen", "uzrokuje", "član", "objavljen", "sporazuma", "ugovora", "kreditu", "o ")

def _is_sq_line(line: str) -> bool:
    t = (line or "").strip().lower()
    if not t:
        return False

    if "ligji" in t or "republikës së kosovës" in t or "për " in t:
        return True

    if any(k in t for k in _SERB_KEYWORDS):
        return False
    return True

def _force_sq_url(detail_url: str) -> str:
    parsed = _u.urlparse(detail_url)
    q = _u.parse_qs(parsed.query)
    q["LangID"] = ["1"]
    new_q = _u.urlencode({k: v[0] for k, v in q.items()})
    return _u.urlunparse(parsed._replace(query=new_q))

def _post_lang_dropdown(detail_url: str, detail_html: str) -> Optional[str]:
    soup = BeautifulSoup(detail_html, "lxml")
    sel = soup.select_one("#MainContent_ddlLang, select[name*='Lang']")
    if not sel:
        return None
    opt_sq = None
    for opt in sel.select("option"):
        if "shqip" in opt.get_text(" ", strip=True).lower():
            opt_sq = opt
            break
    if not opt_sq:
        return None
    data = _hidden_fields(soup)
    data["__EVENTTARGET"] = sel.get("name") or ""
    data["__EVENTARGUMENT"] = opt_sq.get("value") or ""
    headers = dict(HEADERS)
    headers["Referer"] = detail_url
    r = SESS.post(detail_url, headers=headers, data=data, timeout=60)
    r.raise_for_status()

    if "Republika e Kosovës" not in r.text and "Ligji" not in r.text:
        return http_get_cached(_force_sq_url(detail_url))

    return r.text

def _title_from_detail(detail_html: str) -> Optional[str]:
    ds = BeautifulSoup(detail_html, "lxml")
    node = ds.select_one("#MainContent_lblTitle") or ds.select_one("h1")
    raw = node.get_text("\n", strip=True) if node else ""
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    for l in lines:
        if _is_sq_line(l):
            return l

    for cand in ds.select("#MainContent_UpdatePanel1, .content, body *"):
        txt = cand.get_text(" ", strip=True).strip() if cand else ""
        if txt and "Ligji" in txt:
            cut = re.split(r"[\n–]", txt, maxsplit=1)[0].strip()
            return cut

    return raw or None

def _strip_foreign_suffix(title: str) -> str:
    t = title
    t = re.sub(r"\s+[–-]\s+(ZAKON|LAW)\b.*$", "", t, flags=re.I)
    for bad in ("Promenjen od", "Uzrokuje promene u aktima", "Ndryshohet / Plotësohet / Shfuqizohet nga"):
        t = t.replace(bad, "").strip(" –-")
    return t.strip()

def _extract_act_number(s: str) -> Optional[str]:
    m = re.search(r"(\d{2}/L-\d{3})", s or "", flags=re.I)
    return m.group(1) if m else None

def _normalize_sq_title(title_detail: Optional[str], title_list: str) -> str:
    td = (title_detail or "").strip()
    tl = (title_list or "").strip()

    if td:
        td = _strip_foreign_suffix(td)


    if td and _is_sq_line(td):
        return td


    serb_to_sq = {
        "ZAKON": "Ligji",
        "O": "Për",
        "IZMENI": "ndryshimin",
        "DOPUNI": "plotësimin",
        "ZAKONA": "të Ligjit",
        "JAVNIM SLUŽBENICIMA": "zyrtarëve publikë",
        "TUŽILAČKOM SAVETU KOSOVA": "Këshillin Prokurorial të Kosovës",
        "KOSOVA": "Kosovës",
    }

    base = _strip_foreign_suffix(td or tl)
    for k, v in serb_to_sq.items():
        base = re.sub(rf"\b{k}\b", v, base, flags=re.I)

    base = re.sub(r"^(ZAKON|LAW)\s+NO?\.?\s*", "", base, flags=re.I).strip()
    base = re.sub(r"^O\s+", "Për ", base, flags=re.I).strip()
    base = re.sub(r"[“”\"']", "", base).strip()

    base = re.sub(r"\s*[-–]\s*(ZAKON|LAW)\b.*$", "", base, flags=re.I).strip()


    nr = _extract_act_number(td) or _extract_act_number(tl) or ""


    if nr:
        if not base.lower().startswith("ligji"):
            base = f"Ligji nr. {nr} – {base}"
        return base.strip()

    if not base.lower().startswith("ligji"):
        base = f"Ligji – {base}"
    return base.strip()


def _extract_year_triggers(seed_html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(seed_html, "lxml")
    triggers: List[Dict[str, Any]] = []

    for a in soup.select("a[href^='javascript:__doPostBack']"):
        txt = a.get_text(" ", strip=True)
        yrs = re.findall(r"(20\d{2}|19\d{2})", txt)
        year = int(yrs[0]) if yrs else None
        pb = _parse_postback_href(a.get("href"))
        if pb:
            triggers.append({"method": "post", "target": pb[0], "arg": pb[1], "year": year})

    for a in soup.select("a[href*='ActsByCategoryInst.aspx'][href*='InstID='][href*='CatID=']"):
        href = a.get("href") or ""
        if href.lower().startswith("javascript:"):
            continue
        txt = a.get_text(" ", strip=True)
        yrs = re.findall(r"(20\d{2}|19\d{2})", txt)
        year = int(yrs[0]) if yrs else None
        url = urljoin(href)
        if "ActsByCategoryInst.aspx" in url:
            triggers.append({"method": "get", "url": url, "year": year})

    seen = set()
    out: List[Dict[str, Any]] = []
    for t in sorted(triggers, key=lambda d: d.get("year") or 0, reverse=True):
        key = (t.get("method"), t.get("target"), t.get("arg"), t.get("url"))
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out

def _fetch_year_html(seed_url: str, seed_html: str, trig: Dict[str, Any]) -> str:
    cache_key = f"{seed_url}|{trig.get('method')}|{trig.get('target')}|{trig.get('arg')}|{trig.get('url')}"
    c = _cache_read(cache_key)
    if c:
        return c

    if trig.get("method") == "get" and trig.get("url"):
        html = http_get_cached(trig["url"])
        _cache_write(cache_key, html)
        return html

    soup = BeautifulSoup(seed_html, "lxml")
    data = _hidden_fields(soup)
    data["__EVENTTARGET"] = trig.get("target", "")
    data["__EVENTARGUMENT"] = trig.get("arg", "")
    headers = dict(HEADERS)
    headers["Referer"] = seed_url
    r = SESS.post(seed_url, headers=headers, data=data, timeout=60)
    r.raise_for_status()
    html = r.text
    _cache_write(cache_key, html)
    time.sleep(0.4)
    return html


def _pick_published_on(scope_text: str) -> Optional[str]:
    m_pub = (re.search(r"(Publikuar më|Published on|Objavljen)\s*[:\-]?\s*(\d{2}[./]\d{2}[./]\d{4})", scope_text, flags=re.I)
             or re.search(r"(\d{2}[./]\d{2}[./]\d{4})", scope_text))
    if m_pub:
        return m_pub.group(2) if (m_pub.lastindex and m_pub.lastindex >= 2) else m_pub.group(1)
    return None

def _extract_acts_from_html(html: str, year: Optional[int]) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one(
        "#MainContent_UpdatePanel1 .col-md-9, #MainContent_UpdatePanel1 .col-sm-9, .rightCol, .acts"
    ) or soup

    acts: List[Dict[str, Any]] = []
    for link in container.select("a[href*='ActDetail.aspx?ActID=']"):
        list_title = link.get_text(" ", strip=True)
        detail_url = urljoin(link.get("href"))


        detail_html_orig = http_get_cached(detail_url)
        detail_html_sq = _post_lang_dropdown(detail_url, detail_html_orig) or \
                         http_get_cached(_force_sq_url(detail_url)) or \
                         detail_html_orig

        title_detail = _title_from_detail(detail_html_sq)
        title = _normalize_sq_title(title_detail, list_title)

        if not _is_sq_line(title):
            continue  #

        pdf_url = None
        for parent in [link, link.parent, getattr(link.parent, "parent", None)]:
            if parent:
                a = parent.select_one("a[href$='.pdf'], a[href*='.pdf?'], a[href*='DownloadDocument.aspx']")
                if a:
                    pdf_url = urljoin(a.get("href"))
                    break
        if not pdf_url:
            ds = BeautifulSoup(detail_html_sq, "lxml")
            a = ds.select_one("a[href$='.pdf'], a[href*='.pdf?'], a[href*='DownloadDocument.aspx']")
            if a:
                pdf_url = urljoin(a.get("href"))

        scope_text = " ".join([
            link.parent.get_text(" ", strip=True) if link.parent else "",
            container.get_text(" ", strip=True)[:2000]
        ])
        published_on = _pick_published_on(scope_text)
        m_id = re.search(r"ActID=(\d+)", detail_url)

        acts.append({
            "institution": "Kuvendi",
            "category": "Ligje",
            "year": year,
            "title": title,
            "act_id": m_id.group(1) if m_id else None,
            "detail_url": _force_sq_url(detail_url),
            "pdf_url": pdf_url,
            "published_on": published_on
        })
    return acts


def crawl_category(seed_url: str, from_year: Optional[int] = None, to_year: Optional[int] = None) -> List[Dict[str, Any]]:
    seed_html = http_get_cached(seed_url)
    triggers = _extract_year_triggers(seed_html)

    results: List[Dict[str, Any]] = []
    if not triggers:
        results.extend(_extract_acts_from_html(seed_html, year=None))
        return results

    for t in triggers:
        y = t.get("year")
        if from_year and y and y < from_year:
            continue
        if to_year and y and y > to_year:
            continue
        html = _fetch_year_html(seed_url, seed_html, t)
        results.extend(_extract_acts_from_html(html, year=y))

    seen = set()
    out: List[Dict[str, Any]] = []
    for r in sorted(results, key=lambda x: (x.get("year") or 0, x.get("published_on") or ""), reverse=True):
        key = (r.get("act_id"), r.get("title"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def extract_year_links(seed_url: str) -> List[Dict[str, Any]]:
    seed_html = http_get_cached(seed_url)
    return _extract_year_triggers(seed_html)
