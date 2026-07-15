"""Tao video TikTok 1080x1920 tu dien bien khoi ngoai hom nay.

Pipeline: script (Gemini) -> tach [HOOK]/[THAN]/[KET] -> TTS tung doan (Gemini Leda)
-> render 3 slide (PIL) -> ffmpeg ghep anh + audio + caption -> daily.mp4

Chay local (can ffmpeg):
    python video.py          # tao video_out/daily.mp4
    python video.py --send   # tao xong gui vao Telegram (chat dau tien trong config)
"""

import base64
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request
import wave
from functools import lru_cache
from pathlib import Path

from brief import load_env
from collector import DB, fetch_foreign_daily, make_script

load_env()

OUT = Path(__file__).parent / "video_out"
W, H = 1080, 1920
BG, FG = (15, 17, 21), (240, 240, 245)
GREEN, RED, DIM = (34, 197, 94), (239, 68, 68), (140, 145, 160)
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
TTS_STYLE = "Đọc bằng giọng nữ trẻ trung, năng lượng cao, tốc độ nhanh như video TikTok tài chính: "

FPS = 30
XFADE = 0.35            # giay crossfade giua 2 canh
CHART_CUT, HEAT_CUT = 0.4, 0.7  # ponytail: moc chia THAN, chinh tay sau khi xem ban dau


def clamp01(t):
    return 0.0 if t < 0 else 1.0 if t > 1 else float(t)


def ease(t):
    """Ease-out cubic, tu clamp ve [0,1]."""
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    """Tron 2 mau RGB theo t."""
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def build_timeline(d0, d1, d2):
    """5 canh tren truc audio lien tuc; d0/d1/d2 = duration 3 doan TTS."""
    return [
        ("hook", 0.0, d0),
        ("chart", d0, d0 + CHART_CUT * d1),
        ("heatmap", d0 + CHART_CUT * d1, d0 + HEAT_CUT * d1),
        ("movers", d0 + HEAT_CUT * d1, d0 + d1),
        ("outro", d0 + d1, d0 + d1 + d2),
    ]


def chunks_with_times(text, start, duration, size=5):
    """Chia text thanh cum ~size tu, chia duration ty le so ky tu.
    Tra ve [(cum, t0, t1)] voi thoi gian tuyet doi (cong start)."""
    words = text.split()
    if not words:
        return []
    chunks = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
    weights = [len(c) + 1 for c in chunks]
    total = sum(weights)
    out, t = [], start
    for c, w in zip(chunks, weights):
        dt = duration * w / total
        out.append((c, t, t + dt))
        t += dt
    return out


@lru_cache(maxsize=None)
def _font(size, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def _wrap(draw, text, font, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _caption(img, text, max_lines=5):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    font = _font(40, bold=False)
    lines = _wrap(d, text, font, W - 160)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] += " …"
    y = H - 140 - len(lines) * 54
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=FG)
        y += 54


def slide_hook(net_ty, date, text):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 380), "KHỐI NGOẠI HÔM NAY", font=_font(64), fill=DIM, anchor="mm")
    d.text((W / 2, 470), date, font=_font(48, bold=False), fill=DIM, anchor="mm")
    color = GREEN if net_ty >= 0 else RED
    d.text((W / 2, 760), f"{net_ty:+,.0f}", font=_font(220), fill=color, anchor="mm")
    d.text((W / 2, 950), "TỶ ĐỒNG " + ("MUA RÒNG" if net_ty >= 0 else "BÁN RÒNG"),
           font=_font(66), fill=color, anchor="mm")
    _caption(img, text)
    return img


