# BITMAN private market data transport

Status: code and offline validation only. No Railway resources, variables, domains,
deployments or production services are changed by this PR.

| Property | Contract |
| --- | --- |
| Venue | `BINANCE_USDM_PERPETUAL` |
| Source | Binance USD-M REST `https://fapi.binance.com/fapi/v1/klines` |
| Instrument / interval | `BTCUSDT` / `1h`, complete CLOSED candles only |
| Acquisition service (future) | `bitman-market-data`, Railway Amsterdam `europe-west4-drams3a` |
| Consumer | Existing Guardian, Railway SFO; unchanged region and `/data` volume |
| Project / environment (future) | `victorious-energy` / `production`, same private network |
| Transport | `http://bitman-market-data.railway.internal:8080/fapi/v1/klines` |
| Authority | NONE; no orders, accounts, positions, leverage, TP/SL or trading credentials |
| Mode | SHADOW ONLY / MANUAL ONLY; no automatic alerts or schedules |

```text
Authorized manual /bitman
  -> existing Guardian BitmanHost (SFO, same owner filter/poller/sender)
  -> credential-free subprocess, explicitly allowlisted transport URL in JSON
  -> Railway private network -> bitman-market-data (Amsterdam)
  -> official Binance USD-M REST -> validated original response bytes
  -> existing 300-day fetch/prepare/snapshot/decision/render
```

The prior Amsterdam connectivity test returned HTTP 200 with valid 12-column
USD-M pages through 1500 rows. Guardian SFO receives HTTP 451 from that same
official endpoint. This acquisition change preserves the instrument, venue and
source. It does not validate the directional research:
`INCONCLUSIVE DIRECTION ENGINE` and
`EXACT BITMAN KONKORDE PARITY: NOT PROVEN` still apply.

## Restricted gateway

`bitman_market_data_service.py` uses Python stdlib only. Import and startup do no
upstream work. It is stateless, has no disk/volume access, and reads no environment
variables or credentials. Only an incoming kline request triggers a single
upstream request; health checks do not. There are no retries, background fetches,
fallback sources or cache. Guardian's existing 30-second context cache and
25-second child deadline remain unchanged.

Only `GET /health` and `GET /fapi/v1/klines` are served. The health body is just
`{"ok":true}`; this is process liveness, not a guarantee of Binance availability.
The kline request must contain exactly one of each:

```text
symbol=BTCUSDT
interval=1h
startTime=<nonnegative integer milliseconds, UTC hour aligned>
endTime=<integer milliseconds, end of a UTC hour>
limit=<integer 1..1500>
```

The inclusive range must request at most `limit` complete hours, and
`endTime < floor(server_now_ms / 3600000) * 3600000`. A smaller final page with
`limit=1500` is valid. A request for the current open candle, a future candle,
unaligned timestamps, partial/truncated ranges, duplicates, missing or unknown
parameters is rejected before upstream access. The service requires its exact
private Host name (with optional `:8080`); `healthcheck.railway.app` is accepted
only for `/health`. Other paths, hosts, absolute URLs, methods and request bodies
are rejected. A caller cannot supply an upstream URL, credentials or headers.

Upstream is hard-coded HTTPS with certificate verification, an empty proxy map,
redirects disabled, a 4-second socket timeout and a 2 MiB body ceiling. Non-200,
timeout, redirect, invalid JSON or any failed row validation returns a small
sanitized HTTP 502; no upstream error body or exception is exposed.

Each successful page must have the exact expected count, exactly 12 columns per
row, integer open/close timestamps, exact hourly order, no gaps/duplicates,
`closeTime = openTime + 3600000 - 1`, finite positive valid OHLC, nonnegative base
volume, and `0 <= taker_buy_base_volume <= base_volume`. Decimal parsing is used
only for checks. After all rows pass, the **original response bytes** are sent
unchanged. No candle is reconstructed, rounded, resampled or replaced. Binance's
12 columns, including the unused fields, retain their original values. The
existing consumer selects the same seven numerical inputs as before.

## Explicit child transport

Only the Guardian parent reads the optional non-secret `BITMAN_MARKET_DATA_URL`.
Its default is the exact official Binance URL. The only other permitted value is
the private URL shown above. The parent validates it, passes `market_data_url`
in the controlled worker JSON request, and the worker validates it again, even
when using cached context. The existing two-field worker request remains valid
for offline callers, defaulting to the official URL.

