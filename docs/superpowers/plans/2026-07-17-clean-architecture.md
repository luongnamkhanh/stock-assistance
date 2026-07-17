# Clean Architecture Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure stock-assistance (collector.py 809 dòng + brief.py 183 dòng) thành package `src/` theo clean architecture (domain / usecases / adapters / infrastructure + main.py wiring), behavior giữ nguyên 100%.

**Architecture:** Dependency rule một chiều: `domain` không import gì nội bộ; `adapters` (ports ABC + presenters thuần text) chỉ import domain; `usecases` import domain + ports + presenters; `infrastructure` implement ports; `src/main.py` wire tất cả. video.py / backtest.py / variants.py giữ ở root làm entry scripts (chỉ đổi import). **Deviation có chủ đích (ghi lại 1 lần ở đây):** usecases được gọi thẳng presenters vì presenters là pure function không IO — không tạo presenter-port ABC.

**Tech Stack:** Python 3.9+ stdlib only cho core (sqlite3, urllib, dataclasses, abc). `anthropic` vẫn lazy-import. KHÔNG thêm dependency mới. Test = assert-based module (pattern sẵn có của repo), không pytest.

## Global Constraints

- Behavior freeze: mọi message Telegram phải **byte-identical** với bản hiện tại. Mọi assert trong `collector.py:selftest()` (dòng 681-775) và `video.py:selftest()` (dòng 578-638) phải pass sau khi port.
- `DB_PATH` default phải trỏ về **repo root**: trong `src/config.py` dùng `Path(__file__).resolve().parent.parent / "flows.db"` (không phải `parent` — file nằm sâu 1 cấp). Tương tự `telegram.json` và `.env`.
- Entry points sau refactor: `python3 -m src.main [--selftest|--once]` (thay `python3 collector.py ...`); `python3 video.py [...]` CLI **không đổi** (daily-video skill phụ thuộc CLI này).
- Procfile, deploy/setup.sh, deploy/stock-bot.service phải được update trong plan (Task 10).
- Chạy test bằng: `.venv/bin/python -m tests.run_all` (hoặc `python3` nếu venv không có — core là stdlib).
- Git commit: KHÔNG có AI attribution (không Co-Authored-By, không "Generated with").
- Mỗi task kết thúc bằng commit. Không refactor "tiện tay" ngoài scope task.
- `collector.py` và `brief.py` chỉ bị XÓA ở Task 10 (sau khi mọi consumer đã trỏ sang src/) — trước đó code cũ và mới song song, không sửa file cũ.

## Function → Module Map (toàn cục, tra cứu khi làm bất kỳ task nào)

| Hiện tại | Đích |
|---|---|
| collector.py hằng số dòng 42-59, `now_vn`, `in_trading_hours`, `load_config`; brief.py `load_env` | `src/config.py` |
| collector.py `SCHEMA` (61-86) + mọi `db.execute` | `src/infrastructure/sqlite_repo.py` |
| `_f`, `_vps_row`, `_vps_get`, `fetch_vps` (161-201) | `src/infrastructure/vps_api.py` |
| iBoard fetch trong `poll()` (206-217) | `src/infrastructure/hose_feed.py` |
| `fetch_foreign_daily`, `fetch_price_line` (phần HTTP) (435-460); brief.py `_get`, `fetch_fundamentals`, `fetch_prices`, `RATIO_LABELS` | `src/infrastructure/vndirect_api.py` |
| brief.py `fetch_news` (101-110) | `src/infrastructure/news_api.py` |
| brief.py `_call_gemini`, `_call_claude`, `call_llm` (126-171) | `src/infrastructure/llm.py` |
| `send_to`, `send_telegram`, phần getUpdates của `poll_commands` (534-562) | `src/infrastructure/telegram.py` |
| Rule thuần trong `detect_spikes`/`detect_states`/`detect_accel`, phần phân tích của `format_trend` | `src/domain/signals.py` |
| Dataclass mới: `DayFlow`, `TrendStats`, `Spike`, `Accel`, `RegimeChange` | `src/domain/entities.py` |
| Port ABC: `SnapshotRepo` | `src/adapters/repositories.py` |
| Port ABC: `MarketFeed`, `FlowHistory`, `LLM`, `Telegram` | `src/adapters/gateways.py` |
| `format_trend`, `spike_msg`, `accel_msg`, `ctx_line`, `_story_line`, `_trend_ctx`, `top_movers` (format), `price_line` (format), `HELP_TEXT`, `STATE_MSG` | `src/adapters/presenters.py` |
| `poll` (ghi DB) | `src/usecases/poll_market.py` |
| `detect_spikes`, `detect_states`, `detect_accel`, `run_once` | `src/usecases/detect_alerts.py` |
| `trend_ctx`, message /trend | `src/usecases/build_trend.py` |
| `build_day_story` | `src/usecases/day_story.py` |
| `make_script`, `SCRIPT_SYSTEM` | `src/usecases/make_script.py` |
| `maybe_send_summary` | `src/usecases/summary.py` |
| brief.py `gather`, `build_brief`, `SYSTEM` | `src/usecases/build_brief.py` |
| `poll_commands` (routing lệnh) | `src/adapters/bot.py` |
| `main` | `src/main.py` |

---

### Task 1: Skeleton + baseline xanh

**Files:**
- Create: `src/__init__.py`, `src/domain/__init__.py`, `src/usecases/__init__.py`, `src/adapters/__init__.py`, `src/infrastructure/__init__.py`, `tests/__init__.py`, `tests/run_all.py`

**Interfaces:**
- Produces: package importable `src.*`; `tests/run_all.py` chạy được (rỗng cũng in OK).

- [ ] **Step 1: Chạy baseline để chốt trạng thái xanh trước khi đụng gì**

Run: `python3 collector.py --selftest && python3 video.py --selftest`
Expected: 2 dòng `selftest OK`

- [ ] **Step 2: Tạo cây thư mục**

```bash
mkdir -p src/domain src/usecases src/adapters src/infrastructure tests
touch src/__init__.py src/domain/__init__.py src/usecases/__init__.py \
      src/adapters/__init__.py src/infrastructure/__init__.py tests/__init__.py
```

- [ ] **Step 3: Viết `tests/run_all.py` (aggregator, sẽ nạp dần từng task)**

```python
"""Chay toan bo test module. Moi task them 1 dong import + goi run()."""
MODULES = []  # cac task sau append: ("tests.test_config", ...)

def main():
    import importlib
    for name in MODULES:
        importlib.import_module(name).run()
    print("ALL TESTS OK")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify**

Run: `python3 -m tests.run_all`
Expected: `ALL TESTS OK`

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "cau truc src/ + tests/ cho clean arch (skeleton, chua co code)"
```

---

### Task 2: src/config.py — hằng số, giờ giao dịch, config

**Files:**
- Create: `src/config.py`, `tests/test_config.py`
- Modify: `tests/run_all.py` (thêm module)

