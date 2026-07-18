"""Entry point: wiring (composition root) + CLI + vong lap chinh.

Usage:
    python -m src.main --selftest   # chay toan bo tests/
    python -m src.main --once       # 1 poll + report roi thoat
    python -m src.main              # loop (09:00-15:05 VN, T2-T6)
"""
import sys
import time

from src.config import DB, POLL_MINUTES, in_trading_hours, load_config, load_env, now_vn
from src.adapters.bot import handle_updates
from src.infrastructure.hose_feed import HoseFeed
from src.infrastructure.llm import LlmClient
from src.infrastructure.sqlite_repo import SqliteRepo
from src.infrastructure.telegram import TelegramBot
from src.infrastructure.vndirect_api import VnDirect
from src.usecases.detect_alerts import run_once
from src.usecases.funds import maybe_pull_funds
from src.usecases.summary import maybe_send_summary


def build(db_path=None):
    """Composition root — noi DUY NHAT khoi tao class infrastructure."""
    load_env()
    return (SqliteRepo(db_path or DB), HoseFeed(), VnDirect(),
            LlmClient(), TelegramBot(load_config()))


def main():
    if "--selftest" in sys.argv:
        from tests.run_all import main as run_tests
        run_tests()
        return
    repo, feed, flows, llm, tg = build()
    if "--once" in sys.argv:
        run_once(repo, feed, flows, tg)
        return
    print(f"Collector started. Market poll every {POLL_MINUTES}', commands via long-poll. DB: {DB}")
    last_poll = 0.0
    while True:
        tg = TelegramBot(load_config())  # nhu ban goc: sua telegram.json khong can restart
        try:
            handle_updates(repo, tg, flows, llm)  # blocks ~25s, tra ve ngay khi co lenh
        except Exception as e:
            print(f"[{now_vn().isoformat(timespec='seconds')}] commands failed: {e}")
            time.sleep(10)
        if in_trading_hours(now_vn()) and time.time() - last_poll >= POLL_MINUTES * 60:
            try:
                run_once(repo, feed, flows, tg)
            except Exception as e:
                print(f"[{now_vn().isoformat(timespec='seconds')}] poll failed: {e}")
            last_poll = time.time()
        maybe_send_summary(repo, flows, llm, tg)
        maybe_pull_funds(repo, tg)


if __name__ == "__main__":
    main()
