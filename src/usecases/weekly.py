"""Tong ket TUAN cho video cuoi tuan — 2 PHAN: p1 dang thu 7 (tong ket tuan),
p2 dang CN (smart money: hop luu khoi ngoai x quy mo). Moi phan 25-35s.
Script chot 1 lan/tuan/phan vao meta['script:week:YYYY-WXX-pN'] — worker Railway gen + gui
duyet sang thu 7, video local (video.py --weekly [--part2]) dung dung ban do."""
from datetime import timedelta

from src.config import MOVERS_MIN_NET, now_vn
from src.usecases.funds import fund_data, fund_summary_text

_RULES = """Quy tắc: giọng bản tin dữ liệu, nói chuyện tự nhiên, xưng "mình", câu ngắn dễ đọc
thành tiếng, số liệu làm tròn cho dễ nghe, luôn nói rõ "cả tuần"/"tuần này" để không lẫn với video ngày.
KHÔNG khuyến nghị mua/bán. KHÔNG bịa gì ngoài dữ liệu được đưa. TRÁNH ngôn ngữ cá cược/làm giàu
("đặt cửa", "x2 tài khoản", "ăn bằng lần", "cơ hội đổi đời", khoe lãi) — dùng từ trung tính:
"rót vào", "phân bổ", "nắm giữ"."""

WEEK_SYSTEMS = {
    1: f"""Bạn là người viết kịch bản video TikTok tổng kết TUẦN — PHẦN 1/2, đăng thứ Bảy
(25-35 giây đọc thành tiếng) về chứng khoán Việt Nam.

Cấu trúc bắt buộc (plain text):
[HOOK] 1 câu mở đầu bằng con số ấn tượng nhất của TUẦN. Không chào hỏi.
[THÂN] 3-4 câu ngắn: (1) lũy kế cả tuần và phiên nào gãy/đảo chiều, (2) VN-Index cả tuần
tăng/giảm bao nhiêu phần trăm, (3) top gom/xả cả tuần kèm số tỷ và % giá tuần — mỗi chiều tối đa 2 mã.
[KẾT] 1 câu teaser cho phần 2: mai mình nói các quỹ mở đang rót tiền vào những mã nào — mời follow.
Dòng cuối: 4-5 hashtag tiếng Việt.

{_RULES} KHÔNG nhắc đến quỹ mở trong [THÂN] — để dành cho video phần 2.""",
    2: f"""Bạn là người viết kịch bản video TikTok cuối tuần — PHẦN 2/2 "smart money", đăng Chủ nhật
(25-35 giây đọc thành tiếng) về chứng khoán Việt Nam.

Cấu trúc bắt buộc (plain text):
[HOOK] 1 câu về dòng tiền quỹ mở: mã được nhiều quỹ nắm nhất, hoặc điểm hợp lưu đáng chú ý nhất. Không chào hỏi.
[THÂN] 3-4 câu ngắn: (1) HỢP LƯU — mã khối ngoại gom mạnh tuần qua mà cũng đang nằm trong danh mục
nhiều quỹ mở (nói cả số tỷ lẫn số quỹ), (2) mã được nhiều quỹ mở nắm nhất hiện tại,
(3) nếu có mã mới vào top danh mục quỹ thì nhắc 1 câu.
[KẾT] 1 câu hẹn phiên thứ Hai + mời follow.
Dòng cuối: 4-5 hashtag tiếng Việt.

{_RULES} Nói rõ dữ liệu quỹ là danh mục công bố hàng tháng (top 10 khoản mỗi quỹ).""",
}


def week_range(now):
    """(thu_hai, thu_sau) ISO cua tuan hien tai — chay cuoi tuan van tra tuan vua xong."""
    mon = now.date() - timedelta(days=now.weekday())
    return mon.isoformat(), (mon + timedelta(days=4)).isoformat()


def week_movers(repo, flows, d1, d2, n=3):
    """Top gom/xa CA TUAN tu day_story + % gia tuan tung ma -> ([(sym, net, price, pct)], [...])."""
    rows = repo.week_net(d1, d2, MOVERS_MIN_NET)
    gom = [r for r in rows[:n] if r[1] > 0]
    xa = [r for r in rows[::-1][:n] if r[1] < 0]
    out = []
    for sym, net in gom + xa:
        price, pct = 0, 0.0
        try:
            series = flows.daily_closes(sym, 10)
            inw = [c for d, c in series if d1 <= d <= d2]
            base = [c for d, c in series if d < d1]
            if inw:
                price = inw[-1]
                if base and base[-1]:
                    pct = (inw[-1] / base[-1] - 1) * 100
        except Exception:
            pass  # thieu gia -> van co net, pct 0
        out.append((sym, net, price, pct))
    return out[:len(gom)], out[len(gom):]


