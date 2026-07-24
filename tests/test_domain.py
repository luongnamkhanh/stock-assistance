from src.domain.entities import TrendStats
from src.domain.signals import classify_regime, is_accel, is_locked, spike_share, trend_stats

TH = dict(day_net_th=15e9, rate_th=1e9)

def run():
    # regime (tu selftest detect_states cu): gom deu -> GOM; delta thu hep -> GOM_CHUNG
    assert classify_regime(20e9, 10e9, 1.0, **TH) == "GOM"
    assert classify_regime(20.1e9, 0.1e9, 1.0, **TH) == "GOM_CHUNG"
    assert classify_regime(-20e9, -10e9, 1.0, **TH) == "XA"
    assert classify_regime(-20e9, -0.5e9, 1.0, **TH) == "XA_CHUNG"
    assert classify_regime(5e9, 5e9, 1.0, **TH) == "NEUTRAL"
    assert classify_regime(8e9, 5e9, 0.5, **TH) == "GOM"      # watchlist: nguong /2
    # bible §2: exit_th thap hon -> XA fire som hon (thoat nhay); mac dinh doi xung
    assert classify_regime(-12e9, -5e9, 1.0, day_net_th=15e9, rate_th=1e9, exit_th=10e9) == "XA"     # -12 <= -10
    assert classify_regime(-12e9, -5e9, 1.0, **TH) == "NEUTRAL"                                       # exit_th mac dinh 15 -> chua toi
    assert classify_regime(-12e9, -0.5e9, 1.0, day_net_th=15e9, rate_th=1e9, exit_th=10e9) == "XA_CHUNG"

    # spike (tu selftest cu): 5 ty / win 20 ty = share 25% -> spike
    SP = dict(min_day_value=30e9, min_net=3e9, min_share=0.15)
    assert abs(spike_share(5e9, 20e9, 120e9, 1.0, **SP) - 0.25) < 1e-9
    assert spike_share(2e9, 20e9, 120e9, 1.0, **SP) is None    # net < 3 ty
    assert spike_share(5e9, 40e9, 120e9, 1.0, **SP) is None    # share < 15%
    assert spike_share(5e9, 20e9, 20e9, 1.0, **SP) is None     # GTGD ngay < 30 ty
    assert spike_share(5e9, 0, 120e9, 1.0, **SP) is None       # win_value <= 0
    # bible §5.2: gate day-share — net phai dang ke so voi GTGD NGAY, khong chi ap dao 1 window mong
    SP2 = dict(min_day_value=30e9, min_net=3e9, min_share=0.15, min_day_share=0.05)
    assert spike_share(4.2e9, 8e9, 100e9, 1.0, **SP2) is None          # 4.2/100=4.2% < 5% day-share (ca FRT) du share window 52%
    assert abs(spike_share(6e9, 12e9, 100e9, 1.0, **SP2) - 0.5) < 1e-9  # 6/100=6% >= 5% -> qua
    assert spike_share(4.2e9, 8e9, 100e9, 0.5, **SP2) is not None       # watchlist: gate *0.5=2.5% -> qua

    # accel (tu selftest cu): 1.2 -> 2.7 -> 5.0 tang dan, share 25% -> True
    AC = dict(min_day_value=30e9, min_last=1.5e9, min_share=0.10)
    assert is_accel(1.2e9, 2.7e9, 5e9, 20e9, 140e9, 1.0, **AC)
    assert not is_accel(5e9, 2.9e9, 0.9e9, 20e9, 140e9, 1.0, **AC)   # giam toc
    assert not is_accel(1.2e9, 2.7e9, 5e9, 400e9, 1000e9, 1.0, **AC) # chim trong GTGD
    assert not is_accel(1.2e9, -2.7e9, 5e9, 20e9, 140e9, 1.0, **AC)  # khac dau

    # is_locked (san cung): GTGD 1 nhip tang qua nho so tong -> du ban khong khop
    assert is_locked(1000e9, 998e9, 0.005) is True     # +2 ty / 1000 ty = 0.2% < 0.5%
    assert is_locked(1000e9, 980e9, 0.005) is False    # +20 ty = 2% -> con khop
    assert is_locked(1000e9, None, 0.005) is False     # chua co nhip truoc -> khong ket luan
    assert is_locked(0, 0, 0.005) is False             # chua giao dich -> khong ket luan

    # trend_stats: 7 ban + 3 mua -> DAO_CHIEU that; outlier 1 phien -> KHONG dao chieu
    t = trend_stats([-5e9] * 7 + [3e9, 4e9, 6e9])
    assert isinstance(t, TrendStats)
    assert t.momo == "DAO_CHIEU" and t.streak == 3 and t.streak_side == "mua"
    t2 = trend_stats([-50e9] * 7 + [139e9, -13e9, -4e9])       # case HPG 07/2026
    assert t2.momo != "DAO_CHIEU" and t2.streak == 2 and t2.streak_side == "bán"
    t3 = trend_stats([-5e9] * 7 + [3e9])
    assert t3.flipped                                           # vua flip phien cuoi
    print("test_domain OK")

if __name__ == "__main__":
    run()
