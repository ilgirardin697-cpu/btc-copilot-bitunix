import ast
from copy import deepcopy
from decimal import Decimal
import hashlib,json,subprocess,unittest
from pathlib import Path
from .report import build_report,partition_orders,Unverified

HERE=Path(__file__).resolve().parent

class ReadOnlyTests(unittest.TestCase):
    def setUp(self):self.f=json.loads((HERE/'fixtures.json').read_text())
    def report(self):return build_report(self.f['positions'],self.f['orders'],self.f['mark'],self.f['last'])
    def test_both_sides_by_position_id(self):
        r=self.report();self.assertEqual([p['id'] for p in r['positions']],['10001','10002']);self.assertEqual([p['side'] for p in r['positions']],['LONG','SHORT'])
    def test_zero_net_is_not_zero_risk(self):
        r=self.report();self.assertEqual(r['net_notional'],0);self.assertEqual(r['gross_notional'],Decimal('2440'));self.assertIsNone(r['account_equity'])
    def test_money_components_not_double_counted(self):
        r=self.report();self.assertEqual(r['realized_excluding_costs'],1);self.assertEqual(r['unrealized'],40);self.assertEqual(r['sum_reported_position_margin'],244)
    def test_costs_and_funding_remain_separate(self):
        r=self.report();self.assertEqual(r['fee_reported'],Decimal('1.1'));self.assertEqual(r['funding_reported'],0)
    def test_each_stop_bound_independently(self):
        r=self.report();self.assertTrue(r['all_sides_explicit_sl_registered']);self.assertTrue(all(p['tpsl']['full_market_sl_orders']==1 for p in r['positions']))
    def test_one_side_without_stop_not_hidden_by_other(self):
        self.f['orders']['10002']=[];r=self.report();self.assertFalse(r['all_sides_explicit_sl_registered']);self.assertEqual(r['positions'][1]['tpsl']['status'],'NO_REGISTERED_TPSL_RETURNED')
    def test_one_side_orders_unavailable(self):
        del self.f['orders']['10002'];r=self.report();self.assertEqual(r['positions'][1]['tpsl']['issues'],['ORDERS_UNAVAILABLE'])
    def test_cross_contamination_rejected(self):
        self.f['orders']['10001']=self.f['orders']['10002'];self.assertIn('ORDER_SCOPE_MISMATCH',self.report()['positions'][0]['tpsl']['issues'])
    def test_zero_qty_is_not_assumed_full_position(self):
        self.f['orders']['10001'][0]['slQty']='0';self.assertFalse(self.report()['all_sides_explicit_sl_registered'])
    def test_missing_qty_is_not_assumed_full_position(self):
        del self.f['orders']['10001'][0]['slQty'];self.assertFalse(self.report()['all_sides_explicit_sl_registered'])
    def test_partial_sl(self):
        self.f['orders']['10001'][0]['slQty']='0.01';self.assertEqual(self.report()['positions'][0]['tpsl']['status'],'PARTIAL_OR_SPLIT_COVERAGE_REQUIRES_REVIEW')
    def test_split_orders_not_summed_into_certified_coverage(self):
        o=self.f['orders']['10001'][0];o['slQty']='0.01';other=dict(o,id='20003');self.f['orders']['10001'].append(other);self.assertFalse(self.report()['all_sides_explicit_sl_registered'])
    def test_limit_order_not_certified_market_protection(self):
        self.f['orders']['10001'][0]['slOrderType']='LIMIT';self.assertFalse(self.report()['all_sides_explicit_sl_registered'])
    def test_unknown_trigger(self):
        self.f['orders']['10001'][0]['slStopType']='UNKNOWN';self.assertFalse(self.report()['all_sides_explicit_sl_registered'])
    def test_already_crossed_trigger(self):
        self.f['orders']['10001'][0]['slPrice']='62000';self.assertIn('SL_TRIGGER_ALREADY_PASSED',self.report()['positions'][0]['tpsl']['issues'])
    def test_sl_after_liquidation(self):
        self.f['orders']['10001'][0]['slPrice']='49000';self.assertIn('SL_BEYOND_LIQUIDATION_REFERENCE',self.report()['positions'][0]['tpsl']['issues'])
    def test_tp_only_is_not_stop(self):
        self.f['orders']['10001'][0]['slPrice']='0';self.assertEqual(self.report()['positions'][0]['tpsl']['status'],'NO_REGISTERED_SL_RETURNED')
    def test_duplicate_order_not_silently_summed(self):
        self.f['orders']['10001']*=2;self.assertFalse(self.report()['all_sides_explicit_sl_registered'])
    def test_positive_liquidation_2pct_reference_preserved(self):
        self.f['positions'][0]['liqPrice']='60000';self.assertEqual(self.report()['positions'][0]['liquidation_status'],'CRITICAL_2PCT')
    def test_nonpositive_liquidation_documented_not_missing(self):
        for liq in ('0','-1'):
            self.f['positions'][0]['liqPrice']=liq;p=self.report()['positions'][0];self.assertEqual(p['liquidation_status'],'DOCUMENTED_NONPOSITIVE_NO_ESTIMATE_CURRENTLY');self.assertIsNone(p['liquidation_distance_fraction'])
    def test_missing_liquidation_is_unverified(self):
        del self.f['positions'][0]['liqPrice']
        with self.assertRaises(Unverified):self.report()
    def test_invalid_numbers_fail_closed(self):
        for value in ('NaN','Infinity','abc',None,True):
            self.f['positions'][0]['qty']=value
            with self.assertRaises(Unverified):self.report()
    def test_duplicate_position_id_fails_without_picking_a_side(self):
        self.f['positions'][1]['positionId']='10001'
        with self.assertRaisesRegex(Unverified,'DUPLICATE_POSITION_ID'):self.report()
    def test_mixed_account_scope_fails(self):
        self.f['positions'][1]['subAccountId']=2
        with self.assertRaisesRegex(Unverified,'MIXED_ACCOUNT_SCOPE'):self.report()
    def test_input_order_does_not_select_a_side(self):
        r=self.report();self.f['positions'].reverse();self.assertEqual(r,self.report())
    def test_input_not_mutated(self):
        before=deepcopy(self.f);self.report();self.assertEqual(self.f,before)
    def test_no_authority_even_when_full_stops_reported(self):
        r=self.report();self.assertEqual(r['trade_authority'],'NONE');self.assertFalse(r['protection_decision'])
    def test_flat_not_protected_position(self):
        self.f['positions']=[];r=self.report();self.assertEqual(r['gross_notional'],0);self.assertFalse(r['all_sides_explicit_sl_registered'])
    def test_wider_server_reply_partitioned_by_exact_id(self):
        rows=sum(self.f['orders'].values(),[]);self.assertEqual(partition_orders(rows,['10001','10002'],True),self.f['orders'])
    def test_partition_incomplete_denied(self):
        with self.assertRaisesRegex(Unverified,'PAGINATION'):partition_orders([],['10001'],False)
    def test_partition_orphan_order_not_silently_discarded(self):
        with self.assertRaisesRegex(Unverified,'UNASSIGNED'):partition_orders(self.f['orders']['10002'],['10001'],True)
    def test_partition_duplicate_denied(self):
        with self.assertRaisesRegex(Unverified,'DUPLICATE'):partition_orders(self.f['orders']['10001']*2,['10001'],True)
    def test_cross_liquidation_direction_not_treated_as_certified_account_emergency(self):
        self.f['positions'][1]['liqPrice']='50000';r=self.report();p=r['positions'][1]
        self.assertEqual(p['liquidation_status'],'CROSS_HEDGE_DIRECTIONAL_LIQUIDATION_UNVERIFIED');self.assertFalse(r['protection_decision'])
        self.assertEqual(p['tpsl']['status'],'REGISTERED_EXPLICIT_FULL_MARKET_SL');self.assertIn('LIQUIDATION_DIRECTION_UNVERIFIED',p['tpsl']['risk_notes'])
    def test_no_network_or_execution_dependencies(self):
        tree=ast.parse((HERE/'report.py').read_text())
        imports=[n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertEqual(imports,['decimal']);self.assertFalse(any(isinstance(n,ast.Import) for n in ast.walk(tree)))
    def test_production_has_no_research_dependency(self):
        root=HERE.parents[1]
        for p in root.glob('*.py'):
            for n in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
                if isinstance(n,ast.ImportFrom):self.assertNotIn('guardian_hedge_readonly',n.module or '',str(p))
                elif isinstance(n,ast.Import):self.assertFalse(any('guardian_hedge_readonly' in a.name for a in n.names),str(p))

if __name__=='__main__':unittest.main()
