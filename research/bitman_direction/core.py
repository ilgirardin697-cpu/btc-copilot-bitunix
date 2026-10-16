"""Causal hierarchical direction, not an entry/exit or executable strategy."""
import numpy as np
from research.bitman_real.indicators import calculate,lag,roll
from research.bitman_real.events import geometry
from research.bitman_real.market import aggregate,validate
from .spec import VERSION,TIMEFRAMES,HOUR
from . import levels


def align(times,values,interval,query,missing=np.nan):
    ids=np.searchsorted(np.asarray(times)+interval,query,side='right')-1
    out=np.full(len(query),missing,dtype=object if isinstance(missing,str) else float)
    ok=ids>=0;out[ok]=np.asarray(values)[ids[ok]];return out


def feature(frame):
    f=calculate(frame);ao=f['ao'];slope=f['ao_slope'];prior=lag(slope)
    f['ao_acceleration']=slope-prior
    f['ao_cross_up']=(ao>0)&(lag(ao)<=0);f['ao_cross_down']=(ao<0)&(lag(ao)>=0)
    up=((slope>0)&(prior>0))|f['ao_cross_up'];down=((slope<0)&(prior<0))|f['ao_cross_down']
    f['momentum']=np.where(up,'BULLISH_MOMENTUM',np.where(down,'BEARISH_MOMENTUM','MIXED'))
    f['ao_zero_motion']=np.where(abs(ao)<abs(lag(ao)),'TOWARD_ZERO',np.where(abs(ao)>abs(lag(ao)),'AWAY_FROM_ZERO','STABLE'))
    f['adx_acceleration']=f['adx_slope']-lag(f['adx_slope'])
    f['adx_turn_up']=(f['adx_slope']>0)&(lag(f['adx_slope'])<=0)
    f['adx_accelerating']=(f['adx_slope']>0)&(f['adx_acceleration']>0)
    f['adx_decelerating']=(f['adx_slope']>0)&(f['adx_acceleration']<0)
    f['bbwp_acceleration']=f['bbwp_slope']-lag(f['bbwp_slope'])
    f['bbwp_cross_up50']=(f['bbwp']>50)&(lag(f['bbwp'])<=50)
    f['bbwp_cross_down50']=(f['bbwp']<50)&(lag(f['bbwp'])>=50)
    f['bbwp_distance50']=f['bbwp']-50
    di=np.sign(f['di_plus']-f['di_minus']);f['di_direction']=np.where(di>0,'BULLISH',np.where(di<0,'BEARISH','NEUTRAL'))
    valid=np.isfinite(ao)&np.isfinite(di)
    f['ao_bias']=np.where(np.isfinite(ao),np.where(ao>0,'UP',np.where(ao<0,'DOWN','NEUTRAL')),'UNKNOWN')
    f['bias']=np.where(valid,np.where((ao>0)&(di>0),'UP',np.where((ao<0)&(di<0),'DOWN',
        np.where((ao==0)|(di==0),'NEUTRAL','TRANSITION'))),'UNKNOWN')
    _,inside,sep=geometry(f);f['inside']=inside;f['separation']=sep;f['distance_to_zero']=abs(f['ma'])
    f['separation_change']=np.where(inside&np.r_[False,inside[:-1]],sep-lag(sep),np.nan)
    valid_k=np.isfinite(f['mountain'])&np.isfinite(f['ma']);previous=np.r_[False,valid_k[:-1]]
    entry=valid_k&previous&inside&~np.r_[False,inside[:-1]]
    exit_=valid_k&previous&~inside&np.r_[False,inside[:-1]]
    reentry=np.zeros(len(frame),bool);last=-10000
    for i in range(len(frame)):
        if not valid_k[i]:last=-10000
        if exit_[i]:last=i
        reentry[i]=entry[i] and 1<=i-last<=3
    f['konkorde']=np.where(reentry,'KONKORDE_REENTRY',np.where(exit_,'KONKORDE_EXIT_CONTEXT',
        np.where(entry&(f['mountain']>0),'KONKORDE_BULLISH_ENTRY_CONTEXT',
        np.where(inside&(f['mountain']>0),'KONKORDE_BULLISH_INSIDE',
        np.where((f['mountain']<0)|(~inside&(f['mountain_slope']<0)),'KONKORDE_BEARISH_CONTEXT','KONKORDE_NEUTRAL')))))
    return f


