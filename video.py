"""Tao video TikTok 1080x1920 tu dien bien khoi ngoai hom nay.

Pipeline: script (Gemini) -> tach [HOOK]/[THAN]/[KET] -> TTS tung doan (Gemini Leda)
-> render 3 slide (PIL) -> ffmpeg ghep anh + audio + caption -> daily.mp4

Chay local (can ffmpeg):
    python video.py          # tao video_out/daily.mp4
    python video.py --send   # tao xong gui vao Telegram (chat dau tien trong config)
"""

import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request
import wave
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
    ts = db.execute("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    rows = db.execute("SELECT symbol, buy_val - sell_val AS dn FROM snapshots "
                      "WHERE ts=? AND ABS(dn) > 1e9 ORDER BY dn DESC", (ts,)).fetchall()
    return [(s, v) for s, v in rows[:n] if v > 0], [(s, v) for s, v in rows[::-1][:n] if v < 0]


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


if __name__ == "__main__":
    path = make_video()
    print("Video:", path)
    if "--send" in sys.argv:
        send_video(path)
        print("Đã gửi vào Telegram")
