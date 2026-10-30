"""Consume only the existing pure Manual Copilot closed-candle calculations."""
from guardian_signals import snapshot
from .market import digest

SIGNAL_RULE = 'MANUAL_COPILOT_V1_RULES_ON_USDM_PAPER_V0'


def columns(rows):
    return [[r[i] for i in (0, 1, 2, 3, 4, 5, 9)] for r in rows]


def confirmed_context(market, cutoff):
    inputs = {tf: market.history(tf, count, cutoff) for tf, count in (('1h', 3200), ('4h', 220), ('15m', 220))}
    result = snapshot(columns(inputs['1h']), columns(inputs['4h']), columns(inputs['15m']), cutoff)
    # Production Copilot uses Spot; this separate simulation explicitly applies
    # exactly the same pure rules to USD-M. No production host state is claimed.
    result.update(signal_rule=SIGNAL_RULE, source='BINANCE_USDM_PERPETUAL',
                  signal_close=int(inputs['15m'][-1][0]) + 900_000,
                  input_hashes={tf: digest(rows) for tf, rows in inputs.items()},
                  momentum_identity='EXISTING_COPILOT_LOW27_EMA4; NOT PRODUCTION_LOW29_HOST',
                  pattern='CONFIRMED_RECLAIM' if result.get('entry_reason') == 'CONFIRMED_RECLAIM' else 'NONE')
    return result
