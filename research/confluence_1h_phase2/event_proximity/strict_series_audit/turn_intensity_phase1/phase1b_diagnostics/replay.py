"""Contaminated November diagnostics: availability, not original live emission."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import csv,gzip,hashlib,io,json
from pathlib import Path
import numpy as np
from .. import detect as frozen
from research.confluence_1h.data import iso,stamp
from .trace import simple_turn

HOUR=frozen.HOUR
MADRID=ZoneInfo('Europe/Madrid')
HERE=Path(__file__).resolve().parent
BEGIN=stamp('2026-11-12T00:00:00+01:00')
END=stamp('2026-11-16T00:00:00+01:00')


def madrid(t):return datetime.fromtimestamp(t/1000,timezone.utc).astimezone(MADRID).isoformat()


def read_fixture(venue):
    p=HERE/'fixtures'/(venue+'_H1.csv.gz');raw=p.read_bytes()
    m=json.loads((HERE/'fixtures'/(venue+'_manifest.json')).read_text())
    if hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('DIAGNOSTIC_FIXTURE_CHANGED')
    a=np.asarray(list(csv.reader(io.StringIO(gzip.decompress(raw).decode())))[1:],float)
    if not np.isfinite(a).all() or not (np.diff(a[:,0])==HOUR).all() or a[-1,0]+HOUR>m['closed_cutoff_ms']:
        raise ValueError('CLOSED_CONTIGUOUS_DATA_REQUIRED')
    return a,m


def hourly(venue,a,f,events,trace):
    ev={};tr={}
    for e in events:ev.setdefault(e['i'],[]).append(dict(pattern=e['pattern'],side=e['side'],strata=e['strata'],tokens=e['tokens']))
    for r in trace:tr.setdefault(r['i'],[]).append(r)
    out=[]
    for i in range(4,len(a)):
        if not BEGIN<=a[i,0]<END:continue
        d=f['ao'][i]-f['ao'][i-1]
        row=dict(venue=venue,i=i,bar_open_utc=iso(a[i,0]),bar_open_madrid=madrid(a[i,0]),
                 earliest_available_utc=iso(a[i,0]+HOUR),available_madrid=madrid(a[i,0]+HOUR),
                 actual_original_emitted_at=None,capture_mode='HISTORICAL_DIAGNOSTIC_NOT_FORWARD',
                 open=a[i,1],high=a[i,2],low=a[i,3],close=a[i,4],adx=f['adx'][i],
                 plus_di=f['plus_di'][i],minus_di=f['minus_di'][i],adx_slope=f['adx_slope'][i],
                 ao=f['ao'][i],ao_sign='ABOVE' if f['ao'][i]>0 else 'BELOW' if f['ao'][i]<0 else 'ZERO',
                 ao_color='GREEN' if d>0 else 'RED' if d<0 else 'FLAT',ao_slope=d,
                 ao_previous_color='GREEN' if f['ao'][i-1]>f['ao'][i-2] else 'RED' if f['ao'][i-1]<f['ao'][i-2] else 'FLAT',
                 ao_color_changed=bool(np.sign(d)!=np.sign(f['ao'][i-1]-f['ao'][i-2])),
                 ao_zero_cross_up=bool(f['ao'][i]>0 and f['ao'][i-1]<=0),ao_zero_cross_down=bool(f['ao'][i]<0 and f['ao'][i-1]>=0),
                 pececillos=f['minnows'][i],red_ema=f['kon_signal'][i],bbwp=f['bbwp'][i],
                 pece_cross_up=bool(f['minnows'][i]>f['kon_signal'][i] and f['minnows'][i-1]<=f['kon_signal'][i-1]),
                 pece_cross_down=bool(f['minnows'][i]<f['kon_signal'][i] and f['minnows'][i-1]>=f['kon_signal'][i-1]),
                 next_open_utc=iso(a[i+1,0]) if i+1<len(a) else None,
                 next_open_reference=a[i+1,1] if i+1<len(a) else None,
                 confirmed_events=ev.get(i,[]))
        for key,name in [('adx','adx'),('ao','ao'),('minnows','pece')]:
            vals=f[key]
            for side,label in [(1,'up'),(-1,'down')]:
                row[name+'_simple_'+label]=bool(simple_turn(vals,side)[i])
                row[name+'_22_'+label]=bool(frozen.two_turn(vals,side)[i])
        for offset in range(4):row['pece_delta_lag'+str(offset)]=f['minnows'][i-offset]-f['minnows'][i-offset-1]
        row['p1_long_missing']=[n for r in tr.get(i,[]) if r['pattern']==frozen.PATTERNS[0] and r['side']==1 for n in r['missing_tokens']]
        row['p1_long_failed']=[n for r in tr.get(i,[]) if r['pattern']==frozen.PATTERNS[0] and r['side']==1 for n in r['failed_flags']]
        out.append(row)
    return out


def latency(venue,a,f,events):
    """Every AO2+2 turn, never selected by subsequent favorable price moves."""
    out=[]
    for side in (1,-1):
        for i in np.flatnonzero(frozen.two_turn(f['ao'],side)):
            if not BEGIN<=a[i,0]<END or i<4:continue
            vertex=int(i)-2
            sign=f['ao'][i]
            patterns=[frozen.PATTERNS[1],frozen.PATTERNS[0] if side*sign<0 else frozen.PATTERNS[2]]
            ref=float(a[vertex,3 if side==1 else 2])
            group=f'{venue}:{side}:{iso(a[i,0]+HOUR)}'
            stages=[('EXTREME_HINDSIGHT',None,vertex,False),('FIRST_SLOPE_OBSERVABLE',vertex+1,vertex+2,True),
                    ('AO22_CONFIRMED',int(i),int(i)+1,True)]
            for pattern in patterns:
                full=next((e for e in events if e['pattern']==pattern and e['side']==side and e['tokens']['ao']==i and e['i']<=i+24),None)
                stage_rows=stages+[('FULL_FROZEN_COINCIDENCE',full['i'] if full else None,full['i']+1 if full else None,True)]
                for name,signal,entry_i,causal in stage_rows:
                    usable=entry_i is not None and entry_i<len(a)
                    row=dict(group_id=group,venue=venue,pattern=pattern,side=side,stage=name,
                             ao22_available=iso(a[i,0]+HOUR),vertex_bar_open=iso(a[vertex,0]),
                             extreme_reference=ref,reference_definition='Low/high inside AO vertex candle; hindsight, not certified global price extreme',
                             extreme_intrabar_timestamp='UNKNOWN',causal=causal,
                             signal_available=iso(a[signal,0]+HOUR) if signal is not None else None,
                             entry_at=iso(a[entry_i,0]) if usable else None,
                             entry_reference=(float(a[entry_i,1]) if causal else ref) if usable else None,
                             status='OBSERVED' if usable else 'NOT_CONFIRMED' if full is None and name=='FULL_FROZEN_COINCIDENCE' else 'CENSORED',
                             evidence='CONTAMINATED_DIAGNOSTIC_PRICE_ONLY_NOT_PNL')
                    if usable:
                        entry=row['entry_reference'];row['entry_model_slip']=entry*(1+side*.0005) if causal else None
                        row['move_from_hindsight_ref']=side*(entry-ref)/ref
                        row['delay_from_vertex_close_h']=(a[entry_i,0]-(a[vertex,0]+HOUR))/HOUR if causal else None
                        # Common24h endpoint prevents comparing differing look-forward windows.
                        end=vertex+1+24
                        row['common_endpoint']=iso(a[vertex,0]+25*HOUR)
                        row['common_endpoint_complete']=end<len(a)
                        held=a[entry_i:end] if causal else a[vertex+1:end]
                        if end<len(a) and len(held):
                            row['remaining_mfe_fraction']=max(0.,float(held[:,2].max()-entry) if side==1 else float(entry-held[:,3].min()))/entry
                            row['remaining_mae_fraction']=max(0.,float(entry-held[:,3].min()) if side==1 else float(held[:,2].max()-entry))/entry
                        before=a[vertex+1:entry_i] if causal else np.empty((0,6))
                        row['favorable_before_confirmation']=max(0.,float(before[:,2].max()-ref) if side==1 else float(ref-before[:,3].min()))/ref if len(before) else 0.
                        for h in (4,12,24):
                            row['post_'+str(h)+'h_price_fraction']=side*(float(a[entry_i+h,1])-entry)/entry if causal and entry_i+h<len(a) else None
                    out.append(row)
    return out


def early_turns(venue,a,f):
    """All simple turns, including those never surviving to2+2.

    This avoids presenting the latency subset conditioned on a later2+2
    confirmation as an independent test of first-slope entries.
    """
    out=[]
    for key,label in [('adx','ADX'),('ao','AO'),('minnows','PECECILLOS')]:
        values=f[key];d=values-frozen.lag(values)
        for side in (1,-1):
            later22=frozen.two_turn(values,side)
            for i in np.flatnonzero(simple_turn(values,side)):
                if i<3 or not BEGIN<=a[i,0]<END:continue
                prior=0;j=int(i)-1
                while j>=1 and side*d[j]<0:
                    prior+=1;j-=1
                status='PRIOR_RUN_LT2' if prior<2 else 'CENSORED' if i+1>=len(a) else 'CONFIRMED22' if later22[i+1] else 'NEXT_SLOPE_FAILED'
                out.append(dict(venue=venue,series=label,side=side,bar_open=iso(a[i,0]),
                                available=iso(a[i,0]+HOUR),available_madrid=madrid(a[i,0]+HOUR),
                                value=values[i],slope=d[i],prior_opposite_slopes=prior,
                                next_open_reference=float(a[i+1,1]) if i+1<len(a) else None,
                                later22_status=status,confirmation22=iso(a[i+1,0]+HOUR) if status=='CONFIRMED22' else None,
                                trade_authority='NONE',evidence='ALL_SIMPLE_TURNS_NOT_AN_ENTRY_STRATEGY'))
    return out
