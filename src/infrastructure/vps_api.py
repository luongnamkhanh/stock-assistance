"""Nguon du phong khi SSI iBoard chan IP datacenter — VPS feed."""
from src.infrastructure.http import http_json

VPS_LIST = "https://bgapidatafeed.vps.com.vn/getlistallstock"
VPS_DATA = "https://bgapidatafeed.vps.com.vn/getliststockdata/"
_vps_syms = []  # ponytail: cache RAM ca doi process, restart thi lay lai


def _f(x):
    """VPS tra field dang string/None."""
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _vps_row(x):
    """Map 1 record VPS -> tuple snapshot (chua co ts). Don vi: gia tri nghin dong
    (x1000 = VND), gia nghin dong, lot theo lo 10. changePc cua VPS KHONG co dau
    nen pct phai tinh tu gia tham chieu r."""
    last, ref = _f(x.get("lastPrice")), _f(x.get("r"))
    pct = round((last - ref) / ref * 100, 2) if ref else 0.0
    return (x["sym"], _f(x.get("fBValue")) * 1e3, _f(x.get("fSValue")) * 1e3,
            _f(x.get("fBVol")), _f(x.get("fSVolume")), _f(x.get("fRoom")),
            last * 1e3, _f(x.get("lot")) * 10 * _f(x.get("avePrice")) * 1e3, pct)


def fetch_vps():
    """Nguon du phong khi iBoard chan IP datacenter (403 tren Railway).
    Cung feed goc tu so — gia tri khop tuyet doi voi iBoard (da doi chieu)."""
    global _vps_syms
    if not _vps_syms:
        _vps_syms = sorted(s["stock_code"] for s in http_json(VPS_LIST, timeout=30)
                           if s.get("post_to") == "HOSE" and len(s.get("stock_code") or "") == 3)
    rows = []
    for i in range(0, len(_vps_syms), 100):
        rows += [_vps_row(x) for x in http_json(VPS_DATA + ",".join(_vps_syms[i:i + 100]), timeout=30)]
    return rows