The child environment remains restricted to `PATH`, `SYSTEMROOT`, `WINDIR`,
`TEMP`, `TMP`, `PYTHONIOENCODING` and `PYTHONDONTWRITEBYTECODE`. It does not inherit
the transport environment variable, proxies, Bitunix keys, Telegram tokens or
other Guardian credentials. Both consumer transports retain `trust_env=False`
and `allow_redirects=False`. Invalid configuration or any failed fetch returns
the existing `DATA TEMPORARILY UNAVAILABLE`; there is no silent direct fallback.

## Future deployment requirements (not applied)

After separate review/authorization, provision only the data service in the same
project/environment, in Amsterdam. Use an explicit start-command override
`python -B bitman_market_data_service.py` and `PORT=8080` if required for Railway
health checks. The repository's existing `railway.json` remains Guardian's
configuration and must not be inherited as the new service's start command.
The service binds dual-stack `[::]:8080` with IPv4 enabled, covering
`0.0.0.0:8080` and Railway's private IPv6 network. Configure `/health` privately.

Do not create a public domain or TCP proxy, static outbound IP, volume, shared
variable reference, credential or Telegram integration. Private networking is
the access boundary: other services within the same environment may reach this
read-only service; it does not authenticate individual services. Nothing here
creates an application-level public API or provisions Railway infrastructure.

The future Guardian change is only
`BITMAN_MARKET_DATA_URL=http://bitman-market-data.railway.internal:8080/fapi/v1/klines`.
No Guardian region, volume, ML RSI flag or other setting changes. A future
rollback can restore the previous source/configuration; the official default
will retain the safe unavailable response in SFO while HTTP 451 persists.

Before any rollout, separately verify private DNS/routing across Amsterdam and
SFO, service region, upstream access, aggregate manual-command latency under the
unchanged 25-second deadline, absence of public ingress/credentials/volumes,
and Guardian health. Five requests at the 4-second socket timeout can exhaust
that deadline; the child remains killable and the command fails closed. Liveness
does not establish market-data readiness. No natural production command has been
tested against this new service yet.

Official deployment references:
[Railway private networking](https://docs.railway.com/networking/private-networking)
documents same-environment internal DNS and encrypted private transport;
[Railway health checks](https://docs.railway.com/deployments/healthchecks)
documents the health hostname and port requirements.

## Offline validation

```text
python -m unittest test_bitman_market_data test_bitman_manual -v
python mlrsi_safety_audit.py
python -m unittest discover -v
```

`EquivalenceTests.test_host_worker_private_gateway_matches_direct_prepared_input_snapshot_and_output`
uses 7,218 synthetic CLOSED hourly candles, a fixed clock, a synthetic real-shape
ML RSI state, and the actual frozen engine. It runs Host -> controlled worker ->
loopback HTTP gateway -> mocked Binance, and compares with the direct transport
fixture. Only the child process boundary and external Binance are mocked; the
gateway, pagination, validation, engine and rendering execute normally. The
loopback adapter exists exclusively in the test; runtime URLs remain allowlisted.

It asserts identical five-page requests (300 days, page size 1500), identical
`7218 x 7` fetched arrays, every nested prepared array including warmup NaNs,
the entire public cache/snapshot/confirmed-state result, and the exact rendered
message. The state fixture is unchanged. This is transport equivalence evidence,
not forward market observations, a backtest or evidence of directional edge.

The new `Bitman Market Data` workflow adds targeted gateway/equivalence/manual
tests and the existing safety audit. All previous workflows remain unchanged,
including their full-suite and ML RSI/V8 checks. The only existing test change
adds the reviewed non-secret URL field to the Host->Worker request assertion;
the credential/environment guard is retained intact.

No changes to `bitman_manual/frozen/**`, thresholds, indicators, S/R, V8, Guardian
risk/emergency/execution, ML RSI math/recovery/alerts, Manual Copilot, sender or
retry logic. `TRADE AUTHORITY: NONE — NO AUTO TRADE`.

Local validation on 2026-10-19: Python 3.12.10, full discovery **697 passed,
0 failed, 0 skipped**; targeted gateway/manual/commands/canary suite **120 passed**;
`mlrsi_safety_audit.py` returned `MLRSI_SAFETY_AUDIT_OK`. Use Python 3.12 as in CI:
the pre-existing AST fingerprint canary is Python-version-dependent; it was not
rebaselined or weakened for this transport change.
