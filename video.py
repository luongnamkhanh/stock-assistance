"""Tao video TikTok 1080x1920 tu dien bien khoi ngoai hom nay.

Pipeline: script (Gemini) -> tach [HOOK]/[THAN]/[KET] -> TTS tung doan (Gemini Leda)
-> timeline 5 canh -> render tung frame 30fps (PIL) pipe vao ffmpeg -> daily.mp4

Chay local (can ffmpeg):
    python video.py          # tao video_out/daily.mp4
    python video.py --send   # tao xong gui vao Telegram (chat dau tien trong config)
"""

import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import wave
from functools import lru_cache
from pathlib import Path

from src.adapters.chart import BG, BG2, DIM, FG, GREEN, HEAT_NEUTRAL, RED, clamp01, lerp, mix
from src.config import DB, load_config, load_env, now_vn
from src.infrastructure.sqlite_repo import SqliteRepo
from src.infrastructure.telegram import TelegramBot
from src.infrastructure.vndirect_api import VnDirect
from src.usecases.build_trend import top_movers
from src.usecases.funds import fund_data
from src.infrastructure.llm import LlmClient
from src.usecases.make_script import make_script

load_env()

# PIL import cuc bo trong tung ham ve — de --send/--frames chay duoc khong can PIL
OUT = Path(__file__).parent / "video_out"


def day_dir():
    """Artifact chot theo ngay: video_out/YYYY-MM-DD/ — script/voice/render cua
    cung 1 ngay song chung 1 folder, khong ghi de cheo ngay."""
    d = OUT / now_vn().strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d
W, H = 1080, 1920
CAPTION_BOTTOM = H - 360
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
TTS_STYLE = "Đọc bằng giọng nữ trẻ trung, năng lượng cao, tốc độ nhanh như video TikTok tài chính: "

FPS = 30
XFADE = 0.35            # giay crossfade giua 2 canh


def ease(t):
    """Ease-out cubic, tu clamp ve [0,1]."""
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def build_timeline(names, durs):
    """Moi canh khop 1 doan TTS: moc canh = duration that cua doan do,
    thu tu canh = thu tu mach ke cua script (tu plan_scenes)."""
    out, t = [], 0.0
    for name, d in zip(names, durs):
        out.append((name, t, t + d))
        t += d
    return out


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


def draw_bg(t):
    """Nen gradient doc troi cham. Ve cot 1x240 roi resize — re va muot."""
    from PIL import Image
    col = Image.new("RGB", (1, 240))
    phase = math.sin(t * 0.25) * 0.2
    col.putdata([mix(BG, BG2, clamp01(y / 240 + phase)) for y in range(240)])
    return col.resize((W, H))


def heat_color(pct):
    """Diverging: RED <- xam trung tinh -> GREEN, bao hoa tai ±3%.
    Cap 0.75 de chu trang tren o van doc duoc."""
    t = clamp01(abs(pct) / 3) * 0.75
    return mix(HEAT_NEUTRAL, GREEN if pct >= 0 else RED, t)


def draw_caption(img, track, t):
    """Karaoke: cum dang doc to & sang o vung an toan, cum truoc mo phia tren."""
    from PIL import ImageDraw
    idx = next((i for i, (_, a, b) in enumerate(track) if a <= t < b), None)
    if idx is None:
        return
    d = ImageDraw.Draw(img)
    font = _font(52)
    lines = _wrap(d, track[idx][0], font, W - 300)[:2]
    y = CAPTION_BOTTOM - len(lines) * 66
    if idx > 0:
        pfont = _font(38, bold=False)
        prev = _wrap(d, track[idx - 1][0], pfont, W - 300)[0]
        d.text(((W - d.textlength(prev, font=pfont)) / 2, y - 56), prev,
               font=pfont, fill=DIM)
    for ln in lines:
        d.text(((W - d.textlength(ln, font=font)) / 2, y), ln, font=font, fill=FG)
        y += 66


