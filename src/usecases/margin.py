"""Dư nợ margin CTCK theo quý (nhập tay từ BCTC — dữ liệu quý, không real-time).
margin.json lưu NHIỀU quý + vốn hoá TT -> Δ, tỷ lệ margin/vốn hoá, vị trí lịch sử, đọc nhanh
đều tự tính. Vai trò: đèn cảnh báo 'đòn bẩy hệ thống căng/nới' — nhiệt kế rủi ro giải chấp."""
import json

from src.adapters import presenters
from src.config import ROOT


def _quarters():
    f = ROOT / "margin.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("quarters") or []


def margin_message():
    qs = _quarters()
    if not qs:
        return "Chưa có dữ liệu margin (cập nhật margin.json mỗi quý từ BCTC CTCK)."
    return presenters.margin_text(qs)


def market_tension():
    """1 dòng bối cảnh margin cho cảnh báo giải chấp real-time + video; None nếu chưa có data."""
    qs = _quarters()
    return presenters.margin_tension_line(qs) if qs else None
