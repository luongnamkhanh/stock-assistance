"""Toan bo text Telegram. Nhan entity/so lieu thuan tu usecase — khong IO, khong DB,
khong network. Duy nhat doc hang so hien thi tu src.config."""
from src.config import WINDOW_MINUTES
from src.domain import signals

HELP_TEXT = """📖 Lệnh của bot:
/trend — xu hướng khối ngoại toàn HOSE 10 phiên gần nhất
/trend MÃ — xu hướng khối ngoại của 1 mã (vd: /trend HPG)
/brief MÃ — bản tin AI tổng hợp: dòng tiền + định giá + tin tức (~30 giây)
/script — kịch bản video TikTok từ diễn biến khối ngoại hôm nay
/watch MÃ — theo dõi mã (ngưỡng alert giảm một nửa)
/unwatch MÃ — bỏ theo dõi
/list — xem watchlist (list chung, ai trong group cũng sửa được)
/id — xem chat id (để cấp quyền cho group mới)
/help — bảng này

Cuối mỗi phiên bot tự gửi tổng kết xu hướng khối ngoại toàn thị trường.

🤖 Bot quét toàn bộ mã HOSE mỗi 5 phút trong giờ giao dịch, báo 2 loại tín hiệu:

1️⃣ Đột biến 10 phút — khối ngoại mua/bán ròng ≥ 3 tỷ trong 10 phút và chiếm ≥ 15% giao dịch của mã trong nhịp đó. Nếu chiếm > 80% thì kèm cảnh báo nghi lệnh thỏa thuận.

2️⃣ Chuyển trạng thái — tính trên mua/bán ròng LŨY KẾ từ đầu phiên, chỉ báo đúng lúc mã ĐỔI trạng thái:
🟢 GOM — mua ròng ≥ 15 tỷ, 30 phút gần nhất vẫn đang mua thêm
🟡 GOM CHỮNG LẠI — vẫn mua ròng ≥ 15 tỷ nhưng 30 phút gần nhất gần như ngừng mua (lực gom cạn dần)
🔴 XẢ — bán ròng ≥ 15 tỷ, 30 phút gần nhất vẫn đang bán thêm
🟠 XẢ CHỮNG LẠI — vẫn bán ròng ≥ 15 tỷ nhưng 30 phút gần nhất gần như ngừng bán (lực xả cạn dần)

Mã trong watchlist: mọi ngưỡng trên giảm một nửa.

⚠️ Thông tin tham khảo, không phải khuyến nghị đầu tư — quyết định là của bạn."""

STATE_MSG = {  # dong 1 cua khung 3 tang — boi canh phien nam o ctx_line dung chung
    "GOM":       "🟢 {s} — vào trạng thái GOM: 30' qua {r:+.1f} tỷ",
    "GOM_CHUNG": "🟡 {s} — lực gom CHỮNG LẠI: 30' qua chỉ {r:+.1f} tỷ",
    "XA":        "🔴 {s} — vào trạng thái XẢ: 30' qua {r:+.1f} tỷ",
    "XA_CHUNG":  "🟠 {s} — lực xả CHỮNG LẠI: 30' qua chỉ {r:+.1f} tỷ",
}

MOMO_TEXT = {
    "DAO_CHIEU": "3 phiên gần nhất ĐẢO CHIỀU so với xu hướng",
    "MANH": "đà đang MẠNH dần",
    "YEU": "đà đang YẾU dần",
    "ON_DINH": "đà ổn định",
}


def ctx_line(day_net, price, pct):
    """Dong 2 cua khung 3 tang — boi canh phien, DUNG CHUNG cho moi loai alert."""
    return (f"Cả phiên: {'mua' if day_net >= 0 else 'bán'} ròng {abs(day_net)/1e9:.1f} tỷ "
            f"| Giá {price:,.0f} ({pct:+.1f}% hôm nay)")


def spike_msg(s):
    icon, side = ("🟢", "mua ròng") if s.net > 0 else ("🔴", "bán ròng")
    note = "\n⚠️ KN chiếm gần trọn giao dịch nhịp này — khả năng lệnh thỏa thuận" if s.share > 0.8 else ""
    return (f"{icon} {s.symbol} — Khối ngoại {side} {abs(s.net)/1e9:.1f} tỷ trong {WINDOW_MINUTES} phút qua "
            f"(chiếm {s.share:.0%} giao dịch của mã){note}\n" + ctx_line(s.day_net, s.price, s.pct))


def accel_msg(a):
    icon, side = ("🟢⚡", "GOM") if a.deltas[-1] > 0 else ("🔴⚡", "XẢ")
    chain = " → ".join(f"{abs(d)/1e9:.1f}" for d in a.deltas)
    return (f"{icon} {a.symbol} — {side} TĂNG TỐC: 3 nhịp liên tiếp {chain} tỷ\n"
            + ctx_line(a.day_net, a.price, a.pct))


def state_msg(rc):
    return (STATE_MSG[rc.regime].format(s=rc.symbol, r=rc.recent / 1e9) + "\n"
            + ctx_line(rc.day_net, rc.price, rc.pct))