def scene_hook(img, ctx, ts, dur):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    s = ease(ts / 0.4)
    d.text((W / 2, lerp(300, 380, s)), "KHỐI NGOẠI HÔM NAY",
           font=_font(64), fill=mix(BG, DIM, s), anchor="mm")
    d.text((W / 2, 470), ctx["date"], font=_font(44, bold=False), fill=DIM, anchor="mm")
    if ctx["index"] and ts > 0.3:
        i = ctx["index"]
        up = i["change"] >= 0
        d.text((W / 2, 570),
               f"VN-Index {i['close']:,.2f}  {'▲' if up else '▼'} "
               f"{abs(i['change']):,.2f} ({i['pct']:+.2f}%)",
               font=_font(40, bold=False), fill=GREEN if up else RED, anchor="mm")
    net = ctx["net_ty"]
    color = GREEN if net >= 0 else RED
    d.text((W / 2, 810), f"{net * ease(ts / 1.1):+,.0f}",   # count-up 1.1s
           font=_font(220), fill=color, anchor="mm")
    d.text((W / 2, 1000), "TỶ ĐỒNG " + ("MUA RÒNG" if net >= 0 else "BÁN RÒNG"),
           font=_font(64), fill=color, anchor="mm")


def scene_chart(img, ctx, ts, dur):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.text((W / 2, 260), "KHỐI NGOẠI 10 PHIÊN (tỷ đồng)",
           font=_font(52), fill=FG, anchor="mm")
    vals = [r.net_val / 1e9 for r in ctx["rows"]]
    peak = max(abs(v) for v in vals) or 1
    x0, y_mid, bh = 90, 850, 380
    bw = (W - 180) // len(vals)
    d.line([x0, y_mid, W - 90, y_mid], fill=DIM, width=2)
    for i, v in enumerate(vals):
        g = ease((ts - 0.2 - i * 0.06) / 0.35)   # moc dan, so le
        if g <= 0:
            continue
        h = int(abs(v) / peak * bh * g)
        x = x0 + i * bw
        last = i == len(vals) - 1
        color = (GREEN if v >= 0 else RED) if last else mix(BG, GREEN if v >= 0 else RED, 0.75)
        top = y_mid - h if v >= 0 else y_mid
        d.rectangle([x + 8, top, x + bw - 8, top + h], fill=color)
        if last and g >= 1:   # chi label cot hom nay (selective direct label)
            d.rectangle([x + 8, top, x + bw - 8, top + h], outline=FG, width=3)
            d.text((x + bw / 2, top - 44 if v >= 0 else top + h + 44),
                   f"{v:+,.0f}", font=_font(40), fill=FG, anchor="mm")
        d.text((x + bw / 2, y_mid + bh + 50), ctx["rows"][i].trading_date[8:10],
               font=_font(30, bold=False), fill=mix(BG, DIM, g), anchor="mm")


def scene_heatmap(img, ctx, ts, dur):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.text((W / 2, 260), "TOP GIAO DỊCH HÔM NAY", font=_font(52), fill=FG, anchor="mm")
    cols, gap, x0, y0, th = 4, 12, 70, 380, 180
    tw = (W - 2 * x0 - (cols - 1) * gap) // cols
    for i, (sym, pct) in enumerate(ctx["heat"]):
        g = ease((ts - 0.15 - i * 0.05) / 0.3)
        if g <= 0:
            continue
        r, c = divmod(i, cols)
        cx = x0 + c * (tw + gap) + tw / 2
        cy = y0 + r * (th + gap) + th / 2
        w2, h2 = tw / 2 * lerp(0.85, 1, g), th / 2 * lerp(0.85, 1, g)  # pop-in
        d.rectangle([cx - w2, cy - h2, cx + w2, cy + h2], fill=heat_color(pct))
        d.text((cx, cy - 28), sym, font=_font(46), fill=FG, anchor="mm")
        d.text((cx, cy + 34), f"{'▲' if pct >= 0 else '▼'}{abs(pct):.1f}%",
               font=_font(34, bold=False), fill=FG, anchor="mm")


