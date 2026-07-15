"""Test 3 stronger signal variants on the cached data. Run after backtest.py.

V1 streak    : foreign net-buy > 0 for 5 consecutive sessions (flow persistence)
V2 flow-lead : z >= 2 AND same-day price barely moved (< +1%) — flow before the herd
V3 xs-rank   : top-5 stocks per day by netVal / 20d avg traded value (cross-sectional)

Metric: alpha_bps = mean of DATE-DEMEANED forward return on signal days
(controls for market-wide moves), with one-sample t-stat. T+1 shown for
reference only — not executable under T+2.5 settlement.
"""

import numpy as np
import pandas as pd

from backtest import HORIZONS, ROOM_MIN_PCT, UNIVERSE, Z_TH, add_signals, load_symbol


def prep():
    frames = []
    for sym in UNIVERSE:
        df = add_signals(load_symbol(sym))
        df["ret_t"] = df["adClose"].pct_change()
        df["streak5"] = (df["netVal"] > 0).rolling(5).sum() == 5
        volcol = "nmVolume" if "nmVolume" in df.columns else "nmVol"
        tval = (df["average"] * df[volcol] * 1000).rolling(20).mean().shift(1)
        df["fnorm"] = df["netVal"] / tval.where(tval > 0)
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    data["year"] = data["date"].str[:4]
    for h in HORIZONS:  # demean by date: strip market-wide move
        data[f"dm{h}"] = data[f"fwd{h}"] - data.groupby("date")[f"fwd{h}"].transform("mean")
    data["xrank"] = data.groupby("date")["fnorm"].rank(ascending=False)
    return data


def report(data, mask, label, by_year=False):
    print(f"\n=== {label} ===")
    rows = []
    for h in HORIZONS:
        s = data.loc[mask, f"dm{h}"].dropna()
        t = s.mean() / (s.std(ddof=1) / np.sqrt(len(s))) if len(s) > 2 else np.nan
        rows.append({"horizon": f"T+{h}", "n": len(s), "alpha_bps": round(s.mean() * 1e4, 1),
                     "t_stat": round(t, 2), "win>mkt_%": round((s > 0).mean() * 100, 1)})
    print(pd.DataFrame(rows).to_string(index=False))
    if by_year:
        rows = []
        for y, g in data.groupby("year"):
            s = g.loc[mask.reindex(g.index, fill_value=False), "dm3"].dropna()
            if len(s) > 2:
                t = s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))
                rows.append({"year": y, "n": len(s), "alpha_T3_bps": round(s.mean() * 1e4, 1),
                             "t_stat": round(t, 2)})
        print(pd.DataFrame(rows).to_string(index=False))


def main():
    data = prep()
    room_ok = data["room_pct"] > ROOM_MIN_PCT

    report(data, (data["z"] >= Z_TH) & room_ok, "V0 baseline: z >= 2 (date-demeaned, for comparison)")
    report(data, data["streak5"] & room_ok, "V1 streak: 5 consecutive net-buy sessions", by_year=True)
    report(data, (data["z"] >= Z_TH) & (data["ret_t"] < 0.01) & room_ok,
           "V2 flow-lead: z >= 2 AND same-day return < +1%", by_year=True)
    report(data, (data["xrank"] <= 5) & (data["fnorm"] > 0) & room_ok,
           "V3 xs-rank: top-5/day by flow-to-liquidity", by_year=True)


if __name__ == "__main__":
    main()
