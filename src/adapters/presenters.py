"""Toan bo text Telegram. Nhan entity/so lieu thuan tu usecase — khong IO, khong DB,
khong network. Duy nhat doc hang so hien thi tu src.config."""
from src.config import STORY_LATE_SHARE, STORY_MIN_NET, STORY_ROOM_MIN, WINDOW_MINUTES
from src.domain import signals

HELP_TEXT = """📖 Lệnh của bot:
/trend — xu hướng khối ngoại toàn HOSE 10 phiên gần nhất
/trend MÃ — xu hướng khối ngoại của 1 mã (vd: /trend HPG)
/chart — ảnh dashboard khối ngoại phiên gần nhất
/fund — mã nào đang được nhiều quỹ mở nắm nhất (Fmarket, cập nhật hàng tháng)
/fund MÃ — quỹ mở nào đang có mã này trong top 10 danh mục
/dashboard — file dashboard đầy đủ metric quỹ (coverage, phân bổ, NAV) — mở bằng trình duyệt
/margin — dư nợ margin các công ty chứng khoán (theo quý, từ BCTC)
/brief MÃ — bản tin AI tổng hợp: dòng tiền + định giá + tin tức (~30 giây)
/script — kịch bản video TikTok từ diễn biến khối ngoại hôm nay
/watch MÃ — theo dõi mã: ngưỡng alert giảm một nửa, báo riêng chat này
/unwatch MÃ — bỏ theo dõi
/list — xem watchlist của chat này (mỗi chat một danh sách riêng)
/notes — xem các mã đã ghi chú + % giá từ lúc note (bấm nút 📌 dưới mỗi cảnh báo để lưu)
/unnote MÃ — bỏ ghi chú một mã
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

Mã trong watchlist của chat: mọi ngưỡng trên giảm một nửa, và alert ngưỡng-thấp đó chỉ gửi riêng chat này.

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
    """(day, net, late_net, room_delta) cua phien gan nhat da chot -> ghi chu neu dang noi.
    Nhan kem ngay — "hom qua" se sai vao thu 2/sau le."""
    day, net, late, room_d = row
    bits = []
    if abs(net) >= STORY_MIN_NET and late * net > 0 and abs(late) >= STORY_LATE_SHARE * abs(net):
        bits.append(f"{'gom' if net > 0 else 'xả'} dồn 30' cuối ({late/1e9:+,.0f}/{net/1e9:+,.0f} tỷ)")
    if abs(room_d) >= STORY_ROOM_MIN:
        bits.append(f"room ngoại {'giảm' if room_d < 0 else 'tăng'} {abs(room_d)/1e6:.1f}tr cp "
                    f"({'gom thêm' if room_d < 0 else 'nhả bớt'} về khối lượng)")
    return f"\nPhiên trước ({day[8:]}/{day[5:7]}): " + " · ".join(bits) if bits else ""


def trend_ctx_line(flows):
    """1 dong noi alert intraday voi cac phien da chot: o mau + luy ke + streak."""
    if not flows:
        return ""
    vals = [f.net_val for f in flows]
    squares = "".join("🟩" if v >= 0 else "🟥" for v in vals)
    t = signals.trend_stats(vals)
    tail = f" — {t.streak} phiên {t.streak_side} ròng liên tiếp" if t.streak >= 3 else ""
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
    gia = f"{closes[-1]:,.1f} điểm" if code == "VNINDEX" else f"{closes[-1]:,.0f}đ"
    return f"Giá: {gia} | phiên nay {d1:+.1f}% | {len(closes)} phiên {dn:+.1f}%"


def range_line(code, closes, highs, lows):
    """Dinh/day 4 tuan + vi tri gia hien tai — fact thuan, khong goi la ho tro/khang cu.
    Du lieu < 15 phien -> "" (khong ve hop lech tu mau thieu)."""
    if len(closes) < 15:
        return ""
    top, bot, last = max(highs), min(lows), closes[-1]
    d_bot = (last / bot - 1) * 100
    d_top = (last / top - 1) * 100
    if code == "VNINDEX":
        rng = f"{bot:,.1f} – {top:,.1f} điểm"
    else:
        rng = f"{bot:,.0f} – {top:,.0f}"
    return f"Biên 4 tuần: {rng} | cách đáy {d_bot:+.1f}%, cách đỉnh {d_top:+.1f}%"


def top_movers_text(rows):
    if not rows:
        return ""
    top = ", ".join(f"{s} {v/1e9:+.0f} tỷ" for s, v, *_ in rows[:3] if v > 0)
    bot = ", ".join(f"{s} {v/1e9:+.0f} tỷ" for s, v, *_ in rows[::-1][:3] if v < 0)
    out = ""
    if top:
        out += f"\nTop gom hôm nay: {top}"
    if bot:
        out += f"\nTop xả hôm nay: {bot}"
    return out


def fund_line(n, delta, avg=None, sym=None, total=None):
    """1 dong hop luu cho alert//trend: so quy (do rong) + tong tien (VND) + TB %NAV (do tin)."""
    if not n:
        return ""
    d = ""
    if delta:
        d = f" (▲{delta} tháng này)" if delta > 0 else f" (▼{-delta} tháng này)"
    t = f" · tổng {total / 1e9:,.0f} tỷ" if total else ""
    a = f" · TB {avg:.1f}% NAV" if avg else ""
    hint = f" — /fund {sym} để soi" if sym else ""
    return f"\n🏦 {n} quỹ mở đang nắm trong top 10 danh mục{d}{t}{a}{hint}"


