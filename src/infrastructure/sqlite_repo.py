"""SqliteRepo: toan bo SQL cua app gom vao 1 cho."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.adapters.repositories import SnapshotRepo

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
CREATE TABLE IF NOT EXISTS watchlist (  -- rieng tung chat: /watch cua ai nguoi do huong
    chat_id INTEGER NOT NULL, symbol TEXT NOT NULL, PRIMARY KEY (chat_id, symbol));
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS fund_holdings (  -- top 10 khoan/quy tu Fmarket, chup 1 lan/thang
    month TEXT NOT NULL,    -- 'YYYY-MM' thang chup
    fund TEXT NOT NULL,     -- shortName quy
    symbol TEXT NOT NULL,
    pct REAL,               -- % NAV
    industry TEXT,
    volume REAL,            -- so cp quy dang nam
    value REAL,             -- gia tri khoan (VND)
    PRIMARY KEY (month, fund, symbol)
);
CREATE TABLE IF NOT EXISTS fund_assets (     -- phan bo tai san cua quy (Co phieu/Tien/...)
    month TEXT NOT NULL, fund TEXT NOT NULL, asset TEXT NOT NULL, pct REAL,
    PRIMARY KEY (month, fund, asset)
);
CREATE TABLE IF NOT EXISTS fund_industries ( -- phan bo nganh cua quy
    month TEXT NOT NULL, fund TEXT NOT NULL, industry TEXT NOT NULL, pct REAL,
    PRIMARY KEY (month, fund, industry)
);
CREATE TABLE IF NOT EXISTS fund_snapshot (   -- 1 dong/quy/thang: NAV + hieu suat + thang bao cao
    month TEXT NOT NULL, fund TEXT NOT NULL,
    owner TEXT,            -- cong ty quan ly quy
    report_month TEXT,     -- thang bao cao danh muc thuc te (thuong som hon month 1 thang)
    nav REAL,              -- gia 1 ccq
    nav_1m REAL, nav_3m REAL, nav_6m REAL, nav_12m REAL, nav_36m REAL,  -- % thay doi NAV
    aum REAL,              -- tong tai san quy (VND, fundReport.totalAssetValue)
    PRIMARY KEY (month, fund)
);
"""


