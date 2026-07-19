from src.infrastructure.fmarket_api import _parse
from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.funds import fund_data, fund_stock_message

SNAP = ("Owner Co", "2026-05", 10000.0, 1.0, 2.0, 3.0, 4.0, 5.0)  # owner..nav_36m


def hold(r, month, holdings, funds=("QA", "QB", "QC")):
    """Luu holdings kem snapshot toi thieu cho cac quy xuat hien."""
    used = sorted({f for f, *_ in holdings})
    r.save_fund_month(month, holdings, [], [], [(f, *SNAP) for f in used])


def run():
    # parse detail Fmarket (fixture, khong can mang)
    d = _parse({"productTopHoldingList": [{"stockCode": "ACB", "netAssetPercent": 12.5, "industry": "Bank"},
                                          {"netAssetPercent": 9.9}],  # thieu stockCode -> bo
                "productAssetHoldingList": [{"assetType": {"name": "Cổ phiếu"}, "assetPercent": 71.5}],
                "productIndustriesHoldingList": [{"industry": "Ngân hàng", "assetPercent": 39.0}],
                "productFund": {"updateAssetHoldingTime": "06/2026"},
                "productNavChange": {"navTo1Months": -2.0, "navTo12Months": 6.4},
                "nav": 27072.0})
    assert d["holdings"] == [("ACB", 12.5, "Bank")] and d["report_month"] == "2026-06", d
    assert d["assets"] == [("Cổ phiếu", 71.5)] and d["industries"] == [("Ngân hàng", 39.0)]
    assert d["nav_chg"] == (-2.0, None, None, 6.4, None) and d["nav"] == 27072.0

    r = SqliteRepo(":memory:")
    assert fund_data(r) is None and not r.has_fund_month("2026-06")
    assert "Chưa có dữ liệu quỹ" in fund_stock_message("AAA", r)

    # thang dau: chua co gi de so -> delta None, khong new/out
    hold(r, "2026-06", [("QA", "AAA", 10, "Bank"), ("QB", "AAA", 5, "Bank"), ("QA", "DDD", 2, "Steel")])
    assert r.has_fund_month("2026-06")
    d = fund_data(r)
    assert d["month"] == "2026-06" and d["rows"][0] == ("AAA", 2, None), d
    assert d["new"] == [] and d["out"] == []

    # thang 2: AAA them 1 quy (+1), CCC moi vao, DDD roi top
    hold(r, "2026-07", [("QA", "AAA", 10, "Bank"), ("QB", "AAA", 5, "Bank"),
                        ("QC", "AAA", 4, "Bank"), ("QA", "CCC", 3, "Tech")])
    d = fund_data(r)
    assert d["rows"][0] == ("AAA", 3, 1) and ("CCC", 1, 1) in d["rows"], d
    assert d["new"] == ["CCC"] and d["out"] == ["DDD"], d

    # repo: consensus sap theo so quy roi tong pct; funds_holding sap theo pct
    assert r.fund_consensus("2026-06") == [("AAA", 2, 15.0), ("DDD", 1, 2.0)]
    assert r.funds_holding("AAA", "2026-07") == [("QA", 10.0), ("QB", 5.0), ("QC", 4.0)]
    assert r.fund_months() == ["2026-06", "2026-07"]
    # re-save thay the tron thang (khong con dong cu o ca 4 bang)
    hold(r, "2026-07", [("QA", "AAA", 11, "Bank")])
    assert r.fund_consensus("2026-07") == [("AAA", 1, 11.0)]

    msg = fund_stock_message("AAA", r)
    assert "1 quỹ" in msg and "QA: 11.0% NAV" in msg, msg
    assert "▼1 so với tháng trước" in msg, msg          # thang truoc 2 quy -> con 1
    assert "Tỷ trọng trung bình: 11.0% NAV" in msg and "kỳ báo cáo 2026-05" in msg, msg
    assert "không nắm" in fund_stock_message("XXX", r)

    # hop luu: trend_ctx co dong quy (flows tra rong -> chi con fund_line; sym rieng tranh cache)
    from src.usecases.build_trend import trend_ctx
    class EmptyFlows:
        def foreign_daily(self, code, n=10):
            return []
    hold(r, "2026-07", [("QA", "QZZ", 9, "Bank"), ("QB", "QZZ", 5, "Bank")])
    ctx = trend_ctx("QZZ", r, EmptyFlows())
    assert "2 quỹ mở" in ctx and "▲2" in ctx, ctx   # thang truoc 0 quy -> +2
    print("test_funds OK")


if __name__ == "__main__":
    run()
