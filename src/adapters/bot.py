"""Bot controller: route Telegram commands sang usecases (collector.py:552-614 poll_commands).
load_config duoc goi (khong import truc tiep dung) de test monkey-patch bot.load_config duoc."""
import time

from src.adapters import presenters
from src.config import load_config
from src.usecases.build_brief import build_brief
from src.usecases.build_trend import trend_message
from src.usecases.make_script import make_script


def handle_updates(repo, tg, flows, llm, wait=25):
    """Handle commands via long-polling (near-instant replies).
    /id works from any chat; the rest need an authorized chat."""
    cfg = load_config()
    if not (cfg.get("token") and cfg.get("chat_ids")):
        time.sleep(wait)
        return
    offset = int(repo.get_meta("tg_offset", "0"))
    updates = tg.get_updates(offset, wait)
    for u in updates:
        offset = u["update_id"]
        m = u.get("message", {})
        chat_id = m.get("chat", {}).get("id")
        parts = (m.get("text") or "").strip().upper().split()
        if not (chat_id and parts):
            continue
        cmd = parts[0].split("@")[0]  # in groups commands arrive as /watch@BotName
        arg = parts[1] if len(parts) > 1 else None
        if cmd == "/ID":
            tg.send_to(chat_id, f"Chat id: {chat_id}\n"
                       "Đưa id này cho admin thêm vào telegram.json để bot hoạt động ở đây.")
            continue
        if chat_id not in cfg["chat_ids"]:
            continue
        if cmd == "/WATCH" and arg:
            repo.watch(arg)
            tg.send_to(chat_id, f"✅ Đã theo dõi {arg} (ngưỡng alert giảm 1 nửa)")
        elif cmd == "/UNWATCH" and arg:
            repo.unwatch(arg)
            tg.send_to(chat_id, f"Đã bỏ theo dõi {arg}")
        elif cmd == "/LIST":
            wl = sorted(repo.watchlist())
            tg.send_to(chat_id, "Watchlist: " + (", ".join(wl) if wl else "(trống)"))
        elif cmd == "/TREND":
            try:
                if arg:
                    msg = trend_message(arg, arg, repo, flows)
                else:
                    msg = trend_message("VNINDEX", "toàn HOSE", repo, flows)
            except Exception as e:
                msg = f"Không lấy được dữ liệu xu hướng ({e})"
            tg.send_to(chat_id, msg)
        elif cmd == "/SCRIPT":
            try:
                msg = make_script(repo, flows, llm)
            except Exception as e:
                msg = f"Không tạo được script ({e})"
            tg.send_to(chat_id, msg)
        elif cmd == "/BRIEF" and arg:
            tg.send_to(chat_id, f"⏳ Đang tổng hợp brief {arg}, chờ ~30 giây...")
            try:
                msg = build_brief(arg, flows, llm)
            except Exception as e:
                msg = f"Không tạo được brief cho {arg} ({e})"
            tg.send_to(chat_id, msg)
        elif cmd in ("/HELP", "/START"):
            tg.send_to(chat_id, presenters.HELP_TEXT)
    repo.set_meta("tg_offset", str(offset))
