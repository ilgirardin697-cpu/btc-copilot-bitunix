"""Strict named-column comparison; an unprovided platform export cannot pass."""
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .diagnostic import features, H

FIELDS = ('ao', 'adx', 'plus_di', 'minus_di', 'pececillos', 'tendencia', 'roja', 'tiburones', 'bbwp_7_100', 'bbwp_13_252')
SETTINGS = dict(ao_fast=5, ao_slow=34, dmi_length=14, adx_smoothing=14,
                koncorde='SUPPLIED_BITMAN_PROXY_DEFAULTS', bbwp_basis='SMA', bbwp_source='close',
                bbwp_profiles=[[7, 100], [13, 252]], timeframe_seconds=3600)


def compare(records, metadata, bars, market_venue):
    blockers = []
    if metadata.get('settings') != SETTINGS:
        blockers.append('EXACT_INDICATOR_SETTINGS_NOT_VERIFIED')
    if metadata.get('platform') != 'TradingOne' or metadata.get('source_kind') != 'REAL_PLATFORM_EXPORT':
        blockers.append('NOT_VERIFIED_TRADINGONE_EXPORT')
    if metadata.get('venue') != market_venue or not metadata.get('full_ticker'):
        blockers.append('EXACT_MARKET_NOT_VERIFIED')
    if metadata.get('history_first_open_ms') != int(bars[0, 0]):
        blockers.append('INITIALIZATION_PREFIX_NOT_VERIFIED')
    if metadata.get('indicator_identities_reviewed') is not True:
        blockers.append('INDICATOR_IDENTITIES_NOT_VERIFIED')
    f = features(bars)
    index = {int(t): i for i, t in enumerate(bars[:, 0])}
    differences, previous = [], None
    for row in records:
        t = int(row['open_time_ms'])
        if t % H or previous is not None and t != previous+H:
            raise ValueError('EXPORT_GAP_DUPLICATE_OR_ORDER')
        previous = t
        if str(row.get('confirmed')).lower() != 'true' or int(row['available_at_ms']) != t+H:
            raise ValueError('CLOSED_AVAILABILITY_REQUIRED')
        if t not in index:
            raise ValueError('NO_SAME_VENUE_MARKET_ROW')
        i = index[t]
        for name, value in dict(zip(('open','high','low','close','volume'), bars[i, 1:]), **{k:f[k][i] for k in FIELDS}).items():
            actual = row.get(name)
            if actual in (None, '', 'NA', 'na'):
                differences.append(dict(open_time_ms=t, field=name, error=None, match=False, status='NO_EXTERNAL_VALUE'))
                continue
            actual = float(actual)
            if not np.isfinite(actual):
                raise ValueError('NONFINITE_EXTERNAL_VALUE')
            decimals = metadata.get('decimal_places', {}).get(name)
            if decimals is not None and (type(decimals) is not int or not 2 <= decimals <= 15):
                raise ValueError('EXPLICIT_ROUNDING_PRECISION_REQUIRED')
            tolerance = 1e-7 + (0 if decimals is None else .5*10**(-decimals))
            error = float(abs(actual-value)) if np.isfinite(value) else None
            differences.append(dict(open_time_ms=t, field=name, error=error, tolerance=tolerance,
                                    match=error is not None and error <= tolerance, status='COMPARABLE' if error is not None else 'PYTHON_WARMUP'))
    if not records:
        blockers.append('NO_REAL_PLATFORM_ROWS')
    if any(not x['match'] for x in differences):
        blockers.append('NUMERIC_OR_MISSING_VALUES')
    return dict(status='NOT_ESTABLISHED' if blockers else 'NUMERIC_MATCH_REQUIRES_SOURCE_REVIEW',
                external_rows=len(records), blockers=blockers, differences=differences,
                note='Synthetic self-consistency tests cannot certify external parity; rounded ties cannot certify a slope change.')


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('export',type=Path);p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--market',type=Path,required=True);p.add_argument('--venue',required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise SystemExit('NEW_OUTPUT_PATH_REQUIRED')
    raw=args.export.read_bytes();meta=json.loads(args.metadata.read_text('utf-8-sig'))
    if hashlib.sha256(args.market.read_bytes()).hexdigest()!=meta.get('market_sha256'):
        raise SystemExit('SAME_MARKET_SHA256_REQUIRED')
    with np.load(args.market,allow_pickle=False) as z:bars=z['bars']
    records=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    result=compare(records,meta,bars,args.venue)
    result['export_sha256']=hashlib.sha256(raw).hexdigest()
    result['metadata_sha256']=hashlib.sha256(args.metadata.read_bytes()).hexdigest()
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],external_rows=result['external_rows'],blockers=result['blockers'])))
