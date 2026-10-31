"""Proposed global controls. Hash approval is required separately from deployment."""
import hashlib
import json

PROPOSAL={
    'version':'GUARDIAN_CAPITAL_PROTECTION_V2_PROPOSAL_2',
    'symbol':'BTCUSDT','position_mode':'ONE_WAY','margin_coin':'USDT',
    'trade_loss_fraction':'0.01','equity_drawdown_fraction':'0.05',
    'liquidation_distance_fraction':'0.02','liquidation_distance_atr':'2',
    'structural_buffer_atr':'0.25','structural_timeframe':'1h',
    'pivot_left':2,'pivot_right':2,'first_confirmed_closes':1,'second_confirmed_closes':2,
    'tranche_denominator':3,'assumed_taker_fee':'0.0006','assumed_slippage':'0.0005',
    'cycle_time_budget_seconds':8,'native_stop':'POSITION_DYNAMIC_MARKET_MARK_PRICE',
    'excess_structural_risk':'REDUCE_SIZE_NOT_TIGHTEN_STRUCTURE',
    'snapshot_max_age_ms':5000,'unprotected_fail_safe':'CLOSE_REMAINING',
    'manual_additions':'ADOPT_WITHOUT_RESETTING_BUDGET',
    'manual_order_mutations':False,'opening_orders':False,'automatic_averaging':False,
    'campaign_admission':'AUTOMATIC_MANUAL_POSITION_PROTECTED_WITH_GLOBAL_CAPACITY',
    'global_reference':'PERSISTENT_PROTECTED_WALLET_NO_CASH_INFLOW_REBASE',
    'risk_valuation':'SIGNED_NET_AT_STOP',
    'nonpositive_liquidation':'DOCUMENTED_NO_LIQUIDATION_PRICE',
}
def approved_hash():
    # Approval binds both parameters and implementation; changing code invalidates it.
    from pathlib import Path
    root=Path(__file__).parent
    files=('client.py','controller.py','journal.py','host.py','global_policy.py','accounting.py','campaigns.py','policy.py',
           '../guardian_signals.py','../guardian_risk.py','../guardian_bitunix.py')
    sources={name:hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in files}
    return hashlib.sha256(json.dumps(dict(parameters=PROPOSAL,sources=sources),sort_keys=True,separators=(',',':')).encode()).hexdigest()

POLICY_HASH=approved_hash()
APPROVAL_PHRASE='OWNER_APPROVED_CAPITAL_PROTECTION_ONLY_V2'
