from src.domain.entities import Accel, DayFlow, Spike
from src.adapters.presenters import (accel_msg, ctx_line, format_trend, fund_line, price_line,
                                     range_line, scorecard_text, spike_msg, story_line,
                                     top_movers_text, trend_ctx_line)

def flows(vals, month="01"):
    return [DayFlow(f"2026-{month}-{i+1:02d}", v) for i, v in enumerate(vals)]

def run():
    msg = format_trend("TEST", flows([-5e9] * 7 + [3e9, 4e9, 6e9]))
    assert "3 phiên mua ròng liên tiếp" in msg and "🟥" * 7 + "🟩" * 3 in msg, msg
    assert "ĐẢO CHIỀU" in msg and "(+3, +4, +6)" in msg, msg
    assert "ĐẢO CHIỀU" in format_trend("TEST", flows([-5e9] * 7 + [3e9]))   # vua flip
    m3 = format_trend("TEST", flows([-50e9] * 7 + [139e9, -13e9, -4e9], "02"),
                      "Giá: 22,200đ | phiên nay +0.0%")
    assert "ĐẢO CHIỀU" not in m3 and "(+139, -13, -4)" in m3 and "Giá: 22,200đ" in m3, m3
    assert "Giá:" not in format_trend("TEST", flows([-50e9] * 7 + [139e9, -13e9, -4e9], "02"))
    assert format_trend("X", []) == "Không có dữ liệu khối ngoại cho X."

    ctx = trend_ctx_line(flows([-5e9, -7e9, -3e9, -8e9, -9e9]))
    assert "🟥🟥🟥🟥🟥" in ctx and "-32" in ctx and "5 phiên bán ròng liên tiếp" in ctx, ctx
    assert trend_ctx_line([]) == ""
    mixed = trend_ctx_line(flows([5e9, -2e9, 3e9]))
    assert "🟩🟥🟩" in mixed and "liên tiếp" not in mixed, mixed

    s = spike_msg(Spike("AAA", 5e9, 0.25, 20000, 1.5, 25.2e9))
    assert "AAA" in s and "mua ròng" in s and "Cả phiên" in s and "Giá 20,000" in s, s
    assert "thỏa thuận" not in s
    assert "thỏa thuận" in spike_msg(Spike("AAA", 5e9, 0.85, 20000, 1.5, 25.2e9))

    a = accel_msg(Accel("BBB", (1.2e9, 2.7e9, 5e9), 9.9e9, 20000, 1.0))
    assert "BBB" in a and "TĂNG TỐC" in a and "1.2 → 2.7 → 5.0" in a, a

    s = story_line(("2026-01-16", -100e9, -45e9, 0))
    assert "xả dồn 30' cuối" in s and "Phiên trước (16/01)" in s, s
    assert story_line(("2026-01-16", 5e9, 1e9, 0)) == ""
    s = story_line(("2026-01-16", 20e9, 1e9, -1_200_000))
    assert "room ngoại giảm 1.2tr cp (gom thêm" in s, s
    assert "nhả bớt" in story_line(("2026-01-16", 20e9, 1e9, 800_000))

    assert "Cả phiên: mua ròng 25.2 tỷ" in ctx_line(25.2e9, 20000, 1.5)
    # closes don vi VND (ohlc chuan hoa tai nguon); index van la diem
    assert "22,200đ" in price_line("HPG", [23100, 22200]) and "điểm" in price_line("VNINDEX", [1800.0])
    assert price_line("HPG", []) == ""
    t = top_movers_text([("AAA", 8e9), ("BBB", -5e9)])
    assert "Top gom hôm nay: AAA +8 tỷ" in t and "Top xả hôm nay: BBB -5 tỷ" in t, t
    assert top_movers_text([]) == ""

    # bien 4 tuan: dinh/day 20 phien + vi tri gia — co phieu don vi dong, index don vi diem
    closes = [22000] * 19 + [22200]
    highs = [22500] * 19 + [23900]   # dinh 23,900
    lows = [21600] + [21900] * 19    # day 21,600
    r = range_line("HPG", closes, highs, lows)
    assert "21,600 – 23,900" in r and "cách đáy +2.8%" in r and "cách đỉnh -7.1%" in r, r
    ri = range_line("VNINDEX", [1790.0] * 20, [1810.5] * 20, [1750.2] * 20)
    assert "1,750.2 – 1,810.5 điểm" in ri, ri
    assert range_line("HPG", [], [], []) == ""
    assert range_line("HPG", [22000] * 5, [22500] * 5, [21500] * 5) == "", "du lieu mong -> khong ve hop"

    # hop luu quy mo
    assert fund_line(0, None) == "" and fund_line(0, 2) == ""
    assert "27 quỹ mở" in fund_line(27, None) and "tháng này" not in fund_line(27, None)
    assert "▲2" in fund_line(12, 2) and "▼1" in fund_line(12, -1) and "tháng này" not in fund_line(12, 0)
    full = fund_line(15, 2, 5.24, "ACB", 320e9)
    assert "TB 5.2% NAV" in full and "/fund ACB để soi" in full and "tổng 320 tỷ" in full, full
    assert "NAV" not in fund_line(15, None) and "/fund" not in fund_line(15, None)
    assert "tổng" not in fund_line(15, None, 5.0, "ACB", 0), "thang cu chua co value -> khong hien tong"

    # scorecard
    sc = scorecard_text({"ABUY": {5: (1.23, 0.67, 12)}}, 30)
    assert "Tăng tốc GOM" in sc and "+1.2%" in sc and "67%" in sc and "12 tín hiệu" in sc, sc
    assert "chưa có tín hiệu" in scorecard_text({}, 30)

    # forcesell (+ tension optional)
    from src.adapters.presenters import forcesell_msg, margin_text, margin_tension_line
    fs = forcesell_msg("2026-07-20T14:05:00+07:00", [("VIX", -6.9, 800e9), ("SHB", -6.7, 700e9)], 1500e9)
    assert "2 mã" in fs and "VIX -6.9%" in fs and "giải chấp" in fs and "khuyến nghị" in fs, fs
    assert "1,500 tỷ" in fs, fs
    assert "Bối cảnh" not in fs, "khong tension -> khong dong boi canh"
    fs2 = forcesell_msg("2026-07-20T14:05:00+07:00", [("VIX", -6.9, 800e9)], 800e9, "Bối cảnh: dư nợ ~445,000 tỷ")
    assert "Bối cảnh: dư nợ" in fs2, fs2

    # margin full: Δ tu tinh + ty le margin/von hoa + vi tri lich su + doc nhanh
    qs = [
        {"quarter": "Q3/2025", "market_total_ty": 300000, "market_cap_ty": 5200000, "brokers": []},
        {"quarter": "Q1/2026", "market_total_ty": 415000, "market_cap_ty": 5900000, "brokers": []},
        {"quarter": "Q2/2026", "market_total_ty": 445000, "market_cap_ty": 6100000,
         "brokers": [{"n": "TCBS", "debt": 44147}, {"n": "SSI", "debt": 36585, "equity": 30000}]},
    ]
    mt = margin_text(qs)
    assert "TCBS: 44,147 tỷ (10% thị phần)" in mt and "445,000" in mt and "122% VCSH" in mt, mt
    assert "▲30,000 tỷ (+7% so Q1/2026)" in mt, mt
    assert "Margin/vốn hoá TT: 7.3% — cao nhất trong 3 quý" in mt, mt   # 445000/6100000=7.3%, cao nhat
    assert "💡 Đọc nhanh" in mt and "tăng 2 quý liên tiếp" in mt and "thận trọng" in mt, mt
    # 1 quy (khong Δ, khong vi tri) van chay
    assert "445,000" in margin_text([qs[-1]]) and "so " not in margin_text([qs[-1]]).split("nguồn")[1]
    # thieu von hoa -> khong co dong ty le/doc nhanh
    noc = margin_text([{"quarter": "Q2/2026", "market_total_ty": 445000, "brokers": []}])
    assert "Margin/vốn hoá" not in noc and "Đọc nhanh" not in noc, noc
    tl = margin_tension_line(qs)
    assert "445,000 tỷ" in tl and "margin/vốn hoá 7.3%" in tl, tl
    print("test_presenters OK")

if __name__ == "__main__":
    run()