def slide_chart(rows, movers, text):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 200), "10 PHIÊN GẦN NHẤT (tỷ đồng)", font=_font(52), fill=FG, anchor="mm")
    # bar chart ve tay bang PIL
    vals = [r["netVal"] / 1e9 for r in rows]
    peak = max(abs(v) for v in vals) or 1
    x0, y_mid, bw, bh = 90, 620, (W - 180) // len(vals), 300
    for i, v in enumerate(vals):
        h = int(abs(v) / peak * bh)
        x = x0 + i * bw
        color = GREEN if v >= 0 else RED
        top = y_mid - h if v >= 0 else y_mid
        d.rectangle([x + 8, top, x + bw - 8, top + h], fill=color)
        d.text((x + bw / 2, y_mid + bh + 40), rows[i]["tradingDate"][8:10],
               font=_font(30, bold=False), fill=DIM, anchor="mm")
    d.line([x0, y_mid, W - 90, y_mid], fill=DIM, width=2)
    # top movers
    y = 1130
    for title, items, color in (("GOM", movers[0], GREEN), ("XẢ", movers[1], RED)):
        d.text((120, y), title, font=_font(46), fill=color)
        d.text((290, y), "  ".join(f"{s} {v/1e9:+,.0f}" for s, v in items) or "—",
               font=_font(42, bold=False), fill=FG)
        y += 85
    _caption(img, text)
    return img


def slide_outro(text):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 700), "FOLLOW ĐỂ CẬP NHẬT", font=_font(80), fill=FG, anchor="mm")
    d.text((W / 2, 820), "KHỐI NGOẠI MỖI PHIÊN", font=_font(80), fill=GREEN, anchor="mm")
    d.text((W / 2, 1050), "Thông tin tham khảo — không phải khuyến nghị đầu tư",
           font=_font(36, bold=False), fill=DIM, anchor="mm")
    _caption(img, text)
    return img


