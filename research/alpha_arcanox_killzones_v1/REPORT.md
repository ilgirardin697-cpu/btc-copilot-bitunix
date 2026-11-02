# Alpha Arcanox — implementation and source fidelity

**Decision: NO-GO for operational PAPER acceptance until level formulas and
the original market/time identity are verified.** No backtest or return is computed.
The detector/risk/plotting implementation works; missing indicator mathematics
is deliberately not replaced by a lookalike strategy.

## Source actually inspected

Five original JPGs and `LEEME_Codex.txt` in the owner's `referencias_video/alpha_arcanox/`.
Labels are legible in 01, 04 and 05. Original JPG SHA256s are recorded in
[owner_reference.json](fixtures/owner_reference.json). They are unchanged and
not published as raw images by this commit.

The existing [Descript source project](https://web.descript.com/fa46b015-7440-4d90-af6d-de39f4b34a1a/9faf8)
was accessible and its transcript was recovered read-only for this study.
The full transcript remains LOCAL ONLY / gitignored; its SHA256 and relevant
time segments are in [source_audit.json](fixtures/source_audit.json).
Earlier PR #40 / Visual V1 source audits are frozen and were not rewritten.
Public searches did not identify an attributable Pine/source of Alpha's indicator;
unrelated public Killzone scripts were excluded.

The video describes a finite measurement, a clone and its placement. Around
09:55–10:40 it discusses high/low and body confirmation; it does not establish
the old infinite-extension hypothesis. Circle placement and practical TP offset
are visual, without a verified numerical indicator formula. No prior projection,
symmetric multiplier or inferred offset was reused.

## What matches and what does not

| Level | Visible value / faithful label transcription | Formula | Causal numerical replay |
|---|---:|---|---|
| HIGH | 78285.00 | NO VERIFICADO | unavailable |
| LOW | 77517.20 | NO VERIFICADO | unavailable |
| SUPERIOR | 78653.44 | NO VERIFICADO | unavailable |
| INFERIOR | 77095.25 | NO VERIFICADO | unavailable |

HIGH visually aligns with the London box top and LOW with the Asia box bottom
in this example. That supports a visual hypothesis, not proof of the general
formula: exact candle OHLC/times and original venue are missing. Computed union
extremes stay explicitly separate from the four official levels.

The observed gaps SUPERIOR−HIGH = **368.44**, LOW−INFERIOR = **421.95** differ.
No symmetric extension or fitted multiplier is assumed. The reconstructed
level diagram copies observed labels only; it is NOT an independent calculation.
There is no fabricated zero formula-error or percentage-parity score.

In image 01 the LONG marker is below a candle body spanning HIGH. The owner's
new rule requires the entire body outside; that marker is therefore not itself
proof of the requested confirmation. Other later bodies can appear outside,
but exact O/C, UTC and closed status cannot be certified from these pictures.
Visible prices such as 78486.49 / 78646.01 include a running countdown and are
not substituted for the confirming candle's close. No entry/ATR/SL is inferred.

## Implemented rules and evidence

UTC−4 fixed and the exact 5+4 opening-hour schedule replace all older sessions.
All calculations use closed candles and an explicit cutoff. Session availability
is 05:00 local / 09:00 UTC. No earlier signal is evaluated. ATR14 is Wilder RMA
with the first 14 provided true ranges as seed; previous close enters TR. Its
numeric parity to another platform also requires identical source/history seed.

Whole-body LONG/SHORT, equality rejection, first confirmation only, close-price
reference, 0.20 ATR structural stop, price ordering, explicit net costs, 1.5 R/R,
0.25% simulated-capital sizing and 1x notional cap are implemented and unit tested.
These are the owner's research decisions, not an assertion that Alpha's internal
LONG marker uses the same conditions. A rejected first confirmation is retained;
it is not replaced by a later favorable entry. Stops do not widen on replay.

Cost arithmetic uses separate adverse entry/stop/target scenarios. Entry/exit fees
are counted once within each mutually exclusive stop/target scenario, plus an
explicit nonnegative funding reserve. Actual fills and latency remain unknown.
The 6bp/leg fee and 5bp/leg slippage demonstration is an explicit assumption,
not verified Bitunix/exchange costs. Missing cost inputs block the risk filter.

[Gallery](artifacts/index.html): exact label reconstruction without invented candles,
and a **separate** older public USD-M session-mechanics demo, never passed off as
the source market. [Artificial risk controls](artifacts/synthetic_risk_controls.json)
are synthetic arithmetic checks, not events, observed trades or profitability.
[Future /killzone preview](artifacts/killzone_OFFLINE_preview.txt) is offline only.

## Exact remaining blockers

1. The original indicator's source or complete mathematical rule for all four
   levels, including source prices, anchor/offset rules and availability times.
   These five images do not determine a unique formula. More favorable screenshots
   or tuning a projection to 4 values would not establish it.
2. Original exchange, Spot/perpetual and ticker; dated 1H OHLC and indicator output
   with UTC timestamps/settings for the same example, enough prior ATR history.
3. The actual confirming candle under the owner's stricter whole-body rule, so
   theoretical entry, ATR, SL, TP and cost-adjusted R/R can be checked independently.

Until then `APPROVED_FORMULA_IDS` is empty and all real-data PAPER decisions are
RECHAZADA / FORMULA_ORIGINAL_NO_VERIFICADA. The four reference values cannot be
promoted to a formula by a JSON flag. Only synthetic unit tests temporarily
register an explicitly artificial provider to exercise accepted/rejected paths.

No historical performance evaluation, optimization, new forward collector,
Telegram route, production variable, merge or deployment. No order/client access.
PR #40, Visual V1, Guardian V2, V8, readiness, ML RSI and weekly V1 remain intact.

## Validation performed

- 47 offline tests passed: schedules, fixed offset over DST dates, strict body
  inequalities including red LONG/green SHORT bodies, equality/wicks, causal
  availability, ATR, reference-close price, no stop widening, rejected-first
  retention, net costs, 1.5 minimum, risk sizing, unknown-level blockade and isolation.
- Full repository discovery under Python 3.12.12: **1,080 tests / 0 failed**.
- A separate check against the unchanged public frozen Wilder RMA, using the
  same 72 public closed bars, matched all 59 finite ATR values; maximum absolute
  difference **1.2505552149377763e-12**, below 1e-9 tolerance. This is public formula
  parity with identical input/seed, NOT Alpha indicator/TradingView source parity.
- Compile and deterministic evidence regeneration passed. Five original image
  hashes verified before/after the local side-by-side comparison.
- Dedicated offline workflow added; no existing workflow or runtime changed.

SHADOW ONLY. TRADE AUTHORITY: NONE.
