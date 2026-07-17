"""Poll HOSE 1 lan va luu snapshot (collector.py:204-222). Try/except iBoard->VPS
da nam trong HoseFeed.fetch_hose — usecase khong can try nua."""
from src.config import now_vn


def poll(repo, feed):
    rows = feed.fetch_hose()
    ts = now_vn().isoformat(timespec="seconds")
    repo.insert_snapshots(ts, rows)
    return ts, len(rows)
