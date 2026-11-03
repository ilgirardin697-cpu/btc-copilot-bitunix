"""Separate 40x stress gate. Missing verified data never becomes zero liquidations."""
from decimal import Decimal as D
import hashlib
import json
from .data import HERE


def budget(equity):
    e=D(str(equity))
    if not e.is_finite() or e<=0:raise ValueError('NO_REMAINING_EQUITY')
    return dict(equity=e,initial_margin=e*D('.5'),notional=e*D('.5')*D(40),leverage=D(40))


def linear_solvency_threshold(entry,quantity,collateral,side,maintenance_rate,deduction):
    """Algebraic margin-balance=maintenance equality, NOT complete exchange model.

    Does not supply a tier, funding ledger, execution/clearance fees or mark path.
    This function is tested with synthetic inputs only; never historical evidence.
    """
    e,q,c,m,k=map(lambda x:D(str(x)),(entry,quantity,collateral,maintenance_rate,deduction))
    if e<=0 or q<=0 or c<=0 or not 0<=m<1 or k<0 or side not in ('LONG','SHORT'):
        raise ValueError('INVALID_SYNTHETIC_MARGIN_INPUT')
    d=D(1 if side=='LONG' else -1)
    return (d*q*e-c-k)/(q*(d-m))


def require_verified_inputs(checks):
    s=json.loads((HERE/'stress_specification.json').read_text(encoding='utf-8'))
    missing=[name for name in s['required_before_any_historical_liquidation_result'] if checks.get(name) is not True]
    if missing:raise ValueError('OWNER_C_NOT_EVALUABLE_MISSING_VERIFIED_INPUTS')
    return True


def result():
    path=HERE/'stress_specification.json';s=json.loads(path.read_text(encoding='utf-8'))
    sources=[
        dict(url='https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account',
             fact='LEVERAGE_BRACKETS_USER_DATA_SIGNED_CURRENT_USER_BRACKETS_NOT_EFFECTIVE_DATED_HISTORICAL_TABLE'),
        dict(url='https://www.binance.com/en-KZ/support/faq/detail/360033525271',
             fact='LIQUIDATION_TRIGGER_USES_MARK_PRICE_MARGIN_BALANCE_AND_MAINTENANCE_NOT_SPOT_LAST_PRICE'),
        dict(url='https://www.binance.com/en/support/announcement/detail/f55d25695ca8453ab4c132c1fd4dc36a',
             fact='OFFICIAL_MARGIN_TIERS_CAN_CHANGE_2021_NOTICE_NOT_EVIDENCE_FOR_ALL_2025_2026_DATES')]
    ladder=[dict(hypothetical_half_equity_losses=k,equity=D(10000)*D('.5')**k,
                 remaining_fraction=D('.5')**k,
                 role='PURE_HALF_LOSS_ALGEBRA_NO_FEES_NOT_A_HISTORICAL_LIQUIDATION_RESULT') for k in (0,1,2,3,5,10)]
    return dict(name=s['name'],status='BLOCKED_NOT_EVALUABLE',classification='INCONCLUSIVE',
        protocol=s,protocol_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),official_sources=sources,
        blocking_reason='NO_VERIFIED_EFFECTIVE_DATED_BTCUSDT_MAINTENANCE_TIERS_CLEARANCE_RULES_FOR_ENTIRE_WINDOW',
        no_credentials_requested_or_used=True,no_private_account_api_called=True,
        mark_trade_funding_history_status='OFFICIAL_PUBLIC_SERIES_EXIST_BUT_NOT_ACQUIRED_AFTER_TIER_GATE_FAILED_NOT_REPLACED_BY_SPOT',
        required_missing_inputs=s['required_before_any_historical_liquidation_result'],
        modes={m:dict(tp_trades=None,liquidations=None,net_pnl=None,max_drawdown=None,
                       probability_of_ruin=None,reason='MISSING_VERIFIED_MODEL_AND_DATA') for m in s['modes']},
        initial_budget=budget(10000),equity_change_for_one_percent_adverse_move_before_costs='-20% OF EQUITY',
        gross_bankruptcy_distance_ignoring_maintenance_and_costs=dict(isolated='2.5%',cross_single_position='5%',
            warning='NOT_LIQUIDATION_PRICES_MAINTENANCE_AND_COSTS_TRIGGER_EARLIER_OR_CHANGE_THRESHOLD'),
        hypothetical_loss_ladder=ladder,rr_filter_applied=False,stop_loss_added=False,
        equity_reset_or_external_capital=False,trade_authority='NONE')
