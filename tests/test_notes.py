from datetime import datetime

from src.config import VN_TZ
from src.infrastructure.sqlite_repo import SqliteRepo
from src.usecases.notes import add_note, maybe_report_notes, notes_message


def snap(r, ts, sym, price):
    r.insert_snapshots(ts, [(sym, 0, 0, 0, 0, 0, price, 100e9, 0)])


class Tg:
    def __init__(self):
        self.sent, self.answered = [], []
        self.cfg = {"token": "t", "chat_ids": [7]}
    def send_to(self, chat_id, text, silent=False, reply_markup=None):
        self.sent.append((chat_id, text))
    def answer_callback(self, cid, text=""):
        self.answered.append(text)


def run():
    r = SqliteRepo(":memory:")
    assert "chưa ghi chú" in notes_message(r, 7)

    # note VNM luc gia 58000
    snap(r, "2026-07-15T10:00:00+07:00", "VNM", 58000)
    msg = add_note(r, 7, "vnm")
    assert "Đã ghi chú VNM" in msg and "58,000" in msg, msg
    assert r.list_notes(7) == [("VNM", r.list_notes(7)[0][1], 58000.0)]

    # gia len 60900 -> /notes hien +5.0%
    snap(r, "2026-07-16T10:00:00+07:00", "VNM", 60900)
    nm = notes_message(r, 7)
    assert "VNM" in nm and "+5.0%" in nm, nm

    # note cua chat khac khong lan
    assert "chưa ghi chú" in notes_message(r, 99)

    # unnote
    r.unnote(7, "VNM")
    assert r.list_notes(7) == []

    # bao lai sau NOTE_REVIEW_DAYS: note ngay 10/07, hom nay 20/07 (>5 ngay) -> due
    r2 = SqliteRepo(":memory:")
    r2.db.execute("INSERT INTO notes (chat_id, symbol, ts, price) VALUES (?,?,?,?)",
                  (7, "HPG", "2026-07-10T10:00:00+07:00", 20000.0))
    r2.db.commit()
    snap(r2, "2026-07-20T14:00:00+07:00", "HPG", 21000)
    tg = Tg()
    # truoc 15:10 -> chua bao
    maybe_report_notes(r2, tg, now=datetime(2026, 7, 20, 14, 0, tzinfo=VN_TZ))
    assert tg.sent == []
    # sau 15:10 -> bao +5.0%, danh dau reported
    maybe_report_notes(r2, tg, now=datetime(2026, 7, 20, 15, 30, tzinfo=VN_TZ))
    assert len(tg.sent) == 1 and tg.sent[0][0] == 7 and "HPG" in tg.sent[0][1] and "+5.0%" in tg.sent[0][1], tg.sent
    # 1 lan/ngay + da reported -> khong bao lai
    tg2 = Tg()
    maybe_report_notes(r2, tg2, now=datetime(2026, 7, 20, 15, 40, tzinfo=VN_TZ))
    assert tg2.sent == []
    # note moi (chua du tuoi) -> khong bao
    r3 = SqliteRepo(":memory:")
    snap(r3, "2026-07-20T10:00:00+07:00", "SSI", 30000)
    add_note(r3, 7, "SSI")
    tg3 = Tg()
    maybe_report_notes(r3, tg3, now=datetime(2026, 7, 20, 15, 30, tzinfo=VN_TZ))
    assert tg3.sent == [], "note hom nay chua du tuoi"

    # nut inline + callback: bam '📌' duoi alert -> note 1 cham
    from src.adapters.presenters import note_buttons
    from src.adapters.bot import _handle_callback
    kb = note_buttons(["VNM", "VNM", "HPG"])          # dedup
    codes = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert codes == ["n:VNM", "n:HPG"], codes
    assert note_buttons([]) is None
    r4 = SqliteRepo(":memory:")
    snap(r4, "2026-07-20T10:00:00+07:00", "FPT", 90000)
    tg4 = Tg()
    cq = {"id": "c1", "data": "n:FPT", "message": {"chat": {"id": 7}}}
    _handle_callback(r4, tg4, cq, [7])
    assert r4.list_notes(7) and r4.list_notes(7)[0][0] == "FPT"
    assert "Đã lưu FPT" in tg4.answered[0]
    # chat la -> khong note
    _handle_callback(r4, tg4, {"id": "c2", "data": "n:FPT", "message": {"chat": {"id": 99}}}, [7])
    assert r4.list_notes(99) == []
    print("test_notes OK")


if __name__ == "__main__":
    run()
