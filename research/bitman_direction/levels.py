"""Pure read-only reuse of Copilot's confirmed pivots; never calls its decisions."""
import numpy as np
from guardian_signals import confirmed_structure
from .spec import HOUR


def scale(frame,interval):
    """Same strict2L/2R pivots, available after confirmation, within220closed bars."""
    n=len(frame);out={k:np.full(n,np.nan) for k in ('support','resistance','support_pivot','resistance_pivot','support_known','resistance_known')}
    _,highs,lows=confirmed_structure(frame,2,2)
    for name,pivots in (('support',lows),('resistance',highs)):
        active=[];j=0
        for i in range(n):
            while j<len(pivots) and pivots[j][0]<=i:active.append(pivots[j]);j+=1
            # A rolling220-bar helper cannot confirm a pivot requiring left bars outside its input.
            active=[p for p in active if p[0]-4>=max(0,i-219)]
            ref=frame[i,4];eligible=[p for p in active if (p[1]<ref if name=='support' else p[1]>ref)]
            if not eligible:continue
            value=(max if name=='support' else min)(p[1] for p in eligible)
            confirmed=next(k for k,v in reversed(eligible) if v==value)
            out[name][i]=value;out[name+'_pivot'][i]=frame[confirmed-2,0]
            out[name+'_known'][i]=frame[confirmed,0]+interval
    return out


def previous_periods(hourly,times):
    out={k:np.full(len(times),np.nan) for k in ('previous_day_high','previous_day_low','previous_week_high','previous_week_low')}
    # Unix epochThursday; Monday anchor is epoch day-3.
    for prefix,width,offset in (('previous_day',24*HOUR,0),('previous_week',168*HOUR,-3*24*HOUR)):
        bucket=((hourly[:,0]-offset)//width).astype(np.int64)
        complete={}
        for key in np.unique(bucket):
            a=hourly[bucket==key];opening=key*width+offset
            if len(a)==width//HOUR and np.array_equal(a[:,0],opening+np.arange(len(a))*HOUR):complete[key]=(float(max(a[:,2])),float(min(a[:,3])))
        for i,t in enumerate(times):
            key=int((t-offset)//width)-1
            if key in complete:out[prefix+'_high'][i],out[prefix+'_low'][i]=complete[key]
    return out


def context(current,previous,price,high,low,atr):
    """Continuous distances; objective range-touch only, no tuned proximity threshold."""
    supports=[];resistances=[];details={};touch_s=[];touch_r=[]
    for tf,s in current.items():
        details[tf]={}
        for kind in ('support','resistance'):
            level=s.get(kind)
            if level is None or not np.isfinite(level):continue
            crossed=price<level if kind=='support' else price>level
            details[tf][kind]=dict(price=float(level),pivot_time=s.get(kind+'_pivot'),confirmed_time=s.get(kind+'_known'),
                distance_pct=float((level-price)/price),distance_atr=float(abs(level-price)/atr) if atr and np.isfinite(atr) else None,
                relationship='CROSSED_AWAITING_'+tf+'_CLOSE' if crossed else 'ORIGINAL_SIDE')
            if kind=='support' and level<price:supports.append((level,tf))
            if kind=='resistance' and level>price:resistances.append((level,tf))
        old=previous.get(tf,{})
        # Previous-known higher-TF level; do not use a pivot born on this same candle.
        if tf in ('4H','1D'):
            r=old.get('resistance');s=old.get('support')
            if r is not None and np.isfinite(r) and high>=r and price<=r:touch_r.append((float(r),tf))
            if s is not None and np.isfinite(s) and low<=s and price>=s:touch_s.append((float(s),tf))
    support=max(supports,default=None);resistance=min(resistances,default=None)
    return dict(scales=details,nearest_support=float(support[0]) if support else None,
        nearest_support_source=support[1] if support else None,
        nearest_resistance=float(resistance[0]) if resistance else None,nearest_resistance_source=resistance[1] if resistance else None,
        support_distance_pct=float((support[0]-price)/price) if support else None,
        resistance_distance_pct=float((resistance[0]-price)/price) if resistance else None,
        support_distance_atr=float((price-support[0])/atr) if support and atr and np.isfinite(atr) else None,
        resistance_distance_atr=float((resistance[0]-price)/atr) if resistance and atr and np.isfinite(atr) else None,
        state='AT_SUPPORT_AND_RESISTANCE' if touch_s and touch_r else 'AT_RESISTANCE' if touch_r else 'AT_SUPPORT' if touch_s else 'BETWEEN_LEVELS',
        opposing_up=bool(touch_r),opposing_down=bool(touch_s),tested_resistances=touch_r,tested_supports=touch_s,
        absent_level_not_open_space=True)
