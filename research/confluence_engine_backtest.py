"""I-GOD CONFLUENCE ENGINE: isolated public-data research, never execution.

python -m research.confluence_engine_backtest --download
python -m research.confluence_engine_backtest
Only numpy/requests, already required by the repository. Frozen specifications
are written BEFORE results; validation selects and TEST cannot select parameters.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import zipfile
from urllib.parse import urlparse
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'cache' / 'confluence'
OUT = ROOT / 'confluence_artifacts'
STEP = 300000
START = 1577836800000
TRAIN_END = 1640995200000
TEST_START = 1704067200000
ASOF = 1790899200000  # 2026-10-02 00:00 UTC; deterministic closed-bar cutoff

def public_get(url, params=None):
    p = urlparse(url)
    allowed = (p.hostname == 'data.binance.vision' and p.path.startswith('/data/')) or (p.hostname == 'fapi.binance.com' and p.path in ('/fapi/v1/klines', '/fapi/v1/fundingRate'))
    if p.scheme != 'https' or not allowed:
        raise ValueError('Public market data allowlist only')
    r = requests.get(url, params=params, timeout=45)
    if r.status_code != 404:
        r.raise_for_status()
    return r

def ms(x):
    v = int(x)
    return v // 1000 if v > 100000000000000 else v

def month_list():
    for y in range(2020, 2027):
        for m in range(1, 13):
            if (y, m) > (2026, 9):
                return
            yield f'{y}-{m:02d}'

def archive(kind, month):
    prefix = 'klines/BTCUSDT/5m/BTCUSDT-5m' if kind == 'bars' else 'fundingRate/BTCUSDT/BTCUSDT-fundingRate'
    url = f'https://data.binance.vision/data/futures/um/monthly/{prefix}-{month}.zip'
    local = CACHE / f'{kind}-{month}.zip'
    if not local.exists():
        r = public_get(url)
        if r.status_code == 404:
            return [], {'url': url, 'missing': True}
        local.write_bytes(r.content)
    checksum = local.with_suffix('.checksum')
    if not checksum.exists():
        checksum.write_text(public_get(url + '.CHECKSUM').text)
    blob = local.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != checksum.read_text().split()[0]:
        raise ValueError('Archive checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        rows = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))
    if rows and not rows[0][0].isdigit():
        rows = rows[1:]
    return rows, {'url': url, 'sha256': digest, 'official_checksum': True, 'rows': len(rows), 'first_timestamp': ms(rows[0][0]) if rows else None, 'last_timestamp': ms(rows[-1][0]) if rows else None}

def validate(rows, cutoff=ASOF):
    unique = {}
    for r in rows:
        t = ms(r[0])
        if t < START or t + STEP > cutoff:
            continue
        if ms(r[6]) != t + STEP - 1 or t % STEP:
            raise ValueError('Unclosed/misaligned candle')
        v = [t, *map(float, r[1:6]), float(r[9])]
        if not np.all(np.isfinite(v)) or min(v[1:5]) <= 0 or v[3] > min(v[1], v[4]) or v[2] < max(v[1], v[4]) or not 0 <= v[6] <= v[5]:
            raise ValueError('Invalid OHLCV/taker data')
        if t in unique and unique[t] != v:
            raise ValueError('Conflicting duplicate')
        unique[t] = v
    a = np.array([unique[t] for t in sorted(unique)], float)
    if len(a) and np.any(np.diff(a[:, 0]) != STEP):
        raise ValueError('Missing candles: no imputation permitted')
    return a

def download():
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(k, m) for k in ('bars', 'funding') for m in month_list()]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = list(pool.map(lambda job: archive(*job), jobs))
    bars, funding, manifest = [], [], []
    for (kind, month), (rows, info) in zip(jobs, fetched):
        manifest.append(dict(info, kind=kind, month=month))
        if kind == 'bars':
            bars.extend(rows)
        else:
            funding.extend([[ms(r[0]), float(r[2])] for r in rows])
    # Public REST completes unpublished September and the closed October tail.
    a = validate(bars)
    cursor = int(a[-1, 0] + STEP) if len(a) else START
    while cursor < ASOF:
        params = {'symbol': 'BTCUSDT', 'interval': '5m', 'startTime': cursor, 'endTime': ASOF-1, 'limit': 1500}
        url = 'https://fapi.binance.com/fapi/v1/klines'
        local=CACHE/f'rest-bars-{cursor}-{ASOF}.json'
        r=json.loads(local.read_text()) if local.exists() else public_get(url, params).json()
        if not local.exists(): local.write_text(json.dumps(r))
        if not r:
            break
        manifest.append({'url': url, 'params': params, 'rows': len(r), 'first_timestamp': ms(r[0][0]), 'last_timestamp': ms(r[-1][0]), 'sha256': hashlib.sha256(json.dumps(r).encode()).hexdigest()})
        bars.extend(r)
        cursor = ms(r[-1][0]) + STEP
    a = validate(bars)
    cursor = max([r[0] for r in funding], default=START-1)+1
    while cursor < ASOF:
        params = {'symbol': 'BTCUSDT', 'startTime': cursor, 'endTime': ASOF-1, 'limit': 1000}
        url = 'https://fapi.binance.com/fapi/v1/fundingRate'
        local=CACHE/f'rest-funding-{cursor}-{ASOF}.json'
        r=json.loads(local.read_text()) if local.exists() else public_get(url, params).json()
        if not local.exists(): local.write_text(json.dumps(r))
        manifest.append({'url': url, 'params': params, 'rows': len(r), 'first_timestamp':int(r[0]['fundingTime']) if r else None,'last_timestamp':int(r[-1]['fundingTime']) if r else None,'sha256': hashlib.sha256(json.dumps(r).encode()).hexdigest()})
        if not r:
            break
        funding.extend([[int(x['fundingTime']), float(x['fundingRate'])] for x in r])
        cursor = int(r[-1]['fundingTime'])+1
    f = np.array(sorted(dict(funding).items()), float)
    np.savez_compressed(CACHE/'data.npz', bars=a, funding=f)
    manifest.append({'normalized_rows': len(a), 'first_timestamp': int(a[0,0]), 'last_timestamp': int(a[-1,0]), 'funding_rows': len(f), 'normalized_sha256': hashlib.sha256((CACHE/'data.npz').read_bytes()).hexdigest(), 'as_of': ASOF})
    OUT.mkdir(exist_ok=True)
    (OUT/'data_manifest.json').write_text(json.dumps(manifest, indent=2))

def aggregate(a, minutes):
    n = minutes//5
    groups = a[:,0].astype(np.int64)//(minutes*60000)
    starts = np.r_[0, np.flatnonzero(np.diff(groups))+1]
    ends = np.r_[starts[1:], len(a)]
    return np.array([[a[s,0], a[s,1], a[s:e,2].max(), a[s:e,3].min(), a[e-1,4], a[s:e,5].sum(), a[s:e,6].sum()] for s,e in zip(starts,ends) if e-s == n and a[s,0] % (minutes*60000) == 0])

def rolling(x, n, mode='mean'):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        w = np.lib.stride_tricks.sliding_window_view(x,n)
        out[n-1:] = getattr(np, mode)(w, axis=1)
    return out

def shift(x, n=1):
    out = np.full(len(x), np.nan)
    out[n:] = x[:-n]
    return out

def ema(x, alpha):
    out = np.empty(len(x)); value = float(x[0])
    for i,v in enumerate(x):
        value += alpha*(v-value); out[i] = value
    return out

def rsi(close):
    d = np.diff(close, prepend=close[0])
    up, down = ema(np.maximum(d,0),1/14), ema(np.maximum(-d,0),1/14)
    return np.divide(100*up, up+down, out=np.full(len(d),50.), where=up+down>0)

def ml_rsi(close):
    # Deliberately no claim of ML/TradingView identity: fixed causal smoothed RSI.
    v = ema(rsi(close), 2/6)
    state = np.where(v>55, 1, np.where(v<45, -1, 0))
    previous = np.r_[0,state[:-1]]
    return state, (state==1)&(previous==0), (state==-1)&(previous==0)

def pivots(a, oscillator, width=2):
    n=len(a); bull=np.zeros(n,bool); bear=bull.copy(); lo=np.full(n,np.nan); hi=lo.copy()
    lows=[]; highs=[]
    for i in range(n):
        p=i-width
        if p>=width:
            if a[p,3] < np.min(np.r_[a[p-width:p,3],a[p+1:i+1,3]]):
                if lows and a[p,3]<a[lows[-1],3] and oscillator[p]>oscillator[lows[-1]]:
                    bull[i]=True
                lows.append(p)
            if a[p,2] > np.max(np.r_[a[p-width:p,2],a[p+1:i+1,2]]):
                if highs and a[p,2]>a[highs[-1],2] and oscillator[p]<oscillator[highs[-1]]:
                    bear[i]=True
                highs.append(p)
        if lows: lo[i]=a[lows[-1],3]
        if highs: hi[i]=a[highs[-1],2]
    return bull,bear,lo,hi

def align(values, source, minutes, target_close):
    available=source[:,0]+minutes*60000
    idx=np.searchsorted(available,target_close,side='right')-1
    result=np.zeros(len(target_close),dtype=values.dtype)
    valid=idx>=0; result[valid]=values[idx[valid]]
    return result

def recent(x, bars):
    return np.nan_to_num(rolling(x.astype(float),bars,'max'))>0

def features(base, tf, regime_tf=240, window=24, threshold=.60):
    a=aggregate(base,tf); h=aggregate(base,60); g=aggregate(base,regime_tf)
    c=a[:,4]; r=rsi(c); state,green,red=ml_rsi(c)
    times=a[:,0]+tf*60000
    sma=rolling(g[:,4],200); reg=g[:,4]>sma; slope=sma>shift(sma,10)
    lower=shift(rolling(h[:,3],window,'min')); upper=shift(rolling(h[:,2],window,'max'))
    sw=(h[:,3]<lower)&(h[:,4]>lower); us=(h[:,2]>upper)&(h[:,4]<upper)
    # L2: reclaim within the next three closed 1H candles, level fixed at breach.
    reclaim=np.zeros(len(h),bool); reclaim_s=reclaim.copy()
    for lag in (1,2,3):
        reclaim |= (shift(h[:,3],lag)<shift(lower,lag)) & (shift(h[:,4],lag)<=shift(lower,lag)) & (h[:,4]>shift(lower,lag))
        reclaim_s |= (shift(h[:,2],lag)>shift(upper,lag)) & (shift(h[:,4],lag)>=shift(upper,lag)) & (h[:,4]<shift(upper,lag))
    db,ds,low,high=pivots(a,r)
    hb,hs,hl,hh=pivots(h,rsi(h[:,4]))
    hh_up=hh>shift(hh,3); hl_up=hl>shift(hl,3)
    tr=np.maximum(a[:,2]-a[:,3],np.maximum(abs(a[:,2]-shift(c)),abs(a[:,3]-shift(c))))
    tr[0]=a[0,2]-a[0,3]
    ratio=np.divide(a[:,6],a[:,5],out=np.full(len(a),.5),where=a[:,5]>0)
    return a, {'valid_regime':align(np.isfinite(sma),g,regime_tf,times),'reg':align(reg,g,regime_tf,times), 'slope':align(slope,g,regime_tf,times), 'sweep':align(recent(sw|reclaim,3),h,60,times), 'sweep_short':align(recent(us|reclaim_s,3),h,60,times), 'L1':align(sw,h,60,times), 'L2':align(reclaim,h,60,times), 'breakout':align(h[:,4]>shift(hh),h,60,times), 'R3':align(hh_up&hl_up,h,60,times), 'green':green,'red':red,'state':state,'div':recent(db,max(1,180//tf)), 'div_short':recent(ds,max(1,180//tf)), 'flow':ratio>=threshold,'flow_short':ratio<=1-threshold,'volume15':a[:,5]>1.5*rolling(a[:,5],20),'volume2':a[:,5]>2*rolling(a[:,5],20),'rsi_long':(r>55)&(shift(r)<=55),'rsi_short':(r<45)&(shift(r)>=45),'macd':(ema(c,2/13)-ema(c,2/27))-ema(ema(c,2/13)-ema(c,2/27),2/10),'momentum':c>shift(c,12),'atr':ema(tr,1/14),'low':low,'high':high}

def entries(f, family, side=1):
    reg=f['reg'] if side==1 else (~f['reg'] & f['valid_regime'])
    sweep=f['sweep' if side==1 else 'sweep_short']; flow=f['flow' if side==1 else 'flow_short']
    event=f['green' if side==1 else 'red']; state=f['state']==side
    div=f['div' if side==1 else 'div_short']
    mapping={'A':reg&event,'B':reg&sweep&event,'C':reg&sweep&div,'D':reg&flow&state,'E':reg&f['slope']&f['breakout']&state,'F':reg&sweep&state&flow,'R':reg,'L':sweep,'M':state,'RL':reg&sweep,'RM':reg&state,'LM':sweep&state,'RLM':reg&sweep&state}
    return mapping[family]

def funding_vector(a, funding, minutes):
    out=np.zeros(len(a)); ends=a[:,0]+minutes*60000
    for t,rate in funding:
        idx=np.searchsorted(a[:,0],t,side='right')-1
        if idx>=0 and t<ends[idx]: out[idx]+=rate
    return out

def simulate(a, f, signal, funding, tf, exit_kind='opposite', side=1, cost=.001, leverage=1., lo=START, hi=ASOF, benchmark=False):
    idx=np.flatnonzero((a[:,0]>=lo)&(a[:,0]+tf*60000<=hi))
    if not len(idx): return {'metrics':{},'returns':[],'trades':[]}
    rates=funding_vector(a,funding,tf)
    equity=1.; cash=1.; qty=0.; trades=[]; rets=[]; exposures=[]; fees=slippage=paid=turnover=0.; entry_equity=0.; entry_index=0; stop=target=0.; trail=0.
    def close(price,i,reason):
        nonlocal cash,qty,fees,slippage,turnover
        nominal=abs(qty)*price; charge=nominal*cost
        cash += qty*price-charge; fees+=charge*.5; slippage+=charge*.5; turnover+=nominal
        trades.append({'entry_time':int(a[entry_index,0]),'exit_time':int(a[i,0]),'return':cash/entry_equity-1,'reason':reason,'side':side})
        qty=0.
    possible_entries=np.flatnonzero(np.r_[False,signal[:-1]])
    cursor=0
    while cursor<len(idx):
        i=idx[cursor]
        if not qty:
            next_slot=np.searchsorted(possible_entries,i)
            if next_slot==len(possible_entries) or possible_entries[next_slot]>idx[-1] or equity<=0:
                zeros=len(idx)-cursor; rets.extend([0.]*zeros); exposures.extend([False]*zeros); break
            next_i=possible_entries[next_slot]
            skip=int(next_i-i)
            if skip:
                rets.extend([0.]*skip); exposures.extend([False]*skip); cursor+=skip; i=idx[cursor]
        before=equity; opened,high,low,close_price=a[i,1:5]
        if qty:
            opposite=(not f['reg'][i-1]) if benchmark and side==1 else (f['state'][i-1]==-side or (not f['reg'][i-1] if side==1 else f['reg'][i-1]))
            if exit_kind=='opposite' and opposite: close(opened,i,'opposite')
            elif exit_kind=='structure' and ((side==1 and a[i-1,4]<f['low'][i-1]) or (side==-1 and a[i-1,4]>f['high'][i-1])): close(opened,i,'structure')
        # Entry uses ONLY previous closed bar; no same-bar reentry after a stop.
        if not qty and i>0 and signal[i-1] and before>0:
            entry_equity=cash; entry_index=i; qty=side*cash*leverage/opened
            nominal=abs(qty)*opened; charge=nominal*cost; cash-=qty*opened+charge
            fees+=charge*.5; slippage+=charge*.5; turnover+=nominal
            distance=2*f['atr'][i-1]; stop=opened-side*distance; target=opened+side*2*distance; trail=stop
        exposures.append(bool(qty))
        if qty:
            # Funding charged on position at boundary before intrabar exit;
            # 8H timestamps align with opens; any nonaligned timestamp is conservative.
            charge=qty*opened*rates[i]; cash-=charge; paid+=charge
            mark_worst=cash+qty*(low if side==1 else high)
            if leverage>1 and mark_worst<=abs(qty)*(low if side==1 else high)*.005:
                close(((-cash)/(qty*(1-side*.005))),i,'liquidation'); cash=max(cash,0.)
            elif exit_kind in ('atr','rr'):
                breached=low<=trail if side==1 else high>=trail
                hit=high>=target if side==1 else low<=target
                if breached: close(min(opened,trail) if side==1 else max(opened,trail),i,'stop')
                elif exit_kind=='rr' and hit: close(target,i,'target')
                elif exit_kind=='atr': trail=max(trail,close_price-2*f['atr'][i]) if side==1 else min(trail,close_price+2*f['atr'][i])
        equity=cash+qty*close_price
        if equity<=0:
            if qty: trades.append({'entry_time':int(a[entry_index,0]),'exit_time':int(a[i,0]),'return':-1.,'reason':'collateral_insolvency','side':side})
            equity=0.; cash=0.; qty=0.
        rets.append(equity/before-1 if before>0 else 0.)
        cursor+=1
    if qty:
        before=equity; close(a[idx[-1],4],idx[-1],'period_end'); equity=cash
        rets[-1]=(1+rets[-1])*(equity/before)-1
    rr=np.array(rets); metrics=performance(rr,tf)
    ts=np.array([t['return'] for t in trades]); winners=ts[ts>0]; losers=ts[ts<0]
    streak=worst=0
    for t in ts: streak=streak+1 if t<0 else 0; worst=max(worst,streak)
    metrics.update(trades=len(ts),win_rate=float(np.mean(ts>0)) if len(ts) else 0.,expectancy=float(np.mean(ts)) if len(ts) else 0.,avg_winner=float(np.mean(winners)) if len(winners) else 0.,avg_loser=float(np.mean(losers)) if len(losers) else 0.,payoff_ratio=float(-np.mean(winners)/np.mean(losers)) if len(winners) and len(losers) else None,profit_factor=float(-winners.sum()/losers.sum()) if len(losers) else None,turnover=turnover,fees=fees,slippage=slippage,funding=paid,time_in_market=float(np.mean(exposures)),longest_losing_streak=worst)
    return {'metrics':metrics,'returns':rr.tolist(),'trades':trades}

def performance(rr,tf):
    rr=np.asarray(rr); eq=np.cumprod(1+rr); years=len(rr)*tf/(365.25*1440)
    if not len(rr): return {}
    annual=365.25*1440/tf; std=rr.std(); downside=np.sqrt(np.mean(np.minimum(rr,0)**2))
    dd=float(np.min(eq/np.maximum.accumulate(np.r_[1.,eq])[1:]-1)); cagr=float(eq[-1]**(1/years)-1)
    return {'total_return':float(eq[-1]-1),'CAGR':cagr,'Sharpe':float(rr.mean()/std*np.sqrt(annual)) if std else 0.,'Sortino':float(rr.mean()/downside*np.sqrt(annual)) if downside else 0.,'MaxDD':dd,'Calmar':cagr/-dd if dd else None}

def excursions(base, times, side=1, cutoff=ASOF):
    output={}
    indices=np.searchsorted(base[:,0],times)
    for hours in (1,4,12,24,48):
        n=hours*12; valid=indices[(indices+n<=len(base)) & (times+hours*3600000<=cutoff)]; mf=[]; ma=[]
        counts={f'{up}/{dn}':0 for up in (.005,.01,.02,.03) for dn in (.005,.01,.02)}
        for start in range(0,len(valid),512):
            batch=valid[start:start+512]; rows=batch[:,None]+np.arange(n); entry=base[batch,1,None]
            favorable=base[rows,2]/entry-1 if side==1 else 1-base[rows,3]/entry
            adverse=base[rows,3]/entry-1 if side==1 else 1-base[rows,2]/entry
            mf.extend(favorable.max(axis=1).tolist()); ma.extend(adverse.min(axis=1).tolist())
            good={}; bad={}
            for up in (.005,.01,.02,.03):
                touched=favorable>=up; good[up]=np.where(touched.any(axis=1),touched.argmax(axis=1),n)
            for dn in (.005,.01,.02):
                touched=adverse<=-dn; bad[dn]=np.where(touched.any(axis=1),touched.argmax(axis=1),n)
            for up in good:
                for dn in bad: counts[f'{up}/{dn}']+=int(np.sum(good[up]<bad[dn]))
        output[str(hours)]={'n':len(mf),'MFE_mean':float(np.mean(mf)) if mf else None,'MAE_mean':float(np.mean(ma)) if ma else None,'MFE_quantiles':np.quantile(mf,[.1,.5,.9]).tolist() if mf else [],'MAE_quantiles':np.quantile(ma,[.1,.5,.9]).tolist() if ma else [],'first_passage':{k:v/len(mf) if mf else None for k,v in counts.items()}}
    return output

def ablation_signals(f, family):
    """Remove blocks from the selected entry without changing retained blocks."""
    regime=f['reg'] & f['slope'] if family=='E' else f['reg']
    liquidity=f['breakout'] if family=='E' else (f['flow'] if family=='D' else (f['sweep']&f['flow'] if family=='F' else f['sweep']))
    momentum=f['div'] if family=='C' else (f['green'] if family in ('A','B') else f['state']==1)
    # Family A has no liquidity block; diagnostic third block is explicitly added.
    return {'R':regime,'L':liquidity,'M':momentum,'RL':regime&liquidity,'RM':regime&momentum,'LM':liquidity&momentum,'RLM':regime&liquidity&momentum}

def select(rows):
    # No TEST argument or field is consulted. Minimum train+validation count.
    eligible=[r for r in rows if r['TRAIN']['trades']>=20 and r['VALIDATION']['trades']>=20]
    return max(eligible or rows,key=lambda r:(r['VALIDATION']['Sharpe'],r['TRAIN']['Sharpe'],r['id']))

def clean(obj):
    if isinstance(obj,dict): return {k:clean(v) for k,v in obj.items()}
    if isinstance(obj,list): return [clean(v) for v in obj]
    if isinstance(obj,float) and not math.isfinite(obj): return None
    return obj

def load_data():
    path=CACHE/'data.npz'
    manifest=json.loads((OUT/'data_manifest.json').read_text())
    expected=manifest[-1]['normalized_sha256']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError('Normalized dataset checksum mismatch')
    data=np.load(path); base=data['bars']; funding=data['funding']
    if np.any(np.diff(base[:,0])!=STEP) or base[0,0]!=START or base[-1,0]+STEP!=ASOF:
        raise ValueError('Incomplete closed-candle history')
    if np.any(np.diff(funding[:,0])<=0) or np.any(np.diff(funding[:,0])>8*3600000+60000) or funding[0,0]>START or funding[-1,0]<ASOF-8*3600000:
        raise ValueError('Incomplete historical funding')
    return base,funding

def availability_probes():
    """Verify archive availability without pretending samples form full history."""
    observations=[]
    for kind in ('metrics','liquidationSnapshot'):
        for date in ('2020-01-01','2021-12-01','2022-01-01','2026-09-01'):
            url=f'https://data.binance.vision/data/futures/um/daily/{kind}/BTCUSDT/BTCUSDT-{kind}-{date}.zip'
            r=public_get(url); item={'url':url,'date':date,'kind':kind,'status':r.status_code,'used_in_signals':False}
            if r.status_code==200:
                blob=r.content; local=CACHE/f'probe-{kind}-{date}.zip'; local.write_bytes(blob)
                checksum=public_get(url+'.CHECKSUM'); digest=hashlib.sha256(blob).hexdigest()
                verified=checksum.status_code==200 and checksum.text.split()[0]==digest
                if checksum.status_code==200 and not verified: raise ValueError('Probe checksum mismatch')
                with zipfile.ZipFile(io.BytesIO(blob)) as z: rows=list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))
                item.update(sha256=digest,official_checksum_verified=verified,rows=max(0,len(rows)-1),header=rows[0] if rows else [],first_row=rows[1] if len(rows)>1 else [],last_row=rows[-1] if len(rows)>1 else [])
            observations.append(item)
    (OUT/'liquidity_availability_probes.json').write_text(json.dumps(observations,indent=2))

def benchmark_results(base,funding,splits):
    benchmarks={}
    for name in ('V8','BUY_HOLD','FUNDED_HOLD'):
        aa,ff=features(base,240,240); ss=ff['reg'] if name=='V8' else np.ones(len(aa),bool)
        if name!='V8': ff['reg']=np.ones(len(aa),bool)
        rates=np.empty((0,2)) if name=='BUY_HOLD' else funding
        benchmarks[name]={label:simulate(aa,ff,ss,rates,240,benchmark=True,lo=lo,hi=hi)['metrics'] for label,(lo,hi) in splits.items()}
    return benchmarks

def refresh_diagnostics():
    """Accounting diagnostics only; never change entry/exit parameters or selection."""
    d=json.loads((OUT/'results.json').read_text()); base,funding=load_data()
    manifest=json.loads((OUT/'data_manifest.json').read_text())
    for item in manifest:
        if item.get('url','').endswith('/fundingRate'):
            params=item['params']; timestamps=funding[(funding[:,0]>=params['startTime'])&(funding[:,0]<=params['endTime']),0][:params['limit']]
            item['first_timestamp']=int(timestamps[0]) if len(timestamps) else None
            item['last_timestamp']=int(timestamps[-1]) if len(timestamps) else None
    (OUT/'data_manifest.json').write_text(json.dumps(manifest,indent=2))
    b=d['best']; tf=b['tf']; a,f=features(base,tf,b['regime'])
    splits={'TRAIN':(START,TRAIN_END),'VALIDATION':(TRAIN_END,TEST_START),'TEST':(TEST_START,ASOF),'ALL':(START,ASOF)}
    d['benchmarks']=benchmark_results(base,funding,splits)
    (OUT/'benchmark.json').write_text(json.dumps(d['benchmarks'],indent=2))
    signals=ablation_signals(f,b['family'])
    d['ablation']={family:{label:simulate(a,f,mask,funding,tf,b['exit'],lo=lo,hi=hi)['metrics'] for label,(lo,hi) in splits.items()} for family,mask in signals.items()}
    d['ablation_atr_control']={family:{label:simulate(a,f,mask,funding,tf,'atr',lo=lo,hi=hi)['metrics'] for label,(lo,hi) in splits.items()} for family,mask in signals.items()}
    times=a[1:,0][entries(f,b['family'])[:-1]]
    d['excursions']={label:excursions(base,times[(times>=lo)&(times<hi)],cutoff=hi) for label,(lo,hi) in splits.items()}
    d['cost_sensitivity_TEST']={str(bps):simulate(a,f,entries(f,b['family']),funding,tf,b['exit'],cost=bps/10000,lo=TEST_START)['metrics'] for bps in (5,10,20)}
    # Paired daily block bootstrap measures advantage, rather than positivity alone.
    chosen=np.array(simulate(a,f,entries(f,b['family']),funding,tf,b['exit'])['returns'])
    selected_trades=simulate(a,f,entries(f,b['family']),funding,tf,b['exit'])['trades']
    ranked=sorted(selected_trades,key=lambda trade:trade['return'],reverse=True)
    d['remove_best_trade_metrics']={}
    for count in (1,3):
        counterfactual=chosen.copy()
        for trade in ranked[:count]:
            begin=np.searchsorted(a[:,0],trade['entry_time']); end=np.searchsorted(a[:,0],trade['exit_time'])
            counterfactual[begin:end+1]=0.
        d['remove_best_trade_metrics'][str(count)]=performance(counterfactual,tf)
    aa,ff=features(base,240,240); ref=np.array(simulate(aa,ff,ff['reg'],funding,240,benchmark=True)['returns'])
    def daily(rr,minutes):
        size=1440//minutes; n=len(rr)//size
        return np.log1p(rr[:n*size]).reshape(n,size).sum(axis=1)
    actual=daily(chosen,tf); reference=daily(ref,240); rng=np.random.default_rng(773)
    paired=[]; length=min(len(actual),len(reference)); excess=actual[:length]-reference[:length]
    for _ in range(500):
        starts=rng.integers(0,length,size=math.ceil(length/7))
        sample=excess[np.concatenate([(np.arange(7)+s)%length for s in starts])[:length]]
        paired.append(float(sample.mean()*365.25))
    d['paired_bootstrap_vs_V8']={'annual_log_return_difference':float(excess.mean()*365.25),'95_interval':np.quantile(paired,[.025,.975]).tolist(),'probability_positive':float(np.mean(np.array(paired)>0)),'caveat':'descriptive 7-day paired block bootstrap; does not correct 352-candidate selection multiplicity'}
    pair=max(('RL','RM','LM'),key=lambda k:d['ablation'][k]['VALIDATION']['Sharpe'])
    reference_pair=daily(np.array(simulate(a,f,signals[pair],funding,tf,b['exit'])['returns']),tf)
    offset=(TEST_START-START)//86400000; excess=actual[offset:]-reference_pair[offset:]; rng=np.random.default_rng(773); paired=[]
    for _ in range(500):
        starts=rng.integers(0,len(excess),size=math.ceil(len(excess)/7)); sampled=excess[np.concatenate([(np.arange(7)+s)%len(excess) for s in starts])[:len(excess)]]
        paired.append(float(sampled.mean()*365.25))
    d['paired_bootstrap_third_confirmation_TEST']={'two_block_control_selected_on_validation':pair,'annual_log_return_difference':float(excess.mean()*365.25),'95_interval':np.quantile(paired,[.025,.975]).tolist(),'probability_positive':float(np.mean(np.array(paired)>0)),'caveat':'common exit includes regime/momentum; see separate ATR-exit ablation'}
    ts=np.array([t['return'] for t in simulate(a,f,entries(f,b['family']),funding,tf,b['exit'])['trades']]); rng=np.random.default_rng(773)
    samples=[]
    if len(ts):
        for _ in range(500):
            starts=rng.integers(0,len(ts),size=math.ceil(len(ts)/5)); indices=np.concatenate([(np.arange(5)+s)%len(ts) for s in starts])[:len(ts)]
            samples.append(float(ts[indices].mean()))
    d['expectancy_bootstrap_95_interval']=np.quantile(samples,[.025,.975]).tolist() if samples else []
    (OUT/'results.json').write_text(json.dumps(clean(d),indent=2,allow_nan=False)); report(d,base,funding)

def signal_artifacts():
    """Exit-independent forward outcomes for every frozen entry configuration."""
    d=json.loads((OUT/'results.json').read_text())
    base,_=load_data()
    results={}; unique={}
    for row in d['all_candidates']:
        key=(row['tf'],row['regime'],row['family'],row['side'])
        unique[key]=row
    for tf,regime in sorted({(k[0],k[1]) for k in unique}):
        a,f=features(base,tf,regime)
        for key,row in unique.items():
            if key[:2]!=(tf,regime): continue
            sig=entries(f,row['family'],row['side']); times=a[1:,0][sig[:-1]]
            results[f"{row['family']}_{tf}m_R{regime}_{row['side']}"]={label:excursions(base,times[(times>=lo)&(times<hi)],row['side'],hi) for label,(lo,hi) in {'TRAIN':(START,TRAIN_END),'VALIDATION':(TRAIN_END,TEST_START),'TEST':(TEST_START,ASOF)}.items()}
        print(f'Signal outcomes: {tf}m / R{regime}',flush=True)
    with gzip.open(OUT/'all_signal_outcomes.json.gz','wt',encoding='utf-8') as stream:
        json.dump(clean(results),stream,sort_keys=True)
    b=d['best']; a,f=features(base,b['tf'],b['regime']); times=a[1:,0][entries(f,b['family'])[:-1]]
    columns=['timestamp','split']+[f'{kind}_{h}h' for h in (1,4,12,24,48) for kind in ('MFE','MAE')]
    with gzip.open(OUT/'selected_signal_excursions.csv.gz','wt',newline='') as stream:
        writer=csv.writer(stream); writer.writerow(columns)
        for t in times:
            i=np.searchsorted(base[:,0],t); entry=base[i,1]; values=[]
            end=TRAIN_END if t<TRAIN_END else (TEST_START if t<TEST_START else ASOF)
            for h in (1,4,12,24,48):
                path=base[i:i+h*12]
                values.extend([float(path[:,2].max()/entry-1),float(path[:,3].min()/entry-1)] if len(path)==h*12 and t+h*3600000<=end else ['', ''])
            label='TRAIN' if t<TRAIN_END else ('VALIDATION' if t<TEST_START else 'TEST')
            writer.writerow([int(t),label,*values])

def run():
    OUT.mkdir(exist_ok=True)
    spec={'name':'I-GOD CONFLUENCE ENGINE','timeframes':[5,15,30,60],'regime':[60,240],'families':list('ABCDEF'),'exits':['opposite','atr','structure','rr'],'primary_cost_per_side':.001,'cost_split':'50% fee, 50% slippage; market taker assumption','windows':[12,24,48],'imbalance':[.55,.60,.65],'ml_rsi':'RSI14 Wilder recursive initialization, EMA5 smoothing, green>55/red<45; equivalent approximation, no learned model','pivot_width':2,'selection':'validation Sharpe then train Sharpe; minimum 20 trades each; no TEST access','risk':'1x nominal primary, fixed entry quantity; not continuously rebalanced','split':[START,TRAIN_END,TEST_START,ASOF],'bootstrap':'500 stationary contiguous 7-day block resamples, seed 773','promotion':'all ten user gates; positive TEST, net expectancy, Sharpe>=0.5, DD>=-0.35, 20bps positive, robust neighbors, ablation improvement; no best-trade dependence'}
    (OUT/'frozen_spec.json').write_text(json.dumps(spec,indent=2))
    base,funding=load_data()
    if base[-1,0]+STEP<ASOF: raise ValueError('History does not reach frozen cutoff')
    rows=[]; prepared={}
    splits={'TRAIN':(START,TRAIN_END),'VALIDATION':(TRAIN_END,TEST_START),'TEST':(TEST_START,ASOF),'ALL':(START,ASOF)}
    benchmarks=benchmark_results(base,funding,splits)
    (OUT/'benchmark.json').write_text(json.dumps(benchmarks,indent=2))
    for tf in spec['timeframes']:
        for regime in spec['regime']:
            a,f=features(base,tf,regime); prepared[tf,regime]=a,f
            for side in (1,-1):
                # Bearish breakout is separate; E long-only rather than mirrored invalidly.
                for family in ('ABCDF' if side==-1 else 'ABCDEF'):
                    signal=entries(f,family,side)
                    for exit_kind in spec['exits']:
                        item={'id':f'{family}_{tf}m_R{regime}_{side}_{exit_kind}','family':family,'tf':tf,'regime':regime,'side':side,'exit':exit_kind}
                        for label in ('TRAIN','VALIDATION'):
                            item[label]=simulate(a,f,signal,funding,tf,exit_kind,side,lo=splits[label][0],hi=splits[label][1])['metrics']
                        rows.append(item)
            print(f'Frozen train/validation evaluated: trigger={tf} regime={regime}',flush=True)
    best=select([r for r in rows if r['side']==1]); short=select([r for r in rows if r['side']==-1])
    (OUT/'selection_lock.json').write_text(json.dumps({'best':best,'short':short,'spec_sha256':hashlib.sha256((OUT/'frozen_spec.json').read_bytes()).hexdigest()},indent=2))
    # Only after lock do we evaluate TEST for frozen candidates.
    for item in rows:
        a,f=prepared[item['tf'],item['regime']]; sig=entries(f,item['family'],item['side'])
        for label in ('TEST','ALL'):
            evaluated=simulate(a,f,sig,funding,item['tf'],item['exit'],item['side'],lo=splits[label][0],hi=splits[label][1])
            item[label]=evaluated['metrics']
            if label=='ALL':
                rr=np.array(evaluated['returns']); stamps=a[:len(rr),0]
                item['by_year']={str(y):performance(rr[(stamps>=int(datetime(y,1,1,tzinfo=timezone.utc).timestamp()*1000))&(stamps<min(ASOF,int(datetime(y+1,1,1,tzinfo=timezone.utc).timestamp()*1000)))],item['tf']) for y in range(2020,2027)}
                item['by_regime']={name:performance(rr[f['reg'][:len(rr)]==value],item['tf']) for name,value in [('bull',True),('bear',False)]}
    tf=best['tf']; a,f=prepared[tf,best['regime']]; sig=entries(f,best['family']); simulation=simulate(a,f,sig,funding,tf,best['exit'])
    details={'best':best,'best_short':short,'all_candidates':rows,'spec':spec}
    details['benchmarks']=benchmarks
    details['cost_sensitivity']={str(bps):simulate(a,f,sig,funding,tf,best['exit'],cost=bps/10000)['metrics'] for bps in (5,10,20)}
    details['by_year']={str(y):simulate(a,f,sig,funding,tf,best['exit'],lo=int(datetime(y,1,1,tzinfo=timezone.utc).timestamp()*1000),hi=min(ASOF,int(datetime(y+1,1,1,tzinfo=timezone.utc).timestamp()*1000)))['metrics'] for y in range(2020,2027)}
    details['ablation']={family:{label:simulate(a,f,mask,funding,tf,best['exit'],lo=lo,hi=hi)['metrics'] for label,(lo,hi) in splits.items()} for family,mask in ablation_signals(f,best['family']).items()}
    controls={'R1':f['reg'],'R2':f['reg']&f['slope'],'R3':f['R3'],'R4':f['breakout'],'L1':f['L1'],'L2':f['L2'],'L3':f['flow'],'L4_1.5':f['volume15'],'L4_2':f['volume2'],'M1':f['green'],'M2':f['rsi_long'],'M3':(f['macd']>0)&(shift(f['macd'])<=0),'M4':f['momentum']}
    details['predefined_controls']={name:{label:simulate(a,f,mask,funding,tf,best['exit'],lo=lo,hi=hi)['metrics'] for label,(lo,hi) in splits.items()} for name,mask in controls.items()}
    details['neighbors']={}
    for window in (12,24,48):
        for threshold in (.55,.60,.65):
            aa,ff=features(base,tf,best['regime'],window,threshold)
            details['neighbors'][f'{window}/{threshold}']={label:simulate(aa,ff,entries(ff,best['family']),funding,tf,best['exit'],lo=lo,hi=hi)['metrics'] for label,(lo,hi) in splits.items()}
    # Every signal, including overlapping events, measured at next-bar open.
    times=a[1:,0][sig[:-1]]
    details['excursions']={label:excursions(base,times[(times>=lo)&(times<hi)],cutoff=hi) for label,(lo,hi) in splits.items()}
    trades=simulation['trades']; treturns=np.array([t['return'] for t in trades]); order=np.argsort(treturns)[::-1]
    details['remove_best_trades']={str(k):float(np.prod(1+np.delete(treturns,order[:k]))-1) for k in (1,3)}
    details['without_2021_2022']=float(np.prod([1+t['return'] for t in trades if datetime.fromtimestamp(t['entry_time']/1000,timezone.utc).year not in (2021,2022)])-1)
    rr=np.array(simulation['returns']); rng=np.random.default_rng(773); block=7*1440//tf
    estimates=[]
    for _ in range(500):
        starts=rng.integers(0,len(rr),size=math.ceil(len(rr)/block)); sample=np.concatenate([rr[(np.arange(block)+s)%len(rr)] for s in starts])[:len(rr)]
        estimates.append(performance(sample,tf)['CAGR'])
    details['bootstrap']={'CAGR_95_interval':np.quantile(estimates,[.025,.975]).tolist(),'probability_CAGR_positive':float(np.mean(np.array(estimates)>0)),'warning':'Overlapping signals and selection multiplicity; bootstrap is not proof of independent edge'}
    details['by_regime']={name:performance(rr[np.array(f['reg'][:len(rr)])==value],tf) for name,value in [('bull',True),('bear',False)]}
    details['walk_forward']={'method':'fixed pre-TEST validation selection; annual forward evaluation without retuning','years':{str(y):{'selected':best['id'],'metrics':details['by_year'][str(y)]} for y in (2024,2025,2026)}}
    abl=details['ablation']; third=abl['RLM']['VALIDATION']['Sharpe']>max(abl[x]['VALIDATION']['Sharpe'] for x in ('RL','RM','LM')) and abl['RLM']['TEST']['expectancy']>max(abl[x]['TEST']['expectancy'] for x in ('RL','RM','LM'))
    gates={'beats_V8':best['TEST']['Sharpe']>benchmarks['V8']['TEST']['Sharpe'],'positive_test':best['TEST']['total_return']>0,'net_expectancy':best['ALL']['expectancy']>0,'sharpe':best['ALL']['Sharpe']>=.5,'drawdown':best['ALL']['MaxDD']>=-.35,'remove_best':details['remove_best_trades']['1']>0,'neighbors':all(n['TEST']['total_return']>0 for n in details['neighbors'].values()),'20bps':details['cost_sensitivity']['20']['total_return']>0,'1x':best['ALL']['total_return']>0,'ablation':third and best['family']!='A'}
    details['promotion_gates']=gates
    details['conclusion']='PROMOTE TO SHADOW' if all(gates.values()) else ('PROMISING — MORE RESEARCH' if best['TEST']['total_return']>0 and best['ALL']['expectancy']>0 else 'REJECT CONFLUENCE ENGINE')
    details['leverage']={}
    if all(gates.values()):
        details['leverage']={str(lev):simulate(a,f,sig,funding,tf,best['exit'],leverage=lev)['metrics'] for lev in (.25,.5,1,1.25,1.5,2)}
    with gzip.open(OUT/'selected_trades.csv.gz','wt',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['entry_time','exit_time','return','reason','side']); writer.writeheader(); writer.writerows(trades)
    (OUT/'results.json').write_text(json.dumps(clean(details),indent=2,allow_nan=False))
    report(details,base,funding)
    print(json.dumps({'best':best,'conclusion':details['conclusion'],'excursions_TEST_24h':details['excursions']['TEST']['24']},indent=2),flush=True)

def report(d,base,funding):
    b=d['best']; bm=d['benchmarks']['V8']; ex=d['excursions']['TEST']['24']
    lines=['# I-GOD CONFLUENCE ENGINE', '', '**'+d['conclusion']+'**','',f"Frozen best LONG: `{b['id']}`. SHORT evaluated independently: `{d['best_short']['id']}`.",'','Research only. No executor imports, private endpoints, orders, Railway changes, deployment or merge.','',f"Binance BTCUSDT USD-M perpetual, {len(base):,} closed 5m candles, 2020-01-01 through {datetime.fromtimestamp((base[-1,0]+STEP)/1000,timezone.utc).isoformat()}; {len(funding):,} historical funding events. No spot/perp price splice.",'','## Metrics','', '| System / split | CAGR | Sharpe | MaxDD | Return | Trades | Expectancy |','|---|---:|---:|---:|---:|---:|---:|']
    for name,metrics in [('Selected',b),('V8 SMA200 4H',bm),('Buy & hold',d['benchmarks']['BUY_HOLD']),('SHORT',d['best_short'])]:
        for split in ('TRAIN','VALIDATION','TEST','ALL'):
            m=metrics[split]; lines.append(f"| {name} {split} | {m['CAGR']:.2%} | {m['Sharpe']:.3f} | {m['MaxDD']:.2%} | {m['total_return']:.2%} | {m['trades']} | {m['expectancy']:.4%} |")
    lines += ['', '## Signal outcomes', '',f"TEST 24h: +1% before -1% = {ex['first_passage']['0.01/0.01']}; +2% before -1% = {ex['first_passage']['0.02/0.01']}; n={ex['n']}. All signals, overlapping included. Executed next open. Same 5m candle both levels => adverse first. Unresolved paths count as failures. Price probabilities exclude transaction costs; trading metrics include them.", '', f"Longest losing streak: {b['ALL']['longest_losing_streak']}. Without best trade total return: {d['remove_best_trades']['1']:.2%}; without best three: {d['remove_best_trades']['3']:.2%}. Without entries in 2021/2022: {d['without_2021_2022']:.2%}.", '', '## Causality and frozen definitions', '', 'Signals at completed candle close, fill next open. SMA200 uses only completed regime bars. HH/HL and divergences use strict 2-left/2-right pivots with confirmation delayed two trigger bars; no backdated signal. Sweep lookbacks are 12/24/48 closed 1H bars, reclaim within three following bars; sweep validity three 1H bars. Divergence validity 3h. MACD 12/26/9, RSI14 crosses 55/45, momentum12 and volume20 1.5x/2x are computed controls. Main candidates use the predefined A–F families. E uses R2 plus confirmed 1H swing breakout; other entries use R1. R3 is an exploratory structural feature, not a tuned candidate.', '', 'ML RSI exact TradingView version was NOT reproducible: script identity/source unspecified. Approximation is Wilder RSI14 with EMA5 smoothing and fixed neutral [45,55], green >55, red <45. Neutral transitions only, no direct red-to-green transition trigger. This is NOT a trained machine learning model. No future labels or learned coefficients.', '', 'Four exits: opposite state or regime invalidation; 2 ATR14 stop with trailing updated after close; confirmed pivot invalidation at following open; 2 ATR risk / 4 ATR target (1:2). Stop first on ambiguous intrabar touch. Positions are fixed quantities sized at entry equity, no pyramiding. Period boundaries force flat and costs on both sides. Warmup features may use prior periods; holdings cannot cross split boundaries.', '', 'Primary 1x nominal, no liquidation; quantities are fixed until exit. Costs per side 5/10/20 bps total, half fees and half slippage, market taker assumption; not a claim of exchange fee tier. Funding signed and historical at event boundary on current notional. Turnover and costs in units of initial equity. Funding at aligned boundary charged on opening position; exact sequence within nonaligned 5m intervals is conservative. FUNDED_HOLD includes funding; BUY_HOLD is an unfunded underlying-price proxy. Higher leverage evaluated only if all promotion gates survive; isolated margin approximation uses 0.5% maintenance, no claim of exact exchange tiers.', '', '## Statistical checks and limitations', '', 'Selection uses TRAIN through 2021, VALIDATION 2022–2023, minimum 20 trades each, ranked validation Sharpe then train Sharpe. Selection lock is persisted before TEST evaluation. TEST starts 2024 and never reranks candidates. 352 initial candidates (timeframe/regime/side/exit); no claim that these tests are independent. 7-day block bootstrap 500 repetitions seed773, parameter neighbors and ablation are diagnostics, not new selection. Daily dependence and selection bias remain; no corrected statistical significance claimed. The headline annual table resets positions; per-candidate annual equity slices retain positions at year boundaries. Regime results are descriptive conditional bar returns, with compressed time Sharpe, not standalone tradable strategies. Walk-forward is fixed-parameter annual forward evaluation in 2024, 2025 and 2026; no annual retuning. No higher leverage research if primary system fails gates.', '', 'The ablation uses identical regime/sweep/smoothed momentum building blocks and chosen exit; it evaluates states rather than A/B transition events. Therefore it directly tests the three-block RLM construction; if the selected family differs, it is a diagnostic and cannot establish that family’s incremental contribution. Promotion requires all conservative gates including improvement over every two-block ablation.', '', '## Real liquidity data available', '', 'L1/L2 swing sweep and reclaim, L4 volume spikes, and L3 historical taker-buy base volume / total base volume from official kline files. These are reproducible proxies, not resting orderbook liquidity or an Aggr.Trade heatmap. Raw aggTrades were not downloaded because official klines contain the required historical taker volumes. L5 OI and L6 liquidations are excluded: no continuous verified 2020–2026 dataset acquired. This does not assert such archives cannot exist. No current OI, liquidation feed or orderbook used to infer past values.', '', 'Sources: [Binance public data schema](https://github.com/binance/binance-public-data), [funding history](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History). Exact archive URLs, dates, rows, checksums and public REST parameters are in `confluence_artifacts/data_manifest.json`. Datasets cached outside Git; reproduce with `python -m research.confluence_engine_backtest --download`, then offline `python -m research.confluence_engine_backtest`. All metrics, costs, year/regime results, bootstrap, neighbors, ablation, cost sensitivity and five MFE/MAE horizons with all target/barrier pairs are in `results.json`.', '', '## Promotion gates', '', *[f'- {k}: {v}' for k,v in d['promotion_gates'].items()], '', '## Validation', '', '`python -m unittest research.test_confluence_engine -v` and `git diff --check`.']
    lines += ['', '## Decision evidence', '', 'A positive TEST and better Sharpe/drawdown do not establish robust incremental edge. The selected 60% taker threshold has negative TEST neighbors at 55% and 65%. For family D, sweep-window neighbors are identical because sweep is absent; these are not independent stability tests. No parameters were revised after viewing TEST.', '', '| Taker buy threshold | VALIDATION Sharpe | TEST return | TEST expectancy |', '|---|---:|---:|---:|']
    for threshold in (.55,.60,.65):
        item=d['neighbors'][f'24/{threshold}']; lines.append(f"| {threshold:.0%} | {item['VALIDATION']['Sharpe']:.3f} | {item['TEST']['total_return']:.2%} | {item['TEST']['expectancy']:.4%} |")
    lines += ['', '| Ablation | VALIDATION Sharpe | TEST return | TEST expectancy |', '|---|---:|---:|---:|']
    for name,item in d['ablation'].items():
        lines.append(f"| {name} | {item['VALIDATION']['Sharpe']:.3f} | {item['TEST']['total_return']:.2%} | {item['TEST']['expectancy']:.4%} |")
    if 'ablation_atr_control' in d:
        lines += ['', '| Ablation with common ATR exit | VALIDATION Sharpe | TEST return | TEST expectancy |','|---|---:|---:|---:|']
        for name,item in d['ablation_atr_control'].items(): lines.append(f"| {name} | {item['VALIDATION']['Sharpe']:.3f} | {item['TEST']['total_return']:.2%} | {item['TEST']['expectancy']:.4%} |")
    lines += ['', 'The common selected exit itself includes momentum/regime invalidation. Removing a block from entries does not remove it from this exit. In particular, regime-only and momentum-only state entries can repeatedly reenter while the common exit is invalidated, inflating turnover. This ablation is an entry-filter diagnostic, not proof of fully independent complete systems. RLM improves expectancy but does not beat LM on TEST total return. Its mechanical ablation gate must not be interpreted as statistical significance.', '', '| Year | Selected return (flat at year boundary) |', '|---|---:|']
    for year,item in d['by_year'].items(): lines.append(f"| {year} | {item['total_return']:.2%} |")
    lines += ['', '| Cost per side | Full return | TEST return |', '|---|---:|---:|']
    for cost,item in d['cost_sensitivity'].items():
        test=d.get('cost_sensitivity_TEST',{}).get(cost,{}).get('total_return')
        lines.append(f"| {cost} bps | {item['total_return']:.2%} | {format(test,'.2%') if test is not None else 'see results.json'} |")
    if 'paired_bootstrap_vs_V8' in d:
        p=d['paired_bootstrap_vs_V8']; lines += ['', f"Paired daily 7-day-block bootstrap versus V8: annual log-growth difference {p['annual_log_return_difference']:.2%}, 95% interval {p['95_interval']}, probability positive {p['probability_positive']:.1%}. Includes zero, and does not correct selection multiplicity. Expectancy block-bootstrap interval: {d['expectancy_bootstrap_95_interval']}."]
    if 'paired_bootstrap_third_confirmation_TEST' in d:
        p=d['paired_bootstrap_third_confirmation_TEST']; lines += ['', f"Third confirmation paired bootstrap, TEST versus {p['two_block_control_selected_on_validation']} chosen using VALIDATION: annual log-growth difference {p['annual_log_return_difference']:.2%}, 95% interval {p['95_interval']}, probability positive {p['probability_positive']:.1%}. Common ATR exit control above avoids keeping RSI/regime in the exit while removing it from entries. No new entry or exit parameters were selected from these diagnostics."]
    if (OUT/'liquidity_availability_probes.json').exists():
        probes=json.loads((OUT/'liquidity_availability_probes.json').read_text()); lines += ['', 'Archive availability probes (samples, not verified continuous history):']
        lines += [f"- {p['kind']} {p['date']}: HTTP {p['status']}, rows {p.get('rows',0)}, used in signals: false." for p in probes]
    lines += ['', '## Benchmark and risk interpretation', '', 'BUY_HOLD is the unfunded underlying-price control using perpetual OHLC as a price proxy, not a downloaded spot portfolio. FUNDED_HOLD separately models perpetual fixed-quantity holding and all funding. A fixed quantity sized 1x at entry does not maintain constant 1x equity exposure: funding can exhaust collateral and effective leverage can drift. Insolvency floors equity at zero and is recorded; no exchange liquidation is simulated in the primary run. This interpretation also applies to V8 and all candidate trades. Drawdown uses candle-close equity, not intrabar worst equity. These limitations restrict promotion and must be reviewed before a shadow specification.', '', 'All frozen entry configurations have TRAIN/VALIDATION/TEST forward-outcome summaries in `all_signal_outcomes.json.gz`. The selected entry has individual signal MFE/MAE in `selected_signal_excursions.csv.gz`. Forward windows cannot cross split boundaries. The selected actual fills are in `selected_trades.csv.gz`; outcomes are not conditioned on a trade being executed. Diagnostics-only reproduction: `python -m research.confluence_engine_backtest --diagnostics-only`; entry-outcome reproduction: `python -m research.confluence_engine_backtest --signals-only`.']
    (ROOT/'CONFLUENCE_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--download',action='store_true'); parser.add_argument('--signals-only',action='store_true'); parser.add_argument('--diagnostics-only',action='store_true'); parser.add_argument('--availability-only',action='store_true'); args=parser.parse_args()
    if args.availability_only:
        availability_probes()
        raise SystemExit(0)
    if args.diagnostics_only:
        refresh_diagnostics()
        raise SystemExit(0)
    if args.signals_only:
        signal_artifacts()
        raise SystemExit(0)
    if args.download: download()
    run()
    refresh_diagnostics()
    signal_artifacts()
