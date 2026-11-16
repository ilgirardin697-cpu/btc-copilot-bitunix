# Public BTCUSDT USD-M collector preparation — disabled / disconnected

SHADOW ONLY. TRADE AUTHORITY: NONE. No real endpoint requests were executed.

This is a separate DRAFT from observer hardening. It is independently based on
PR #52 HEAD `9f307fd9feda6279253c0a0813d49b47d3f1d9b2`; no old source, model,
hash or production file changes. It does not import/connect the new observer.

## Exact public boundary

Only unsigned GET to `https://fapi.binance.com` is possible:

- `/fapi/v1/time`: raw public exchange-clock witness.
- `/fapi/v1/klines`: BTCUSDT,1h, exact bounded closed ranges, maximum1500 rows.
- `/fapi/v1/fundingRate`: BTCUSDT, inclusive bounded ranges up to7days, limit1000;
 1000 returned rows means completeness is unknown and fails closed.

No API key, signature, custom host, arbitrary URL/query/header, order/account
endpoint, POST/PUT/DELETE, exchange fallback or proxy option exists. Stdlib
HTTPSConnection validates TLS and ignores proxy environment variables. Redirects
are recorded and rejected. Network is disabled by default and requires separate
explicit authorization; fixtures cannot certify a live network qualification.
There is one bounded request per call,10s timeout and2MB body cap. Oversized
responses are rejected with the received prefix explicitly marked truncated.
No retry loop or continuous scheduler has been installed.

Source references reviewed read-only on2026-11-16:
[official market-data API](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data),
[official Python public-market connector](https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/market.py).
The current documentation includes optional funding `rateType`. Preserve it in
original bytes; accept only absent/Regular for this BTC study. Special/unknown
cashflows fail closed. Missing settlement marks remain UNKNOWN, never zero.

## Raw records and timing

Every attempted response is stored before schema validation, including non200
and redirects. The independently located SQLite spool uses WAL, synchronousFULL,
transactions, append-only triggers, a verified hash chain and an OS-held writer
lock. It records original received bytes and their SHA256, UTC request/receipt
times, monotonic duration, URL, params, method, status, Content-Type, actual Python/
NumPy versions and the linked original exchange-clock witness. No full headers,
environment, exception payload or private/account information is logged.

Malformed data, incomplete/gapped/duplicate H1 pages, open candles, uncertain
clock or missing funding completeness produce no observation/prediction. Time
requests require a valid integer timestamp, bounded RTT and<=2s midpoint skew.
Wall/monotonic discontinuities fail closed. Original raw receipts remain intact.

The spool is not WORM or an independently anchored production store. Before any
capture, review independent volume/permissions, versioned snapshots, trusted
external anchors and two-process locking on the actual filesystem. None of those
infrastructure qualifications is asserted by local SQLite tests.

## Publication delay is NOT qualified

The provisional wait is60s after each UTC H1 close, within the5min punctuality
budget. **This is not a measured Binance publication guarantee.** A separately
authorized measurement phase must record48closed hours at offsets0,15,30,60,120,
240seconds, including failed publication attempts and every numeric revision.
The comparison uses actual timestamps and candle numeric hashes; cosmetic
formatting alone is not a revision.

`revision_report()` requires complete attempts and real HTTPS-origin records;
synthetic fixtures never qualify. A revision at/after60s, late first availability,
clock uncertainty or insufficient sample leaves NOT_QUALIFIED. It does not select
a better offset automatically. Even an observed stable window requires an
independent audit and cannot guarantee absence of later corrections.

Real revision measurements: **0**. Continuous capture: **not authorized**.
No observer adapter is connected, and no infrastructure resources were created.
Do not use replayed historical requests as timely forward emissions.

## Pinned environment and offline reproduction

Forward network qualification requires Python3.12.12 and NumPy2.3.5 exactly.
All executed transport tests use offline connections; they verify bytes,
schema/clock behavior, SHA256 and exact H1 OHLCV transfer, not real wire parity or
indicator profitability. The inherited latest-version CI is compatibility only.

```text
python -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.collector_v1.test_collector -v
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.collector_v1
```

The second command prints disabled status only; it cannot start capture.

## Resources and next review

No cost was incurred for new services/volumes in this task. Expected normal
collection is at most two clock+data request pairs per hour (96GET/day), plus
separately approved recovery/probe work. Actual payload/storage and real-region
availability are unmeasured; do not present a quote or capacity guarantee.
Use measured bytes and approved retention/pricing before deployment. The body
cap implies a deliberately loose upper bound near70GB/year at the normal request
ceiling; actual market snapshots should be measured rather than assumed.

Before activation: source/region authorization, real revision qualification,
pinned Linux parity, separate storage/locking/backup/anchor proof, sealed future
cohort and independent review of any observer adapter. No connection or deployment
is authorized by this DRAFT. Guardian, V8, ML RSI, Bitman, Railway and Bitunix are
untouched. No merge, deploy, activation or orders.