def fund_stock_text(sym, month, rows, prev_n=None, report_month=None):
    """rows: [(fund, pct, value)] cac quy dang co sym trong top 10 danh muc.
    prev_n: so quy thang truoc (None = chua co); report_month: (min, max) ky bao cao."""
    if not rows:
        return (f"Không quỹ mở nào (trên Fmarket) có {sym} trong top 10 danh mục tháng {month}.\n"
                "Lưu ý: quỹ chỉ công bố 10 khoản lớn nhất — không thấy ≠ không nắm.")
    head = f"🏦 {sym} — trong top 10 danh mục của {len(rows)} quỹ mở"
    if prev_n is not None and len(rows) != prev_n:
        d = len(rows) - prev_n
        head += f" ({'▲' if d > 0 else '▼'}{abs(d)} so với tháng trước)"
    total = sum(v or 0 for _, _, v in rows)
    if total:
        head += f"\nTổng tiền các quỹ đang đặt: {total / 1e9:,.0f} tỷ"
    avg = sum(p for _, p, _ in rows) / len(rows)
    lines = "\n".join(f"• {f}: {p:.1f}% NAV" + (f" · {v / 1e9:,.0f} tỷ" if v else "")
                      for f, p, v in rows)
    src = "(Nguồn: Fmarket, mỗi quỹ chỉ công bố top 10 khoản"
    if report_month:
        lo, hi = report_month
        src += f", kỳ báo cáo {lo}" + (f"–{hi}" if hi != lo else "")
    return f"{head}\nTỷ trọng trung bình: {avg:.1f}% NAV mỗi quỹ\n{lines}\n{src})"


DIRECTION_LABEL = {"BUY": "Đột biến MUA", "SELL": "Đột biến BÁN",
                   "ABUY": "Tăng tốc GOM", "ASELL": "Tăng tốc XẢ"}


def scorecard_text(stats, days):
    """stats tu scorecard.score -> bao cao chat luong tin hieu (kenh duyet)."""
    if not stats:
        return f"📈 Scorecard {days} ngày: chưa có tín hiệu nào đủ tuổi để chấm."
    lines = [f"📈 Scorecard tín hiệu {days} ngày qua — giá sau N phiên, win = đi thuận chiều:"]
    for d in sorted(stats):
        for h in sorted(stats[d]):
            avg, wr, n = stats[d][h]
            lines.append(f"• {DIRECTION_LABEL.get(d, d)} — sau {h} phiên: TB {avg:+.1f}%, win {wr:.0%} ({n} tín hiệu)")
    lines.append("Thông tin tham khảo — không phải khuyến nghị đầu tư.")
    return "\n".join(lines)


