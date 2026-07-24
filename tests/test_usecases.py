from datetime import datetime

from src.config import VN_TZ
from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.detect_alerts import detect_accel, detect_spikes, detect_states
from src.usecases.summary import maybe_send_open

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
    assert len(msgs) == 1 and "GOM" in msgs[0][1] and "CHỮNG" not in msgs[0][1], msgs
    assert "Cả phiên" in msgs[0][1] and "Giá 20,000" in msgs[0][1], msgs
    assert msgs[0][0] == "AAA" and msgs[0][2] is False, "khong watch -> khong phai wl_only"
    assert msgs[0][3] is False, "GOM khong du quy nam -> khong loud (im lang)"
    snap(r, f"{day}T10:30:00+07:00", "AAA", 20.1e9)
    msgs = detect_states(r, F, f"{day}T10:30:00+07:00", set())
    assert len(msgs) == 1 and "CHỮNG" in msgs[0][1], msgs
    snap(r, f"{day}T11:00:00+07:00", "AAA", 20.2e9)
    assert detect_states(r, F, f"{day}T11:00:00+07:00", set()) == []

    # cua so 30' de len khoang trong nghi trua -> khong danh gia (chong 'chung lai' gia luc 13:0x)
    r8 = SqliteRepo(":memory:")
    snap(r8, f"{day}T11:28:00+07:00", "GGG", 20e9)
    snap(r8, f"{day}T13:05:00+07:00", "GGG", 20.1e9)
    assert detect_states(r8, F, f"{day}T13:05:00+07:00", set()) == [], "gap nghi trua -> skip"

    snap(r, f"{day}T10:10:00+07:00", "AAA", 26.5e9, dv=120e9)   # net 6.5 / GTGD ngay 120 = 5.4% >= gate 5% (bible §5.2)
    msgs = detect_spikes(r, F, f"{day}T10:10:00+07:00", set())
    assert len(msgs) == 1 and "AAA" in msgs[0][1] and "mua ròng" in msgs[0][1], msgs
    assert "thỏa thuận" not in msgs[0][1] and msgs[0][2] is False
    assert msgs[0][3] is False, "spike le, offline khong xac nhan setup da phien -> khong loud (bible §4)"
    assert detect_spikes(r, F, f"{day}T10:10:00+07:00", set()) == [], "cooldown"

    # wl_only: chi qua nguong NHO watchlist -> flag True; khong watch thi khong co alert nao
    r6 = SqliteRepo(":memory:")
    snap(r6, f"{day}T10:00:00+07:00", "WLS", 1e9, dv=38e9)
    snap(r6, f"{day}T10:10:00+07:00", "WLS", 3e9, dv=40e9)   # net 2 ty: >=1.5 (wl) nhung <3 (day)
    out = detect_spikes(r6, F, f"{day}T10:10:00+07:00", {"WLS"})
    assert len(out) == 1 and out[0][0] == "WLS" and out[0][2] is True, out
    r7 = SqliteRepo(":memory:")
    snap(r7, f"{day}T10:00:00+07:00", "WLS", 1e9, dv=38e9)
    snap(r7, f"{day}T10:10:00+07:00", "WLS", 3e9, dv=40e9)
    assert detect_spikes(r7, F, f"{day}T10:10:00+07:00", set()) == []

    r2 = SqliteRepo(":memory:")
    dvs = {"10:00": 100e9, "10:05": 110e9, "10:10": 120e9, "10:15": 140e9}
    big = {"10:00": 100e9, "10:05": 300e9, "10:10": 600e9, "10:15": 1000e9}
    for hhmm, bbb, ccc in (("10:00", 1e9, 1e9), ("10:05", 2.2e9, 6e9),
                           ("10:10", 4.9e9, 8e9), ("10:15", 9.9e9, 9e9)):
        for sym, buy, dv in (("BBB", bbb, dvs[hhmm]), ("CCC", ccc, dvs[hhmm]), ("EEE", bbb, big[hhmm])):
            snap(r2, f"{day}T{hhmm}:00+07:00", sym, buy, dv=dv, pct=1.0)
    msgs = detect_accel(r2, F, f"{day}T10:15:00+07:00", set())
    assert len(msgs) == 1 and "BBB" in msgs[0][1] and "TĂNG TỐC" in msgs[0][1], msgs
    assert "1.2 → 2.7 → 5.0" in msgs[0][1] and "Cả phiên" in msgs[0][1] and msgs[0][2] is False, msgs
    assert msgs[0][3] is True, "tang toc luon loud (keu chuong)"
    assert detect_accel(r2, F, f"{day}T10:15:00+07:00", set()) == [], "cooldown accel"

    # spike thoa thuan (share > 80%) -> loud du khong watch, khong du quy
    r9 = SqliteRepo(":memory:")
    snap(r9, f"{day}T10:00:00+07:00", "TT1", 1e9, dv=100e9)
    snap(r9, f"{day}T10:10:00+07:00", "TT1", 10e9, dv=110e9)   # net 9 ty / win_value 10 ty = 90% share
    out = detect_spikes(r9, F, f"{day}T10:10:00+07:00", set())
    assert len(out) == 1 and out[0][3] is True and "thỏa thuận" in out[0][1], out

    # bible §2/§6: XA (diem thoat) -> loud du khong quy nao nam; va exit_th=10 nhay hon (day_net -13 < -10 nhung > -15)
    rx = SqliteRepo(":memory:")
    snap(rx, f"{day}T09:30:00+07:00", "XXX", 0, sell=6e9)
    snap(rx, f"{day}T10:00:00+07:00", "XXX", 0, sell=13e9)   # day_net -13e9, 30' qua -7e9
    mx = detect_states(rx, F, f"{day}T10:00:00+07:00", set())
    assert len(mx) == 1 and "XẢ" in mx[0][1] and mx[0][3] is True, mx   # XA -> loud (thoat keu ngang vao)

    # bible §4/§5.4: trend_side = chieu chuoi phien lien tiep (>=2) -> "setup da phien" cho _continues
    from src.domain.entities import DayFlow
    from src.usecases.build_trend import _daily_cache, trend_side
    class BuyFlows:                       # 2 phien mua lien tiep cuoi -> lean "mua"
        def foreign_daily(self, code, n=10):
            return [DayFlow("2026-01-01", -1e9), DayFlow("2026-01-02", 5e9), DayFlow("2026-01-03", 6e9)]
    class ChopFlows:                      # dao lien tuc -> streak 1 -> None
        def foreign_daily(self, code, n=10):
            return [DayFlow("2026-01-01", 5e9), DayFlow("2026-01-02", -3e9), DayFlow("2026-01-03", 4e9)]
    _daily_cache.clear()
    assert trend_side("ZZ1", r, BuyFlows()) == "mua"
    _daily_cache.clear()
    assert trend_side("ZZ2", r, ChopFlows()) is None
    _daily_cache.clear()
    assert trend_side("ZZ3", r, NoFlows()) is None      # API loi -> None, khong chan

    # nhip tim dau phien: 1 lan/ngay, chi trong cua so 09:15-10:00, can snapshot hom nay
    class Tg:
        sent = []
        cfg = {"token": "t", "chat_ids": [7]}
        def broadcast(self, text):
            self.sent.append(text)
    r4, tg = SqliteRepo(":memory:"), Tg()
    at = lambda h, m: datetime(2026, 1, 5, h, m, tzinfo=VN_TZ)  # thu 2
    snap(r4, "2026-01-05T09:14:00+07:00", "AAA", 9e9, sell=2e9)
    maybe_send_open(r4, tg, now=at(9, 10))
    assert tg.sent == [], "truoc 09:15 chua gui"
    maybe_send_open(r4, tg, now=at(9, 20))
    assert len(tg.sent) == 1 and "Mở phiên 05/01" in tg.sent[0] and "mua ròng 7 tỷ" in tg.sent[0], tg.sent
    assert "1/1 mã xanh" in tg.sent[0] and "1 mã HOSE" in tg.sent[0], tg.sent
    maybe_send_open(r4, tg, now=at(9, 25))
    assert len(tg.sent) == 1, "1 lan/ngay"
    r5 = SqliteRepo(":memory:")
    snap(r5, "2026-01-05T09:14:00+07:00", "AAA", 9e9)
    maybe_send_open(r5, tg, now=at(10, 30))
    assert len(tg.sent) == 1, "qua 10:00 khong gui muon"

    # forcesell: >= FORCESELL_MIN_STOCKS ma san VA tong GTGD san >= FORCESELL_MIN_GTGD -> broadcast 1 lan/ngay
    from src.config import FORCESELL_MIN_GTGD, FORCESELL_MIN_STOCKS
    from src.usecases.detect_alerts import maybe_forcesell

    class FTg:
        def __init__(self):
            self.sent, self.cfg = [], {"token": "t", "chat_ids": [7]}
        def send_to(self, cid, text, silent=False, reply_markup=None):
            self.sent.append((cid, text))

    fts = f"{day}T10:30:00+07:00"
    big_dv = FORCESELL_MIN_GTGD / FORCESELL_MIN_STOCKS + 1e9   # moi ma du keo tong qua nguong
    r10 = SqliteRepo(":memory:")
    for i in range(FORCESELL_MIN_STOCKS):
        snap(r10, fts, f"F{i:02d}", 1e9, dv=big_dv, pct=-6.8)  # gan san, GTGD lon
    snap(r10, fts, "GRN", 1e9, dv=big_dv, pct=1.0)             # xanh -> khong tinh
    snap(r10, fts, "PNY", 1e9, dv=1e9, pct=-6.9)               # san nhung GTGD nho -> loai
    tgf = FTg()
    maybe_forcesell(r10, tgf, fts)
    assert len(tgf.sent) == 1 and "giảm sàn" in tgf.sent[0][1] and "tổng GTGD" in tgf.sent[0][1], tgf.sent
    maybe_forcesell(r10, tgf, fts)
    assert len(tgf.sent) == 1, "1 lan/ngay"
    # du so ma nhung tong GTGD duoi nguong -> khong bao (cot loi cua doi logic: do tien, khong dem dau ma)
    r11 = SqliteRepo(":memory:")
    for i in range(FORCESELL_MIN_STOCKS + 2):
        snap(r11, fts, f"S{i:02d}", 1e9, dv=100e9, pct=-6.8)
    tgf2 = FTg()
    maybe_forcesell(r11, tgf2, fts)
    assert tgf2.sent == []
    print("test_usecases OK")

if __name__ == "__main__":
    run()
