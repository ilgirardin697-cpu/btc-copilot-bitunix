# Alpha Arcanox — owner rules V1, independent offline prototype

**SHADOW ONLY. TRADE AUTHORITY: NONE. No network, orders, daemon or Telegram integration.**
Base: `9d40020d539033cefb8f01734db8c6a6fdbba2e3`.
Branch: `kill-zones-alpha-arcanox-v1`. All files here are Git-tracked research,
even though the separate working checkout lives physically under a cache folder.

Read [REPORT](REPORT.md) and open [the evidence gallery](artifacts/index.html).
The five source images were visually inspected. Their four labels are verified
transcriptions, **not verified level formulas**. Original ticker, bar timestamps
and market OHLC are unknown. No source-level parity or real confirmation is invented.

## Implemented

- Fixed UTC−4, 1H: Asia opens 20,21,22,23,00; London 01,02,03,04.
- Freeze at 05:00 fixed UTC−4 = 09:00 UTC, all year. No New York DST dependency.
- Strict whole-body `min(O,C)>HIGH` / `max(O,C)<LOW`; wick/cross/equality rejected.
- The first technical confirmation only, including a subsequent risk rejection.
- Theoretical signal entry = confirming CLOSE, never claimed as an executable fill.
- Wilder ATR14 1H; SL HIGH−0.20 ATR / LOW+0.20 ATR, fixed at confirmation.
- TP SUPERIOR / INFERIOR; invalid price order rejected.
- Explicit assumed fees/slippage/funding reserve; net R/R >=1.5; sizing to
  0.25% simulated capital at estimated stop, also capped to 1x notional.
- Render functions support all levels, confirmation, theoretical entry, SL and
  TP when verified inputs exist; artificial tests exercise that path. Current
  real-data snapshots intentionally have no official levels or accepted plan.

`core.levels_for_pair()` returns unknown official levels. Session high/low and
union extremes are calculated as named OHLC statistics, **not aliases for the
original indicator's HIGH/LOW**. `APPROVED_FORMULA_IDS` is empty: no fixture,
manual reference, command-line flag or JSON `verified` field can turn it on.
A source-backed implementation is required, not a numerical fit to screenshots.

## Reproduce (Python 3.12+, stdlib only)

```sh
python -m unittest research.alpha_arcanox_killzones_v1.test_alpha -v
python -m research.alpha_arcanox_killzones_v1.build
python -m research.alpha_arcanox_killzones_v1.compare_source \
  --source-dir /local/owner/referencias_video/alpha_arcanox \
  --out research/cache/alpha_source_comparison.svg
python -m research.alpha_arcanox_killzones_v1 \
  --csv research/alpha_arcanox_killzones_v1/fixtures/public_sessions_demo.csv \
  --manifest research/alpha_arcanox_killzones_v1/fixtures/public_data_manifest.json \
  --day 2026-09-02 --as-of 2026-09-02T14:00:00Z --capital 10000 \
  --costs research/alpha_arcanox_killzones_v1/fixtures/illustrative_costs.json \
  --out research/cache/alpha_cli_demo
```

The public historical CSV is BTCUSDT Binance USD-M used ONLY to check sessions
and ATR mechanics. It is **not** the original Alpha example or an independent
holdout. No Spot/perpetual/exchange identity is assigned to the source screenshots.
Its manifest and SHA256 are checked. No new data downloader or backtest exists.
The source-comparison command verifies all five image hashes and embeds unchanged
source bytes in a local SVG. It refuses output outside this checkout's gitignored
`research/cache/` to avoid accidentally publishing private source pictures.

Cost numbers are explicit illustrative assumptions, not account/venue facts.
The separate entry/SL/TP adverse fill scenarios are NOT observed executable
prices. No latency, borrow, gap, liquidation or guaranteed capital-loss model
is claimed. An explicit zero funding reserve is a scenario, not an assertion
that funding is absent. Funding/latency/real fills must be measured in a future
validated evaluation. Rounding to 0.000001 BTC is simulation granularity, not
an exchange lot rule. No automatic leverage change or position is possible.

The observation cutoff is explicit; no old 12:00/20:00 expiry is imported.
Multi-day expiry, rollover and overlapping-position policies remain to be fixed
before any later historical/forward execution simulation. No such simulation runs.
At exactly 05:00 the fully closed 04:00 candle can be evaluated, never before;
this follows the availability rule without imposing an extra wait candle.

The prospective `/killzone` output is plain offline text only. It registers no
command, poller, webhook, sender, flag, Railway service or execution path.
PR #40, Visual V1, Guardian V2, V8, ML RSI, readiness and weekly V1 untouched.
