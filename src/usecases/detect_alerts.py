"""Spike / accel / state detectors + run_once.
Diem noi config<->domain duy nhat: f = WL_FACTOR neu sym in watchlist."""
from datetime import datetime

from src.adapters import presenters
from src.config import (ACCEL_MIN_LAST, ACCEL_MIN_SHARE, ALERT_MIN_NET, ALERT_MIN_SHARE,
                        COOLDOWN_MINUTES, DAY_NET_TH, FLOOR_LOCK_SHARE, FLOOR_PCT,
                        FORCESELL_MIN_GTGD, FORCESELL_MIN_STOCKS, FUND_CONFLUENCE_MIN,
                        MIN_DAY_VALUE, RATE_TH, STALL_MINUTES, WINDOW_MINUTES, WL_FACTOR)
from src.domain import signals
from src.domain.entities import Accel, RegimeChange, Spike
from src.usecases import margin
from src.usecases.build_trend import trend_ctx
from src.usecases.feed_health import feed_ok
from src.usecases.funds import holders_of
from src.usecases.poll_market import poll

# "loud" = tin hieu dang keo chuong (lam phien user); con lai gui im lang.
SPIKE_LOUD_SHARE = 0.8   # spike chiem > 80% GTGD nhip -> nghi thoa thuan, dang chu y


def _confluence(sym, buy_side, repo):
    """Hop luu: chieu MUA/GOM + >= FUND_CONFLUENCE_MIN quy mo dang nam -> tin hieu manh."""
    return buy_side and holders_of(repo, sym) >= FUND_CONFLUENCE_MIN


def detect_spikes(repo, flows, ts, wl):
    """-> [(sym, msg, wl_only, loud)] — wl_only: chi qua nguong nho watchlist, giao rieng chat watch;
    loud: dang keu chuong (thoa thuan share>80% hoac hop luu gom+quy)."""
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
        loud = share > SPIKE_LOUD_SHARE or _confluence(sym, net > 0, repo)
        alerts.append((ts, sym, direction, net, share, price))
        msgs.append((sym, presenters.spike_msg(Spike(sym, net, share, price, pct or 0, day_net))
                     + trend_ctx(sym, repo, flows), wl_only, loud))
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
            loud = _confluence(sym, regime.startswith("GOM"), repo)  # gom + nhieu quy -> keu; xa thuong -> im
            msgs.append((sym, presenters.state_msg(RegimeChange(sym, regime, recent, day_net, price or 0, pct or 0))
                         + trend_ctx(sym, repo, flows), wl_only, loud))
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
                     + trend_ctx(sym, repo, flows), wl_only, True))  # tang toc: luon keu
    repo.add_alerts(alerts)
    return msgs


def maybe_forcesell(repo, tg, ts):
    """Nhieu ma GTGD lon (gan) san + tong GTGD san lon -> canh bao ban thao/giai chap dien rong.
    Do bang TONG GTGD (tien bi dap san), khong dem dau ma: 5 tru nghin ty > 15 ma nho.
    1 lan/ngay khi lan dau vuot nguong. Market-wide -> broadcast, keu chuong."""
    day = ts[:10]
    if repo.get_meta("forcesell_day") == day:
        return
    floors = repo.floor_stocks(ts, FLOOR_PCT, MIN_DAY_VALUE)
    gtgd = sum(dv for _, _, dv, _ in floors)
    if len(floors) < FORCESELL_MIN_STOCKS or gtgd < FORCESELL_MIN_GTGD:
        return
    repo.set_meta("forcesell_day", day)
    # gan co san-cung (GTGD tac = du ban khong khop = mat thanh khoan, ngoi no giai chap cheo)
    marked = [(s, p, dv, signals.is_locked(dv, pdv, FLOOR_LOCK_SHARE)) for s, p, dv, pdv in floors]
    text = presenters.forcesell_msg(ts, marked, gtgd, margin.market_tension())  # ghep boi canh margin quy
    for cid in tg.cfg.get("chat_ids", []):
        try:
            tg.send_to(cid, text)  # keu — tin hieu rui ro dien rong dang chu y
        except Exception as e:
            print(f"forcesell send failed ({cid}): {e}")


def run_once(repo, feed, flows, tg):
    ts, n = poll(repo, feed)  # raise neu feed timeout -> main bat -> feed_fail
    feed_ok(repo, tg)         # poll OK -> bao phuc hoi neu truoc do mat feed
    wl = repo.watch_union()
    alerts = detect_spikes(repo, flows, ts, wl) + detect_accel(repo, flows, ts, wl) + detect_states(repo, flows, ts, wl)
    print(f"[{ts}] snapshot {n} symbols, {len(alerts)} alerts")
    if alerts:
        print(presenters.alert_digest(ts, [m for _, m, _, _ in alerts]))
        for cid in tg.cfg.get("chat_ids", []):
            watch = repo.watchlist(cid)
            # wl_only: chi den chat dang watch ma do. loud/watch -> keu chuong; con lai gui im lang
            mine = [(s, m, loud) for s, m, wl_only, loud in alerts if not wl_only or s in watch]
            if not mine:
                continue
            keu = any(loud or s in watch for s, _, loud in mine)
            # nut 📌 cho MOI ma trong alert (deu la tin hieu that, deu dang note); cap 6 lo ca cao diem
            buttons = presenters.note_buttons([s for s, _, _ in mine])
            try:
                tg.send_to(cid, presenters.alert_digest(ts, [m for _, m, _ in mine]),
                           silent=not keu, reply_markup=buttons)
            except Exception as e:
                print(f"telegram send failed ({cid}): {e}")
    maybe_forcesell(repo, tg, ts)
    return alerts
