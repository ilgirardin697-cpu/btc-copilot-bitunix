"""Frozen-formula weekly AO/BBWP study. Historical, offline, no authority."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import sys

import numpy as np

from bitman_manual.frozen.indicators import calculate, lag, roll
from research.bitman_weekly_data import FOUR_HOURS, WEEK, MONDAY, CUTOFF, aggregate_weeks

SEED = 20261020
REPLICATES = 2000
BLOCK = 8
HORIZONS = (1, 2, 4)
EPOCHS = ('2020-2022', '2023-2024', '2025-2026')
CORE_METRICS = ('forward', 'signed', 'absolute', 'mfe', 'mae', 'max_move')
CI_METRICS = ('signed', 'absolute', 'max_move', 'hit')
THRESHOLDS = (3, 5, 10, 15)


def iso(timestamp):
    return datetime.fromtimestamp(int(timestamp)/1000, timezone.utc).isoformat()


def weekly_features(frame):
    f = calculate(frame)
    f['frame'] = frame
    f['available_at'] = frame[:, 0] + WEEK
    f['prior_bbwp'] = lag(f['bbwp'])
    f['prior_slope'] = lag(f['bbwp_slope'])
    f['color'] = np.where(f['ao_slope'] > 0, 'GREEN', np.where(f['ao_slope'] < 0, 'RED', 'FLAT'))
    f['ao_side'] = np.where(f['ao_slope'] > 0, 1., np.where(f['ao_slope'] < 0, -1., np.nan))
    # Common eligibility, including previous slope for START; never shorten warmup.
    f['valid'] = np.logical_and.reduce([np.isfinite(f[k]) for k in
        ('ao', 'ao_slope', 'bbwp', 'bbwp_slope', 'prior_slope')])
    prior_run, run = [], 0
    for slope in f['bbwp_slope']:
        prior_run.append(run)
        run = run + 1 if np.isfinite(slope) and slope <= 0 else 0
    f['prior_nonincreasing'] = np.asarray(prior_run)
    years = np.asarray([datetime.fromtimestamp(t/1000, timezone.utc).year for t in f['available_at']])
    f['epoch'] = np.where(years <= 2022, EPOCHS[0], np.where(years <= 2024, EPOCHS[1], EPOCHS[2]))
    f['phase'] = np.arange(len(frame)) % 4
    return f


def features(four, cutoff=CUTOFF):
    weekly, excluded = aggregate_weeks(four, cutoff)
    frame = np.asarray([[r[j] for j in (0, 1, 2, 3, 4, 5, 9)] for r in weekly], float)
    f = weekly_features(frame)
    four_array = np.asarray([[r[0], r[4]] for r in four], float)
    sma = roll(four_array[:, 1], 200)
    ids = np.searchsorted(four_array[:, 0] + FOUR_HOURS, f['available_at'], side='right') - 1
    sign = np.sign(four_array[ids, 1] - sma[ids])
    f['regime'] = np.where(sign > 0, 'BULL', np.where(sign < 0, 'BEAR', np.where(sign == 0, 'FLAT', 'UNKNOWN')))
    f['regime_4h_close'] = four_array[ids, 1]
    f['regime_sma200'] = sma[ids]
    f['regime_available_at'] = four_array[ids, 0] + FOUR_HOURS
    return f, weekly, excluded


def events(f):
    rising, falling = f['bbwp_slope'] > 0, f['bbwp_slope'] < 0
    start = rising & (f['prior_slope'] <= 0)
    previous = f['prior_bbwp']
    masks = dict(ALL=np.ones(len(rising), bool), A_RISING=rising, B_FALLING=falling, C_START=start)
    masks.update({'D_PRIOR_'+str(n): start & (f['prior_nonincreasing'] >= n) for n in (2, 3, 4)})
    masks['E_0_10'] = start & (previous >= 0) & (previous <= 10)
    for lo, hi in ((10, 20), (20, 30), (30, 50)):
        masks['E_'+str(lo)+'_'+str(hi)] = start & (previous > lo) & (previous <= hi)
    masks['E_GT50'] = start & (previous > 50)
    masks['F_CROSS50'] = (f['bbwp'] > 50) & (previous <= 50)
    masks['F_BELOW50_RISING'] = rising & (f['bbwp'] < 50)
    masks['F_ABOVE50_RISING'] = rising & (f['bbwp'] > 50)
    return {name: mask & f['valid'] for name, mask in masks.items()}


def outcomes(f, horizon):
    frame = f['frame']
    n = len(frame)
    out = {k: np.full(n, np.nan) for k in (*CORE_METRICS, 'hit', 'up', 'down', 'flat')}
    out.update({kind+'_ge_'+str(t): np.full(n, np.nan) for kind in ('terminal', 'move') for t in THRESHOLDS})
    for i in range(n - horizon):
        anchor = frame[i, 4]
        future = frame[i+1:i+horizon+1]
        r = 100 * (future[-1, 4] / anchor - 1)
        up = max(0., 100 * (np.max(future[:, 2]) / anchor - 1))
        down = max(0., 100 * (1 - np.min(future[:, 3]) / anchor))
        side = f['ao_side'][i]
        values = dict(forward=r, signed=side*r, absolute=abs(r), max_move=max(up, down),
                      mfe=up if side == 1 else down if side == -1 else np.nan,
                      mae=down if side == 1 else up if side == -1 else np.nan,
                      hit=float(side*r > 0) if np.isfinite(side) else np.nan,
                      up=float(r > 0), down=float(r < 0), flat=float(r == 0))
        for t in THRESHOLDS:
            values['terminal_ge_'+str(t)] = float(abs(r) >= t)
            values['move_ge_'+str(t)] = float(max(up, down) >= t)
        for key, value in values.items():
            out[key][i] = value
    return out


def block_counts(n, replicates=REPLICATES, seed=SEED, block=BLOCK):
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(replicates, (n+block-1)//block))
    draws = ((starts[:, :, None] + np.arange(block)) % n).reshape(replicates, -1)[:, :n]
    return np.asarray([np.bincount(row, minlength=n) for row in draws], dtype=np.int16)


def bootstrap_mean(values, mask, weights):
    selected = mask & np.isfinite(values)
    counts = weights[:, selected]
    denominator = counts.sum(axis=1)
    numerator = (counts * values[selected]).sum(axis=1)
    return np.divide(numerator, denominator, out=np.full(len(weights), np.nan), where=denominator > 0)


def interval(samples, n):
    finite = samples[np.isfinite(samples)]
    if n < 10 or len(finite) < .95 * len(samples):
        return None, None
    return tuple(float(v) for v in np.quantile(finite, (.025, .975)))


def bootstrap_median(values, mask, weights):
    selected = np.flatnonzero(mask & np.isfinite(values))
    selected = selected[np.argsort(values[selected], kind='stable')]
    if not len(selected):
        return np.full(len(weights), np.nan)
    counts = weights[:, selected]
    total = counts.sum(axis=1)
    cumulative = np.cumsum(counts, axis=1)
    lower = np.argmax(cumulative > ((total-1)//2)[:, None], axis=1)
    upper = np.argmax(cumulative > (total//2)[:, None], axis=1)
    result = (values[selected[lower]] + values[selected[upper]]) / 2
    result[total == 0] = np.nan
    return result


def describe(f, out, grid, mask, weights, scope, name, stratum, horizon, with_ci=True):
    local = mask[grid]
    ids = grid[local]
    n = len(ids)
    eligible = mask & np.isin(np.arange(len(mask)), grid)
    episodes = int(np.count_nonzero(eligible & ~np.r_[False, eligible[:-1]]))
    exposure = int(np.count_nonzero(f['epoch'][grid]==scope)) if scope in EPOCHS else (
               int(np.count_nonzero(f['regime'][grid]==scope)) if scope in ('BULL','BEAR') else len(grid))
    row = dict(scope=scope, event=name, stratum=stratum, horizon=horizon, n=n,
               episodes=episodes, annual_frequency=n/(exposure/52.1775) if exposure else 0,
               exposure_weeks=exposure,
               sample_status='INSUFFICIENT FOR CONCLUSION' if n < 30 else 'DESCRIPTIVE ONLY')
    for metric in CORE_METRICS:
        values = out[metric][ids]
        values = values[np.isfinite(values)]
        row[metric+'_n'] = len(values)
        for key in ('mean', 'median', 'sd', 'min', 'max', 'p10', 'p25', 'p75', 'p90', 'ex_best1_mean', 'ex_best3_mean'):
            row[metric+'_'+key] = None
        if len(values):
            ordered = np.sort(values)
            row.update({metric+'_mean': float(np.mean(values)), metric+'_median': float(np.median(values)),
                        metric+'_sd': float(np.std(values)), metric+'_min': float(ordered[0]), metric+'_max': float(ordered[-1])})
            row.update({metric+'_p'+str(p): float(np.percentile(values, p)) for p in (10, 25, 75, 90)})
            for k in (1, 3):
                row[metric+'_ex_best'+str(k)+'_mean'] = float(np.mean(ordered[:-k])) if len(values) > k else None
        if metric in CI_METRICS:
            row[metric+'_ci_low'], row[metric+'_ci_high'] = interval(bootstrap_mean(out[metric][grid], local, weights), len(values)) if with_ci else (None, None)
            row[metric+'_median_ci_low'], row[metric+'_median_ci_high'] = interval(bootstrap_median(out[metric][grid], local, weights), len(values)) if with_ci else (None, None)
    for metric in ('hit', 'up', 'down', 'flat', *('terminal_ge_'+str(t) for t in THRESHOLDS), *('move_ge_'+str(t) for t in THRESHOLDS)):
        v = out[metric][ids]
        v = v[np.isfinite(v)]
        row[metric] = float(np.mean(v)) if len(v) else None
    hit = out['hit'][ids]
    row['hit_ci_low'], row['hit_ci_high'] = interval(bootstrap_mean(out['hit'][grid], local, weights), np.isfinite(hit).sum()) if with_ci else (None, None)
    return row


def strata(f):
    result = {'ALL': np.ones(len(f['valid']), bool), 'GREEN': f['color'] == 'GREEN', 'RED': f['color'] == 'RED'}
    for color, sign in itertools.product(('GREEN', 'RED'), ('POS', 'NEG')):
        result[color+'_'+sign] = result[color] & ((f['ao'] > 0) if sign == 'POS' else (f['ao'] < 0))
    return result


def past_controls(out, grid, horizon):
    """Outcomes of control weeks must already be mature at the event close."""
    result = {k: np.full(len(out['forward']), np.nan) for k in ('absolute', 'max_move', 'forward', 'up', 'down')}
    for i in grid:
        previous = grid[(grid >= i-52) & (grid+horizon <= i)]
        if len(previous) >= 12:
            for metric in result:
                result[metric][i] = float(np.mean(out[metric][previous]))
    return result


def contrast(out, grid, weights, event, reference, metric, side=None):
    values = out[metric][grid]
    if side is not None:
        values = side * out['forward'][grid] if metric == 'signed' else (side*out['forward'][grid] > 0).astype(float)
    a, b = event[grid] & np.isfinite(values), reference[grid] & np.isfinite(values)
    av, bv = values[a], values[b]
    difference = float(av.mean()-bv.mean()) if len(av) and len(bv) else None
    ci = interval(bootstrap_mean(values, a, weights)-bootstrap_mean(values, b, weights), min(len(av),len(bv)))
    trims = {}
    for k in (1, 3):
        trims['ex_best'+str(k)+'_difference'] = float(np.mean(np.sort(av)[:-k])-bv.mean()) if len(av)>k and len(bv) else None
    return dict(metric=metric, n_event=len(av), n_reference=len(bv), difference=difference, ci_low=ci[0], ci_high=ci[1], **trims)


def analyze(f, replicates=REPLICATES):
    masks, colors = events(f), strata(f)
    summaries, comparisons, temporal, observations, influence = [], [], [], [], []
    for h in HORIZONS:
        out = outcomes(f, h)
        grid = np.flatnonzero(f['valid'] & np.isfinite(out['forward']))
        weights = block_counts(len(grid), replicates, SEED+h)
        for name, event in masks.items():
            for stratum, color in colors.items():
                mask = event & color & np.isfinite(out['forward'])
                summaries.append(describe(f,out,grid,mask,weights,'FULL',name,stratum,h))
                if stratum not in ('ALL', 'GREEN', 'RED'):
                    continue
                for epoch in EPOCHS:
                    summaries.append(describe(f,out,grid,mask & (f['epoch']==epoch),weights,epoch,name,stratum,h))
                for regime in ('BULL', 'BEAR'):
                    summaries.append(describe(f,out,grid,mask & (f['regime']==regime),weights,regime,name,stratum,h))
        for color, rising, adx, di in itertools.product(('GREEN','RED'),(True,False),('RISING','FALLING'),('BULLISH','BEARISH','NEUTRAL')):
            di_mask = (f['di_plus'] > f['di_minus']) if di=='BULLISH' else (f['di_plus'] < f['di_minus']) if di=='BEARISH' else (f['di_plus']==f['di_minus'])
            adx_mask = (f['adx_slope'] > 0) if adx=='RISING' else (f['adx_slope'] < 0)
            name = ('A_RISING' if rising else 'B_FALLING')+'|ADX_'+adx+'|DI_'+di
            mask = masks['A_RISING' if rising else 'B_FALLING'] & colors[color] & adx_mask & di_mask
            summaries.append(describe(f,out,grid,mask,weights,'ADX_SECONDARY',name,color,h))
        for phase in range(4):
            for name, color in (('ALL','ALL'),('A_RISING','ALL'),('B_FALLING','ALL'),('A_RISING','GREEN'),('A_RISING','RED'),('ALL','GREEN'),('ALL','RED')):
                mask = masks[name] & colors[color] & (f['phase']==phase)
                summaries.append(describe(f,out,grid,mask,weights,'NONOVERLAP_'+str(phase),name,color,h,False))
        for metric in ('absolute', 'max_move'):
            row = contrast(out,grid,weights,masks['A_RISING'],masks['B_FALLING'],metric)
            comparisons.append(dict(kind='MAGNITUDE',horizon=h,color='ALL',reference='B_FALLING',**row))
        for color, side in (('GREEN',1),('RED',-1)):
            event = masks['A_RISING'] & colors[color]
            for reference, baseline in (('A_RISING_CONSTANT_SIDE',masks['A_RISING']),('SAME_COLOR',colors[color]&f['valid']),('FALLING_SAME_COLOR',masks['B_FALLING']&colors[color])):
                for metric in ('signed','hit'):
                    row = contrast(out,grid,weights,event,baseline,metric,side)
                    comparisons.append(dict(kind='DIRECTION',horizon=h,color=color,reference=reference,**row))
        # Complete the user-specified grid; these are descriptive, not rule selection.
        for name,event in masks.items():
            for reference,baseline in (('ALL',masks['ALL']),('B_FALLING',masks['B_FALLING'])):
                for metric in ('absolute','max_move'):
                    comparisons.append(dict(kind='EVENT_MAGNITUDE',event=name,horizon=h,color='ALL',reference=reference,
                        **contrast(out,grid,weights,event,baseline,metric)))
            for color,side in (('GREEN',1),('RED',-1)):
                for reference,baseline in (('EVENT_WITHOUT_AO',event),('SAME_COLOR',colors[color]&f['valid'])):
                    for metric in ('signed','hit'):
                        comparisons.append(dict(kind='EVENT_DIRECTION',event=name,horizon=h,color=color,reference=reference,
                            **contrast(out,grid,weights,event&colors[color],baseline,metric,side)))
        for color, rising, adx, di in itertools.product(('GREEN','RED'),(True,False),('RISING','FALLING'),('BULLISH','BEARISH','NEUTRAL')):
            di_mask=(f['di_plus']>f['di_minus']) if di=='BULLISH' else (f['di_plus']<f['di_minus']) if di=='BEARISH' else (f['di_plus']==f['di_minus'])
            base=masks['A_RISING' if rising else 'B_FALLING']&colors[color]
            adx_mask=(f['adx_slope']>0) if adx=='RISING' else (f['adx_slope']<0)
            other=(f['adx_slope']<0) if adx=='RISING' else (f['adx_slope']>0)
            for reference,baseline in (('SAME_AO_BBWP',base),('OTHER_ADX_SAME_DI',base&di_mask&other)):
                for metric in ('signed','max_move'):
                    comparisons.append(dict(kind='ADX_SECONDARY',event=('A_RISING' if rising else 'B_FALLING')+'|ADX_'+adx+'|DI_'+di,
                        horizon=h,color=color,reference=reference,**contrast(out,grid,weights,base&di_mask&adx_mask,baseline,metric)))
        past = past_controls(out, grid, h)
        for name, color in (('ALL','ALL'),('A_RISING','ALL'),('B_FALLING','ALL'),('C_START','ALL'),('A_RISING','GREEN'),('A_RISING','RED')):
            for metric in ('absolute','max_move','signed'):
                mask = masks[name] & colors[color]
                difference = out[metric] - (f['ao_side']*past['forward'] if metric=='signed' else past[metric])
                v = difference[grid]
                selected = mask[grid] & np.isfinite(v)
                ci = interval(bootstrap_mean(v,selected,weights), selected.sum())
                temporal.append(dict(event=name,color=color,horizon=h,metric=metric,n=int(selected.sum()),
                                     mean_excess=float(v[selected].mean()) if selected.any() else None,ci_low=ci[0],ci_high=ci[1]))
        for i in grid:
            observations.append(dict(open_time=int(f['time'][i]),available_at=int(f['available_at'][i]),epoch=str(f['epoch'][i]),
                regime=str(f['regime'][i]),ao_color=str(f['color'][i]),ao=float(f['ao'][i]),bbwp=float(f['bbwp'][i]),
                bbwp_slope=float(f['bbwp_slope'][i]),horizon=h,**{k:float(v[i]) if np.isfinite(v[i]) else None for k,v in out.items()}))
        for name in masks:
            for color in colors:
                ids = grid[(masks[name]&colors[color])[grid]]
                for metric in ('signed','absolute','max_move'):
                    ordered = sorted((int(i) for i in ids if np.isfinite(out[metric][i])), key=lambda i:out[metric][i], reverse=True)
                    influence.append(dict(event=name,color=color,horizon=h,metric=metric,
                        best_three=[dict(available_at=iso(f['available_at'][i]),value=float(out[metric][i])) for i in ordered[:3]]))
    return dict(summaries=summaries,contrasts=comparisons,temporal=temporal,observations=observations,influence=influence)


def lookup(result,scope,event,stratum,horizon):
    return next(r for r in result['summaries'] if (r['scope'],r['event'],r['stratum'],r['horizon'])==(scope,event,stratum,horizon))


def decision(result):
    magnitude = [r for r in result['contrasts'] if r['kind']=='MAGNITUDE']
    direction = [r for r in result['contrasts'] if r['kind']=='DIRECTION' and
                 (r['reference']=='A_RISING_CONSTANT_SIDE' or r['metric']=='signed' and r['reference']=='SAME_COLOR')]
    good = lambda r: r['n_event']>=30 and r['n_reference']>=30 and r['ci_low'] is not None and r['ci_low']>0 and r['ex_best3_difference'] is not None and r['ex_best3_difference']>0
    mag = all(good(r) for r in magnitude)
    direct = all(good(r) for r in direction)
    apparent_fragile = False
    reasons = []
    for h in HORIZONS:
        for epoch in EPOCHS:
            a,b = (lookup(result,epoch,k,'ALL',h) for k in ('A_RISING','B_FALLING'))
            for metric in ('absolute','max_move'):
                point = next(r for r in magnitude if r['horizon']==h and r['metric']==metric)
                era_lift = a[metric+'_mean']-b[metric+'_mean'] if a['n'] and b['n'] else None
                if a['n']<10 or b['n']<10 or era_lift is None or era_lift<=0:
                    mag=False
                    reasons.append(f'MAGNITUDE_{h}W_{epoch}_{metric}_NOT_ROBUST')
                if point['difference'] is not None and point['difference']>0 and (era_lift is not None and era_lift<=0 or point['ex_best3_difference'] is not None and point['ex_best3_difference']<=0):
                    apparent_fragile=True
            for color,side in (('GREEN',1),('RED',-1)):
                event=lookup(result,epoch,'A_RISING',color,h)
                base=lookup(result,epoch,'A_RISING','ALL',h)
                same=lookup(result,epoch,'ALL',color,h)
                signed=event['signed_mean']
                drift=base['forward_mean']
                constant_hit = base['up'] if side==1 else base['down']
                if (event['n']<10 or signed is None or signed<=0 or drift is None or signed-side*drift<=0
                    or event['hit'] is None or constant_hit is None or event['hit']-constant_hit<=0
                    or same['signed_mean'] is None or signed-same['signed_mean']<=0):
                    direct=False
                    reasons.append(f'DIRECTION_{color}_{h}W_{epoch}_NOT_ROBUST')
        for color in ('GREEN','RED'):
            row=lookup(result,'FULL','A_RISING',color,h)
            if row['signed_ci_low'] is None or row['signed_ci_low']<=0 or row['signed_ex_best3_mean'] is None or row['signed_ex_best3_mean']<=0:
                direct=False
    label = ('ROBUST EXPANSION EFFECT — DIRECTION EFFECT ROBUST' if direct else
             'ROBUST EXPANSION EFFECT — DIRECTION INCONCLUSIVE') if mag else (
             'EXPANSION EFFECT FRAGILE' if apparent_fragile else 'INCONCLUSIVE — DO NOT INTEGRATE')
    return dict(conclusion=label,magnitude_robust=mag,direction_robust=direct,
                integration='DO NOT INTEGRATE' if not mag else 'FUTURE SPECIFICATION ONLY; FORWARD AUDIT REQUIRED',
                failed_epoch_checks=reasons)


def current_observation(f, result):
    i=len(f['time'])-1
    start=events(f)['C_START'][i]
    rising=f['bbwp_slope'][i]>0
    cooling=f['bbwp_slope'][i]<0
    classification='STARTING' if start else 'ACTIVE' if rising else 'COOLING' if cooling else 'UNKNOWN (FLAT BBWP)'
    return dict(label='CURRENT OBSERVATION — NOT PART OF VALIDATION',week_open=iso(f['time'][i]),
        available_at=iso(f['available_at'][i]),ao=float(f['ao'][i]),ao_slope=float(f['ao_slope'][i]),ao_color=str(f['color'][i]),
        previous_bbwp=float(f['prior_bbwp'][i]),bbwp=float(f['bbwp'][i]),bbwp_slope=float(f['bbwp_slope'][i]),
        expansion=classification,prior_nonincreasing=int(f['prior_nonincreasing'][i]),
        strong_move_watch='UNKNOWN — NOT VALIDATED',note='Descriptive labels only; no runtime gate or signal. Cooling does not assert low volatility.')


def write_csv(path, rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def load_snapshot(directory):
    """Offline reproduction from versioned public weekly bars + frozen regime labels."""
    directory=Path(directory)
    with (directory/'weekly_bars.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    frame=np.asarray([[float(r[k]) for k in ('open_time','open','high','low','close','base_volume','taker_buy_base_volume')] for r in rows])
    if (frame.ndim!=2 or frame.shape[1]!=7 or not len(frame) or not np.isfinite(frame).all()
        or np.any(frame[:,1:5]<=0) or np.any(frame[:,2]<np.maximum(frame[:,1],frame[:,4]))
        or np.any(frame[:,3]>np.minimum(frame[:,1],frame[:,4])) or np.any(frame[:,3]>frame[:,2])
        or np.any(frame[:,5]<0) or np.any(frame[:,6]<0) or np.any(frame[:,6]>frame[:,5])):
        raise ValueError('SNAPSHOT_VALUES')
    if np.any(np.diff(frame[:,0])!=WEEK) or np.any((frame[:,0]-MONDAY)%WEEK):
        raise ValueError('SNAPSHOT_GAP')
    f=weekly_features(frame)
    with (directory/'weekly_features.csv').open(encoding='utf-8',newline='') as stream:
        saved=list(csv.DictReader(stream))
    if len(saved)!=len(frame) or [int(r['open_time']) for r in saved]!=frame[:,0].astype(np.int64).tolist():
        raise ValueError('SNAPSHOT_ALIGNMENT')
    for key in ('close','ao','ao_slope','bbwp','bbwp_slope','adx','adx_slope','di_plus','di_minus'):
        values=np.asarray([float(r[key]) if r[key] else np.nan for r in saved])
        if not np.allclose(values,f[key],rtol=0,atol=1e-10,equal_nan=True):
            raise ValueError('SNAPSHOT_FORMULA_DISAGREEMENT')
        if key.endswith('slope') and not np.array_equal(np.sign(values),np.sign(f[key]),equal_nan=True):
            raise ValueError('SNAPSHOT_SLOPE_SIGN_DISAGREEMENT')
    f['regime']=np.asarray([r['regime'] for r in saved])
    if not all(r in ('BULL','BEAR','FLAT','UNKNOWN') for r in f['regime']):
        raise ValueError('SNAPSHOT_REGIME_INVALID')
    for key in ('regime_4h_close','regime_sma200','regime_available_at'):
        f[key]=np.asarray([float(r[key]) if r[key] else np.nan for r in saved])
    if not np.array_equal(f['regime_available_at'],f['available_at']):
        raise ValueError('SNAPSHOT_REGIME_LOOKAHEAD')
    sign=np.sign(f['regime_4h_close']-f['regime_sma200'])
    expected=np.where(sign>0,'BULL',np.where(sign<0,'BEAR',np.where(sign==0,'FLAT','UNKNOWN')))
    if not np.array_equal(expected,f['regime']):
        raise ValueError('SNAPSHOT_REGIME_FORMULA_DISAGREEMENT')
    return f


def run(cache, destination):
    cache,destination=Path(cache),Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((cache/'manifest.json').read_text('utf-8'))
    raw=(cache/'four_hour.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['four_hour.json']['sha256']:
        raise ValueError('INPUT_HASH_MISMATCH')
    f, weekly, _=features(json.loads(raw),manifest['cutoff'])
    native=[]
    for request in manifest['requests']:
        if (request.get('params') or {}).get('interval')=='1w':
            data=(cache/request['file']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=request['sha256']:
                raise ValueError('NATIVE_HASH_MISMATCH')
            native.extend(r for r in json.loads(data) if r[0]>=weekly[0][0])
    native_features=calculate(np.asarray([[r[j] for j in (0,1,2,3,4,5,9)] for r in native],float))
    equivalence={key:bool(np.array_equal(f[key],native_features[key],equal_nan=True)) for key in
                 ('ao','ao_slope','bbwp','bbwp_slope','adx','adx_slope','di_plus','di_minus')}
    if not all(equivalence.values()):
        raise ValueError('PRIMARY_INDICATOR_SOURCE_DISAGREEMENT')
    result=analyze(f)
    result['decision']=decision(result)
    result['current']=current_observation(f,result)
    result['metadata']=dict(weeks=len(weekly),valid_weeks=int(f['valid'].sum()),
        python_version=sys.version.split()[0],numpy_version=np.__version__,
        first_bbwp_at=iso(f['available_at'][np.flatnonzero(np.isfinite(f['bbwp']))[0]]),
        first_valid_at=iso(f['available_at'][np.flatnonzero(f['valid'])[0]]),
        last_closed_at=iso(f['available_at'][-1]),bbwp_flat=int(((f['bbwp_slope']==0)&f['valid']).sum()),
        ao_flat=int(((f['ao_slope']==0)&f['valid']).sum()),ao_zero=int(((f['ao']==0)&f['valid']).sum()),
        warmup_excluded=int((~f['valid']).sum()),native_indicator_equivalence=equivalence,
        bootstrap=dict(seed=SEED,replicates=REPLICATES,block_weeks=BLOCK),
        cutoff=manifest['cutoff'],protocol_sha256=manifest['protocol_sha256'])
    for name in ('summaries','contrasts','temporal','observations'):
        write_csv(destination/(name+'.csv'),result[name])
    (destination/'analysis.json').write_text(json.dumps({k:v for k,v in result.items() if k not in ('summaries','observations')},indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (destination/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    write_csv(destination/'weekly_features.csv',[dict(open_time=int(f['time'][i]),available_at=int(f['available_at'][i]),
        **{key:float(f[key][i]) if np.isfinite(f[key][i]) else None for key in ('close','ao','ao_slope','bbwp','bbwp_slope','adx','adx_slope','di_plus','di_minus','regime_4h_close','regime_sma200','regime_available_at')},
        epoch=str(f['epoch'][i]),regime=str(f['regime'][i]),valid=bool(f['valid'][i])) for i in range(len(weekly))])
    write_csv(destination/'weekly_bars.csv',[dict(zip(('open_time','open','high','low','close','base_volume','taker_buy_base_volume'),[r[j] for j in (0,1,2,3,4,5,9)])) for r in weekly])
    names=('analysis.json','contrasts.csv','data_manifest.json','observations.csv','summaries.csv','temporal.csv','weekly_bars.csv','weekly_features.csv')
    integrity=dict(normalization='CRLF to LF only',sha256={name:hashlib.sha256((destination/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in names})
    (destination/'artifact_manifest.json').write_text(json.dumps(integrity,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--cache')
    source.add_argument('--replay',help='Offline recomputation from versioned public CSVs, no writes/network')
    parser.add_argument('--output',default='research/results/bitman_weekly_expansion')
    args=parser.parse_args()
    if args.replay:
        f=load_snapshot(args.replay)
        result=analyze(f)
        result.update(decision=decision(result),current=current_observation(f,result),
                      metadata=dict(weeks=len(f['time']),valid_weeks=int(f['valid'].sum()),offline_replay=True))
    else:
        result=run(args.cache,args.output)
    print(json.dumps({k:result[k] for k in ('metadata','decision','current')},indent=2))
