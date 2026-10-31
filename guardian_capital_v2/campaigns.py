"""Automatic per-position campaigns and an independent, never-rebased global floor.

Observing an owner position is not allocating risk. Allocation needs verified
protection, a reconciled predecessor and remaining global capacity. No order API.
"""
from decimal import Decimal
import hashlib
import json
from .accounting import number,timestamp_ms,ZERO
from .global_policy import PROPOSAL


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class CampaignBook:
    ACCOUNTING=('CAMPAIGN_ACCOUNTING','CAMPAIGN_CLOSE','CAMPAIGN_ADJUSTMENT')

    def __init__(self,journal):self.journal=journal

    def observed(self):
        return {r['payload']['position_id']:r['payload'] for r in self.journal.rows if r['kind']=='CAMPAIGN_OBSERVED'}

    def campaign(self,pid):return self.observed().get(pid)

    def observe(self,position):
        pid=position['positionId'];prior=self.campaign(pid)
        identity=dict(position_id=pid,side=position['side'],position_created_ms=int(position['ctime']))
        if prior is not None:
            if any(prior[k]!=identity[k] for k in identity) or self.closed(pid):
                raise ValueError('CAPITAL_POSITION_ID_REUSE_OR_SIDE_CHANGE')
            return prior
        payload=dict(identity,campaign_id=digest(identity)[:32])
        self.journal.append('CAMPAIGN:'+payload['campaign_id'],'CAMPAIGN_OBSERVED',payload)
        return payload

    def accounting(self,pid):
        return next((r['payload'] for r in reversed(self.journal.rows)
                     if r['kind'] in self.ACCOUNTING and r['payload']['position_id']==pid),None)

    def closed(self,pid):
        return any(r['kind']=='CAMPAIGN_CLOSE' and r['payload']['position_id']==pid for r in self.journal.rows)

    def record_accounting(self,pid,values,*,closed,history_fingerprint=None):
        observed=self.campaign(pid)
        if observed is None:raise ValueError('CAPITAL_UNOBSERVED_POSITION')
        payload=dict(values,position_id=pid,campaign_id=observed['campaign_id'],closed=closed,
                     history_fingerprint=history_fingerprint)
        previous=self.accounting(pid)
        if payload==previous:return previous
        kind=('CAMPAIGN_ADJUSTMENT' if self.closed(pid) else 'CAMPAIGN_CLOSE') if closed else 'CAMPAIGN_ACCOUNTING'
        if self.closed(pid) and not closed:raise ValueError('CAPITAL_CLOSED_CAMPAIGN_CANNOT_REOPEN')
        # Include lineage so a genuine revision back to an earlier value is not lost.
        identifier=kind+':'+observed['campaign_id']+':'+digest([payload,self.journal.tip])
        self.journal.append(identifier,kind,payload)
        return payload

    def settled_total(self):
        total=ZERO
        for pid in self.observed():
            values=self.accounting(pid)
            if values is None:raise ValueError('CAPITAL_ACCOUNTING_INCOMPLETE')
            total+=number(values['net'])
        return total

    def initialize(self,account,equity,*,position=None,deferred=False):
        baseline=self.journal.latest('BASELINE')
        if baseline is not None:
            if baseline.get('schema')!=2:raise ValueError('CAPITAL_LEGACY_BASELINE_REQUIRES_REVIEW')
            return baseline
        if self.journal.latest('BASELINE_UNAVAILABLE'):raise ValueError('CAPITAL_REFERENCE_UNAVAILABLE_NO_RESET')
        equity=number(equity)
        if equity<=0:raise ValueError('CAPITAL_REFERENCE_NONPOSITIVE')
        wallet=sum((number(account[k]) for k in ('available','frozen','margin')),ZERO)
        baseline=dict(schema=2,reference_equity=str(equity),wallet_anchor=str(wallet),
                      settled_anchor=None if deferred else str(self.settled_total()),
                      created_ms=int(self.journal.clock()*1000))
        if deferred:
            if position is None:raise ValueError('CAPITAL_ANCHOR_POSITION_REQUIRED')
            baseline.update(anchor_position_id=position['positionId'],anchor_fee_magnitude=str(abs(number(position['fee']))),
                            anchor_funding=str(number(position['funding'])),anchor_position_realized=str(number(position['realizedPNL'])))
        self.journal.append('BASELINE','BASELINE',baseline)
        return baseline

    def resolve_anchor(self,trades):
        baseline=self.journal.latest('BASELINE')
        if baseline is None or baseline['settled_anchor'] is not None or self.journal.latest('GLOBAL_ANCHOR'):return
        before=[]
        for row in trades:
            stamp=timestamp_ms(row.get('ctime'))
            if stamp<baseline['created_ms']:before.append(row)
        fees=sum((number(r['fee']) for r in before),ZERO)
        gross=sum((number(r['realizedPNL']) for r in before),ZERO)
        magnitude=number(baseline['anchor_fee_magnitude']);funding=number(baseline['anchor_funding'])
        observed=number(baseline['anchor_position_realized'])
        deduction=gross-magnitude+funding;rebate=gross+magnitude+funding
        # A late fee must affect current settlement, not rewrite the captured account anchor.
        if observed==deduction:net=deduction
        elif observed==rebate:net=rebate
        elif observed==gross and abs(fees)==magnitude:net=gross-fees+funding
        else:raise ValueError('CAPITAL_ANCHOR_COST_UNVERIFIED')
        self.journal.append('GLOBAL_ANCHOR','GLOBAL_ANCHOR',dict(settled_net=str(net)))

    def global_state(self,account,equity):
        baseline=self.journal.latest('BASELINE')
        if baseline is None:raise ValueError('CAPITAL_GLOBAL_BASELINE_REQUIRED')
        anchor=baseline['settled_anchor']
        if anchor is None:
            resolved=self.journal.latest('GLOBAL_ANCHOR')
            if resolved is None:raise ValueError('CAPITAL_GLOBAL_ANCHOR_PENDING')
            anchor=resolved['settled_net']
        # Deposits never lift the accounting-backed wallet or reset the reference.
        protected_wallet=number(baseline['wallet_anchor'])+self.settled_total()-number(anchor)
        unrealized=number(account['crossUnrealizedPNL'])+number(account['isolationUnrealizedPNL'])
        effective=min(number(equity),protected_wallet+unrealized)
        floor=number(baseline['reference_equity'])*(1-number(PROPOSAL['equity_drawdown_fraction']))
        return dict(effective_equity=effective,floor=floor,headroom=effective-floor,blocked=effective<=floor,
                    protected_wallet=protected_wallet,actual_equity=number(equity))

    def reference(self,pid,global_state):
        identifier='CAMPAIGN_REFERENCE:'+self.campaign(pid)['campaign_id']
        prior=next((r['payload'] for r in self.journal.rows if r['id']==identifier),None)
        if prior is not None:return prior
        equity=global_state['effective_equity']
        if equity<=0:raise ValueError('CAPITAL_NO_ADMISSIBLE_EQUITY')
        result=dict(position_id=pid,campaign_id=self.campaign(pid)['campaign_id'],
                    reference_equity=str(equity),loss_limit=str(equity*number(PROPOSAL['trade_loss_fraction'])))
        self.journal.append(identifier,'CAMPAIGN_REFERENCE',result)
        return result

    def budget(self,pid,global_state,net_at_mark):
        reference=self.reference(pid,global_state)
        allocated=next((r['payload'] for r in self.journal.rows
                        if r['id']=='ALLOCATION:'+reference['campaign_id']),None)
        individual=number(allocated['loss_limit'] if allocated else reference['loss_limit'])
        return individual

    def allocate(self,pid,budget,*,stop_id,net_at_stop,global_state,risk_ceiling):
        campaign=self.campaign(pid)
        if (not stop_id or budget<=0 or -number(net_at_stop)>min(budget,risk_ceiling) or global_state['blocked']
                or any(other!=pid and not self.closed(other) for other in self.observed())):
            raise ValueError('CAPITAL_ALLOCATION_PRECONDITIONS')
        payload=dict(position_id=pid,campaign_id=campaign['campaign_id'],loss_limit=str(budget),
                     stop_id=str(stop_id),net_at_stop=str(net_at_stop),global_loss_ceiling=str(risk_ceiling),
                     global_reference=self.journal.latest('BASELINE')['reference_equity'])
        identifier='ALLOCATION:'+campaign['campaign_id']
        self.journal.append(identifier,'CAMPAIGN_ALLOCATED',payload)
        return next(r['payload'] for r in self.journal.rows if r['id']==identifier)