def scene_movers(img, ctx, ts, dur):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.text((W / 2, 240), "KHỐI NGOẠI GOM / XẢ", font=_font(52), fill=FG, anchor="mm")
    cards = ([("GOM", *r, GREEN) for r in ctx["gom"]]
             + [("XẢ", *r, RED) for r in ctx["xa"]])
    y = 340
    for i, (tag, sym, net, price, pct, color) in enumerate(cards):
        g = ease((ts - 0.15 - i * 0.12) / 0.3)
        if g <= 0:
            y += 160
            continue
        x = 90 + int((1 - g) * 500)                 # truot tu phai vao
        d.rounded_rectangle([x, y, x + W - 180, y + 140], radius=18, fill=(28, 32, 42))
        d.rectangle([x, y, x + 14, y + 140], fill=color)
        d.text((x + 50, y + 70), f"{tag} {sym}", font=_font(54), fill=FG, anchor="lm")
        d.text((x + 470, y + 70), f"{net / 1e9:+,.0f} tỷ", font=_font(48), fill=color, anchor="lm")
        d.text((x + W - 230, y + 42), f"{price:,.0f}", font=_font(38, bold=False), fill=FG, anchor="rm")
        d.text((x + W - 230, y + 100), f"{'▲' if pct >= 0 else '▼'}{abs(pct):.1f}%",
               font=_font(38), fill=GREEN if pct >= 0 else RED, anchor="rm")
        y += 160


def scene_funds(img, ctx, ts, dur):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.text((W / 2, 240), "QUỸ MỞ ĐANG NẮM", font=_font(52), fill=FG, anchor="mm")
    fd = ctx.get("funds")
    if not fd:
        return
    d.text((W / 2, 310), f"nguồn Fmarket — tháng {fd['month'][5:]}/{fd['month'][:4]}, top 10 khoản mỗi quỹ",
           font=_font(28, bold=False), fill=DIM, anchor="mm")
    rows = fd["rows"][:7]
    peak = rows[0][1] if rows else 1
    y = 400
    for i, (sym, n, delta) in enumerate(rows):
        g = ease((ts - 0.15 - i * 0.08) / 0.35)
        if g <= 0:
            y += 140
            continue
        d.text((100, y + 34), sym, font=_font(46), fill=FG, anchor="lm")
        w = max(int(n / peak * 500 * g), 24)  # cap 500 de label "N quỹ" khong cham delta ben phai
        d.rounded_rectangle([260, y + 4, 260 + w, y + 64], radius=12, fill=mix(BG, GREEN, 0.55))
        d.text((280 + w, y + 34), f"{n} quỹ", font=_font(38), fill=FG, anchor="lm")
        if delta and g >= 1:
            up = delta > 0
            d.text((W - 90, y + 34), f"{'▲' if up else '▼'}{abs(delta)}",
                   font=_font(36), fill=GREEN if up else RED, anchor="rm")
        y += 140


def scene_outro(img, ctx, ts, dur):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    s1, s2 = ease((ts - 0.1) / 0.35), ease((ts - 0.3) / 0.35)
    if s1 > 0:
        d.text((W / 2, 700), "FOLLOW ĐỂ CẬP NHẬT",
               font=_font(int(lerp(60, 80, s1))), fill=FG, anchor="mm")
    if s2 > 0:
        d.text((W / 2, 830), "KHỐI NGOẠI MỖI PHIÊN",
               font=_font(int(lerp(60, 80, s2))), fill=GREEN, anchor="mm")
    d.text((W / 2, 1060), "Thông tin tham khảo — không phải khuyến nghị đầu tư",
           font=_font(36, bold=False), fill=mix(BG, DIM, ease(ts / 0.8)), anchor="mm")


SCENES = {"hook": scene_hook, "chart": scene_chart, "heatmap": scene_heatmap,
          "movers": scene_movers, "funds": scene_funds, "outro": scene_outro}


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


def tts(text, path):
    body = json.dumps({
        "contents": [{"parts": [{"text": TTS_STYLE + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Leda"}}},
        },
    }).encode()
    j = None
    for model in ("gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=body, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"})
        for attempt in range(3):
            try:
                j = json.load(urllib.request.urlopen(req, timeout=180))
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:  # het quota model nay -> thu model sau
                    break
                if e.code < 500 or attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))  # 5xx transient -> thu lai
        if j is not None:
            break
    if j is None:
        raise RuntimeError("TTS: het quota tat ca model")
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


