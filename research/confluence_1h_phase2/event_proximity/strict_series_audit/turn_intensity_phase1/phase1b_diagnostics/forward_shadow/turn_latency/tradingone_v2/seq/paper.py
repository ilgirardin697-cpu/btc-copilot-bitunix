"""Pure local simulated positions; no exchange, credential or transport imports."""
import math
from copy import deepcopy
from research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.swing_capture.simulator import be_level,FEE,SLIP
from .maths import H,M
from .engine import Ledger


def exposure(lots,stop,side,equity,budget,realized_net=0.):
    """A manual add never resets realized losses. Descriptive, never executes."""
    values=[stop,equity,budget,realized_net]+[v for lot in lots for v in (lot['qty'],lot['entry'])]
    if side not in (-1,1) or not all(math.isfinite(v) for v in values) or min(stop,equity,budget)<=0 or not lots or any(min(lot['qty'],lot['entry'])<=0 for lot in lots):
        raise ValueError('UNVERIFIABLE_EXPOSURE')
    qty=sum(lot['qty'] for lot in lots)
    entry=sum(lot['qty']*lot['entry'] for lot in lots)/qty
    exit_fill=stop*(1-side*SLIP)
    gross=sum(side*lot['qty']*(exit_fill-lot['entry']) for lot in lots)
    # realized_net already contains previously realized entry/exit costs.
    # Remaining-lot entry fee is counted exactly once here.
    costs=sum(lot['qty']*lot['entry']*FEE for lot in lots)+qty*exit_fill*FEE
    net_at_stop=realized_net+gross-costs
    notional=qty*entry
    return dict(qty=qty,average_entry=entry,net_at_stop=net_at_stop,
        aggregate_loss_at_stop=max(0.,-net_at_stop),budget=budget,
        budget_consumed=max(0.,-realized_net),
        excessive=net_at_stop < -budget or notional>equity,
        notional_equity=notional/equity,liquidation='NOT_MODELED_1X_COLLATERALIZED_SYNTHETIC',
        action='INFORM_ONLY_NO_ADD_SUPPORTED')


