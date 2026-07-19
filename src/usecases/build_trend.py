"""Boi canh xu huong: noi alert intraday voi cac phien da chot
+ thong bao xu huong toan cuc/1 ma cho /trend, script, summary."""
from src.adapters import presenters
from src.config import MOVERS_MIN_NET, now_vn
from src.domain.entities import DayFlow

_ctx_cache = {}   # sym -> ctx cua _ctx_day: phien da chot + story hom truoc khong doi trong ngay
_ctx_day = None


def trend_ctx(sym, repo, flows):
    """Loi mang/API -> chuoi rong (khong cache), alert van gui binh thuong. Chi giu phien
    DA CHOT (hom nay da co dong 'Ca phien' trong alert roi). Kem dac tinh phien gan nhat
    tu day_story + hop luu quy mo (fund_line)."""
    global _ctx_day
    today = now_vn().date().isoformat()
    if _ctx_day != today:
        _ctx_day = today
        _ctx_cache.clear()
    if sym in _ctx_cache:
        return _ctx_cache[sym]
    try:
        rows = [f for f in flows.foreign_daily(sym, 6) if f.trading_date < today]
        out = presenters.trend_ctx_line(rows[-5:])
        row = repo.last_story(sym, today)
        if row:
            out += presenters.story_line(row)
        out += fund_ctx(sym, repo)
        _ctx_cache[sym] = out
        return out
    except Exception:
        return ""


def fund_ctx(sym, repo):
    """Dong hop luu quy mo cho 1 ma: n quy dang nam + bien dong vs thang truoc."""
    months = repo.fund_months()
    if not months:
        return ""
    n = len(repo.funds_holding(sym, months[-1]))
    prev = len(repo.funds_holding(sym, months[-2])) if len(months) > 1 else None
    return presenters.fund_line(n, None if prev is None else n - prev)


def top_movers(repo, n=3):
    """Top mua/ban rong tu snapshot moi nhat -> ([(sym, net, price, pct)] gom, [...] xa)."""
    rows = repo.top_net_full(repo.max_ts(), MOVERS_MIN_NET)
    return ([r for r in rows[:n] if r[1] > 0], [r for r in rows[::-1][:n] if r[1] < 0])


def market_snapshot(repo, flows):
    """Du lieu cho anh dashboard ngay: net hom nay (intraday tu repo), 10 phien VNDirect,
    VN-Index, top movers. -> None neu DB chua co snapshot nao."""
    ts = repo.max_ts()
    if not ts:
        return None
    day, net = ts[:10], repo.market_net(ts)
    gom, xa = top_movers(repo)
    try:
        rows = flows.foreign_daily("VNINDEX", 10)
    except Exception:
        rows = []  # bars trong — anh van ve phan con lai
    if rows and rows[-1].trading_date < day:
        rows = (rows + [DayFlow(day, net)])[-10:]  # 15:10 VNDirect chua co hom nay -> bar cuoi = intraday
    return {"date": day, "net_ty": net / 1e9,
            "index": flows.index_quote(), "rows": rows, "gom": gom, "xa": xa}


def trend_message(code, repo, flows, movers=False):
    label = "toàn HOSE" if code == "VNINDEX" else code
    closes, highs, lows = flows.ohlc(code)
    price = "\n".join(x for x in (presenters.price_line(code, closes[-10:]),
                                  presenters.range_line(code, closes, highs, lows)) if x)
    text = presenters.format_trend(label, flows.foreign_daily(code), price)
    if movers:
        ts = repo.max_ts()
        if ts:
            text += presenters.top_movers_text(repo.top_net_full(ts, MOVERS_MIN_NET))
    if code != "VNINDEX":
        text += fund_ctx(code, repo)
    return text