def week_fusion(repo, flows, d1, d2):
    """Hop luu tuan: movers kem SO QUY MO dang nam -> ([(sym, net, n_quy, pct_tuan)] gom, [...] xa)."""
    months = repo.fund_months()
    m = months[-1] if months else None
    gom, xa = week_movers(repo, flows, d1, d2)
    enrich = lambda rows: [(s, v, len(repo.funds_holding(s, m)) if m else 0, p) for s, v, _, p in rows]
    return enrich(gom), enrich(xa)


def weekly_ctx(repo, flows):
    """Nhu video.build_ctx nhung gop tuan: bar = tung phien trong tuan, movers = tong
    day_story, heat = % gia tuan cua chinh cac movers. week=True de scene doi tieu de.
    Dung chung cho ca 2 phan — scene nao chieu do script phan do quyet (plan_scenes)."""
    d1, d2 = week_range(now_vn())
    rows = [f for f in flows.foreign_daily("VNINDEX", 6) if d1 <= f.trading_date <= d2]
    gom, xa = week_movers(repo, flows, d1, d2)
    closes, _, _ = flows.ohlc("VNINDEX")
    index = None
    if len(closes) >= 6 and closes[-6]:
        index = {"close": closes[-1], "change": closes[-1] - closes[-6],
                 "pct": (closes[-1] / closes[-6] - 1) * 100}
    return {"net_ty": sum(f.net_val for f in rows) / 1e9,
            "date": f"Tuần {d1[8:]}/{d1[5:7]} – {d2[8:]}/{d2[5:7]}/{d2[:4]}",
            "index": index, "rows": rows, "heat": [(s, p) for s, _, _, p in gom + xa],
            "gom": gom, "xa": xa, "funds": fund_data(repo), "week": True}


def _week_data(repo, flows, d1, d2, part):
    rows = [f for f in flows.foreign_daily("VNINDEX", 6) if d1 <= f.trading_date <= d2]
    data = f"Tuần {d1} đến {d2}, khối ngoại sàn HOSE:"
    data += f"\nLũy kế cả tuần: {sum(f.net_val for f in rows) / 1e9:+,.0f} tỷ"
    if part == 1:
        data += "\nTừng phiên (tỷ đồng): " + ", ".join(
            f"{f.trading_date[8:]}/{f.trading_date[5:7]}: {f.net_val / 1e9:+,.0f}" for f in rows)
        closes, _, _ = flows.ohlc("VNINDEX")
        if len(closes) >= 6 and closes[-6]:
            data += f"\nVN-Index: {closes[-1]:,.1f} điểm, cả tuần {(closes[-1] / closes[-6] - 1) * 100:+.1f}%"
        gom, xa = week_movers(repo, flows, d1, d2)
        for label, rows2 in (("Top gom cả tuần", gom), ("Top xả cả tuần", xa)):
            if rows2:
                data += f"\n{label}: " + ", ".join(
                    f"{s} {v / 1e9:+,.0f} tỷ (giá tuần {p:+.1f}%)" for s, v, _, p in rows2)
    else:
        gom, xa = week_fusion(repo, flows, d1, d2)
        for label, rows2 in (("Khối ngoại gom cả tuần", gom), ("Khối ngoại xả cả tuần", xa)):
            if rows2:
                data += f"\n{label}: " + ", ".join(
                    f"{s} {v / 1e9:+,.0f} tỷ, {n} quỹ mở đang nắm, giá tuần {p:+.1f}%"
                    for s, v, n, p in rows2)
        data += fund_summary_text(repo)
    return data


def make_week_script(repo, flows, llm, part=1, now=None):
    """Script tuan tho phan 1/2 — chot 1 lan/tuan/phan vao meta. `now` inject duoc cho test."""
    now = now or now_vn()
    y, w, _ = now.isocalendar()
    key = f"script:week:{y}-W{w:02d}-p{part}"
    saved = repo.get_meta(key)
    if saved:
        return saved
    d1, d2 = week_range(now)
    data = _week_data(repo, flows, d1, d2, part)
    text = llm.complete(WEEK_SYSTEMS[part], f"Dữ liệu tuần:\n\n{data}\n\nViết script.").strip()
    repo.set_meta(key, text)
    return text


def maybe_send_week_script(repo, flows, llm, tg):
    """Goi moi vong lap main; thu 7 chot script 2 phan + gui kenh duyet (single source of
    truth nhu script ngay — video local sync DB ve la dung dung ban nay)."""
    now = now_vn()
    y, w, _ = now.isocalendar()
    if now.weekday() != 5 or repo.get_meta(f"script:week:{y}-W{w:02d}-p1"):
        return
    try:
        for part, label in ((1, "đăng thứ 7"), (2, "đăng CN")):
            text = make_week_script(repo, flows, llm, part=part)
            if tg.cfg.get("chat_ids"):
                tg.send_to(tg.cfg["chat_ids"][0], f"🎬 Script video tuần — phần {part} ({label}):\n\n{text}")
        print(f"[{now.isoformat(timespec='seconds')}] script tuan {y}-W{w:02d} (2 phan) da chot")
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] script tuan failed: {e}")