def hook_number(text, fallback):
    """So dem o canh hook = so dau tien script doc (vd 'xả 4.600 tỷ' -> -4600)
    de hinh khop loi doc; hook khong neu so 'tỷ' nao -> net hom nay."""
    m = re.search(r"([\d.,]+)\s*(nghìn\s+)?tỷ", text, re.I)
    if not m:
        return fallback
    v = float(m.group(1).replace(".", "").replace(",", "."))
    if m.group(2):
        v *= 1000
    if re.search(r"bán|xả", text, re.I):
        return -v
    if re.search(r"mua|gom", text, re.I):
        return v
    return v if fallback >= 0 else -v


TREND_RE = re.compile(r"\d+\s*phiên|liên tiếp|chuỗi|lũy kế|đảo chiều|hạ nhiệt|xu hướng", re.I)
HEAT_RE = re.compile(r"%|phần trăm|sắc xanh|sắc đỏ|nhuộm|bứt phá|tăng trần|giảm sàn|tăng giá|giảm giá", re.I)
FLOW_RE = re.compile(r"gom|xả|mua|bán|\btỷ\b", re.I)  # cau noi dong tien (vs cau thuan % gia)
FUND_RE = re.compile(r"quỹ", re.I)                    # cau noi quy mo -> scene funds


def plan_scenes(hook, than, ket, symbols):
    """Gan tung cau cua THAN vao canh theo noi dung (ten ma -> movers, chuoi phien ->
    chart, %/mau -> heatmap, khong ro -> theo cau truoc), cau lien nhau cung canh thi
    gop chung 1 doan TTS — canh chieu theo mach ke cua script, khong ep script theo canh."""
    sym_re = re.compile("|".join(map(re.escape, symbols))) if symbols else None
    segs, prev = [("hook", hook)], "chart"
    for s in re.split(r"(?<=[.!?])\s+", than):
        s = s.strip()
        if not s:
            continue
        if FUND_RE.search(s):
            sc = "funds"   # uu tien truoc sym: "quỹ gom HPG" van la chuyen quy
        elif sym_re and sym_re.search(s):
            # co ten ma nhung thuan % gia (khong gom/xa/ty) -> van la noi dung heatmap
            sc = "heatmap" if HEAT_RE.search(s) and not FLOW_RE.search(s) else "movers"
        elif TREND_RE.search(s):
            sc = "chart"
        elif HEAT_RE.search(s):
            sc = "heatmap"
        else:
            sc = prev
        if segs[-1][0] == sc:
            segs[-1] = (sc, f"{segs[-1][1]} {s}")
        else:
            segs.append((sc, s))
        prev = sc
    segs.append(("outro", ket))
    return segs


def heatmap_rows(repo, n=20):
    """Top n ma theo GTGD ngay, tu snapshot moi nhat -> [(symbol, pct)]."""
    return repo.heat(repo.max_ts(), n)


