"""Read the actual host's atomic state file; never calculate any ML RSI."""
import json
import math
from pathlib import Path
from .frozen.confirmed import confirmed_cache
from .frozen.constants import MLRSI_CONFIG


def read_current(path, now_ms):
    try:
        with Path(path).open('r', encoding='utf-8') as stream:
            raw = stream.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError
        export = json.loads(raw)
    except (OSError, ValueError, TypeError):
        export = {}
    engine = confirmed_cache(export, now_ms)  # frozen 1H/4H confirmation rules
    display = {tf: engine[tf].copy() for tf in ('1H', '4H')}
    display['15m'] = dict(color='UNKNOWN')
    try:
        if (export['config_version'] != MLRSI_CONFIG or export['symbol'] != 'BTCUSDT'
                or export['venue'] != 'BINANCE_SPOT' or export['shadow_only'] is not True or export['trade_authority'] is not False):
            return engine, display
        p = export['timeframes']['15m']['observation']
        stamp, read, values = p['last_closed_timestamp'], p['last_successful_read'], p['latest_confirmed_values']
        interval = 900000
        if (type(stamp) is int and stamp % interval == 0 and stamp <= now_ms < stamp + interval
                and type(read) is int and 0 <= now_ms - read <= 90000 and p['fresh'] is True
                and p['confirmed_color'] in ('GREEN', 'RED', 'NEUTRAL') and values['color'] == p['confirmed_color']
                and values['valid'] is True and all(type(values[k]) in (float, int) and math.isfinite(values[k])
                    for k in ('mlrsi_smoothed', 'upper_threshold', 'lower_threshold'))):
            display['15m'] = dict(color=p['confirmed_color'], closed_at=stamp, observed_at=read)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        pass
    return engine, display
