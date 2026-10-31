# Kill Zones single-segment visual prototype V1

ID: `KZ_SINGLE_SEGMENT_VISUAL_V1`. PAPER / SHADOW ONLY. TRADE AUTHORITY: NONE.
Status: **one experimental interpretation, NOT verified original strategy**.
No performance evaluation, parameter search, live data collector or runtime integration.

## Confirmed concept and source limits

The video explanation supplied by the owner uses 1H BTCUSDT, Asia 20:00–00:00,
London 02:00–05:00, ONE finite measurement segment between relevant opposite
box extremes, and a geometry-preserving clone. Its far endpoint is the projected
target. Confirmation requires a closed candle, not a wick. Practical TP can be
before the theoretical target; no exact offset is demonstrated.

This implements the LINE-break interpretation requested for the 09:55 segment,
not a generic horizontal rectangle breakout. The frame supplied nearest that
moment is 10:11; the full transcript was reported by the owner, not independently
received here. **The frames do not prove that the measurement itself is the
trigger line, or which extension is used.** This prototype chooses that hypothesis
explicitly. No pair of HH/LL diagonals from PR #40 is used or imported.

Source images and the previous SPEC_V1 remain the visual reference. Image hashes,
the prior specification hash and evidence limitations are in `source_audit.json`.
Photograph pixels are not exact timestamps/prices. Scale and venue of the original
chart are not certified. No numeric or full-method parity is claimed.

## Single frozen interpretation (automation assumptions, not demonstrated rules)

1. **Clock / venue:** `America/New_York` with DST; BTCUSDT
   `BINANCE_USDM_PERPETUAL`, linear price axis. This research choice does not
   prove the original chart's timezone, scale or venue. No fixed-UTC−4 comparator.
2. Trading day d is London's date. Sessions are half-open intervals
   `[d−1 20:00,d 00:00)` and `[d 02:00,d 05:00)`. Use all complete 1H candles,
   wick highs/lows; earliest candle wins tied extrema. Missing/duplicated hours,
   nonexistent or ambiguous local boundaries fail closed. Never invent a DST hour.
3. Freeze both boxes only at London's end. A box is lower only if BOTH its high
   and low are strictly lower than the other's. Nested/equal boxes are ambiguous:
   show boxes, record rejection, do not substitute a geometry.
4. **A** = lower box's low at its actual candle OPEN timestamp.
   **B** = upper box's high at its actual candle OPEN timestamp. One segment A–B.
   All extrema are known at freezing. Equal endpoint times cannot define L(t): reject.
   These precise endpoint/tie choices are automation assumptions, not proven snaps.
5. In linear time/price coordinates let `v=B−A`. UP copy: `A′=C`, `B′=C+v`,
   with `C=(freeze_time, lower.high)`. DOWN copy: `B′=C`, `A′=C−v`,
   with `C=(freeze_time, upper.low)`. Only the confirmed side's copy is shown;
   absent confirmation, UP is a clearly labelled geometry preview. C's exact
   time/price is an assumption. Preserve BOTH components, no scaling/rotation.
6. **Trigger line = infinite extension of that SAME A–B segment**:
   `L(t)=pA+(pB−pA)*(t−tA)/(tB−tA)`. A candle is plotted at its OPEN time x,
   so evaluate `L(candle_open)`. Its OHLC is usable only at `candle_open+1h`.
   Do not evaluate the line at an inconsistent candle-close x coordinate.
7. Test only candles OPENING at/after freezing and CLOSING at/before the next
   Asia start (20:00 local). UP: `open <= L < close`. DOWN:
   `close < L <= open`. This chooses a body actually crossing the line with
   a strict closing inequality. Wick-only, close equality and bodies entirely
   outside do not confirm. This body definition is an assumption; the video
   does not quantify it. A line moving past an unchanged price is not enough.
8. Take the FIRST such confirmation per session pair. Never retry that day if
   the resulting plan is rejected. Expiry and one-opportunity limit are assumptions.

## Reference entry and SL for later simulation

Signal available at the confirming candle's CLOSE. Earliest reference entry is
the NEXT 1H OPEN at that boundary, reading only that open, not its later H/L/C.
If absent: `ENTRY_PENDING`. This is a zero-latency price reference, not an actual
or guaranteed fill. Fees, funding, spread, latency and slippage are **not yet
assessed** and must be fixed before any future performance test.

Structural SL is frozen at the lower box's low for UP or upper box's high for
DOWN. Target is the UP clone's upper endpoint or DOWN clone's lower endpoint,
NOT `L(confirmation)+range`. Both SL and next-open entry are added conventions.
Require `SL < entry < target` for UP, or `target < entry < SL` for DOWN.
Otherwise `REJECTED_STOP_TARGET_ORDER`: retain the geometry and reason; do not
move the target, change sides or find another entry. No size, account or leverage.

No TP-before-target offset, holding-time exit or stop/target intrabar resolution
is invented here. This phase defines and draws the reference plan; it does not
run trades or measure profit. Target endpoint TIME preserves vector geometry,
not a forecast of arrival. The clone is not a second breakout line.

## Initial verification and next boundary

Use the entire predetermined public excerpt 2026-09-01 through 2026-09-03 UTC.
The first display day was fixed as 2026-09-02 BEFORE reading signals; it was
ambiguous. Display all three complete session pairs, including unavailable and
rejected cases, rather than select a good-looking example. Known historical
data, **NO VIRGIN HOLDOUT**. Separate artificial UP/DOWN controls prove wiring,
not profitability or independent visual parity. No winner/loser, hit rate or PnL.

Tests cover clone vectors, real timestamps, wick rejection, closed availability,
next-open-only access, deterministic replay, unchanged prefixes, missing data,
DST, invalid plan rejection and absence of production consumers. Before any
future evaluation, review this chosen line/anchor interpretation on the drawings
and predeclare remaining fill/cost/exit rules. Never optimize it on past outcomes.

PR #40 remains frozen and excluded as a faithful reproduction. No Guardian V2,
V8, ML RSI, readiness, market-data, Telegram, Railway or weekly V1 changes.
