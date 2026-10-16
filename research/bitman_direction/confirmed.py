"""Read-only projection of existing ML RSI observations. NO mathematical port."""
from datetime import datetime
import json
import math
from pathlib import Path
from .spec import TIMEFRAMES,MLRSI_CONFIG


def unknown(reason):return dict(color='UNKNOWN',reason=reason,source='EXISTING_CONFIRMED_OBSERVER_ONLY')


def confirmed_cache(export,now_ms):
    result={tf:unknown('NO_CONFIRMED_CACHE') for tf in TIMEFRAMES}
    result['1D']=unknown('EXISTING_OBSERVER_HAS_NO_1D')
    try:
        if (export['config_version']!=MLRSI_CONFIG or export['symbol']!='BTCUSDT' or export['venue']!='BINANCE_SPOT'
                or export['trade_authority'] is not False or export['shadow_only'] is not True):return result
        for tf in ('1H','4H'):
            p=export['timeframes'].get(tf.lower(),export['timeframes'].get(tf))
            if not isinstance(p,dict):continue
            p=p.get('observation',p)
            stamp=p['last_closed_timestamp'];read=p['last_successful_read'];v=p['latest_confirmed_values']
            if (type(stamp) is not int or stamp%TIMEFRAMES[tf] or stamp>now_ms or now_ms-stamp>=TIMEFRAMES[tf]
                    or type(read) is not int or read>now_ms or now_ms-read>90000 or p['fresh'] is not True
                    or p['confirmed_color'] not in ('GREEN','RED','NEUTRAL') or v['color']!=p['confirmed_color'] or v['valid'] is not True):continue
            if not all(type(v[k]) in (int,float) and math.isfinite(v[k]) for k in ('mlrsi_smoothed','upper_threshold','lower_threshold')):continue
            result[tf]=dict(color=p['confirmed_color'],closed_at=stamp,observed_at=read,config_version=MLRSI_CONFIG,
                venue='BINANCE_SPOT',source='EXISTING_CONFIRMED_OBSERVER_ONLY',not_private_bitman_rsi=True)
    except (KeyError,ValueError,TypeError,OverflowError,AttributeError):pass
    return result


def read_cache(path,now_ms):
    try:
        with Path(path).open('r',encoding='utf-8') as stream:export=json.load(stream)
        return confirmed_cache(export,now_ms)
    except (OSError,ValueError,TypeError):return {tf:unknown('CACHE_UNAVAILABLE') for tf in TIMEFRAMES}


def confirmed_journal_rows(records):
    """Optional future copied-journal adapter. Never retimes an observation earlier."""
    output=[]
    for r in records:
        try:
            if (r['config_version']!=MLRSI_CONFIG or r['symbol']!='BTCUSDT' or r['source']!='LOW'
                    or r['timeframe'] not in ('1h','4h') or r['candle_complete'] is not True
                    or r['trade_authority'] is not False or r['shadow_only'] is not True
                    or r['event'].startswith(('APPROACHING','PROVISIONAL'))):continue
            color=r['confirmed_color']
            if color not in ('GREEN','RED','NEUTRAL'):continue
            times=[datetime.fromisoformat(r[k].replace('Z','+00:00')) for k in ('recorded_at_utc','candle_timestamp_utc')]
            if any(t.utcoffset() is None or t.utcoffset().total_seconds()!=0 for t in times):continue
            observed,closed=(int(t.timestamp()*1000) for t in times)
            if observed<closed:continue
            output.append(dict(timeframe=r['timeframe'].upper(),closed_at=closed,available_at=observed,color=color,
                config_version=MLRSI_CONFIG,source='FORWARD_LIVE_CONFIRMED_EXPORT'))
        except (KeyError,ValueError,TypeError,OverflowError,AttributeError):continue
    return sorted(output,key=lambda r:(r['available_at'],r['timeframe']))
