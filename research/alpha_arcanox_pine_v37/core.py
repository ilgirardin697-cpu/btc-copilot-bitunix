"""Pine variable names retained for audit. Numeric inputs use binary64 like Pine.

No venue or trading authority can be inferred from an OHLC fixture.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import math

HOUR = 3_600_000


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        values = (self.open, self.high, self.low, self.close)
        if (type(self.open_time) is not int or self.open_time % HOUR
                or any(not math.isfinite(x) or x <= 0 for x in values)
                or self.low > min(self.open, self.close)
                or self.high < max(self.open, self.close) or self.low > self.high):
            raise ValueError('INVALID_CLOSED_H1_CANDLE')

    @property
    def available_at(self):
        # Exclusive close boundary; Binance's inclusive closeTime is this - 1ms.
        return self.open_time + HOUR


def session_member(bar, profile, start, count):
    local = datetime.fromtimestamp(bar.open_time / 1000, timezone.utc).astimezone(profile.tz)
    return (local.hour - start) % 24 < count


def project(aHigh, aLow, lHigh, lLow, topInsetPct=3.0, bottomInsetPct=3.0):
    vals = (aHigh, aLow, lHigh, lLow)
    if (any(not math.isfinite(x) or x <= 0 for x in vals)
            or aHigh < aLow or lHigh < lLow
            or not 0 <= topInsetPct <= 35 or not 0 <= bottomInsetPct <= 35):
        raise ValueError('INVALID_BOX_OR_INSET')
    # Zero-height, overlapping and nested boxes are legal Pine configurations.
    amplitude = max(aHigh, lHigh) - min(aLow, lLow)
    topInAsia = aHigh <= lHigh
    bottomInAsia = aLow >= lLow
    topBoxHeight = aHigh - aLow if topInAsia else lHigh - lLow
    bottomBoxHeight = aHigh - aLow if bottomInAsia else lHigh - lLow
    topAnchor = min(aHigh, lHigh) - topBoxHeight * topInsetPct / 100.0
    bottomAnchor = max(aLow, lLow) + bottomBoxHeight * bottomInsetPct / 100.0
    return dict(aHigh=aHigh, aLow=aLow, lHigh=lHigh, lLow=lLow,
                amplitude=amplitude, topInAsia=topInAsia, bottomInAsia=bottomInAsia,
                topBoxHeight=topBoxHeight, bottomBoxHeight=bottomBoxHeight,
                topAnchor=topAnchor, bottomAnchor=bottomAnchor,
                newTopTarget=topAnchor + amplitude, newBottomTarget=bottomAnchor - amplitude,
                highGuideValue=max(aHigh, lHigh), lowGuideValue=min(aLow, lLow))


def display_tick(value, tick):
    """Display only. Never round an input to a signal/risk calculation."""
    t = Decimal(str(tick))
    if not t.is_finite() or t <= 0:
        raise ValueError('INVALID_TICK')
    d = (Decimal(str(value)) / t).quantize(Decimal(1), rounding=ROUND_HALF_UP) * t
    return format(d.quantize(t), 'f')


class ATR14:
    """ta.atr(14): true range, first TR=H-L, SMA seed, Wilder RMA thereafter."""
    def __init__(self):
        self.previous_close = None
        self.seed = []
        self.value = None

    def append(self, bar):
        tr = bar.high - bar.low
        if self.previous_close is not None:
            tr = max(tr, abs(bar.high-self.previous_close), abs(bar.low-self.previous_close))
        self.previous_close = bar.close
        if self.value is None:
            self.seed.append(tr)
            if len(self.seed) == 14:
                self.value = sum(self.seed) / 14
        else:
            alpha = 1.0 / 14
            self.value = alpha * tr + (1-alpha) * self.value
        return self.value
