# Manual Bitman operability gate

This PR starts at production commit
`5a61ca5cb942290377909dcfb569651a80c39dd3`. It adds a pure display-time layer in
`bitman_manual/readiness.py`; only `bitman_manual/render.py` calls it. There are
no changes to the frozen Direction Engine, indicators, thresholds, market data
acquisition, confirmed ML RSI adapter, worker protocol, host/cache, Guardian
commands, V8, risk/execution or Telegram sender.

## Meaning and limits

**READY is not a guarantee, a validated trading signal or permission to execute.**
It means only that all five technical gates defined below match the existing
snapshot. The word SÍ in the manual panel has exactly that limited meaning. It
does not establish profitability, historical edge or suitability for an account.
The engine remains `INCONCLUSIVE DIRECTION ENGINE`.

WATCH means UP/DOWN already exists, no blocking condition is present, and at
least one remaining READY gate is missing. WAIT means a blocking condition or
unknown input prevents a candidate. Both always display `¿OPERAR AHORA? NO`.
No orders, positions, accounts, entry prices, stops, targets, schedules,
automatic alerts or new data requests are created.

## Exact technical contract

`evaluate(snapshot)` receives only the already calculated snapshot and reads
exactly these five fields:

| Field | READY_LONG | READY_SHORT |
| --- | --- | --- |
| `state` | `UP` | `DOWN` |
| `strength` | `STRONG` | `STRONG` |
| `evidence_grade` | `A` | `A` |
| `timing_state` | `impulse_up` | `impulse_down` |
| `mlrsi_confirmation` | `SUPPORTING` | `SUPPORTING` |

WAIT takes precedence over every favorable field when state is TRANSITION,
UNCLEAR or CONFLICT, strength is WEAK, evidence is C, or confirmed ML RSI is
OPPOSING. UP maps only to LONG and DOWN only to SHORT. There is no candidate
inferred from AO, DI, a single timeframe, macro bias or a raw ML RSI color.

With UP/DOWN and no blocker: BUILDING, grade B, wrong/non-impulse timing, pullback,
ML RSI NEUTRAL or ML RSI UNAVAILABLE permit at most WATCH_LONG/WATCH_SHORT.
Only all five exact matches permit READY_LONG/READY_SHORT. No gate is relaxed.

The existing frozen computation of evidence grade and ML RSI confirmation is
not changed or repeated. In particular, `SUPPORTING` is already relative to the
engine's direction; this layer never substitutes GREEN for LONG or RED for SHORT.
Neither provisional nor approaching state is consumed.

Missing, malformed or unknown values in any of the five input fields fail
closed to WAIT. This is input validation, with no imputation, alias, case
conversion or probability substitution. The documented `UNAVAILABLE` ML RSI
value is a recognized state and permits WATCH; an absent/unrecognized field is
UNKNOWN and yields WAIT. Timing alignment cannot be claimed before direction
is confirmed.

The result contains `operate`, `status`, `side`, deterministic `reason_codes`
and structured `missing_conditions` (`field`, sanitized `actual`, `required`).
The only statuses are WAIT, WATCH_LONG, WATCH_SHORT, READY_LONG and READY_SHORT.
`operate` is true only for the two READY statuses. WAIT has `side=None`.
The result is a new object and cannot mutate the input snapshot or its nested
data. The function has no imports, I/O, client, environment, clock or state.

## Manual panel

The existing direction, strength, timeframe hierarchy, indicator context, real
confirmed ML RSI display, structural levels and closed-candle reference precede
the new operability block. A READY block shows the five exact matches and states
explicitly that it is neither a guarantee nor a validated signal/order.

For WAIT/WATCH the renderer lists exactly the failed predicates and derives
`👀 QUÉ TIENE QUE PASAR` from those predicates only. When the failed direction
gate has an existing 4H TRANSITION context, its wording asks for 4H confirmation;
that context changes only the explanation, never the decision. It does not
create a SHORT WATCH candidate from a bearish macro during TRANSITION.

