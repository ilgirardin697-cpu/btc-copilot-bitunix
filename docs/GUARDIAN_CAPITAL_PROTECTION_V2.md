# Guardian Capital Protection V2 — proposed policy, execution disarmed

This is a protection controller for an already existing BTCUSDT position, not an
entry strategy. Installation does not authorize exchange writes. The owner must
approve the complete policy and its implementation hash before live protection.
No V8 execution, automatic entries, averaging, reversal, leverage/margin change,
transfer, cancellation, or modification of manual orders is permitted.

## Stable global policy proposed for approval

These are conservative engineering choices, not optimized or proven optimal.
They apply symmetrically to LONG and SHORT, main account, USDT, ONE_WAY mode.
HEDGE, ambiguous/multiple BTC positions, unknown schemas and bonus collateral
are unsupported and reported as degraded; no guessed order-side mapping.

| Condition | Proposed behavior |
|---|---|
| Valid structure, verified native SL, aggregate risk within budget | Keep; ordinary price fluctuations alone never trim. |
| One completed 1H close beyond the first frozen structural level plus buffer | Reduce one third, rounded down to exchange size precision, once. |
| At least two consecutive breached 1H closes, including a NEW close after the first verified reduction | Reduce another third of the reconstructed basis, once. |
| Final frozen level invalidated, aggregate limit reached, unsafe liquidation distance or protection cannot be verified | Close the remainder, exclusively reduce-only. |
| Oversized position relative to its actual SL and remaining budget | Reduce excess size; do not invent an artificially tight structural stop. |

Structure uses existing causal confirmed 1H pivots (2 left / 2 right) and ATR14,
from **Bitunix MARK_PRICE** closed candles. Two nearest eligible supports for a
LONG or resistances for a SHORT are frozen when the position is adopted.
The level buffer is **0.25 ATR**, frozen at that same observation. New data cannot
retroactively create an earlier breach. Final native SL is at the buffered second
level. No future pivots, AO tuning, new directional signals or readiness changes.

Capital overrides (NOT ordinary floating-loss percentage trim triggers):

* Lock actual account reference equity at first adoption; never silently reset it.
* Campaign aggregate loss limit: **1% of locked reference equity**.
* Account safety floor: **95% of locked reference equity**.
* Final liquidation guard: actual reported distance <= **2% of mark** OR **2 current
  causal 1H ATR**. A rebound hypothesis never overrides this guard.
* Cost reserve: published base taker fee **0.06%** plus assumed **0.05% slippage**
  for a protective market close. Actual account fee tier is not independently
  known. These reserves are assumptions, not guaranteed execution prices.

Equity is read as available + frozen + position margin + cross unrealized PnL +
isolated unrealized PnL, requiring bonus=0. This is current equity, not an invented
pre-trade wallet balance. Cumulative loss uses actual fill realized PnL, actual
fill fees, signed position funding and current unrealized PnL. It deliberately
does not add position.realizedPNL again: the observed position response already
includes fees/funding there. Closed positions remain in the same campaign ledger.
New deposits, new position IDs or manual additions do not reset the budget.
Profits offset losses within that same net campaign accounting.

For structural risk sizing let L=current cumulative net loss, Q=current quantity,
P=mark, S=verified SL, c=fee+slippage reserve, B=locked limit and d=abs(P-S).
Projected loss is L+Q*(d+c*S). If it exceeds B, proposed close quantity is
ceil_to_step((projected-B)/(d+c*(S-P))), bounded by Q and exchange minimum size.
If no valid sizing/protection interval exists, the proposal is a full close.
This is a capital exception; structural stage reductions remain independent.

## Manual additions and retaining a residual

Each cycle reads current position ID, size, average entry, margin mode and actual
liquidation. An addition is adopted under the global approval, without a new
per-addition question, while preserving reference equity and accumulated costs.
Coverage and aggregate risk are recomputed. The controller never adds exposure.
After every protective fill it queries actual trades, remaining size, average,
account equity, margin, **exchange-reported liquidation** and pending SL again.
It never presents a modeled improvement in liquidation as a verified result.

Bitunix documents a position-level market TP/SL that closes the quantity present
at trigger time. V2 creates only its SL leg. Ownership requires a recorded create
ACK plus matching pending-order readback and fields; a manual zero/unknown quantity
is never treated as full coverage. Only an owned position SL with no TP can be
modified. A manual TP/SL is never canceled or modified to free the one-position
SL slot. If creation is rejected or coverage stays unverifiable, the authorized
fallback is closing the remainder, not leaving an assumed protected residual.
An owned dynamic SL continues to cover the current position when quantity changes.
A newly opened manual position with a different position ID is detected on the next
poll; software polling cannot guarantee an SL exists at the instant of that entry.
Do not open a manual position without exchange protection while waiting for a poll.

## Durable actions and recovery

