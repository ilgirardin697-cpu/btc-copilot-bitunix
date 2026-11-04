# Validation

- Python 3.12 full discovery: **1082 passed, 0 failed**.
- Dedicated research tests: **49 passed, 0 failed**.
- ML RSI / Guardian safety audit: PASS. Separate pinned V8 reference: PASS.
- Weekly and readiness architecture boundary suites: 9 + 7 PASS.
- Readiness remains 900 cases: WAIT 780, WATCH_LONG 59, WATCH_SHORT 59,
  READY_LONG 1, READY_SHORT 1. Approved normalized result hash unchanged.
- All 162 protected base files unchanged; new research has no execution/network client.
- Protocol and verbatim reference hashes checked before evaluation.
- Three previously audited real Pine geometry records reused, not new platform evidence.
- All seven numerical output files reproduced byte-for-byte, including full MTM payload.
- Artifact checksum manifest verified; no optimization, prospective events or activation.

Full local logs remain ignored in research/cache/optimal_entry_checks. Hashes and
the reproduction/readiness proof are in artifacts/validation.json.
The dedicated offline workflow is .github/workflows/killzone-optimal-entry.yml.
Remote CI status must be read for the actual pushed HEAD; local success is not
presented as remote workflow success.

The first remote V8 dependency-free discovery exposed a research test import of
NumPy in a job that intentionally installs no runtime dependencies. Only this
new research test's import bootstrap was changed to SkipTest when NumPy is
absent, matching existing repository conventions. The dedicated research job
explicitly imports NumPy/timezone data before running all 49 tests, so it cannot
silently pass by skipping. No V8 source, existing workflow or statistical rule
was changed to address this integration failure.

The SVG-only formatting pass removes Matplotlib trailing whitespace and uses
text fonts. It does not change numerical inputs, trades, results or classifications.

SHADOW ONLY. TRADE AUTHORITY: NONE.