class Paper:
    def __init__(self,ledger=None,venue='BINANCE_SPOT'):
        if venue!='BINANCE_SPOT':
            raise ValueError('FUTURES_BLOCKED_WITHOUT_CONTRACT_FUNDING_AND_MARK_DATA')
        self.log=ledger if ledger is not None else Ledger()
        self.cash=10000.
        self.peak=10000.
        self.halted=False
        self.position=None
        self.pending=[]
        self.trades=[]
        self.curve=[]
        self.fills=[]
        self.last_open=None
        self.last_closed=None
        self.maxdd=0.

    def enqueue(self,plan):
        if any(p['id']==plan['id'] for p in self.pending) or (self.position and self.position['id']==plan['id']):
            return
        self.pending.append(deepcopy(plan))

    def _equity(self,price):
        p=self.position
        return self.cash+(p['side']*p['left']*(price-p['entry']) if p else 0)

    def _limit(self,price,when):
        equity=self._equity(price)
        self.peak=max(self.peak,equity)
        dd=(self.peak-equity)/self.peak
        self.maxdd=max(self.maxdd,dd)
        if dd>=.05 and not self.halted:
            self.halted=True
            self.log.add('SIM_RISK_HALTED',when,drawdown=dd,equity=equity)

    def _fill(self,qty,reference,kind,at,interval):
        p=self.position
        price=reference*(1-p['side']*SLIP)
        fee=qty*price*FEE
        gross=p['side']*qty*(price-p['entry'])
        self.cash+=gross-fee
        p['gross']+=gross
        p['exit_fees']+=fee
        p['left']-=qty
        r=self.log.add('SIM_FILL',at,trade_id=p['id'],reason=kind,qty=qty,price=price,
            gross=gross,fee=fee,window_end=at+interval,time_is_interval=bool(interval),
            funding=0.,funding_status='NOT_APPLICABLE_SPOT',not_a_real_fill=True)
        self.fills.append(r)
        if p['left']<=p['qty']*1e-12:
            net=p['gross']-p['entry_fee']-p['exit_fees']
            trade=dict(id=p['id'],side=p['side'],entry_at=p['entry_at'],exit_at=at+interval,
                exit_time_is_interval=bool(interval),exit_reason=kind,net=net,gross=p['gross'],
                entry_fee=p['entry_fee'],exit_fees=p['exit_fees'],funding=0.,funding_status='NOT_APPLICABLE_SPOT',
                qty=p['qty'],entry=p['entry'],risk=p['risk'],net_R=net/p['risk'],
                tp1=p['tp1'],ambiguous=p['ambiguous'],mfe_bound=p['mfe'],mae_bound=p['mae'],
                signal_at=p['at'],entry_latency_ms=p['entry_at']-p['at'],borrow_or_futures_costs='NOT_MODELED',
                evidence='ENGINEERING_REPLAY_NOT_VALIDATION')
            self.trades.append(trade)
            self.log.add('SIM_CLOSED',at+interval,**trade)
            self.position=None

    def step(self,row,known_atr):
        t,o,h,l,c,v=map(float,row)
        t=int(t)
        if self.last_open is not None and t!=self.last_open+M:
            raise ValueError('SIM_DATA_GAP_OR_REPLAY')
        if self.last_closed is not None and self.last_closed>t:
            raise ValueError('SIM_TIME_REVERSED')
        self.last_open=t
        self._limit(o,t)
        due,self.pending=self.pending,[]
        for plan in due:
            reason=None
            side=plan['side']
            if plan['at']!=t:
                reason='STALE_SIGNAL_NO_RETROACTIVE_FILL'
            elif self.position:
                reason='POSITION_OPEN_NO_AVERAGING'
            elif self.halted:
                reason='CUMULATIVE_RISK_BUDGET'
            elif not plan['pivot'] or not math.isfinite(plan['atr']) or plan['atr']<=0:
                reason='NO_VERIFIABLE_STRUCTURAL_STOP'
            elif side*(o-plan['pivot'])<=0:
                reason='OPEN_GAP_INVALIDATES_STRUCTURE'
            else:
                fill=o*(1+side*SLIP)
                structural=plan['pivot']-side*.2*plan['atr']
                stop=min(structural,fill-1.5*plan['atr']) if side==1 else max(structural,fill+1.5*plan['atr'])
                exit_fill=stop*(1-side*SLIP)
                unit=side*(fill-exit_fill)+FEE*(fill+exit_fill)
                risk=self.cash*.005
                if min(stop,unit,risk)<=0:
                    reason='INVALID_STOP_OR_EQUITY'
                else:
                    qty=risk/unit
                    if qty*fill*(1+FEE)>self.cash:
                        reason='LEVERAGE_REQUIRED_REJECTED'
                    else:
                        fee=qty*fill*FEE
                        self.cash-=fee
                        self.position=dict(**plan,entry=fill,entry_at=t,qty=qty,left=qty,
                            initial_stop=stop,stop=stop,target=fill*(1+side*.01),risk=risk,
                            entry_fee=fee,exit_fees=0.,gross=0.,tp1=False,ambiguous=False,
                            peak=fill,trough=fill,mfe=0.,mae=0.,stop_kind='INITIAL_STOP')
                        self.log.add('SIM_ENTRY',t,trade_id=plan['id'],side=side,qty=qty,entry=fill,stop=stop,
                            target=self.position['target'],risk=risk,fee=fee,entry_latency_ms=t-plan['at'],
                            fill_assumption='NEXT_15M_OPEN_PLUS_SLIPPAGE_NOT_GUARANTEED',not_a_real_fill=True)
            if reason:
                self.log.add('SIM_REJECTED',t,trade_id=plan['id'],side=side,reason=reason)
        p=self.position
        if p:
            side=p['side']
            p['peak']=max(p['peak'],h)
            p['trough']=min(p['trough'],l)
            p['mfe']=max(p['mfe'],max(0.,side*((h if side==1 else l)-p['entry'])/p['entry']))
            p['mae']=max(p['mae'],max(0.,-side*((l if side==1 else h)-p['entry'])/p['entry']))
            stop_hit=l<=p['stop'] if side==1 else h>=p['stop']
            target_hit=not p['tp1'] and (h>=p['target'] if side==1 else l<=p['target'])
            if side*(o-p['stop'])<=0:
                self._fill(p['left'],o,'GAP_'+p['stop_kind'],t,0)
            elif stop_hit:
                p['ambiguous']=bool(target_hit)
                self._fill(p['left'],p['stop'],p['stop_kind'],t,M)
            else:
                if target_hit:
                    self._fill(min(p['left'],p['qty']*.5),p['target'],'TP1',t,M)
                    p['tp1']=True
                if self.position and t+M-p['entry_at']>=24*H:
                    self._fill(p['left'],c,'TIME_EXIT_24H',t+M,0)
            if self.position and p['tp1']:
                if known_atr is not None and math.isfinite(known_atr) and known_atr>0:
                    be=be_level(p['entry'],side,0.)
                    trail=p['peak']-1.5*known_atr if side==1 else p['trough']+1.5*known_atr
                    old=p['stop']
                    p['stop']=max(old,be,trail) if side==1 else min(old,be,trail)
                    if p['stop']!=old:
                        p['stop_kind']='TRAIL_STOP' if side*(trail-be)>0 else 'NET_BE_STOP'
                        self.log.add('SIM_STOP_UPDATE',t+M,trade_id=p['id'],old=old,new=p['stop'],
                            effective_at=t+M,kind_name=p['stop_kind'],never_widened=True)
        self.last_closed=t+M
        self._limit(c,t+M)
        equity=self._equity(c)
        self.curve.append(dict(available_at=t+M,equity=equity,cash=self.cash,halted=self.halted))
        self.log.add('SIM_MARK',t+M,equity=equity,cash=self.cash,
                     open_id=self.position['id'] if self.position else None,halted=self.halted)
        if not math.isclose(self.cash,10000+sum(x['net'] for x in self.trades)-(self.position['entry_fee']-self.position['gross']+self.position['exit_fees'] if self.position else 0),abs_tol=1e-7):
            raise AssertionError('SIM_CASH_RECONCILIATION')

    def summary(self):
        nets=[x['net'] for x in self.trades]
        return dict(completed=len(nets),long=sum(x['side']==1 for x in self.trades),
            short=sum(x['side']==-1 for x in self.trades),net_realized=sum(nets),
            marked_equity=self.curve[-1]['equity'] if self.curve else self.cash,
            max_close_drawdown=self.maxdd,halted=self.halted,
            censored_open=deepcopy(self.position),pending=deepcopy(self.pending),
            win_rate=sum(n>0 for n in nets)/len(nets) if nets else None,
            validation='NOT_ESTIMATED_SELECTED_ENGINEERING_SAMPLE')