The owner's current example (TRANSITION, WEAK, 1D DOWN, 4H TRANSITION, 1H DOWN;
displayed ML RSI RED/NEUTRAL/NEUTRAL) yields **WAIT / operate=false / side=None**.
Tests use only the fields the owner supplied. Omitted grade/timing/confirmation
fields are UNKNOWN, never reconstructed from the display. TRANSITION and WEAK
already independently require WAIT even if every other gate is favorable.

Every rendered panel, including READY and unavailable, retains the original
footer verbatim:

```text
INCONCLUSIVE DIRECTION ENGINE
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
SHADOW ONLY · MANUAL ONLY · NO AUTO ALERTS
NOT AN ORDER · TRADE AUTHORITY: NONE — NO AUTO TRADE
```

The existing Telegram UTF-16 length guard and unavailable header remain unchanged.
Unavailable also states `¿OPERAR AHORA? NO / WAIT`; it cannot display a candidate.
No sender/retry logic, authorization policy or poller is added.

## Validation

```text
python -m unittest test_bitman_readiness -v
python -m unittest test_bitman_manual test_bitman_market_data test_guardian_commands test_live_levels_canary -v
python mlrsi_safety_audit.py
python -m unittest discover -v
```

The gate tests cover all 900 canonical combinations, the two READY fixtures,
the owner's WAIT example, blocker precedence, exact failed predicates, missing
and malformed inputs, no candidate inferred from unrelated fields, input/result
isolation, no I/O, footer and Telegram length. All these tests use stdlib only,
so V8's dependency-free discovery can execute them unchanged.

`tests/fixtures/bitman_readiness_base.json` adds SHA256 guards captured from the
exact production base (only CRLF-to-LF normalization) for all frozen files,
V8 tests/runtime present in this branch, Guardian/Copilot/protections/execution,
ML RSI math/observer/recovery/alert sources, and the existing data/child boundary.
Existing guards and tests are not rebaselined or weakened. The existing V8 audit
also checks its separate frozen executor reference. Transport integration still
compares the same prepared input/snapshot and rendered output for direct versus
private acquisition; the underlying snapshots do not acquire readiness fields.

The new `Bitman operability gate` workflow runs dedicated gates, isolation,
transport and existing safety checks. All six existing workflows remain
unchanged, including full Guardian/ML RSI regression and V8 checks.

No backtests, parameter search, retuning or new strategy rules inside the engine.
No merge, deploy, Railway or production configuration changes in this phase.
`TRADE AUTHORITY: NONE`.

Local validation on 2026-10-19 (Python 3.12.10): **743 passed, 0 failed, 0 skipped**
in full discovery; **166 passed** in the targeted gate/manual/market-data/commands/
canary suite. Of these, **46 are new tests**, including the 900-combination matrix.
`mlrsi_safety_audit.py` returned `MLRSI_SAFETY_AUDIT_OK`. Dependency-free discovery
also passed: 62 executed tests (including all 46 new tests), with the 15 existing
dependency-requiring module skips. No existing test or workflow was changed.

Observed outputs from the contract fixtures (the positive fixtures are synthetic,
not forward observations):

| Input | `status` | `operate` | `side` |
| --- | --- | --- | --- |
| Owner's TRANSITION / WEAK example above | WAIT | false | null |
| UP / STRONG / A / impulse_up / SUPPORTING | READY_LONG | true | LONG |
| DOWN / STRONG / A / impulse_down / SUPPORTING | READY_SHORT | true | SHORT |

The positive render headings are respectively
`🎯 ¿OPERAR AHORA? SÍ — CANDIDATO LONG` and
`🎯 ¿OPERAR AHORA? SÍ — CANDIDATO SHORT`; the owner example displays
`🎯 ¿OPERAR AHORA? NO` followed by `⏳ WAIT`.
