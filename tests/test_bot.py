from src.adapters.bot import handle_updates
from src.infrastructure.sqlite_repo import SqliteRepo

class FakeTg:
    def __init__(self, updates, cfg={"token": "t", "chat_ids": [7]}):
        self.updates, self.sent, self.cfg = updates, [], cfg
    def send_to(self, chat_id, text):
        self.sent.append((chat_id, text))
    def broadcast(self, text):
        return True
    def get_updates(self, offset, wait):
        u, self.updates = self.updates, []
        return u

def upd(i, chat, text):
    return {"update_id": i, "message": {"chat": {"id": chat}, "text": text}}

def run():
    r = SqliteRepo(":memory:")
    tg = FakeTg([upd(1, 7, "/watch hpg"), upd(2, 7, "/list"),
                 upd(3, 99, "/list"), upd(4, 99, "/id"), upd(5, 7, "/help")])
    handle_updates(r, tg, flows=None, llm=None, wait=0)
    assert r.watchlist(7) == {"HPG"} and r.watchlist(99) == set()
    texts = [t for _, t in tg.sent]
    assert any("Đã theo dõi HPG" in t for t in texts)
    assert any(t.startswith("Watchlist của chat này: HPG") for t in texts)
    assert any("Chat id: 99" in t for t in texts)          # /id chay o chat la
    assert sum(c == 99 for c, _ in tg.sent) == 1           # chat la CHI duoc tra loi /id
    assert any("Lệnh của bot" in t for t in texts)
    assert r.get_meta("tg_offset") == "5"
    print("test_bot OK")

if __name__ == "__main__":
    run()
