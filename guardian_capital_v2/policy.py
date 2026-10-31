"""Explicit position-bound reduction proposals. No client, network or order sender."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
import hashlib

D = Decimal
ZERO = D('0')


def positive(value):
    return isinstance(value, D) and value.is_finite() and value > ZERO


@dataclass(frozen=True)
class Stop:
    order_id: str
    position_id: str
    qty: D
    price: D
    active: bool
    trigger: str
    order_type: str

    def covers(self, snapshot):
        return bool(self.order_id and self.position_id==snapshot.position_id
                    and self.active and positive(self.qty) and positive(self.price)
                    and self.qty == snapshot.qty and self.trigger == 'MARK_PRICE'
                    and self.order_type == 'MARKET' and (
                        snapshot.liquidation < self.price < snapshot.mark if snapshot.side == 'LONG'
                        else snapshot.mark < self.price < snapshot.liquidation))


@dataclass(frozen=True)
class Snapshot:
    position_id: str
    side: str
    qty: D
    mark: D
    liquidation: D
    equity: D
    margin: D
    total_loss_usdt: D | None  # Canonical cumulative loss INCLUDING costs, once.
    observed_ms: int
    stop: Stop | None = None
    source: str = 'BITUNIX_GET'
    atr_1h: D | None = None

    def fresh(self, now_ms, max_age_ms):
        return (self.source == 'BITUNIX_GET' and self.side in ('LONG', 'SHORT')
                and isinstance(self.qty, D) and self.qty.is_finite() and self.qty >= ZERO
                and positive(self.mark) and (positive(self.liquidation) if self.qty>ZERO else self.liquidation==ZERO)
                and isinstance(self.equity, D) and self.equity.is_finite()
                and isinstance(self.margin, D) and self.margin.is_finite() and self.margin >= ZERO
                and type(self.observed_ms) is int and 0 <= now_ms-self.observed_ms <= max_age_ms)

    def protected(self):
        return self.qty == ZERO or bool(self.stop and self.stop.covers(self))


@dataclass(frozen=True)
class Policy:
    policy_id: str
    position_id: str
    side: str
    initial_qty: D
    total_loss_limit_usdt: D
    minimum_liquidation_distance: D
    first_trim_qty: D
    second_trim_qty: D
    activated_ms: int
    max_snapshot_age_ms: int
    max_evidence_age_ms: int
    # Evidence definitions must be reviewed/approved, not merely a boolean signal.
    structure_definition_hash: str
    owner_authorized: bool = False
    close_remaining_if_unprotected: bool = False
    minimum_liquidation_atr: D | None = None
    account_equity_floor: D | None = None

    def __post_init__(self):
        if (not self.policy_id or not self.position_id or self.side not in ('LONG','SHORT')
                or not all(positive(x) for x in (self.initial_qty,self.total_loss_limit_usdt,
                    self.minimum_liquidation_distance,self.first_trim_qty,self.second_trim_qty))
                or self.minimum_liquidation_distance >= D('1')
                or self.first_trim_qty+self.second_trim_qty >= self.initial_qty
                or type(self.max_snapshot_age_ms) is not int or self.max_snapshot_age_ms <= 0
                or type(self.max_evidence_age_ms) is not int or self.max_evidence_age_ms <= 0
                or len(self.structure_definition_hash) != 64
                or any(c not in '0123456789abcdef' for c in self.structure_definition_hash)
                or type(self.owner_authorized) is not bool
                or type(self.close_remaining_if_unprotected) is not bool
                or (self.minimum_liquidation_atr is not None and not positive(self.minimum_liquidation_atr))
                or (self.account_equity_floor is not None and not positive(self.account_equity_floor))):
            raise ValueError('EXPLICIT_VALID_POSITION_POLICY_REQUIRED')


@dataclass(frozen=True)
class Evidence:
    event_id: str
    level: int  # 0 valid, 1 first deterioration, 2 confirmed worsening, 3 invalidated.
    closed_at_ms: int
    definition_hash: str


@dataclass(frozen=True)
class Progress:
    completed_stage: int = 0
    pending_client_id: str | None = None
    last_confirmed_fill_ms: int = 0
    last_verified_qty: D | None = None
    consumed_events: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    status: str
    qty: D = ZERO
    reason: str = ''
    stage: int = 0
    event_id: str = ''
    trade_authority: str = 'NONE'


def decide(snapshot, policy, progress, evidence, now_ms):
    if policy is None or not policy.owner_authorized:
        return Decision('AWAITING_EXPLICIT_POLICY')
    if progress.pending_client_id:
        return Decision('RECONCILIATION_REQUIRED',reason='NO_REPEAT_AFTER_TIMEOUT_OR_PENDING_FILL')
    if not snapshot.fresh(now_ms,policy.max_snapshot_age_ms):
        return Decision('DATA_UNAVAILABLE',reason='NO_ACTION_WITHOUT_FRESH_EXCHANGE_STATE')
    if snapshot.position_id != policy.position_id or snapshot.side != policy.side:
        return Decision('SUSPENDED',reason='POSITION_CHANGED_NEW_AUTHORIZATION_REQUIRED')
    if snapshot.qty == ZERO:
        return Decision('EXPOSURE_CLOSED')
    # Quantity changes are adopted from a fresh GET under global authorization.
    # The caller must recompute aggregate loss, equity and coverage; no budget reset.
    absolute_distance=(snapshot.mark-snapshot.liquidation if snapshot.side=='LONG'
                       else snapshot.liquidation-snapshot.mark)
    near=absolute_distance/snapshot.mark <= policy.minimum_liquidation_distance
    if policy.minimum_liquidation_atr is not None and positive(snapshot.atr_1h):
        near=near or absolute_distance/snapshot.atr_1h <= policy.minimum_liquidation_atr
    if near or (policy.account_equity_floor is not None and snapshot.equity<=policy.account_equity_floor):
        return Decision('PROPOSE_CLOSE_REMAINING',snapshot.qty,'CAPITAL_OVERRIDES_STRUCTURE',3)
    loss=snapshot.total_loss_usdt
    if not isinstance(loss,D) or not loss.is_finite() or loss < ZERO:
        return Decision('LOSS_ACCOUNTING_UNVERIFIED',reason='DO_NOT_DOUBLE_COUNT_FEES_OR_REALIZED_PNL')
    if loss >= policy.total_loss_limit_usdt:
        return Decision('PROPOSE_CLOSE_REMAINING',snapshot.qty,'CAPITAL_OVERRIDES_STRUCTURE',3)
    if policy.minimum_liquidation_atr is not None and not positive(snapshot.atr_1h):
        return Decision('DATA_UNAVAILABLE',reason='VOLATILITY_SAFETY_UNVERIFIED')
    causal=bool(evidence and evidence.event_id and evidence.level in (0,1,2,3)
        and evidence.definition_hash==policy.structure_definition_hash
        and policy.activated_ms < evidence.closed_at_ms <= now_ms
        and now_ms-evidence.closed_at_ms <= policy.max_evidence_age_ms
        and evidence.closed_at_ms > progress.last_confirmed_fill_ms
        and evidence.event_id not in progress.consumed_events)
    if causal and evidence.level==3:
        return Decision('PROPOSE_CLOSE_REMAINING',snapshot.qty,'THESIS_INVALIDATED',3,evidence.event_id)
    if not snapshot.protected():
        return (Decision('PROPOSE_CLOSE_REMAINING',snapshot.qty,'AUTHORIZED_UNPROTECTED_FAILSAFE',3)
                if policy.close_remaining_if_unprotected else
                Decision('PROTECTION_UNVERIFIED',reason='DO_NOT_LABEL_RESIDUAL_SAFE'))
    if causal and progress.completed_stage==0 and evidence.level>=1:
        return Decision('PROPOSE_REDUCE',min(snapshot.qty,policy.first_trim_qty),
                        'FIRST_CONFIRMED_DETERIORATION',1,evidence.event_id)
    if causal and progress.completed_stage==1 and evidence.level>=2:
        return Decision('PROPOSE_REDUCE',min(snapshot.qty,policy.second_trim_qty),
                        'FURTHER_CONFIRMED_DETERIORATION',2,evidence.event_id)
    return Decision('KEEP_PROTECTED_RESIDUAL',reason='NO_NEW_APPROVED_DETERIORATION')


def reconcile(progress, before, after, filled_qty, decision, policy):
    """Only a fresh AFTER-fill exchange snapshot can complete a reduction stage."""
    if (not progress.pending_client_id or decision.status not in ('PROPOSE_REDUCE','PROPOSE_CLOSE_REMAINING')
            or not positive(filled_qty) or filled_qty != decision.qty
            or after.position_id != before.position_id or after.side != before.side
            or after.observed_ms <= before.observed_ms or after.source != 'BITUNIX_GET'
            or after.qty != before.qty-filled_qty
            or not after.fresh(after.observed_ms,policy.max_snapshot_age_ms)):
        raise ValueError('FILL_OR_POST_ACTION_STATE_UNVERIFIED')
    return Progress(decision.stage,None,after.observed_ms,after.qty,
                    progress.consumed_events+((decision.event_id,) if decision.event_id else ()))


def close_only_draft(snapshot, policy, decision, *, position_mode, quantity_step):
    """Returns review data only. No HTTP client, credentials or send method exists."""
    if (not policy.owner_authorized or snapshot.position_id!=policy.position_id
            or snapshot.side!=policy.side or position_mode!='ONE_WAY'
            or decision.status not in ('PROPOSE_REDUCE','PROPOSE_CLOSE_REMAINING')
            or not positive(quantity_step) or not positive(decision.qty)
            or decision.qty>snapshot.qty or decision.qty%quantity_step!=ZERO):
        raise ValueError('CLOSE_ONLY_DRAFT_REFUSED')
    identity=f'{policy.policy_id}:{snapshot.position_id}:{decision.stage}:{decision.event_id}'
    body=dict(symbol='BTCUSDT',positionId=snapshot.position_id,
              side='SELL' if snapshot.side=='LONG' else 'BUY',orderType='MARKET',
              qty=str(decision.qty),reduceOnly=True,clientId=hashlib.sha256(identity.encode()).hexdigest()[:32])
    return dict(method='POST',path='/api/v1/futures/trade/place_order',body=body,
                executable=False,trade_authority='NONE',requires_fresh_preflight=True)


def proposed_conservative_policy(*,policy_id,position_id,side,qty,reference_equity,
                                 quantity_step,activated_ms,structure_definition_hash):
    """Proposal, NEVER authorization. Reference equity is locked, not reset after loss."""
    if not positive(reference_equity) or not positive(quantity_step) or not positive(qty):
        raise ValueError('VERIFIED_REFERENCE_EQUITY_AND_SIZE_REQUIRED')
    third=(qty/D('3')/quantity_step).to_integral_value(rounding=ROUND_FLOOR)*quantity_step
    if third<=ZERO:raise ValueError('THREE_TRANCHES_BELOW_MINIMUM_SIZE')
    return Policy(policy_id,position_id,side,qty,reference_equity*D('.01'),D('.02'),
                  third,third,activated_ms,5000,3600_000,structure_definition_hash,
                  owner_authorized=False,close_remaining_if_unprotected=True,
                  minimum_liquidation_atr=D('2'),account_equity_floor=reference_equity*D('.95'))
