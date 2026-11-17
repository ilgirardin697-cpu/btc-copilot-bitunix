"""Closed H1 public source profile; no signals, accounts, services or trading.

TSA translation: © Zeiierman, CC BY-NC-SA4.0; noncommercial offline research.
Koncorde/BBWP public source ports: original MPL2.0 notices in sources/.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
from research.confluence_1h.indicators import calculate as audited,roll,smooth,divide,bbwp,lag
from .backquant import OriginalMLRSI

HERE=Path(__file__).resolve().parent
H=3600000


def settings():
    value=json.loads((HERE/'profile.json').read_text('utf-8'))
    expected={'bbwp':dict(i_priceSrc='close',i_basisType='SMA',i_basisLen=13,i_lookback=252,i_maType='SMA',i_maLen=5),
              'mlrsi':dict(src='low',rsiLength=27,smooth=True,maType='ALMA',smoothP=4,sig=1,maxData=3000,maxIter=1000),
              'adx':dict(adxlen=14,dilen=14),'tsa':dict(max_length=119,accel_multiplier=2.8,lookback_period=50,collen=100,timer='From start'),
              'koncorde':dict(tprice='ohlc4',srcMfi='hlc3',len_mfi_rsi=14,length_bb=25,mult_bb=2,length_ma01=15,type_ma01='EMA',m_pvi_nvi=15,longitudPVI=90,longitudNVI=90)}
    if value['profile']!='TRADINGONE_V2' or value['venue']!='BINANCE_SPOT':raise ValueError('PROFILE_CHANGED')
    for name,fields in expected.items():
        if any(value['active_inputs'][name].get(k)!=v for k,v in fields.items()):raise ValueError('ACTIVE_PROFILE_CHANGED')
    for name,s in json.loads((HERE/'source_manifest.json').read_text('utf-8')).items():
        source=(HERE/'sources'/(name+'.pine')).read_bytes().replace(b'\r\n',b'\n')
        if hashlib.sha256(source).hexdigest()!=s['normalized_sha256']:raise ValueError('SOURCE_CHANGED')
    return value


def fixnan(x):
    out=np.asarray(x,float).copy();last=np.nan
    for i,v in enumerate(out):
        if np.isfinite(v):last=v
        else:out[i]=last
    return out


def adx14(bars):
    t,o,h,l,c,v=np.asarray(bars,float).T
    up=h-lag(h);down=lag(l)-l
    plus=np.where(np.isnan(up),np.nan,np.where((up>down)&(up>0),up,0))
    minus=np.where(np.isnan(down),np.nan,np.where((down>up)&(down>0),down,0))
    tr=np.maximum(h-l,np.maximum(abs(h-lag(c)),abs(l-lag(c))))
    den=smooth(tr,14,'rma')
    p=fixnan(100*divide(smooth(plus,14,'rma'),den))
    m=fixnan(100*divide(smooth(minus,14,'rma'),den))
    total=p+m;dx=divide(abs(p-m),np.where(total==0,1,total))
    return 100*smooth(dx,14,'rma'),p,m


def wma(x,n):
    x=np.asarray(x,float);out=np.full(len(x),np.nan)
    if len(x)>=n:
        windows=np.lib.stride_tricks.sliding_window_view(x,n)
        out[n-1:]=(windows*np.arange(1,n+1)).sum(axis=1)/(n*(n+1)/2)
    return out


def rgba(hexadecimal):
    h=hexadecimal.lstrip('#')
    if len(h)==6:h+='FF'
    return tuple(int(h[j:j+2],16) for j in (0,2,4,6))


def gradient(value,lo,hi,c1,c2):
    if not math.isfinite(value):return None
    frac=0 if hi==lo else max(0,min(1,(value-lo)/(hi-lo)))
    return '#'+''.join(f'{int(math.floor(a+(b-a)*frac+.5)):02X}' for a,b in zip(rgba(c1),rgba(c2)))


def bbwp_color(value,cfg):
    if not np.isfinite(value):return None
    if cfg['i_clrTypStr']=='Solid':return cfg['i_c_solid']
    points=[(0,cfg['i_c_sp_lo']),(25,cfg['i_c_sp_mlo']),(50,cfg['i_c_sp_mid']),
            (75,cfg['i_c_sp_mhi']),(100,cfg['i_c_sp_hi'])]
    q=math.floor(value+.5)  # Pine nonnegative .5 up, not Python bankers' round
    for (lo,c1),(hi,c2) in zip(points,points[1:]):
        if q<=hi:return gradient(q,lo,hi,c1,c2)
    return points[-1][1]


def tsa(bars,cfg):
    t,o,h,l,c,v=np.asarray(bars,float).T;n=len(c)
    greatest=roll(abs(c),200,'max',True);norm=(c+greatest)/(2*greatest)
    dynlen=5+norm*(cfg['max_length']-5)
    delta=abs(c-np.r_[0,c[:-1]])
    delta_max=roll(delta,200,'max',True);delta_max=np.where(delta_max==0,1,delta_max)
    alpha=np.minimum(1,2/(dynlen+1)*(1+delta/delta_max*cfg['accel_multiplier']))
    trend=np.full(n,np.nan)
    for i in range(n):trend[i]=c[i] if i==0 else alpha[i]*c[i]+(1-alpha[i])*trend[i-1]
    rclose=smooth(c,10,'rma');ropen=smooth(o,10,'rma');speed=np.full(n,np.nan)
    x1=None;prior_speed=0.;bulls=[];bears=[];bullavg=[];bearavg=[];bullmax=[];bearmax=[];direction=[]
    for i in range(n):
        enabled=t[i]>cfg['start'] or cfg['timer']=='From start'
        if x1 is None and enabled:x1=i
        s=prior_speed
        if enabled and i and c[i]>trend[i] and c[i-1]<=trend[i]:
            length=i-x1
            if length<=0:raise ValueError('SOURCE_DYNAMIC_LENGTH_ZERO')
            window=np.r_[speed[max(0,i-length+1):i],s]
            finite=window[np.isfinite(window)];bears.insert(0,float(finite.min()) if len(finite) else np.nan)
            x1=i;s=rclose[i]-ropen[i]
        if enabled and i and c[i]<trend[i] and c[i-1]>=trend[i]:
            length=i-x1
            if length<=0:raise ValueError('SOURCE_DYNAMIC_LENGTH_ZERO')
            window=np.r_[speed[max(0,i-length+1):i],s]
            finite=window[np.isfinite(window)];bulls.insert(0,float(finite.max()) if len(finite) else np.nan)
            x1=i;s=rclose[i]-ropen[i]
        s=s+rclose[i]-ropen[i]  # source adds AGAIN after a phase reset; do not repair
        speed[i]=prior_speed=s
        b=np.array(bulls[:cfg['lookback_period']]);d=np.array(bears[:cfg['lookback_period']])
        b=b[np.isfinite(b)];d=d[np.isfinite(d)]
        bullavg.append(float(b.mean()) if len(b) else np.nan);bearavg.append(float(d.mean()) if len(d) else np.nan)
        bullmax.append(float(b.max()) if len(b) else np.nan);bearmax.append(float(d.min()) if len(d) else np.nan)
        direction.append(1 if i and (2*c[i]+c[i-1])/3>trend[i] else -1)
    lo=roll(speed,cfg['collen'],'min',True);hi=roll(speed,cfg['collen'],'max',True)
    # ta.lowest/highest ignore NA, including partially populated initial windows.
    for i in range(n):
        z=speed[max(0,i-cfg['collen']+1):i+1];z=z[np.isfinite(z)]
        lo[i]=z.min() if len(z) else np.nan;hi[i]=z.max() if len(z) else np.nan
    normalized=divide(speed-lo,hi-lo)
    speed_colors=[]
    for value,normal in zip(speed,normalized):
        speed_colors.append(gradient(normal,0,.5,cfg['dn_hist_col'],cfg['dn_hist_col_']) if value<0 else gradient(normal,.5,1,cfg['up_hist_col'],cfg['up_hist_col_']))
    return dict(tsa_trend=trend,tsa_alpha=alpha,tsa_length=dynlen,tsa_raw_speed=speed,
                tsa_speed=wma(2*wma(speed,2)-wma(speed,5),2),tsa_bull_avg=np.array(bullavg),
                tsa_bear_avg=np.array(bearavg),tsa_bull_max=np.array(bullmax),tsa_bear_max=np.array(bearmax),
                tsa_trend_side=np.array(direction),tsa_candle_color=np.array(speed_colors,object))


def calculate(bars,last_bar_index=None):
    a=np.asarray(bars,float)
    if a.ndim!=2 or a.shape[1]!=6 or not np.isfinite(a).all():raise ValueError('OHLCV_REQUIRED')
    if len(a)>1 and np.any(np.diff(a[:,0])!=H):raise ValueError('CLOSED_H1_GAP')
    if np.any(a[:,3]<=0) or np.any(a[:,3]>np.minimum(a[:,1],a[:,4])) or np.any(a[:,2]<np.maximum(a[:,1],a[:,4])) or np.any(a[:,5]<0):raise ValueError('OHLCV_RANGE')
    cfg=settings()['active_inputs'];base=audited(a)
    adx,pdi,mdi=adx14(a)
    width=2*roll(a[:,4],13,'std')/roll(a[:,4],13)
    rank=bbwp(width,252,13)
    ml=OriginalMLRSI(len(a)-1 if last_bar_index is None else last_bar_index)
    records=[ml.push(low) for low in a[:,3]]
    f=dict(ao=base['ao'],adx=adx,plus_di=pdi,minus_di=mdi,atr=base['atr'],
           pececillos=base['minnows'],tendencia=base['kon_trend'],tiburones=base['sharks'],roja=base['kon_signal'],
           bbwp=rank,bbwp_signal=roll(rank,5),bbw=width)
    for k in ('raw','value','lower','middle','upper','samples','iterations','cluster1','cluster2','cluster3'):
        f['ml_'+k]=np.array([np.nan if r[k] is None else r[k] for r in records],float)
    f['ml_color']=np.array([r['color'] for r in records]);f['ml_valid']=np.array([r['valid'] for r in records])
    for k in ('ao','adx','pececillos','tendencia','tiburones','roja','bbwp','bbwp_signal','ml_value'):
        d=f[k]-lag(f[k]);prev=lag(d)
        f[k+'_slope']=d;f[k+'_acceleration']=d-prev
        f[k+'_turn']=np.where((d>0)&(prev<=0),1,np.where((d<0)&(prev>=0),-1,0))
    f['ao_color']=np.where(np.isfinite(f['ao_slope']),np.where(f['ao_slope']>0,'GREEN','RED'),'UNKNOWN')
    f['bbwp_color']=np.array([bbwp_color(v,cfg['bbwp']) for v in rank],object)
    f['pececillos_cross_red']=np.where((f['pececillos']>f['roja'])&(lag(f['pececillos'])<=lag(f['roja'])),1,
                                      np.where((f['pececillos']<f['roja'])&(lag(f['pececillos'])>=lag(f['roja'])),-1,0))
    f.update(tsa(a,cfg['tsa']))
    for k in ('tsa_trend','tsa_raw_speed','tsa_speed'):
        f[k+'_slope']=f[k]-lag(f[k]);f[k+'_acceleration']=f[k+'_slope']-lag(f[k+'_slope'])
    return f,ml


def tsa_table(f,index=-1):
    """Original last-bar wave ratios; no profitability or direction authority."""
    get=lambda k:float(f[k][index])
    ba,da,bm,dm=(get(k) for k in ('tsa_bull_avg','tsa_bear_avg','tsa_bull_max','tsa_bear_max'))
    wave=get('tsa_raw_speed')
    ratio=lambda a,b:a/b if np.isfinite([a,b]).all() and b!=0 else np.nan
    return dict(bull_average=ba,bear_average=da,bull_maximum=bm,bear_minimum=dm,
                wave_ratio_average=ratio(ba,abs(da)),wave_ratio_maximum=ratio(bm,abs(dm)),
                dominance_average=ba-abs(da),dominance_maximum=bm-abs(dm),current_raw_wave=wave,
                current_ratio_average=ratio(wave,ba if wave>0 else abs(da)),
                current_ratio_maximum=ratio(wave,bm if wave>0 else abs(dm)),
                current_wave_color='GREEN' if wave>0 else 'RED')
