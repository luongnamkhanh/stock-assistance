"""Port: kho snapshot/alert/state/watchlist/day_story/meta. Infra implement bang SQLite
(hoac gi khac sau nay) — usecases chi biet interface nay, khong biet SQL."""
from abc import ABC, abstractmethod


class SnapshotRepo(ABC):
    @abstractmethod
    def insert_snapshots(self, ts, rows): ...          # rows: list[tuple 9 cot nhu _vps_row]

    @abstractmethod
    def max_ts(self): ...                              # -> str | None

    @abstractmethod
    def prev_snapshot_ts(self, ts, minutes): ...       # -> str | None

    @abstractmethod
    def snapshot_times(self, day, until_ts, n): ...    # -> list[str] tang dan, n moc cuoi

    @abstractmethod
    def spike_rows(self, ts, prev_ts): ...             # -> [(sym, net, win_value, day_value, price, pct, day_net)]

    @abstractmethod
    def state_rows(self, ts, prev_ts): ...             # -> [(sym, day_net, recent, day_value, price, pct)]

    @abstractmethod
    def accel_rows(self, t0, t1, t2, t3): ...          # -> [(sym, day_value, win3, d1, d2, d3, day_net, price, pct)]

    @abstractmethod
    def recent_alert(self, symbol, direction, ts, minutes): ...  # -> bool (cooldown `minutes` phut truoc ts)

    @abstractmethod
    def add_alerts(self, rows): ...                    # rows: [(ts, sym, direction, net, share, price)]

    @abstractmethod
    def alerts_since(self, day): ...                   # -> [(ts, sym, direction)] tu ngay day

    @abstractmethod
    def get_regime(self, symbol, day): ...             # -> str ("NEUTRAL" neu chua co)

    @abstractmethod
    def set_regime(self, symbol, regime, day): ...

    @abstractmethod
    def watchlist(self, chat_id): ...                  # -> set[str] rieng cua chat

    @abstractmethod
    def watch_union(self): ...                         # -> set[str] hop moi chat (cho detector)

    @abstractmethod
    def watch(self, chat_id, symbol): ...

    @abstractmethod
    def unwatch(self, chat_id, symbol): ...

    @abstractmethod
    def save_day_story(self, day, late_from): ...      # net/late_net/room_delta tung ma (late_net tu moc late_from)

    @abstractmethod
    def last_story(self, symbol, before_day): ...      # -> (day, net, late_net, room_delta) | None

    @abstractmethod
    def week_net(self, d1, d2, min_net): ...           # -> [(sym, tong_net d1..d2)] DESC, |net|>min_net

    @abstractmethod
    def market_net(self, ts): ...                      # -> tong day_net toan thi truong tai ts (VND)

    @abstractmethod
    def snapshot_count(self, ts): ...                  # -> so ma trong snapshot ts

    @abstractmethod
    def top_net_full(self, ts, min_net): ...           # -> [(sym, day_net, price, pct)] DESC, |net|>min_net

    @abstractmethod
    def heat(self, ts, n): ...                         # -> [(sym, pct)] theo day_value DESC

    @abstractmethod
    def has_snapshots(self, day): ...                  # -> bool

    @abstractmethod
    def save_fund_month(self, month, holdings, assets, industries, snapshots): ...  # thay tron 1 thang, 4 bang

    @abstractmethod
    def has_fund_month(self, month): ...               # -> bool: thang do da chup day du chua

    @abstractmethod
    def fund_report_month(self, month): ...            # -> (min, max) ky bao cao | None

    @abstractmethod
    def fund_months(self): ...                         # -> list[str 'YYYY-MM'] tang dan

    @abstractmethod
    def fund_consensus(self, month): ...               # -> [(symbol, so_quy, tong_pct, tong_value)] DESC

    @abstractmethod
    def funds_holding(self, symbol, month): ...        # -> [(fund, pct)] DESC theo pct

    @abstractmethod
    def last_price(self, symbol): ...                  # -> gia khop gan nhat | None

    @abstractmethod
    def add_note(self, chat_id, symbol, ts, price): ...

    @abstractmethod
    def list_notes(self, chat_id): ...                 # -> [(symbol, ts, price)] moi -> cu

    @abstractmethod
    def unnote(self, chat_id, symbol): ...

    @abstractmethod
    def notes_due(self, cutoff_day): ...               # -> [(chat_id, symbol, ts, price)] chua bao, du tuoi

    @abstractmethod
    def mark_note_reported(self, chat_id, symbol, ts): ...

    @abstractmethod
    def get_meta(self, k, default=None): ...

    @abstractmethod
    def set_meta(self, k, v): ...
