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
snapshot. `SETUP READY` means technically aligned for manual review only. It
does not establish profitability, historical edge or suitability for an account.
The engine remains `INCONCLUSIVE DIRECTION ENGINE`.

WATCH means UP/DOWN already exists, no blocking condition is present, and at
least one remaining READY gate is missing. WAIT means a blocking condition or
unknown input prevents a candidate. Both always display `OPERATIVA BITMAN: NO OPERAR`.
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

The result contains `gates_ready`, `status`, `side`, deterministic `reason_codes`
and structured `missing_conditions` (`field`, sanitized `actual`, `required`).
The only statuses are WAIT, WATCH_LONG, WATCH_SHORT, READY_LONG and READY_SHORT.
`gates_ready` is true only for the two READY statuses. WAIT has `side=None`.
It conveys no execution authority; no previous boolean-name alias is retained.
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
displayed ML RSI RED/NEUTRAL/NEUTRAL) yields **WAIT / gates_ready=false / side=None**.
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
Unavailable also states `OPERATIVA BITMAN: NO OPERAR / WAIT`; it cannot display a candidate.
No sender/retry logic, authorization policy or poller is added.

## Validation

```text
python -m unittest test_bitman_readiness -v
python test_bitman_readiness_boundary.py --require-v8 -v
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

`tests/fixtures/bitman_readiness_approved.json` records the reviewed commit
`1875f91e0c8515c267129c6e9cf8ccc6bc4306fa`, its original gate-source SHA256,
and a digest of all 900 complete results after the boolean-key rename only.
The tests require the entire gate source to match that approved source when
exactly its three result keywords are restored for comparison. They separately
compare all result data, including sides, reason codes and missing conditions.
The unchanged matrix contains 780 WAIT, 59 WATCH_LONG, 59 WATCH_SHORT,
one READY_LONG and one READY_SHORT. These are synthetic combinations, not
observations or estimates of market frequency. Every combination is also
rendered to check the manual wording, original footer and Telegram size limit.

## Architecture boundary enforced by CI

`test_bitman_readiness_boundary.py` scans every repository Python source,
including new non-ignored modules, without importing execution code. Only
`bitman_manual/render.py` may consume readiness or `gates_ready`; the gate
definition is the other reserved source. All other modules are rejected for
direct, aliased, relative or literal dynamic readiness imports, gate-key/attribute
access, or renderer-helper reexports. The only existing passive renderer routes
are the host's `render`/`unavailable` imports and Guardian commands' `unavailable`.
The renderer itself may retain only its exact pure imports. No runtime guard,
execution hook or authority field is added to Guardian.

The scan includes `trade_guardian.py`, `guardian_bitunix.py`, `guardian_risk.py`,
`live_auto.py`, `main.py`, and any new module regardless of its filename or order
method names. The separate frozen V8 executor, client, runtime and notification
sources are read from `origin/v8-real-executor`, checked against the existing
immutable SHA/hash manifest, and scanned too. Mutation tests reject synthetic
imports and open/close/cancel uses for every required execution path and new
helper modules, without editing those files or making any orders.

The dedicated workflow runs this audit with `--require-v8`: a missing V8 ref
fails CI. Only the existing shallow dependency-free V8 workflow may skip that
separate-ref test; it still scans all sources present in its checkout. This is
a conservative source guard and regression check, not a sandbox for deliberately
obfuscated Python. All existing protected-source hashes and AST canaries remain
unchanged; the six pre-existing workflows remain unchanged.

Observed outputs from the contract fixtures (the positive fixtures are synthetic,
not forward observations):

| Input | `status` | `gates_ready` | `side` |
| --- | --- | --- | --- |
| Owner's TRANSITION / WEAK example above | WAIT | false | null |
| UP / STRONG / A / impulse_up / SUPPORTING | READY_LONG | true | LONG |
| DOWN / STRONG / A / impulse_down / SUPPORTING | READY_SHORT | true | SHORT |

The positive render headings are respectively
`🎯 OPERATIVA BITMAN: SETUP READY — CANDIDATO LONG` and
`🎯 OPERATIVA BITMAN: SETUP READY — CANDIDATO SHORT`; the owner example displays
`🎯 OPERATIVA BITMAN: NO OPERAR` followed by `⏳ WAIT`.

READY also states:

```text
⚠️ SETUP READY = gates técnicos alineados.
No garantiza rentabilidad y no es una orden automática.
```

Local hardening validation (Python 3.12.10): **754 passed, 0 failed, 0 skipped**
in full discovery. Targeted gates/boundary/manual/market-data/commands/canaries:
**177 passed**; gates/display/protected sources: **50 tests**; mandatory separate
architecture/V8 audit: **7 passed**. `MLRSI_SAFETY_AUDIT_OK`; compilation and
patch whitespace checks passed. Dependency-free discovery also passed with
73 executed tests and the 15 existing dependency-requiring module skips.
