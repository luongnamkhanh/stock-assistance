"""Cong (ports) cho cac nguon du lieu ngoai + LLM + Telegram. Usecase chi biet
interface nay, khong biet iBoard/VPS/VNDirect/Claude/Gemini/Bot API cu the."""
from abc import ABC, abstractmethod


class MarketFeed(ABC):
    @abstractmethod
    def fetch_hose(self): ...   # -> list[tuple 9 cot] (sym, buy_val, sell_val, buy_qtty, sell_qtty, room, price, day_value, pct)


class FlowHistory(ABC):
    @abstractmethod
    def foreign_daily(self, code, n=10): ...   # -> list[DayFlow] cu -> moi

    @abstractmethod
    def closes(self, code, n=10): ...          # -> list[float] cu -> moi ([] neu loi)


class LLM(ABC):
    @abstractmethod
    def complete(self, system, user): ...      # -> str


class Telegram(ABC):
    @abstractmethod
    def send_to(self, chat_id, text): ...

    @abstractmethod
    def broadcast(self, text): ...             # -> bool (False neu chua config)

    @abstractmethod
    def get_updates(self, offset, wait): ...   # -> list[dict]
