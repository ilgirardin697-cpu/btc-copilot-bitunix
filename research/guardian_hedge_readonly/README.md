# HEDGE/CROSS: review of read-only inventory support

Status: **OFFLINE REVIEW ONLY — NOT INTEGRATED — TRADE AUTHORITY NONE**.

This branch starts at the reviewed notification SHA `5c6cc6a78a16520deda2d21f562fa6cf0a4cbaad`. It changes only this research directory. It does not fix, bypass or replace the deployed Guardian's fail-closed position parser. No new PR or service is created by this study.

## Verified cause and additional finding

The authorized 26 November GET-only investigation found two distinct BTCUSDT `positionId` values, one BUY/LONG and one SELL/SHORT, both HEDGE/CROSS. The existing `parse_positions` accepts each record separately and rejects their combined list with `AMBIGUOUS_POSITIONS`. Do not choose the first, largest or preferred side.

An independent per-ID TP/SL read also found that both scoped requests returned a wider list containing orders for both IDs. The existing client's `ORDERS_SCOPE_INVALID` rejection is consequently justified. The offline report can partition a **complete** wider response by exact `positionId`, preserving both sides; it fails on unknown IDs, duplicate order IDs or incomplete pagination. This interpretation has not been added to production.

Actual private balances, prices, quantities, credentials and account IDs are not committed here. `fixtures.json` uses the documented/observed field layout, with **all IDs and financial values replaced**. It is a synthetic anonymized-shape fixture, not a certified snapshot of a real account. Tests cover both directions, missing stops and failures, not just full coverage.

## What the pure report calculates

- Both positions, deterministically keyed by `positionId`, with BUY→LONG / SELL→SHORT aliases.
- Reported margin, leverage, realized PnL **excluding costs**, floating PnL, reported transaction fees and funding separately.
- Gross BTC/notional: sum of absolute quantities, valued at the same mark. Net BTC/notional: LONG minus SHORT. Zero net exposure does not imply zero gross exposure, zero margin requirements or zero risk.
- Sum of reported position margins, explicitly **not account equity**. CROSS margin is shared; no equity is allocated twice and no combined liquidation price is invented.
- Each side's exact returned liquidation reference. A nonpositive value is documented as no current estimate, not automatically missing data. A positive reference on the unexpected side of the mark in CROSS/HEDGE remains unverified for a directional interpretation; it does not prove liquidation has already occurred.
- Per-ID TP/SL registration checks. No stop is inferred from a theoretical level. Missing/zero SL quantity is not assumed to mean the full position. Split orders, unknown triggers, LIMIT stops and inconsistent IDs remain unverified. A verified pending MARKET registration still cannot guarantee fills during gaps or exchange failure.

The existing 2% emergency rule is untouched. The offline directional distance is a reference only, not a replacement account-risk or execution decision.

## Pending production review

1. Specify a multi-position read snapshot and account-level CROSS reconciliation using documented account components, timestamps and completeness checks. Do not sum position equities.
2. Revalidate per-position TPSL bindings from complete results and detect revisions during the non-atomic read window. Keep other IDs and unknown orders visible.
3. Expose LONG, SHORT, gross/net risk and protection uncertainty through passive presentation only.
4. Keep all mutation capabilities OFF. No decision about reducing, closing or replacing stops belongs to this module. Any protection expansion requires a separate review.

No live credentials are needed for the tests:

```text
python -B -m unittest research.guardian_hedge_readonly.test_report -v
```

Official references checked on 26 November 2026:

- [Pending positions](https://www.bitunix.com/api-docs/futures/position/get_pending_positions.html): list response, HEDGE/CROSS, positionId, realized PnL excluding fees/funding and nonpositive liquidation semantics.
- [Pending TP/SL](https://www.bitunix.com/api-docs/futures/tp_sl/get_pending_tp_sl_order.html): positionId binding, pagination, trigger/type/quantity fields.
- [Account components](https://www.bitunix.com/api-docs/futures/account/get_single_account.html): account fields require explicit reconciliation; the report deliberately does not infer equity from position margin.

Technical tests are not evidence of trading performance. No strategy, indicator, notification protocol, weekly journal or trading permission is changed.
