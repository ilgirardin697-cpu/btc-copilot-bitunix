"""Offline API fault/position simulations. No real exchange or Telegram calls."""
import copy
import ast
import hashlib
from datetime import datetime,timezone
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
try:
    import requests
except ImportError:
    raise unittest.SkipTest('Capital V2 workflow installs explicit runtime dependencies') from None
from guardian_capital_v2.client import (Client,Rejected,count,rows,POSITIONS,TPSL,TRADES,
    HISTORY_POSITIONS,ACCOUNT,TICKER,PAIRS,REDUCE,PLACE_STOP,MODIFY_STOP,PLACE_POSITION_STOP,MODIFY_POSITION_STOP,DETAIL)
from guardian_capital_v2.controller import Controller
from guardian_capital_v2.global_policy import POLICY_HASH,APPROVAL_PHRASE
from guardian_capital_v2.journal import Journal
from guardian_capital_v2.host import before_guardian_cycle,owner_reply


class Clock:
    def __init__(self):self.value=1800000000.0
    def __call__(self):return self.value


def position(pid='123',qty='1',side='LONG'):
    return dict(positionId=pid,symbol='BTCUSDT',qty=qty,leverage=2,liqPrice='50' if side=='LONG' else '150',
        avgOpenPrice='101' if side=='LONG' else '99',unrealizedPNL='-1',margin='10',marginRate='.1',
        marginMode='CROSS',positionMode='ONE_WAY',side=side,ctime=1700000000000,mtime=1700000000000,
        fee='-1',funding='-1',realizedPNL='-2')


def stop(qty='1',identifier='900',pid='123'):
    return dict(id=identifier,positionId=pid,symbol='BTCUSDT',slPrice='95',slQty=qty,
                slStopType='MARK_PRICE',slOrderType='MARKET',tpPrice=None)


