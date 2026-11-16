"""Unvalidated comparative facts; never imported by the emission engine."""
import numpy as np
import hashlib,json
from research.confluence_1h.indicators import calculate,lag

HOUR=3600000
DAY=24*HOUR


def scalar(v):return float(v) if np.isfinite(v) else None


def mtf(a):
    result={};asof=int(a[-1,0]+HOUR)
    for name,size,offset in [('1H',HOUR,0),('4H',4*HOUR,0),('1D',DAY,0),('1W',7*DAY,4*DAY)]:
        ids=((a[:,0]-offset)//size).astype(int);groups=[]
        for group in np.unique(ids):
            start=int(group*size+offset);b=a[ids==group]
            if start+size>asof or len(b)!=size//HOUR or not np.array_equal(b[:,0],start+np.arange(len(b))*HOUR):continue
            groups.append([start,b[0,1],b[:,2].max(),b[:,3].min(),b[-1,4],b[:,5].sum()])
        b=np.asarray(groups,float).reshape((-1,6));row=dict(closed=True,rows=len(b),available_at=None,state='UNKNOWN')
        if len(b):
            row['available_at']=int(b[-1,0]+size);row['open_time']=int(b[-1,0]);row['close']=float(b[-1,4])
            f=calculate(b);ao=scalar(f['ao'][-1]) if len(b)>=34 else None
            row.update(ao=ao,ao_slope=scalar(f['ao'][-1]-f['ao'][-2]) if len(b)>=35 else None,
                       adx=scalar(f['adx'][-1]) if len(b)>=28 else None,
                       plus_di=scalar(f['plus_di'][-1]) if len(b)>=28 else None,minus_di=scalar(f['minus_di'][-1]) if len(b)>=28 else None,
                       pececillos=scalar(f['minnows'][-1]) if len(b)>=90 else None,
                       bbwp=scalar(f['bbwp'][-1]) if len(b)>=108 else None,
                       price_sma200=scalar(b[-200:,4].mean()) if len(b)>=200 else None)
            if ao is not None:row['state']='AO_ABOVE_ZERO' if ao>0 else 'AO_BELOW_ZERO' if ao<0 else 'AO_ZERO'
            row['price_regime']='UNKNOWN' if row['price_sma200'] is None else 'ABOVE' if row['close']>row['price_sma200'] else 'BELOW' if row['close']<row['price_sma200'] else 'AT'
        result[name]=row
    return result


class Facts:
    def __init__(self):
        self.breaks={};self.recoveries={};self.last_rebound=None;self.watch=None;self.pair_tokens={};self.pair_ids=set()

    def step(self,i,a,f,contexts=True):
        now=int(a[i,0]+HOUR);events=[];atomics=[]
        def fact(kind,**values):
            row=dict(kind=kind,available_at=now,**values)
            row['fact_id']=kind+':'+str(now)+':'+hashlib.sha256(json.dumps(row,sort_keys=True,allow_nan=False).encode()).hexdigest()[:16]
            events.append(row);return row
        values={name:scalar(f[key][i]) for name,key in [('adx','adx'),('plus_di','plus_di'),('minus_di','minus_di'),
                 ('ao','ao'),('pececillos','minnows'),('red_ema15_tendencia','kon_signal'),('tendencia','kon_trend'),('tiburones','sharks'),('bbwp','bbwp')]}
        if i<4:return dict(values=values,events=[],watch=None,mtf={} if not contexts else mtf(a[:i+1]))
        slopes={name:scalar(f[key][i]-f[key][i-1]) for name,key in [('adx','adx'),('ao','ao'),('pececillos','minnows'),('red_ema15_tendencia','kon_signal'),('bbwp','bbwp')]}
        for series,key in [('ADX','adx'),('AO','ao'),('pececillos','minnows'),('ma_trend','kon_signal')]:
            x=f[key]
            for n in (1,2):
                for side in (1,-1):
                    if all(side*(x[i-j]-x[i-j-1])>0 for j in range(n)) and all(side*(x[i-j]-x[i-j-1])<0 for j in range(n,2*n)):
                        row=fact('SLOPE_TURN',series=series,side=side,n=n,vertex_at=int(a[i-n,0]+HOUR),value=scalar(x[i]))
                        row['comparison_anchor_id']=series+':'+str(side)+':'+str(int(a[i-n,0]+HOUR))
                        atomics.append(row)
        for series,key in [('AO','ao'),('pececillos','minnows'),('tendencia','kon_trend'),('tiburones','sharks'),('ma_trend','kon_signal')]:
            x=f[key]
            if x[i]>0 and x[i-1]<=0:fact('ZERO_CROSS',series=series,side=1,previous=scalar(x[i-1]),current=scalar(x[i]))
            elif x[i]<0 and x[i-1]>=0:fact('ZERO_CROSS',series=series,side=-1,previous=scalar(x[i-1]),current=scalar(x[i]))
        pece,red=f['minnows'],f['kon_signal']
        if pece[i]>red[i] and pece[i-1]<=red[i-1]:fact('PECECILLOS_RED_CROSS',series='pececillos_vs_EMA15_tendencia',side=1)
        elif pece[i]<red[i] and pece[i-1]>=red[i-1]:fact('PECECILLOS_RED_CROSS',series='pececillos_vs_EMA15_tendencia',side=-1)
        bs=f['bbwp'][i]-f['bbwp'][i-1];bp=f['bbwp'][i-1]-f['bbwp'][i-2]
        if bs>0 and bp<=0:fact('BBWP_SLOPE_TURN',series='BBWP',side=1,level=scalar(f['bbwp'][i]),slope=scalar(bs))
        elif bs<0 and bp>=0:fact('BBWP_SLOPE_TURN',series='BBWP',side=-1,level=scalar(f['bbwp'][i]),slope=scalar(bs))
        # AO/ADX pairs are comparative labels, not additional model emissions.
        for e in atomics:
            if e['series'] in ('AO','ADX'):self.pair_tokens[e['n'],e['series'],e['side']]=(i,e['fact_id'])
        for n in (1,2):
            for aos in (1,-1):
                for ads in (1,-1):
                    aa=self.pair_tokens.get((n,'AO',aos));dd=self.pair_tokens.get((n,'ADX',ads))
                    if aa and dd and i-min(aa[0],dd[0])<=2:
                        identity=(aa[1],dd[1])
                        if identity not in self.pair_ids:
                            self.pair_ids.add(identity);fact('AO_ADX_PAIR',n=n,side=aos,adx_turn_direction=ads,components=list(identity))
        # Price levels use prior20 closes/candles only, never the current high.
        if i>=20:
            high=float(a[i-20:i,2].max());low=float(a[i-20:i,3].min());o,h,l,c=a[i,1:5];prev=a[i-1,4]
            for side,level in ((1,high),(-1,low)):
                if side*(c-level)>0:
                    e=fact('STRUCTURE_BREAK',side=side,level=level,level_source_cutoff=int(a[i-1,0]+HOUR));self.breaks[e['fact_id']]=(i,side,level)
                if (side==1 and h>level and max(o,c)<=level) or (side==-1 and l<level and min(o,c)>=level):
                    fact('STRUCTURE_REJECTION',side=-side,level=level,level_source_cutoff=int(a[i-1,0]+HOUR))
            for identity,(j,side,level) in list(self.breaks.items()):
                if i-j>4:fact('STRUCTURE_WINDOW_EXPIRED',source_id=identity,side=side,level=level);self.breaks.pop(identity);continue
                if i>j and side*(prev-level)>=0 and side*(c-level)<0:
                    e=fact('LEVEL_RECOVERY',side=-side,level=level,source_break_at=int(a[j,0]+HOUR),source_break_id=identity)
                    self.recoveries[e['fact_id']]=(i,-side,level);self.breaks.pop(identity)
            for identity,(j,side,level) in list(self.recoveries.items()):
                if i-j>4:fact('RECOVERY_WINDOW_EXPIRED',source_id=identity,side=side,level=level);self.recoveries.pop(identity);continue
                if i>j and side*(prev-level)>=0 and side*(c-level)<0:
                    fact('FAILED_REBOUND' if side==1 else 'FAILED_PULLBACK',side=-side,level=level,source_recovery_at=int(a[j,0]+HOUR),source_recovery_id=identity);self.recoveries.pop(identity)
        ao=values['ao'];aps=slopes['ao'];ps=slopes['pececillos'];watch=None
        if None not in (ao,aps,ps,values['plus_di'],values['minus_di']):
            bearish=values['minus_di']>values['plus_di']
            if ao<0 and aps>0 and ps>0:watch='WATCH_REBOUND';self.last_rebound=i
            elif self.last_rebound is not None and i-self.last_rebound<=4 and ao<0 and aps<0 and ps<0 and bearish:
                watch='WATCH_SHORT_REENTRY'
            elif ao<0 and bearish and (aps<0 or any(e['kind']=='STRUCTURE_BREAK' and e['side']==-1 for e in events)):watch='WATCH_SHORT'
        if watch!=self.watch:
            if watch:fact('OBSERVATIONAL_WATCH',label=watch,meaning='OBSERVATION_ONLY_NOT_AN_ENTRY')
            self.watch=watch
        return dict(values=values,slopes=slopes,events=events,watch=watch,
                    konkorde_comparison=dict(pececillos_slope=slopes['pececillos'],pececillos_above_red=bool(pece[i]>red[i]) if np.isfinite([pece[i],red[i]]).all() else None,
                                             red_crosses=[e for e in events if e['kind']=='PECECILLOS_RED_CROSS'],
                                             zero_crosses=[e for e in events if e['kind']=='ZERO_CROSS']),
                    structure_pending=dict(breaks={str(k):v for k,v in self.breaks.items()},recoveries={str(k):v for k,v in self.recoveries.items()}),
                    mtf=mtf(a[:i+1]) if contexts else {},external_context='UNVERIFIED_NARRATIVE_NOT_TRAINING_DATA')

    def warm(self,a,f):
        for i in range(len(a)):self.step(i,a,f,contexts=False)
