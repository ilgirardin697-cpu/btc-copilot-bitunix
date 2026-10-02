"""Public data only: Binance direction/flow, Bitunix venue ATR. Separate failure paths."""
import time
import requests
import numpy as np
from guardian_signals import closed_bars, atr14, snapshot
from guardian_risk import SafetyError


BINANCE_MARKET_DATA_BASE = "https://data-api.binance.vision"


class Market:
    def __init__(self, bitunix, transport=None, clock=time.time):
        self.bitunix = bitunix
        self.http = transport or requests.Session()
        self.clock = clock
        self._bias = None
        self._hour = None
        self._atr = None
        self._atr_hour = None

    def venue_atr(self):
        hour = int(self.clock() // 3600)
        if self._atr_hour == hour:
            return self._atr
        for kind in ('MARK_PRICE', 'LAST_PRICE'):
            try:
                raw = self.bitunix.klines(kind)
                rows = [[r['time'], r['open'], r['high'], r['low'], r['close'], 0, 0] for r in raw]
                rows = closed_bars(rows, self.clock() * 1000, 3600000)
                if len(rows) < 15 or self.clock() * 1000 - (rows[-1, 0] + 3600000) >= 3600000:
                    continue
                if np.any(np.diff(rows[:, 0]) != 3600000):
                    continue
                self._atr = atr14(rows)
                if self._atr is not None:
                    self._atr_hour = hour
                    return self._atr
            except Exception:
                continue
        self._atr = None
        return None  # percentage emergency remains active, never reuse stale ATR

    def _binance(self, interval, count):
        rows = []
        end = int(self.clock() * 1000)
        while len(rows) < count:
            response = self.http.get(BINANCE_MARKET_DATA_BASE + '/api/v3/klines',
                                     params={'symbol': 'BTCUSDT', 'interval': interval,
                                             'limit': min(1000, count - len(rows)), 'endTime': end},
                                     timeout=(2, 3), allow_redirects=False)
            if response.status_code != 200:
                raise SafetyError('BINANCE_UNAVAILABLE')
            page = response.json()
            if not isinstance(page, list) or not page:
                raise SafetyError('BINANCE_INCOMPLETE')
            rows = page + rows
            end = int(page[0][0]) - 1
        return [[r[0], r[1], r[2], r[3], r[4], r[5], r[9]] for r in rows]

    def bias(self):
        # Entry evidence includes 15m closed pivots; refresh on that boundary.
        hour = int(self.clock() // 900)
        if self._hour == hour and self._bias is not None:
            return self._bias
        try:
            # Warm-up preserves a full 3000 RSI window, not merely 3000 price bars.
            self._bias = snapshot(self._binance('1h', 3200), self._binance('4h', 220),
                                  self._binance('15m', 220), self.clock() * 1000)
            self._hour = hour
            return self._bias
        except Exception:
            self._bias = None
            return {'version': 'MANUAL_COPILOT_V1', 'bias': 'UNKNOWN',
                    'why': 'Binance closed data unavailable; percentage liquidation guard remains active'}
