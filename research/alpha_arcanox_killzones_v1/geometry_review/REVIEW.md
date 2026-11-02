# Vertical geometry review — source images pending

Base: `6aa977782aa7d5e499dd765622350888176a8cfe`, existing Alpha owner-rule prototype.
Separate branch: `alpha-arcanox-vertical-geometry-review`.
This is a geometry-only extension; all 23 parent prototype/source/result files
are checked byte-for-byte against their reviewed Git blobs. No rule or old result
is rewritten. Guardian, V8, readiness, Telegram and Railway remain untouched.

## Current evidence limitation

The latest message describes TWO NEW captures with blue measurement circles,
but those files are not exposed as readable attachments or in the local source
directory. The directory currently contains the earlier five Alpha captures and
11 original video frames. They are NOT substituted for the two new images.

[cases.json](cases.json) keeps two distinct new setup IDs with image/hash/circle
coordinates/anchors UNKNOWN. Neither is assigned the old HIGH=78285.00,
LOW=77517.20, SUPERIOR=78653.44, INFERIOR=77095.25 setup. Even the two new images
are not assumed to describe the same setup until evidence establishes it.

[The symbolic diagram](vertical_contract.svg) illustrates the owner's clarification
only. **It is not a comparison with the absent images.** No price calibration,
market candle, exact anchor or target has been invented to fill that gap.

## Four independent objects

A. Original measurement: explicitly identified upper and lower circles.
B. Upper projection: clone with its LOWER circle at an observed anchor A↑
   inside the lower rectangle; the free circle is the upper one.
C. Lower projection: clone with its UPPER circle at an observed anchor A↓
   inside the upper rectangle; the free circle is the lower one.
D. HIGH/LOW: separate confirmation levels. They are not a segment, a clone,
   or its infinite extrapolation. Existing whole-body owner rules stay unchanged.

The circle roles in B/C follow the stated projection direction without rotation.
**The actual support/contact point within either rectangle remains to be seen.**
Circle center, visible border and internal horizontal level must be distinguished;
an approximate touch in pixels is not an exact price or numerical offset rule.

## Only conditional mathematics is established

Let P+ and P− be the original upper/lower circle PRICES in the SAME setup:

```
H = P+ − P− > 0
UP copy:   lower′ = A↑; upper′ = A↑ + H
DOWN copy: upper′ = A↓; lower′ = A↓ − H
```

These formulas give free-circle endpoints. Naming those endpoints SUPERIOR /
INFERIOR requires observing their relation to the indicator's horizontal labels.
No equality to HIGH+H or LOW−H is claimed: that would additionally require proof
that A↑=HIGH or A↓=LOW, respectively. No anchor is derived backward from a desired
old target, and no symmetry around HIGH/LOW or global session-extreme selection
is presumed. `project()` does not even accept HIGH/LOW or candle timestamps.

Literal screen-space clones separately preserve both apparent components of the
drawn vector, including any slight tilt. Their pixel height is never converted to
USDT without source price evidence. A perfectly vertical segment is valid; there
is no slope/line-at-time API and no path to signal generation.

## Comparison mechanism prepared

`render.comparison()` takes one real image, its SHA256 and explicit annotations:
original circles, all visible anchor alternatives and separately observed HIGH/LOW.
It shows an unmodified original on the left, every documented clone hypothesis
on the right, with padding for endpoints beyond the image. It does not generate
anchors, choose a best fit, calibrate prices or reuse another image's coordinates.
Outputs containing source photos are restricted to gitignored `research/cache/`.

For each new source image, annotations must record the visible feature used:
rectangle edge, visible interior level, or circle contact/center. If alternatives
remain, show ALL of them on that same image with dashed hypotheses. A missing
feature/anchor stays missing; the program does not invent a pixel offset.

`compare_verified_label()` refuses setup mixing and withholds residuals until
same-setup binding and endpoint/label identity are explicitly verified. No old
target is used to rank or choose candidates. Conditional endpoints are not
registered as official levels in the parent prototype; PAPER remains blocked.

## What is and is not reproduced now

- Vertical distance and clone algebra: implemented and tested as a geometric contract.
- Source-image renderer and hypothesis preservation: implemented; source hashes checked.
- Actual original segment / two translated copies from the NEW images: pending files.
- Actual support circles at exact source prices: pending source annotation/calibration.
- Numerical reconstruction of the old four levels: NOT established.
- Original whole-body rules, ATR14, stop, theoretical close entry, 1.5 net R and
  0.25% simulated risk: unchanged, protected by parent source hashes.

Run the geometry/parent regressions:

```sh
python -m unittest research.alpha_arcanox_killzones_v1.test_alpha \
  research.alpha_arcanox_killzones_v1.geometry_review.test_geometry -v
```

After actual files and annotations are available, render one case:

```sh
python -m research.alpha_arcanox_killzones_v1.geometry_review \
  --case /local/one_annotated_case.json --source /local/the_same_capture.png \
  --out research/cache/one_case_comparison.svg
```

No backtest, market download, operational Telegram, orders, merge or deployment.
Validation: 69 tests passed (47 existing owner-rule tests + 22 geometry/isolation
tests). All 23 parent prototype and result files match the reviewed parent hashes.
No real-image comparison or numerical-level-parity test is claimed while the
new source pictures are absent.
SHADOW ONLY. TRADE AUTHORITY: NONE.
