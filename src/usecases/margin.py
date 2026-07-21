"""Dư nợ margin CTCK theo quý (nhập tay từ BCTC — dữ liệu quý, không real-time).
Nguồn: margin.json ở repo root; cập nhật mỗi quý + commit + deploy (nhịp quý nên nhẹ).
Vai trò: bối cảnh vĩ mô 'đòn bẩy hệ thống căng/nới', bổ sung cho khối ngoại + quỹ."""
import json

from src.adapters import presenters
from src.config import ROOT


def _load():
    f = ROOT / "margin.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def margin_message():
    d = _load()
    if not d:
        return "Chưa có dữ liệu margin (cập nhật margin.json mỗi quý từ BCTC CTCK)."
    return presenters.margin_text(d)
