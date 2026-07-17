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
    # top_net_full (video.py top_mover_rows): net + price + pct cho snapshot ts do
    snap(r, f"{day}T10:10:00+07:00", "AAA", 25.2e9, day_value=120e9)
    assert r.top_net_full(f"{day}T10:10:00+07:00") == [("AAA", 25.2e9, 20000, 1.5)]
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
