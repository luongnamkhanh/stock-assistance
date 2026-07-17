"""Boi canh xu huong: noi alert intraday voi cac phien da chot (collector.py:285-302)
+ thong bao xu huong toan cuc/1 ma cho /trend, script, summary (collector.py:624-625,652-653)."""
from src.adapters import presenters
from src.config import now_vn


def trend_ctx(sym, repo, flows):
    """Loi mang/API -> chuoi rong, alert van gui binh thuong. Chi giu phien DA CHOT
    (hom nay da co dong 'Ca phien' trong alert roi). Kem dac tinh phien gan nhat tu day_story."""
    try:
        today = now_vn().date().isoformat()
        rows = [f for f in flows.foreign_daily(sym, 6) if f.trading_date < today]
        out = presenters.trend_ctx_line(rows[-5:])
        row = repo.last_story(sym, today)
        if row:
            out += presenters.story_line(row)
        return out
    except Exception:
        return ""


def trend_message(code, label, repo, flows, movers=False):
    text = presenters.format_trend(label, flows.foreign_daily(code), presenters.price_line(code, flows.closes(code)))
    if movers:
        ts = repo.max_ts()
        if ts:
            text += presenters.top_movers_text(repo.top_net(ts))
    return text
