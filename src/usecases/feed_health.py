"""Cảnh báo khi MẤT / KHÔI PHỤC data feed — phân biệt 'bot mù' (mất data) với
'thị trường yên' (không tín hiệu). Trạng thái lưu meta để bền qua restart."""
FEED_FAIL_ALERT = 2   # poll fail lien tiep >= 2 -> bao mat feed (1 lan)


def _broadcast(tg, text):
    for cid in tg.cfg.get("chat_ids", []):
        try:
            tg.send_to(cid, text)
        except Exception:
            pass


def feed_ok(repo, tg):
    """Poll thanh cong -> neu dang bao mat feed thi bao phuc hoi + reset dem."""
    if repo.get_meta("feed_down") == "1":
        repo.set_meta("feed_down", "0")
        _broadcast(tg, "✅ Dữ liệu thị trường đã phục hồi — bot theo dõi lại bình thường.")
    if (repo.get_meta("poll_fails") or "0") != "0":
        repo.set_meta("poll_fails", "0")


def feed_fail(repo, tg):
    """Poll that bai -> dem fail lien tiep; dat nguong thi bao mat feed 1 lan."""
    n = int(repo.get_meta("poll_fails") or "0") + 1
    repo.set_meta("poll_fails", str(n))
    if n >= FEED_FAIL_ALERT and repo.get_meta("feed_down") != "1":
        repo.set_meta("feed_down", "1")
        _broadcast(tg, "⚠️ Mất kết nối dữ liệu thị trường — bot tạm thời không theo dõi được, "
                       "sẽ báo lại khi phục hồi. (Không phải thị trường yên.)")
