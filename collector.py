"""Collector + alert engine: foreign-flow deltas on HOSE via SSI iBoard REST.

Polls all HOSE symbols every POLL_MINUTES during trading hours, stores snapshots
in SQLite, and sends two kinds of Telegram alerts:

1. SPIKE — foreign net flow within a WINDOW_MINUTES window is abnormally large
2. STATE — a symbol's flow regime CHANGES. Regime is derived from cumulative
   day net flow + its speed over the last STALL_MINUTES:
       GOM       day net >> 0 and still flowing in
       GOM_CHUNG day net >> 0 but inflow has stalled (delta thu hep)
       XA        day net << 0 and still flowing out
       XA_CHUNG  day net << 0 but outflow has stalled
   Only transitions are reported, so steady accumulation alerts once, and a
   stall alerts once more — no repeats.

Telegram commands (from any chat id listed in telegram.json "chat_ids";
the shared watchlist is editable by every member of an authorized chat):
    /watch HPG   — add to watchlist (half thresholds, state alerts luon bat)
    /unwatch HPG — remove
    /list        — show watchlist
    /help        — command help
    /id          — reply with the chat's id (works anywhere, for onboarding groups)

Alerts are INFORMATION ONLY — decisions stay with the human.

Usage:
    python collector.py --selftest   # run logic checks on synthetic data
    python collector.py --once       # one poll + report, then exit
    python collector.py              # loop forever (acts only 09:00-15:05 VN, Mon-Fri)
"""

import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

POLL_MINUTES = 5           # snapshot cadence
WINDOW_MINUTES = 10        # spike window ("1 phien" cua user)
MIN_DAY_VALUE = 30e9       # chi xet ma co GTGD ngay >= 30 ty VND (tru watchlist)
ALERT_MIN_NET = 3e9        # spike: |net flow 10'| >= 3 ty VND
ALERT_MIN_SHARE = 0.15     # spike: va >= 15% GTGD cua chinh window do
COOLDOWN_MINUTES = 30      # spike: khong bao lai cung ma cung chieu trong 30'
DAY_NET_TH = 15e9          # state: |net rong tu dau phien| >= 15 ty => co trang thai
STALL_MINUTES = 30         # state: cua so do toc do gan nhat
RATE_TH = 1e9              # state: |net 30'| < 1 ty => coi nhu chung lai
WL_FACTOR = 0.5            # watchlist: nguong spike & state nhan he so nay
ACCEL_MIN_LAST = 1.5e9     # accel: nhip cuoi >= 1.5 ty (nua nguong spike — tin hieu som)
ACCEL_MIN_SHARE = 0.10     # accel: nhip cuoi phai chiem >= 10% GTGD cua ma trong nhip do
DB = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "flows.db")))
CONFIG = Path(__file__).parent / "telegram.json"  # {"token": ..., "chat_id": ...} — keep private
VN_TZ = timezone(timedelta(hours=7))

