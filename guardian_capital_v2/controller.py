"""Serial protection control. Live mode requires a separate exact global approval.

No open/reverse/cancel/leverage/margin paths. Exchange evidence after every write.
"""
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
import hashlib
import json
import time
import numpy as np
from guardian_risk import parse_positions
from guardian_signals import closed_bars,confirmed_structure,atr14
from .client import (POSITIONS,TPSL,TRADES,HISTORY_POSITIONS,ACCOUNT,TICKER,PAIRS,KLINES,
                     REDUCE,PLACE_STOP,MODIFY_STOP,PLACE_POSITION_STOP,MODIFY_POSITION_STOP,DETAIL,rows,Rejected)
from .global_policy import POLICY_HASH,PROPOSAL

D=Decimal
ZERO=D('0')


def num(value):
    result=D(str(value))
    if not result.is_finite():raise ValueError('CAPITAL_NONFINITE')
    return result


def identity(*parts):
    return hashlib.sha256(':'.join(map(str,parts)).encode()).hexdigest()[:32]


class Controller:
    def __init__(self,client,journal,*,notify=lambda text:None,clock=time.time):
        self.client,self.journal,self.notify,self.clock=client,journal,notify,clock
        self.status='STARTING';self._last_notice=None
        activation=journal.latest('ACTIVATION')
        if activation and activation['policy_hash']!=POLICY_HASH:raise ValueError('CAPITAL_POLICY_CHANGED_NO_SILENT_RESET')
        if activation is None:
            journal.append('ACTIVATION:'+POLICY_HASH,'ACTIVATION',dict(policy_hash=POLICY_HASH,mode='LIVE_PROTECTION_ONLY' if client.execution else 'SHADOW'))

    def report(self,status,reason='',**fields):
        self.status=status
        key=(status,reason)
        if key!=self._last_notice:
            self._last_notice=key
            try:
                print('GUARDIAN_CAPITAL_V2_STATUS='+json.dumps(dict(status=status,reason=reason,
                    execution=self.client.execution,policy_hash=POLICY_HASH[:12]),separators=(',',':')),flush=True)
            except Exception:pass
            if self.client.execution:
                try:
                    self.notify('🛡️ GUARDIAN CAPITAL V2\n'+status+'\n'+reason+
                                '\nPROTECTION ONLY · NO AUTOMATIC ENTRIES')
                except Exception:pass
        return dict(status=status,reason=reason,**fields)

    def position(self):
        data,total=rows(self.client.get(POSITIONS,{'symbol':'BTCUSDT','includeSubAccounts':'false'}),'positionList')
        if total is not None and total!=len(data):raise ValueError('CAPITAL_POSITION_LIST_INCOMPLETE')
        parsed=parse_positions(data)
        if parsed is None:return None
        row=dict(data[0]);row['_observed_ms']=int(self.clock()*1000)
        if row['positionMode']!='ONE_WAY':raise ValueError('CAPITAL_HEDGE_UNSUPPORTED_NO_GUESSED_SIDE')
        return row

    def mark(self):
        tick=self.client.get(TICKER,{'symbols':'BTCUSDT'})
        if not isinstance(tick,list) or len(tick)!=1 or tick[0].get('symbol')!='BTCUSDT':raise ValueError('CAPITAL_TICKER_SCOPE')
        value=num(tick[0]['markPrice'])
        if value<=0:raise ValueError('CAPITAL_MARK_INVALID')
        return value

    def orders(self,pid):
        result=self.client.pages(TPSL,{'symbol':'BTCUSDT','positionId':pid},'orderList')
        if any(r.get('positionId')!=pid or r.get('symbol')!='BTCUSDT' for r in result):raise ValueError('CAPITAL_TPSL_SCOPE')
        return result

    def account(self):
        data=self.client.get(ACCOUNT,{'marginCoin':'USDT'})
        data=data[0] if isinstance(data,list) and len(data)==1 else data
        if not isinstance(data,dict) or data.get('marginCoin')!='USDT' or num(data['bonus'])!=0:
            raise ValueError('CAPITAL_ACCOUNT_SCHEMA_OR_BONUS_UNSUPPORTED')
        equity=sum((num(data[k]) for k in ('available','frozen','margin','crossUnrealizedPNL','isolationUnrealizedPNL')),ZERO)
        return data,equity

    def history(self,pid):
        result=self.client.pages(TRADES,{'symbol':'BTCUSDT','positionId':pid},'tradeList')
        ids=[r['tradeId'] for r in result]
        if len(ids)!=len(set(ids)) or any(r.get('symbol')!='BTCUSDT' for r in result):raise ValueError('CAPITAL_TRADES_INCOMPLETE')
        return result

    def total_loss(self,position):
        known={r['payload']['position_id']:r['payload'] for r in self.journal.rows if r['kind']=='POSITION'}
        pid=position['positionId'];known[pid]=dict(position_id=pid,funding=position['funding'])
        realized=fees=funding=ZERO
        for prior_id,record in known.items():
            trades=self.history(prior_id)
            realized+=sum((num(r['realizedPNL']) for r in trades),ZERO)
            fees+=sum((num(r['fee']) for r in trades),ZERO)  # actual GET uses positive fee paid
            if prior_id==pid:
                funding-=num(position['funding'])  # position GET uses negative funding paid
            else:
                closed=self.client.pages(HISTORY_POSITIONS,{'symbol':'BTCUSDT','positionId':prior_id},'positionList')
                matching=[r for r in closed if r.get('positionId')==prior_id and r.get('symbol')=='BTCUSDT']
                if len(matching)!=1:raise ValueError('CAPITAL_CLOSED_POSITION_ACCOUNTING_UNVERIFIED')
                funding-=num(matching[0]['funding'])
        # Never add position.realizedPNL again: production includes fee/funding there.
        return max(ZERO,-realized+fees+funding-num(position['unrealizedPNL']))

    def structure(self,position,mark):
        raw=self.client.get(KLINES,{'symbol':'BTCUSDT','interval':'1h','limit':100,'type':'MARK_PRICE'})
        candles=closed_bars([[r['time'],r['open'],r['high'],r['low'],r['close'],0,0] for r in raw],self.clock()*1000,3600_000)
        if len(candles)<15 or np.any(np.diff(candles[:,0])!=3600_000) or self.clock()*1000-(candles[-1,0]+3600_000)>3600_000:
            raise ValueError('CAPITAL_CLOSED_STRUCTURE_UNVERIFIED')
        atr=num(atr14(candles));_,highs,lows=confirmed_structure(candles)
        long=position['side']=='LONG'
        levels=sorted({num(v) for _,v in (lows if long else highs) if (num(v)<mark if long else num(v)>mark)},reverse=long)
        if len(levels)<2:raise ValueError('CAPITAL_TWO_CAUSAL_LEVELS_REQUIRED')
        frozen=self.journal.latest('STRUCTURE')
        if frozen is None or frozen['position_id']!=position['positionId']:
            frozen=dict(position_id=position['positionId'],side=position['side'],first=str(levels[0]),final=str(levels[1]),
                        frozen_ms=int(self.clock()*1000),atr=str(atr))
            self.journal.append('STRUCTURE:'+position['positionId'],'STRUCTURE',frozen)
        buffer=num(frozen['atr'])*num(PROPOSAL['structural_buffer_atr'])
        first=num(frozen['first'])-buffer if long else num(frozen['first'])+buffer
        final=num(frozen['final'])-buffer if long else num(frozen['final'])+buffer
        def broken(c):return num(c)<first if long else num(c)>first
        count=0
        for bar in reversed(candles):
            if int(bar[0])+3600_000<=frozen['frozen_ms'] or not broken(bar[4]):break
            count+=1
        invalid=(num(candles[-1,4])<final if long else num(candles[-1,4])>final)
        return dict(atr=atr,stop=final,broken_closes=count,invalidated=invalid,
                    closed_at=int(candles[-1,0])+3600_000,frozen=frozen)

    def dynamic_stop(self,row,pid):
        owned=self.journal.owned_stops().get(str(row.get('id')), {})
        if owned.get('position_id')==pid and owned.get('position_dynamic') is True:return True
        # A successful create ACK alone is insufficient: the caller still checks GET fields.
        pending=self.journal.pending()
        if pending and pending['position_id']==pid and pending['path'] in (PLACE_POSITION_STOP,MODIFY_POSITION_STOP):
            return any(r['kind']=='ACK' and r['payload']['client_id']==pending['client_id']
                       and str(r['payload']['order_id'])==str(row.get('id')) for r in self.journal.rows)
        return False

    def verified_stop(self,position,orders,mark):
        qty=num(position['qty']);liq=num(position['liqPrice']);long=position['side']=='LONG'
        for row in orders:
            if row.get('positionId')!=position['positionId'] or row.get('symbol')!='BTCUSDT' or row.get('slPrice') is None:continue
            dynamic=self.dynamic_stop(row,position['positionId'])
            size_ok=dynamic or (row.get('slQty') not in (None,'','0',0) and num(row['slQty'])==qty)
            market=row.get('slOrderType')=='MARKET' or (dynamic and row.get('slOrderType') is None)
            price=num(row['slPrice'])
            if (row.get('id') and size_ok and row.get('slStopType')=='MARK_PRICE' and market
                    and (liq<price<mark if long else mark<price<liq)):
                return row
        return None

    def reconcile_pending(self):
        pending=self.journal.pending()
        if pending is None:return True
        pid=pending['position_id'];path=pending['path']
        p=self.position();mark=self.mark()
        account,equity=self.account()
        if path==REDUCE:
            fills=[r for r in self.history(pid) if r.get('clientId')==pending['client_id']]
            actual=sum((num(r['qty']) for r in fills),ZERO)
            if actual!=num(pending['body']['qty']):
                detail=self.client.get(DETAIL,{'clientId':pending['client_id']})
                # Terminal zero/partial fills can be resolved, never inferred from a timeout.
                if (not isinstance(detail,dict) or detail.get('symbol')!='BTCUSDT'
                        or detail.get('clientId')!=pending['client_id'] or detail.get('reduceOnly') is not True
                        or detail.get('status') not in ('FILLED','CANCELED')
                        or num(detail['tradeQty'])!=actual or actual>num(pending['body']['qty'])):return False
            # A concurrent manual addition is adopted on the next cycle, never erased.
            orders=self.orders(p['positionId']) if p else []
            payload=dict(client_id=pending['client_id'],position_id=pid,stage=pending['stage'] if actual>0 else 0,
                event_at=pending['event_at'],filled_qty=str(actual),remaining_qty=str(p['qty']) if p else '0',
                requested_qty=pending['body']['qty'],terminal_partial=actual!=num(pending['body']['qty']),
                average_entry=str(p['avgOpenPrice']) if p else None,equity=str(equity),
                margin=str(p['margin']) if p else '0',liquidation=str(p['liqPrice']) if p else None,
                residual_stop_verified=bool(p and self.verified_stop(p,orders,mark)),
                verified_at_ms=int(self.clock()*1000))
            self.journal.append('RECONCILED:'+pending['client_id'],'RECONCILED',payload)
            self.report('CLOSE_VERIFIED' if p is None else 'REDUCTION_VERIFIED',
                        'ACTUAL_BITUNIX_STATE_RECHECKED; RESIDUAL_SL_'+('VERIFIED' if payload['residual_stop_verified'] else 'NOT_VERIFIED'))
            return True
        if p is None or p['positionId']!=pid:
            self.journal.append('RECONCILED:'+pending['client_id'],'RECONCILED',dict(client_id=pending['client_id'],position_id=pid,stage=0,event_at=0,verified_at_ms=int(self.clock()*1000)))
            return True
        orders=self.orders(pid);ack=next((r['payload'] for r in reversed(self.journal.rows)
            if r['kind']=='ACK' and r['payload']['client_id']==pending['client_id']),None)
        candidates=[r for r in orders if str(r.get('id'))==str(ack['order_id'])] if ack else []
        if not candidates:
            # A timed-out create cannot be retried or marked owned by guessing.
            if int(self.clock()*1000)-pending['prepared_ms']>=30_000:
                self.journal.append('STOP_FAILED:'+pending['client_id'],'STOP_FAILED',dict(position_id=pid,reason='ACK_WITHOUT_VERIFIABLE_STOP'))
                self.journal.append('RECONCILED:'+pending['client_id'],'RECONCILED',dict(client_id=pending['client_id'],position_id=pid,stage=0,event_at=0,verified_at_ms=int(self.clock()*1000)))
                return True
            return False
        row=candidates[0]
        if (not self.verified_stop(p,[row],mark) or num(row['slPrice'])!=num(pending['body']['slPrice'])
                or row.get('tpPrice') not in (None,'',0,'0')):
            if int(self.clock()*1000)-pending['prepared_ms']>=30_000:
                self.journal.append('STOP_FAILED:'+pending['client_id'],'STOP_FAILED',dict(position_id=pid,reason='ACK_STOP_FIELDS_NOT_VERIFIABLE'))
                self.journal.append('RECONCILED:'+pending['client_id'],'RECONCILED',dict(client_id=pending['client_id'],position_id=pid,stage=0,event_at=0,verified_at_ms=int(self.clock()*1000)))
                return True
            return False
        self.journal.append('OWNED:'+str(row['id']),'STOP_OWNED',dict(order_id=str(row['id']),position_id=pid,
            position_dynamic=path in (PLACE_POSITION_STOP,MODIFY_POSITION_STOP)))
        self.journal.append('RECONCILED:'+pending['client_id'],'RECONCILED',dict(client_id=pending['client_id'],position_id=pid,stage=0,event_at=0,verified_at_ms=int(self.clock()*1000)))
        self.report('STOP_VERIFIED','ACTUAL_BITUNIX_PENDING_ORDER_RECHECKED')
        return True

    def act(self,position,path,body,stage,event_at,mark,reason='VERIFY_NATIVE_SL'):
        cid=body.get('clientId') or identity(position['positionId'],path,body)
        if not self.client.execution:return self.report('SHADOW_PROPOSAL',reason,quantity=body.get('qty',body.get('slQty')),trade_authority='NONE')
        fresh=self.position()
        if fresh is None or any(str(fresh[k])!=str(position[k]) for k in ('positionId','side','qty','avgOpenPrice','marginMode','positionMode')):
            return self.report('RECALCULATING_MANUAL_CHANGE')
        fresh_mark=self.mark()
        if abs(fresh_mark-mark)/mark>num('0.001'):
            return self.report('RECALCULATING_MARK_CHANGE')
        fresh_liq=num(fresh['liqPrice'])
        fresh_distance=(fresh_mark-fresh_liq if fresh['side']=='LONG' else fresh_liq-fresh_mark)
        critical=fresh_liq<=0 or fresh_distance/fresh_mark<=num(PROPOSAL['liquidation_distance_fraction'])
        if critical and (path!=REDUCE or num(body['qty'])<num(fresh['qty'])):
            return self.reduce(fresh,num(fresh['qty']),'CRITICAL_PREFLIGHT_OVERRIDES_PARTIAL_ACTION',3,0,fresh_mark)
        intent=dict(client_id=cid,position_id=position['positionId'],path=path,body=body,stage=stage,event_at=event_at,
                    reason=reason,mark=str(fresh_mark),prepared_ms=int(self.clock()*1000))
        identifier='INTENT:'+cid
        if not self.journal.append(identifier,'INTENT',intent):return self.report('RECONCILIATION_REQUIRED')
        try:
            response=self.client.mutate(path,body,journal=self.journal,intent_id=identifier,
                policy_hash=POLICY_HASH,position=fresh,owned_order_ids=self.journal.owned_stops())
        except Rejected:
            self.journal.append('REJECTED:'+cid,'RECONCILED',dict(client_id=cid,position_id=position['positionId'],stage=0,event_at=0,verified_at_ms=int(self.clock()*1000),rejected=True))
            if path in (PLACE_STOP,MODIFY_STOP,PLACE_POSITION_STOP,MODIFY_POSITION_STOP):
                self.journal.append('STOP_FAILED:'+cid,'STOP_FAILED',dict(position_id=position['positionId'],reason='DEFINITIVE_API_REJECTION'))
            return self.report('ACTION_REJECTED','NO_BLIND_RETRY')
        order_id=str(response.get('orderId',''))
        if not order_id:raise ValueError('CAPITAL_ACK_WITHOUT_ORDER_ID')
        self.journal.append('ACK:'+cid,'ACK',dict(client_id=cid,order_id=order_id))
        if not self.reconcile_pending():return self.report('RECONCILIATION_REQUIRED')
        # A fixed-quantity manual SL cannot be assumed to cover a smaller remainder.
        # Immediate second evaluation installs/verifies a dynamic position SL if needed.
        if path==REDUCE:
            reconciliation=self.journal.latest('RECONCILED')
            if (reconciliation and num(reconciliation.get('filled_qty','0'))>0
                    and num(reconciliation.get('remaining_qty','0'))>0 and not reconciliation['residual_stop_verified']):
                return self.step()
        return dict(status=self.status)

    def reduce(self,p,qty,reason,stage,event_at,mark):
        cid=identity(POLICY_HASH,p['positionId'],stage,event_at,str(qty),p['qty'],p['avgOpenPrice'],reason)
        body=dict(symbol='BTCUSDT',positionId=p['positionId'],side='SELL' if p['side']=='LONG' else 'BUY',
                  orderType='MARKET',qty=str(qty),reduceOnly=True,clientId=cid)
        result=self.act(p,REDUCE,body,stage,event_at,mark,reason)
        return dict(result,reason=reason)

    def step(self):
        if self.journal.pending() and not self.reconcile_pending():return self.report('RECONCILIATION_REQUIRED','NO_BLIND_RETRY')
        p=self.position()
        if p is None:return self.report('NO_OPEN_BTCUSDT_POSITION')
        mark=self.mark();qty=num(p['qty']);liq=num(p['liqPrice']);long=p['side']=='LONG'
        previous=self.journal.latest('POSITION')
        current=dict(position_id=p['positionId'],qty=str(qty),average_entry=str(p['avgOpenPrice']),funding=str(p['funding']))
        if previous!=current:
            self.journal.append('POSITION:'+identity(current,self.journal.tip),'POSITION',current)
        distance=mark-liq if long else liq-mark
        if liq<=0 or distance/mark<=num(PROPOSAL['liquidation_distance_fraction']):
            if self.journal.latest('BASELINE') is None and self.journal.latest('BASELINE_UNAVAILABLE') is None:
                try:
                    _,equity=self.account()
                    self.journal.append('BASELINE','BASELINE',dict(reference_equity=str(equity),created_ms=int(self.clock()*1000)))
                except Exception:
                    self.journal.append('BASELINE_UNAVAILABLE','BASELINE_UNAVAILABLE',dict(reason='NO_BUDGET_RESET_AFTER_EMERGENCY'))
            return self.reduce(p,qty,'CRITICAL_LIQUIDATION_DISTANCE' if liq>0 else 'LIQUIDATION_UNVERIFIABLE',3,0,mark)
        if self.journal.latest('BASELINE_UNAVAILABLE') is not None:
            return self.reduce(p,qty,'LOCKED_REFERENCE_UNAVAILABLE_NO_SILENT_RESET',3,0,mark)
        account,equity=self.account()
        baseline=self.journal.latest('BASELINE')
        if baseline is None:
            if equity<=0:return self.reduce(p,qty,'NONPOSITIVE_EQUITY',3,0,mark)
            baseline=dict(reference_equity=str(equity),created_ms=int(self.clock()*1000))
            self.journal.append('BASELINE','BASELINE',baseline)
        ref=num(baseline['reference_equity'])
        try:loss=self.total_loss(p)
        except Exception:return self.reduce(p,qty,'CUMULATIVE_LOSS_UNVERIFIABLE_FAILSAFE',3,0,mark)
        if equity<=ref*(1-num(PROPOSAL['equity_drawdown_fraction'])) or loss>=ref*num(PROPOSAL['trade_loss_fraction']):
            return self.reduce(p,qty,'TOTAL_BUDGET_OR_ACCOUNT_FLOOR',3,0,mark)
        orders=self.orders(p['positionId']);stop=self.verified_stop(p,orders,mark)
        try:
            context=self.structure(p,mark)
        except Exception:
            if stop is not None:
                adverse=(mark-num(stop['slPrice']) if long else num(stop['slPrice'])-mark)*qty
                if loss+adverse+num(PROPOSAL['assumed_taker_fee'])*qty*mark <= ref*num(PROPOSAL['trade_loss_fraction']):
                    return self.report('PROTECTED_STRUCTURE_DATA_DEGRADED','NO_NEW_STRUCTURAL_TRIM')
            return self.reduce(p,qty,'NO_VERIFIABLE_PROTECTION_CONTEXT',3,0,mark)
        if liq>0 and distance/context['atr']<=num(PROPOSAL['liquidation_distance_atr']):
            return self.reduce(p,qty,'CRITICAL_ATR_DISTANCE',3,0,mark)
        if stop is None and any(r['kind']=='STOP_FAILED' and r['payload']['position_id']==p['positionId'] for r in self.journal.rows):
            return self.reduce(p,qty,'STOP_NOT_VERIFIABLE_FAILSAFE',3,0,mark)
        pair=self.client.get(PAIRS,{'symbols':'BTCUSDT'})
        if not isinstance(pair,list) or len(pair)!=1 or pair[0].get('symbol')!='BTCUSDT':raise ValueError('CAPITAL_PAIR_SCOPE')
        meta=pair[0];step=D('1').scaleb(-int(meta['basePrecision']));tick=D('1').scaleb(-int(meta['quotePrecision']))
        target=context['stop'].quantize(tick,rounding=ROUND_FLOOR if long else ROUND_CEILING)
        # Keep room for structure. Excess size is a capital override, not a noisy stop.
        cost=num(PROPOSAL['assumed_taker_fee'])+num(PROPOSAL['assumed_slippage'])
        limit=ref*num(PROPOSAL['trade_loss_fraction'])
        room=limit-loss-cost*qty*mark
        if room<=0:return self.reduce(p,qty,'COST_RESERVE_EXHAUSTS_BUDGET',3,0,mark)
        if not (liq<target<mark if long else mark<target<liq):return self.reduce(p,qty,'NO_SAFE_STOP_INTERVAL',3,0,mark)
        if context['invalidated']:
            return self.reduce(p,qty,'THESIS_INVALIDATED',3,context['closed_at'],mark)
        if stop is None:
            owned=self.journal.owned_stops()
            ours=next((r for r in orders if str(r.get('id')) in owned
                       and owned[str(r['id'])]['position_id']==p['positionId']
                       and r.get('tpPrice') in (None,'',0,'0')),None)
            if ours is not None and owned[str(ours['id'])].get('position_dynamic') is True:
                # Never touch a manual order or an order containing a take-profit.
                if ours.get('tpPrice') not in (None,'',0,'0'):raise ValueError('CAPITAL_OWNED_ORDER_HAS_TP')
                if ours.get('slPrice'):
                    target=max(target,num(ours['slPrice'])) if long else min(target,num(ours['slPrice']))
                body=dict(symbol='BTCUSDT',positionId=p['positionId'],slPrice=str(target),slStopType='MARK_PRICE')
                return self.act(p,MODIFY_POSITION_STOP,body,0,0,mark)
            body=dict(symbol='BTCUSDT',positionId=p['positionId'],slPrice=str(target),slStopType='MARK_PRICE')
            return self.act(p,PLACE_POSITION_STOP,body,0,0,mark)
        # Do not widen any manual stop. Resize only when actual aggregate risk exceeds budget.
        risk_stop=num(stop['slPrice'])
        adverse=abs(mark-risk_stop)
        projected=loss+qty*(adverse+cost*risk_stop)
        if projected>limit:
            denominator=adverse+cost*(risk_stop-mark)
            if denominator<=0:return self.reduce(p,qty,'UNSIZABLE_STRUCTURAL_RISK',3,0,mark)
            needed=((projected-limit)/denominator/step).to_integral_value(rounding=ROUND_CEILING)*step
            needed=min(qty,max(needed,num(meta['minTradeVolume'])))
            return self.reduce(p,needed,'EXPOSURE_EXCEEDS_AGGREGATE_STRUCTURAL_BUDGET',0,context['closed_at'],mark)
        completed=[r['payload'] for r in self.journal.rows if r['kind']=='RECONCILED'
                   and r['payload'].get('position_id')==p['positionId'] and r['payload'].get('stage') in (1,2,3)]
        stage=max((r['stage'] for r in completed),default=0)
        last_fill=max((r['verified_at_ms'] for r in completed),default=0)
        if context['closed_at']<=last_fill:return self.report('RESIDUAL_PROTECTED','NO_REUSE_OF_PRE_FILL_CANDLE')
        basis=qty+sum((num(r['filled_qty']) for r in completed),ZERO)
        amount=(basis/num(PROPOSAL['tranche_denominator'])/step).to_integral_value(rounding=ROUND_FLOOR)*step
        amount=min(qty,amount)
        next_stage=1 if stage==0 and context['broken_closes']>=1 else 2 if stage==1 and context['broken_closes']>=2 else None
        if next_stage is not None and amount>=num(meta['minTradeVolume']):
            return self.reduce(p,amount,'STRUCTURAL_DETERIORATION',next_stage,context['closed_at'],mark)
        return self.report('RESIDUAL_PROTECTED','STRUCTURE_AND_CAPITAL_WITHIN_POLICY',quantity=str(qty),
                           actual_liquidation=str(liq),actual_equity=str(equity),verified_stop_id=str(stop['id']))
