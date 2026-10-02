"""Pure, frozen capital protection rules. No HTTP, trading or strategy imports."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
import os


SIDE_ALIASES = {'LONG': 'LONG', 'BUY': 'LONG', 'SHORT': 'SHORT', 'SELL': 'SHORT'}


class SafetyError(Exception):
    """Messages are static codes: never include exchange bodies or credentials."""


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise SafetyError('INVALID_NUMBER') from None
    if not math.isfinite(result):
        raise SafetyError('INVALID_NUMBER')
    return result


@dataclass(frozen=True)
class Config:
    mode: str = 'SHADOW'
    allow_sl: bool = False
    allow_close: bool = False
    arm_phrase: str = ''
    warning_atr: float = 3.0
    danger_atr: float = 2.0
    emergency_atr: float = 1.25
    warning_pct: float = .03
    danger_pct: float = .02
    emergency_pct: float = .0125
    buffer_atr: float = .75
    buffer_pct: float = .005
    lockout_minutes: float = 120
    state_dir: str = '/data/guardian'

    def __post_init__(self):
        if self.mode not in ('SHADOW', 'PROTECT'):
            raise SafetyError('INVALID_MODE')
        for suffix in ('atr', 'pct'):
            values = [number(getattr(self, name + '_' + suffix))
                      for name in ('warning', 'danger', 'emergency')]
            if not values[0] >= values[1] >= values[2] > 0:
                raise SafetyError('INVALID_THRESHOLDS')
        if min(number(self.buffer_atr), number(self.buffer_pct), number(self.lockout_minutes)) <= 0:
            raise SafetyError('INVALID_CONFIG')

    def armed(self, action):
        flag = self.allow_sl if action == 'SL' else self.allow_close if action == 'CLOSE' else False
        return self.mode == 'PROTECT' and flag is True and self.arm_phrase == 'PROTECT_CAPITAL_ONLY'

    @classmethod
    def from_env(cls):
        if os.getenv('GUARDIAN_SYMBOLS', 'BTCUSDT') != 'BTCUSDT':
            raise SafetyError('BTCUSDT_ONLY')
        args = dict(mode=os.getenv('GUARDIAN_MODE', 'SHADOW'),
                    allow_sl=os.getenv('GUARDIAN_ALLOW_PLACE_SL', 'false') == 'true',
                    allow_close=os.getenv('GUARDIAN_ALLOW_FLASH_CLOSE', 'false') == 'true',
                    arm_phrase=os.getenv('GUARDIAN_ARM_PHRASE', ''),
                    state_dir=os.getenv('GUARDIAN_STATE_DIR', '/data/guardian'))
        for field in ('warning_atr', 'danger_atr', 'emergency_atr', 'warning_pct',
                      'danger_pct', 'emergency_pct', 'buffer_atr', 'buffer_pct', 'lockout_minutes'):
            key = 'GUARDIAN_' + (field.replace('buffer', 'catastrophic_buffer')).upper()
            if key in os.environ:
                args[field] = number(os.environ[key])
        return cls(**args)


@dataclass(frozen=True)
class Position:
    position_id: str
    side: str
    qty: float
    leverage: float
    liq: float
    entry: float
    pnl: float
    margin: float
    margin_rate: float
    margin_mode: str
    position_mode: str
    ctime: int
    mtime: int


def parse_positions(rows):
    """Parse the fixed Guardian GET scoped with includeSubAccounts=false."""
    if not isinstance(rows, list) or len(rows) > 1:
        raise SafetyError('AMBIGUOUS_POSITIONS')
    if not rows:
        return None
    p = rows[0]
    try:
        if not isinstance(p, dict):
            raise SafetyError('POSITION_INCOMPLETE')
        if p.get('symbol') != 'BTCUSDT':
            raise SafetyError('POSITION_SYMBOL_INVALID')
        raw_side = str(p.get('side')).upper()
        side = SIDE_ALIASES.get(raw_side)
        if side is None:
            raise SafetyError('POSITION_SIDE_INVALID')
        if p.get('marginMode') not in ('ISOLATION', 'CROSS'):
            raise SafetyError('POSITION_MARGIN_MODE_INVALID')
        if p.get('positionMode') not in ('ONE_WAY', 'HEDGE'):
            raise SafetyError('POSITION_MODE_INVALID')
        if 'subAccountId' in p:
            account_id = p['subAccountId']
            # The scoped request controls account inclusion; a nonzero ID is not
            # evidence of an unexpected subaccount. Never coerce floats or bools.
            valid_account = ((type(account_id) is int and account_id >= 0)
                             or (isinstance(account_id, str) and account_id.isascii()
                                 and account_id.isdecimal()))
            if not valid_account:
                raise SafetyError('POSITION_ACCOUNT_ID_INVALID')
        pid = p['positionId']
        if not isinstance(pid, str) or not pid.isdecimal() or len(pid) > 64:
            raise SafetyError('POSITION_ID_INVALID')
        pos = Position(pid, side, number(p['qty']), number(p['leverage']),
                       number(p['liqPrice']), number(p['avgOpenPrice']), number(p['unrealizedPNL']),
                       number(p['margin']), number(p['marginRate']), p['marginMode'], p['positionMode'],
                       int(p['ctime']), int(p['mtime']))
        if (min(pos.qty, pos.leverage, pos.entry) <= 0
                or min(pos.margin, pos.margin_rate, pos.ctime, pos.mtime) < 0):
            raise SafetyError('POSITION_INVALID')
        return pos
    except (KeyError, TypeError, ValueError, OverflowError):
        raise SafetyError('POSITION_INCOMPLETE') from None


def risk(position, mark, atr, config):
    mark = number(mark)
    if mark <= 0 or position.liq <= 0:
        raise SafetyError('LIQUIDATION_PRICE_INVALID')
    if (position.side == 'LONG' and position.liq >= mark) or (position.side == 'SHORT' and position.liq <= mark):
        raise SafetyError('LIQUIDATION_SIDE_INVALID')
    distance = abs(position.liq - mark)
    atr = number(atr) if atr is not None else None
    if atr is not None and atr <= 0:
        raise SafetyError('ATR_INVALID')
    pct = distance / mark
    multiple = distance / atr if atr else None
    state = 'NORMAL'
    for name in ('emergency', 'danger', 'warning'):
        if pct <= getattr(config, name + '_pct') or (multiple is not None and multiple <= getattr(config, name + '_atr')):
            state = name.upper()
            break
    return dict(state=state, mark=mark, liq=position.liq, distance=distance,
                distance_pct=pct, distance_atr=multiple, atr=atr,
                atr_pct=atr / mark if atr else None)


def catastrophic_stop(position, mark, atr, precision, config):
    risk(position, mark, atr, config)
    if not isinstance(precision, int) or not 0 <= precision <= 12:
        raise SafetyError('PRECISION_INVALID')
    tick = Decimal(1).scaleb(-precision)
    buffer = max(config.buffer_atr * (atr or 0), config.buffer_pct * mark)
    raw = position.liq + buffer if position.side == 'LONG' else position.liq - buffer
    rounding = ROUND_CEILING if position.side == 'LONG' else ROUND_FLOOR
    stop = Decimal(str(raw)).quantize(tick, rounding=rounding)
    value = float(stop)
    if position.side == 'LONG':
        valid = position.liq < value < mark
    else:
        valid = mark < value < position.liq
    if not valid or abs(mark - value) < float(tick) * 2:
        raise SafetyError('STOP_OUTSIDE_SAFE_INTERVAL')
    return format(stop, 'f')


def assess_orders(orders, position, target):
    """Never modify ANY existing TP/SL, including TP-only and partial stops."""
    if not isinstance(orders, list):
        raise SafetyError('ORDERS_INVALID')
    statuses = []
    for row in orders:
        if not isinstance(row, dict):
            raise SafetyError('ORDERS_INVALID')
        if row.get('positionId') != position.position_id or row.get('symbol') != 'BTCUSDT':
            raise SafetyError('ORDERS_SCOPE_INVALID')
        sl = row.get('slPrice')
        if not sl or number(sl) <= 0:
            statuses.append('EXISTING_TP_OR_UNKNOWN_UNTOUCHED')
            continue
        price = number(sl)
        safer = price >= float(target) if position.side == 'LONG' else price <= float(target)
        full = row.get('slQty') in (None, '', '0', 0) or number(row['slQty']) >= position.qty
        market = row.get('slStopType') == 'MARK_PRICE' and row.get('slOrderType', 'MARKET') == 'MARKET'
        statuses.append('EXISTING_SAFER_SL_UNTOUCHED' if safer and full and market else
                        'EXISTING_SL_CLOSER_TO_LIQUIDATION_OR_UNVERIFIED')
    return statuses or ['MISSING_SL']
