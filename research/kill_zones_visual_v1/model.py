"""One explicit geometric hypothesis; no PnL, optimizer, exchange or orders."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

HOUR = 3_600_000
PROTOTYPE = 'KZ_SINGLE_SEGMENT_VISUAL_V1'
CLOCK = 'America/New_York'


@dataclass(frozen=True)
class Bar:
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal(0)


@dataclass(frozen=True)
class Point:
    t: int
    p: Decimal


@dataclass(frozen=True)
class Segment:
    a: Point
    b: Point

    def at(self, t):
        if self.b.t == self.a.t:
            raise ValueError('VERTICAL_SEGMENT_NO_TIME_LINE')
        with localcontext() as ctx:
            ctx.prec = 40
            return self.a.p + (self.b.p - self.a.p) * Decimal(t - self.a.t) / Decimal(self.b.t - self.a.t)

    def clone(self, c, side):
        if side not in ('UP', 'DOWN'):
            raise ValueError('SIDE_INVALID')
        dt, dp = self.b.t - self.a.t, self.b.p - self.a.p
        if side == 'UP':
            return Segment(c, Point(c.t + dt, c.p + dp))
        return Segment(Point(c.t - dt, c.p - dp), c)


@dataclass(frozen=True)
class Box:
    name: str
    start: int
    end: int
    high: Decimal
    low: Decimal
    high_at: int
    low_at: int


@dataclass(frozen=True)
class Setup:
    day: str
    asia: Box
    london: Box
    lower: Box
    upper: Box
    measurement: Segment
    available_at: int
    expires_at: int

    def projection(self, side):
        c = Point(self.available_at, self.lower.high if side == 'UP' else self.upper.low)
        return self.measurement.clone(c, side)


def iso(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).isoformat().replace('+00:00', 'Z')


def boundary(day, hour):
    """Reject nonexistent/ambiguous local boundaries instead of guessing DST."""
    naive = datetime.combine(day, time(hour))
    tz = ZoneInfo(CLOCK)
    first, second = naive.replace(tzinfo=tz, fold=0), naive.replace(tzinfo=tz, fold=1)
    if first.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != naive:
        raise ValueError('NONEXISTENT_LOCAL_SESSION_BOUNDARY')
    if first.utcoffset() != second.utcoffset():
        raise ValueError('AMBIGUOUS_LOCAL_SESSION_BOUNDARY')
    return int(first.timestamp() * 1000)


def validate(bars):
    previous = None
    for b in bars:
        if type(b.open_time) is not int or b.open_time % HOUR:
            raise ValueError('HOURLY_TIMESTAMP_INVALID')
        if previous is not None and b.open_time - previous != HOUR:
            raise ValueError('HOURLY_GAP_OR_DUPLICATE')
        if not all(x.is_finite() for x in (b.open, b.high, b.low, b.close, b.volume)):
            raise ValueError('NONFINITE_BAR')
        if min(b.open, b.high, b.low, b.close) <= 0 or b.volume < 0:
            raise ValueError('BAR_VALUES_INVALID')
        if b.low > min(b.open, b.close) or b.high < max(b.open, b.close) or b.high < b.low:
            raise ValueError('OHLC_INVALID')
        previous = b.open_time


def box(bars, name, start, end):
    rows = [b for b in bars if start <= b.open_time < end]
    if [b.open_time for b in rows] != list(range(start, end, HOUR)):
        raise ValueError('SESSION_INCOMPLETE')
    high, low = max(rows, key=lambda b: b.high), min(rows, key=lambda b: b.low)
    return Box(name, start, end, high.high, low.low, high.open_time, low.open_time)


def session_boxes(bars, day, as_of):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    ae, ls, le, expiry = (boundary(day, h) for h in (0, 2, 5, 20))
    ast = boundary(day - timedelta(days=1), 20)
    if as_of < le:
        raise ValueError('SESSIONS_NOT_CLOSED')
    return box(bars, 'ASIA', ast, ae), box(bars, 'LONDON', ls, le), expiry


def construct(bars, day, as_of):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    a, l, expiry = session_boxes(bars, day, as_of)
    if a.high < l.high and a.low < l.low:
        lower, upper = a, l
    elif l.high < a.high and l.low < a.low:
        lower, upper = l, a
    else:
        raise ValueError('BOX_ORDER_AMBIGUOUS')
    # Explicit automation assumptions: wick extremes, earliest ties, bar OPEN x.
    measure = Segment(Point(lower.low_at, lower.low), Point(upper.high_at, upper.high))
    if measure.a.t == measure.b.t:
        raise ValueError('VERTICAL_SEGMENT_NO_TIME_LINE')
    return Setup(day.isoformat(), a, l, lower, upper, measure, l.end, expiry)


def body_cross(bar, level):
    # Same chart x for the complete candle body: its OPEN timestamp.
    if bar.open <= level < bar.close:
        return 'UP'
    if bar.close < level <= bar.open:
        return 'DOWN'
    return None


def observe(bars, day, as_of):
    """Closed prefix only. Next-open plan reads that OPEN and no subsequent OHLC."""
    closed = tuple(b for b in bars if b.open_time + HOUR <= as_of)
    validate(closed)
    result = dict(prototype=PROTOTYPE, mode='PAPER_SHADOW_ONLY', trade_authority='NONE',
                  as_of=as_of, status='NO_CONFIRMATION', confirmation=None, plan=None)
    try:
        setup = construct(closed, day, as_of)
    except ValueError as error:
        result.update(status='UNAVAILABLE', reason=str(error), setup=None)
        # Preserve observable boxes even when geometry cannot be constructed.
        try:
            a, l, expiry = session_boxes(closed, day, as_of)
            result['session_boxes'] = (a, l)
            result['expires_at'] = expiry
        except ValueError:
            pass
        return result
    result['setup'] = setup
    for b in closed:
        if b.open_time < setup.available_at or b.open_time + HOUR > setup.expires_at:
            continue
        level = setup.measurement.at(b.open_time)
        side = body_cross(b, level)
        if side is None:
            continue
        copy = setup.projection(side)
        target = copy.b.p if side == 'UP' else copy.a.p
        stop = setup.lower.low if side == 'UP' else setup.upper.high
        signal_at = b.open_time + HOUR
        result.update(status='CONFIRMED_HYPOTHESIS', confirmation=dict(
            side=side, candle_open=b.open_time, available_at=signal_at,
            signal_close=b.close, line_value=level, copy=copy, target=target, stop=stop))
        # First body-crossing per session pair, even if its plan is rejected.
        next_bar = next((n for n in bars if n.open_time == signal_at), None)
        if next_bar is None or signal_at > as_of:
            result['plan'] = dict(status='ENTRY_PENDING', entry_at=signal_at)
        else:
            entry = next_bar.open  # Never read this candle's high/low/close/volume.
            if not entry.is_finite() or entry <= 0:
                raise ValueError('ENTRY_OPEN_INVALID')
            valid = stop < entry < target if side == 'UP' else target < entry < stop
            result['plan'] = dict(status='REFERENCE_PLAN' if valid else 'REJECTED_STOP_TARGET_ORDER',
                                  side=side, entry_at=signal_at, reference_entry=entry,
                                  stop=stop, target=target, cost_model='NOT_ASSESSED',
                                  fill_model='NEXT_OPEN_REFERENCE_ONLY_NOT_EXECUTED')
        break
    return result
