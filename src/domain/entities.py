"""Data object di qua ranh gioi layer. Frozen — domain khong co state."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DayFlow:                # 1 phien khoi ngoai da chot (tu VNDirect)
    trading_date: str         # "2026-07-17"
    net_val: float            # VND, co the am


@dataclass(frozen=True)
class TrendStats:             # phan tich chuoi phien — SO, khong text
    cum: float
    buys: int
    last3: tuple
    momo: str                 # DAO_CHIEU | MANH | YEU | ON_DINH
    streak: int
    streak_side: str          # "mua" | "bán"
    flipped: bool


@dataclass(frozen=True)
class Spike:
    symbol: str
    net: float
    share: float
    price: float
    pct: float
    day_net: float


@dataclass(frozen=True)
class Accel:
    symbol: str
    deltas: tuple             # (d1, d2, d3)
    day_net: float
    price: float
    pct: float


@dataclass(frozen=True)
class RegimeChange:
    symbol: str
    regime: str               # GOM | GOM_CHUNG | XA | XA_CHUNG
    recent: float
    day_net: float
    price: float
    pct: float
