"""Spike / accel / state detectors + run_once.
Diem noi config<->domain duy nhat: f = WL_FACTOR neu sym in watchlist."""
from datetime import datetime

from src.adapters import presenters
from src.config import (ACCEL_MIN_LAST, ACCEL_MIN_SHARE, ALERT_MIN_NET, ALERT_MIN_SHARE,
                        COOLDOWN_MINUTES, DAY_NET_TH, MIN_DAY_VALUE, RATE_TH, STALL_MINUTES,
                        WINDOW_MINUTES, WL_FACTOR)
from src.domain import signals
from src.domain.entities import Accel, RegimeChange, Spike
from src.usecases.build_trend import trend_ctx
from src.usecases.poll_market import poll


def detect_spikes(repo, flows, ts, wl):
    """-> [(sym, msg, wl_only)] — wl_only: chi qua nguong nho watchlist, giao rieng chat dang watch."""
    prev_ts = repo.prev_snapshot_ts(ts, WINDOW_MINUTES)
    if not prev_ts:
        return []
    alerts, msgs = [], []
    for sym, net, win_value, day_value, price, pct, day_net in repo.spike_rows(ts, prev_ts):
        f = WL_FACTOR if sym in wl else 1.0
        share = signals.spike_share(net, win_value, day_value, f, MIN_DAY_VALUE, ALERT_MIN_NET, ALERT_MIN_SHARE)
        if share is None:
            continue
        direction = "BUY" if net > 0 else "SELL"
        if repo.recent_alert(sym, direction, ts, COOLDOWN_MINUTES):
            continue
        wl_only = f != 1.0 and signals.spike_share(
            net, win_value, day_value, 1.0, MIN_DAY_VALUE, ALERT_MIN_NET, ALERT_MIN_SHARE) is None
        alerts.append((ts, sym, direction, net, share, price))
        msgs.append((sym, presenters.spike_msg(Spike(sym, net, share, price, pct or 0, day_net))
                     + trend_ctx(sym, repo, flows), wl_only))
    repo.add_alerts(alerts)
    return msgs


def detect_states(repo, flows, ts, wl):
    """Stateful layer: report only regime TRANSITIONS (gom/xa bat dau hoac chung lai)."""
    prev_ts = repo.prev_snapshot_ts(ts, STALL_MINUTES)
    if not prev_ts:
        return []
    gap = (datetime.fromisoformat(ts) - datetime.fromisoformat(prev_ts)).total_seconds() / 60
    if gap > STALL_MINUTES * 2:
        return []  # cua so dinh khoang trong du lieu (nghi trua/outage) -> 'chung lai' se la gia
    day = ts[:10]
    msgs = []
    for sym, day_net, recent, day_value, price, pct in repo.state_rows(ts, prev_ts):
        in_wl = sym in wl
        f = WL_FACTOR if in_wl else 1.0
        if not in_wl and day_value < MIN_DAY_VALUE:
            continue
        regime = signals.classify_regime(day_net, recent, f, DAY_NET_TH, RATE_TH)
        old = repo.get_regime(sym, day)
        if regime == old:
            continue
        repo.set_regime(sym, regime, day)  # state luu chung theo nguong wl — chat khong watch co the
        if regime != "NEUTRAL":            # bo lo 1 transition nguong-thap (chap nhan, hiem)
            wl_only = f != 1.0 and signals.classify_regime(day_net, recent, 1.0, DAY_NET_TH, RATE_TH) != regime
            msgs.append((sym, presenters.state_msg(RegimeChange(sym, regime, recent, day_net, price or 0, pct or 0))
                         + trend_ctx(sym, repo, flows), wl_only))
    return msgs


def detect_accel(repo, flows, ts, wl):
    """3 nhip poll lien tiep cung chieu, do lon tang dan => dong tien dang tang toc."""
    day = ts[:10]
    tss = repo.snapshot_times(day, ts, 4)  # da tang dan san
    if len(tss) < 4:
        return []
    alerts, msgs = [], []
    for sym, day_value, win3, d1, d2, d3, day_net, price, pct in repo.accel_rows(tss[0], tss[1], tss[2], tss[3]):
        f = WL_FACTOR if sym in wl else 1.0
        if not signals.is_accel(d1, d2, d3, win3, day_value, f, MIN_DAY_VALUE, ACCEL_MIN_LAST, ACCEL_MIN_SHARE):
            continue
        direction = "ABUY" if d3 > 0 else "ASELL"
        if repo.recent_alert(sym, direction, ts, COOLDOWN_MINUTES):
            continue
        wl_only = f != 1.0 and not signals.is_accel(
            d1, d2, d3, win3, day_value, 1.0, MIN_DAY_VALUE, ACCEL_MIN_LAST, ACCEL_MIN_SHARE)
        alerts.append((ts, sym, direction, d3, 0, 0))
        msgs.append((sym, presenters.accel_msg(Accel(sym, (d1, d2, d3), day_net, price or 0, pct or 0))
                     + trend_ctx(sym, repo, flows), wl_only))
    repo.add_alerts(alerts)
    return msgs


def run_once(repo, feed, flows, tg):
    ts, n = poll(repo, feed)
    wl = repo.watch_union()
    alerts = detect_spikes(repo, flows, ts, wl) + detect_accel(repo, flows, ts, wl) + detect_states(repo, flows, ts, wl)
    print(f"[{ts}] snapshot {n} symbols, {len(alerts)} alerts")
    if alerts:
        print(presenters.alert_digest(ts, [m for _, m, _ in alerts]))
        for cid in tg.cfg.get("chat_ids", []):
            # alert nguong-thap (wl_only) chi den chat dang watch ma do; alert nguong day den moi chat
            mine = [m for s, m, wl_only in alerts if not wl_only or s in repo.watchlist(cid)]
            if mine:
                try:
                    tg.send_to(cid, presenters.alert_digest(ts, mine))
                except Exception as e:
                    print(f"telegram send failed ({cid}): {e}")
    return alerts