Storage: `/data/guardian/capital_protection_v2.jsonl`, private, append-only.
Schema 1 records contain ID, kind, observation time, payload, previous hash and hash.
Types include ACTIVATION, BASELINE, POSITION, STRUCTURE, INTENT, ACK, STOP_OWNED,
STOP_FAILED and RECONCILED. Writes flush/fsync before any exchange POST.
Hash-chain replay rejects changed, reordered or truncated history. It is an
integrity check, not cryptographic authentication against an attacker rewriting
the whole file. No silent truncation, repair or budget reset is implemented.

Only one pending intent is allowed. Each action has a deterministic client ID.
Timeout or reboot after preparing/sending an action requires exchange reconciliation;
the API client never blindly retries a POST. A confirmed terminal partial fill is
recorded at its actual quantity (not the requested quantity); that counts as one
stage attempt, and a later stage requires a newer completed candle. Unresolved or
unknown order state blocks further writes and reports a degraded/reconciliation state.
It may require operator investigation; absence of an ACK is not proof of rejection.
Stop readback failure after 30s invokes the separately authorized final close.
The pre-existing Guardian store lock prevents a second process sharing the same
state directory; V2 is serial in that process and has no second poller or executor.

## Authorization, isolation and disabling

Defaults (none created automatically):

```text
GUARDIAN_CAPITAL_V2_ENABLED=false
GUARDIAN_CAPITAL_V2_EXECUTION=false
```

Later live activation additionally requires the exact `POLICY_HASH` in
`GUARDIAN_CAPITAL_V2_POLICY_HASH` and
`GUARDIAN_CAPITAL_V2_AUTHORIZATION=OWNER_APPROVED_CAPITAL_PROTECTION_ONLY_V2`.
Hash binds policy parameters AND implementation/safety dependencies, normalized
for CRLF/LF. A code/policy change invalidates approval; it cannot silently reuse it.
Classic Guardian SL/CLOSE permissions must remain disarmed to prevent competing
executors. Authorization is rechecked each cycle. V8 remains untouched.

Disabled means no V2 client, network, journal or diagnostic. Enabled SHADOW permits
reads/journaling/proposals only. Live transport permits exactly three POST paths:
reduce-only market close, position SL create, owned position SL modify. The client
refuses extra order fields, TP, OPEN, unsupported sides, excess quantity, arbitrary
hosts, redirect/proxy inheritance and a write without a fresh durable intent.
Normal cycle network work has an 8-second budget and per-request timeouts.
Risk/structure computation cannot send an order directly; only the gated adapter can.
The existing cycle, risk rules, client, sender/retry and protected code remain intact
after removing the exact audited main-loop hook and read-only `/risk` reply wrapper.

Disable `GUARDIAN_CAPITAL_V2_EXECUTION` (or ENABLED) and redeploy Guardian only to
stop new protective mutations. **Do not cancel its native SL to disable the host.**
Do not restore an old variable snapshot containing revoked API keys. Rollback code
by branch+SHA only, preserving the currently valid keys, volume and all other flags.

## Operational limits and deployment checklist

Railway failure leaves an already registered native SL in Bitunix, but prevents
new reductions, alerts and verification. Bitunix/API failure can prevent both
verification and execution. Market gaps, slippage and funding can exceed a planned
monetary cap. No software can guarantee a fill or prevent all liquidation risk.
CROSS collateral and other manual trades affect the actual account/liquidation.
The controller protects BTCUSDT only; it cannot guarantee losses of other assets.

1. Tests, existing source/AST guards, 900 readiness cases, weekly V1 protocol and
   ML RSI/V8 safety checks must pass. Real API checks are GET-only; simulated POST
   tests are not claimed as exchange mutation validation.
2. Publish a separate draft PR from current Guardian code. No merge is required
   for the authorized DISARMED deployment.
3. Stage ONLY Guardian source branch+SHA after confirming current deployment,
   variables, SFO, volume and no foreign staged changes. Preserve all credentials.
4. Await terminal SUCCESS/Online 1/1 and inspect actual build commit (a displayed
   source pin alone previously did not guarantee the fetched branch commit).
5. Verify V2 disabled/silent, old protections/config, ML RSI, weekly observer,
   commands and untouched V8/market-data/daily/PAPER deployments.
6. Present current position and **one** policy/permission approval summary. Before
   that approval, do not send even a test exchange POST.
7. Only after approval, re-read position and actual orders before the first action;
   verify fills and residual SL directly. Never claim a position protected from a
   successful deployment or a theoretical stop.

Public API sources: [position](https://www.bitunix.com/api-docs/futures/position/get_pending_positions.html),
[account](https://www.bitunix.com/api-docs/futures/account/get_single_account.html),
[pending TP/SL](https://www.bitunix.com/api-docs/futures/tp_sl/get_pending_tp_sl_order.html),
[position SL create](https://www.bitunix.com/api-docs/futures/tp_sl/place_position_tp_sl_order.html),
[position SL modify](https://www.bitunix.com/api-docs/futures/tp_sl/modify_position_tp_sl_order.html),
[order](https://www.bitunix.com/api-docs/futures/trade/place_order.html),
[fills](https://www.bitunix.com/api-docs/futures/trade/get_history_trades.html),
[published fee schedule](https://www.bitunix.com/hub/blog/bitunix-features/bitunix-fees-spot-futures-vip-trading-discounts).
