"""Dư nợ margin CTCK theo quý (nhập tay từ BCTC — dữ liệu quý, không real-time).
margin.json lưu NHIỀU quý -> Δ so quý trước tự tính, không nhập số phái sinh.
Vai trò: đèn cảnh báo 'đòn bẩy hệ thống căng/nới', ghép với cảnh báo giải chấp real-time."""
import json

from src.adapters import presenters
from src.config import ROOT


def _latest_prev():
    f = ROOT / "margin.json"
    if not f.exists():
        return None, None
    qs = json.loads(f.read_text(encoding="utf-8")).get("quarters") or []
    if not qs:
        return None, None
    return qs[-1], (qs[-2] if len(qs) > 1 else None)


def margin_message():
    latest, prev = _latest_prev()
    if not latest:
        return "Chưa có dữ liệu margin (cập nhật margin.json mỗi quý từ BCTC CTCK)."
    return presenters.margin_text(latest, prev)


def market_tension():
    """1 dòng bối cảnh margin cho cảnh báo giải chấp real-time; None nếu chưa có data."""
    latest, prev = _latest_prev()
    return presenters.margin_tension_line(latest, prev) if latest else None
