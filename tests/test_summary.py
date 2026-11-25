"""Daily notifications must not resend to successful recipients after a partial failure."""
from datetime import datetime
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.config import VN_TZ
from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.summary import maybe_send_open, maybe_send_summary


class Tg:
    cfg = {"token": "test", "chat_ids": [1, 2, 3]}

    def __init__(self, error):
        self.error, self.sent, self.attempts = error, [], []

    def send_to(self, cid, text):
        self.attempts.append(cid)
        if cid == 2 and self.error:
            raise self.error
        self.sent.append(cid)

    def broadcast(self, text):
        for cid in self.cfg["chat_ids"]:
            self.send_to(cid, text)


def run():
    for kind in ("summary", "open"):
        for code in (403, 500):
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / "flows.db"
                repo = SqliteRepo(path)
                repo.insert_snapshots("2026-11-25T09:15:00+07:00",
                                      [("AAA", 1e9, 0, 0, 0, 0, 20000, 2e9, 1)])
                now = datetime(2026, 11, 25, 15 if kind == "summary" else 9, 20, tzinfo=VN_TZ)
                tg = Tg(HTTPError("https://telegram.invalid", code, "simulated", {}, None))
                def send(r):
                    if kind == "open":
                        maybe_send_open(r, tg, now=now)
                    else:
                        maybe_send_summary(r, None, None, tg)
                with patch("src.usecases.summary.now_vn", return_value=now), \
                     patch("src.usecases.summary.trend_message", return_value="summary"), \
                     patch("src.usecases.summary.market_snapshot", return_value=None), \
                     patch("src.usecases.summary.make_script", side_effect=RuntimeError("offline")):
                    send(repo)
                    assert tg.sent == [1, 3], "one failed chat must not block later recipients"
                    assert repo.get_meta(kind + "_day") == ("2026-11-25" if code == 403 else None)
                    repo.db.close()
                    repo = SqliteRepo(path)  # delivery state must survive a process restart
                    tg.error = None
                    send(repo)
                    send(repo)
                    assert tg.sent == ([1, 3] if code == 403 else [1, 3, 2]), tg.sent
                    assert tg.attempts == ([1, 2, 3] if code == 403 else [1, 2, 3, 2]), tg.attempts
                    assert repo.get_meta(kind + "_day") == "2026-11-25"
                repo.db.close()
    print("test_summary OK")


if __name__ == "__main__":
    run()
