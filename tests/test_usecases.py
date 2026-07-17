from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.detect_alerts import detect_accel, detect_spikes, detect_states
from src.usecases.day_story import build_day_story

class NoFlows:                       # FlowHistory cam: trend_ctx -> "" nhu khi API loi
    def foreign_daily(self, code, n=10):
        raise RuntimeError("offline")
    def ohlc(self, code, n=20):
        return ([], [], [])

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
