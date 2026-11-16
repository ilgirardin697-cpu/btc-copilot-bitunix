# Hardening V2 — offline technical audit

Decision: **NO-GO for continuous activation.** No trading authority.

Base PR #52: `9f307fd9feda6279253c0a0813d49b47d3f1d9b2`. New registry: `df5476bbd984dd7f2dd23d52eaa956c9adc0429b7f785782a880cf4de99e4c10`.
V1 remains unchanged, including its old window and hashes. Source changes are additions only under this new V2 directory.

| Qualification | Actual result |
|---|---:|
| New tests | 33 passed /0 failed |
| Synthetic closed hours after warmup | 8760 |
| Warmup hours | 6000 |
| Exact full-reference arrays | 78 |
| TURN22 vs PR #50 | exact |
| TURN11 vs PR #52 | exact |
| Closed MTF context | exact |
| Peak process RSS | 207.87 MiB |
| Local storage after annual test | 348.89 MiB |
| Wall time, including reference checks | 461.162s |
| Process CPU time | 298.781s |
| Mean /p95 processing per hour | 0.028029s /0.040492s |
| Prospective records | 0 |

Restart measurements (same-state hashes, increasing prefix):
[
  {
    "hours": 2190,
    "seconds": 9.404385599773377,
    "exact_state": true
  },
  {
    "hours": 4380,
    "seconds": 12.607667999807745,
    "exact_state": true
  },
  {
    "hours": 8760,
    "seconds": 28.95777720026672,
    "exact_state": true
  }
]

These are Windows local technical measurements with generated public-schema prices and fake funding receipts. They are not real trades, market-event frequency, profitability or a Railway/cloud SLA. Host load and filesystem behavior affect times. No test record enters the prospective cohort. Raw annual synthetic journal was temporary; the seed/input hash and generator reproduce it.

The inclusive estimator jointly resamples calendar7day blocks for labels and all same-side/month/regime/volatility baseline hours, including neighbors. Six primary contrasts retain Holm; insufficient cells receive p=1. At least20 occupied blocks and adequate ESS/coverage remain required. Explanatory1+1/ALL/Q90/4H/24H/comparative facts never replace the primary.

Power planning used 18995 already-inspected development hours before2025, source SHA `5b2544c9bf353cedb77a07781ffe9e6202b12513c0c10f3d25bca67756a4825a`. Residual sigmas: [0.01703994625523474, 0.01710846660532593]; fixed conservative planning sigma:0.04. Required effective n:16751 per contrast. The25h cooldown allows only351–352 raw events per12calendar months before Q75. **Confirmatory power is infeasible.** This can only be a descriptive observation project under the unchanged design; no thresholds, MDE or duration were loosened.

Local two-process lock exclusion is exercised by tests. Real-volume probe: **NOT RUN**. External provider/versioning/IAM and trusted ACK transport: **NOT CONFIGURED**. New cohort date: **NOT APPROVED**. Public-source publication/revision measurement and pinned Linux image qualification: **PENDING**. These limitations prevent activation; a local backup export is not an independent anchor.

No Guardian/V8/ML RSI/Bitman/runtime, Railway, Bitunix or Telegram change. No merge/deploy/capture/orders. See README for immutable cohort, token eligibility, revisions/child sessions, terminal funding and source-schema rules.
