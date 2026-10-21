# Manual `/bitman` — review only

An authorized `/bitman` asks Guardian's existing Telegram command poller for a
read-only BTC direction snapshot. No automatic Bitman notifications, scheduler,
orders or trading authority are added. The research result remains
`INCONCLUSIVE DIRECTION ENGINE` and
`EXACT BITMAN KONKORDE PARITY: NOT PROVEN`.

Production base: PR #26 merge
`5e6c63926015dd31217948de2b2e6e9a5fa5cee4` on `mlrsi-mtf-observer`.
This PR does not merge, deploy, access Railway, change variables or send test
messages to production. Existing research PRs are untouched.

## Frozen engine reuse

`bitman_manual/frozen/provenance.json` records source paths, SHA256s, selected
symbols and import rewrites from research commit
`4027242b86fcad81209cffde4c85e59c9418088d`. The runtime vendors the existing pure
functions rather than depending on an unmerged research branch:

| Existing source | Runtime reuse |
| --- | --- |
| `research/bitman_direction/core.py` | Exact features, hierarchy, strength, timing, decision and snapshot; imports relocated only |
| `research/bitman_direction/levels.py` | Exact causal structure context, completed UTC day/week and confirmed pivots |
| `research/bitman_direction/confirmed.py` | Exact existing confirmed-state validation/projection; no ML RSI calculation |
| `research/bitman_direction/spec.py` | Existing version, intervals and ML RSI config constants only |
| `research/bitman_real/indicators.py` | Exact AO, ADX/DI, Konkorde proxy and BBWP public formulas |
| `research/bitman_real/market.py` | Only existing `validate` and `aggregate` functions |
| `research/bitman_real/events.py` | Only existing pure `geometry` function |
| `research/bitman_direction/telegram.py` | Presentation adapted to compact plain text; decision rules unchanged |

The runtime does not import research observers, research loaders, backtests,
Phase2/Phase4 strategies, artifact journals, exit/entry logic or extension
trackers. Vendored unused helpers do not run automatically. No thresholds or
rules were recalibrated and no new backtest was run.

The hierarchy remains 1D MACRO BIAS, 4H SWING BIAS and 1H IMPULSE / TIMING.
Aligned 1D/4H can remain UP/DOWN through a 1H pullback. Opposed 1D/4H with 1H
supporting the swing is TRANSITION; otherwise the existing conflict rules apply.
Missing required higher context is UNCLEAR. Existing opposing major structure
tests and opposing confirmed ML RSI 4H can produce CONFLICT. ADX measures
strength; DI supplies directional confirmation. Strength remains
WEAK/BUILDING/STRONG. Grade/probability and entry/exit suggestions are not shown.

## Manual request path and limits

1. `guardian_commands.TelegramCommands.process` applies its existing enabled,
   token and exact owner-chat checks before creating a lazy `BitmanHost`.
   `/bitman@bot` uses the same existing parser. `/help` lists `/bitman`.
   No second poller, bot or sender exists.
2. A daemon supervisor returns control to the poller immediately and starts one
   killable Python child. Guardian's protection cycle is not involved. At most
   one calculation is in flight; another manual request gets the static
   unavailable response. Idle hosts do no work.
