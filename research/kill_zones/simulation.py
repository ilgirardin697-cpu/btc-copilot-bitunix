"""Offline fills and accounting only. No API/client, orders or authority."""
import numpy as np
from .data import M5,HOUR,stamp
FEE=.0006
SLIPPAGE=.0005
STRESS_SLIPPAGE=.001
SPLITS={'DEVELOPMENT':(stamp('2024-01-01T00:00:00Z'),stamp('2025-01-01T00:00:00Z')),
        'VALIDATION':(stamp('2025-01-01T00:00:00Z'),stamp('2026-01-01T00:00:00Z')),
        'EVALUATION':(stamp('2026-01-01T00:00:00Z'),stamp('2026-10-01T00:00:00Z'))}
def split_at(t):
    return next((k for k,(lo,hi) in SPLITS.items() if lo+48*HOUR<=t<hi-48*HOUR),None)
def funding_cash(base,funding,side,entry,exit_at):
    rows=funding[(funding[:,0]>=entry)&(funding[:,0]<=exit_at)]
    total=0.;detail=[]
    for t,rate in rows:
        i=int(np.searchsorted(base[:,0]+M5,t,side='right'))-1
        if i<0 or not 0<=t-(base[i,0]+M5)<M5:raise ValueError('FUNDING_PRICE_PROXY_MISSING')
        cash=-side*rate*base[i,4]
        if t==entry:cash=min(0.,cash)
        total+=cash;detail.append((int(t),float(cash)))
    return total,detail
def fill_bar(side,stop,target,bar):
    o,h,l=bar[1:4]
    stop_gap=side*(o-stop)<=0
    target_gap=side*(o-target)>=0
    hit_stop=l<=stop if side==1 else h>=stop
    hit_target=h>=target if side==1 else l<=target
    if stop_gap:return float(o),'STOP_GAP',False,True
    if target_gap:return target,'TARGET_GAP',False,True
    if hit_stop:return stop,'STOP',bool(hit_target),False
    if hit_target:return target,'TARGET',False,False
    return None
def simulate(signal,base,funding,*,slip=SLIPPAGE,fee=FEE):
    t=signal['entry_at'];s=signal['side'];stop=signal['stop'];target=signal['target']
    j=int(np.searchsorted(base[:,0],t))
    if j>=len(base) or base[j,0]!=t:return dict(rejection='ENTRY_MISSING')
    entry=float(base[j,1])*(1+s*slip)
    if min(stop,target)<=0 or s*(entry-stop)<=0:return dict(rejection='ENTRY_AT_OR_BEYOND_STOP')
    if s*(target-entry)<=0:return dict(rejection='ENTRY_AT_OR_BEYOND_TARGET')
    until=t+24*HOUR;mae=mfe=0.;path=[];exit_at=None;ambiguous=False
    for k in range(j,len(base)):
        b=base[k]
        expected=t+(k-j)*M5
        if b[0]!=expected:return dict(rejection='CENSORED_DATA_GAP',censored_until=until)
        if b[0]>=until:
            raw=float(b[1]);reason='TIME';exit_at=until;break
        outcome=fill_bar(s,stop,target,b)
        if outcome:
            raw,reason,ambiguous,gap=outcome
            exit_at=int(b[0] if gap else b[0]+M5);break
        favorable=s*((b[2] if s==1 else b[3])-entry)
        adverse=s*((b[3] if s==1 else b[2])-entry)
        mfe=max(mfe,favorable);mae=min(mae,adverse)
        path.append((int(b[0]+M5),float(b[4])))
    if exit_at is None:return dict(rejection='CENSORED_HISTORY_END',censored_until=until)
    exit_price=raw*(1-s*slip)
    favorable=s*(exit_price-entry);mfe=max(mfe,favorable);mae=min(mae,favorable)
    fund,events=funding_cash(base,funding,s,t,exit_at)
    gross=s*(exit_price-entry);fees=fee*(entry+exit_price);net=gross-fees+fund
    risk=abs(entry-stop)
    marks=[];cursor=0;accrued=0.
    for when,price in path:
        while cursor<len(events) and events[cursor][0]<=when:
            accrued+=events[cursor][1];cursor+=1
        marks.append((when,s*(price-entry)-fee*entry+accrued))
    marks.append((exit_at,net))
    return dict(entry_price=entry,exit_price=exit_price,exit_at=exit_at,reason=reason,ambiguous=ambiguous,
        gross_unit=gross,fees_unit=fees,funding_unit=fund,net_unit=net,risk_unit=risk,
        slippage_unit=abs(entry-float(base[j,1]))+abs(exit_price-raw),
        net_r=net/risk,gross_r=gross/risk,net_bps=net/entry*10000,mae_r=-mae/risk,mfe_r=mfe/risk,
        duration_hours=(exit_at-t)/HOUR,target_hit=reason.startswith('TARGET'),
        funding_events=len(events),mtm_unit=marks)
def replay(signals,base,funding,*,slip=SLIPPAGE,features=None,gate_name='ALL'):
    from .models import gate
    trades=[];rejections=[];state={}
    for signal in signals:
        split=split_at(signal['entry_at'])
        if split is None:continue
        key=(signal['model'],split)
        st=state.setdefault(key,dict(equity=10000.,peak=10000.,drawdown=0.,until=0,curve=[(SPLITS[split][0],10000.)]))
        if signal['entry_at']<st['until']:
            rejections.append(dict(model=key[0],split=split,date=signal['date'],reason='OVERLAPPING_POSITION'));continue
        if features is not None and not gate(features,signal['signal_index'],signal['side'],gate_name):
            rejections.append(dict(model=key[0],split=split,date=signal['date'],reason='FILTER_'+gate_name));continue
        result=simulate(signal,base,funding,slip=slip)
        if 'rejection' in result:
            rejections.append(dict(model=key[0],split=split,date=signal['date'],reason=result['rejection']))
            st['until']=result.get('censored_until',0);continue
        planned_exit=signal['stop']*(1-signal['side']*slip)
        planned_loss=abs(result['entry_price']-planned_exit)+FEE*(result['entry_price']+planned_exit)
        qty=min(.01*st['equity']/planned_loss,st['equity']/result['entry_price'])
        initial=st['equity'];curve=result.pop('mtm_unit')
        for when,unit in [(signal['entry_at'],-FEE*result['entry_price'])]+curve:
            equity=initial+qty*unit
            st['peak']=max(st['peak'],equity)
            st['drawdown']=max(st['drawdown'],1-equity/st['peak'])
            st['curve'].append((when,equity))
        st['equity']=initial+qty*result['net_unit'];st['until']=result['exit_at']
        trades.append(dict(signal,**result,split=split,qty=qty,pnl=qty*result['net_unit'],
                           equity_after=st['equity'],gate=gate_name))
    summaries={m+'|'+sp:dict(equity=s['equity'],drawdown=s['drawdown'],curve=s['curve']) for (m,sp),s in state.items()}
    return trades,rejections,summaries