class SqliteRepo(SnapshotRepo):
    def __init__(self, path_or_conn):
        if isinstance(path_or_conn, sqlite3.Connection):
            self.db = path_or_conn
        else:
            self.db = sqlite3.connect(str(path_or_conn) if isinstance(path_or_conn, Path) else path_or_conn)
        self.db.executescript(SCHEMA)
        for stmt in ("ALTER TABLE snapshots ADD COLUMN pct REAL",          # migrate DB cu
                     "ALTER TABLE fund_holdings ADD COLUMN volume REAL",
                     "ALTER TABLE fund_holdings ADD COLUMN value REAL",
                     "ALTER TABLE fund_snapshot ADD COLUMN aum REAL"):
            try:
                self.db.execute(stmt)
            except sqlite3.OperationalError:
                pass
        # watchlist tu global (1 cot) -> per-chat: giu bang cu lam backup, tao bang moi rong
        cols = [c[1] for c in self.db.execute("PRAGMA table_info(watchlist)")]
        if cols and "chat_id" not in cols:
            self.db.execute("ALTER TABLE watchlist RENAME TO watchlist_old")
            self.db.execute("CREATE TABLE watchlist (chat_id INTEGER NOT NULL, symbol TEXT NOT NULL, "
                            "PRIMARY KEY (chat_id, symbol))")
            self.db.commit()

    def insert_snapshots(self, ts, rows):
        self.db.executemany("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
                            [(ts, *r) for r in rows])
        self.db.commit()

    def max_ts(self):
        return self.db.execute("SELECT MAX(ts) FROM snapshots").fetchone()[0]

    def prev_snapshot_ts(self, ts, minutes):
        cutoff = (datetime.fromisoformat(ts) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        return self.db.execute("SELECT MAX(ts) FROM snapshots WHERE ts <= ? AND ts >= ?",
                               (cutoff, ts[:10])).fetchone()[0]

    def snapshot_times(self, day, until_ts, n):
        rows = self.db.execute(
            "SELECT DISTINCT ts FROM snapshots WHERE ts >= ? AND ts <= ? ORDER BY ts DESC LIMIT ?",
            (day, until_ts, n)).fetchall()
        return [r[0] for r in rows][::-1]

    def spike_rows(self, ts, prev_ts):
        q = """
        SELECT a.symbol,
               (a.buy_val - b.buy_val) - (a.sell_val - b.sell_val) AS net,
               a.day_value - b.day_value AS win_value,
               a.day_value, a.price, a.pct,
               a.buy_val - a.sell_val AS day_net
        FROM snapshots a JOIN snapshots b USING (symbol)
        WHERE a.ts = ? AND b.ts = ?
        """
        return self.db.execute(q, (ts, prev_ts)).fetchall()

    def state_rows(self, ts, prev_ts):
        q = """
        SELECT a.symbol,
               a.buy_val - a.sell_val AS day_net,
               (a.buy_val - a.sell_val) - (b.buy_val - b.sell_val) AS recent,
               a.day_value, a.price, a.pct
        FROM snapshots a JOIN snapshots b USING (symbol)
        WHERE a.ts = ? AND b.ts = ?
        """
        return self.db.execute(q, (ts, prev_ts)).fetchall()

    def accel_rows(self, t0, t1, t2, t3):
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
        return self.db.execute(q, (t3, t2, t1, t0)).fetchall()

    def recent_alert(self, symbol, direction, ts, minutes):
        """Da alert cung ma cung chieu trong `minutes` phut truoc ts chua (cooldown)."""
        cutoff = (datetime.fromisoformat(ts) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        return self.db.execute("SELECT 1 FROM alerts WHERE symbol=? AND direction=? AND ts>?",
                               (symbol, direction, cutoff)).fetchone() is not None

    def alerts_since(self, day):
        """[(ts, symbol, direction)] tu ngay `day` (cho scorecard)."""
        return self.db.execute("SELECT ts, symbol, direction FROM alerts WHERE ts >= ? ORDER BY ts",
                               (day,)).fetchall()

    def add_alerts(self, rows):
        self.db.executemany(
            "INSERT INTO alerts (ts,symbol,direction,net_10m,share,price) VALUES (?,?,?,?,?,?)", rows)
        self.db.commit()

    def get_regime(self, symbol, day):
        row = self.db.execute("SELECT regime FROM state WHERE symbol=? AND day=?", (symbol, day)).fetchone()
        return row[0] if row else "NEUTRAL"

    def set_regime(self, symbol, regime, day):
        self.db.execute("INSERT OR REPLACE INTO state VALUES (?,?,?)", (symbol, regime, day))
        self.db.commit()

    def watchlist(self, chat_id):
        """Watchlist rieng cua 1 chat."""
        return {r[0] for r in self.db.execute("SELECT symbol FROM watchlist WHERE chat_id=?", (chat_id,))}

    def watch_union(self):
        """Hop watchlist moi chat — detector dung de biet ma nao can nguong thap."""
        return {r[0] for r in self.db.execute("SELECT DISTINCT symbol FROM watchlist")}

    def watch(self, chat_id, symbol):
        self.db.execute("INSERT OR IGNORE INTO watchlist VALUES (?, ?)", (chat_id, symbol))
        self.db.commit()

    def unwatch(self, chat_id, symbol):
        self.db.execute("DELETE FROM watchlist WHERE chat_id=? AND symbol=?", (chat_id, symbol))
        self.db.commit()

    def save_day_story(self, day, late_from):
        span = self.db.execute("SELECT MIN(ts), MAX(ts) FROM snapshots WHERE ts >= ? AND ts < ?",
                               (day, day + "~")).fetchone()  # '~' > 'T' -> het ngay, an theo index PK
        first, last = span
        if not first:
            return
        cut = self.db.execute("SELECT MAX(ts) FROM snapshots WHERE ts >= ? AND ts <= ?",
                              (day, f"{day}T{late_from}")).fetchone()[0] or first
        self.db.execute("""
            INSERT OR REPLACE INTO day_story
            SELECT ?, l.symbol, l.buy_val - l.sell_val,
                   (l.buy_val - l.sell_val) - (c.buy_val - c.sell_val),
                   l.room - f.room
            FROM snapshots l
            JOIN snapshots c ON c.symbol = l.symbol AND c.ts = ?
            JOIN snapshots f ON f.symbol = l.symbol AND f.ts = ?
            WHERE l.ts = ?""", (day, cut, first, last))
        self.db.commit()

    def week_net(self, d1, d2, min_net):
        """Tong NN rong tung ma qua cac phien d1..d2 (tu day_story) — movers theo tuan."""
        return self.db.execute(
            "SELECT symbol, SUM(net) AS wn FROM day_story WHERE day>=? AND day<=? "
            "GROUP BY symbol HAVING ABS(wn) > ? ORDER BY wn DESC", (d1, d2, min_net)).fetchall()

    def last_story(self, symbol, before_day):
        return self.db.execute(
            "SELECT day, net, late_net, room_delta FROM day_story "
            "WHERE symbol=? AND day<? ORDER BY day DESC LIMIT 1",
            (symbol, before_day)).fetchone()

    def market_net(self, ts):
        """Tong mua/ban rong KN toan thi truong tai snapshot ts (VND)."""
        return self.db.execute("SELECT SUM(buy_val - sell_val) FROM snapshots WHERE ts=?",
                               (ts,)).fetchone()[0]

    def snapshot_count(self, ts):
        """So ma trong snapshot ts (cho tin nhip tim dau phien)."""
        return self.db.execute("SELECT COUNT(*) FROM snapshots WHERE ts=?", (ts,)).fetchone()[0]

    def top_net_full(self, ts, min_net):
        return self.db.execute(
            "SELECT symbol, buy_val - sell_val AS dn, price, COALESCE(pct, 0) "
            "FROM snapshots WHERE ts=? AND ABS(dn) > ? ORDER BY dn DESC", (ts, min_net)).fetchall()

    def heat(self, ts, n):
        return self.db.execute(
            "SELECT symbol, COALESCE(pct, 0) FROM snapshots WHERE ts=? ORDER BY day_value DESC LIMIT ?",
            (ts, n)).fetchall()

    def has_snapshots(self, day):
        return self.db.execute("SELECT 1 FROM snapshots WHERE ts >= ? AND ts < ? LIMIT 1",
                               (day, day + "~")).fetchone() is not None

    def save_fund_month(self, month, holdings, assets, industries, snapshots):
        """Thay tron du lieu quy cua 1 thang (1 transaction — loi giua chung khong ghi gi).
        holdings [(fund,sym,pct,industry,volume,value)], assets [(fund,asset,pct)],
        industries [(fund,industry,pct)], snapshots [(fund,owner,report_month,nav,n1..n36,aum)]."""
        for t in ("fund_holdings", "fund_assets", "fund_industries", "fund_snapshot"):
            self.db.execute(f"DELETE FROM {t} WHERE month=?", (month,))
        self.db.executemany("INSERT OR REPLACE INTO fund_holdings VALUES (?,?,?,?,?,?,?)",
                            [(month, *r) for r in holdings])
        self.db.executemany("INSERT OR REPLACE INTO fund_assets VALUES (?,?,?,?)",
                            [(month, *r) for r in assets])
        self.db.executemany("INSERT OR REPLACE INTO fund_industries VALUES (?,?,?,?)",
                            [(month, *r) for r in industries])
        self.db.executemany("INSERT OR REPLACE INTO fund_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            [(month, *r) for r in snapshots])
        self.db.commit()

    def fund_report_month(self, month):
        """(min, max) ky bao cao danh muc thuc te cua thang chup — None neu chua co."""
        r = self.db.execute("SELECT MIN(report_month), MAX(report_month) FROM fund_snapshot WHERE month=?",
                            (month,)).fetchone()
        return r if r and r[0] else None

    def has_fund_month(self, month):
        """Thang do da chup DAY DU (co aum) chua — dieu kien `aum IS NOT NULL` de ban pull cu
        (truoc khi co aum/volume/value) tu dong duoc chup bu."""
        return self.db.execute("SELECT 1 FROM fund_snapshot WHERE month=? AND aum IS NOT NULL LIMIT 1",
                               (month,)).fetchone() is not None

    def fund_months(self):
        return [r[0] for r in self.db.execute("SELECT DISTINCT month FROM fund_holdings ORDER BY month")]

    def fund_consensus(self, month):
        """[(symbol, so_quy_nam, tong_pct, tong_value_vnd)] DESC theo so quy."""
        return self.db.execute(
            "SELECT symbol, COUNT(*) AS n, SUM(pct), SUM(value) FROM fund_holdings WHERE month=? "
            "GROUP BY symbol ORDER BY n DESC, SUM(pct) DESC", (month,)).fetchall()

    def funds_holding(self, symbol, month):
        return self.db.execute(
            "SELECT fund, pct, value FROM fund_holdings WHERE month=? AND symbol=? ORDER BY pct DESC",
            (month, symbol)).fetchall()

    def get_meta(self, k, default=None):
        row = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row[0] if row else default

    def set_meta(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, v))
        self.db.commit()