def wav_dur(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def concat_wavs(paths, out):
    """Noi cac wav cung format (24kHz/mono/16-bit tu Gemini TTS)."""
    with wave.open(str(paths[0])) as w0:
        params = w0.getparams()
    with wave.open(str(out), "wb") as o:
        o.setparams(params)
        for p in paths:
            with wave.open(str(p)) as w:
                o.writeframes(w.readframes(w.getnframes()))


def build_ctx(repo):
    vnd = VnDirect()
    rows = vnd.foreign_daily("VNINDEX", 10)
    gom, xa = top_movers(repo)
    return {"net_ty": rows[-1].net_val / 1e9, "date": rows[-1].trading_date,
            "index": vnd.index_quote(), "rows": rows,
            "heat": heatmap_rows(repo), "gom": gom, "xa": xa, "funds": fund_data(repo)}


def stage_script(repo, force=False):
    """Stage 1 — chot script cua ngay (1 lan goi Gemini); da chot thi dung lai."""
    f = day_dir() / "script.txt"
    if f.exists() and not force:
        print("script: dung ban da chot", f)
        return f.read_text()
    text = make_script(repo, VnDirect(), LlmClient())  # script tho, khong header
    f.write_text(text)
    print("script: chot ban moi", f)
    return text


def stage_tts(repo, script, force=False):
    """Stage 2 — chot voice: scene plan (segs.json) + TTS tung doan (s{i}.wav).
    Da co du artifact thi dung lai; thieu wav nao (crash giua chung) thi TTS bu."""
    d = day_dir()
    segs_f = d / "segs.json"
    if segs_f.exists() and not force:
        segs = [tuple(x) for x in json.loads(segs_f.read_text())]
    else:
        gom, xa = top_movers(repo)
        segs = plan_scenes(*split_script(script), [s for s, *_ in gom + xa])
        segs_f.write_text(json.dumps(segs, ensure_ascii=False))
    wavs = []
    for i, (_, text) in enumerate(segs):
        w = d / f"s{i}.wav"
        if force or not w.exists():
            tts(text, w)
        wavs.append(w)
    return segs, wavs


def stage_render(repo, segs, wavs):
    """Stage 3 — thuan local (PIL + ffmpeg, khong API): lap lai thoai mai khi chinh
    visual/animation, script & voice giu nguyen. Moi lan ra 1 ban render-HHMM.mp4."""
    d = day_dir()
    ctx = build_ctx(repo)
    ctx["net_ty"] = hook_number(segs[0][1], ctx["net_ty"])  # so tren hinh = so voice doc
    durs = [wav_dur(p) for p in wavs]
    audio = d / "audio.wav"
    concat_wavs(wavs, audio)

    timeline = build_timeline([n for n, _ in segs], durs)
    (d / "timeline.json").write_text(json.dumps(timeline))  # cho --frames biet moc canh
    karaoke = []
    start = 0.0
    for (_, text), dur in zip(segs, durs):
        karaoke += chunks_with_times(text, start, dur)
        start += dur

    out = d / f"render-{now_vn():%H%M}.mp4"
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", audio, "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)], stdin=subprocess.PIPE)
    try:
        for f in range(int(sum(durs) * FPS)):
            proc.stdin.write(render_frame(f / FPS, ctx, timeline, karaoke).tobytes())
    finally:
        proc.stdin.close()
        code = proc.wait()
    if code != 0:
        raise RuntimeError("ffmpeg failed")
    shutil.copy(out, d / "daily.mp4")  # ban moi nhat cua ngay
    frames(out)  # keyframes QA luon co san trong <ngay>/frames/
    return out


def make_video():
    repo = SqliteRepo(DB)
    fresh = "--fresh" in sys.argv  # chot lai script + voice (mac dinh: dung ban da chot)
    script = stage_script(repo, force=fresh)
    segs, wavs = stage_tts(repo, script, force=fresh)
    return stage_render(repo, segs, wavs)


def frames(video=None):
    """Trich 2 frame/canh (dau + giua) de soat bang mat — rule: moi frame bat ky
    cua video phai doc duoc day du noi dung (khong caption trong, khong so cut)."""
    d = day_dir()
    video = video or d / "daily.mp4"
    tl_f = d / "timeline.json"
    fdir = d / "frames"
    fdir.mkdir(exist_ok=True)
    for p in fdir.glob("*.png"):
        p.unlink()  # don frame cu — canh dong theo script, ten/so luong doi tung ngay
    if tl_f.exists():
        marks = []
        for i, (name, a, b) in enumerate(json.loads(tl_f.read_text())):
            marks += [(f"{i}_{name}_dau", a + 0.45), (f"{i}_{name}_giua", (a + b) / 2)]
    else:  # video cu chua co timeline -> chia deu theo thoi luong
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(video)], capture_output=True, text=True, check=True).stdout)
        marks = [(f"p{i}", dur * f) for i, f in
                 enumerate((0.03, 0.15, 0.3, 0.45, 0.55, 0.7, 0.85, 0.97))]
    out = []
    for name, t in marks:
        png = fdir / f"{name}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                        "-i", str(video), "-frames:v", "1", str(png)], check=True)
        out.append(png)
        print("frame:", png)
    return out


