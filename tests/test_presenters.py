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

    assert "xả dồn 30' cuối" in story_line((-100e9, -45e9, 0))
    assert story_line((5e9, 1e9, 0)) == ""
    assert "room -1.2tr" in story_line((20e9, 1e9, -1_200_000))

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

    # scorecard
    sc = scorecard_text({"ABUY": {5: (1.23, 0.67, 12)}}, 30)
    assert "Tăng tốc GOM" in sc and "+1.2%" in sc and "67%" in sc and "12 tín hiệu" in sc, sc
    assert "chưa có tín hiệu" in scorecard_text({}, 30)
    print("test_presenters OK")

if __name__ == "__main__":
    run()
