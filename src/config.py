"""Cau hinh + hang so nguong + tien ich thoi gian. Tang duy nhat doc env/file."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # repo root — flows.db/telegram.json/.env o day

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
MOVERS_MIN_NET = 1e9       # top movers: |net rong ngay| > 1 ty moi vao bang
LATE_SESSION_START = "14:15:00"  # day_story: late_net = net tu moc nay ("30' cuoi phien")
STORY_MIN_NET = 10e9       # story_line: |net ca phien| >= 10 ty moi dang noi
STORY_LATE_SHARE = 0.4     # story_line: 30' cuoi chiem >= 40% net ca phien -> "don cuoi phien"
STORY_ROOM_MIN = 500_000   # story_line: |room delta| >= 0.5tr cp moi nhac  # ponytail: nguong tho, chinh khi thay keu nhieu/it qua
FUND_CONFLUENCE_MIN = 10    # alert kem chuong: gom + >= 10 quy mo dang nam -> tin hieu hop luu (loud)
DB = Path(os.environ.get("DB_PATH", str(ROOT / "flows.db")))
CONFIG = ROOT / "telegram.json"  # {"token": ..., "chat_id": ...} — keep private
VN_TZ = timezone(timedelta(hours=7))


def now_vn():
    return datetime.now(VN_TZ)


def in_trading_hours(dt):
    if dt.weekday() >= 5:
        return False
    hm = dt.hour * 60 + dt.minute
    if 11 * 60 + 30 <= hm < 13 * 60:    # nghi trua HOSE: khong khop lenh -> poll chi de ra tin hieu gia
        return False
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


def load_env():
    """Nap .env vao os.environ (local dev; tren Railway dung Variables)."""
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
