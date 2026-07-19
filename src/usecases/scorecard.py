"""Cham diem tin hieu: gia lam gi sau 5/10 phien ke tu alert (spike + accel;
state khong luu vao bang alerts nen khong cham duoc). Gui kenh duyet sang thu 7 hang tuan."""
from datetime import timedelta

from src.adapters import presenters
from src.config import now_vn

HORIZONS = (5, 10)
LOOKBACK_DAYS = 30


def score(alerts, closes_fn, horizons=HORIZONS):
    """alerts: [(ts, symbol, direction)]; closes_fn(sym) -> [(date, close)] cu -> moi.
    Base = gia dong cua phien alert; win = gia di thuan chieu tin hieu.
    -> {direction: {horizon: (avg_pct, win_rate, n)}}."""
    cache, out = {}, {}
    for ts, sym, direction in alerts:
        if sym not in cache:
            try:
                cache[sym] = closes_fn(sym)
            except Exception:
                cache[sym] = []
        series = cache[sym]
        day = ts[:10]
        i = max((k for k, (d, _) in enumerate(series) if d <= day), default=None)
        if i is None or not series[i][1]:
            continue
        base = series[i][1]
        sign = 1 if direction in ("BUY", "ABUY") else -1
        for h in horizons:
            if i + h >= len(series):
                continue  # chua du tuoi — tuan sau cham tiep
            pct = (series[i + h][1] / base - 1) * 100
            s, w, n = out.setdefault(direction, {}).get(h, (0.0, 0, 0))
            out[direction][h] = (s + pct, w + (1 if pct * sign > 0 else 0), n + 1)
    for hs in out.values():
        for h, (s, w, n) in hs.items():
            hs[h] = (s / n, w / n, n)
    return out


def maybe_send_scorecard(repo, flows, tg):
    """Goi moi vong lap main; chay 1 lan vao thu 7 hang tuan, gui kenh duyet chat_ids[0]."""
    now = now_vn()
    week = "{}-W{:02d}".format(*now.isocalendar()[:2])
    if now.weekday() != 5 or repo.get_meta("scorecard_week") == week:
        return
    repo.set_meta("scorecard_week", week)
    try:
        since = (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
        stats = score(repo.alerts_since(since), lambda s: flows.daily_closes(s, 60))
        text = presenters.scorecard_text(stats, LOOKBACK_DAYS)
        if tg.cfg.get("chat_ids"):
            tg.send_to(tg.cfg["chat_ids"][0], text)
        print(f"[{now.isoformat(timespec='seconds')}] scorecard {week} da gui")
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] scorecard failed: {e}")
