# Visual / temporal verification — not a backtest

Base: `9d40020d539033cefb8f01734db8c6a6fdbba2e3`.
Code and examples are tracked under `research/kill_zones_visual_v1/` in the
separate branch `kill-zones-visual-prototype-v1`.

- New geometry/causality/isolation suite: **34 passed / 0 failed**.
- Full `unittest discover -v`, Python **3.12.12**: **1,067 passed / 0 failed**.
- ML RSI safety audit: passed, Guardian protection AST and frozen V8 unchanged.
- Weekly boundary `--require-v8`: 9 passed; readiness boundary: 7 passed.
- All 900 readiness results and approved normalized hash preserved:
  WAIT 780, WATCH_LONG 59, WATCH_SHORT 59, READY_LONG 1, READY_SHORT 1;
  `1ffcf53c6b056e7bdf3b780f1fc4ebce49616363a66467e573c5c1a2ef71f014`.
- Compile, deterministic SVG/JSON regeneration, excerpt SHA256 and patch whitespace checked.
- No non-research runtime file changed; one isolated research workflow added.

Environment note: an initial Python 3.13.7 run had two AST-hash canary failures,
also reproduced on the unchanged base. They both pass under the CI version
Python 3.12. No canary/baseline/protocol was weakened or refrozen. The local 3.12
run used a process-local `PYTHONTZPATH` pointing to already installed IANA data;
no production environment or Railway variable was changed.

## Public historical pictures

All complete session pairs in the fixed 72-hour excerpt are shown. Not a
performance sample, not a virgin holdout, no ranking by later outcome.

| London date (New York) | Observation |
|---|---|
| 2026-09-01 | BOX_ORDER_AMBIGUOUS — boxes retained, no geometry forced |
| 2026-09-02 | BOX_ORDER_AMBIGUOUS — initial fixed display day, retained |
| 2026-09-03 | UP body crossing, available 15:00 UTC; next-open plan rejected |

On 2026-09-03 the projected target is **79,105.30**, next-open reference entry
**80,508.40**, structural SL **76,927.30**. The target is already behind entry,
so `REJECTED_STOP_TARGET_ORDER`. No target was moved and no second entry was
sought. This establishes correct rejection/wiring, not edge or video parity.

Separate synthetic UP and DOWN controls show complete valid reference plans,
clearly labelled artificial. They are not independent market evidence.

No historical trade exits, winning/losing results, fees/funding returns, PnL,
optimizer or new backtest were computed. The extension of the measurement as
the trigger remains an explicitly unverified interpretation. Review the drawings
before considering a subsequent fixed evaluation/forward protocol.

PR #40 remains untouched at `a612c4200eeecc41952393d02ff371f9daea0b0b`.
Guardian V2, V8, ML RSI, readiness, frozen engine, weekly V1, market-data,
Railway and Telegram unchanged. No merge, deployment, activation or orders.

SHADOW ONLY. TRADE AUTHORITY: NONE.
