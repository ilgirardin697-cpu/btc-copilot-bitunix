# Verification and provenance of the research

## Pre-outcome trail
- Base: 9d40020d539033cefb8f01734db8c6a6fdbba2e3.
- 5ccea82: original specification and owner-provided source segment audit.
- 9b7e77f: implemented rules, data manifest hashes, source lock and tests,
  committed before first outcome execution.
- 218783b: four owner-requested TP-offset sensitivities fixed before their own
  outcome run, explicitly post-hoc relative to the original analysis.
- No signal, entry, stop, target, cost, bootstrap or classification tuning after outcomes.
- No actual transcript or diagonal viewed. All exact-source parity remains unproven.

## Explicit reporting-only amendments
The original lock was 44a6bd39e7e30a8a63c52c4ac1b8ea6a8ff89e015140b1760d0757c2e7f3f680.
The current main lock is bd0aa0b041a78ddfe318f6d05576bc731e9c707f66ace8d1bf8a25f12055249c.
Both amendments and their predecessor hashes are retained in protocol_lock.json:
1. A reserved word in a report-prose string triggered the existing architecture
   canary. Only prose changed; the canary itself was not weakened or edited.
2. Descriptive annual exposure denominators for 2024/2025 now use their own
   calendar split. No trades, net/gross results, costs, drawdown, confidence
   intervals, ablations, classifications or examples changed.
Comparison of first and final results found only the main lock field and those
24 annual exposure metadata fields different. Every other numeric result was identical.
No formula or frozen runtime protocol was refrozen.

## Test scope
64 new offline tests: sessions/DST, earliest tied anchors, no wick entry, causal
prefix invariance, missing/duplicate data, exact aggregation, future-extreme
immunity, next-open fills, stops/targets, gap handling, 5m stop-first ambiguity,
fees/slippage once, real timestamp funding convention, expiry, overlapping
positions, frozen formula parity, already-closed higher frames, deterministic
bootstrap, small-sample classification, offset signs/amounts and production isolation.

The repository's complete suite was run on Python 3.12: 1097 tests, zero failures.
A first Python 3.13 run hit two pre-existing ast.dump hash-format baseline
differences. Both were reproduced unchanged on the approved base commit, and
both pass under Python 3.12, matching their existing CI. No baseline was replaced.
The report-prose reserved word was corrected independently as described above.
MLRSI_PUBLIC_REBOOTSTRAP / MLRSI_CLOSED_CANDLE_REVISED is a diagnostic from a
passing existing fixture, not a new ML RSI failure.

Existing audits: ML RSI/Guardian protection AST and V8 frozen hashes pass;
weekly boundary 9 tests and manual-operability boundary 7 tests pass.
The full suite includes the 900 approved operability combinations and protocol V1 checks.
New isolated workflow runs compile, 64 research tests, both source locks and diff check.
All existing workflows remain in place.

## Runtime/source integrity
protocol_lock.json binds LF-normalized hashes of every tracked production Python
source and the public dataset arrays. A production import of this research fails
the new guard. No raw candle/funding files or private journal exports are committed.

Guardian V2 policy hash remains:
62618b461ce7e9ffb678b79790afc0ab52ed227bffc20af8c0406294b671b731

BITMAN_WEEKLY_FORWARD_V1 remains:
d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8

All tracked changes are under research/kill_zones/ plus its isolated CI workflow.
No Railway calls/mutations, deployments, merges, Telegram sends, private account
reads, orders or production flag changes occurred in this research task.