def timing(f,ao_only=False):
    m=f['momentum'];di=f['di_direction']
    if m=='BULLISH_MOMENTUM' and (ao_only or di=='BULLISH'):return 'impulse_up'
    if m=='BEARISH_MOMENTUM' and (ao_only or di=='BEARISH'):return 'impulse_down'
    return 'transition' if m!='MIXED' else 'no_impulse'


def hierarchy(macro,swing,timer):
    lean=1 if timer=='impulse_up' else -1 if timer=='impulse_down' else 0
    if 'UNKNOWN' in (macro,swing):return 'UNCLEAR','REQUIRED_CONTEXT_UNAVAILABLE',0
    if macro==swing and macro in ('UP','DOWN'):
        side=1 if macro=='UP' else -1
        detail=macro+'_WITH_1H_PULLBACK' if lean==-side else macro+'_CONFIRMED' if lean==side else macro+'_NO_1H_IMPULSE'
        return macro,detail,side
    if macro in ('UP','DOWN') and swing in ('UP','DOWN'):
        if (lean==1 and swing=='UP') or (lean==-1 and swing=='DOWN'):
            return 'TRANSITION','POSSIBLE_BULLISH_TRANSITION' if lean==1 else 'POSSIBLE_BEARISH_TRANSITION',lean
        return 'CONFLICT','MACRO_SWING_CONFLICT',0
    if lean and ('TRANSITION' in (macro,swing)):
        return 'TRANSITION','EARLY_TRANSITION_UP' if lean==1 else 'EARLY_TRANSITION_DOWN',lean
    return 'UNCLEAR','NO_CONFIRMED_HIERARCHY',0


def decide(components,structure=None,ml=None,ao_only=False):
    key='ao_bias' if ao_only else 'bias';d,h,q=(components[t] for t in ('1D','4H','1H'))
    timer=timing(q,ao_only);state,detail,lean=hierarchy(d[key],h[key],timer)
    mtf_aligned=d[key]==h[key] and d[key] in ('UP','DOWN')
    rising=lambda f: f['adx_slope'] is not None and f['adx_slope']>0
    expanding=lambda f: f['bbwp_slope'] is not None and f['bbwp_slope']>0
    strong=mtf_aligned and rising(d) and rising(h) and expanding(d) and expanding(h)
    building=bool(lean and (rising(h) and expanding(h) or timer==('impulse_up' if lean==1 else 'impulse_down') and q['adx_turn_up'] and expanding(q)))
    strength='STRONG' if strong else 'BUILDING' if building else 'WEAK'
    ml=ml or {};confirmed=ml.get('4H',{}).get('color','UNKNOWN')
    if not ao_only and state in ('UP','DOWN') and structure and structure['opposing_up' if state=='UP' else 'opposing_down']:
        detail='CONFIRMED_STRUCTURAL_TEST_OPPOSES_'+state;state='CONFLICT'
    if not ao_only and state in ('UP','DOWN') and confirmed==('RED' if state=='UP' else 'GREEN'):
        detail='CONFIRMED_MLRSI_OPPOSITION';state='CONFLICT'
    grade='A' if state in ('UP','DOWN') and strong and confirmed==('GREEN' if state=='UP' else 'RED') else 'B' if state in ('UP','DOWN') else 'C'
    return dict(state=state,detail=detail,direction=lean,strength=strength,evidence_grade=grade,
        macro_bias=d[key],swing_bias=h[key],timing_state='pullback' if detail.endswith('PULLBACK') else timer,
        pullback_direction=('DOWN' if lean==1 else 'UP') if detail.endswith('PULLBACK') else None,
        mlrsi_confirmation='UNAVAILABLE' if confirmed=='UNKNOWN' else 'NEUTRAL' if confirmed=='NEUTRAL' else 'SUPPORTING' if (confirmed=='GREEN')==(lean==1) else 'OPPOSING')


