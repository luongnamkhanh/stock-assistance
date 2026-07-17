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