def tts(text, path):
    body = json.dumps({
        "contents": [{"parts": [{"text": TTS_STYLE + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Leda"}}},
        },
    }).encode()
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview:generateContent",
        data=body, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
    j = json.load(urllib.request.urlopen(req, timeout=180))
    pcm = base64.b64decode(j["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def split_script(script):
    """Tach script thanh (hook, than, ket); fallback: chia cau."""
    parts = re.split(r"\[(?:HOOK|THÂN|THAN|KẾT|KET)\]", script)
    parts = [p.strip() for p in parts[1:] if p.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], re.sub(r"#\S+", "", parts[2]).strip()
    sents = re.split(r"(?<=[.!?]) ", script)
    third = max(1, len(sents) // 3)
    return " ".join(sents[:third]), " ".join(sents[third:-third] or sents[third:]), " ".join(sents[-third:])


def top_mover_rows(db, n=3):
    """Top mua/ban rong tu snapshot moi nhat -> ([(sym, net, price, pct)], [...])."""
    ts = db.execute("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    rows = db.execute(
        "SELECT symbol, buy_val - sell_val AS dn, price, COALESCE(pct, 0) "
        "FROM snapshots WHERE ts=? AND ABS(dn) > 1e9 ORDER BY dn DESC", (ts,)).fetchall()
    gom = [tuple(r) for r in rows[:n] if r[1] > 0]
    xa = [tuple(r) for r in rows[::-1][:n] if r[1] < 0]
    return gom, xa


def heatmap_rows(db, n=20):
    """Top n ma theo GTGD ngay, tu snapshot moi nhat -> [(symbol, pct)]."""
    ts = db.execute("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    return [tuple(r) for r in db.execute(
        "SELECT symbol, COALESCE(pct, 0) FROM snapshots WHERE ts=? "
        "ORDER BY day_value DESC LIMIT ?", (ts, n))]


def fetch_index():
    """Diem VN-Index phien gan nhat tu VNDirect; None neu loi — video van render."""
    url = ("https://api-finfo.vndirect.com.vn/v4/vnmarket_prices"
           "?q=code:VNINDEX&size=1&sort=date:desc")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(req, timeout=15))["data"][0]
        return {"close": d["close"], "change": d["change"], "pct": d["pctChange"]}
    except Exception:
        return None


def make_video(out=None):
    OUT.mkdir(exist_ok=True)
    out = out or OUT / "daily.mp4"
    db = sqlite3.connect(DB)
    script = make_script(db).split("\n\n", 1)[-1]  # bo header "🎬 ..."
    hook, than, ket = split_script(script)
    rows = fetch_foreign_daily("VNINDEX", 10)
    net_ty = rows[-1]["netVal"] / 1e9
    date = rows[-1]["tradingDate"]
    slides = [
        slide_hook(net_ty, date, hook),
        slide_chart(rows, top_mover_rows(db), than),
        slide_outro(ket),
    ]
    segs = []
    for i, (img, text) in enumerate(zip(slides, (hook, than, ket))):
        png, wav_f, seg = OUT / f"s{i}.png", OUT / f"s{i}.wav", OUT / f"s{i}.mp4"
        img.save(png)
        tts(text, wav_f)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png,
                        "-i", wav_f, "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
                        "-pix_fmt", "yuv420p", "-shortest", seg], check=True)
        segs.append(seg)
    concat = OUT / "list.txt"
    concat.write_text("".join(f"file '{s.name}'\n" for s in segs))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", concat, "-c", "copy", out], check=True, cwd=OUT)
    return out


def send_video(path):
    from collector import load_config
    cfg = load_config()
    url = f"https://api.telegram.org/bot{cfg['token']}/sendVideo"
    subprocess.run(["curl", "-s", "-F", f"chat_id={cfg['chat_ids'][0]}",
                    "-F", f"video=@{path}", "-F", "caption=🎬 Video khối ngoại hôm nay", url],
                   check=True, capture_output=True)


def selftest():
    assert ease(0) == 0 and ease(1) == 1 and 0 < ease(0.5) < 1
    assert ease(-5) == 0 and ease(5) == 1
    assert mix((0, 0, 0), (100, 200, 50), 0.5) == (50, 100, 25)

    tl = build_timeline(3, 10, 4)
    assert [s[0] for s in tl] == ["hook", "chart", "heatmap", "movers", "outro"]
    assert tl[0][1] == 0 and abs(tl[-1][2] - 17) < 1e-9
    for (_, _, b), (_, c, _) in zip(tl, tl[1:]):
        assert abs(b - c) < 1e-9  # cac canh lien tuc, khong ho

    ks = chunks_with_times("một hai ba bốn năm sáu bảy tám", 2.0, 6.0, size=3)
    assert ks[0][0] == "một hai ba" and ks[0][1] == 2.0
    assert abs(ks[-1][2] - 8.0) < 1e-9
    assert all(a[2] == b[1] for a, b in zip(ks, ks[1:]))
    assert chunks_with_times("", 0, 5) == []

    from collector import SCHEMA
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    ts = "2026-01-05T14:00:00+07:00"
    rows = [  # (symbol, buy, sell, day_value, price, pct)
        ("AAA", 9e9, 1e9, 300e9, 20000, 2.5),   # net +8 ty
        ("BBB", 1e9, 6e9, 200e9, 15000, -1.2),  # net -5 ty
        ("CCC", 2e9, 2.5e9, 100e9, 30000, 0.4), # net -0.5 ty -> duoi nguong movers
    ]
    for s, b, sl, dv, p, pc in rows:
        db.execute("INSERT INTO snapshots VALUES (?,?,?,?,0,0,1e6,?,?,?)",
                   (ts, s, b, sl, p, dv, pc))
    heat = heatmap_rows(db, n=2)
    assert heat == [("AAA", 2.5), ("BBB", -1.2)], heat  # sap theo day_value
    gom, xa = top_mover_rows(db)
    assert gom == [("AAA", 8e9, 20000, 2.5)], gom
    assert xa == [("BBB", -5e9, 15000, -1.2)], xa
    print("selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        path = make_video()
        print("Video:", path)
        if "--send" in sys.argv:
            send_video(path)
            print("Đã gửi vào Telegram")
