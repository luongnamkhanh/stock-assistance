"""Backtest: abnormal foreign net-flow (khoi ngoai) delta -> forward returns, VN stocks.

Signal (computed after close of day t):
    z = (netVal_t - mean(netVal, 20d)) / std(netVal, 20d)   # "innovation" component
    BUY  signal: z >= Z_TH  and stock not near full foreign room
    SELL signal: z <= -Z_TH
Entry at next session's open (adjusted), exit at adjusted close after H sessions.
Compare signal-day forward returns vs all other days (same stock universe), per year.

Data: VNDirect finfo API (free, no auth). Cached under ./data/.
"""

import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

UNIVERSE = [
    "HPG", "FPT", "MWG", "VNM", "MSN", "VIC", "VHM", "VRE",
    "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "STB", "VPB", "HDB", "TPB", "SHB", "EIB",
    "SSI", "VND", "HCM", "VCI", "VIX",
    "GAS", "POW", "PLX", "DGC", "DPM", "DCM",
    "PNJ", "SAB", "VJC", "GMD", "KBC", "NLG", "KDH", "DXG", "PDR",
]
START = "2021-01-01"
LOOKBACK = 20          # sessions for baseline mean/std
Z_TH = 2.0             # signal threshold
ROOM_MIN_PCT = 0.02    # skip signals when remaining foreign room < 2% (kin room)
HORIZONS = [1, 3, 5]   # exit at adClose of entry_day + (h-1) sessions; h=1 -> open->close same day
DATA_DIR = Path(__file__).parent / "data"

API = "https://api-finfo.vndirect.com.vn/v4"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_all(endpoint, q, sort):
    # ponytail: size=1000 per page, loop pages; VND caps a page at 1000 rows
    rows, page = [], 1
    while True:
        j = fetch_json(f"{API}/{endpoint}?q={q}&size=1000&page={page}&sort={sort}")
        rows += j["data"]
        if len(rows) >= j.get("totalElements", 0) or not j["data"]:
            return rows
        page += 1


def load_symbol(sym):
    cache = DATA_DIR / f"{sym}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    fr = pd.DataFrame(fetch_all("foreigns", f"code:{sym}~tradingDate:gte:{START}", "tradingDate:asc"))
    px = pd.DataFrame(fetch_all("stock_prices", f"code:{sym}~date:gte:{START}", "date:asc"))
    if fr.empty or px.empty:
        return pd.DataFrame()
    fr = fr[["tradingDate", "netVal", "buyVal", "sellVal", "totalRoom", "currentRoom"]].rename(
        columns={"tradingDate": "date"})
    keep = [c for c in ["date", "adOpen", "adClose", "nmVolume", "nmVol", "average"] if c in px.columns]
    px = px[keep]
    df = px.merge(fr, on="date", how="inner").sort_values("date").reset_index(drop=True)
    df["symbol"] = sym
    DATA_DIR.mkdir(exist_ok=True)
    df.to_parquet(cache)
    time.sleep(0.4)
    return df


def add_signals(df):
    roll = df["netVal"].rolling(LOOKBACK)
    mu, sd = roll.mean().shift(1), roll.std().shift(1)  # baseline up to t-1, no lookahead
    df["z"] = (df["netVal"] - mu) / sd.where(sd > 1e6)  # sd < 1M VND => dead stock, no signal
    df["room_pct"] = df["currentRoom"] / df["totalRoom"].where(df["totalRoom"] > 0)
    # forward returns: enter adOpen(t+1), exit adClose(t+h)
    for h in HORIZONS:
        df[f"fwd{h}"] = df["adClose"].shift(-h) / df["adOpen"].shift(-1) - 1
    return df


def welch_t(a, b):
    a, b = a.dropna(), b.dropna()
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    return (a.mean() - b.mean()) / np.sqrt(va + vb)


def report(df, mask, label):
    print(f"\n=== {label} ===")
    rows = []
    for h in HORIZONS:
        sig, rest = df.loc[mask, f"fwd{h}"].dropna(), df.loc[~mask, f"fwd{h}"].dropna()
        rows.append({
            "horizon": f"T+{h}", "n_signals": len(sig),
            "sig_mean_%": round(sig.mean() * 100, 3), "base_mean_%": round(rest.mean() * 100, 3),
            "excess_bps": round((sig.mean() - rest.mean()) * 1e4, 1),
            "win_rate_%": round((sig > 0).mean() * 100, 1), "t_stat": round(welch_t(sig, rest), 2),
        })
    print(pd.DataFrame(rows).to_string(index=False))


def selftest():
    s = pd.DataFrame({"netVal": [2e9, -2e9] * 12 + [0.0, 100e9], "adOpen": [1.0] * 26, "adClose": [1.0] * 26,
                      "currentRoom": [1e9] * 26, "totalRoom": [2e9] * 26})
    out = add_signals(s.copy())
    assert out["z"].iloc[-1] > Z_TH, "z-score must flag a 100B-VND spike after flat history"
    assert out["z"].iloc[:LOOKBACK].isna().all(), "no signal before lookback window fills"


def main():
    selftest()
    frames = []
    for sym in UNIVERSE:
        try:
            df = load_symbol(sym)
            if not df.empty:
                frames.append(add_signals(df))
                print(f"{sym}: {len(df)} sessions {df['date'].iloc[0]} -> {df['date'].iloc[-1]}")
        except Exception as e:
            print(f"{sym}: FAILED {e}")
    data = pd.concat(frames, ignore_index=True)
    data["year"] = data["date"].str[:4]

    buy = (data["z"] >= Z_TH) & (data["room_pct"] > ROOM_MIN_PCT)
    sell = data["z"] <= -Z_TH

    report(data, buy, f"BUY signal (z >= {Z_TH}, room > {ROOM_MIN_PCT:.0%}) — pooled all years")
    report(data, sell, f"SELL signal (z <= -{Z_TH}) — pooled all years")
    for y, g in data.groupby("year"):
        report(g, (g["z"] >= Z_TH) & (g["room_pct"] > ROOM_MIN_PCT), f"BUY — {y}")

    out = DATA_DIR / "signals.csv"
    data.loc[buy | sell, ["date", "symbol", "z", "netVal", "room_pct"] + [f"fwd{h}" for h in HORIZONS]].to_csv(out, index=False)
    print(f"\nSignal list saved: {out}")


if __name__ == "__main__":
    main()
