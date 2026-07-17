"""Tin tuc lien quan 1 ma tu Google News RSS (brief.py:101-110)."""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read()


def fetch_news(sym, n=6):
    q = urllib.parse.quote(f'"{sym}" cổ phiếu')
    raw = _get(f"https://news.google.com/rss/search?q={q}&hl=vi&gl=VN&ceid=VN:vi")
    items = ET.fromstring(raw).findall(".//item")[:n]
    lines = []
    for i, it in enumerate(items, 1):
        src = it.findtext("source") or "?"
        date = it.findtext("pubDate", "")[5:16]  # "15 Jul 2026"
        lines.append(f"[{i}] ({src}, {date}) {it.findtext('title')}")
    return "\n".join(lines) or "(không thấy tin tức gần đây)"