3. The child uses a fixed public GET endpoint for BTCUSDT USD-M 1H klines:
   [Binance USD-M market data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#klinecandlestick-data).
   It has no account client, credentials, Telegram client or mutating HTTP path.
   OS/interpreter environment is allowlisted; tokens, account keys and proxy
   credentials are not inherited. Bytecode writes are disabled in the child.
4. Public history is bounded to 300 completed UTC days plus the current partial
   day, with at most five pages of 1,500 hourly candles. This is a transport
   warmup bound, not an optimized engine threshold. It covers the frozen
   220-bar daily structure window and BBWP warmup. Recursive indicator seeds
   use that finite prefix; they are not asserted bit-identical to an arbitrarily
   longer historical prefix. The formulas and decision rules remain exact.
5. Every public candle must match the expected contiguous UTC open/close time
   and schema, with finite valid OHLC/volume. Partial/open candles are excluded;
   complete 4H/1D candles are aggregated with the frozen functions. Missing,
   duplicate, malformed or stale public data returns unavailable. There is no
   extrapolation, future pivot or switch to an unverified source.
6. Public components/structure have a 30-second RAM cache, invalidated at the
   next hourly close. Cached public context never caches ML RSI colors: each
   manual request reads current production confirmed state and applies the
   same frozen decision function again. No runtime files/journals are written.
7. Public requests use 3-second connect / 5-second read limits, no redirects,
   auth or added retry/backoff. The parent enforces a 25-second child timeout,
   then kills/reaps it. Failure replies contain no exception/API payload/path.
8. Only the existing owner reply callback sends one response per completed
   manual request, including failures. The shared sender/retry is unchanged.
   Host shutdown kills pending work and suppresses its reply.

## Real ML RSI, read only

The existing `mlrsi_guardian_host.storage_directory()` resolves the actual host
state location (`MLRSI_STATE_DIR`, volume path, or its existing fallback).
`igod_mlrsi_state.json` is read only; no journal export is consumed and nothing
is written into `/data`. ML RSI math, observer, cache, state writer and alert
flags are unchanged.

The frozen projection accepts the real BTCUSDT SPOT
`CAPTURE_LOW29_EMA4_PINE_PARITY_V4` schema, closed 1H/4H confirmed values,
valid finite fields, freshness and successful observation within 90 seconds.
A matching read-only check displays 15m confirmed context. A missing, stale,
future, invalid or different-config state is UNKNOWN. No historical ML RSI is
reconstructed. PROVISIONAL and APPROACHING fields are never passed into a
decision; 15m display cannot determine the macro direction. The output labels
public USD-M and confirmed production SPOT to preserve their distinct venues.

## Protection and test boundaries

`trade_guardian.py`, Guardian risk/emergency/order modules, V8, Manual Copilot,
ML RSI math/alert controls, sender/retry, Early Breakout and D60 remain
unchanged. The only production integration edits are the command route, help,
lazy host field and shutdown hook in `guardian_commands.py`.

The existing immutable safety manifest is preserved. Its audit now removes
only the exact new `/bitman` AST fragments, verifies the remainder against the
production merge and then performs the existing baseline checks. Tests prove
owner-policy/old-command changes are still detected, and verify every frozen
source against its original Git object. Existing V8 hash and Guardian
protection assertions remain active.

Offline tests cover all five states, owner filtering, current confirmed ML,
ignored provisional/approaching, unavailable data, causal closed frames/pivots,
public GET validation, hard timeout, cache expiry, no startup work, shutdown,
nonblocking help, sender failure and zero order/network effects through the
manual calculation route. All fixtures below are synthetic, not claimed
production observations or forward evidence.

Validation commands:

```text
python -m unittest test_bitman_manual test_guardian_commands test_mlrsi_alert_controls -v
python mlrsi_safety_audit.py
python -m unittest discover -v
git diff --check
```

Local validation after the exact guard adaptations: **668 tests passed**
(including 38 new Bitman tests), no failures/skips, direct process exit code 0.
The targeted Guardian/commands/canary/ML RSI battery passed **544 tests**.
Compilation, `mlrsi_safety_audit.py` and patch whitespace checks passed.

## Existing regression guards

Before the test-only corrections, `python -m unittest discover -v` ran 667
tests and reproduced exactly two failures. Both were category A: expected
regression guards for the intentional manual command extension:

- `test_mlrsi_integration.CommandIntegrationTests.test_help_preserves_all_previous_text_and_commands`:
  the old help equality did not remove the new Bitman line. It now permits
  exactly one audited Bitman help fragment and exactly one additional command,
  preserves the entire preceding help/command set and rejects `/bitman_help`.
- `test_mlrsi_recovery.ProviderRecoveryTests.test_math_preset_reference_and_protection_files_unchanged`:
  the byte-level guard noticed the authorized `guardian_commands.py` diff.
  That path alone now uses the exact passive AST normalization, compares the
  entire remainder to its original baseline and separately verifies the
  production command extension. All mathematical/protection files retain the
  previous byte checks. No recovery, cache, journal or ML RSI runtime code was
  changed.

The hypothesized `test_live_levels_canary` failure did not occur. Its original
TelegramCommands/SnapshotCache hashes remain intact and pass through the
existing `guardian_baseline_tree` audit. No hash was replaced. Additional
mutation tests verify that owner filtering, SnapshotCache's copy boundary,
previous command routes and unaudited changes to the new helper cannot pass
normalization. Generic old command-loop tests mock only the new async request
boundary so they stay offline; the new manual-route test runs the real frozen
calculation with synthetic public input while prohibiting every network/order
request and checking unchanged Guardian state.

`MLRSI_PUBLIC_REBOOTSTRAP 15m MLRSI_CLOSED_CANDLE_REVISED` is expected output
from the passing `test_mlrsi_observer.PublicTests.test_closed_revision_rejected`.
It is not one of the failures and does not justify a change to ML RSI.

## Exact example message (synthetic fixture)

Generated by `render(snapshot('UP', 'UP', 'DOWN'))` in
`test_bitman_manual.py`; numbers/colors illustrate formatting only.

```text
🧭 BITMAN — BTC DIRECTION

🟢 Direction: UP
💪 Strength: STRONG

1D 🟢 UP — MACRO BIAS
4H 🟢 UP — SWING BIAS
1H 🔴 DOWN — IMPULSE / TIMING (PULLBACK)

AO: 1D 120.00 bullish | 4H 120.00 bullish | 1H -120.00 bearish
ADX/DI (4H): 24.00 RISING · +DI leads (ADX strength; DI direction)
Konkorde (4H, PROXY): BULLISH INSIDE
BBWP / volatility (4H): 64.00 · RISING

ML RSI confirmed (production SPOT):
15m 🔴 RED
1H 🔴 RED
4H ⚪ NEUTRAL

Support: 80,400.00
Resistance: 83,200.00
Public USD-M · closed 1H reference: 2026-10-16 18:00 UTC

⚠️ Directional research context — INCONCLUSIVE DIRECTION ENGINE
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
👀 SHADOW ONLY · MANUAL ONLY · NO AUTO ALERTS
🚫 NOT AN ORDER · TRADE AUTHORITY: NONE — NO AUTO TRADE
```

Unavailable replies start with `⚪ BITMAN: DATA TEMPORARILY UNAVAILABLE` and
retain the same research/shadow/no-authority footer. Component-level unknowns
remain `UNKNOWN` without fabricated substitutes.
