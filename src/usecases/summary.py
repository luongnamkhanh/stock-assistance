"""Tin nhan theo vong doi phien: nhip tim mo cua (09:15+) va tong ket dong cua (15:10+)."""
from urllib.error import HTTPError

from src.adapters import chart, presenters
from src.config import LATE_SESSION_START, now_vn
from src.usecases.build_trend import market_snapshot, trend_message
from src.usecases.make_script import make_script


def _send_daily(repo, tg, text, key, today):
    if not (tg.cfg.get("token") and tg.cfg.get("chat_ids")):
        return False
    complete = True
    for cid in tg.cfg["chat_ids"]:
        chat_key = f"{key}:{cid}"
        if repo.get_meta(chat_key) == today:
            continue
        try:
            tg.send_to(cid, text)
        except Exception as e:
            print(f"[{now_vn().isoformat(timespec='seconds')}] {key} failed ({cid}): {e}")
            if not isinstance(e, HTTPError) or e.code != 403:
                complete = False
                continue
        repo.set_meta(chat_key, today)  # 403 la tu choi: khong thu lai chat nay trong ngay
    if complete:
        repo.set_meta(key, today)
    return complete


def maybe_send_open(repo, tg, now=None):
    """Nhip tim dau phien — 1 tin/ngay trong cua so 09:15-10:00 (restart muon hon thi bo qua,
    khong gui muon). Xac nhan bot song + khong khi som; `now` inject duoc cho test."""
    now = now or now_vn()
    hm = now.hour * 60 + now.minute
    if now.weekday() >= 5 or not (9 * 60 + 15 <= hm <= 10 * 60):
        return
    today = now.date().isoformat()
    if repo.get_meta("open_day") == today:
        return
    ts = repo.max_ts()
    if not ts or ts[:10] != today:
        return  # poll dau chua chay / nghi le -> cho vong sau
    heat = repo.heat(ts, 8)
    text = presenters.open_msg(ts, repo.market_net(ts), sum(p > 0 for _, p in heat),
                               len(heat), repo.snapshot_count(ts))
    try:
        _send_daily(repo, tg, text, "open_day", today)
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] open msg failed: {e}")


def maybe_send_summary(repo, flows, llm, tg):
    now = now_vn()
    if now.weekday() >= 5 or now.hour * 60 + now.minute < 15 * 60 + 10:
        return
    today = now.date().isoformat()
    if repo.get_meta("summary_day") == today:
        return
    if not repo.has_snapshots(today):
        return  # khong co du lieu hom nay (nghi le) -> khong tong ket
    try:
        repo.save_day_story(today, LATE_SESSION_START)  # chot dac tinh phien de lam giau alert cac ngay sau
        text = "🔔 Tổng kết phiên\n\n" + trend_message("VNINDEX", repo, flows, movers=True)
        if not _send_daily(repo, tg, text, "summary_day", today):
            return
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] summary failed: {e}")
        return
    try:  # anh dashboard — loi (vd thieu Pillow) khong chan summary/script
        ctx = market_snapshot(repo, flows)
        if ctx:
            tg.broadcast_photo(chart.daily_png(ctx), f"📊 Khối ngoại {today}")
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] chart failed: {e}")
    try:  # script TikTok la do noi bo (de render video) -> chi gui kenh duyet chat_ids[0], khong broadcast
        if tg.cfg.get("chat_ids"):
            tg.send_to(tg.cfg["chat_ids"][0], presenters.script_msg(make_script(repo, flows, llm)))
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] script failed: {e}")  # script loi khong chan summary