def send_video(path):
    tg = TelegramBot(load_config())
    tg.send_video(tg.cfg["chat_ids"][0], path, "🎬 Video khối ngoại hôm nay")


def render_frame(t, ctx, timeline, karaoke):
    """1 frame tai thoi diem t: nen + canh (crossfade voi canh truoc) + caption."""
    from PIL import Image
    idx = next((i for i, (_, a, b) in enumerate(timeline) if a <= t < b),
               len(timeline) - 1)
    name, a, b = timeline[idx]
    img = draw_bg(t)
    SCENES[name](img, ctx, t - a, b - a)
    if idx > 0 and t - a < XFADE:
        pname, pa, pb = timeline[idx - 1]
        prev = draw_bg(t)
        SCENES[pname](prev, ctx, pb - pa, pb - pa)   # canh truoc o trang thai cuoi
        img = Image.blend(prev, img, ease((t - a) / XFADE))
    draw_caption(img, karaoke, t)
    return img


def preview():
    """PNG giua moi canh tu data gia — khong can mang/TTS/ffmpeg."""
    from src.domain.entities import DayFlow
    ctx = {
        "net_ty": -193, "date": "2026-07-16",
        "index": {"close": 1782.12, "change": -24.51, "pct": -1.36},
        "rows": [DayFlow(f"2026-07-{d:02d}", v * 1e9)
                 for d, v in zip(range(1, 11),
                                 (120, -80, 200, -350, 90, -60, 150, -500, 300, -193))],
        "heat": list(zip(
            "HPG VIC VHM FPT MSN CTG TCB MBB SSI VND HDB STB MWG VNM GAS PNJ DGC VRE BID ACB".split(),
            (1.2, -2.3, 0.5, 3.1, -0.8, 1.9, -1.2, 0.0, 2.4, -3.5,
             0.7, -0.3, 1.1, -1.8, 0.9, 2.8, -2.1, 0.4, -0.6, 1.5))),
        "gom": [("HPG", 120e9, 22300, 1.2), ("FPT", 85e9, 98700, 3.1), ("SSI", 40e9, 31200, 2.4)],
        "xa": [("VND", -95e9, 15600, -3.5), ("VIC", -70e9, 41800, -2.3), ("DGC", -33e9, 88000, -2.1)],
        "funds": {"month": "2026-07", "rows": [("HPG", 27, 2), ("CTG", 25, -1), ("MWG", 23, 0),
                                               ("MBB", 20, None), ("TCB", 19, 3), ("VCB", 17, None),
                                               ("ACB", 15, 1)], "new": ["VIX"], "out": []},
    }
    timeline = build_timeline(["hook", "chart", "heatmap", "movers", "funds", "outro"], [4.0] * 6)
    demo = chunks_with_times(
        "Đây là caption karaoke chạy thử để xem vị trí vùng an toàn phía dưới", 0, 20)
    pdir = OUT / "preview"
    pdir.mkdir(parents=True, exist_ok=True)
    for name, a, b in timeline:
        f = pdir / f"{name}.png"
        render_frame((a + b) / 2, ctx, timeline, demo).save(f)
        print("preview:", f)


