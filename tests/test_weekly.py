from datetime import datetime

from src.config import VN_TZ
from src.domain.entities import DayFlow
from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.weekly import make_week_script, week_fusion, week_movers, week_range


class FakeFlows:
    def foreign_daily(self, code, n=10):
        return [DayFlow(f"2026-07-{d:02d}", v * 1e9)
                for d, v in ((13, -100), (14, 50), (15, -200), (16, -30), (17, -120))]

    def ohlc(self, code, n=20):
        return ([1800.0] * 15 + [1850, 1840, 1830, 1820, 1810], [], [])

    def daily_closes(self, code, n=30):
        return [("2026-07-10", 20000), ("2026-07-13", 20500), ("2026-07-17", 21000)]


class FakeLlm:
    def complete(self, system, user):
        self.user = user
        return "[HOOK] Cả tuần xả 400 tỷ.\n[THÂN] Nội dung.\n[KẾT] Hẹn tuần sau. #kn"


def run():
    # thu 7/CN van tra ve tuan vua xong
    assert week_range(datetime(2026, 7, 25, tzinfo=VN_TZ)) == ("2026-07-20", "2026-07-24")
    assert week_range(datetime(2026, 7, 19, tzinfo=VN_TZ)) == ("2026-07-13", "2026-07-17")

    r = SqliteRepo(":memory:")
    # day_story.net = net CA PHIEN (buy-sell cuoi ngay): +5 ty ngay 16, +7 ty ngay 17 -> tuan +12
    for day, buy in (("2026-07-16", 5e9), ("2026-07-17", 7e9)):
        r.insert_snapshots(f"{day}T09:30:00+07:00", [("AAA", 1e9, 0, 0, 0, 0, 20000, 50e9, 1.0)])
        r.insert_snapshots(f"{day}T14:45:00+07:00", [("AAA", buy, 0, 0, 0, 0, 20000, 50e9, 1.0)])
        r.save_day_story(day, "14:15:00")
    assert r.week_net("2026-07-13", "2026-07-17", 1e9) == [("AAA", 12e9)]
    gom, xa = week_movers(r, FakeFlows(), "2026-07-13", "2026-07-17")
    assert xa == [] and gom[0][:3] == ("AAA", 12e9, 21000), gom
    assert abs(gom[0][3] - (21000 / 20000 - 1) * 100) < 1e-9  # % gia tuan: so voi phien TRUOC tuan

    llm = FakeLlm()
    now = datetime(2026, 7, 18, tzinfo=VN_TZ)
    txt = make_week_script(r, FakeFlows(), llm, part=1, now=now)
    assert "Lũy kế cả tuần: -400 tỷ" in llm.user and "AAA +12 tỷ" in llm.user, llm.user
    # closes[-6] = phien thu 6 tu cuoi = thu 6 tuan truoc (1800) -> +0.6%
    assert "VN-Index: 1,810.0 điểm, cả tuần +0.6%" in llm.user, llm.user
    assert "quỹ" not in llm.user, "p1 khong co data quy"
    assert txt.startswith("[HOOK]")
    llm2 = FakeLlm()  # da chot -> khong goi LLM lai
    assert make_week_script(r, FakeFlows(), llm2, part=1, now=now) == txt
    assert not hasattr(llm2, "user")

    # phan 2: hop luu khoi ngoai x quy
    r.save_fund_month("2026-07", [("QA", "AAA", 10, "", 0, 0), ("QB", "AAA", 5, "", 0, 0)], [], [],
                      [(f, "Own", "2026-06", 1000, None, None, None, None, None, 1e11) for f in ("QA", "QB")])
    g2, x2 = week_fusion(r, FakeFlows(), "2026-07-13", "2026-07-17")
    assert g2 == [("AAA", 12e9, 2, g2[0][3])] and x2 == [], (g2, x2)
    llm3 = FakeLlm()
    make_week_script(r, FakeFlows(), llm3, part=2, now=now)
    assert "AAA +12 tỷ, 2 quỹ mở đang nắm" in llm3.user, llm3.user
    assert "Quỹ mở đang nắm nhiều nhất" in llm3.user and "VN-Index" not in llm3.user, llm3.user
    y, w, _ = now.isocalendar()
    assert r.get_meta(f"script:week:{y}-W{w:02d}-p1") and r.get_meta(f"script:week:{y}-W{w:02d}-p2")
    print("test_weekly OK")


if __name__ == "__main__":
    run()