def prepare(hourly,now):
    hourly=validate(hourly);hourly=hourly[hourly[:,0]+HOUR<=now]
    if len(hourly)<48:raise ValueError('DIRECTION_HISTORY_INSUFFICIENT')
    times=hourly[:,0]+HOUR;frames={};aligned={};level_arrays={}
    for tf,interval in TIMEFRAMES.items():
        frame=aggregate(hourly,interval,now)
        if not len(frame):raise ValueError('DIRECTION_HISTORY_INSUFFICIENT')
        f=feature(frame);frames[tf]=dict(frame=frame,features=f,closes=frame[:,0]+interval)
        aligned[tf]={k:align(frame[:,0],v,interval,times,'UNKNOWN' if np.asarray(v).dtype.kind in 'UO' else np.nan) for k,v in f.items()}
        level_arrays[tf]={k:align(frame[:,0],v,interval,times) for k,v in levels.scale(frame,interval).items()}
    periods=levels.previous_periods(hourly,times)
    h4=frames['4H']['frame'];sma=roll(h4[:,4],200)
    regime=align(h4[:,0],np.where(np.isfinite(sma),np.sign(h4[:,4]-sma),np.nan),4*HOUR,times)
    return dict(bars=hourly,times=times,frames=frames,aligned=aligned,levels=level_arrays,periods=periods,regime=regime)


def component_at(data,tf,i):
    out={}
    for k,v in data['aligned'][tf].items():
        value=v[i]
        out[k]=str(value) if isinstance(value,str) else float(value) if np.isfinite(value) else None
    out['last_closed_at']=int(out['time']+TIMEFRAMES[tf]) if out.get('time') is not None else None
    return out


def snapshot(data,i,ml=None):
    bars=data['bars'];price=float(bars[i,4]);atr=data['aligned']['1H']['atr'][i]
    current={tf:{k:float(a[i]) if np.isfinite(a[i]) else None for k,a in v.items()} for tf,v in data['levels'].items()}
    previous={tf:{k:float(a[i-1]) if i and np.isfinite(a[i-1]) else None for k,a in v.items()} for tf,v in data['levels'].items()}
    for tf in ('previous_day','previous_week'):
        current[tf]=dict(support=data['periods'][tf+'_low'][i],resistance=data['periods'][tf+'_high'][i])
    structure=levels.context(current,previous,price,float(bars[i,2]),float(bars[i,3]),float(atr))
    components={tf:component_at(data,tf,i) for tf in TIMEFRAMES}
    decision=decide(components,structure,ml)
    return dict(version=VERSION,symbol='BTCUSDT',venue='BINANCE_USDM_PERPETUAL',timestamp=int(data['times'][i]),
        reference_price=price,components=components,structure=structure,confirmed_mlrsi=ml or {},**decision,
        shadow_only=True,trade_authority=False,not_trade_signal=True)


def series(data,with_structure=True,ao_only=False):
    """Closed-hour public history. Missing confirmed ML remains UNKNOWN, never reconstructed."""
    n=len(data['times']);keys=('bias','ao_bias','momentum','di_direction','adx_slope','bbwp_slope','adx_turn_up')
    output={k:[] for k in ('state','detail','direction','strength','evidence_grade')}
    resist=np.zeros(n,bool);support=resist.copy();bars=data['bars']
    for tf in ('4H','1D'):
        r=lag(data['levels'][tf]['resistance']);s=lag(data['levels'][tf]['support'])
        resist|=np.isfinite(r)&(bars[:,2]>=r)&(bars[:,4]<=r)
        support|=np.isfinite(s)&(bars[:,3]<=s)&(bars[:,4]>=s)
    for i in range(n):
        parts={tf:{k:a[k][i] for k in keys} for tf,a in data['aligned'].items()}
        context=dict(opposing_up=bool(resist[i]),opposing_down=bool(support[i])) if with_structure else None
        result=decide(parts,context,ao_only=ao_only)
        for k in output:output[k].append(result[k])
    return {k:np.asarray(v) for k,v in output.items()}
