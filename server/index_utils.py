import os, re, json, time, hashlib, urllib.parse as _u
from typing import Optional
import requests
from bs4 import BeautifulSoup

BASE = "https://gzk.rks-gov.net"
HEADERS = {
    "User-Agent": "kosovo-laws-mcp/1.0 (crawler)",
    "Accept-Language": "sq-AL,sq;q=0.9,en;q=0.5",
    "Cookie": "LangID=1"
}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(ROOT, "cache")
HTML_DIR = os.path.join(CACHE_DIR, "html")
PDF_DIR = os.path.join(CACHE_DIR, "pdf")
TXT_DIR = os.path.join(CACHE_DIR, "txt")
INDEX_PATH = os.path.join(CACHE_DIR, "index.jsonl")

for d in [CACHE_DIR, HTML_DIR, PDF_DIR, TXT_DIR]:
    os.makedirs(d, exist_ok=True)

SESS = requests.Session()

def urljoin(url: str) -> str:
    return url if url.startswith("http") else _u.urljoin(BASE, url)

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:24]

def http_get_cached(url: str) -> str:
    h = _hash(url)
    p = os.path.join(HTML_DIR, f"{h}.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    r = SESS.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    text = r.text
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    time.sleep(0.5)
    return text

def soup_for(url: str) -> BeautifulSoup:
    return BeautifulSoup(http_get_cached(url), "lxml")

def download_pdf(url: str) -> Optional[str]:
    if not url:
        return None
    u = urljoin(url)
    h = _hash(u)
    p = os.path.join(PDF_DIR, f"{h}.pdf")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return p
    r = SESS.get(u, headers=HEADERS, timeout=60)
    r.raise_for_status()
    with open(p, "wb") as f:
        f.write(r.content)
    time.sleep(0.5)
    return p

def read_text_cache(key: str) -> Optional[str]:
    p = os.path.join(TXT_DIR, f"{_hash(key)}.txt")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return None

def write_text_cache(key: str, text: str) -> str:
    p = os.path.join(TXT_DIR, f"{_hash(key)}.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p
