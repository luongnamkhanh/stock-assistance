from datetime import datetime
from src.config import DB, in_trading_hours, load_config, VN_TZ

def run():
    # bien gio giao dich: 08:59 out, 09:00 in, 15:05 in, 15:06 out, T7 out
    assert not in_trading_hours(datetime(2026, 1, 5, 8, 59, tzinfo=VN_TZ))
    assert in_trading_hours(datetime(2026, 1, 5, 9, 0, tzinfo=VN_TZ))
    assert in_trading_hours(datetime(2026, 1, 5, 15, 5, tzinfo=VN_TZ))
    assert not in_trading_hours(datetime(2026, 1, 5, 15, 6, tzinfo=VN_TZ))
    assert not in_trading_hours(datetime(2026, 1, 10, 10, 0, tzinfo=VN_TZ))  # Saturday
    # nghi trua HOSE 11:30-13:00
    assert in_trading_hours(datetime(2026, 1, 5, 11, 29, tzinfo=VN_TZ))
    assert not in_trading_hours(datetime(2026, 1, 5, 11, 30, tzinfo=VN_TZ))
    assert not in_trading_hours(datetime(2026, 1, 5, 12, 59, tzinfo=VN_TZ))
    assert in_trading_hours(datetime(2026, 1, 5, 13, 0, tzinfo=VN_TZ))
    # DB default phai o repo root (canh flows.db hien tai), khong nam trong src/
    assert DB.parent.name != "src", DB
    # load_config doc env var truoc file
    import os
    os.environ["TELEGRAM_TOKEN"] = "t"
    os.environ["TELEGRAM_CHAT_IDS"] = "1, 2"
    try:
        assert load_config() == {"token": "t", "chat_ids": [1, 2]}
    finally:
        del os.environ["TELEGRAM_TOKEN"], os.environ["TELEGRAM_CHAT_IDS"]
    print("test_config OK")

if __name__ == "__main__":
    run()
