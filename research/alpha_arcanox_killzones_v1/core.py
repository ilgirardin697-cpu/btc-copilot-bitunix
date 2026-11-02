"""Fixed UTC-4 sessions and closed-body confirmation. No level formula guesses."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext

HOUR = 3_600_000
CLOCK = timezone(timedelta(hours=-4))  # Fixed offset. Never America/New_York DST.
RULES = 'ALPHA_ARCANOX_OWNER_RULES_V1'
LEVEL_NAMES = ('HIGH', 'LOW', 'SUPERIOR', 'INFERIOR')
# Empty deliberately. A screenshot value or JSON flag cannot authorize a formula.
# A verified implementation/source must be added in a separately reviewed change.
APPROVED_FORMULA_IDS = frozenset()


@dataclass(frozen=True)
class Bar:
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal(0)

    @property
    def available_at(self):
        return self.open_time + HOUR


@dataclass(frozen=True)
class Session:
    name: str
    start: int
    end: int
    high: Decimal
    low: Decimal
    candles: tuple


@dataclass(frozen=True)
class Pair:
    day: str
    asia: Session
    london: Session
    available_at: int


@dataclass(frozen=True)
class Levels:
    HIGH: Decimal | None = None
    LOW: Decimal | None = None
    SUPERIOR: Decimal | None = None
    INFERIOR: Decimal | None = None
    formula_id: str | None = None
    evidence_id: str | None = None
    pair_day: str | None = None
    available_at: int | None = None


def iso(t):
    return datetime.fromtimestamp(t/1000, timezone.utc).isoformat().replace('+00:00', 'Z')


def stamp(day, hour):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    return int(datetime.combine(day, time(hour), CLOCK).timestamp()*1000)


def validate(bars):
    prev = None
    for b in bars:
        if type(b.open_time) is not int or b.open_time % HOUR:
            raise ValueError('TIMESTAMP_NOT_1H_UTC')
        if prev is not None and b.open_time-prev != HOUR:
            raise ValueError('GAP_DUPLICATE_OR_UNORDERED')
        if not all(v.is_finite() for v in (b.open,b.high,b.low,b.close,b.volume)):
            raise ValueError('BAR_NONFINITE')
        if min(b.open,b.high,b.low,b.close) <= 0 or b.volume < 0:
            raise ValueError('BAR_VALUE_INVALID')
        if b.low > min(b.open,b.close) or b.high < max(b.open,b.close) or b.low > b.high:
            raise ValueError('BAR_OHLC_INVALID')
        prev = b.open_time


def session(bars, name, start, hours):
    end = start+hours*HOUR
    rows = tuple(b for b in bars if start <= b.open_time < end)
    if tuple(b.open_time for b in rows) != tuple(range(start,end,HOUR)):
        raise ValueError('SESSION_INCOMPLETE_'+name)
    return Session(name,start,end,max(b.high for b in rows),min(b.low for b in rows),rows)


def pair(bars, day, as_of):
    if isinstance(day,str):
        day = date.fromisoformat(day)
    freeze = stamp(day,5)
    if as_of < freeze:
        raise ValueError('BOTH_SESSIONS_NOT_CLOSED')
    # Asia opens 20,21,22,23,00; London 01,02,03,04. No gap between them.
    a = session(bars,'ASIA',stamp(day-timedelta(days=1),20),5)
    l = session(bars,'LONDON',stamp(day,1),4)
    return Pair(day.isoformat(),a,l,freeze)


def levels_for_pair(p):
    """No implementation is verified for the original indicator's four levels.

    Session extremes are available in p. They are NOT silently assigned to
    HIGH/LOW. No symmetry, diagonal, multiplier or hard-coded screenshot level.
    """
    return Levels(pair_day=p.day,available_at=p.available_at)


def atr14(bars):
    """Wilder ATR14: TR first=H-L, SMA seed14, then (13*previous+TR)/14."""
    validate(bars)
    out, seed, previous, last = [], [], None, None
    with localcontext() as ctx:
        ctx.prec = 40
        for b in bars:
            tr = b.high-b.low if previous is None else max(b.high-b.low,abs(b.high-previous),abs(b.low-previous))
            previous = b.close
            if last is None:
                seed.append(tr)
                if len(seed) == 14:
                    last = sum(seed)/Decimal(14)
            else:
                last = (13*last+tr)/Decimal(14)
            out.append(last)
    return tuple(out)


def body_direction(b, high, low):
    """Pure numeric predicate; NOT a verified event or authorization to trade."""
    if not high.is_finite() or not low.is_finite() or high <= low:
        raise ValueError('THRESHOLDS_INVALID')
    if min(b.open,b.close) > high:
        return 'LONG'
    if max(b.open,b.close) < low:
        return 'SHORT'
    return None


def level_blockers(levels,p,as_of):
    reasons = []
    for name in LEVEL_NAMES:
        v = getattr(levels,name)
        if v is None:
            reasons.append(name+'_NO_VERIFICADO')
        elif not v.is_finite() or v <= 0:
            reasons.append(name+'_INVALIDO')
    if levels.formula_id not in APPROVED_FORMULA_IDS or not levels.evidence_id:
        reasons.append('FORMULA_ORIGINAL_NO_VERIFICADA')
    if levels.pair_day != p.day:
        reasons.append('LEVELS_SESSION_MISMATCH')
    if levels.available_at is None or levels.available_at < p.available_at or levels.available_at > as_of:
        reasons.append('LEVELS_AVAILABILITY_INVALID')
    if not reasons and not (levels.INFERIOR < levels.LOW < levels.HIGH < levels.SUPERIOR):
        reasons.append('FOUR_LEVEL_ORDER_INVALID')
    return reasons


def scan(bars,day,as_of,costs=None,capital=None):
    """One first technical confirmation per pair in the supplied observation window.

    No implicit legacy expiry. Caller records an explicit as_of; no collector,
    overlapping-position simulation, entry fill, stop execution or PnL exists.
    """
    closed = tuple(b for b in bars if b.available_at <= as_of)
    validate(closed)
    result = dict(rules=RULES,as_of=as_of,clock='UTC-04:00_FIXED',pair=None,levels=None,
                  levels_verified=False,
                  atr14_context=None,
                  confirmation=None,paper_decision='RECHAZADA',reason_codes=[],
                  risk=None,shadow_only=True,trade_authority='NONE')
    try:
        p = pair(closed,day,as_of)
    except ValueError as error:
        result['reason_codes']=[str(error)]
        return result
    result['pair']=p
    atr=atr14(closed)
    result['atr14_context']=dict(value=atr[-1],available_at=closed[-1].available_at,
                                seed='First 14 true ranges of supplied closed history; Wilder RMA')
    levels = levels_for_pair(p)  # Only closed session bars are exposed to this boundary.
    result['levels']=levels
    result['session_statistics']=dict(asia_high=p.asia.high,asia_low=p.asia.low,
        london_high=p.london.high,london_low=p.london.low,
        union_high=max(p.asia.high,p.london.high),union_low=min(p.asia.low,p.london.low),
        warning='These are OHLC statistics, NOT verified Alpha HIGH/LOW formulas')
    blocked = level_blockers(levels,p,as_of)
    if blocked:
        result['reason_codes']=blocked
        return result
    result['levels_verified']=True
    for i,b in enumerate(closed):
        # Availability-based boundary: the 04:00 candle is not evaluated BEFORE 05:00.
        if b.available_at < max(p.available_at,levels.available_at):
            continue
        side = body_direction(b,levels.HIGH,levels.LOW)
        if side is None:
            continue
        result['confirmation']=dict(side=side,candle_open=b.open_time,available_at=b.available_at,
                                    theoretical_entry=b.close,atr14=atr[i],event='TECHNICAL_ONLY')
        from .risk import estimate
        target = levels.SUPERIOR if side == 'LONG' else levels.INFERIOR
        risk = estimate(side,b.close,levels.HIGH,levels.LOW,target,atr[i],costs,capital)
        result['risk']=risk
        result['reason_codes']=risk['reason_codes']
        if risk['risk_filter_passed']:
            result['paper_decision']='ACEPTADA'
        return result  # First confirmation only, including rejected opportunities.
    result['reason_codes']=['NO_CONFIRMED_BODY']
    return result
