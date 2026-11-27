"""Offline comparison using existing public candles; source bytes never executed."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import importlib
import io
import json
import numpy as np
from . import audit as a

HERE = Path(__file__).resolve().parent
DATA = a.profile.HERE / 'seq/a26/d'
PROFILES = [('LOREN_APK_DEFAULT_LOW27_SMA4', 27, 'SMA'),
            ('TRADINGONE_LOW27_ALMA4', 27, 'ALMA'),
            ('OPERATIONAL_PARAMS_LOW29_EMA4', 29, 'EMA')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(tf):
    manifest = json.loads((DATA / 'manifest.json').read_text('utf-8'))
    if manifest['venue'] != 'BINANCE_SPOT' or manifest['symbol'] != 'BTCUSDT':
        raise ValueError('SOURCE_VENUE')
    path = DATA / (tf + '.csv.gz')
    if sha(path) != manifest['frames'][tf]['sha256']:
        raise ValueError('SOURCE_BYTES_CHANGED')
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        rows = np.asarray(list(csv.reader(f))[1:], float)
    if len(rows) != manifest['frames'][tf]['rows']:
        raise ValueError('ROW_COUNT')
    return a.checked_bars(rows, {'1h': a.HOUR, '4h': 4*a.HOUR}[tf], manifest['cutoff']), manifest


def utc(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()


def write_csv(path, rows):
    if not rows:
        return
    text = io.StringIO(newline='')
    w = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    raw = text.getvalue().encode('utf-8')
    if path.suffix == '.gz':
        blob = io.BytesIO()
        with gzip.GzipFile(fileobj=blob, filename='', mode='wb', mtime=0) as f:
            f.write(raw)
        raw = blob.getvalue()
    path.write_bytes(raw)


def finite(value):
    return float(value) if np.isfinite(value) else None


def metric(x, y):
    good = np.isfinite(x) & np.isfinite(y)
    d = np.abs(x[good]-y[good])
    return dict(paired=int(good.sum()), max_abs=float(d.max()) if len(d) else None,
                mean_abs=float(d.mean()) if len(d) else None,
                different_gt_1e_9=int((d > 1e-9).sum()),
                availability_differences=int(np.count_nonzero(np.isfinite(x) != np.isfinite(y))))


def compare(out):
    if out.exists():
        raise ValueError('OUTPUT_EXISTS')
    out.mkdir(parents=True)
    bars, manifest = load('1h')
    _, fe = a.fractal_energy(bars)
    rows = []
    gate_rows = []
    summaries = []
    profiles = {}
    for name, length, method in PROFILES:
        values = a.smoothed_rsi(bars[:, 3], length, method)
        seeds = a.percentile_thresholds(values, len(bars)-1)
        apk = a.percentile_thresholds(values, len(bars)-1, finite_only=True)
        cross = a.crosses(values, seeds[:, 0], seeds[:, 2])
        recent = np.array([np.nanmax(fe[max(0, i-6):i+1]) if np.isfinite(fe[max(0, i-6):i+1]).any() else np.nan for i in range(len(fe))])
        # Separate shared cooldown states: unfiltered crosses vs TXT FE gate.
        last_raw = -9999
        cooled = np.zeros(len(bars), int)
        selected = np.zeros(len(bars), int)
        cooldown = a.SharedCooldown()
        for i in range(len(bars)):
            if cross[i] and i-last_raw > 10:
                cooled[i] = cross[i]
                last_raw = i
            if i:
                selected[i] = cooldown.accept(i, cross[i], fe[i], fe[i-1], recent[i])
            if cross[i]:
                gate_rows.append(dict(profile=name, available_at=utc(bars[i, 0]+a.HOUR), side=int(cross[i]),
                    rsi=finite(values[i]), lower=finite(seeds[i, 0]), upper=finite(seeds[i, 2]),
                    fe=finite(fe[i]), fe_previous=finite(fe[i-1]) if i else None,
                    fe_recent7=finite(recent[i]), falling=bool(i and fe[i]<fe[i-1]),
                    above38_2=bool(fe[i]>38.2), recent50=bool(recent[i]>=50),
                    ml_only_shared_cooldown=bool(cooled[i]), ml_fe_shared_cooldown=bool(selected[i])))
            rows.append(dict(profile=name, week_or_signal='NONE_SOURCE_AUDIT', open_time=utc(bars[i, 0]),
                available_at=utc(bars[i, 0]+a.HOUR), value=finite(values[i]),
                p25=finite(seeds[i, 0]), p50=finite(seeds[i, 1]), p75=finite(seeds[i, 2]),
                apk_finite_p25=finite(apk[i, 0]), apk_finite_p75=finite(apk[i, 2]), fe=finite(fe[i])))
        final = a.lloyd_diagnostic(values)
        summary = dict(profile=name, final_rsi=finite(values[-1]), final_seed=seeds[-1].tolist(),
            final_lloyd=[finite(v) for v in final], apk_finite_threshold_differences=metric(seeds[:, 0], apk[:, 0]),
            raw_crosses=dict(Counter('UP' if x>0 else 'DOWN' for x in cross if x)),
            ml_only_after_cooldown=int(np.count_nonzero(cooled)), ml_fe_after_cooldown=int(np.count_nonzero(selected)),
            incremental_predictive_value='NOT_ESTABLISHED_BY_GATE_COUNTS')
        if method in ('ALMA', 'EMA'):
            literal = a.original.OriginalMLRSI(len(bars)-1, length=length, ma=method)
            legacy = [literal.push(float(low)) for low in bars[:, 3]]
            summary['literal_existing_comparison'] = {
                field: metric(np.array([np.nan if r[key] is None else r[key] for r in legacy]), arr)
                for field, key, arr in [('value', 'value', values), ('lower', 'lower', seeds[:, 0]), ('upper', 'upper', seeds[:, 2])]}
        summaries.append(summary)
        profiles[name] = values
    mean_rows = []
    mean_summary = []
    for tf in ('1h', '4h'):
        b, _ = load(tf)
        cfg = a.profile.settings()['active_inputs']['tsa'].copy()
        cfg['max_length'] = 118
        port = a.profile.tsa(b, cfg)['tsa_trend']
        scalar = a.trend_mean_reference(b[:, 4], 118, 2.8)
        mean119 = a.trend_mean_reference(b[:, 4], 119, 2.8)
        reject = a.rejection_observations(b, scalar)
        mean_summary.append(dict(tf=tf, rows=len(b), mean_same_parameters=metric(port, scalar),
            parameter118_vs119=metric(scalar, mean119),
            own_descriptive_touch_rejections=dict(Counter('UP' if x>0 else 'DOWN' for x in reject if x))))
        for i in range(len(b)):
            mean_rows.append(dict(tf=tf, available_at=utc(b[i, 0]+(a.HOUR if tf=='1h' else 4*a.HOUR)),
                close=float(b[i, 4]), mean118=float(scalar[i]), mean119=float(mean119[i]),
                rejection_observation=int(reject[i]), original_bitman_definition='NOT_VERIFIED'))
    report = dict(plan_sha256=sha(HERE/'plan.json'), source_commit='1e3005fdc8465a4778ce235f7f59484617d1cba0',
        venue=manifest['venue'], symbol=manifest['symbol'], rows=len(bars), first_open=utc(bars[0, 0]),
        available_through=utc(bars[-1, 0]+a.HOUR), load_anchor=len(bars)-1,
        source_manifest_sha256=sha(DATA/'manifest.json'), profiles=summaries,
        cross_profile_rsi={k: metric(profiles[PROFILES[0][0]], v) for k, v in profiles.items()},
        bbwp_generic_apk_vs_tradingone=metric(a.apk_bbwp_reference(bars[:, 4]), a.tradingone_bbwp(bars[:, 4])),
        trend_speed=mean_summary, original_js_executed=False, external_parity_certified=False,
        pnl_or_profitability_evaluated=False, conclusion='SOURCE_DIFFERENCES_ESTABLISHED_PRIVATE_BITMAN_PARITY_NOT_PROVEN')
    write_csv(out/'profiles.csv.gz', rows)
    write_csv(out/'fe_gate_counts.csv', gate_rows)
    write_csv(out/'ts.csv.gz', mean_rows)
    (out/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', 'utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    report = compare(p.parse_args().out)
    print(json.dumps({k: report[k] for k in ('rows', 'available_through', 'original_js_executed', 'external_parity_certified', 'conclusion')}))
