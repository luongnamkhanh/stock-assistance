"""Tin tuc lien quan 1 ma tu Google News RSS."""
import urllib.parse
import xml.etree.ElementTree as ET

from src.infrastructure.http import http_get


def fetch_news(sym, n=6):
    q = urllib.parse.quote(f'"{sym}" cổ phiếu')
    raw = http_get(f"https://news.google.com/rss/search?q={q}&hl=vi&gl=VN&ceid=VN:vi")
    items = ET.fromstring(raw).findall(".//item")[:n]
    lines = []
    for i, it in enumerate(items, 1):
        src = it.findtext("source") or "?"
        date = it.findtext("pubDate", "")[5:16]  # "15 Jul 2026"
        lines.append(f"[{i}] ({src}, {date}) {it.findtext('title')}")
    return "\n".join(lines) or "(không thấy tin tức gần đây)"
