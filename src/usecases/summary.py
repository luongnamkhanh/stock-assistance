"""Sau khi phien dong (15:10+), gui tong ket xu huong + script TikTok 1 lan/ngay
(collector.py:639-663)."""
from src.config import now_vn
from src.usecases.build_trend import trend_message
from src.usecases.day_story import build_day_story
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
        build_day_story(repo, today)  # chot dac tinh phien de lam giau alert cac ngay sau
        text = "🔔 Tổng kết phiên\n\n" + trend_message("VNINDEX", "toàn HOSE", repo, flows, movers=True)
        tg.broadcast(text)
        repo.set_meta("summary_day", today)
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] summary failed: {e}")
        return
    try:
        tg.broadcast(make_script(repo, flows, llm))
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] script failed: {e}")  # script loi khong chan summary