**Interfaces:**
- Produces: mọi hằng số cấu hình `POLL_MINUTES, WINDOW_MINUTES, MIN_DAY_VALUE, ALERT_MIN_NET, ALERT_MIN_SHARE, COOLDOWN_MINUTES, DAY_NET_TH, STALL_MINUTES, RATE_TH, WL_FACTOR, ACCEL_MIN_LAST, ACCEL_MIN_SHARE, DB, VN_TZ`; hàm `now_vn() -> datetime`, `in_trading_hours(dt) -> bool`, `load_config() -> dict`, `load_env() -> None`.

- [ ] **Step 1: Viết test `tests/test_config.py`**

```python
from datetime import datetime
from src.config import DB, in_trading_hours, load_config, VN_TZ

def run():
    # bien gio giao dich: 08:59 out, 09:00 in, 15:05 in, 15:06 out, T7 out
    assert not in_trading_hours(datetime(2026, 1, 5, 8, 59, tzinfo=VN_TZ))
    assert in_trading_hours(datetime(2026, 1, 5, 9, 0, tzinfo=VN_TZ))
    assert in_trading_hours(datetime(2026, 1, 5, 15, 5, tzinfo=VN_TZ))
    assert not in_trading_hours(datetime(2026, 1, 5, 15, 6, tzinfo=VN_TZ))
    assert not in_trading_hours(datetime(2026, 1, 10, 10, 0, tzinfo=VN_TZ))  # Saturday
    # DB default phai o repo root (canh flows.db hien tai), khong nam trong src/
    assert DB.parent.name != "src", DB
    # load_config doc env var truoc file
    import os
    os.environ["TELEGRAM_TOKEN"] = "t"
    os.environ["TELEGRAM_CHAT_IDS"] = "1, 2"
    try:
        assert load_config() == {"token": "t", "chat_ids": [1, 2]}
    finally:
        del os.environ["TELEGRAM_TOKEN"], os.environ["TELEGRAM_CHAT_IDS"]
    print("test_config OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `python3 -m tests.test_config`
Expected: FAIL `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Viết `src/config.py`**

Nội dung = MOVE verbatim từ collector.py:42-59 (hằng số, DB, CONFIG, VN_TZ, API, HEADERS) + collector.py:137-158 (`now_vn`, `in_trading_hours`, `load_config`) + brief.py:19-27 (`load_env`), với đúng 2 sửa đổi:

```python
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
DB = Path(os.environ.get("DB_PATH", str(ROOT / "flows.db")))
CONFIG = ROOT / "telegram.json"  # {"token": ..., "chat_id": ...} — keep private
VN_TZ = timezone(timedelta(hours=7))


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


def load_env():
    """Nap .env vao os.environ (local dev; tren Railway dung Variables)."""
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
```

- [ ] **Step 4: Nối vào aggregator — sửa `tests/run_all.py`: `MODULES = ["tests.test_config"]`**

- [ ] **Step 5: Verify**

Run: `python3 -m tests.run_all`
Expected: `test_config OK` rồi `ALL TESTS OK`

- [ ] **Step 6: Commit**

```bash
git add src/config.py tests
git commit -m "src/config.py: hang so + gio giao dich + load_config/load_env"
```

---

### Task 3: domain — entities + signals (rule thuần, 0 IO)

**Files:**
- Create: `src/domain/entities.py`, `src/domain/signals.py`, `tests/test_domain.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Consumes: hằng số từ `src.config` — **KHÔNG import**; các hàm nhận `wl_factor: float` làm tham số để domain không phụ thuộc config.
- Produces (chữ ký chính xác, task sau dùng đúng tên này):
  - `entities.DayFlow(trading_date: str, net_val: float)` frozen dataclass
  - `entities.TrendStats(cum, buys, last3: tuple, momo: str, streak: int, streak_side: str, flipped: bool)` — `momo ∈ {"DAO_CHIEU","MANH","YEU","ON_DINH"}`, `streak_side ∈ {"mua","bán"}`
  - `entities.Spike(symbol, net, share, price, pct, day_net)`
  - `entities.Accel(symbol, deltas: tuple, day_net, price, pct)`
  - `entities.RegimeChange(symbol, regime, recent, day_net, price, pct)`
  - `signals.classify_regime(day_net, recent, factor, day_net_th, rate_th) -> str` — trả `"GOM"|"GOM_CHUNG"|"XA"|"XA_CHUNG"|"NEUTRAL"` (logic = collector.py:417-422)
  - `signals.spike_share(net, win_value, day_value, factor, min_day_value, min_net, min_share) -> float | None` — share nếu là spike, None nếu không (logic = collector.py:250-254)
  - `signals.is_accel(d1, d2, d3, win3, day_value, factor, min_day_value, min_last, min_share) -> bool` (logic = collector.py:334-340)
  - `signals.trend_stats(nets: "list[float]") -> TrendStats` (logic = collector.py:466-491, momo trả mã thay vì câu tiếng Việt)

- [ ] **Step 1: Viết test `tests/test_domain.py`**

```python
from src.domain.entities import TrendStats
from src.domain.signals import classify_regime, is_accel, spike_share, trend_stats

TH = dict(day_net_th=15e9, rate_th=1e9)

