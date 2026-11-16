# I-GOD H1 forward shadow audit — PREPARED, NOT ACTIVATED

SHADOW ONLY. TRADE AUTHORITY: NONE. No observed edge has been established.

This new laboratory prepares prospective recording after the historical
investigation closed. It does not activate a collector, scheduler, service,
Telegram sender or exchange client. Default `Observer(..., enabled=False)`
performs no filesystem/network work. No production file is changed.

The original PRs #46–#51 remain intact. This branch is based on PR #51
`3fcfc793f1db1c37dd9a3e905c9e7e1368f0c544`; its diff adds only this directory.
It is a stacked research draft, not a proposal to merge those studies into
production. There is no new backtest and no prospective market sample here.
All newly executed tests use synthetic inputs and temporary directories.

## What is separate

| Component | Meaning | Can change either model's emission? |
|---|---|---|
| TURN22_FORWARD_V1 | Frozen PR #50 2+2 patterns and mirrors | Only its own original rules |
| TURN11_EXPLORATORY_V1 | Exactly one opposing + one confirming slope; necessary timing indices adapted | Only this independently identified model |
| OBSERVATIONAL_FACTS_V1 | AO/ADX atomics, named Konkorde events, BBWP, closed MTF, causal price facts, three WATCH labels | No |
| Inclusive regime census | All eligible hours and both directional outcomes, including signal neighbors | No |

The owner's report of Claude's audit is retained as context: 1+1 has not shown
a reliable advantage over a regime baseline. We do not repeat historical
optimization, choose a winner, or interpret another chat's narrative as data.

Read [SPEC.md](SPEC.md) for exact conventions, clocks, cohort and limitations.
`protocols.json` and `manifest.json` bind the **new, inactive** registry to source
and old dependencies; existing frozen protocol hashes have not been changed.
The final new registry hash is in `protocol.EXPECTED` and `validation.json`.
After review, changes require a new registry/version and separate journal.

## Review and reproduce offline

From this branch's repository root with Python 3.12, NumPy and tzdata available:

```powershell
python -m unittest discover -s research/confluence_1h_phase2/event_proximity/strict_series_audit/turn_intensity_phase1/phase1b_diagnostics/forward_shadow -t . -v
python -m unittest discover -v
python mlrsi_safety_audit.py
python test_bitman_weekly_boundary.py --require-v8 -v
python test_bitman_readiness_boundary.py --require-v8 -v
git diff --check
```

Existing CI discovers the new tests through the full repository suite. No
deployment workflow or production dependency was added. On a long Windows
checkout, compile source in memory or use a short worktree path: temporary
`.pyc` paths from `compileall` can exceed MAX_PATH, although imports/tests work.
Linux CI uses the existing compile steps.

## Authorization still required

This PR prepares receipt-driven observer logic, not continuous capture. A
subsequent review must approve an independent collector, legitimate access to
unsigned public USD-M data, isolated durable storage, clock synchronization,
health monitoring, backup/external hash checkpoints and restart/load behavior.
No API credentials, real account information or trading permissions are needed.

The cohort dates remain 2026-11-17 to 2027-11-17 UTC. If activation misses the
start, missing hours stay missing; neither dates nor acceptance criteria move
silently. Coverage and sample adequacy may therefore prevent inference.

No orders, stops, TP1, break-even, trailing or leverage logic is implemented.
Guardian, V8, ML RSI, readiness, market-data and BITMAN_WEEKLY_FORWARD_V1 are
unchanged. No Railway/Bitunix calls, Telegram messages, merge or deploy occurred.
