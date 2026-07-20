"""Anh dashboard tinh (PNG) cho Telegram/social — palette dung chung voi video.py
(video import tu day). PIL import cuc bo trong ham: bot van chay text-only neu thieu Pillow.
Font DejaVu bundle trong assets/ vi Railway khong co font he thong tieng Viet."""
import io
from functools import lru_cache

from src.config import ROOT

BG, FG = (15, 17, 21), (240, 240, 245)
GREEN, RED, DIM = (34, 197, 94), (239, 68, 68), (140, 145, 160)
BG2 = (26, 31, 46)
HEAT_NEUTRAL = (44, 49, 60)

W, H = 1080, 1350   # 4:5 — hien thi tot trong chat Telegram, dung duoc lam carousel
FONT_BOLD = str(ROOT / "assets" / "DejaVuSans-Bold.ttf")
FONT_REG = str(ROOT / "assets" / "DejaVuSans.ttf")


def clamp01(t):
    return 0.0 if t < 0 else 1.0 if t > 1 else float(t)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    """Tron 2 mau RGB theo t."""
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


@lru_cache(maxsize=None)
def _font(size, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def _bg():
    from PIL import Image
    col = Image.new("RGB", (1, 240))
    col.putdata([mix(BG, BG2, y / 240) for y in range(240)])
    return col.resize((W, H))


def _bars(d, rows):
    d.text((W / 2, 620), "Khối ngoại 10 phiên gần nhất (tỷ đồng)",
           font=_font(32, bold=False), fill=DIM, anchor="mm")
    if not rows:
        d.text((W / 2, 820), "(không lấy được dữ liệu phiên)",
               font=_font(32, bold=False), fill=DIM, anchor="mm")
        return
    vals = [r.net_val / 1e9 for r in rows]
    peak = max(abs(v) for v in vals) or 1
    x0, y_mid, bh = 90, 820, 130
    bw = (W - 180) // len(vals)
    d.line([x0, y_mid, W - x0, y_mid], fill=DIM, width=2)
    for i, v in enumerate(vals):
        h = int(abs(v) / peak * bh)
        x = x0 + i * bw
        last = i == len(vals) - 1
        color = (GREEN if v >= 0 else RED) if last else mix(BG, GREEN if v >= 0 else RED, 0.75)
        top = y_mid - h if v >= 0 else y_mid
        d.rectangle([x + 10, top, x + bw - 10, top + h], fill=color)
        if last:
            d.rectangle([x + 10, top, x + bw - 10, top + h], outline=FG, width=3)
            d.text((x + bw / 2, (top - 34) if v >= 0 else (y_mid - 34)), f"{v:+,.0f}",
                   font=_font(32), fill=FG, anchor="mm")
        d.text((x + bw / 2, y_mid + bh + 40), rows[i].trading_date[8:10],
               font=_font(26, bold=False), fill=DIM, anchor="mm")


def _movers(d, gom, xa):
    for x, title, rows, color in ((300, "TOP GOM", gom, GREEN), (W - 300, "TOP XẢ", xa, RED)):
        d.text((x, 1070), title, font=_font(40), fill=color, anchor="mm")
        if not rows:
            d.text((x, 1134), "—", font=_font(34, bold=False), fill=DIM, anchor="mm")
            continue
        y = 1134
        for sym, net, price, pct in rows:
            d.text((x, y), f"{sym}  {net / 1e9:+,.0f} tỷ  ({pct:+.1f}%)",
                   font=_font(34), fill=FG, anchor="mm")
            y += 56


def fund_png(data):
    """data (tu funds.fund_data): month, rows[(sym, so_quy, delta|None)], new, out
    -> PNG bytes 1080x1350."""
    from PIL import ImageDraw
    img = _bg()
    d = ImageDraw.Draw(img)
    d.text((W / 2, 100), "QUỸ MỞ ĐỒNG THUẬN", font=_font(58), fill=FG, anchor="mm")
    d.text((W / 2, 170), f"Tháng {data['month'][5:]}/{data['month'][:4]} — nguồn Fmarket (top 10 khoản mỗi quỹ)",
           font=_font(28, bold=False), fill=DIM, anchor="mm")
    d.text((W / 2, 232), "Số quỹ mở đang nắm mỗi mã trong top danh mục",
           font=_font(30, bold=False), fill=DIM, anchor="mm")
    rows = data["rows"]
    if not rows:
        d.text((W / 2, 700), "(chưa có dữ liệu)", font=_font(32, bold=False), fill=DIM, anchor="mm")
    else:
        peak = rows[0][1] or 1
        y = 330
        for sym, n, delta, *rest in rows:
            val = rest[0] if rest else None
            w = int(lerp(140, 560, n / peak))
            d.rounded_rectangle([260, y - 28, 260 + w, y + 28], radius=12, fill=mix(BG, GREEN, 0.45))
            d.text((110, y), sym, font=_font(44), fill=FG, anchor="lm")
            d.text((278, y), f"{n} quỹ" + (f" · {val / 1e9:,.0f} tỷ" if val else ""),
                   font=_font(34), fill=FG, anchor="lm")
            if delta:
                up = delta > 0
                d.text((980, y), f"{'▲' if up else '▼'}{abs(delta)}", font=_font(36),
                       fill=GREEN if up else RED, anchor="mm")
            y += 82
    if data["new"]:
        d.text((W / 2, 1160), "Mới vào top: " + ", ".join(data["new"]),
               font=_font(30), fill=GREEN, anchor="mm")
    if data["out"]:
        d.text((W / 2, 1215), "Rời top: " + ", ".join(data["out"]),
               font=_font(30), fill=RED, anchor="mm")
    d.text((W / 2, 1312), "Thông tin tham khảo — không phải khuyến nghị đầu tư",
           font=_font(24, bold=False), fill=DIM, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def daily_png(ctx):
    """ctx (tu build_trend.market_snapshot): date, net_ty, index|None, rows, gom, xa
    -> PNG bytes 1080x1350."""
    from PIL import ImageDraw
    img = _bg()
    d = ImageDraw.Draw(img)
    d.text((W / 2, 100), "KHỐI NGOẠI HÔM NAY", font=_font(58), fill=FG, anchor="mm")
    d.text((W / 2, 170), ctx["date"], font=_font(36, bold=False), fill=DIM, anchor="mm")
    if ctx.get("index"):
        i = ctx["index"]
        up = i["change"] >= 0
        d.text((W / 2, 240),
               f"VN-Index {i['close']:,.2f}  {'▲' if up else '▼'} {abs(i['change']):,.2f} ({i['pct']:+.2f}%)",
               font=_font(38, bold=False), fill=GREEN if up else RED, anchor="mm")
    net = ctx["net_ty"]
    color = GREEN if net >= 0 else RED
    d.text((W / 2, 400), f"{net:+,.0f}", font=_font(150), fill=color, anchor="mm")
    d.text((W / 2, 520), "TỶ ĐỒNG " + ("MUA RÒNG" if net >= 0 else "BÁN RÒNG") + " HÔM NAY",
           font=_font(44), fill=color, anchor="mm")
    _bars(d, ctx["rows"])
    _movers(d, ctx["gom"], ctx["xa"])
    d.text((W / 2, 1312), "Thông tin tham khảo — không phải khuyến nghị đầu tư",
           font=_font(24, bold=False), fill=DIM, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
