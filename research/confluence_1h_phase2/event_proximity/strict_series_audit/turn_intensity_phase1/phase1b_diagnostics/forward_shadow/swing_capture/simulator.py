"""One-position offline partial/BE/trailing ledger. No exchange client."""
from dataclasses import dataclass,field
import numpy as np

H=3600000;FEE=.001;SLIP=.0005
@dataclass(frozen=True)
class Config:
    tp:float
    stop:float
    risk:float
    def __post_init__(self):
        if self.tp not in (.005,.01,.02) or self.stop not in (1.5,2.5) or self.risk not in (.005,.01):raise ValueError('ONLY_FROZEN_SCENARIOS')
    @property
    def key(self):return f'TP{self.tp:g}_SL{self.stop:g}_RISK{self.risk:g}'

class Minutes:
    def __init__(self,a,hourly):
        self.a=np.asarray(a,float);self.first=int(a[0,0]);self.good={};self.calls=0
        if np.any(np.diff(a[:,0])!=60000) or self.first%H:raise ValueError('MINUTE_GRID')
        for row in hourly:
            start=(int(row[0])-self.first)//60000
            if start<0 or start+60>len(a):continue
            b=a[start:start+60]
            if not np.array_equal(b[:,0],row[0]+np.arange(60)*60000):continue
            got=np.array([b[0,1],b[:,2].max(),b[:,3].min(),b[-1,4]])
            if np.array_equal(got,row[1:5]) and np.isclose(b[:,5].sum(),row[5],atol=1e-6,rtol=1e-12):self.good[int(row[0])]=start
    def get(self,t):
        self.calls+=1;start=self.good.get(int(t));return None if start is None else self.a[start:start+60]

@dataclass
class Position:
    signal:dict
    entry_i:int
    entry:float
    qty:float
    remaining:float
    stop:float
    target:float
    risk_usdt:float
    equity_before:float
    side:int
    entry_fee:float
    peak:float
    trough:float
    gross:float=0.
    exit_fees:float=0.
    funding_low:float=0.
    funding_high:float=0.
    funding_per_btc:float=0.
    funding_uncertain:int=0
    tp1:bool=False
    be:bool=False
    trailing:bool=False
    stop_kind:str='INITIAL_STOP'
    exit_kind:str=''
    exit_i:int=-1
    ambiguous_h1:int=0
    h1_both:int=0
    ambiguous_m1:int=0
    resolved_m1:int=0
    gaps:int=0
    mfe:float=0.
    mae:float=0.
    fills:list=field(default_factory=list)
    stop_updates:list=field(default_factory=list)

def be_level(entry,side,funding_per_btc):
    fill=(entry*(1+FEE)+funding_per_btc)/(1-FEE) if side==1 else (entry*(1-FEE)-funding_per_btc)/(1+FEE)
    return fill/(1-side*SLIP)

