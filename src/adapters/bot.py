"""Bot controller: route Telegram commands sang usecases."""
import time

from src.adapters import chart, presenters
from src.config import now_vn
from src.dashboard import build_html
from src.usecases.build_brief import build_brief
from src.usecases.build_trend import market_snapshot, trend_message
from src.usecases.funds import fund_data, fund_stock_message
from src.usecases.make_script import make_script


def handle_updates(repo, tg, flows, llm, wait=25):
    """Handle commands via long-polling (near-instant replies).
    /id works from any chat; the rest need an authorized chat."""
    cfg = tg.cfg  # 1 nguon config duy nhat — main reload TelegramBot moi vong lap
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
                    msg = trend_message(arg, repo, flows)
                else:
                    msg = trend_message("VNINDEX", repo, flows, movers=True)
            except Exception as e:
                msg = f"Không lấy được dữ liệu xu hướng ({e})"
            tg.send_to(chat_id, msg)
        elif cmd == "/SCRIPT":
            try:
                msg = presenters.script_msg(make_script(repo, flows, llm))
            except Exception as e:
                msg = f"Không tạo được script ({e})"
            tg.send_to(chat_id, msg)
        elif cmd == "/FUND":
            try:
                if arg:
                    tg.send_to(chat_id, fund_stock_message(arg, repo))
                else:
                    data = fund_data(repo)
                    if data:
                        tg.send_photo(chat_id, chart.fund_png(data),
                                      f"🏦 Quỹ mở đồng thuận tháng {data['month'][5:]}/{data['month'][:4]}")
                    else:
                        tg.send_to(chat_id, "Chưa có dữ liệu quỹ (bot chụp danh mục Fmarket từ ngày 15 hàng tháng).")
            except Exception as e:
                tg.send_to(chat_id, f"Không lấy được dữ liệu quỹ ({e})")
        elif cmd == "/DASHBOARD":
            try:
                if repo.fund_months():
                    tg.send_document(chat_id, build_html().encode(),
                                     f"dashboard-{now_vn().date().isoformat()}.html",
                                     "📊 Dashboard quỹ đầy đủ — tải về rồi mở bằng trình duyệt")
                else:
                    tg.send_to(chat_id, "Chưa có dữ liệu quỹ (bot chụp danh mục Fmarket từ ngày 15 hàng tháng).")
            except Exception as e:
                tg.send_to(chat_id, f"Không tạo được dashboard ({e})")
        elif cmd == "/CHART":
            try:
                ctx = market_snapshot(repo, flows)
                if ctx:
                    tg.send_photo(chat_id, chart.daily_png(ctx), f"📊 Khối ngoại {ctx['date']}")
                else:
                    tg.send_to(chat_id, "Chưa có dữ liệu phiên nào trong DB.")
            except Exception as e:
                tg.send_to(chat_id, f"Không vẽ được chart ({e})")
        elif cmd == "/BRIEF" and arg:
            tg.send_to(chat_id, f"⏳ Đang tổng hợp brief {arg}, chờ ~30 giây...")
            try:
                msg = build_brief(arg, flows, llm)
            except Exception as e:
                msg = f"Không tạo được brief cho {arg} ({e})"
            tg.send_to(chat_id, msg)
        elif cmd in ("/HELP", "/START"):
            tg.send_to(chat_id, presenters.HELP_TEXT)
    if updates:  # khong co update -> offset khong doi, khoi commit sqlite moi 25s
        repo.set_meta("tg_offset", str(offset))
