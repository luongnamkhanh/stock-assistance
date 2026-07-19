"""VnDirect: dong tien khoi ngoai hang ngay + gia dong cua + chi so co ban."""
from src.adapters.gateways import FlowHistory
from src.domain.entities import DayFlow
from src.infrastructure.http import http_json

VND = "https://api-finfo.vndirect.com.vn/v4"
RATIO_LABELS = {
    "MARKETCAP": ("Vốn hóa", lambda v: f"{v/1e12:,.1f} nghìn tỷ"),
    "PRICE_TO_EARNINGS": ("P/E", lambda v: f"{v:.1f}"),
    "PRICE_TO_BOOK": ("P/B", lambda v: f"{v:.2f}"),
    "ROAE_TR_AVG5Q": ("ROE (TB 5 quý)", lambda v: f"{v:.1%}"),
    "EPS_TR": ("EPS (4 quý)", lambda v: f"{v:,.0f} đ"),
}


def fetch_fundamentals(sym):
    codes = ",".join(RATIO_LABELS)
    url = (f"{VND}/ratios/latest?filter=ratioCode:{codes}"
           f"&where=code:{sym}&order=reportDate&fields=ratioCode,value,reportDate")
    rows = http_json(url)["data"]
    lines = []
    for r in rows:
        label, fmt = RATIO_LABELS[r["ratioCode"]]
        lines.append(f"{label}: {fmt(r['value'])} (tại {r['reportDate']})")
    return "\n".join(lines) or "(không có dữ liệu)"


def fetch_prices_text(sym, n=20):
    url = f"{VND}/stock_prices?q=code:{sym}&size={n}&sort=date:desc&fields=date,close,nmVolume"
    rows = list(reversed(http_json(url)["data"]))
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
        rows = list(reversed(http_json(url, timeout=20)["data"]))  # oldest -> newest
        return [DayFlow(trading_date=r["tradingDate"], net_val=r["netVal"] or 0) for r in rows]

    def ohlc(self, code, n=20):
        """(closes, highs, lows) cu -> moi, don vi VND (VNINDEX: diem). Loi/rong -> ([], [], [])."""
        ep = "vnmarket_prices" if code == "VNINDEX" else "stock_prices"
        url = f"{VND}/{ep}?q=code:{code}&size={n}&sort=date:desc&fields=date,close,high,low"
        try:
            rows = list(reversed(http_json(url, timeout=20)["data"]))
        except Exception:
            return ([], [], [])
        k = 1 if code == "VNINDEX" else 1000  # stock_prices tra nghin dong -> chuan hoa VND tai nguon
        return ([r["close"] * k for r in rows], [r["high"] * k for r in rows], [r["low"] * k for r in rows])

    def daily_closes(self, code, n=30):
        """[(date, close_VND)] cu -> moi — cho scorecard tinh return sau tin hieu."""
        url = f"{VND}/stock_prices?q=code:{code}&size={n}&sort=date:desc&fields=date,close"
        rows = list(reversed(http_json(url, timeout=20)["data"]))
        return [(r["date"], (r["close"] or 0) * 1000) for r in rows]

    def index_quote(self):
        """Diem VN-Index phien gan nhat: {'close','change','pct'} | None neu loi."""
        try:
            d = http_json(f"{VND}/vnmarket_prices?q=code:VNINDEX&size=1&sort=date:desc", timeout=15)["data"][0]
            return {"close": float(d["close"]), "change": float(d["change"]), "pct": float(d["pctChange"])}
        except Exception:
            return None
