"""Incremental paper adapter to the supplied V0 sizing/cost/stop conventions."""
import copy
from dataclasses import asdict
import math
import hashlib
from pathlib import Path

from .journal import JournalError
from .market import STEPS, VENUE, digest, validate_rows
from .vendor.paper_engine_v0 import Config, _floor_qty, _validate

STEP = STEPS['5m']
VERSION = 'IGOD_SHADOW_PAPER_V0_FORWARD_1'
MAX_HOLD_BARS = 288


def source_identity():
    directory = Path(__file__).resolve().parent
    paths = [directory / name for name in ('engine.py', 'market.py', 'signals.py', 'journal.py', 'service.py', '__main__.py', 'vendor/paper_engine_v0.py')]
    paths.append(directory.parent / 'guardian_signals.py')
    return {path.relative_to(directory.parent).as_posix(): hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for path in paths}


def validate_config(config):
    _validate([], config)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in asdict(config).values()):
        raise ValueError('PAPER_CONFIG_NONFINITE')
    if type(config.max_trades_day) is not int or type(config.cooldown_bars) is not int or config.cooldown_bars < 0:
        raise ValueError('PAPER_CONFIG_COUNTS')


class Engine:
    def __init__(self, journal, activated_at, config=Config()):
        validate_config(config)
        self.journal, self.config = journal, config
        source_hashes = source_identity()
        identity = digest(dict(version=VERSION, config=asdict(config), source_hashes=source_hashes, max_hold_bars=MAX_HOLD_BARS,
                               signal_rule='MANUAL_COPILOT_V1_RULES_ON_USDM_PAPER_V0'))
        if journal.records:
            first = journal.records[0]
            if first['type'] != 'FORWARD_START' or first['payload']['configuration_hash'] != identity:
                raise JournalError('PAPER_PROTOCOL_OR_CONFIG_CHANGED')
            self.state = copy.deepcopy(journal.records[-1]['state_after'])
            self._validate_state()
            return
        self.state = dict(version=VERSION, mode='SHADOW_ONLY', trade_authority='NONE',
                          activated_at=activated_at, last_bar=activated_at // STEP * STEP - STEP,
                          last_signal=None, equity=config.starting_equity,
                          initial_equity=config.starting_equity, position=None, pending=None,
                          day=None, day_equity=config.starting_equity, trades_today=0,
                          cooldown_until=-1, peak_equity=config.starting_equity, max_drawdown=0.,
                          equity_marked=config.starting_equity, fees=0., funding=0., gross=0.,
                          trades=0, wins=0, losses=0, breakeven=0, exposure_bars=0, bars=0)
        journal.append('START', 'FORWARD_START', dict(configuration_hash=identity,
                       config=asdict(config), source_hashes=source_hashes, max_hold_bars=MAX_HOLD_BARS,
                       source=VENUE, symbol='BTCUSDT', evidence='INSUFFICIENT',
                       historical_signals_imported=0), self.state, activated_at)

    def _validate_state(self):
        s = self.state
        if s.get('version') != VERSION or s.get('mode') != 'SHADOW_ONLY' or s.get('trade_authority') != 'NONE' or s['last_bar'] % STEP:
            raise JournalError('PAPER_STATE_INVALID')

    def observe(self, context, atr_5m, observed_at):
        close = context['signal_close']
        if type(close) is not int or close % 900_000 or not close <= observed_at < close + 900_000 or self.state['last_bar'] + STEP > observed_at:
            raise ValueError('PAPER_SIGNAL_STALE_OR_FUTURE')
        if self.state['last_signal'] is not None and close <= self.state['last_signal']:
            return False
        if not math.isfinite(atr_5m) or atr_5m <= 0:
            raise ValueError('PAPER_ATR_INVALID')
        s = copy.deepcopy(self.state)
        s['last_signal'] = close
        accepted = context.get('bias') in ('LONG_ALLOWED', 'SHORT_ALLOWED') and context.get('entry_quality') == 'GOOD'
        reason = 'NOT_CONFIRMED_GOOD'
        if accepted and s['position'] is None and s['pending'] is None:
            # Strictly future open AFTER the actual observation, never the open
            # at signal close that has already traded by the time we poll.
            s['pending'] = dict(side='LONG' if context['bias'] == 'LONG_ALLOWED' else 'SHORT',
                                signal_close=close, observed_at=observed_at,
                                entry_open=(observed_at // STEP + 1) * STEP,
                                atr=atr_5m, context=context)
            reason = 'COMMITTED_FUTURE_PAPER_PLAN'
        elif accepted:
            reason = 'POSITION_OR_PLAN_ALREADY_EXISTS'
        self.journal.append('SIGNAL:' + str(close), 'SIGNAL_OBSERVED',
                            dict(context=context, atr_5m=atr_5m, accepted=accepted, disposition=reason), s, observed_at)
        self.state = s
        return True

    def process_bar(self, row, funding, observed_at):
        stamp = row[0]
        if stamp <= self.state['last_bar']:
            return False
        validate_rows([row], '5m', stamp, stamp + STEP)
        if stamp != self.state['last_bar'] + STEP or stamp + STEP > observed_at:
            raise ValueError('PAPER_BAR_GAP_OR_OPEN')
        if not isinstance(funding, list):
            raise ValueError('PAPER_FUNDING_UNKNOWN')
        cfg, s = self.config, copy.deepcopy(self.state)
        o, high, low, close = [float(row[k]) for k in (1, 2, 3, 4)]
        day = stamp // 86_400_000
        if day != s['day']:
            s.update(day=day, day_equity=s['equity'], trades_today=0)
        fee, slip = cfg.fee_bps_per_side / 10_000, cfg.slippage_bps_per_side / 10_000
        actions, trade = [], None
        # Funding is an outcome cost, not an entry feature. Only positions held
        # before settlement qualify. Intrabar ambiguous credits are omitted;
        # debits are conservatively charged even if a stop may have occurred first.
        seen_funding = set()
        for f in funding:
            when, rate, mark = f['fundingTime'], float(f['fundingRate']), float(f['markPrice'])
            if type(when) is not int or not stamp <= when < stamp + STEP or when in seen_funding or not all(math.isfinite(x) for x in (rate, mark)) or mark <= 0 or f['symbol'] != 'BTCUSDT':
                raise ValueError('PAPER_FUNDING_INVALID')
            seen_funding.add(when)
        pending = s['pending']
        if pending and stamp >= pending['entry_open']:
            s['pending'] = None
            reason = None
            if stamp != pending['entry_open'] or pending['observed_at'] >= stamp:
                reason = 'MISSED_OR_NONCAUSAL_ENTRY'
            elif stamp > pending['signal_close'] + 900_000:
                reason = 'SIGNAL_TOO_OLD_AT_ENTRY'
            elif s['position'] is not None:
                reason = 'POSITION_ALREADY_EXISTS'
            elif stamp <= s['cooldown_until']:
                reason = 'COOLDOWN'
            elif s['equity'] <= 0 or s['equity'] <= s['day_equity'] * (1 - cfg.max_daily_loss_pct):
                reason = 'DAILY_LOSS_OR_CAPITAL'
            elif s['trades_today'] >= cfg.max_trades_day:
                reason = 'TRADES_DAY'
            side = pending['side']
            sign = 1 if side == 'LONG' else -1
            entry = o * (1 + sign * slip)
            distance = pending['atr'] * cfg.atr_stop_multiple
            level = pending['context'].get('entry_level')
            opposing = pending['context'].get('resistance' if sign == 1 else 'support')
            if any(value is None or not math.isfinite(value) or value <= 0 for value in (level, opposing)):
                reason = reason or 'STRUCTURE_UNAVAILABLE'
            elif (entry - level) * sign <= 0 or (opposing - entry) * sign <= 0:
                reason = reason or 'STRUCTURE_INVALIDATED_BEFORE_ENTRY'
            if reason is None:
                risk = distance + 2 * entry * (fee + slip)
                qty = _floor_qty(min(s['equity'] * cfg.risk_pct / risk,
                                     cfg.max_notional_multiple * s['equity'] / entry), cfg.qty_step)
                stop, target = entry - sign * distance, entry + sign * distance * cfg.reward_to_risk
                if qty <= 0 or qty * entry < cfg.minimum_notional or min(stop, target) <= 0:
                    reason = 'MINIMUM_SIZE_OR_INVALID_LEVELS'
                else:
                    entry_fee = qty * entry * fee
                    s['equity'] -= entry_fee
                    s['fees'] += entry_fee
                    s['trades_today'] += 1
                    s['position'] = dict(side=side, qty=qty, entry_ts=stamp, entry=entry,
                                         stop=stop, target=target, entry_fee=entry_fee, funding=0.,
                                         signal_close=pending['signal_close'], observed_at=pending['observed_at'],
                                         entry_reason=pending['context']['entry_reason'],
                                         invalidation_level=level, context=pending['context'],
                                         risk_cash=qty * risk, mfe=0., mae=0.)
                    actions.append(dict(type='PAPER_OPEN', side=side, entry=entry, qty=qty, stop=stop, target=target))
            if reason:
                actions.append(dict(type='PLAN_BLOCKED', reason=reason))
        pos = s['position']
        if pos:
            for f in funding:
                when = f['fundingTime']
                if pos['entry_ts'] < when:
                    charge = pos['qty'] * float(f['markPrice']) * float(f['fundingRate']) * (1 if pos['side'] == 'LONG' else -1)
                    if when != stamp and charge < 0:
                        charge = 0.
                    s['equity'] -= charge
                    s['funding'] += charge
                    pos['funding'] += charge
                    actions.append(dict(type='PAPER_FUNDING', amount=charge, funding_time=when))
            s['exposure_bars'] += 1
            sign = 1 if pos['side'] == 'LONG' else -1
            stopped = low <= pos['stop'] if sign == 1 else high >= pos['stop']
            targeted = high >= pos['target'] if sign == 1 else low <= pos['target']
            invalidated = (stamp + STEP) % 900_000 == 0 and (close - pos['invalidation_level']) * sign <= 0
            expired = stamp + STEP - pos['entry_ts'] >= MAX_HOLD_BARS * STEP
            reason = 'STOP' if stopped else 'TARGET' if targeted else 'STRUCTURE_INVALIDATION' if invalidated else 'TIME_EXIT' if expired else None
            # Full-candle excursions are bounds, not an intrabar path. On an
            # exit candle, do not claim an unobserved favorable pre-exit extreme.
            favorable = (high - pos['entry']) if sign == 1 else (pos['entry'] - low)
            adverse = (pos['entry'] - low) if sign == 1 else (high - pos['entry'])
            pos['mae'] = max(pos['mae'], adverse / pos['entry'])
            if reason is None:
                pos['mfe'] = max(pos['mfe'], favorable / pos['entry'])
            if reason:
                raw = (min(o, pos['stop']) if sign == 1 else max(o, pos['stop'])) if stopped else pos['target'] if targeted else close
                fill = raw * (1 - sign * slip)
                gross = (fill - pos['entry']) * pos['qty'] * sign
                exit_fee = pos['qty'] * fill * fee
                net = gross - pos['entry_fee'] - exit_fee - pos['funding']
                s['equity'] += gross - exit_fee
                s['fees'] += exit_fee
                s['gross'] += gross
                s['trades'] += 1
                s['wins' if net > 0 else 'losses' if net < 0 else 'breakeven'] += 1
                trade = dict(pos, exit_bar_open=stamp, exit_available_at=stamp + STEP,
                             exit=fill, exit_reason=reason, gross_pnl=gross,
                             fees=pos['entry_fee'] + exit_fee, net_pnl=net,
                             net_r=net / pos['risk_cash'], equity_after=s['equity'],
                             collision=bool(stopped and targeted),
                             excursion_quality='MFE_LOWER_BOUND_MAE_BAR_UPPER_BOUND')
                actions.append(dict(type='PAPER_CLOSE', reason=reason, net_pnl=net))
                s['position'] = None
                s['cooldown_until'] = stamp + cfg.cooldown_bars * STEP
        mark = s['equity']
        if s['position']:
            pos = s['position']
            sign = 1 if pos['side'] == 'LONG' else -1
            estimated_exit = close * (1 - sign * slip)
            mark += (estimated_exit - pos['entry']) * pos['qty'] * sign - pos['qty'] * estimated_exit * fee
        s['peak_equity'] = max(s['peak_equity'], mark)
        s['max_drawdown'] = max(s['max_drawdown'], (s['peak_equity'] - mark) / s['peak_equity'])
        s.update(last_bar=stamp, equity_marked=mark, bars=s['bars'] + 1)
        self.journal.append('BAR:' + str(stamp), 'CLOSED_BAR_PROCESSED',
                            dict(candle=row, candle_sha256=digest(row), funding=funding,
                                 actions=actions, closed_trade=trade,
                                 recovery=observed_at - stamp - STEP >= 2 * STEP), s, observed_at)
        self.state = s
        return True