def story_line(row):
    """(net, late_net, room_delta) cua phien gan nhat -> ghi chu neu dang noi."""
    net, late, room_d = row
    bits = []
    if abs(net) >= 10e9 and late * net > 0 and abs(late) >= 0.4 * abs(net):
        bits.append(f"{'gom' if net > 0 else 'xả'} dồn 30' cuối ({late/1e9:+,.0f}/{net/1e9:+,.0f} tỷ)")
    if abs(room_d) >= 500_000:  # ponytail: nguong tho, chinh khi thay keu nhieu/it qua
        bits.append(f"room {'+' if room_d > 0 else '-'}{abs(room_d)/1e6:.1f}tr cp")
    return "\nHôm qua: " + " · ".join(bits) if bits else ""


def trend_ctx_line(flows):
    """1 dong noi alert intraday voi cac phien da chot: o mau + luy ke + streak."""
    if not flows:
        return ""
    vals = [f.net_val for f in flows]
    squares = "".join("🟩" if v >= 0 else "🟥" for v in vals)
    last = vals[-1] >= 0
    streak = 0
    for v in reversed(vals):
        if (v >= 0) != last:
            break
        streak += 1
    side = "mua" if last else "bán"
    tail = f" — {streak} phiên {side} ròng liên tiếp" if streak >= 3 else ""
    return f"\n{len(vals)} phiên trước: {squares} lũy kế {sum(vals)/1e9:+,.0f} tỷ{tail}"


def format_trend(label, flows, price=""):
    if not flows:
        return f"Không có dữ liệu khối ngoại cho {label}."
    nets = [f.net_val for f in flows]
    t = signals.trend_stats(nets)
    bars = "".join("🟩" if v > 0 else "🟥" if v < 0 else "⬜" for v in nets)
    momo = MOMO_TEXT[t.momo]
    side = "MUA ròng" if t.cum > 0 else "BÁN ròng"
    flip = "\n🔄 VỪA ĐẢO CHIỀU phiên nay!" if t.flipped else ""
    verb = "gom hàng" if nets[-1] > 0 else "rút vốn"
    if t.flipped:
        read = (f"khối ngoại vừa quay sang {t.streak_side} ròng sau chuỗi "
                f"{'bán' if nets[-2] < 0 else 'mua'} — cần 1-2 phiên nữa để xác nhận đảo chiều thật")
    elif t.streak >= 5:
        read = f"khối ngoại {verb} bền bỉ — chuỗi {t.streak} phiên chưa đứt, lực chưa có dấu hiệu dừng"
    elif t.momo == "MANH":
        read = f"dòng tiền {t.streak_side} ròng đang tăng tốc"
    elif t.momo == "YEU":
        read = f"vẫn {t.streak_side} ròng nhưng lực đang hạ nhiệt"
    else:
        read = f"xu hướng {t.streak_side} ròng, cường độ bình thường"
    bd = ", ".join(f"{v/1e9:+,.0f}" for v in t.last3)  # bay outlier ngay tren mat chu
    return (f"📈 Khối ngoại {label} — {len(flows)} phiên ({flows[0].trading_date[5:]} → {flows[-1].trading_date[5:]})\n"
            f"{bars}  (cũ → mới)\n"
            f"Xu hướng: {side} lũy kế {t.cum/1e9:+,.0f} tỷ | {t.buys}/{len(flows)} phiên mua ròng\n"
            f"Chuỗi hiện tại: {t.streak} phiên {t.streak_side} ròng liên tiếp{flip}\n"
            f"3 phiên gần nhất: {sum(t.last3)/1e9:+,.0f} tỷ ({bd}) — {momo}\n"
            f"Phiên mới nhất ({flows[-1].trading_date}): {nets[-1]/1e9:+,.0f} tỷ\n"
            + (f"{price}\n" if price else "")
            + f"💡 Đọc nhanh: {read}")


def price_line(code, closes):
    if not closes:
        return ""
    d1 = (closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else 0.0
    dn = (closes[-1] / closes[0] - 1) * 100
    gia = f"{closes[-1]:,.1f} điểm" if code == "VNINDEX" else f"{closes[-1]*1000:,.0f}đ"
    return f"Giá: {gia} | phiên nay {d1:+.1f}% | {len(closes)} phiên {dn:+.1f}%"


def top_movers_text(rows):
    if not rows:
        return ""
    top = ", ".join(f"{s} {v/1e9:+.0f} tỷ" for s, v in rows[:3] if v > 0)
    bot = ", ".join(f"{s} {v/1e9:+.0f} tỷ" for s, v in rows[::-1][:3] if v < 0)
    out = ""
    if top:
        out += f"\nTop gom hôm nay: {top}"
    if bot:
        out += f"\nTop xả hôm nay: {bot}"
    return out


def alert_digest(ts, msgs):
    return f"📊 Khối ngoại — {ts[11:16]}\n\n" + "\n\n".join(msgs)