class FakeClient:
    def __init__(self,clock,execution=True):
        self.clock,self.execution=clock,execution;self.p=position();self.s=[stop()]
        self.wallet=D('10000')
        self.closed={};self.trades={'123':[dict(tradeId='100',symbol='BTCUSDT',qty='1',fee='1',realizedPNL='0',
            clientId='manual',side='BUY',ctime=int(clock()*1000)-3600000)]}
        self.mark='100';self.mutations=[];self.bad_stop=False;self.timeout=False;self.reject=False
    def get(self,path,params):
        if path==POSITIONS:return [copy.deepcopy(self.p)] if self.p else []
        if path==TICKER:return [dict(symbol='BTCUSDT',markPrice=self.mark,lastPrice=self.mark)]
        if path==ACCOUNT:
            margin=D(self.p['margin']) if self.p else D('0')
            return dict(marginCoin='USDT',available=str(self.wallet-margin),frozen='0',margin=str(margin),transfer='0',
                        crossUnrealizedPNL=self.p['unrealizedPNL'] if self.p and self.p['marginMode']=='CROSS' else '0',
                        isolationUnrealizedPNL=self.p['unrealizedPNL'] if self.p and self.p['marginMode']=='ISOLATION' else '0',bonus='0')
        if path==PAIRS:return [dict(symbol='BTCUSDT',basePrecision=4,quotePrecision=1,minTradeVolume='.0001')]
        if path==DETAIL:return dict(symbol='BTCUSDT',clientId=params['clientId'],status='NEW',reduceOnly=True,tradeQty='0')
        raise ValueError('FAKE_UNEXPECTED_GET')
    def pages(self,path,params,key):
        if path==TPSL:return copy.deepcopy([r for r in self.s if r['positionId']==params['positionId']])
        if path==TRADES:return copy.deepcopy(self.trades.get(params['positionId'],[]))
        if path==HISTORY_POSITIONS:
            return [copy.deepcopy(self.closed[params['positionId']])] if 'positionId' in params else copy.deepcopy(list(self.closed.values()))
        raise ValueError('FAKE_UNEXPECTED_PAGES')
    def manual_qty(self,qty,average=None,fee='0'):
        p=self.p;delta=D(qty)-D(p['qty']);long=p['side'] in ('LONG','BUY')
        opening='BUY' if long else 'SELL'
        gross=D('0') if delta>0 else (D(self.mark)-D(p['avgOpenPrice']))*abs(delta)*(1 if long else -1)
        self.trades.setdefault(p['positionId'],[]).append(dict(tradeId='M'+str(len(self.trades[p['positionId']])),
            symbol='BTCUSDT',qty=str(abs(delta)),fee=fee,realizedPNL=str(gross),clientId='manual',
            side=opening if delta>0 else 'SELL' if long else 'BUY',ctime=int(self.clock()*1000)))
        self.wallet+=gross-D(fee);p['qty']=str(qty)
        if average is not None:p['avgOpenPrice']=str(average)
        p['fee']=str(-sum((D(r['fee']) for r in self.trades[p['positionId']]),D('0')))
        p['unrealizedPNL']=str((D(self.mark)-D(p['avgOpenPrice']))*D(qty)*(1 if long else -1))
    def mutate(self,path,body,**kwargs):
        self.mutations.append((path,copy.deepcopy(body)))
        if self.timeout:raise ValueError('CAPITAL_REQUEST_UNCERTAIN')
        if self.reject:raise Rejected('CAPITAL_API_REJECTED')
        if path==REDUCE:
            p=self.p;qty=D(body['qty']);before=D(p['qty']);remaining=before-qty
            gross=(D(self.mark)-D(p['avgOpenPrice']))*qty*(1 if p['side']=='LONG' else -1)
            self.trades.setdefault(p['positionId'],[]).append(dict(tradeId=str(1000+len(self.mutations)),
                symbol='BTCUSDT',qty=str(qty),fee=str(qty*D(self.mark)*D('.0006')),
                realizedPNL=str(gross),clientId=body['clientId'],side=body['side'],ctime=int(self.clock()*1000)))
            self.wallet+=gross-qty*D(self.mark)*D('.0006')
            p['fee']=str(-sum((D(r['fee']) for r in self.trades[p['positionId']]),D('0')))
            if remaining==0:
                self.closed[p['positionId']]=copy.deepcopy(p);self.p=None
            else:
                self.p['qty']=str(remaining)
                self.p['margin']=str(D(self.p['margin'])*remaining/before)
                self.p['unrealizedPNL']=str(D(self.p['unrealizedPNL'])*remaining/before)
            return dict(orderId=str(500+len(self.mutations)))
        if path in (PLACE_STOP,PLACE_POSITION_STOP):
            identifier=str(500+len(self.mutations))
            self.s.append(dict(body,id=identifier,tpPrice=None))
            if self.bad_stop:self.s[-1]['slPrice']=None
            return dict(orderId=identifier)
        if path in (MODIFY_STOP,MODIFY_POSITION_STOP):
            row=next(r for r in self.s if r['id']==body['orderId']) if path==MODIFY_STOP else next(r for r in self.s if r.get('slQty') is None)
            row.update(body)
            if self.bad_stop:row['slPrice']=None
            return dict(orderId=row['id'])
        raise ValueError('FAKE_UNEXPECTED_MUTATION')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.clock=Clock();self.j=Journal(Path(self.tmp.name)/'journal.jsonl',clock=self.clock)
        self.client=FakeClient(self.clock);self.c=Controller(self.client,self.j,clock=self.clock)
        self.context=dict(atr=D('1'),stop=D('90'),broken_closes=0,invalidated=False,
            closed_at=int(self.clock()*1000)-1000,frozen={'first':'95','final':'90'})
        self.c.structure=lambda p,mark:dict(self.context)
        self.output=patch('builtins.print');self.output.start();self.addCleanup(self.output.stop)
    def own(self,identifier='900'):
        self.j.append('OWN:'+identifier,'STOP_OWNED',dict(order_id=identifier,position_id='123'))
    def test_healthy_structure_keeps_position(self):
        self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED');self.assertFalse(self.client.mutations)
    def test_real_bitunix_buy_sell_position_aliases_use_audited_normalization(self):
        for api_side,expected in (('BUY','LONG'),('SELL','SHORT'),('LONG','LONG'),('SHORT','SHORT')):
            self.client.p['side']=api_side
            self.assertEqual(self.c.position()['side'],expected)
    def test_raw_buy_position_can_only_propose_sell_and_raw_sell_only_buy(self):
        for api_side,liq,close_side in (('BUY','99','SELL'),('SELL','101','BUY')):
            self.client.p.update(positionId='123' if api_side=='BUY' else '456',side=api_side,liqPrice=liq)
            with patch.object(self.c,'act',return_value={'status':'SHADOW_PROPOSAL'}) as action:
                self.c.step()
                body=action.call_args.args[2]
                self.assertEqual(body['side'],close_side)
                self.assertIs(body['reduceOnly'],True)
                self.assertEqual(body['qty'],'1')
    def test_price_oscillations_alone_never_trim(self):
        for value in ('99.8','100.1','99.9'):
            self.client.mark=value;self.c.step()
        self.assertFalse(self.client.mutations)
    def test_critical_closes_without_waiting_candles_or_loss_accounting(self):
        self.client.p['liqPrice']='99'
        self.c.structure=Mock(side_effect=AssertionError('NO_PATTERN_WAIT'))
        self.c.total_loss=Mock(side_effect=AssertionError('NO_PATTERN_WAIT'))
        self.c.step();self.assertEqual(self.client.mutations[0][1]['qty'],'1')
        self.assertIsNone(self.client.p);self.assertIsNone(self.j.pending())
    def test_total_loss_includes_fees_funding_not_realized_field_twice(self):
        self.assertEqual(self.c.total_loss(self.client.p),D('3'))
    def test_manual_add_qty_and_average_are_automatically_adopted(self):
        self.own();self.c.step();ref=self.j.latest('BASELINE')['reference_equity']
        self.client.manual_qty('2','100.5')
        self.c.step()
        self.assertEqual(self.client.mutations[-1][0],PLACE_POSITION_STOP)
        self.assertNotIn('slQty',self.client.mutations[-1][1])
        self.assertEqual(self.j.latest('POSITION')['average_entry'],'100.5')
        self.assertEqual(self.j.latest('BASELINE')['reference_equity'],ref)
        self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')
    def test_manual_add_does_not_reset_realized_loss_budget(self):
        self.c.step()
        self.client.trades['123'].append(dict(tradeId='200',symbol='BTCUSDT',qty='.1',fee='0',realizedPNL='-95',clientId='manual-close',side='SELL',ctime=int(self.clock()*1000)))
        self.client.p['qty']='.9';self.client.wallet-=D('95')
        self.client.manual_qty('2','100');self.client.p['unrealizedPNL']='-10'
        self.c.step();self.assertEqual(self.client.mutations[-1][1]['qty'],'2')
        self.assertIsNone(self.client.p)
    def test_new_position_after_close_has_own_budget_and_preserves_global_losses(self):
        self.c.step();baseline=self.j.latest('BASELINE')
        self.client.trades['123'].append(dict(tradeId='200',symbol='BTCUSDT',qty='.1',fee='0',realizedPNL='-110',clientId='manual-close',side='SELL',ctime=int(self.clock()*1000)))
        self.client.p['qty']='.9';self.client.wallet-=D('110')
        self.c.step();self.assertIsNone(self.client.p)
        self.client.p=position('456');self.client.s=[stop(pid='456')]
        self.client.trades['456']=[dict(self.client.trades['123'][0],tradeId='NEW')];self.client.wallet-=D('2')
        self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')
        self.assertIsNotNone(self.client.p)
        self.assertEqual(sum(r['kind']=='CAMPAIGN_ALLOCATED' for r in self.j.rows),2)
        self.assertLess(D(self.c.book.accounting('123')['net']),D('-100'))
        self.assertEqual(self.j.latest('BASELINE'),baseline)
    def test_first_and_second_structural_trims_once_each(self):
        self.own();self.context['broken_closes']=1
        self.c.step();self.assertEqual(self.client.mutations[0][1]['qty'],'0.3333')
        self.assertEqual(self.client.mutations[1][0],PLACE_POSITION_STOP)
        self.assertTrue(self.j.latest('RECONCILED'))
        self.c.step()  # update owned stop to actual remaining qty
        n=len(self.client.mutations)
        self.context['broken_closes']=2
        self.c.step();self.assertEqual(len(self.client.mutations),n)
        self.clock.value+=3600;self.context['closed_at']=int(self.clock()*1000)-1
        self.c.step();self.assertEqual(self.client.mutations[-1][1]['qty'],'0.3333')
        self.c.step();n=len(self.client.mutations)
        self.clock.value+=3600;self.context.update(closed_at=int(self.clock()*1000)-1,broken_closes=9)
        self.c.step();self.assertEqual(len(self.client.mutations),n)
    def test_invalidation_exits_remainder(self):
        self.context['invalidated']=True;self.c.step();self.assertIsNone(self.client.p)
    def test_stop_verification_checks_actual_qty_trigger_and_position(self):
        p=self.c.position()
        for row in (dict(stop(),slQty='.5'),dict(stop(),slQty='2'),dict(stop(),slPrice=None),
                    dict(stop(),slStopType='LAST_PRICE'),dict(stop(),slOrderType='LIMIT')):
            self.assertIsNone(self.c.verified_stop(p,[row],D('100')))
    def test_no_manual_order_modified_or_cancelled(self):
        self.client.s=[dict(stop(),slQty='.5',tpPrice='110')]
        self.c.step();self.assertEqual(self.client.mutations[0][0],PLACE_POSITION_STOP)
        self.assertEqual(self.client.s[0]['tpPrice'],'110')
    def test_failed_stop_readback_uses_authorized_final_failsafe(self):
        self.client.s=[];self.client.bad_stop=True
        self.c.step();self.assertIsNotNone(self.j.pending())
        self.clock.value+=31
        self.c.step();self.assertEqual(self.client.mutations[-1][0],REDUCE)
        self.assertIsNone(self.client.p)
    def test_stop_rejected_closes_remaining_never_modifies_manual(self):
        self.client.s=[];self.client.reject=True
        self.c.step();self.client.reject=False
        self.c.step();self.assertIsNone(self.client.p)
        self.assertEqual([p for p,b in self.client.mutations],[PLACE_POSITION_STOP,REDUCE])
    def test_dynamic_stop_covers_manual_add_and_reduction_without_qty_guess(self):
        self.client.s=[];self.c.step()
        row=self.client.s[-1]
        self.assertNotIn('slQty',row)
        self.client.p['qty']='2'
        self.assertIsNotNone(self.c.verified_stop(self.client.p,[row],D('100')))
        self.client.p['qty']='.25'
        self.assertIsNotNone(self.c.verified_stop(self.client.p,[row],D('100')))
        self.assertIsNone(self.c.verified_stop(self.client.p,[dict(row,id='MANUAL')],D('100')))
    def test_partial_trim_checks_real_residual_and_installs_native_sl_same_step(self):
        self.context['broken_closes']=1;self.c.step()
        reductions=[r['payload'] for r in self.j.rows if r['kind']=='RECONCILED' and r['payload'].get('stage')==1]
        self.assertEqual(reductions[0]['remaining_qty'],'0.6667')
        self.assertEqual(reductions[0]['liquidation'],'50')
        self.assertFalse(reductions[0]['residual_stop_verified'])
        self.assertIsNotNone(self.c.verified_stop(self.client.p,self.client.s,D('100')))
    def test_excess_size_reduced_to_budget_not_artificially_tight_stop(self):
        self.c.step()
        self.client.manual_qty('30','100')
        self.client.s=[]
        self.c.step()  # register structural position SL, never tighten for an oversized trade
        self.assertEqual(D(self.client.s[-1]['slPrice']),D('90'))
        self.c.step()
        close=self.client.mutations[-1][1]
        self.assertEqual(self.client.mutations[-1][0],REDUCE)
        self.assertGreater(D(close['qty']),D('20'))
        self.assertLess(D(close['qty']),D('30'))
        self.assertIsNotNone(self.c.verified_stop(self.client.p,self.client.s,D('100')))
    def test_actual_total_budget_can_exit_even_if_structure_stays_valid(self):
        self.c.step();self.client.p['unrealizedPNL']='-101'
        self.c.step();self.assertIsNone(self.client.p)
    def test_short_structural_trim_is_buy_reduce_only_never_open_long(self):
        self.client.p=position(side='SHORT');self.client.s=[dict(stop(),slPrice='105')]
        self.client.trades['123'][0]['side']='SELL'
        self.context.update(stop=D('110'),broken_closes=1)
        self.c.step()
        body=next(b for path,b in self.client.mutations if path==REDUCE)
        self.assertEqual(body['side'],'BUY');self.assertIs(body['reduceOnly'],True)
        self.assertGreater(D(self.client.p['qty']),D('0'))
    def test_same_material_manual_change_back_again_does_not_reset_budget(self):
        self.c.step();baseline=self.j.latest('BASELINE')
        self.client.manual_qty('2');self.c.step()
        self.client.manual_qty('1');self.c.step()
        self.assertEqual(self.j.latest('POSITION')['qty'],'1')
        self.assertEqual(self.j.latest('BASELINE'),baseline)
    def test_logger_failure_does_not_prevent_critical_close(self):
        self.client.p['liqPrice']='99'
        with patch('builtins.print',side_effect=OSError('offline')):
            self.c.step()
        self.assertIsNone(self.client.p)
    def test_critical_close_locks_equity_before_future_manual_position(self):
        self.client.p['liqPrice']='99';self.c.step()
        self.assertEqual(self.j.latest('BASELINE')['reference_equity'],'9999')
    def test_zero_liquidation_is_documented_and_still_requires_protection(self):
        self.client.p['liqPrice']='0'
        self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')
        self.assertFalse(self.client.mutations)
    def test_critical_fresh_preflight_supersedes_structural_partial_trim(self):
        self.context['broken_closes']=1
        original=self.c.position;count=[0]
        def changed():
            count[0]+=1
            if count[0]==2:self.client.p['liqPrice']='99'
            return original()
        self.c.position=changed;self.c.step()
        self.assertEqual(self.client.mutations[0][1]['qty'],'1')
        self.assertIsNone(self.client.p)
    def test_unverifiable_history_closes_instead_of_claiming_budget_safe(self):
        self.c.total_loss=Mock(side_effect=ValueError('CAPITAL_PAGINATION_INCOMPLETE'))
        self.c.step();self.assertIsNone(self.client.p)
    def test_terminal_partial_is_measured_not_claimed_full_fill(self):
        pending=dict(client_id='PARTIAL',position_id='123',path=REDUCE,stage=1,event_at=1,
                     body={'qty':'.4'},prepared_ms=int(self.clock()*1000))
        self.j.append('INTENT:PARTIAL','INTENT',pending)
        self.client.p['qty']='.8'
        self.client.trades['123'].append(dict(tradeId='PART',clientId='PARTIAL',symbol='BTCUSDT',qty='.2',fee='.01',realizedPNL='-.2'))
        original=self.client.get
        self.client.get=lambda path,params:dict(symbol='BTCUSDT',clientId='PARTIAL',status='CANCELED',reduceOnly=True,tradeQty='.2') if path==DETAIL else original(path,params)
        self.assertTrue(self.c.reconcile_pending())
        self.assertEqual(D(self.j.latest('RECONCILED')['filled_qty']),D('.2'))
        self.assertTrue(self.j.latest('RECONCILED')['terminal_partial'])
        self.assertFalse(self.client.mutations)
    def test_rejected_reduction_is_not_repeated_without_a_new_action_identity(self):
        self.client.p['liqPrice']='99';self.client.reject=True
        self.c.step();self.c.step();self.assertEqual(len(self.client.mutations),1)
    def test_timeout_restarts_do_not_duplicate_market_order(self):
        self.client.p['liqPrice']='99';self.client.timeout=True
        with self.assertRaises(ValueError):self.c.step()
        for _ in range(4):
            self.clock.value+=10
            rebuilt=Controller(self.client,Journal(self.j.path,clock=self.clock),clock=self.clock)
            rebuilt.step()
        self.assertEqual(len(self.client.mutations),1)
    def test_equity_and_liquidation_report_are_exchange_values(self):
        result=self.c.step()
        self.assertEqual(result['actual_liquidation'],'50')
        self.assertEqual(result['actual_equity'],'9999')
    def test_no_mutations_in_shadow(self):
        self.client.execution=False;self.client.p['liqPrice']='99'
        self.assertEqual(self.c.step()['status'],'SHADOW_PROPOSAL')
        self.assertFalse(self.client.mutations);self.assertIsNone(self.j.pending())
    def test_structure_failure_keeps_only_verified_budgeted_server_stop(self):
        self.c.structure=Mock(side_effect=ValueError('STALE'))
        self.assertEqual(self.c.step()['status'],'PROTECTED_STRUCTURE_DATA_DEGRADED')
        self.assertFalse(self.client.mutations)
        self.client.s=[];self.c.step();self.assertIsNone(self.client.p)
    def test_no_post_if_fsync_fails(self):
        self.c.step();self.context['broken_closes']=1
        with patch('guardian_capital_v2.journal.os.fsync',side_effect=OSError('full')):
            with self.assertRaises(ValueError):self.c.step()
        self.assertFalse(self.client.mutations)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.jsonl';self.j=Journal(self.path)
    def test_replay_and_dedupe(self):
        self.assertTrue(self.j.append('ONE','TEST',{'a':1}))
        self.assertFalse(self.j.append('ONE','TEST',{'a':2}))
        replay=Journal(self.path);self.assertEqual(replay.rows,self.j.rows)
    def test_truncated_line_never_repaired(self):
        self.j.append('ONE','TEST',{'a':1});self.path.write_bytes(self.path.read_bytes()[:-1])
        raw=self.path.read_bytes()
        with self.assertRaises(ValueError):Journal(self.path)
        self.assertEqual(self.path.read_bytes(),raw)
    def test_modified_or_reordered_history_fails(self):
        self.j.append('ONE','TEST',{'a':1});self.j.append('TWO','TEST',{'a':2})
        data=self.path.read_bytes();self.path.write_bytes(data.replace(b'"a":1',b'"a":9'))
        with self.assertRaises(ValueError):Journal(self.path)
        self.path.write_bytes(b'\n'.join(reversed(data.splitlines()))+b'\n')
        with self.assertRaises(ValueError):Journal(self.path)
    def test_write_uncertainty_latches(self):
        with patch('guardian_capital_v2.journal.os.fsync',side_effect=OSError('full')):
            with self.assertRaises(ValueError):self.j.append('ONE','TEST',{})
        with self.assertRaisesRegex(ValueError,'LATCHED'):self.j.append('TWO','TEST',{})


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.clock=Clock();self.http=Mock();self.j=Journal(Path(self.tmp.name)/'ledger',clock=self.clock)
        self.c=Client('FAKE_KEY','FAKE_SECRET',transport=self.http,clock=self.clock,execution=True,approval_hash=POLICY_HASH)
        self.p=dict(position(),_observed_ms=int(self.clock()*1000))
        self.body=dict(symbol='BTCUSDT',positionId='123',side='SELL',orderType='MARKET',qty='1',reduceOnly=True,clientId='TEST')
        self.http.request.return_value.status_code=200
        self.http.request.return_value.headers={'Date':datetime.fromtimestamp(self.clock(),timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}
        self.http.request.return_value.json.return_value={'code':0,'data':{'orderId':'500'}}
    def intent(self,path=REDUCE,body=None,prepared_ms=None):
        body=self.body if body is None else body
        self.j.append('INTENT:TEST','INTENT',dict(client_id='TEST',path=path,body=body,
            mark='100',position_id='123',prepared_ms=int(self.clock()*1000) if prepared_ms is None else prepared_ms))
    def send(self,path=REDUCE,body=None,owned=()):
        return self.c.mutate(path,self.body if body is None else body,journal=self.j,intent_id='INTENT:TEST',
                             policy_hash=POLICY_HASH,position=self.p,owned_order_ids=owned)
    def test_approved_close_only_one_post_no_redirects(self):
        self.intent();self.send()
        self.assertEqual(self.http.request.call_count,1)
        self.assertFalse(self.http.request.call_args.kwargs['allow_redirects'])
        with self.assertRaises(ValueError):self.send()
        self.assertEqual(self.http.request.call_count,1)
    def test_disabled_or_missing_approval_does_not_post(self):
        self.intent();self.c.execution=False
        with self.assertRaises(ValueError):self.send()
        self.c.execution=True;self.c.approval_hash='WRONG'
        with self.assertRaises(ValueError):self.send()
        self.http.request.assert_not_called()
    def test_no_direct_wire_bypass(self):
        with self.assertRaises(ValueError):self.c._wire('POST',REDUCE,body=self.body)
        self.http.request.assert_not_called()
    def test_open_increase_wrong_position_and_hedge_refused(self):
        for change in ({'reduceOnly':False},{'qty':'2'},{'side':'BUY'},{'positionId':'456'},{'tradeSide':'OPEN'}):
            with self.subTest(change=change):
                with tempfile.TemporaryDirectory() as directory:
                    self.j=Journal(Path(directory)/'ledger',clock=self.clock)
                    body=dict(self.body,**change);self.intent(body=body)
                    with self.assertRaises(ValueError):self.send(body=body)
        self.http.request.assert_not_called()
    def test_no_post_without_fsynced_intent_or_with_stale_preflight(self):
        with self.assertRaises(ValueError):self.send()
        self.intent(prepared_ms=int(self.clock()*1000)-6000)
        with self.assertRaises(ValueError):self.send()
        self.http.request.assert_not_called()
    def test_unowned_manual_sl_modification_refused(self):
        body=dict(orderId='MANUAL',slPrice='90',slStopType='MARK_PRICE',slOrderType='MARKET',slQty='1')
        self.intent(MODIFY_STOP,body)
        with self.assertRaises(ValueError):self.send(MODIFY_STOP,body)
        self.http.request.assert_not_called()
    def test_stop_must_cover_exact_quantity_mark_market(self):
        body=dict(symbol='BTCUSDT',positionId='123',slPrice='90',slStopType='LAST_PRICE',slOrderType='LIMIT',slQty='.5')
        self.intent(PLACE_STOP,body)
        with self.assertRaises(ValueError):self.send(PLACE_STOP,body)
        self.http.request.assert_not_called()
    def test_timeout_has_one_attempt_even_if_reinvoked(self):
        self.intent();self.http.request.side_effect=TimeoutError('secret must not escape')
        with self.assertRaisesRegex(ValueError,'CAPITAL_REQUEST_UNCERTAIN'):self.send()
        with self.assertRaises(ValueError):self.send()
        self.assertEqual(self.http.request.call_count,1)
    def test_string_api_total_is_supported_without_truncation(self):
        self.assertEqual(count('2'),2)
        for item in (True,2.1,'2.1',-1):
            with self.assertRaises(ValueError):count(item)
    def test_position_stop_create_is_quantity_dynamic_and_sl_only(self):
        body=dict(symbol='BTCUSDT',positionId='123',slPrice='90',slStopType='MARK_PRICE')
        self.intent(PLACE_POSITION_STOP,body);self.send(PLACE_POSITION_STOP,body)
        self.assertEqual(self.http.request.call_args.args[1],'https://fapi.bitunix.com'+PLACE_POSITION_STOP)
        self.assertNotIn('tpPrice',json.loads(self.http.request.call_args.kwargs['data']))
        self.assertNotIn('slQty',json.loads(self.http.request.call_args.kwargs['data']))
    def test_documented_nonpositive_liquidation_allows_a_protective_sl_post(self):
        self.p['liqPrice']='0'
        body=dict(symbol='BTCUSDT',positionId='123',slPrice='90',slStopType='MARK_PRICE')
        self.intent(PLACE_POSITION_STOP,body);self.send(PLACE_POSITION_STOP,body)
        self.assertEqual(self.http.request.call_count,1)
    def test_short_documented_no_liquidation_has_no_guessed_upper_bound(self):
        self.p.update(side='SHORT',liqPrice='-1')
        body=dict(symbol='BTCUSDT',positionId='123',slPrice='110',slStopType='MARK_PRICE')
        self.intent(PLACE_POSITION_STOP,body);self.send(PLACE_POSITION_STOP,body)
        self.assertEqual(self.http.request.call_count,1)
    def test_position_stop_modify_requires_owned_live_order_without_manual_tp(self):
        body=dict(symbol='BTCUSDT',positionId='123',slPrice='90',slStopType='MARK_PRICE')
        self.intent(MODIFY_POSITION_STOP,body)
        self.http.request.return_value.json.return_value={'code':0,'data':[dict(stop(),tpPrice='110')]}
        with self.assertRaises(ValueError):self.send(MODIFY_POSITION_STOP,body,owned={'900':dict(position_id='123',position_dynamic=True)})
        self.assertEqual([c.args[0] for c in self.http.request.call_args_list],['GET'])
    def test_arbitrary_paths_account_and_subaccounts_are_rejected(self):
        for path,params in ((POSITIONS,{'symbol':'BTCUSDT','includeSubAccounts':'true'}),
            (TPSL,{'symbol':'BTCUSDT','url':'https://evil.invalid'}),(ACCOUNT,{'marginCoin':'BTC'})):
            with self.assertRaises(ValueError):self.c.get(path,params)
        self.http.request.assert_not_called()
    def test_cycle_deadline_blocks_more_network_without_touching_guardian(self):
        self.c.begin_cycle(1);self.clock.value+=2
        with self.assertRaisesRegex(ValueError,'CAPITAL_CYCLE_TIME_BUDGET'):self.c.get(ACCOUNT,{'marginCoin':'USDT'})
        self.http.request.assert_not_called()
    def test_api_rejection_without_data_is_definitive_not_a_retry(self):
        self.intent();self.http.request.return_value.json.return_value={'code':100,'msg':'redacted'}
        with self.assertRaisesRegex(Rejected,'CAPITAL_API_REJECTED'):self.send()
        with self.assertRaises(ValueError):self.send()
        self.assertEqual(self.http.request.call_count,1)


class HostTests(unittest.TestCase):
    def test_disabled_has_no_network_storage_or_new_sender(self):
        g=SimpleNamespace(telegram=SimpleNamespace(send_owner=Mock()))
        with patch.dict('os.environ',{},clear=True),patch('guardian_capital_v2.host.Client') as c,patch('guardian_capital_v2.host.Journal') as j:
            before_guardian_cycle(g)
            self.assertIs(owner_reply(g),g.telegram.send_owner)
            c.assert_not_called();j.assert_not_called()
    def test_execution_requires_exact_hash_and_authorization(self):
        g=SimpleNamespace(telegram=SimpleNamespace(send=Mock()),config=Mock())
        with patch.dict('os.environ',{'GUARDIAN_CAPITAL_V2_ENABLED':'true','GUARDIAN_CAPITAL_V2_EXECUTION':'true'},clear=True),patch('guardian_capital_v2.host.Client') as c,patch('builtins.print'):
            before_guardian_cycle(g);c.assert_not_called()
    def test_logger_or_sender_failure_does_not_escape_into_guardian(self):
        g=SimpleNamespace(telegram=SimpleNamespace(send=Mock(side_effect=RuntimeError('offline'))))
        with patch.dict('os.environ',{'GUARDIAN_CAPITAL_V2_ENABLED':'true'},clear=True),patch('guardian_capital_v2.host.Client',side_effect=RuntimeError('unavailable')),patch('builtins.print',side_effect=OSError('stdout')):
            before_guardian_cycle(g)
    def test_existing_live_controller_is_disarmed_when_approval_changes(self):
        controller=SimpleNamespace(client=SimpleNamespace(execution=True))
        g=SimpleNamespace(_capital_v2=controller,telegram=SimpleNamespace(send=Mock()),config=SimpleNamespace(armed=lambda action:False))
        with patch.dict('os.environ',{'GUARDIAN_CAPITAL_V2_ENABLED':'true','GUARDIAN_CAPITAL_V2_EXECUTION':'true','GUARDIAN_CAPITAL_V2_POLICY_HASH':'WRONG'},clear=True),patch('builtins.print'):
            before_guardian_cycle(g)
        self.assertFalse(controller.client.execution)


class CapitalBoundaryTests(unittest.TestCase):
    def test_previous_guardian_source_restored_exactly_by_only_reviewed_hook(self):
        from capital_v2_safety import normalize_capital
        text=Path('trade_guardian.py').read_text(encoding='utf-8')
        self.assertEqual(hashlib.sha256(normalize_capital(text).encode()).hexdigest(),
                         'cb57a7e7f9ed12ac99f0bfeb107117ec79415e5902f40834c3ef88ecf02d2323')
        tree=ast.parse(text)
        guardian=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Guardian')
        self.assertNotIn('capital_v2',ast.unparse(guardian))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        source=ast.unparse(main)
        self.assertLess(source.index('Store('),source.index('before_guardian_cycle('))
        self.assertLess(source.index('before_guardian_cycle('),source.index('guardian.cycle('))
    def test_policy_hash_covers_parameters_and_all_protective_dependencies(self):
        from guardian_capital_v2.global_policy import approved_hash,PROPOSAL
        self.assertEqual(POLICY_HASH,approved_hash())
        with patch.dict(PROPOSAL,{'trade_loss_fraction':'.99'}):
            self.assertNotEqual(POLICY_HASH,approved_hash())
    def test_no_readiness_v8_market_data_mlrsi_paper_or_opening_integration(self):
        for path in ('bitman_manual/readiness.py','bitman_market_data_service.py','mlrsi_observer.py',
                     'mlrsi_math.py','trend_v8.py','live_auto.py','main.py','guardian_risk.py'):
            self.assertNotIn('guardian_capital_v2',Path(path).read_text(encoding='utf-8'),path)
        for path in Path('guardian_capital_v2').glob('*.py'):
            source=path.read_text(encoding='utf-8')
            for forbidden in ('TELEGRAM_BOT_TOKEN','getUpdates','V8_LIVE_EXECUTION','/cancel_orders',
                              '/change_leverage','/close_all_position','/flash_close_position'):
                self.assertNotIn(forbidden,source,str(path))


if __name__=='__main__':unittest.main()
