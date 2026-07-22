"""User note 1 tin hieu de theo doi -> /notes xem lai (% tu luc note) + bot bao lai sau vai phien.
Bien alert push mot chieu thanh cong cu co trang thai cua user (nhat ky tin hieu ca nhan)."""
from datetime import date, timedelta

from src.adapters import presenters
from src.config import NOTE_REVIEW_DAYS, now_vn


def add_note(repo, chat_id, sym):
    sym = sym.upper()
    row = repo.last_row(sym)  # (price, day_net, pct) tai luc note
    price = row[0] if row else None
    summary = presenters.note_snapshot(row) if row else ""
    repo.add_note(chat_id, sym, now_vn().isoformat(timespec="seconds"), price, summary)
    return presenters.note_added_msg(sym, price, NOTE_REVIEW_DAYS)


def notes_message(repo, chat_id):
    """/notes: moi note kem gia + tom tat tin hieu luc note + % gia toi hien tai."""
    rows = [(s, ts, p0, summary, repo.last_price(s)) for s, ts, p0, summary in repo.list_notes(chat_id)]
    return presenters.notes_list_text(rows)


def maybe_report_notes(repo, tg, now=None):
    """Goi moi vong lap; sau phien (15:10+), 1 lan/ngay bao cac note du tuoi (~NOTE_REVIEW_DAYS
    ngay), gom theo chat -> gui rieng tung chat. `now` inject duoc cho test."""
    now = now or now_vn()
    today = now.date().isoformat()
    if now.weekday() >= 5 or now.hour * 60 + now.minute < 15 * 60 + 10:
        return
    if repo.get_meta("notes_report_day") == today:
        return
    cutoff = (date.fromisoformat(today) - timedelta(days=NOTE_REVIEW_DAYS)).isoformat()
    due = repo.notes_due(cutoff)
    by_chat = {}
    for chat_id, sym, ts, p0, summary in due:
        cur = repo.last_price(sym)
        pct = (cur / p0 - 1) * 100 if p0 and cur else None
        by_chat.setdefault(chat_id, []).append((sym, ts, pct, summary))
        repo.mark_note_reported(chat_id, sym, ts)
    for chat_id, items in by_chat.items():
        try:
            tg.send_to(chat_id, presenters.note_report_text(items))
        except Exception as e:
            print(f"[{now.isoformat(timespec='seconds')}] note report failed ({chat_id}): {e}")
    repo.set_meta("notes_report_day", today)