def run(a,funding,atr,signals,config,minutes=None,marks=None,details=True):
    a=np.asarray(a,float);funding=np.asarray(funding,float);atr=np.asarray(atr,float)
    if marks is None:marks=a
    mark_map={int(r[0]):r for r in marks};by_i={};collision=set();multiplicity={}
    for s in signals:
        j=int(s['i'])+1
        multiplicity[j]=multiplicity.get(j,0)+1
        if j in by_i:collision.add(j)
        else:by_i[j]=s
    by_fund={}
    for row in funding:
        if int(row[0])%H:raise ValueError('NON_H1_SETTLEMENT_REQUIRES_NEW_REVIEW')
        by_fund.setdefault(int(row[0]),[]).append(row)
    cash=10000.;position=None;trades=[];opportunities=[];curve=[];equity_peak=10000.;maxdd=0.;last_eq=10000.;exposure=0
    counts=dict(raw_signals=len(signals),taken=0,skipped_position=0,leverage_required=0,collision=0,invalid_risk=0,insolvent=0,no_entry_data=sum(v for j,v in multiplicity.items() if j>=len(a)))
    first=min(by_i,default=len(a))
    def fill(p,amount,raw,kind,j,t,span):
        nonlocal cash
        execution=raw*(1-p.side*SLIP);gross=p.side*amount*(execution-p.entry);fee=amount*execution*FEE
        p.gross+=gross;p.exit_fees+=fee;cash+=gross-fee;p.remaining-=amount
        if p.remaining<p.qty*1e-10:p.remaining=0.;p.exit_kind=kind;p.exit_i=j
        if details:p.fills.append(dict(kind=kind,qty=amount,reference=raw,fill=execution,fee=fee,window_start=int(t),window_end=int(t+span),time_is_interval=span>0))
    def excursions(p,row):
        p.peak=max(p.peak,float(row[2]));p.trough=min(p.trough,float(row[3]))
        p.mfe=max(p.mfe,max(0.,(row[2]-p.entry)/p.entry if p.side==1 else (p.entry-row[3])/p.entry))
        p.mae=max(p.mae,max(0.,(p.entry-row[3])/p.entry if p.side==1 else (row[2]-p.entry)/p.entry))
    def step_bar(p,row,j,span):
        op,hi,lo=row[1:4];stop=p.side*(op-p.stop)<=0
        hitstop=(lo<=p.stop if p.side==1 else hi>=p.stop)
        target=not p.tp1 and (hi>=p.target if p.side==1 else lo<=p.target)
        excursions(p,row)
        if stop:
            p.gaps+=int(p.side*(op-p.stop)<0);fill(p,p.remaining,float(op),p.stop_kind,j,row[0],0);return
        if hitstop:
            if target:
                if span==60000:p.ambiguous_m1+=1
                else:p.ambiguous_h1+=1
            fill(p,p.remaining,p.stop,p.stop_kind,j,row[0],span);return
        if target:
            fill(p,min(p.qty*.5,p.remaining),p.target,'TP1',j,row[0],span);p.tp1=True
    for j in range(first,len(a)):
        row=a[j];t=int(row[0]);had_position=position is not None;s=by_i.get(j);decision=None
        if s is not None:
            if j in collision:decision='CONTROL_COLLISION';counts['collision']+=multiplicity[j]
            elif had_position:decision='POSITION_OPEN';counts['skipped_position']+=1
            elif cash<=0:decision='INSOLVENT';counts['insolvent']+=1
            else:
                side=int(s['side']);entry=float(row[1]*(1+side*SLIP));distance=config.stop*atr[int(s['i'])];stop=entry-side*distance
                stopfill=stop*(1-side*SLIP);unit=side*(entry-stopfill)+FEE*(entry+stopfill)
                if not np.isfinite([entry,stop,unit]).all() or min(entry,stop,unit)<=0:
                    decision='INVALID_RISK';counts['invalid_risk']+=1
                else:
                    risk=cash*config.risk;qty=risk/unit
                    if qty*entry*(1+FEE)>cash:
                        decision='LEVERAGE_REQUIRED';counts['leverage_required']+=1
                    else:
                        before=cash;fee=qty*entry*FEE;cash-=fee
                        position=Position(s,j,entry,qty,qty,stop,entry*(1+side*config.tp),risk,before,side,fee,entry,entry)
                        counts['taken']+=1;decision='ENTERED'
            if details:opportunities.append(dict(signal_id=s.get('signal_id','CONTROL:'+str(s['i'])),signal_i=s['i'],entry_i=j,side=s['side'],decision=decision))
        if position is not None:
            p=position;exposure+=1;owned=p.remaining;new=j==p.entry_i;gap=p.side*(row[1]-p.stop)<=0
            pending=[]
            for frow in by_fund.get(t,[]):
                _,rate,mark,_,low,high=frow
                prices=[mark] if np.isfinite(mark) else [low,high]
                if not np.isfinite(prices).all():raise ValueError('UNKNOWN_FUNDING_BOUNDS')
                values=[p.side*rate*x for x in prices]
                if new or gap:values.append(0.)
                pending.append((min(values),max(values),not np.isfinite(mark) or new or gap))
            hitstop=(row[3]<=p.stop if p.side==1 else row[2]>=p.stop)
            hittarget=not p.tp1 and (row[2]>=p.target if p.side==1 else row[3]<=p.target)
            minute_rows=minutes.get(t) if minutes is not None and (hitstop or hittarget) and not gap else None
            p.h1_both+=int(hitstop and hittarget and not gap)
            if minute_rows is not None:
                old_ambiguous=p.ambiguous_m1
                for m in minute_rows:
                    step_bar(p,m,j,60000)
                    if p.remaining==0:break
                if hitstop and hittarget and p.ambiguous_m1==old_ambiguous:p.resolved_m1+=1
            else:step_bar(p,row,j,H)
            # Data from this completed H1, including missing mark bounds, affect
            # cash/BE only now. No intrahour decision uses a future range.
            for low,high,uncertain in pending:
                p.funding_low+=owned*low;p.funding_high+=owned*high;p.funding_per_btc+=high;p.funding_uncertain+=int(uncertain);cash-=owned*high
            if p.remaining and j==len(a)-1:fill(p,p.remaining,float(row[4]),'END_OF_DATA',j,t+H,0)
            if not p.remaining:
                net=p.gross-p.entry_fee-p.exit_fees-p.funding_high
                trade=dict(signal_id=p.signal.get('signal_id','CONTROL:'+str(p.signal['i'])),signal_i=p.signal['i'],entry_i=p.entry_i,exit_i=p.exit_i,
                    side=p.side,entry_at=int(a[p.entry_i,0]),exit_hour=int(a[p.exit_i,0]),entry_fill=p.entry,qty=p.qty,equity_before=p.equity_before,
                    risk_usdt=p.risk_usdt,net=net,net_upper=net+p.funding_high-p.funding_low,net_R=net/p.risk_usdt,
                    gross=p.gross,entry_fee=p.entry_fee,exit_fees=p.exit_fees,funding_low=p.funding_low,funding_high=p.funding_high,funding_uncertain=p.funding_uncertain,
                    tp1=p.tp1,be_armed=p.be,trailing_armed=p.trailing,exit_kind=p.exit_kind,ambiguous_h1=p.ambiguous_h1,ambiguous_m1=p.ambiguous_m1,h1_both=p.h1_both,resolved_m1=p.resolved_m1,gaps=p.gaps,
                    mfe_pct=p.mfe*100,mae_pct=p.mae*100,excursion_is_bar_bound=True,duration_hours=p.exit_i-p.entry_i+1,
                    regime4h=p.signal.get('regime4h'),adx_phase=p.signal.get('adx_phase'),bbwp_phase=p.signal.get('bbwp_phase'))
                if details:trade['fills']=p.fills;trade['stop_updates']=p.stop_updates
                trades.append(trade);position=None
            elif p.tp1:
                old_stop=p.stop
                p.be=True;p.trailing=True;be=be_level(p.entry,p.side,p.funding_per_btc)
                trail=p.peak-1.5*atr[j] if p.side==1 else p.trough+1.5*atr[j]
                if p.side==1:
                    candidate=max(p.stop,be,trail)
                    if candidate>p.stop:p.stop=candidate;p.stop_kind='TRAIL_STOP' if trail>be else 'BE_STOP'
                else:
                    candidate=min(p.stop,be,trail)
                    if candidate<p.stop:p.stop=candidate;p.stop_kind='TRAIL_STOP' if trail<be else 'BE_STOP'
                if details and p.stop!=old_stop:p.stop_updates.append(dict(effective_at=t+H,level=float(p.stop),kind=p.stop_kind,atr=float(atr[j]),source_H1_close=t+H))
        mark=mark_map.get(t)
        if mark is None:raise ValueError('EQUITY_MARK_MISSING')
        eq=cash+(position.side*position.remaining*(mark[4]-position.entry) if position else 0.)
        equity_peak=max(equity_peak,eq);maxdd=max(maxdd,(equity_peak-eq)/equity_peak)
        if details:curve.append(dict(open_ms=t,equity=eq,cash=cash,unrealized=eq-cash))
        last_eq=eq
    assert position is None
    if not np.isclose(cash,10000+sum(x['net'] for x in trades),atol=1e-7,rtol=1e-12):raise AssertionError('CASH_LEDGER_DOES_NOT_RECONCILE')
    result=metrics(trades);result.update(config=config.key,ending_equity=cash,account_return_pct=100*(cash/10000-1),max_close_drawdown_pct=100*maxdd,exposure_hours=exposure,counts=counts)
    return dict(summary=result,trades=trades,opportunities=opportunities,equity=curve)

