from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.funds import fund_data, fund_stock_message


def run():
    r = SqliteRepo(":memory:")
    assert fund_data(r) is None
    assert "Chưa có dữ liệu quỹ" in fund_stock_message("AAA", r)

    # thang dau: chua co gi de so -> delta None, khong new/out
    r.save_fund_holdings("2026-06", [("QA", "AAA", 10, "Bank"), ("QB", "AAA", 5, "Bank"),
                                     ("QA", "DDD", 2, "Steel")])
    d = fund_data(r)
    assert d["month"] == "2026-06" and d["rows"][0] == ("AAA", 2, None), d
    assert d["new"] == [] and d["out"] == []

    # thang 2: AAA them 1 quy (+1), CCC moi vao, DDD roi top
    r.save_fund_holdings("2026-07", [("QA", "AAA", 10, "Bank"), ("QB", "AAA", 5, "Bank"),
                                     ("QC", "AAA", 4, "Bank"), ("QA", "CCC", 3, "Tech")])
    d = fund_data(r)
    assert d["rows"][0] == ("AAA", 3, 1) and ("CCC", 1, 1) in d["rows"], d
    assert d["new"] == ["CCC"] and d["out"] == ["DDD"], d

    # repo: consensus sap theo so quy roi tong pct; funds_holding sap theo pct
    assert r.fund_consensus("2026-06") == [("AAA", 2, 15.0), ("DDD", 1, 2.0)]
    assert r.funds_holding("AAA", "2026-07") == [("QA", 10.0), ("QB", 5.0), ("QC", 4.0)]
    assert r.fund_months() == ["2026-06", "2026-07"]
    # re-save thay the tron thang (khong con dong cu)
    r.save_fund_holdings("2026-07", [("QA", "AAA", 11, "Bank")])
    assert r.fund_consensus("2026-07") == [("AAA", 1, 11.0)]

    msg = fund_stock_message("AAA", r)
    assert "1 quỹ" in msg and "QA: 11.0% NAV" in msg, msg
    assert "không nắm" in fund_stock_message("XXX", r)
    print("test_funds OK")


if __name__ == "__main__":
    run()
