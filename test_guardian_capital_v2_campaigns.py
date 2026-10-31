"""Protection regressions only. Fictitious accounts and clients; no real requests."""
import copy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from test_guardian_capital_v2_runtime import FakeClient,Clock,position,stop
from guardian_capital_v2.accounting import projected_net,critical_liquidation,stop_interval,number,timestamp_ms
from guardian_capital_v2.controller import Controller
from guardian_capital_v2.journal import Journal
from guardian_capital_v2.client import ACCOUNT,REDUCE,PLACE_POSITION_STOP,HISTORY_POSITIONS


class AccountingTests(unittest.TestCase):
    def test_profitable_long_stop_preserves_the_signed_profit(self):
        self.assertEqual(projected_net('-.054','LONG','.9','100','110','.0011'),D('8.83710'))

    def test_profitable_short_stop_preserves_the_signed_profit(self):
        self.assertEqual(projected_net('-.054','SHORT','.9','100','90','.0011'),D('8.85690'))

    def test_realized_loss_fees_and_funding_are_already_settled_once(self):
        # -3 gross, -1 fees, -.5 funding; remainder loses 4 plus .088 reserved close.
        self.assertEqual(projected_net('-4.5','LONG','.5','96','88','.002'),D('-8.588'))

    def test_nonpositive_liquidation_is_not_a_critical_distance(self):
        for side in ('LONG','SHORT'):
            for liq in ('0','-1','-100'):
                self.assertFalse(critical_liquidation(side,'100',liq,'.02'))
                self.assertTrue(stop_interval(side,'100',liq,'90' if side=='LONG' else '110'))

    def test_missing_and_incoherent_liquidation_are_not_zero(self):
        for value in (None,True,False,'','NaN','Infinity',{},[]):
            with self.subTest(value=value),self.assertRaises((ValueError,ArithmeticError)):
                number(value)

    def test_positive_two_percent_boundary_remains_exact(self):
        for side,critical,safe in (('LONG','98','97.9999'),('SHORT','102','102.0001')):
            self.assertTrue(critical_liquidation(side,'100',critical,'.02'))
            self.assertFalse(critical_liquidation(side,'100',safe,'.02'))

    def test_actual_api_integer_and_ascii_string_timestamps_are_equivalent(self):
        self.assertEqual(timestamp_ms('1800000000000'),timestamp_ms(1800000000000))
        for invalid in (None,True,1800000000000.0,'1800000000000.0','not-a-time','-1','١٢٣'):
            with self.subTest(value=invalid),self.assertRaises(ValueError):timestamp_ms(invalid)


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.jsonl';self.clock=Clock()
        self.client=FakeClient(self.clock);self.j=Journal(self.path,clock=self.clock)
        self.c=Controller(self.client,self.j,clock=self.clock)
        self.context=dict(atr=D('1'),stop=D('90'),broken_closes=0,invalidated=False,
                          closed_at=int(self.clock()*1000)-1,frozen={'first':'95','final':'90'})
        self.c.structure=lambda p,mark:dict(self.context)
        output=patch('builtins.print');output.start();self.addCleanup(output.stop)

    def allocations(self):return [r['payload'] for r in self.j.rows if r['kind']=='CAMPAIGN_ALLOCATED']

    def reopen_controller(self):
        self.j=Journal(self.path,clock=self.clock);self.c=Controller(self.client,self.j,clock=self.clock)
        self.c.structure=lambda p,mark:dict(self.context)

    def new_manual(self,pid,fee='1',funding='-1'):
        self.clock.value+=10
        self.client.p=position(pid);self.client.p.update(fee=str(-D(fee)),funding=funding)
        self.client.s=[stop(pid=pid)]
        self.client.trades[pid]=[dict(tradeId='OPEN'+pid,symbol='BTCUSDT',qty='1',fee=fee,realizedPNL='0',
                                      clientId='manual',side='BUY',ctime=int(self.clock()*1000))]
        self.client.wallet-=D(fee)-D(funding)

    def close(self):
        self.context['invalidated']=True;self.c.step();self.context['invalidated']=False
        self.assertIsNone(self.client.p)

    def test_floating_profit_and_profitable_stop_do_not_trigger_resize(self):
        self.c.step()
        self.client.mark='125';self.client.p['unrealizedPNL']='24'
        self.client.s[0]['slPrice']='110'
        result=self.c.step()
        self.assertEqual(result['status'],'RESIDUAL_PROTECTED')
        self.assertGreater(D(result['projected_net_at_stop']),D('0'))
        self.assertFalse(self.client.mutations)

    def test_short_floating_profit_and_profitable_stop_do_not_trigger_resize(self):
        self.client.p=position(side='SHORT');self.client.trades['123'][0]['side']='SELL'
        self.client.s=[dict(stop(),slPrice='105')];self.context['stop']=D('110')
        self.c.step();self.client.mark='75';self.client.p['unrealizedPNL']='24';self.client.s[0]['slPrice']='90'
        result=self.c.step()
        self.assertEqual(result['status'],'RESIDUAL_PROTECTED');self.assertFalse(self.client.mutations)

    def test_sized_position_normal_fluctuations_keep_same_risk_at_stop(self):
        self.client.p=position(qty='.0011');self.client.p.update(avgOpenPrice='77400',unrealizedPNL='0',funding='0',fee='-.051084',liqPrice='74000',margin='3.4056')
        self.client.mark='77400';self.client.wallet=D('120')
        self.client.trades['123'][0].update(qty='.0011',fee='.051084')
        self.client.s=[dict(stop(qty='.0011'),slPrice='76500')]
        self.context.update(atr=D('400'),stop=D('76500'))
        values=[]
        for mark in ('77400','77200','76800','76510'):
            self.client.mark=mark;self.client.p['unrealizedPNL']=str((D(mark)-D('77400'))*D('.0011'))
            result=self.c.step();self.assertEqual(result['status'],'RESIDUAL_PROTECTED')
            values.append(result['projected_net_at_stop'])
        self.assertEqual(len(set(values)),1);self.assertFalse(self.client.mutations)

    def test_closed_operation_gets_new_individual_budget_automatically(self):
        self.c.step();first=self.allocations()[0];baseline=copy.deepcopy(self.j.latest('BASELINE'))
        self.close();self.new_manual('456')
        self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')
        second=self.allocations()[1]
        self.assertNotEqual(first['campaign_id'],second['campaign_id'])
        self.assertEqual(second['position_id'],'456')
        self.assertEqual(self.j.latest('BASELINE'),baseline)
        self.assertTrue(self.c.book.closed('123'))
        self.assertLess(D(self.c.book.accounting('123')['net']),D('0'))

    def test_new_position_without_intermediate_flat_poll_reconciles_old_first(self):
        self.c.step();self.close();self.new_manual('456')
        self.c.step()
        close_index=next(i for i,r in enumerate(self.j.rows) if r['kind']=='CAMPAIGN_CLOSE')
        new_index=next(i for i,r in enumerate(self.j.rows) if r['kind']=='CAMPAIGN_ALLOCATED' and r['payload']['position_id']=='456')
        self.assertLess(close_index,new_index)

    def test_manual_additions_cannot_create_another_campaign_or_raise_budget(self):
        self.c.step();first=copy.deepcopy(self.allocations())
        self.client.manual_qty('2','100.5');self.c.step();self.c.step()
        self.assertEqual(self.allocations(),first)
        self.assertEqual(len(self.c.book.observed()),1)

    def test_restart_and_repeat_cannot_allocate_twice(self):
        self.c.step();count=len(self.j.rows)
        for _ in range(5):self.reopen_controller();self.c.step()
        self.assertEqual(len(self.allocations()),1);self.assertEqual(len(self.j.rows),count)

    def test_reboot_between_close_and_new_operation_preserves_global_reference(self):
        self.c.step();baseline=copy.deepcopy(self.j.latest('BASELINE'));self.close()
        self.reopen_controller();self.c.step();self.new_manual('456');self.c.step()
        self.assertEqual(len(self.allocations()),2);self.assertEqual(self.j.latest('BASELINE'),baseline)

    def test_no_allocation_until_native_stop_is_verified(self):
        self.client.s=[];self.c.step()
        self.assertFalse(self.allocations())
        self.assertEqual(self.client.mutations[0][0],PLACE_POSITION_STOP)
        self.c.step();self.assertEqual(len(self.allocations()),1)

    def test_bad_stop_and_api_error_cannot_allocate(self):
        self.client.s=[];self.client.bad_stop=True
        self.c.step();self.assertFalse(self.allocations())
        self.clock.value+=31;self.c.step();self.assertFalse(self.allocations())
        self.assertIsNone(self.client.p)

    def test_missing_closed_history_blocks_assignment_and_keeps_old_records(self):
        self.c.step();self.close();before=copy.deepcopy(self.j.rows)
        self.new_manual('456');self.client.closed.clear()
        self.c.step();self.assertEqual(len(self.allocations()),1)
        self.assertEqual(self.j.rows[:len(before)],before)

    def test_global_floor_blocks_even_a_new_small_manual_operation(self):
        self.c.step();self.close()
        # Verified realized loss on the old operation, not a synthetic counter reset.
        trade=self.client.trades['123'][-1];trade['realizedPNL']=str(D(trade['realizedPNL'])-D('600'))
        self.client.closed['123']['realizedPNL']='-600';self.client.wallet-=D('600')
        self.new_manual('456')
        self.c.step();self.assertIsNone(self.client.p);self.assertEqual(len(self.allocations()),1)
        self.assertEqual(self.c.step()['status'],'GLOBAL_RISK_BLOCKED')

    def test_deposit_does_not_erase_global_loss_or_unblock_new_assignments(self):
        self.c.step();self.close()
        trade=self.client.trades['123'][-1];trade['realizedPNL']=str(D(trade['realizedPNL'])-D('600'))
        self.client.closed['123']['realizedPNL']='-600';self.client.wallet+=D('100000')
        self.new_manual('456');self.c.step()
        self.assertIsNone(self.client.p);self.assertEqual(len(self.allocations()),1)
        self.assertEqual(self.j.latest('BASELINE')['reference_equity'],'9999')

    def test_deposit_cannot_raise_next_campaign_reference_equity(self):
        self.c.step();first_ref=D(self.allocations()[0]['loss_limit']);self.close()
        self.client.wallet+=D('100000');self.new_manual('456');result=self.c.step()
        self.assertEqual(result['status'],'RESIDUAL_PROTECTED')
        self.assertLess(D(self.allocations()[1]['loss_limit']),first_ref)

    def test_late_fee_adjustment_is_appended_and_charged_exactly_once(self):
        self.c.step();self.close();self.c.step();before=copy.deepcopy(self.j.rows)
        self.client.trades['123'][-1]['fee']='3'
        self.client.closed['123']['fee']='-4';self.client.wallet-=D('2.94')
        self.c.step();net=self.c.book.accounting('123')['net'];n=len(self.j.rows)
        self.reopen_controller();self.c.step()
        self.assertEqual(self.c.book.accounting('123')['net'],net)
        self.assertEqual(len(self.j.rows),n);self.assertEqual(self.j.rows[:len(before)],before)
        self.assertEqual(sum(r['kind']=='CAMPAIGN_ADJUSTMENT' for r in self.j.rows),1)

    def test_active_late_fee_is_not_subtracted_twice_from_global_equity(self):
        self.c.step();baseline=copy.deepcopy(self.j.latest('BASELINE'))
        self.client.trades['123'][0]['fee']='2';self.client.p['fee']='-2';self.client.wallet-=D('1')
        result=self.c.step()
        self.assertEqual(D(result['global_protected_equity']),D('9998'))
        self.assertEqual(self.c.total_loss(self.client.p),D('4'))
        count=len(self.j.rows);self.c.step();self.assertEqual(len(self.j.rows),count)
        self.assertEqual(self.j.latest('BASELINE'),baseline)

    def test_late_summary_fee_without_matching_fills_cannot_allocate(self):
        self.c.step();self.close();self.client.closed['123']['fee']='-100'
        self.new_manual('456');self.c.step()
        self.assertEqual(len(self.allocations()),1)

    def test_starting_idle_then_manual_entry_allocates_without_a_request(self):
        self.client.p=None;self.client.s=[]
        self.assertEqual(self.c.step()['status'],'NO_OPEN_BTCUSDT_POSITION')
        self.assertEqual(self.j.latest('BASELINE')['reference_equity'],'10000')
        self.new_manual('456');self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')
        self.assertEqual(len(self.allocations()),1)

    def test_late_funding_can_reduce_current_campaign_global_room(self):
        self.c.step();self.close();self.c.step();self.new_manual('456');self.c.step()
        self.client.closed['123']['funding']='-601';self.client.wallet-=D('600')
        self.c.step();self.assertIsNone(self.client.p)
        self.assertEqual(len(self.allocations()),2)

    def test_profitable_stop_can_preserve_global_floor_without_forcing_exit(self):
        self.c.step();self.close();self.new_manual('456');self.c.step()
        self.client.closed['123']['funding']='-511';self.client.wallet-=D('510')
        self.client.mark='125';self.client.p['unrealizedPNL']='24';self.client.s[0]['slPrice']='120'
        mutations=len(self.client.mutations);result=self.c.step()
        self.assertEqual(result['status'],'RESIDUAL_PROTECTED')
        self.assertLess(D(result['effective_loss_ceiling']),D('0'))
        self.assertGreater(D(result['projected_net_at_stop']),D('0'))
        self.assertEqual(len(self.client.mutations),mutations)

    def test_correction_of_verified_costs_can_restore_global_capacity(self):
        self.c.step();self.close()
        self.client.closed['123']['funding']='-601';self.client.wallet-=D('600')
        self.assertEqual(self.c.step()['status'],'GLOBAL_RISK_BLOCKED')
        self.client.closed['123']['funding']='-1';self.client.wallet+=D('600')
        self.assertEqual(self.c.step()['status'],'NO_OPEN_BTCUSDT_POSITION')
        self.new_manual('456');self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')

    def test_zero_liquidation_does_not_disable_monetary_emergency(self):
        self.c.step();self.client.p.update(liqPrice='0',unrealizedPNL='-200')
        self.c.step();self.assertIsNone(self.client.p)

    def test_short_zero_liquidation_accepts_a_verified_stop(self):
        self.client.p=position(side='SHORT');self.client.p['liqPrice']='0'
        self.client.trades['123'][0]['side']='SELL';self.client.s=[dict(stop(),slPrice='105')];self.context['stop']=D('110')
        self.assertEqual(self.c.step()['status'],'RESIDUAL_PROTECTED')
        self.assertFalse(self.client.mutations)

    def test_missing_liquidation_cannot_start_a_campaign(self):
        self.client.p['liqPrice']=None
        with self.assertRaises((ValueError,ArithmeticError)):self.c.step()
        self.assertFalse(self.allocations());self.assertFalse(self.client.mutations)

    def test_global_limit_still_precedes_structural_pattern_wait(self):
        self.c.step();self.client.wallet-=D('600');self.c.structure=Mock(side_effect=AssertionError('NO_WAIT'))
        self.c.step();self.assertIsNone(self.client.p)

    def test_history_api_error_does_not_allocate_a_fresh_campaign(self):
        self.c.step();self.close();self.new_manual('456')
        original=self.client.pages
        self.client.pages=lambda path,*args: (_ for _ in ()).throw(ValueError('API_UNAVAILABLE')) if path==HISTORY_POSITIONS else original(path,*args)
        self.c.step()
        self.assertEqual(len(self.allocations()),1)
        self.assertEqual(self.j.latest('BASELINE')['reference_equity'],'9999')

    def test_partial_old_close_evidence_cannot_fund_new_risk(self):
        self.c.step();self.close();self.new_manual('456')
        self.client.trades['123'][-1]['qty']='.5'
        self.c.step();self.assertEqual(len(self.allocations()),1)
        self.assertFalse(self.c.book.closed('123'))

    def test_critical_positive_liquidation_does_not_wait_for_accounting(self):
        self.client.p['liqPrice']='99';self.c.sync_accounting=Mock(side_effect=AssertionError('NO_WAIT'))
        self.c.step();self.assertIsNone(self.client.p)

    def test_initial_critical_close_does_not_double_count_old_unrealized_loss(self):
        self.client.p['liqPrice']='99';self.c.step();self.c.step()
        self.assertIsNotNone(self.j.latest('GLOBAL_ANCHOR'))
        account,equity=self.c.account();state=self.c.book.global_state(account,equity)
        self.assertEqual(state['effective_equity'],equity)

    def test_restart_after_emergency_before_anchor_reconciliation(self):
        self.client.p['liqPrice']='99';self.c.step()
        self.reopen_controller();self.c.step();count=len(self.j.rows)
        self.assertEqual(sum(r['kind']=='GLOBAL_ANCHOR' for r in self.j.rows),1)
        self.reopen_controller();self.c.step();self.assertEqual(len(self.j.rows),count)

    def test_emergency_anchor_accepts_real_api_numeric_string_timestamps(self):
        self.client.p['liqPrice']='99'
        self.client.trades['123'][0]['ctime']=str(self.client.trades['123'][0]['ctime'])
        self.c.step()
        for trade in self.client.trades['123']:trade['ctime']=str(trade['ctime'])
        self.assertEqual(self.c.step()['status'],'NO_OPEN_BTCUSDT_POSITION')
        self.assertIsNotNone(self.j.latest('GLOBAL_ANCHOR'))

    def test_late_opening_fee_after_initial_emergency_does_not_rebase_reference(self):
        self.client.p['liqPrice']='99';self.c.step()
        self.client.trades['123'][0]['fee']='3'
        self.client.closed['123']['fee']='-3.06';self.client.wallet-=D('2')
        result=self.c.step()
        self.assertEqual(result['status'],'NO_OPEN_BTCUSDT_POSITION')
        self.assertEqual(self.j.latest('BASELINE')['reference_equity'],'9999')
        account,equity=self.c.account()
        self.assertEqual(self.c.book.global_state(account,equity)['effective_equity'],equity)

    def test_failed_initial_reference_is_not_reset_by_a_later_deposit(self):
        self.client.p['liqPrice']='99';self.c.account=Mock(side_effect=ValueError('API_UNAVAILABLE'))
        with self.assertRaises(ValueError):self.c.step()  # POST occurred only on the fake client; reconciliation cannot finish.
        self.reopen_controller();self.c.step()
        self.client.wallet+=D('100000');self.new_manual('456');self.c.step()
        self.assertIsNone(self.client.p);self.assertFalse(self.allocations())
        self.assertIsNone(self.j.latest('BASELINE'))

    def test_restart_after_allocation_fsync_uncertainty_cannot_allocate_again(self):
        sync=self.j.append
        def uncertain(identifier,kind,payload):
            result=sync(identifier,kind,payload)
            if kind=='CAMPAIGN_ALLOCATED':raise ValueError('FSYNC_RESULT_UNKNOWN')
            return result
        with patch.object(self.j,'append',side_effect=uncertain):
            with self.assertRaises(ValueError):self.c.step()
        self.reopen_controller();self.c.step();self.assertEqual(len(self.allocations()),1)

    def test_new_campaign_cannot_reopen_a_closed_exchange_id(self):
        self.c.step();self.close();self.c.step();self.new_manual('123')
        with self.assertRaisesRegex(ValueError,'POSITION_ID_REUSE'):self.c.step()
        self.assertEqual(len(self.allocations()),1)

    def test_fsync_failure_cannot_grant_an_allocation(self):
        with patch('guardian_capital_v2.journal.os.fsync',side_effect=OSError('disk')):
            with self.assertRaises(ValueError):self.c.step()
        self.assertFalse(self.client.mutations);self.assertFalse(self.allocations())


if __name__=='__main__':unittest.main()