def selftest():
    assert ease(0) == 0 and ease(1) == 1 and 0 < ease(0.5) < 1
    assert ease(-5) == 0 and ease(5) == 1
    assert mix((0, 0, 0), (100, 200, 50), 0.5) == (50, 100, 25)

    tl = build_timeline(["hook", "chart", "movers", "outro"], [3, 6, 5, 2])
    assert [s[0] for s in tl] == ["hook", "chart", "movers", "outro"]
    assert tl[0][1] == 0 and abs(tl[-1][2] - 16) < 1e-9
    for (_, _, b), (_, c, _) in zip(tl, tl[1:]):
        assert abs(b - c) < 1e-9  # cac canh lien tuc, khong ho

    h, t, k = split_script("[HOOK] Bán ròng 29 tỷ.\n[THÂN] Nội dung chính.\n[KẾT] Follow nhé. #kn #vn")
    assert h == "Bán ròng 29 tỷ." and t == "Nội dung chính." and k == "Follow nhé."

    segs = plan_scenes("Hôm nay bán ròng 29 tỷ.",
                       "Đây là phiên bán ròng thứ tư liên tiếp. Sắc xanh vẫn áp đảo bảng điện. "
                       "Họ gom VIC 250 tỷ. VHM cũng được mua 150 tỷ. Ngày mai mình xem tiếp.",
                       "Follow nhé.", ["VIC", "VHM"])
    assert [s for s, _ in segs] == ["hook", "chart", "heatmap", "movers", "outro"], segs
    assert "VHM" in segs[3][1]          # 2 cau movers lien nhau gop 1 doan TTS
    assert "Ngày mai" in segs[3][1]     # cau khong ro chu de -> di theo canh truoc

    segs = plan_scenes("Mở đầu.", "VHM bứt phá 5%, VIC và ACB cùng tăng gần 3%. "
                       "Họ gom mạnh VIC 253 tỷ.", "Kết.", ["VIC", "VHM", "ACB"])
    assert [s for s, _ in segs] == ["hook", "heatmap", "movers", "outro"], segs

    segs = plan_scenes("Mở đầu.", "Các quỹ mở đang nắm HPG nhiều nhất, 27 quỹ trong danh mục. "
                       "Họ gom VIC 250 tỷ.", "Kết.", ["HPG", "VIC"])
    assert [s for s, _ in segs] == ["hook", "funds", "movers", "outro"], segs

    assert hook_number("Khối ngoại xả ròng hơn 4.600 tỷ đồng!", -29) == -4600
    assert hook_number("Họ gom 1,5 nghìn tỷ hôm nay", -29) == 1500
    assert hook_number("Một phiên không có gì nổi bật.", -29) == -29

    ks = chunks_with_times("một hai ba bốn năm sáu bảy tám", 2.0, 6.0, size=3)
    assert ks[0][0] == "một hai ba" and ks[0][1] == 2.0
    assert abs(ks[-1][2] - 8.0) < 1e-9
    assert all(a[2] == b[1] for a, b in zip(ks, ks[1:]))
    assert chunks_with_times("", 0, 5) == []

    repo = SqliteRepo(":memory:")
    ts = "2026-01-05T14:00:00+07:00"
    rows = [  # (symbol, buy, sell, day_value, price, pct)
        ("AAA", 9e9, 1e9, 300e9, 20000, 2.5),   # net +8 ty
        ("BBB", 1e9, 6e9, 200e9, 15000, -1.2),  # net -5 ty
        ("CCC", 2e9, 2.5e9, 100e9, 30000, 0.4), # net -0.5 ty -> duoi nguong movers
    ]
    repo.insert_snapshots(ts, [(s, b, sl, 0, 0, 1e6, p, dv, pc) for s, b, sl, dv, p, pc in rows])
    heat = heatmap_rows(repo, n=2)
    assert heat == [("AAA", 2.5), ("BBB", -1.2)], heat  # sap theo day_value
    gom, xa = top_movers(repo)
    assert gom == [("AAA", 8e9, 20000, 2.5)], gom
    assert xa == [("BBB", -5e9, 15000, -1.2)], xa

    assert heat_color(0) == HEAT_NEUTRAL
    assert heat_color(9) == heat_color(3.1)          # bao hoa tai ±3%
    g3, r3 = heat_color(3), heat_color(-3)
    assert g3[1] > g3[0] and r3[0] > r3[1]           # xanh nghieng G, do nghieng R
    bg = draw_bg(0.0)
    assert bg.size == (W, H) and bg.mode == "RGB"
    print("selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--preview" in sys.argv:
        preview()
    elif "--frames" in sys.argv:
        frames()
    elif "--send" in sys.argv:  # gui ban moi nhat cua ngay, khong render lai
        send_video(day_dir() / "daily.mp4")
        print("Đã gửi vào Telegram")
    else:
        path = make_video()
        print("Video:", path)
        if "--no-send" not in sys.argv:  # tele vua la noi duyet vua la archive
            send_video(path)
            print("Đã gửi vào Telegram")
