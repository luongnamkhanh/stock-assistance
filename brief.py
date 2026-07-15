"""/brief MA — ban tin tong hop 1 ma: dong tien khoi ngoai + co ban + tin tuc.

Gom du lieu tu VNDirect + Google News, dua cho Claude tong hop thanh ban brief
tieng Viet ngan cho Telegram. INFORMATION ONLY — khong khuyen nghi mua/ban.

Credentials: ANTHROPIC_API_KEY hoac ANTHROPIC_AUTH_TOKEN trong env.

Usage: python brief.py HPG   # in brief ra stdout (kiem tra nhanh)
"""

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from collector import fetch_foreign_daily, format_trend

HEADERS = {"User-Agent": "Mozilla/5.0"}
VND = "https://api-finfo.vndirect.com.vn/v4"
RATIO_LABELS = {
    "MARKETCAP": ("Vốn hóa", lambda v: f"{v/1e12:,.1f} nghìn tỷ"),
    "PRICE_TO_EARNINGS": ("P/E", lambda v: f"{v:.1f}"),
    "PRICE_TO_BOOK": ("P/B", lambda v: f"{v:.2f}"),
    "ROAE_TR_AVG5Q": ("ROE (TB 5 quý)", lambda v: f"{v:.1%}"),
    "EPS_TR": ("EPS (4 quý)", lambda v: f"{v:,.0f} đ"),
}

SYSTEM = """Bạn là trợ lý dữ liệu tài chính cho nhà đầu tư cá nhân Việt Nam.
Nhiệm vụ: tổng hợp dữ liệu được cung cấp thành bản tin ngắn về một cổ phiếu.

Quy tắc bắt buộc:
- CHỈ tổng hợp và diễn giải dữ liệu được đưa. Không bịa số liệu.
- TUYỆT ĐỐI không khuyến nghị mua/bán/nắm giữ, không dự đoán giá mục tiêu.
- Nếu dữ liệu mâu thuẫn (vd: KN bán nhưng giá tăng), hãy chỉ ra điều đó.
- Tiếng Việt, văn xuôi tự nhiên, tối đa 220 từ, plain text (không markdown).
- Cấu trúc: 1 câu tổng quan → dòng tiền khối ngoại → định giá/cơ bản → tin tức đáng chú ý → 1 câu về điều đáng theo dõi nhất.
- Kết thúc bằng dòng: "⚠️ Thông tin tham khảo, không phải khuyến nghị đầu tư." """


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read()


def fetch_fundamentals(sym):
    codes = ",".join(RATIO_LABELS)
    url = (f"{VND}/ratios/latest?filter=ratioCode:{codes}"
           f"&where=code:{sym}&order=reportDate&fields=ratioCode,value,reportDate")
    rows = json.loads(_get(url))["data"]
    lines = []
    for r in rows:
        label, fmt = RATIO_LABELS[r["ratioCode"]]
        lines.append(f"{label}: {fmt(r['value'])} (tại {r['reportDate']})")
    return "\n".join(lines) or "(không có dữ liệu)"


def fetch_prices(sym, n=20):
    url = f"{VND}/stock_prices?q=code:{sym}&size={n}&sort=date:desc&fields=date,close,nmVolume"
    rows = list(reversed(json.loads(_get(url))["data"]))
    if not rows:
        return "(không có dữ liệu giá)"
    last, first = rows[-1], rows[0]
    chg = (last["close"] / rows[-6]["close"] - 1) * 100 if len(rows) > 6 else 0
    chg_m = (last["close"] / first["close"] - 1) * 100
    return (f"Giá đóng cửa {last['date']}: {last['close']:,.2f} (nghìn đồng)\n"
            f"Thay đổi 1 tuần: {chg:+.1f}% | {len(rows)} phiên gần nhất: {chg_m:+.1f}%")


def fetch_news(sym, n=6):
    q = urllib.parse.quote(f'"{sym}" cổ phiếu')
    raw = _get(f"https://news.google.com/rss/search?q={q}&hl=vi&gl=VN&ceid=VN:vi")
    items = ET.fromstring(raw).findall(".//item")[:n]
    lines = [f"- {it.findtext('title')} ({it.findtext('pubDate', '')[:16]})" for it in items]
    return "\n".join(lines) or "(không thấy tin tức gần đây)"


def gather(sym):
    sections = {}
    for name, fn in [("DÒNG TIỀN KHỐI NGOẠI 10 PHIÊN", lambda: format_trend(sym, fetch_foreign_daily(sym))),
                     ("GIÁ", lambda: fetch_prices(sym)),
                     ("CHỈ SỐ CƠ BẢN", lambda: fetch_fundamentals(sym)),
                     ("TIN TỨC GẦN ĐÂY", lambda: fetch_news(sym))]:
        try:
            sections[name] = fn()
        except Exception as e:
            sections[name] = f"(lỗi khi lấy dữ liệu: {e})"
    return "\n\n".join(f"### {k}\n{v}" for k, v in sections.items())


def _call_gemini(system, user):
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body,
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
    j = json.load(urllib.request.urlopen(req, timeout=120))
    return "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])


def _call_claude(system, user):
    import anthropic  # lazy: collector chay duoc ke ca khi chua cai SDK
    resp = anthropic.Anthropic().messages.create(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def call_llm(system, user):
    # uu tien Claude neu co API key rieng; khong thi Gemini (free tier)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _call_claude(system, user)
    if os.environ.get("GEMINI_API_KEY"):
        return _call_gemini(system, user)
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return _call_claude(system, user)
    raise RuntimeError("Chưa cấu hình LLM key (GEMINI_API_KEY hoặc ANTHROPIC_API_KEY)")


def build_brief(sym):
    sym = sym.upper()
    context = gather(sym)
    text = call_llm(SYSTEM, f"Dữ liệu về cổ phiếu {sym} hôm nay:\n\n{context}\n\nViết bản tin.").strip()
    return f"📋 Brief {sym}\n\n{text}"[:4000]  # Telegram cap 4096


if __name__ == "__main__":
    import sys
    print(build_brief(sys.argv[1] if len(sys.argv) > 1 else "HPG"))