def run():
    # regime (tu selftest detect_states cu): gom deu -> GOM; delta thu hep -> GOM_CHUNG
    assert classify_regime(20e9, 10e9, 1.0, **TH) == "GOM"
    assert classify_regime(20.1e9, 0.1e9, 1.0, **TH) == "GOM_CHUNG"
    assert classify_regime(-20e9, -10e9, 1.0, **TH) == "XA"
    assert classify_regime(-20e9, -0.5e9, 1.0, **TH) == "XA_CHUNG"
    assert classify_regime(5e9, 5e9, 1.0, **TH) == "NEUTRAL"
    assert classify_regime(8e9, 5e9, 0.5, **TH) == "GOM"      # watchlist: nguong /2

    # spike (tu selftest cu): 5 ty / win 20 ty = share 25% -> spike
    SP = dict(min_day_value=30e9, min_net=3e9, min_share=0.15)
    assert abs(spike_share(5e9, 20e9, 120e9, 1.0, **SP) - 0.25) < 1e-9
    assert spike_share(2e9, 20e9, 120e9, 1.0, **SP) is None    # net < 3 ty
    assert spike_share(5e9, 40e9, 120e9, 1.0, **SP) is None    # share < 15%
    assert spike_share(5e9, 20e9, 20e9, 1.0, **SP) is None     # GTGD ngay < 30 ty
    assert spike_share(5e9, 0, 120e9, 1.0, **SP) is None       # win_value <= 0

    # accel (tu selftest cu): 1.2 -> 2.7 -> 5.0 tang dan, share 25% -> True
    AC = dict(min_day_value=30e9, min_last=1.5e9, min_share=0.10)
    assert is_accel(1.2e9, 2.7e9, 5e9, 20e9, 140e9, 1.0, **AC)
    assert not is_accel(5e9, 2.9e9, 0.9e9, 20e9, 140e9, 1.0, **AC)   # giam toc
    assert not is_accel(1.2e9, 2.7e9, 5e9, 400e9, 1000e9, 1.0, **AC) # chim trong GTGD
    assert not is_accel(1.2e9, -2.7e9, 5e9, 20e9, 140e9, 1.0, **AC)  # khac dau

    # trend_stats: 7 ban + 3 mua -> DAO_CHIEU that; outlier 1 phien -> KHONG dao chieu
    t = trend_stats([-5e9] * 7 + [3e9, 4e9, 6e9])
    assert isinstance(t, TrendStats)
    assert t.momo == "DAO_CHIEU" and t.streak == 3 and t.streak_side == "mua"
    t2 = trend_stats([-50e9] * 7 + [139e9, -13e9, -4e9])       # case HPG 07/2026
    assert t2.momo != "DAO_CHIEU" and t2.streak == 2 and t2.streak_side == "bán"
    t3 = trend_stats([-5e9] * 7 + [3e9])
    assert t3.flipped                                           # vua flip phien cuoi
    print("test_domain OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Chạy để thấy fail** — Run: `python3 -m tests.test_domain` → `ModuleNotFoundError`

- [ ] **Step 3: Viết `src/domain/entities.py`**

```python
"""Data object di qua ranh gioi layer. Frozen — domain khong co state."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DayFlow:                # 1 phien khoi ngoai da chot (tu VNDirect)
    trading_date: str         # "2026-07-17"
    net_val: float            # VND, co the am


@dataclass(frozen=True)
class TrendStats:             # phan tich chuoi phien — SO, khong text
    cum: float
    buys: int
    last3: tuple
    momo: str                 # DAO_CHIEU | MANH | YEU | ON_DINH
    streak: int
    streak_side: str          # "mua" | "bán"
    flipped: bool


@dataclass(frozen=True)
class Spike:
    symbol: str
    net: float
    share: float
    price: float
    pct: float
    day_net: float


@dataclass(frozen=True)
class Accel:
    symbol: str
    deltas: tuple             # (d1, d2, d3)
    day_net: float
    price: float
    pct: float


@dataclass(frozen=True)
class RegimeChange:
    symbol: str
    regime: str               # GOM | GOM_CHUNG | XA | XA_CHUNG
    recent: float
    day_net: float
    price: float
    pct: float
```

- [ ] **Step 4: Viết `src/domain/signals.py`**

```python
"""Rule thuan: nhan so, tra quyet dinh. Khong IO, khong import config."""
import statistics

from .entities import TrendStats


def classify_regime(day_net, recent, factor, day_net_th, rate_th):
    if day_net >= day_net_th * factor:
        return "GOM" if recent > rate_th * factor else "GOM_CHUNG"
    if day_net <= -day_net_th * factor:
        return "XA" if recent < -rate_th * factor else "XA_CHUNG"
    return "NEUTRAL"


def spike_share(net, win_value, day_value, factor, min_day_value, min_net, min_share):
    if day_value < min_day_value * factor or abs(net) < min_net * factor or win_value <= 0:
        return None
    share = abs(net) / win_value
    return share if share >= min_share else None


def is_accel(d1, d2, d3, win3, day_value, factor, min_day_value, min_last, min_share):
    same_sign = (d1 > 0 and d2 > 0 and d3 > 0) or (d1 < 0 and d2 < 0 and d3 < 0)
    if day_value < min_day_value * factor or not same_sign or abs(d3) < min_last * factor:
        return False
    if not (abs(d1) < abs(d2) < abs(d3)):
        return False
    return win3 > 0 and abs(d3) / win3 >= min_share


def trend_stats(nets):
    cum, buys = sum(nets), sum(v > 0 for v in nets)
    last3 = tuple(nets[-3:])
    a3 = sum(last3) / len(last3)
    rest = nets[:-3] or [0]
    a_rest = sum(rest) / len(rest)
    # median: 1 phien dot bien (thoa thuan) khong duoc phep tu minh tao nhan dao chieu
    if cum != 0 and statistics.median(last3) * cum < 0:
        momo = "DAO_CHIEU"
    elif abs(a3) > 1.5 * abs(a_rest):
        momo = "MANH"
    elif abs(a3) < 0.5 * abs(a_rest):
        momo = "YEU"
    else:
        momo = "ON_DINH"
    streak = 1
    for v in reversed(nets[:-1]):
        if v * nets[-1] > 0:
            streak += 1
        else:
            break
    streak_side = "mua" if nets[-1] > 0 else "bán"
    flipped = len(nets) > 1 and nets[-1] * nets[-2] < 0
    return TrendStats(cum=cum, buys=buys, last3=last3, momo=momo,
                      streak=streak, streak_side=streak_side, flipped=flipped)
```

- [ ] **Step 5: Verify** — Run: `python3 -m tests.test_domain` → `test_domain OK`. Thêm `"tests.test_domain"` vào `MODULES`, chạy `python3 -m tests.run_all` → `ALL TESTS OK`.

- [ ] **Step 6: Commit** — `git add src/domain tests && git commit -m "domain: entities + signals thuan (regime/spike/accel/trend)"`

---

### Task 4: Port SnapshotRepo + infrastructure/sqlite_repo.py

**Files:**
- Create: `src/adapters/repositories.py`, `src/infrastructure/sqlite_repo.py`, `tests/test_repo.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Produces (mọi task sau gọi đúng các method này):

```python
class SnapshotRepo(ABC):
    def insert_snapshots(self, ts, rows): ...          # rows: list[tuple 9 cot nhu _vps_row]
    def max_ts(self): ...                              # -> str | None
    def prev_snapshot_ts(self, ts, minutes): ...       # -> str | None
    def snapshot_times(self, day, until_ts, n): ...    # -> list[str] tang dan, n moc cuoi
    def spike_rows(self, ts, prev_ts): ...             # -> [(sym, net, win_value, day_value, price, pct, day_net)]
    def state_rows(self, ts, prev_ts): ...             # -> [(sym, day_net, recent, day_value, price, pct)]
    def accel_rows(self, t0, t1, t2, t3): ...          # -> [(sym, day_value, win3, d1, d2, d3, day_net, price, pct)]
    def recent_alert(self, symbol, direction, cutoff): ...  # -> bool
    def add_alerts(self, rows): ...                    # rows: [(ts, sym, direction, net, share, price)]
    def get_regime(self, symbol, day): ...             # -> str ("NEUTRAL" neu chua co)
    def set_regime(self, symbol, regime, day): ...
    def watchlist(self): ...                           # -> set[str]
    def watch(self, symbol): ...
    def unwatch(self, symbol): ...
    def save_day_story(self, day): ...                 # SQL aggregation (collector.py:353-370)
    def last_story(self, symbol, before_day): ...      # -> (net, late_net, room_delta) | None
    def top_net(self, ts): ...                         # -> [(sym, day_net)] DESC, |net|>1 ty
    def heat(self, ts, n): ...                         # -> [(sym, pct)] theo day_value DESC
    def has_snapshots(self, day): ...                  # -> bool
    def get_meta(self, k, default=None): ...
    def set_meta(self, k, v): ...
```

- `SqliteRepo(path_or_conn)` — nhận `":memory:"`, `Path`, hoặc `sqlite3.Connection`; tự `executescript(SCHEMA)` + migrate cột `pct` (collector.py:785-787). `SCHEMA` MOVE verbatim từ collector.py:61-86. Mỗi method wrap đúng câu SQL đang nằm rải trong collector.py (spike_rows = query dòng 239-247, state_rows = 403-410, accel_rows = 320-329, save_day_story = 355-370, top_net = 519-521, heat = 628-629...). Method ghi tự `commit()`.

- [ ] **Step 1: Viết test `tests/test_repo.py`** — dựng data giống selftest cũ, exercise từng method:

```python
from src.infrastructure.sqlite_repo import SqliteRepo

def snap(repo, ts, sym, buy, sell=0, day_value=100e9, price=20000, pct=1.5, room=0):
    repo.insert_snapshots(ts, [(sym, buy, sell, 0, 0, room, price, day_value, pct)])

def run():
    r = SqliteRepo(":memory:")
    day = "2026-01-05"
    snap(r, f"{day}T09:30:00+07:00", "AAA", 10e9)
    snap(r, f"{day}T10:00:00+07:00", "AAA", 20e9)
    assert r.max_ts() == f"{day}T10:00:00+07:00"
    assert r.prev_snapshot_ts(f"{day}T10:00:00+07:00", 30) == f"{day}T09:30:00+07:00"
    # semantics goc: "snapshot gan nhat CU >= n phut" — cutoff 09:55 -> MAX(ts) <= cutoff la 09:30
    assert r.prev_snapshot_ts(f"{day}T10:00:00+07:00", 5) == f"{day}T09:30:00+07:00"
    rows = r.state_rows(f"{day}T10:00:00+07:00", f"{day}T09:30:00+07:00")
    assert rows == [("AAA", 20e9, 10e9, 100e9, 20000, 1.5)], rows
    sp = r.spike_rows(f"{day}T10:00:00+07:00", f"{day}T09:30:00+07:00")
    assert sp[0][0] == "AAA" and sp[0][1] == 10e9            # net cua cua so
    # regime state
    assert r.get_regime("AAA", day) == "NEUTRAL"
    r.set_regime("AAA", "GOM", day)
    assert r.get_regime("AAA", day) == "GOM"
    # alerts + cooldown
    assert not r.recent_alert("AAA", "BUY", f"{day}T09:00:00+07:00")
    r.add_alerts([(f"{day}T10:00:00+07:00", "AAA", "BUY", 5e9, 0.2, 20000)])
    assert r.recent_alert("AAA", "BUY", f"{day}T09:00:00+07:00")
    # watchlist
    r.watch("HPG"); r.watch("HPG"); assert r.watchlist() == {"HPG"}
    r.unwatch("HPG"); assert r.watchlist() == set()
    # day_story (tu selftest cu: 9 ty cuoi phien, 5 ty sau 14:15, room -20)
    r2 = SqliteRepo(":memory:")
    for hhmm, buy, room in (("09:30", 2e9, 100), ("14:00", 4e9, 90), ("14:30", 9e9, 80)):
        snap(r2, f"{day}T{hhmm}:00+07:00", "DDD", buy, day_value=50e9, room=room)
    r2.save_day_story(day)
    assert r2.last_story("DDD", "2026-01-06") == (9e9, 5e9, -20)
    assert r2.last_story("DDD", day) is None                  # before_day nghiem ngat
    # meta
    assert r.get_meta("x") is None and r.get_meta("x", "0") == "0"
    r.set_meta("x", "42"); assert r.get_meta("x") == "42"
    assert r.has_snapshots(day) and not r.has_snapshots("2020-01-01")
    print("test_repo OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Fail** — `python3 -m tests.test_repo` → ModuleNotFoundError
- [ ] **Step 3: Viết `src/adapters/repositories.py`** (ABC đúng như Interfaces trên, mỗi method `raise NotImplementedError` qua `@abstractmethod`) và `src/infrastructure/sqlite_repo.py` implement — SQL copy verbatim từ các dòng collector.py đã liệt kê, chỉ đổi tham số hoá. `heat(ts, n)` dùng `COALESCE(pct, 0)`. `top_net` giữ `ABS(dn) > 1e9 ORDER BY dn DESC`.
- [ ] **Step 4: Verify** — `python3 -m tests.test_repo` OK; thêm vào `MODULES`; `python3 -m tests.run_all` OK.
- [ ] **Step 5: Commit** — `git commit -m "port SnapshotRepo + SqliteRepo: toan bo SQL vao 1 cho"`

---

### Task 5: gateways ABC + infrastructure feeds (SSI/VPS/VNDirect/news)

**Files:**
- Create: `src/adapters/gateways.py`, `src/infrastructure/vps_api.py`, `src/infrastructure/hose_feed.py`, `src/infrastructure/vndirect_api.py`, `src/infrastructure/news_api.py`, `tests/test_feeds.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Produces:

```python
# src/adapters/gateways.py
class MarketFeed(ABC):
    def fetch_hose(self): ...        # -> list[tuple 9 cot] (sym, buy_val, sell_val, buy_qtty, sell_qtty, room, price, day_value, pct)

class FlowHistory(ABC):
    def foreign_daily(self, code, n=10): ...   # -> list[DayFlow] cu -> moi
    def closes(self, code, n=10): ...          # -> list[float] cu -> moi ([] neu loi)

class LLM(ABC):
    def complete(self, system, user): ...      # -> str

class Telegram(ABC):
    def send_to(self, chat_id, text): ...
    def broadcast(self, text): ...             # -> bool (False neu chua config)
    def get_updates(self, offset, wait): ...   # -> list[dict]
```

- `vps_api.py`: MOVE verbatim collector.py:161-201 (`VPS_LIST`, `VPS_DATA`, `_vps_syms`, `_f`, `_vps_row`, `_vps_get`, `fetch_vps`).
- `hose_feed.py`: `class HoseFeed(MarketFeed)` — `fetch_hose()` = thử iBoard (logic collector.py:206-215, hằng `API`/`HEADERS` chuyển vào đây từ config) `except Exception:` fallback `fetch_vps()` (collector.py:216-217).
- `vndirect_api.py`: `class VnDirect(FlowHistory)` — `foreign_daily` = collector.py:435-441 nhưng map sang `DayFlow(trading_date=r["tradingDate"], net_val=r["netVal"] or 0)`; `closes` = phần HTTP của collector.py:444-456 trả `list[float]` (KHÔNG format — format sang presenters). Kèm module-level `fetch_fundamentals(sym)`, `fetch_prices_text(sym, n=20)` (MOVE brief.py:77-98 verbatim, đổi `_get` nội bộ), `RATIO_LABELS` (brief.py:34-40).
- `news_api.py`: MOVE brief.py:101-110 `fetch_news` verbatim.

- [ ] **Step 1: Viết test `tests/test_feeds.py`** — chỉ test phần thuần (không network):

```python
from src.infrastructure.vps_api import _vps_row

def run():
    # tu selftest cu: field string, gia tri nghin dong x1000, lot theo lo 10, pct co DAU
    row = _vps_row({"sym": "ABS", "fBValue": "1000", "fSValue": "2000.5", "fBVol": "10",
                    "fSVolume": "20", "fRoom": "99", "lastPrice": "12.6", "r": "12.8",
                    "lot": "100", "avePrice": "12.7", "changePc": "1.56"})
    assert row == ("ABS", 1000000.0, 2000500.0, 10.0, 20.0, 99.0, 12600.0, 12700000.0, -1.56), row
    assert _vps_row({"sym": "XXX"}) == ("XXX", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    # ABC compile + subclass quan he
    from src.adapters.gateways import FlowHistory, MarketFeed
    from src.infrastructure.hose_feed import HoseFeed
    from src.infrastructure.vndirect_api import VnDirect
    assert issubclass(HoseFeed, MarketFeed) and issubclass(VnDirect, FlowHistory)
    print("test_feeds OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Fail** → **Step 3: Implement 5 file như mô tả** → **Step 4: Verify + thêm MODULES + run_all OK**
- [ ] **Step 5: Smoke test network (không bắt buộc pass khi offline):** `python3 -c "from src.infrastructure.vndirect_api import VnDirect; f=VnDirect(); rows=f.foreign_daily('HPG',3); print(rows[-1]); print(f.closes('VNINDEX',3))"` — Expected: `DayFlow(trading_date='2026-07-1x', net_val=...)` + list 3 số.
- [ ] **Step 6: Commit** — `git commit -m "gateways ABC + infra feeds: SSI/VPS/VNDirect/news"`

---

### Task 6: adapters/presenters.py — mọi text Telegram

**Files:**
- Create: `src/adapters/presenters.py`, `tests/test_presenters.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Consumes: `DayFlow`, `TrendStats`, `Spike`, `Accel`, `RegimeChange`, `signals.trend_stats`.
- Produces (usecases + bot dùng):
  - `HELP_TEXT` (MOVE collector.py:88-113), `STATE_MSG` (129-134)
  - `ctx_line(day_net, price, pct) -> str` (384-387 verbatim)
  - `spike_msg(s: Spike) -> str` — text = collector.py:390-394, `WINDOW_MINUTES` nhận qua tham số default 10? KHÔNG — giữ import `from src.config import WINDOW_MINUTES` (presenters đọc hằng hiển thị từ config là chấp nhận được, config không phải layer nghiệp vụ)
  - `accel_msg(a: Accel) -> str` (305-308)
  - `state_msg(rc: RegimeChange) -> str` = `STATE_MSG[rc.regime].format(s=rc.symbol, r=rc.recent/1e9) + "\n" + ctx_line(...)`
  - `story_line(row) -> str` (373-381 verbatim, bỏ dấu `_`)
  - `trend_ctx_line(flows: "list[DayFlow]") -> str` (268-282, đổi `r["netVal"]` → `f.net_val`)
  - `format_trend(label, flows: "list[DayFlow]", price="") -> str` — text output byte-identical collector.py:463-512; phần tính toán gọi `signals.trend_stats([f.net_val for f in flows])`, map momo: `{"DAO_CHIEU": "3 phiên gần nhất ĐẢO CHIỀU so với xu hướng", "MANH": "đà đang MẠNH dần", "YEU": "đà đang YẾU dần", "ON_DINH": "đà ổn định"}`; câu "Đọc nhanh" giữ nguyên logic 493-503 dùng `t.flipped/t.streak/t.momo`
  - `price_line(code, closes: "list[float]") -> str` — phần format của collector.py:456-460 (nhận closes đã fetch)
  - `top_movers_text(rows: "list[tuple]") -> str` — phần format của collector.py:515-531 (nhận `repo.top_net(ts)` rows, không đụng DB)
  - `alert_digest(ts, msgs) -> str` = `f"📊 Khối ngoại — {ts[11:16]}\n\n" + "\n\n".join(msgs)` (từ run_once 672)

- [ ] **Step 1: Viết test `tests/test_presenters.py`** — port NGUYÊN các assert format từ selftest cũ (dòng 712-741) + case giá:

```python
from src.domain.entities import Accel, DayFlow, Spike
from src.adapters.presenters import (accel_msg, ctx_line, format_trend, price_line,
                                     spike_msg, story_line, top_movers_text, trend_ctx_line)

def flows(vals, month="01"):
    return [DayFlow(f"2026-{month}-{i+1:02d}", v) for i, v in enumerate(vals)]

def run():
    msg = format_trend("TEST", flows([-5e9] * 7 + [3e9, 4e9, 6e9]))
    assert "3 phiên mua ròng liên tiếp" in msg and "🟥" * 7 + "🟩" * 3 in msg, msg
    assert "ĐẢO CHIỀU" in msg and "(+3, +4, +6)" in msg, msg
    assert "ĐẢO CHIỀU" in format_trend("TEST", flows([-5e9] * 7 + [3e9]))   # vua flip
    m3 = format_trend("TEST", flows([-50e9] * 7 + [139e9, -13e9, -4e9], "02"),
                      "Giá: 22,200đ | phiên nay +0.0%")
    assert "ĐẢO CHIỀU" not in m3 and "(+139, -13, -4)" in m3 and "Giá: 22,200đ" in m3, m3
    assert "Giá:" not in format_trend("TEST", flows([-50e9] * 7 + [139e9, -13e9, -4e9], "02"))
    assert format_trend("X", []) == "Không có dữ liệu khối ngoại cho X."

    ctx = trend_ctx_line(flows([-5e9, -7e9, -3e9, -8e9, -9e9]))
    assert "🟥🟥🟥🟥🟥" in ctx and "-32" in ctx and "5 phiên bán ròng liên tiếp" in ctx, ctx
    assert trend_ctx_line([]) == ""
    mixed = trend_ctx_line(flows([5e9, -2e9, 3e9]))
    assert "🟩🟥🟩" in mixed and "liên tiếp" not in mixed, mixed

    s = spike_msg(Spike("AAA", 5e9, 0.25, 20000, 1.5, 25.2e9))
    assert "AAA" in s and "mua ròng" in s and "Cả phiên" in s and "Giá 20,000" in s, s
    assert "thỏa thuận" not in s
    assert "thỏa thuận" in spike_msg(Spike("AAA", 5e9, 0.85, 20000, 1.5, 25.2e9))

    a = accel_msg(Accel("BBB", (1.2e9, 2.7e9, 5e9), 9.9e9, 20000, 1.0))
    assert "BBB" in a and "TĂNG TỐC" in a and "1.2 → 2.7 → 5.0" in a, a

    assert "xả dồn 30' cuối" in story_line((-100e9, -45e9, 0))
    assert story_line((5e9, 1e9, 0)) == ""
    assert "room -1.2tr" in story_line((20e9, 1e9, -1_200_000))

    assert "Cả phiên: mua ròng 25.2 tỷ" in ctx_line(25.2e9, 20000, 1.5)
    assert "22,200đ" in price_line("HPG", [23.1, 22.2]) and "điểm" in price_line("VNINDEX", [1800.0])
    assert price_line("HPG", []) == ""
    t = top_movers_text([("AAA", 8e9), ("BBB", -5e9)])
    assert "Top gom hôm nay: AAA +8 tỷ" in t and "Top xả hôm nay: BBB -5 tỷ" in t, t
    assert top_movers_text([]) == ""
    print("test_presenters OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Fail** → **Step 3: Implement `src/adapters/presenters.py`** theo Interfaces (bodies MOVE từ các dòng đã ghi; `accel_msg` nhận entity nhưng text giữ nguyên — thêm dòng 2 `ctx_line(a.day_net, a.price, a.pct)` NHƯ HIỆN TẠI đang ghép ở detect_accel:346-347, tức accel_msg trả cả 2 dòng).
- [ ] **Step 4: Verify + MODULES + run_all OK** → **Step 5: Commit** `git commit -m "presenters: toan bo text Telegram, nhan entity/so lieu thuan"`

---

### Task 7: infrastructure/telegram.py + infrastructure/llm.py

**Files:**
- Create: `src/infrastructure/telegram.py`, `src/infrastructure/llm.py`, `tests/test_infra_misc.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Produces:
  - `telegram.TelegramBot(cfg: dict)` implements `Telegram` — `send_to` (MOVE collector.py:534-539), `broadcast` (542-549, trả False nếu thiếu token/chat_ids), `get_updates(offset, wait)` (phần HTTP của poll_commands 560-562, trả `json["result"]`)
  - `llm.LlmClient()` implements `LLM` — `complete(system, user)` = brief.py `call_llm` (163-171); `_call_gemini`/`_call_claude` MOVE verbatim brief.py:126-160

- [ ] **Step 1: Test `tests/test_infra_misc.py`**

```python
from src.adapters.gateways import LLM, Telegram
from src.infrastructure.llm import LlmClient
from src.infrastructure.telegram import TelegramBot

def run():
    assert issubclass(TelegramBot, Telegram) and issubclass(LlmClient, LLM)
    assert TelegramBot({}).broadcast("x") is False       # chua config -> im lang, khong crash
    import os
    saved = {k: os.environ.pop(k, None) for k in
             ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        try:
            LlmClient().complete("s", "u")
            assert False, "phai raise khi khong co key"
        except RuntimeError as e:
            assert "LLM key" in str(e)
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    print("test_infra_misc OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Fail** → **Step 3: Implement** → **Step 4: Verify + MODULES** → **Step 5: Commit** `git commit -m "infra: TelegramBot + LlmClient (Claude/Gemini fallback)"`

---

### Task 8: usecases — poll, detect, trend, story, script, summary

**Files:**
- Create: `src/usecases/poll_market.py`, `src/usecases/detect_alerts.py`, `src/usecases/build_trend.py`, `src/usecases/day_story.py`, `src/usecases/make_script.py`, `src/usecases/summary.py`, `tests/test_usecases.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Consumes: `SnapshotRepo`, `MarketFeed`, `FlowHistory`, `LLM`, `Telegram`, domain signals, presenters.
- Produces:
  - `poll_market.poll(repo, feed) -> (ts, n)` (logic collector.py:204-222; ts = `now_vn().isoformat(timespec="seconds")`)
  - `detect_alerts.detect_spikes(repo, flows, ts, wl) -> list[str]` — quét `repo.spike_rows`, rule `signals.spike_share`, cooldown `repo.recent_alert`, text `presenters.spike_msg(Spike(...)) + trend_ctx(...)`, ghi `repo.add_alerts`. Logic 1-1 với collector.py:235-265.
  - `detect_alerts.detect_states(repo, flows, ts, wl) -> list[str]` (1-1 với 397-432; NEUTRAL vẫn `set_regime` nhưng không message — giữ nguyên)
  - `detect_alerts.detect_accel(repo, flows, ts, wl) -> list[str]` (1-1 với 311-350)
  - `detect_alerts.run_once(repo, feed, flows, tg) -> list[str]` (666-678; print giữ nguyên; `tg.broadcast` trong try/except)
  - `build_trend.trend_ctx(sym, repo, flows) -> str` (285-302: lọc `f.trading_date < today`, lấy 5 phiên, cộng `story_line(repo.last_story(...))`; mọi lỗi → `""`)
  - `build_trend.trend_message(code, label, repo, flows) -> str` = `format_trend(label, flows.foreign_daily(code), price_line(code, flows.closes(code)))` + (`top_movers_text(repo.top_net(repo.max_ts()))` CHỈ khi code=="VNINDEX" — match hành vi /trend hiện tại)
  - `day_story.build_day_story(repo, day)` = `repo.save_day_story(day)` (giữ hàm mỏng để usecase gọi tên nghiệp vụ)
  - `make_script.make_script(repo, flows, llm) -> str` (617-636 + `SCRIPT_SYSTEM` MOVE 115-127; data trend lấy qua `trend_message`)
  - `summary.maybe_send_summary(repo, flows, llm, tg)` (639-663)
- **Lưu ý wl_factor:** trong usecase tính `f = WL_FACTOR if sym in wl else 1.0` rồi truyền vào signals cùng các ngưỡng từ config — đây là điểm nối config↔domain duy nhất. Riêng detect_states giữ nguyên semantics hiện tại: bỏ qua mã ngoài watchlist có `day_value < MIN_DAY_VALUE` (KHÔNG nhân factor, xem collector.py:415), khác detect_spikes (nhân factor, dòng 251).

- [ ] **Step 1: Viết test `tests/test_usecases.py`** — port nguyên kịch bản selftest cũ (dòng 691-710 states/spikes, 743-759 accel, 761-769 day_story) chạy trên `SqliteRepo(":memory:")` + fake flows:

```python
from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.detect_alerts import detect_accel, detect_spikes, detect_states
from src.usecases.day_story import build_day_story

class NoFlows:                       # FlowHistory cam: trend_ctx -> "" nhu khi API loi
    def foreign_daily(self, code, n=10):
        raise RuntimeError("offline")
    def closes(self, code, n=10):
        return []

def snap(r, ts, sym, buy, sell=0, dv=100e9, price=20000, pct=1.5, room=0):
    r.insert_snapshots(ts, [(sym, buy, sell, 0, 0, room, price, dv, pct)])

def run():
    day, F = "2026-01-05", NoFlows()
    r = SqliteRepo(":memory:")
    snap(r, f"{day}T09:30:00+07:00", "AAA", 10e9)
    snap(r, f"{day}T10:00:00+07:00", "AAA", 20e9)
    msgs = detect_states(r, F, f"{day}T10:00:00+07:00", set())
    assert len(msgs) == 1 and "GOM" in msgs[0] and "CHỮNG" not in msgs[0], msgs
    assert "Cả phiên" in msgs[0] and "Giá 20,000" in msgs[0], msgs
    snap(r, f"{day}T10:30:00+07:00", "AAA", 20.1e9)
    msgs = detect_states(r, F, f"{day}T10:30:00+07:00", set())
    assert len(msgs) == 1 and "CHỮNG" in msgs[0], msgs
    snap(r, f"{day}T11:00:00+07:00", "AAA", 20.2e9)
    assert detect_states(r, F, f"{day}T11:00:00+07:00", set()) == []

    snap(r, f"{day}T10:10:00+07:00", "AAA", 25.2e9, dv=120e9)
    msgs = detect_spikes(r, F, f"{day}T10:10:00+07:00", set())
    assert len(msgs) == 1 and "AAA" in msgs[0] and "mua ròng" in msgs[0], msgs
    assert "thỏa thuận" not in msgs[0]
    assert detect_spikes(r, F, f"{day}T10:10:00+07:00", set()) == [], "cooldown"

    r2 = SqliteRepo(":memory:")
    dvs = {"10:00": 100e9, "10:05": 110e9, "10:10": 120e9, "10:15": 140e9}
    big = {"10:00": 100e9, "10:05": 300e9, "10:10": 600e9, "10:15": 1000e9}
    for hhmm, bbb, ccc in (("10:00", 1e9, 1e9), ("10:05", 2.2e9, 6e9),
                           ("10:10", 4.9e9, 8e9), ("10:15", 9.9e9, 9e9)):
        for sym, buy, dv in (("BBB", bbb, dvs[hhmm]), ("CCC", ccc, dvs[hhmm]), ("EEE", bbb, big[hhmm])):
            snap(r2, f"{day}T{hhmm}:00+07:00", sym, buy, dv=dv, pct=1.0)
    msgs = detect_accel(r2, F, f"{day}T10:15:00+07:00", set())
    assert len(msgs) == 1 and "BBB" in msgs[0] and "TĂNG TỐC" in msgs[0], msgs
    assert "1.2 → 2.7 → 5.0" in msgs[0] and "Cả phiên" in msgs[0], msgs
    assert detect_accel(r2, F, f"{day}T10:15:00+07:00", set()) == [], "cooldown accel"

    r3 = SqliteRepo(":memory:")
    for hhmm, buy, room in (("09:30", 2e9, 100), ("14:00", 4e9, 90), ("14:30", 9e9, 80)):
        snap(r3, f"{day}T{hhmm}:00+07:00", "DDD", buy, dv=50e9, room=room)
    build_day_story(r3, day)
    assert r3.last_story("DDD", "2026-01-06") == (9e9, 5e9, -20)
    print("test_usecases OK")

if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Fail** → **Step 3: Implement 6 file usecases** theo Interfaces (logic 1-1 theo line refs; KHÔNG sáng tạo thêm)
- [ ] **Step 4: Verify + MODULES + run_all OK** → **Step 5: Commit** `git commit -m "usecases: poll/detect/trend/story/script/summary tren ports"`

---

### Task 9: usecases/build_brief.py + adapters/bot.py

**Files:**
- Create: `src/usecases/build_brief.py`, `src/adapters/bot.py`, `tests/test_bot.py`
- Modify: `tests/run_all.py`

**Interfaces:**
- Produces:
  - `build_brief.build_brief(sym, flows, llm) -> str` — MOVE brief.py `SYSTEM` (42-69), `gather` (113-123: trend qua `presenters.format_trend(sym, flows.foreign_daily(sym))`, giá qua `vndirect_api.fetch_prices_text`, cơ bản qua `fetch_fundamentals`, tin qua `news_api.fetch_news`), `build_brief` (174-178)
  - `bot.handle_updates(repo, tg, flows, llm, wait=25) -> None` — logic poll_commands collector.py:552-614 nguyên vẹn: offset từ `repo.get_meta("tg_offset", "0")`, updates từ `tg.get_updates`, route /ID /WATCH /UNWATCH /LIST /TREND /SCRIPT /BRIEF /HELP /START sang usecases (`build_trend.trend_message`, `make_script.make_script`, `build_brief.build_brief`), reply qua `tg.send_to`, cuối cùng `repo.set_meta("tg_offset", str(offset))`. Nếu thiếu config: `time.sleep(wait)` rồi return (như hiện tại).

- [ ] **Step 1: Test `tests/test_bot.py`** — fake Telegram ghi lại message, test route /WATCH /LIST /HELP /ID + chat lạ bị chặn:

```python
from src.adapters.bot import handle_updates
from src.infrastructure.sqlite_repo import SqliteRepo

class FakeTg:
    def __init__(self, updates):
        self.updates, self.sent = updates, []
    def send_to(self, chat_id, text):
        self.sent.append((chat_id, text))
    def broadcast(self, text):
        return True
    def get_updates(self, offset, wait):
        u, self.updates = self.updates, []
        return u

def upd(i, chat, text):
    return {"update_id": i, "message": {"chat": {"id": chat}, "text": text}}

def run(monkey_cfg={"token": "t", "chat_ids": [7]}):
    import src.adapters.bot as bot
    bot.load_config = lambda: monkey_cfg          # khong doc file that
    r = SqliteRepo(":memory:")
    tg = FakeTg([upd(1, 7, "/watch hpg"), upd(2, 7, "/list"),
                 upd(3, 99, "/list"), upd(4, 99, "/id"), upd(5, 7, "/help")])
    handle_updates(r, tg, flows=None, llm=None, wait=0)
    assert r.watchlist() == {"HPG"}
    texts = [t for _, t in tg.sent]
    assert any("Đã theo dõi HPG" in t for t in texts)
    assert any(t.startswith("Watchlist: HPG") for t in texts)
    assert any("Chat id: 99" in t for t in texts)          # /id chay o chat la
    assert sum(c == 99 for c, _ in tg.sent) == 1           # chat la CHI duoc tra loi /id
    assert any("Lệnh của bot" in t for t in texts)
    assert r.get_meta("tg_offset") == "5"
    print("test_bot OK")

if __name__ == "__main__":
    run()
```

(Để test được, `bot.py` đọc config qua tên module-level `load_config` — import `from src.config import load_config` rồi gọi `load_config()` bên trong hàm.)

- [ ] **Step 2: Fail** → **Step 3: Implement** → **Step 4: Verify + MODULES** → **Step 5: Commit** `git commit -m "bot controller + build_brief usecase"`

---

### Task 10: src/main.py wiring + cắt đuôi (xoá collector.py/brief.py, update mọi consumer)

**Files:**
- Create: `src/main.py`
- Modify: `video.py` (imports + DayFlow), `Procfile`, `deploy/setup.sh`, `deploy/stock-bot.service`
- Delete: `collector.py`, `brief.py`

**Interfaces:**
- Consumes: mọi thứ ở trên.
- Produces: `python3 -m src.main [--selftest|--once]`; module-level `src.main.build()` trả `(repo, feed, flows, llm, tg)` để video.py dùng.

- [ ] **Step 1: Viết `src/main.py`**

```python
"""Entry point: wiring (composition root) + CLI + vong lap chinh.

Usage:
    python -m src.main --selftest   # chay toan bo tests/
    python -m src.main --once       # 1 poll + report roi thoat
    python -m src.main              # loop (09:00-15:05 VN, T2-T6)
"""
import sys
import time

from src.config import DB, POLL_MINUTES, in_trading_hours, load_config, load_env, now_vn
from src.adapters.bot import handle_updates
from src.infrastructure.hose_feed import HoseFeed
from src.infrastructure.llm import LlmClient
from src.infrastructure.sqlite_repo import SqliteRepo
from src.infrastructure.telegram import TelegramBot
from src.infrastructure.vndirect_api import VnDirect
from src.usecases.detect_alerts import run_once
from src.usecases.summary import maybe_send_summary


def build(db_path=None):
    """Composition root — noi DUY NHAT khoi tao class infrastructure."""
    load_env()
    return (SqliteRepo(db_path or DB), HoseFeed(), VnDirect(),
            LlmClient(), TelegramBot(load_config()))


def main():
    if "--selftest" in sys.argv:
        from tests.run_all import main as run_tests
        run_tests()
        return
    repo, feed, flows, llm, tg = build()
    if "--once" in sys.argv:
        run_once(repo, feed, flows, tg)
        return
    print(f"Collector started. Market poll every {POLL_MINUTES}', commands via long-poll. DB: {DB}")
    last_poll = 0.0
    while True:
        try:
            handle_updates(repo, tg, flows, llm)  # blocks ~25s, tra ve ngay khi co lenh
        except Exception as e:
            print(f"[{now_vn().isoformat(timespec='seconds')}] commands failed: {e}")
            time.sleep(10)
        if in_trading_hours(now_vn()) and time.time() - last_poll >= POLL_MINUTES * 60:
            try:
                run_once(repo, feed, flows, tg)
            except Exception as e:
                print(f"[{now_vn().isoformat(timespec='seconds')}] poll failed: {e}")
            last_poll = time.time()
        maybe_send_summary(repo, flows, llm, tg)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update `video.py`** — đúng các chỗ sau, còn lại giữ nguyên:
  - Dòng 27-28: `from brief import load_env` / `from collector import DB, fetch_foreign_daily, make_script` →

    ```python
    from src.config import DB, load_config, load_env
    from src.infrastructure.sqlite_repo import SqliteRepo, SCHEMA
    from src.infrastructure.vndirect_api import VnDirect
    from src.infrastructure.llm import LlmClient
    from src.usecases.make_script import make_script
    ```
  - `build_ctx` (410-415): `rows = VnDirect().foreign_daily("VNINDEX", 10)` rồi `rows[-1].net_val`, `rows[-1].trading_date`
  - `scene_chart` (164, 183): `vals = [r.net_val / 1e9 for r in ctx["rows"]]`; nhãn ngày `ctx["rows"][i].trading_date[8:10]`
  - `preview` (557-558): fake rows thành `[DayFlow(f"2026-07-{d:02d}", v * 1e9) for ...]` với `from src.domain.entities import DayFlow`
  - `stage_script` (424): `make_script(db, ...)` → `make_script(SqliteRepo(DB), VnDirect(), LlmClient())` — chú ý: `make_video()`/`stage_*` đang cầm `sqlite3.connect(DB)`; đổi các hàm này nhận `repo = SqliteRepo(DB)` và các query nội bộ của video.py (`top_mover_rows`, `heatmap_rows` dòng 363-379) đổi sang `repo.top_net`/`repo.heat`: `top_mover_rows` cần price+pct → thêm method `top_net_full(ts)` vào SnapshotRepo/SqliteRepo trả `(sym, dn, price, pct)` (SQL = video.py:366-368) trong task này (kèm 1 assert trong tests/test_repo.py)
  - `send_video` (526): bỏ `from collector import load_config` (đã import đầu file)
  - `selftest` (614): `from collector import SCHEMA` → dùng `SqliteRepo(":memory:")` và exercise `repo.heat`/`repo.top_net_full` thay vì SQL tay
- [ ] **Step 3: Update entry points**
  - `Procfile`: `worker: python -u -m src.main`
  - `deploy/setup.sh` dòng 6: `cp collector.py telegram.json /opt/stock-bot/` → `rsync -a src tests telegram.json /opt/stock-bot/` (tests đi kèm để `--selftest` chạy được trên VPS)
  - `deploy/stock-bot.service`: `ExecStart=/usr/bin/python3 -u -m src.main` + thêm `WorkingDirectory=/opt/stock-bot` (đã có — giữ)
- [ ] **Step 4: Xoá file cũ** — `git rm collector.py brief.py`
- [ ] **Step 5: Verify toàn cục**

Run: `python3 -m src.main --selftest && python3 video.py --selftest && python3 video.py --preview`
Expected: `ALL TESTS OK`, `selftest OK`, 5 file preview PNG.

Run: `grep -rn "from collector\|import collector\|from brief\|import brief" --include="*.py" . | grep -v .venv`
Expected: không còn kết quả nào.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "main.py wiring, video/deploy tro sang src/, xoa collector.py + brief.py"`

---

### Task 11: Verification end-to-end + dọn tài liệu

**Files:**
- Modify: `.claude/skills/daily-video/SKILL.md` (chỉ nếu grep thấy tham chiếu collector.py/brief.py), docstring `src/main.py` đã là README usage mới

- [ ] **Step 1: Smoke test có mạng (đọc-only, không gửi Telegram):**

Run: `python3 -c "
from src.main import build
repo, feed, flows, llm, tg = build(':memory:')
from src.usecases.build_trend import trend_message
print(trend_message('HPG', 'HPG', repo, flows))
"`
Expected: message trend HPG đầy đủ 7 dòng, có dòng `Giá: ...đ` — so bằng mắt với output bản cũ (đã lưu ở conversation / chạy lại bản cũ từ git stash nếu cần đối chiếu).

- [ ] **Step 2: Poll thật 1 nhịp (ghi DB tạm, không gửi):** `DB_PATH=/tmp/ca-test.db python3 -m src.main --once`
Expected: dòng `[...] snapshot ~400 symbols, 0 alerts` (số symbol > 300).

- [ ] **Step 3: Grep tham chiếu chết trong skill + docs:** `grep -rn "collector.py\|brief.py" .claude/ deploy/ Procfile docs/ | grep -v plans/` — sửa mọi chỗ còn trỏ file cũ (SKILL.md của daily-video chỉ nói về video.py — dự kiến không phải sửa).
- [ ] **Step 4: Chạy lại toàn bộ:** `python3 -m src.main --selftest && python3 video.py --selftest`
- [ ] **Step 5: Commit cuối** — `git commit -am "hoan tat clean arch: verify e2e, don tai lieu"`

---

## Self-Review (đã chạy)

1. **Spec coverage:** src/ 4 layer + main.py wiring ✔ (Task 2-10); deploy/setup.sh + systemd + Procfile ✔ (Task 10); imports video/brief/backtest/variants — video ✔ (Task 10), brief thành usecase ✔ (Task 9), backtest.py/variants.py không import collector/brief nên không cần sửa (đã xác minh bằng grep); behavior freeze + selftest ✔ (mọi assert cũ được port ở Task 3/4/6/8/9, verify e2e Task 11).
2. **Placeholder scan:** không còn TBD/TODO; các bước MOVE đều kèm line-ref chính xác từ bản collector.py/brief.py/video.py hiện tại.
3. **Type consistency:** `SnapshotRepo` method list ở Task 4 khớp usage Task 8/9/10 (`top_net_full` bổ sung có chủ đích ở Task 10 — ghi rõ kèm test); `DayFlow.net_val/trading_date` dùng thống nhất ở presenters/video; momo codes `DAO_CHIEU|MANH|YEU|ON_DINH` khớp giữa signals (Task 3) và presenters (Task 6).
