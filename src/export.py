"""Xuat 4 bang du lieu quy tu flows.db ra CSV cho Power BI (spec: docs/metrics/Metrics-Palantir-Fmarket.md).

Usage: python -m src.export [thu_muc]   # mac dinh: export/
Chay moi thang sau khi bot chup danh muc (tu ngay 15), roi refresh PBIX.
"""
import csv
import sqlite3
import sys
from pathlib import Path

from src.config import DB

TABLES = ["fund_holdings", "fund_assets", "fund_industries", "fund_snapshot"]


def main(db_path=None, out_dir=None):
    out = Path(out_dir or (sys.argv[1] if len(sys.argv) > 1 else "export"))
    out.mkdir(exist_ok=True)
    db = sqlite3.connect(str(db_path or DB))
    for t in TABLES:
        cols = [c[1] for c in db.execute(f"PRAGMA table_info({t})")]
        rows = db.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
        with open(out / f"{t}.csv", "w", newline="", encoding="utf-8-sig") as f:  # BOM cho Power BI
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"{out / t}.csv: {len(rows)} dong")


if __name__ == "__main__":
    main()
