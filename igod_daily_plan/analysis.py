"""Public closed-data plan; optional diagnostics cannot modify protected systems."""
from datetime import datetime, timezone
from .core import generate_plan, normalize, HISTORIES, support_resistance, atr14
from .cycle import cycle_series
from .market import public_market


def calculate(now_ms):
    try:
        raw = public_market(now_ms)
        plan = generate_plan(raw, now_ms, live_public=True)
        if plan['bias'] == 'UNKNOWN':
            return plan
        bars = {tf: normalize(raw[tf], tf, now_ms, HISTORIES[tf]) for tf in HISTORIES}
        from .core import STEPS, WEEKLY_ANCHOR
        for tf, rows in bars.items():
            anchor = WEEKLY_ANCHOR if tf == '1w' else 0
            expected = (now_ms-anchor)//STEPS[tf]*STEPS[tf]+anchor
            if rows[-1]['close_ts'] != expected:
                raise ValueError('LATEST_CLOSED_CANDLE_MISSING')
        plan['closed_times'] = {tf: rows[-1]['close_ts'] for tf, rows in bars.items()}
        plan['daily_recent_closed'] = bars['1d'][-30:]
        plan['cycle'] = cycle_series(bars['1d'])[-1]
        plan['weekly_cycle'] = cycle_series(bars['1w'])[-1]
        if not plan.get('structural_levels'):
            plan['structural_levels'] = support_resistance({'1h': bars['1h'], '4h': bars['4h']},
                bars['15m'][-1]['c'], max(.25 * atr14(bars['1h']), .0001 * bars['15m'][-1]['c']))
        plan['entry_confirmation'] = 'PENDING: future closed 15m rejection and structure reconfirmation; no executable trigger claimed'
        plan['cycle_used_for_execution'] = False
        return plan
    except Exception:
        return dict(bias='UNKNOWN', source='BINANCE_USDM_PERPETUAL', symbol='BTCUSDT',
                    asof_utc=datetime.fromtimestamp(now_ms/1000, timezone.utc).isoformat(),
                    entries=[], targets=[], risk=None, reason_no_trade='PUBLIC_DATA_UNAVAILABLE',
                    mode='SHADOW_ONLY', trade_authority='NONE')
