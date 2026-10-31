"""Fictitious unit fixtures: no production/account data, clients or network."""
import ast
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import unittest
from guardian_capital_v2.policy import (Policy,Snapshot,Stop,Evidence,Progress,
    Decision,decide,reconcile,close_only_draft,proposed_conservative_policy)


class CapitalV2Tests(unittest.TestCase):
    def setUp(self):
        self.now=100_000
        self.policy=Policy('TEST_POLICY','TEST_POSITION','LONG',D('1'),D('50'),D('.05'),
            D('.2'),D('.3'),1000,5000,10_000,'a'*64,True)
        self.stop=Stop('TEST_ORDER','TEST_POSITION',D('1'),D('90'),True,'MARK_PRICE','MARKET')
        self.snap=Snapshot('TEST_POSITION','LONG',D('1'),D('100'),D('80'),D('200'),D('20'),D('10'),self.now,self.stop)
        self.evidence=Evidence('EVENT_A',1,99_000,'a'*64)
        self.progress=Progress(last_verified_qty=D('1'))

    def decision(self,**changes):
        return decide(replace(self.snap,**changes),self.policy,self.progress,self.evidence,self.now)

    def test_no_policy_or_authorization_no_action(self):
        for policy in (None,replace(self.policy,owner_authorized=False)):
            self.assertEqual(decide(self.snap,policy,self.progress,self.evidence,self.now).status,'AWAITING_EXPLICIT_POLICY')

    def test_valid_thesis_holds_protected_residual(self):
        self.evidence=replace(self.evidence,level=0)
        self.assertEqual(self.decision().status,'KEEP_PROTECTED_RESIDUAL')

    def test_small_fluctuation_does_not_trim(self):
        self.evidence=replace(self.evidence,level=0)
        for mark in (D('99'),D('100'),D('101')):
            self.assertEqual(self.decision(mark=mark).qty,D('0'))

    def test_first_deterioration_uses_only_authorized_qty(self):
        d=self.decision()
        self.assertEqual((d.status,d.qty,d.stage),('PROPOSE_REDUCE',D('.2'),1))

    def test_second_requires_postfill_and_new_evidence(self):
        self.progress=Progress(1,None,99_100,D('.8'),('EVENT_A',))
        self.snap=replace(self.snap,stop=replace(self.stop,qty=D('.8')))
        old=self.decision(qty=D('.8'))
        self.assertEqual(old.status,'KEEP_PROTECTED_RESIDUAL')
        self.evidence=Evidence('EVENT_B',2,99_500,'a'*64)
        self.assertEqual(self.decision(qty=D('.8')).qty,D('.3'))

    def test_same_event_cannot_recut(self):
        self.progress=replace(self.progress,consumed_events=('EVENT_A',))
        self.assertEqual(self.decision().qty,D('0'))

    def test_money_cap_overrides_valid_thesis(self):
        self.evidence=replace(self.evidence,level=0)
        d=self.decision(total_loss_usdt=D('50'))
        self.assertEqual((d.status,d.qty),('PROPOSE_CLOSE_REMAINING',D('1')))

    def test_liquidation_safety_overrides_rebound(self):
        self.evidence=replace(self.evidence,level=0)
        self.assertEqual(self.decision(liquidation=D('96')).reason,'CAPITAL_OVERRIDES_STRUCTURE')

    def test_invalidation_closes_remaining_not_new_trade(self):
        self.evidence=replace(self.evidence,level=3)
        self.assertEqual(self.decision().status,'PROPOSE_CLOSE_REMAINING')

    def test_no_stop_never_labels_residual_protected(self):
        self.assertEqual(self.decision(stop=None).status,'PROTECTION_UNVERIFIED')

    def test_wrong_position_partial_limit_and_unknown_stops_fail(self):
        for stop in (replace(self.stop,position_id='OTHER'),replace(self.stop,qty=D('.5')),
                     replace(self.stop,order_type='LIMIT'),replace(self.stop,trigger='LAST_PRICE'),
                     replace(self.stop,active=False),replace(self.stop,price=D('0'))):
            self.assertEqual(self.decision(stop=stop).status,'PROTECTION_UNVERIFIED')

    def test_optional_fail_safe_requires_explicit_policy(self):
        self.policy=replace(self.policy,close_remaining_if_unprotected=True)
        self.assertEqual(self.decision(stop=None).reason,'AUTHORIZED_UNPROTECTED_FAILSAFE')

    def test_no_action_after_timeout_until_reconciliation(self):
        self.progress=replace(self.progress,pending_client_id='PENDING')
        self.assertEqual(self.decision(total_loss_usdt=D('100')).status,'RECONCILIATION_REQUIRED')

    def test_missing_loss_accounting_does_not_guess_total(self):
        self.assertEqual(self.decision(total_loss_usdt=None).status,'LOSS_ACCOUNTING_UNVERIFIED')

    def test_stale_and_future_snapshot_fail_closed(self):
        for timestamp in (self.now+1,self.now-5001):
            self.assertEqual(self.decision(observed_ms=timestamp).status,'DATA_UNAVAILABLE')

    def test_future_old_and_wrong_definition_evidence_ignored(self):
        for event in (replace(self.evidence,closed_at_ms=self.now+1),
                      replace(self.evidence,closed_at_ms=1000),
                      replace(self.evidence,definition_hash='b'*64)):
            self.evidence=event
            self.assertEqual(self.decision().qty,D('0'))

    def test_external_increase_or_reduction_requires_new_verified_coverage(self):
        for qty in (D('1.1'),D('.9')):
            self.assertEqual(self.decision(qty=qty).status,'PROTECTION_UNVERIFIED')
            self.assertEqual(self.policy.total_loss_limit_usdt,D('50'))

    def test_postfill_requires_actual_new_qty_not_model_liquidation(self):
        decision=self.decision()
        pending=replace(self.progress,pending_client_id='PENDING')
        after=replace(self.snap,qty=D('.8'),observed_ms=self.now+100,
                      equity=D('199'),margin=D('16'),liquidation=D('79'))
        actual=reconcile(pending,self.snap,after,D('.2'),decision,self.policy)
        self.assertEqual((actual.completed_stage,actual.last_verified_qty),(1,D('.8')))
        for invalid in (replace(after,qty=D('.7')),replace(after,source='MODEL'),
                        replace(after,observed_ms=self.snap.observed_ms)):
            with self.assertRaises(ValueError):
                reconcile(pending,self.snap,invalid,D('.2'),decision,self.policy)

    def test_partial_fill_keeps_pending(self):
        pending=replace(self.progress,pending_client_id='PENDING')
        with self.assertRaises(ValueError):
            reconcile(pending,self.snap,replace(self.snap,qty=D('.9'),observed_ms=self.now+1),D('.1'),self.decision(),self.policy)
        self.assertEqual(pending.pending_client_id,'PENDING')

    def test_full_exit_reconciles_flat(self):
        d=self.decision(total_loss_usdt=D('50'))
        after=replace(self.snap,qty=D('0'),liquidation=D('0'),margin=D('0'),observed_ms=self.now+100)
        done=reconcile(replace(self.progress,pending_client_id='PENDING'),self.snap,after,D('1'),d,self.policy)
        self.assertEqual(decide(after,self.policy,done,None,self.now+100).status,'EXPOSURE_CLOSED')

    def test_only_close_only_drafts_and_long_short_symmetry(self):
        for side,mark,liq,stop,order_side in (('LONG','100','80','90','SELL'),('SHORT','100','120','110','BUY')):
            p=replace(self.policy,side=side)
            s=replace(self.snap,side=side,mark=D(mark),liquidation=D(liq),stop=replace(self.stop,price=D(stop)))
            d=decide(s,p,self.progress,self.evidence,self.now)
            draft=close_only_draft(s,p,d,position_mode='ONE_WAY',quantity_step=D('.01'))
            self.assertTrue(draft['body']['reduceOnly'])
            self.assertEqual(draft['body']['side'],order_side)
            self.assertFalse(draft['executable'])
            self.assertEqual(draft['trade_authority'],'NONE')
            self.assertNotIn('tradeSide',draft['body'])
            self.assertEqual(draft,close_only_draft(s,p,d,position_mode='ONE_WAY',quantity_step=D('.01')))

    def test_hedge_ambiguous_mapping_unverified_quantity_and_unauthorized_refused(self):
        d=self.decision()
        for mode,qty,authorized in (('HEDGE',D('.2'),True),('ONE_WAY',D('2'),True),('ONE_WAY',D('.201'),True),('ONE_WAY',D('.2'),False)):
            with self.assertRaises(ValueError):
                close_only_draft(self.snap,replace(self.policy,owner_authorized=authorized),replace(d,qty=qty),
                                 position_mode=mode,quantity_step=D('.01'))

    def test_no_network_account_or_production_integration(self):
        tree=ast.parse(Path('guardian_capital_v2/policy.py').read_text(encoding='utf-8'))
        imports={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names)
        self.assertEqual(imports,{'dataclasses','decimal','hashlib'})
        for name in ('guardian_bitunix.py','guardian_risk.py','guardian_commands.py'):
            self.assertNotIn('guardian_capital_v2',Path(name).read_text(encoding='utf-8'))

    def test_conservative_template_proposes_not_authorizes(self):
        proposal=proposed_conservative_policy(policy_id='TEST',position_id='TEST_POSITION',side='LONG',
            qty=D('1'),reference_equity=D('200'),quantity_step=D('.01'),activated_ms=1000,structure_definition_hash='a'*64)
        self.assertEqual((proposal.first_trim_qty,proposal.second_trim_qty),(D('.33'),D('.33')))
        self.assertEqual(proposal.total_loss_limit_usdt,D('2'))
        self.assertEqual(proposal.minimum_liquidation_atr,D('2'))
        self.assertEqual(proposal.account_equity_floor,D('190'))
        self.assertFalse(proposal.owner_authorized)

    def test_near_liquidation_overrides_missing_loss_accounting(self):
        self.assertEqual(self.decision(liquidation=D('99'),total_loss_usdt=None).status,'PROPOSE_CLOSE_REMAINING')

    def test_two_atr_distance_and_equity_floor_override_structure(self):
        self.policy=replace(self.policy,minimum_liquidation_atr=D('2'),account_equity_floor=D('190'))
        self.assertEqual(self.decision(atr_1h=D('11')).status,'PROPOSE_CLOSE_REMAINING')
        self.assertEqual(self.decision(atr_1h=D('1'),equity=D('189')).status,'PROPOSE_CLOSE_REMAINING')

    def test_no_string_authorization(self):
        with self.assertRaises(ValueError):replace(self.policy,owner_authorized='true')


if __name__=='__main__':unittest.main()
