from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.feed_health import feed_fail, feed_ok


class Tg:
    def __init__(self):
        self.sent = []
        self.cfg = {"token": "t", "chat_ids": [7, 8]}
    def send_to(self, cid, text, silent=False, reply_markup=None):
        self.sent.append((cid, text))


def run():
    r, tg = SqliteRepo(":memory:"), Tg()
    # fail lan 1 -> chua bao (nguong 2)
    feed_fail(r, tg)
    assert tg.sent == [] and r.get_meta("poll_fails") == "1"
    # fail lan 2 -> bao mat feed 1 lan, moi chat
    feed_fail(r, tg)
    assert len(tg.sent) == 2 and all("Mất kết nối" in t for _, t in tg.sent), tg.sent
    assert r.get_meta("feed_down") == "1"
    # fail tiep -> KHONG bao lai (da down)
    tg.sent = []
    feed_fail(r, tg)
    assert tg.sent == []
    # poll OK -> bao phuc hoi 1 lan, reset
    feed_ok(r, tg)
    assert len(tg.sent) == 2 and all("phục hồi" in t for _, t in tg.sent), tg.sent
    assert r.get_meta("feed_down") == "0" and r.get_meta("poll_fails") == "0"
    # poll OK khi dang binh thuong -> khong bao gi
    tg.sent = []
    feed_ok(r, tg)
    assert tg.sent == []
    # 1 fail le roi OK -> khong bao (chua dat nguong)
    feed_fail(r, tg)
    tg.sent = []
    feed_ok(r, tg)
    assert tg.sent == [] and r.get_meta("poll_fails") == "0"
    print("test_feed_health OK")


if __name__ == "__main__":
    run()
