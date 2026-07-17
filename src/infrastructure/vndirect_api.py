"""VnDirect: dong tien khoi ngoai hang ngay + gia dong cua + chi so co ban
(collector.py:435-456, brief.py:32-98)."""
import json
import urllib.request

from src.adapters.gateways import FlowHistory
from src.domain.entities import DayFlow

HEADERS = {"User-Agent": "Mozilla/5.0"}
VND = "https://api-finfo.vndirect.com.vn/v4"
RATIO_LABELS = {
    "MARKETCAP": ("Vốn hóa", lambda v: f"{v/1e12:,.1f} nghìn tỷ"),
    "PRICE_TO_EARNINGS": ("P/E", lambda v: f"{v:.1f}"),
    "PRICE_TO_BOOK": ("P/B", lambda v: f"{v:.2f}"),
    "ROAE_TR_AVG5Q": ("ROE (TB 5 quý)", lambda v: f"{v:.1%}"),
    "EPS_TR": ("EPS (4 quý)", lambda v: f"{v:,.0f} đ"),
}


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


def fetch_prices_text(sym, n=20):
    url = f"{VND}/stock_prices?q=code:{sym}&size={n}&sort=date:desc&fields=date,close,nmVolume"
    rows = list(reversed(json.loads(_get(url))["data"]))
    if not rows:
        return "(không có dữ liệu giá)"
    last, first = rows[-1], rows[0]
    chg = (last["close"] / rows[-6]["close"] - 1) * 100 if len(rows) > 6 else 0
    chg_m = (last["close"] / first["close"] - 1) * 100
    return (f"Giá đóng cửa {last['date']}: {last['close']*1000:,.0f} đồng\n"
            f"Thay đổi 1 tuần: {chg:+.1f}% | {len(rows)} phiên gần nhất: {chg_m:+.1f}%")


class VnDirect(FlowHistory):
    def foreign_daily(self, code, n=10):
        """Dong tien khoi ngoai hang ngay (code hoac VNINDEX cho ca san)."""
        url = f"{VND}/foreigns?q=code:{code}&size={n}&sort=tradingDate:desc"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            rows = list(reversed(json.load(r)["data"]))  # oldest -> newest
        return [DayFlow(trading_date=r["tradingDate"], net_val=r["netVal"] or 0) for r in rows]

    def closes(self, code, n=10):
        """Gia dong cua, cu -> moi. Loi/rong -> []."""
        ep = "vnmarket_prices" if code == "VNINDEX" else "stock_prices"
        url = f"{VND}/{ep}?q=code:{code}&size={n}&sort=date:desc&fields=date,close"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return [row["close"] for row in reversed(json.load(r)["data"])]
        except Exception:
            return []