def note_buttons(syms):
    """Nut inline '📌 MA' cho tung ma trong alert -> bam 1 cham de note. None neu rong."""
    seen = list(dict.fromkeys(syms))[:6]  # dedup giu thu tu, cap 6 nut
    if not seen:
        return None
    btns = [{"text": f"📌 {s}", "callback_data": f"n:{s}"} for s in seen]
    return {"inline_keyboard": [btns[i:i + 3] for i in range(0, len(btns), 3)]}


def note_added_msg(sym, price, days):
    p = f" (giá {price:,.0f})" if price else ""
    return (f"📌 Đã ghi chú {sym}{p}. Xem lại bất cứ lúc nào: /notes\n"
            f"Bot sẽ tự báo kết quả sau ~{days} phiên. Thông tin tham khảo, không phải khuyến nghị.")


def notes_list_text(rows):
    """rows: [(sym, ts, price_luc_note, gia_hien_tai)]."""
    if not rows:
        return "Bạn chưa ghi chú mã nào. Thấy tín hiệu muốn theo dõi thì gõ /note MÃ."
    lines = []
    for sym, ts, p0, cur in rows:
        chg = f"{(cur / p0 - 1) * 100:+.1f}%" if p0 and cur else "—"
        lines.append(f"• {sym} (từ {ts[8:10]}/{ts[5:7]}): {chg}")
    return ("📌 Ghi chú của bạn — % giá từ lúc note đến hiện tại:\n" + "\n".join(lines)
            + "\n(/unnote MÃ để xóa · thông tin tham khảo)")


def note_report_text(items):
    """items: [(sym, ts, pct|None)] — bot tu bao sau vai phien."""
    lines = []
    for sym, ts, pct in items:
        chg = f"{pct:+.1f}%" if pct is not None else "(không có giá)"
        lines.append(f"• {sym} (ghi chú {ts[8:10]}/{ts[5:7]}): {chg}")
    return ("🔔 Cập nhật mã bạn đã ghi chú:\n" + "\n".join(lines)
            + "\nThông tin tham khảo, không phải khuyến nghị đầu tư.")


def script_msg(text):
    return f"🎬 Script TikTok hôm nay:\n\n{text}"


def open_msg(ts, net, ups, top_n, n_syms):
    """Nhip tim dau phien: xac nhan bot dang quet + khong khi som — khong phai tin hieu."""
    side = "mua" if net >= 0 else "bán"
    return (f"🔔 Mở phiên {ts[8:10]}/{ts[5:7]} — lúc {ts[11:16]}: khối ngoại {side} ròng "
            f"{abs(net) / 1e9:,.0f} tỷ · nhóm GTGD lớn {ups}/{top_n} mã xanh · đang quét {n_syms} mã HOSE")


def forcesell_msg(ts, floors):
    """floors: [(sym, pct)] cac ma (gan) san, DESC theo GTGD."""
    ex = ", ".join(f"{s} {p:.1f}%" for s, p in floors[:6])
    return (f"🚨 {ts[11:16]} — {len(floors)} mã thanh khoản lớn đang giảm sàn/gần sàn\n"
            f"{ex}{'...' if len(floors) > 6 else ''}\n"
            "Dấu hiệu bán tháo / giải chấp diện rộng — thường rơi vào khung 10-11h và 14h.\n"
            "Thông tin tham khảo, không phải khuyến nghị đầu tư.")


def margin_text(d):
    """d: dict tu margin.json — dư nợ margin CTCK theo quy (nhap tay tu BCTC)."""
    lines = []
    for i, b in enumerate(d["brokers"][:12], 1):
        ratio = f" · {b['debt'] / b['equity'] * 100:.0f}% VCSH" if b.get("equity") else ""
        lines.append(f"{i}. {b['n']}: {b['debt']:,.0f} tỷ{ratio}")
    return (f"📊 Dư nợ margin CTCK — {d['quarter']} (nguồn: BCTC quý, cập nhật chậm)\n"
            f"Toàn thị trường: ~{d['market_total_ty']:,.0f} tỷ\n" + "\n".join(lines)
            + "\n(Trần quy định: dư nợ ≤ 200% VCSH. Thông tin tham khảo.)")


def alert_digest(ts, msgs):
    return f"📊 Khối ngoại — {ts[11:16]}\n\n" + "\n\n".join(msgs)