def metrics(trades):
    n=len(trades);nets=np.array([r['net'] for r in trades]);wins=nets[nets>1e-8];losses=nets[nets<-1e-8]
    streak=worst=0
    for r in trades:
        streak=streak+1 if r['net']<-1e-8 else 0;worst=max(worst,streak)
    def avg(key):return float(np.mean([r[key] for r in trades])) if n else None
    return dict(n=n,long_n=sum(r['side']==1 for r in trades),short_n=sum(r['side']==-1 for r in trades),win_rate_pct=100*len(wins)/n if n else None,
        mean_win=float(wins.mean()) if len(wins) else None,mean_loss=float(losses.mean()) if len(losses) else None,
        net_expectancy=float(nets.mean()) if n else None,expectancy_R=avg('net_R'),profit_factor=float(wins.sum()/-losses.sum()) if len(losses) else None,
        net_total=float(nets.sum()),max_losing_streak=worst,mean_duration_hours=avg('duration_hours'),mean_mfe_pct=avg('mfe_pct'),mean_mae_pct=avg('mae_pct'),worst_trade_R=min((r['net_R'] for r in trades),default=None),tp1_n=sum(r['tp1'] for r in trades),
        be_armed_n=sum(r['be_armed'] for r in trades),trailing_armed_n=sum(r['trailing_armed'] for r in trades),
        initial_stop_n=sum(r['exit_kind']=='INITIAL_STOP' for r in trades),be_exit_n=sum(r['exit_kind']=='BE_STOP' for r in trades),trailing_exit_n=sum(r['exit_kind']=='TRAIL_STOP' for r in trades),
        forced_end_n=sum(r['exit_kind']=='END_OF_DATA' for r in trades),h1_ambiguous=sum(r['ambiguous_h1'] for r in trades),m1_ambiguous=sum(r['ambiguous_m1'] for r in trades),resolved_m1=sum(r['resolved_m1'] for r in trades),funding_uncertain_trades=sum(r['funding_uncertain']>0 for r in trades))
