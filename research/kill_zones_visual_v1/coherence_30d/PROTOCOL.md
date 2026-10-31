# Coherence audit — frozen V1, no profitability evaluation

Written before computing monthly signal counts. Fixed sample: ALL 30 New York
London dates, 2026-09-01 through 2026-09-30. All are in UTC−4 under the already
chosen America/New_York clock. No alternate month, clock or parameter selection.

Import the unchanged `model.py` from reviewed commit
`cc81cca28cf1b770ae8b9c22ad7c680821151e11`.
Required model SHA256:
`20a646c5cd5300b6cb478d578a1904d446fd28a72ebb94ff527679345df926e2`.
Do not change construction, ordering, line, clone, trigger, entry, SL, expiry or
one-first-confirmation rule. Fail if model bytes change. No PR #40 strategy code.

Data: saved official September 2026 Binance Vision USD-M 5m archive and its
official saved checksum; verify SHA256 locally, no new download. Aggregate only
12 exact contiguous closed rows per hour, Decimal OHLC and base volume. All 720
hours required, no gaps/filling. Record archive / hourly CSV hashes and normalization.
Month starts exactly at Asia start for day 1 and ends at expiry for day 30.
If the final possible next-open reference is absent, report ENTRY_PENDING;
do not fabricate a boundary fill or treat pending as rejection.

One daily frozen result, retaining all ambiguous days and rejected plans. Render
ALL 30 charts; no favorable-case selection. Separately count UP/DOWN, valid
geometry, no confirmation, confirmed/reference plan, rejection and pending.
Explain rejected plans using stop/entry/target ordering only. Reasons can overlap;
also provide an exclusive TARGET_ONLY / STOP_ONLY / BOTH partition.

For each confirmation, compare frozen target with the trigger line, signal close
and next open. These are contemporaneous distances, NOT realized returns. Replay
at confirmation time and at day expiry must preserve the confirmation and plan.
No signal rerouting, no added filter, no offset or anchor adjustment.

No PnL, win/loss, targets hit after entry, MAE/MFE, return, funding, fees, ranking,
parameter search or optimization. Reused historical data: NO VIRGIN HOLDOUT.
This audit is not a prospective observation and cannot establish edge.

Decision rule: do not start PAPER observation as a reproduction of the VIDEO
strategy while the identity of its trigger line and temporal anchor placement
remain unverified. Technical causal replay does not prove source fidelity.
Monthly counts describe mechanical feasibility, not profitability or validation.

SHADOW ONLY. TRADE AUTHORITY: NONE.
