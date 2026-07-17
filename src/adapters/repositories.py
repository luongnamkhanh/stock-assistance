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
    def recent_alert(self, symbol, direction, cutoff): ...  # -> bool

    @abstractmethod
    def add_alerts(self, rows): ...                    # rows: [(ts, sym, direction, net, share, price)]

    @abstractmethod
    def get_regime(self, symbol, day): ...             # -> str ("NEUTRAL" neu chua co)

    @abstractmethod
    def set_regime(self, symbol, regime, day): ...

    @abstractmethod
    def watchlist(self): ...                           # -> set[str]

    @abstractmethod
    def watch(self, symbol): ...

    @abstractmethod
    def unwatch(self, symbol): ...

    @abstractmethod
    def save_day_story(self, day): ...                 # SQL aggregation (collector.py:353-370)

    @abstractmethod
    def last_story(self, symbol, before_day): ...      # -> (net, late_net, room_delta) | None

    @abstractmethod
    def top_net(self, ts): ...                         # -> [(sym, day_net)] DESC, |net|>1 ty

    @abstractmethod
    def heat(self, ts, n): ...                         # -> [(sym, pct)] theo day_value DESC

    @abstractmethod
    def has_snapshots(self, day): ...                  # -> bool

    @abstractmethod
    def get_meta(self, k, default=None): ...

    @abstractmethod
    def set_meta(self, k, v): ...
