"""Sau khi phien dong (15:10+), gui tong ket xu huong + anh dashboard + script TikTok 1 lan/ngay."""
from src.adapters import chart, presenters
from src.config import LATE_SESSION_START, now_vn
from src.usecases.build_trend import market_snapshot, trend_message
from src.usecases.make_script import make_script


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
        tg.broadcast(text)
        repo.set_meta("summary_day", today)
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] summary failed: {e}")
        return
    try:  # anh dashboard — loi (vd thieu Pillow) khong chan summary/script
        ctx = market_snapshot(repo, flows)
        if ctx:
            tg.broadcast_photo(chart.daily_png(ctx), f"📊 Khối ngoại {today}")
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] chart failed: {e}")
    try:
        tg.broadcast(presenters.script_msg(make_script(repo, flows, llm)))
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] script failed: {e}")  # script loi khong chan summary