API = "https://iboard-query.ssi.com.vn/stock/exchange/hose"
HEADERS = {"User-Agent": "Mozilla/5.0", "Origin": "https://iboard.ssi.com.vn"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    ts TEXT NOT NULL,               -- ISO time of poll (VN time)
    symbol TEXT NOT NULL,
    buy_val REAL, sell_val REAL,    -- cumulative foreign buy/sell value (VND) since open
    buy_qtty REAL, sell_qtty REAL,
    room REAL,                      -- remaining foreign room (shares)
    price REAL, day_value REAL,     -- matched price, cumulative day traded value
    pct REAL,                       -- price change % vs reference
    PRIMARY KEY (ts, symbol)
);
CREATE TABLE IF NOT EXISTS alerts (
    ts TEXT, symbol TEXT, direction TEXT, net_10m REAL, share REAL, price REAL,
    sent INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS state (symbol TEXT PRIMARY KEY, regime TEXT, day TEXT);
CREATE TABLE IF NOT EXISTS day_story (   -- dac tinh tung phien, chot luc tong ket 15:10
    day TEXT, symbol TEXT,
    net REAL,        -- NN mua/ban rong ca phien (VND)
    late_net REAL,   -- rieng 30' cuoi (tu 14:15)
    room_delta REAL, -- room NN cuoi - dau phien (cp)
    PRIMARY KEY (day, symbol)
);
CREATE TABLE IF NOT EXISTS watchlist (symbol TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

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

SCRIPT_SYSTEM = """Bạn là người viết kịch bản video TikTok ngắn (30-40 giây đọc thành tiếng) về chứng khoán Việt Nam.
Nhiệm vụ: từ dữ liệu giao dịch khối ngoại hôm nay, viết script cho 1 video.

Cấu trúc bắt buộc (plain text):
[HOOK] 1 câu mở đầu gây chú ý bằng con số ấn tượng nhất của phiên. Không chào hỏi.
[THÂN] 3-5 câu ngắn, kể ĐỦ 3 ý theo mạch: (1) chuỗi/xu hướng các phiên gần đây,
(2) sắc xanh/đỏ và % giá nổi bật của nhóm mã giao dịch lớn, (3) top gom/xả kèm số tỷ;
thêm điểm bất thường nếu có (đảo chiều, chuỗi phiên dài...).
[KẾT] 1 câu mời theo dõi kênh để cập nhật phiên sau.
Dòng cuối: 4-5 hashtag tiếng Việt.

Quy tắc: giọng nói chuyện tự nhiên, xưng "mình", câu ngắn dễ đọc thành tiếng, số liệu làm tròn
cho dễ nghe. KHÔNG khuyến nghị mua/bán. KHÔNG bịa gì ngoài dữ liệu được đưa."""

STATE_MSG = {  # dong 1 cua khung 3 tang — boi canh phien nam o ctx_line dung chung
    "GOM":       "🟢 {s} — vào trạng thái GOM: 30' qua {r:+.1f} tỷ",
    "GOM_CHUNG": "🟡 {s} — lực gom CHỮNG LẠI: 30' qua chỉ {r:+.1f} tỷ",
    "XA":        "🔴 {s} — vào trạng thái XẢ: 30' qua {r:+.1f} tỷ",
    "XA_CHUNG":  "🟠 {s} — lực xả CHỮNG LẠI: 30' qua chỉ {r:+.1f} tỷ",
}


def now_vn():
    return datetime.now(VN_TZ)


def in_trading_hours(dt):
    if dt.weekday() >= 5:
        return False
    hm = dt.hour * 60 + dt.minute
    return 9 * 60 <= hm <= 15 * 60 + 5  # 09:00 -> 15:05 (het ATC + du phong)


def load_config():
    if os.environ.get("TELEGRAM_TOKEN"):  # env vars (Railway/cloud) truoc, file sau
        ids = os.environ.get("TELEGRAM_CHAT_IDS", "").replace(" ", "")
        return {"token": os.environ["TELEGRAM_TOKEN"],
                "chat_ids": [int(x) for x in ids.split(",") if x]}
    if not CONFIG.exists():
        return {}
    cfg = json.loads(CONFIG.read_text())
    if "chat_ids" not in cfg and cfg.get("chat_id"):  # backward compat
        cfg["chat_ids"] = [cfg["chat_id"]]
    return cfg


VPS_LIST = "https://bgapidatafeed.vps.com.vn/getlistallstock"
VPS_DATA = "https://bgapidatafeed.vps.com.vn/getliststockdata/"
_vps_syms = []  # ponytail: cache RAM ca doi process, restart thi lay lai


def _f(x):
    """VPS tra field dang string/None."""
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _vps_row(x):
    """Map 1 record VPS -> tuple snapshot (chua co ts). Don vi: gia tri nghin dong
    (x1000 = VND), gia nghin dong, lot theo lo 10. changePc cua VPS KHONG co dau
    nen pct phai tinh tu gia tham chieu r."""
    last, ref = _f(x.get("lastPrice")), _f(x.get("r"))
    pct = round((last - ref) / ref * 100, 2) if ref else 0.0
    return (x["sym"], _f(x.get("fBValue")) * 1e3, _f(x.get("fSValue")) * 1e3,
            _f(x.get("fBVol")), _f(x.get("fSVolume")), _f(x.get("fRoom")),
            last * 1e3, _f(x.get("lot")) * 10 * _f(x.get("avePrice")) * 1e3, pct)


def _vps_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_vps():
    """Nguon du phong khi iBoard chan IP datacenter (403 tren Railway).
    Cung feed goc tu so — gia tri khop tuyet doi voi iBoard (da doi chieu)."""
    global _vps_syms
    if not _vps_syms:
        _vps_syms = sorted(s["stock_code"] for s in _vps_get(VPS_LIST)
                           if s.get("post_to") == "HOSE" and len(s.get("stock_code") or "") == 3)
    rows = []
    for i in range(0, len(_vps_syms), 100):
        rows += [_vps_row(x) for x in _vps_get(VPS_DATA + ",".join(_vps_syms[i:i + 100]))]
    return rows


def poll(db):
    try:
        with urllib.request.urlopen(urllib.request.Request(API, headers=HEADERS), timeout=30) as r:
            data = json.load(r)["data"]
        rows = [
            (x["stockSymbol"], x.get("buyForeignValue") or 0, x.get("sellForeignValue") or 0,
             x.get("buyForeignQtty") or 0, x.get("sellForeignQtty") or 0,
             x.get("remainForeignQtty") or 0, x.get("matchedPrice") or 0,
             x.get("nmTotalTradedValue") or 0, x.get("priceChangePercent") or 0)
            for x in data
            if x.get("stockType") == "s" and x.get("stockSymbol") and len(x["stockSymbol"]) == 3
        ]
    except Exception:
        rows = fetch_vps()  # iBoard chan IP datacenter -> fallback VPS
    ts = now_vn().isoformat(timespec="seconds")
    db.executemany("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
                   [(ts, *r) for r in rows])
    db.commit()
    return ts, len(rows)


def get_watchlist(db):
    return {r[0] for r in db.execute("SELECT symbol FROM watchlist")}


def prev_snapshot_ts(db, ts, minutes):
    cutoff = (datetime.fromisoformat(ts) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
    return db.execute("SELECT MAX(ts) FROM snapshots WHERE ts <= ? AND ts LIKE ?",
                      (cutoff, ts[:10] + "%")).fetchone()[0]


def detect_spikes(db, ts, wl):
    prev_ts = prev_snapshot_ts(db, ts, WINDOW_MINUTES)
    if not prev_ts:
        return []
    q = """
    SELECT a.symbol,
           (a.buy_val - b.buy_val) - (a.sell_val - b.sell_val) AS net,
           a.day_value - b.day_value AS win_value,
           a.day_value, a.price, a.pct,
           a.buy_val - a.sell_val AS day_net
    FROM snapshots a JOIN snapshots b USING (symbol)
    WHERE a.ts = ? AND b.ts = ?
    """
    alerts, msgs = [], []
    for sym, net, win_value, day_value, price, pct, day_net in db.execute(q, (ts, prev_ts)):
        f = WL_FACTOR if sym in wl else 1.0
        if day_value < MIN_DAY_VALUE * f or abs(net) < ALERT_MIN_NET * f or win_value <= 0:
            continue
        share = abs(net) / win_value
        if share < ALERT_MIN_SHARE:
            continue
        direction = "BUY" if net > 0 else "SELL"
        cooldown = (datetime.fromisoformat(ts) - timedelta(minutes=COOLDOWN_MINUTES)).isoformat(timespec="seconds")
        if db.execute("SELECT 1 FROM alerts WHERE symbol=? AND direction=? AND ts>?",
                      (sym, direction, cooldown)).fetchone():
            continue
        alerts.append((ts, sym, direction, net, share, price))
        msgs.append(spike_msg(sym, net, share, price, pct or 0, day_net) + trend_ctx(sym, db))
    db.executemany("INSERT INTO alerts (ts,symbol,direction,net_10m,share,price) VALUES (?,?,?,?,?,?)", alerts)
    db.commit()
    return msgs


def _trend_ctx(rows):
    """1 dong noi alert intraday voi cac phien da chot: o mau + luy ke + streak."""
    if not rows:
        return ""
    vals = [(r["netVal"] or 0) for r in rows]
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


def trend_ctx(sym, db=None):
    """Loi mang/API -> chuoi rong, alert van gui binh thuong.
    VNDirect tra ca ngay hom nay (intraday) -> bo ra, chi giu phien DA CHOT
    (hom nay da co dong 'Ca phien' trong alert roi). Co db thi kem dac tinh
    phien gan nhat tu day_story (tich luy dan tu khi bot chay)."""
    try:
        today = now_vn().date().isoformat()
        rows = [r for r in fetch_foreign_daily(sym, 6) if r["tradingDate"] < today]
        out = _trend_ctx(rows[-5:])
        if db is not None:
            r = db.execute("SELECT net, late_net, room_delta FROM day_story "
                           "WHERE symbol=? AND day<? ORDER BY day DESC LIMIT 1",
                           (sym, today)).fetchone()
            if r:
                out += _story_line(r)
        return out
    except Exception:
        return ""


def accel_msg(sym, deltas):
    icon, side = ("🟢⚡", "GOM") if deltas[-1] > 0 else ("🔴⚡", "XẢ")
    chain = " → ".join(f"{abs(d)/1e9:.1f}" for d in deltas)
    return f"{icon} {sym} — {side} TĂNG TỐC: 3 nhịp liên tiếp {chain} tỷ"


def detect_accel(db, ts, wl):
    """3 nhip poll lien tiep cung chieu, do lon tang dan => dong tien dang tang toc.
    Bao som hon spike (nguong thap hon) vi gia toc moi la tin hieu dan duong."""
    day = ts[:10]
    tss = [r[0] for r in db.execute(
        "SELECT DISTINCT ts FROM snapshots WHERE ts LIKE ? AND ts <= ? ORDER BY ts DESC LIMIT 4",
        (day + "%", ts))][::-1]
    if len(tss) < 4:
        return []
    q = """
    SELECT t3.symbol, t3.day_value, t3.day_value - t2.day_value,
           (t1.buy_val - t1.sell_val) - (t0.buy_val - t0.sell_val),
           (t2.buy_val - t2.sell_val) - (t1.buy_val - t1.sell_val),
           (t3.buy_val - t3.sell_val) - (t2.buy_val - t2.sell_val),
           t3.buy_val - t3.sell_val, t3.price, t3.pct
    FROM snapshots t3
    JOIN snapshots t2 USING (symbol) JOIN snapshots t1 USING (symbol) JOIN snapshots t0 USING (symbol)
    WHERE t3.ts=? AND t2.ts=? AND t1.ts=? AND t0.ts=?
    """
    cooldown = (datetime.fromisoformat(ts) - timedelta(minutes=COOLDOWN_MINUTES)).isoformat(timespec="seconds")
    alerts, msgs = [], []
    for sym, day_value, win3, d1, d2, d3, day_net, price, pct in db.execute(q, (tss[3], tss[2], tss[1], tss[0])):
        f = WL_FACTOR if sym in wl else 1.0
        same_sign = (d1 > 0 and d2 > 0 and d3 > 0) or (d1 < 0 and d2 < 0 and d3 < 0)
        if day_value < MIN_DAY_VALUE * f or not same_sign or abs(d3) < ACCEL_MIN_LAST * f:
            continue
        if not (abs(d1) < abs(d2) < abs(d3)):
            continue
        if win3 <= 0 or abs(d3) / win3 < ACCEL_MIN_SHARE:
            continue  # ma to: tang toc nhung chim trong GTGD -> nhieu, bo qua
        direction = "ABUY" if d3 > 0 else "ASELL"
        if db.execute("SELECT 1 FROM alerts WHERE symbol=? AND direction=? AND ts>?",
                      (sym, direction, cooldown)).fetchone():
            continue
        alerts.append((ts, sym, direction, d3, 0, 0))
        msgs.append(accel_msg(sym, (d1, d2, d3)) + "\n"
                    + ctx_line(day_net, price or 0, pct or 0) + trend_ctx(sym, db))
    db.executemany("INSERT INTO alerts (ts,symbol,direction,net_10m,share,price) VALUES (?,?,?,?,?,?)", alerts)
    db.commit()
    return msgs


def build_day_story(db, day):
    """Chot dac tinh phien vao day_story — goi 1 lan luc tong ket 15:10."""
    span = db.execute("SELECT MIN(ts), MAX(ts) FROM snapshots WHERE ts LIKE ?", (day + "%",)).fetchone()
    first, last = span
    if not first:
        return
    cut = db.execute("SELECT MAX(ts) FROM snapshots WHERE ts LIKE ? AND ts <= ?",
                     (day + "%", day + "T14:15:00")).fetchone()[0] or first
    db.execute("""
        INSERT OR REPLACE INTO day_story
        SELECT ?, l.symbol, l.buy_val - l.sell_val,
               (l.buy_val - l.sell_val) - (c.buy_val - c.sell_val),
               l.room - f.room
        FROM snapshots l
        JOIN snapshots c ON c.symbol = l.symbol AND c.ts = ?
        JOIN snapshots f ON f.symbol = l.symbol AND f.ts = ?
        WHERE l.ts = ?""", (day, cut, first, last))
    db.commit()


def _story_line(row):
    """(net, late_net, room_delta) cua phien gan nhat -> ghi chu neu dang noi."""
    net, late, room_d = row
    bits = []
    if abs(net) >= 10e9 and late * net > 0 and abs(late) >= 0.4 * abs(net):
        bits.append(f"{'gom' if net > 0 else 'xả'} dồn 30' cuối ({late/1e9:+,.0f}/{net/1e9:+,.0f} tỷ)")
    if abs(room_d) >= 500_000:  # ponytail: nguong tho, chinh khi thay keu nhieu/it qua
        bits.append(f"room {'+' if room_d > 0 else '-'}{abs(room_d)/1e6:.1f}tr cp")
    return "\nHôm qua: " + " · ".join(bits) if bits else ""


def ctx_line(day_net, price, pct):
    """Dong 2 cua khung 3 tang — boi canh phien, DUNG CHUNG cho moi loai alert."""
    return (f"Cả phiên: {'mua' if day_net >= 0 else 'bán'} ròng {abs(day_net)/1e9:.1f} tỷ "
            f"| Giá {price:,.0f} ({pct:+.1f}% hôm nay)")


def spike_msg(sym, net, share, price, pct, day_net):
    icon, side = ("🟢", "mua ròng") if net > 0 else ("🔴", "bán ròng")
    note = "\n⚠️ KN chiếm gần trọn giao dịch nhịp này — khả năng lệnh thỏa thuận" if share > 0.8 else ""
    return (f"{icon} {sym} — Khối ngoại {side} {abs(net)/1e9:.1f} tỷ trong {WINDOW_MINUTES} phút qua "
            f"(chiếm {share:.0%} giao dịch của mã){note}\n" + ctx_line(day_net, price, pct))


def detect_states(db, ts, wl):
    """Stateful layer: report only regime TRANSITIONS (gom/xa bat dau hoac chung lai)."""
    prev_ts = prev_snapshot_ts(db, ts, STALL_MINUTES)
    if not prev_ts:
        return []
    day = ts[:10]
    q = """
    SELECT a.symbol,
           a.buy_val - a.sell_val AS day_net,
           (a.buy_val - a.sell_val) - (b.buy_val - b.sell_val) AS recent,
           a.day_value, a.price, a.pct
    FROM snapshots a JOIN snapshots b USING (symbol)
    WHERE a.ts = ? AND b.ts = ?
    """
    msgs = []
    for sym, day_net, recent, day_value, price, pct in db.execute(q, (ts, prev_ts)).fetchall():
        in_wl = sym in wl
        f = WL_FACTOR if in_wl else 1.0
        if not in_wl and day_value < MIN_DAY_VALUE:
            continue
        if day_net >= DAY_NET_TH * f:
            regime = "GOM" if recent > RATE_TH * f else "GOM_CHUNG"
        elif day_net <= -DAY_NET_TH * f:
            regime = "XA" if recent < -RATE_TH * f else "XA_CHUNG"
        else:
            regime = "NEUTRAL"
        row = db.execute("SELECT regime FROM state WHERE symbol=? AND day=?", (sym, day)).fetchone()
        old = row[0] if row else "NEUTRAL"
        if regime == old:
            continue
        db.execute("INSERT OR REPLACE INTO state VALUES (?,?,?)", (sym, regime, day))
        if regime != "NEUTRAL":
            msgs.append(STATE_MSG[regime].format(s=sym, r=recent / 1e9) + "\n"
                        + ctx_line(day_net, price or 0, pct or 0) + trend_ctx(sym, db))
    db.commit()
    return msgs


def fetch_foreign_daily(code, n=10):
    """Daily foreign net flow history from VNDirect (code or VNINDEX for whole HOSE)."""
    url = (f"https://api-finfo.vndirect.com.vn/v4/foreigns"
           f"?q=code:{code}&size={n}&sort=tradingDate:desc")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return list(reversed(json.load(r)["data"]))  # oldest -> newest


def format_trend(label, rows):
    if not rows:
        return f"Không có dữ liệu khối ngoại cho {label}."
    nets = [r["netVal"] or 0 for r in rows]
    bars = "".join("🟩" if v > 0 else "🟥" if v < 0 else "⬜" for v in nets)
    cum, buys = sum(nets), sum(v > 0 for v in nets)
    last3 = nets[-3:]
    a3 = sum(last3) / len(last3)
    rest = nets[:-3] or [0]
    a_rest = sum(rest) / len(rest)
    if cum != 0 and a3 * cum < 0:
        momo = "3 phiên gần nhất ĐẢO CHIỀU so với xu hướng"
    elif abs(a3) > 1.5 * abs(a_rest):
        momo = "đà đang MẠNH dần"
    elif abs(a3) < 0.5 * abs(a_rest):
        momo = "đà đang YẾU dần"
    else:
        momo = "đà ổn định"
    side = "MUA ròng" if cum > 0 else "BÁN ròng"
    streak = 1
    for v in reversed(nets[:-1]):
        if v * nets[-1] > 0:
            streak += 1
        else:
            break
    streak_side = "mua" if nets[-1] > 0 else "bán"
    flipped = len(nets) > 1 and nets[-1] * nets[-2] < 0
    flip = "\n🔄 VỪA ĐẢO CHIỀU phiên nay!" if flipped else ""
    verb = "gom hàng" if nets[-1] > 0 else "rút vốn"
    if flipped:
        read = (f"khối ngoại vừa quay sang {streak_side} ròng sau chuỗi "
                f"{'bán' if nets[-2] < 0 else 'mua'} — cần 1-2 phiên nữa để xác nhận đảo chiều thật")
    elif streak >= 5:
        read = f"khối ngoại {verb} bền bỉ — chuỗi {streak} phiên chưa đứt, lực chưa có dấu hiệu dừng"
    elif "MẠNH" in momo:
        read = f"dòng tiền {streak_side} ròng đang tăng tốc"
    elif "YẾU" in momo:
        read = f"vẫn {streak_side} ròng nhưng lực đang hạ nhiệt"
    else:
        read = f"xu hướng {streak_side} ròng, cường độ bình thường"
    return (f"📈 Khối ngoại {label} — {len(rows)} phiên ({rows[0]['tradingDate'][5:]} → {rows[-1]['tradingDate'][5:]})\n"
            f"{bars}  (cũ → mới)\n"
            f"Xu hướng: {side} lũy kế {cum/1e9:+,.0f} tỷ | {buys}/{len(rows)} phiên mua ròng\n"
            f"Chuỗi hiện tại: {streak} phiên {streak_side} ròng liên tiếp{flip}\n"
            f"3 phiên gần nhất: {sum(last3)/1e9:+,.0f} tỷ — {momo}\n"
            f"Phiên mới nhất ({rows[-1]['tradingDate']}): {nets[-1]/1e9:+,.0f} tỷ\n"
            f"💡 Đọc nhanh: {read}")


def top_movers(db):
    ts = db.execute("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    if not ts:
        return ""
    rows = db.execute(
        "SELECT symbol, buy_val - sell_val AS dn FROM snapshots WHERE ts=? AND ABS(dn) > 1e9 ORDER BY dn DESC",
        (ts,)).fetchall()
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


def send_to(token, chat_id, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15)


def send_telegram(text):
    """Broadcast alerts to every authorized chat."""
    cfg = load_config()
    if not (cfg.get("token") and cfg.get("chat_ids")):
        return False
    for cid in cfg["chat_ids"]:
        send_to(cfg["token"], cid, text)
    return True


def poll_commands(db, wait=25):
    """Handle commands via long-polling (near-instant replies).
    /id works from any chat; the rest need an authorized chat."""
    cfg = load_config()
    if not (cfg.get("token") and cfg.get("chat_ids")):
        time.sleep(wait)
        return
    offset = int((db.execute("SELECT v FROM meta WHERE k='tg_offset'").fetchone() or [0])[0])
    url = f"https://api.telegram.org/bot{cfg['token']}/getUpdates?offset={offset + 1}&timeout={wait}"
    with urllib.request.urlopen(urllib.request.Request(url), timeout=wait + 10) as r:
        updates = json.load(r)["result"]
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
            send_to(cfg["token"], chat_id, f"Chat id: {chat_id}\n"
                    "Đưa id này cho admin thêm vào telegram.json để bot hoạt động ở đây.")
            continue
        if chat_id not in cfg["chat_ids"]:
            continue
        if cmd == "/WATCH" and arg:
            db.execute("INSERT OR IGNORE INTO watchlist VALUES (?)", (arg,))
            send_to(cfg["token"], chat_id, f"✅ Đã theo dõi {arg} (ngưỡng alert giảm 1 nửa)")
        elif cmd == "/UNWATCH" and arg:
            db.execute("DELETE FROM watchlist WHERE symbol=?", (arg,))
            send_to(cfg["token"], chat_id, f"Đã bỏ theo dõi {arg}")
        elif cmd == "/LIST":
            wl = sorted(get_watchlist(db))
            send_to(cfg["token"], chat_id, "Watchlist: " + (", ".join(wl) if wl else "(trống)"))
        elif cmd == "/TREND":
            try:
                if arg:
                    msg = format_trend(arg, fetch_foreign_daily(arg))
                else:
                    msg = format_trend("toàn HOSE", fetch_foreign_daily("VNINDEX")) + top_movers(db)
            except Exception as e:
                msg = f"Không lấy được dữ liệu xu hướng ({e})"
            send_to(cfg["token"], chat_id, msg)
        elif cmd == "/SCRIPT":
            try:
                msg = make_script(db)
            except Exception as e:
                msg = f"Không tạo được script ({e})"
            send_to(cfg["token"], chat_id, msg)
        elif cmd == "/BRIEF" and arg:
            send_to(cfg["token"], chat_id, f"⏳ Đang tổng hợp brief {arg}, chờ ~30 giây...")
            try:
                from brief import build_brief
                msg = build_brief(arg)
            except Exception as e:
                msg = f"Không tạo được brief cho {arg} ({e})"
            send_to(cfg["token"], chat_id, msg)
        elif cmd in ("/HELP", "/START"):
            send_to(cfg["token"], chat_id, HELP_TEXT)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('tg_offset', ?)", (str(offset),))
    db.commit()


def make_script(db):
    data = format_trend("toàn HOSE", fetch_foreign_daily("VNINDEX")) + top_movers(db)
    ts = db.execute("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    if ts:  # % gia nhom GTGD lon — de script co the ke ve sac xanh/do (canh heatmap)
        heat = db.execute("SELECT symbol, COALESCE(pct, 0) FROM snapshots WHERE ts=? "
                          "ORDER BY day_value DESC LIMIT 8", (ts,)).fetchall()
        data += "\nGiá mã GTGD lớn hôm nay: " + ", ".join(f"{s} {p:+.1f}%" for s, p in heat)
    from brief import call_llm  # lazy — tranh circular import
    text = call_llm(SCRIPT_SYSTEM, f"Dữ liệu phiên hôm nay:\n\n{data}\n\nViết script.").strip()
    return f"🎬 Script TikTok hôm nay:\n\n{text}"[:4000]


def maybe_send_summary(db):
    """After the session closes (15:10+), send the market foreign-flow trend once per day."""
    now = now_vn()
    if now.weekday() >= 5 or now.hour * 60 + now.minute < 15 * 60 + 10:
        return
    today = now.date().isoformat()
    sent = (db.execute("SELECT v FROM meta WHERE k='summary_day'").fetchone() or [None])[0]
    if sent == today:
        return
    if not db.execute("SELECT 1 FROM snapshots WHERE ts LIKE ? LIMIT 1", (today + "%",)).fetchone():
        return  # khong co du lieu hom nay (nghi le) -> khong tong ket
    try:
        build_day_story(db, today)  # chot dac tinh phien de lam giau alert cac ngay sau
        text = "🔔 Tổng kết phiên\n\n" + format_trend("toàn HOSE", fetch_foreign_daily("VNINDEX")) + top_movers(db)
        send_telegram(text)
        db.execute("INSERT OR REPLACE INTO meta VALUES ('summary_day', ?)", (today,))
        db.commit()
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] summary failed: {e}")
        return
    try:
        send_telegram(make_script(db))
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] script failed: {e}")  # script loi khong chan summary


def run_once(db):
    ts, n = poll(db)
    wl = get_watchlist(db)
    msgs = detect_spikes(db, ts, wl) + detect_accel(db, ts, wl) + detect_states(db, ts, wl)
    print(f"[{ts}] snapshot {n} symbols, {len(msgs)} alerts")
    if msgs:
        text = f"📊 Khối ngoại — {ts[11:16]}\n\n" + "\n\n".join(msgs)
        print(text)
        try:
            send_telegram(text)
        except Exception as e:
            print(f"telegram send failed: {e}")
    return msgs


def selftest():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    day = "2026-01-05"

    def snap(hhmm, buy, sell, day_value=100e9):
        db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (f"{day}T{hhmm}:00+07:00", "AAA", buy, sell, 0, 0, 1e6, 20000, day_value, 1.5))
    db.commit()

    # 09:30 -> 10:00: gom deu, day_net 20 ty, recent 10 ty => GOM transition
    snap("09:30", 10e9, 0)
    snap("10:00", 20e9, 0)
    msgs = detect_states(db, f"{day}T10:00:00+07:00", set())
    assert len(msgs) == 1 and "GOM" in msgs[0] and "CHỮNG" not in msgs[0], msgs
    assert "Cả phiên" in msgs[0] and "Giá 20,000" in msgs[0], msgs  # khung 3 tang thong nhat
    # 10:30: khong mua them => GOM_CHUNG (delta thu hep)
    snap("10:30", 20.1e9, 0)
    msgs = detect_states(db, f"{day}T10:30:00+07:00", set())
    assert len(msgs) == 1 and "CHỮNG" in msgs[0], msgs
    # 11:00: van chung => KHONG bao lai (state khong doi)
    snap("11:00", 20.2e9, 0)
    assert detect_states(db, f"{day}T11:00:00+07:00", set()) == [], "no repeat on same state"

    # spike: 10:00 -> 10:10 mua rong 5 ty / window value 20 ty
    snap("10:10", 25.2e9, 0, day_value=120e9)
    msgs = detect_spikes(db, f"{day}T10:10:00+07:00", set())
    assert len(msgs) == 1 and "AAA" in msgs[0] and "mua ròng" in msgs[0] and "Cả phiên" in msgs[0], msgs
    assert "thỏa thuận" not in msgs[0], "26% share must not be flagged as put-through"
    assert detect_spikes(db, f"{day}T10:10:00+07:00", set()) == [], "cooldown must suppress"

    # trend: 7 phien ban rong roi 3 phien mua rong => dao chieu detect o phien thu 8
    rows = [{"tradingDate": f"2026-01-{i+1:02d}", "netVal": v}
            for i, v in enumerate([-5e9] * 7 + [3e9, 4e9, 6e9])]
    msg = format_trend("TEST", rows)
    assert "3 phiên mua ròng liên tiếp" in msg and "🟥" * 7 + "🟩" * 3 in msg, msg
    rows2 = rows[:8]  # phien cuoi vua flip
    assert "ĐẢO CHIỀU" in format_trend("TEST", rows2)

    # _vps_row: field string, gia tri nghin dong x1000 = VND, lot theo lo 10,
    # pct phai co DAU tinh tu tham chieu r (changePc cua VPS khong co dau)
    row = _vps_row({"sym": "ABS", "fBValue": "1000", "fSValue": "2000.5", "fBVol": "10",
                    "fSVolume": "20", "fRoom": "99", "lastPrice": "12.6", "r": "12.8",
                    "lot": "100", "avePrice": "12.7", "changePc": "1.56"})
    assert row == ("ABS", 1000000.0, 2000500.0, 10.0, 20.0, 99.0, 12600.0, 12700000.0, -1.56), row
    assert _vps_row({"sym": "XXX"}) == ("XXX", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # trend context gan vao alert: o vuong + luy ke + streak >=3 moi keu
    ctx = _trend_ctx([{"netVal": v} for v in (-5e9, -7e9, -3e9, -8e9, -9e9)])
    assert "🟥🟥🟥🟥🟥" in ctx and "-32" in ctx and "5 phiên bán ròng liên tiếp" in ctx, ctx
    assert _trend_ctx([]) == ""
    mixed = _trend_ctx([{"netVal": v} for v in (5e9, -2e9, 3e9)])
    assert "🟩🟥🟩" in mixed and "liên tiếp" not in mixed, mixed

    # detect_accel: 3 nhip poll cung chieu, do lon tang dan => TANG TOC
    db2 = sqlite3.connect(":memory:")
    db2.executescript(SCHEMA)
    dvs = {"10:00": 100e9, "10:05": 110e9, "10:10": 120e9, "10:15": 140e9}   # win cuoi 20 ty -> share 25%
    big = {"10:00": 100e9, "10:05": 300e9, "10:10": 600e9, "10:15": 1000e9}  # win cuoi 400 ty -> share ~1%
    for hhmm, bbb, ccc in (("10:00", 1e9, 1e9), ("10:05", 2.2e9, 6e9),
                           ("10:10", 4.9e9, 8e9), ("10:15", 9.9e9, 9e9)):
        # CCC giam toc -> khong bao; EEE tang toc nhung chim trong GTGD lon -> khong bao
        for sym, buy, dv in (("BBB", bbb, dvs[hhmm]), ("CCC", ccc, dvs[hhmm]), ("EEE", bbb, big[hhmm])):
            db2.execute("INSERT INTO snapshots VALUES (?,?,?,0,0,0,1e6,20000,?,1.0)",
                        (f"{day}T{hhmm}:00+07:00", sym, buy, dv))
    db2.commit()
    msgs = detect_accel(db2, f"{day}T10:15:00+07:00", set())
    assert len(msgs) == 1 and "BBB" in msgs[0] and "TĂNG TỐC" in msgs[0], msgs
    assert "Cả phiên" in msgs[0] and "Giá 20,000" in msgs[0], msgs  # khung 3 tang thong nhat
    assert "1.2 → 2.7 → 5.0" in msgs[0], msgs
    assert detect_accel(db2, f"{day}T10:15:00+07:00", set()) == [], "cooldown accel"

    # day_story: net cuoi phien, net 30' cuoi (tu 14:15), thay doi room
    db3 = sqlite3.connect(":memory:")
    db3.executescript(SCHEMA)
    for hhmm, buy, room in (("09:30", 2e9, 100), ("14:00", 4e9, 90), ("14:30", 9e9, 80)):
        db3.execute("INSERT INTO snapshots VALUES (?,?,?,0,0,0,?,20000,50e9,0)",
                    (f"{day}T{hhmm}:00+07:00", "DDD", buy, room))
    db3.commit()
    build_day_story(db3, day)
    assert db3.execute("SELECT net, late_net, room_delta FROM day_story").fetchone() == (9e9, 5e9, -20)

    # _story_line: chi len tieng khi co gi dang noi
    assert "xả dồn 30' cuối" in _story_line((-100e9, -45e9, 0))
    assert _story_line((5e9, 1e9, 0)) == ""
    assert "room -1.2tr" in _story_line((20e9, 1e9, -1_200_000))
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    try:
        db.execute("ALTER TABLE snapshots ADD COLUMN pct REAL")  # migrate pre-pct DBs
    except sqlite3.OperationalError:
        pass
    if "--once" in sys.argv:
        run_once(db)
        return
    print(f"Collector started. Market poll every {POLL_MINUTES}', commands via long-poll. DB: {DB}")
    last_poll = 0.0
    while True:
        try:
            poll_commands(db)  # blocks up to ~25s, returns instantly when a command arrives
        except Exception as e:
            print(f"[{now_vn().isoformat(timespec='seconds')}] commands failed: {e}")
            time.sleep(10)
        if in_trading_hours(now_vn()) and time.time() - last_poll >= POLL_MINUTES * 60:
            try:
                run_once(db)
            except Exception as e:
                print(f"[{now_vn().isoformat(timespec='seconds')}] poll failed: {e}")
            last_poll = time.time()
        maybe_send_summary(db)


if __name__ == "__main__":
    main()
