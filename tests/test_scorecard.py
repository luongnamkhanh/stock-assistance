from src.usecases.scorecard import score


def run():
    # 12 phien lien tuc, gia tang 1 gia/ngay: 100, 101, ... 111
    series = [(f"2026-01-{d:02d}", 100.0 + d) for d in range(1, 13)]
    closes = lambda sym: series if sym == "AAA" else []

    alerts = [("2026-01-05T10:00:00+07:00", "AAA", "BUY"),     # base 105 -> +5: 110 (+4.76%), +10: het data
              ("2026-01-05T10:30:00+07:00", "AAA", "ASELL"),   # gia van tang -> nguoc chieu, win 0
              ("2026-01-05T11:00:00+07:00", "XXX", "BUY")]     # khong co gia -> bo qua
    st = score(alerts, closes)
    avg, wr, n = st["BUY"][5]
    assert n == 1 and wr == 1.0 and abs(avg - (110 / 105 - 1) * 100) < 1e-9, st
    assert 10 not in st["BUY"], "chua du 10 phien sau alert -> khong cham"
    assert st["ASELL"][5][1] == 0.0, "gia tang sau tin hieu XA -> khong win"
    # alert ngay nghi (07 khong co phien? co — chuoi lien tuc; thu ts giua 2 phien: base = phien gan nhat truoc do)
    st2 = score([("2026-01-05T10:00:00+07:00", "AAA", "SELL")], closes, horizons=(3,))
    assert st2["SELL"][3][2] == 1
    assert score([], closes) == {}
    print("test_scorecard OK")


if __name__ == "__main__":
    run()
