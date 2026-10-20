"""Deterministic report of the independent weekly sequence proxy study."""
from collections import Counter
import csv
import json
from pathlib import Path
import statistics

from research import bitman_weekly_state_machine as sm


def numeric(rows):
    result = []
    for row in rows:
        converted = {}
        for key, value in row.items():
            if value == '':
                converted[key] = None
                continue
            try:
                converted[key] = float(value)
            except ValueError:
                converted[key] = value
        result.append(converted)
    return result


def read_csv(directory, name):
    with (Path(directory)/(name+'.csv')).open(newline='', encoding='utf-8') as stream:
        return numeric(list(csv.DictReader(stream)))


def fmt(value, percent=False):
    if value is None:
        return 'NA'
    if isinstance(value, str):
        return value
    return f'{value*100:.2f}%' if percent else f'{value:.3f}'


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])+'\n'


def conclusion(n):
    # Never promote a tiny historical sample to validated evidence.
    if n < 30:
        return 'INCONCLUSIVE'
    return 'INCONCLUSIVE'  # A larger future study requires a new documented evidence review.


def render(result, summaries, comparisons, temporal, falsification):
    def row(group='SIGNALS', horizon=4, length=4, scope='FULL'):
        return next(r for r in summaries if r['group'] == group and r['scope'] == scope and
                    r['range_weeks'] == length and r['horizon'] == horizon)
    primary, base, turn = row(), row('ALL'), row('VOL_TURN')
    episodes = result['episodes']
    current = result['current']
    lines = ['# BITMAN weekly state-machine research', '',
        '**'+conclusion(primary['n'])+' — NO RUNTIME INTEGRATION.**', '',
        f"The predeclared sequential proxy rules produce **{int(primary['n'])} episodes**, not 263 independent signals. "
        f"The main large-breakout label occurs in {int(primary['true_positive'])}/{int(primary['n'])} episodes "
        f"({fmt(primary['precision'], True)}), versus {int(base['positives'])}/{int(base['n'])} weekly opportunities "
        f"({fmt(base['base_rate'], True)}). Anchor-level recall {fmt(primary['recall'], True)}; lift {fmt(primary['lift'])}. "
        '**INSUFFICIENT FOR CONCLUSION.** These historical results do not establish or refute the creator\'s private indicators.', '',
        '**NO VIRGIN HOLDOUT. HYPOTHESIS FOR FORWARD OBSERVATION only.**', '',
        '**EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN**', '',
        '**EXACT BITMAN VOLATILITY PARITY: NOT PROVEN**', '',
        '## 1. Source: what was reported and what was independently verified', '',
        '[Primary video](https://www.youtube.com/watch?v=v8d3OxE1-_c), approximately minute20 onward. '
        'The owner reports a weekly sequence: same-side oscillator corrections with contracting volatility, followed by '
        'renewed momentum/expansion, or a zero crossing and expansion in the new direction. This report formalizes that supplied account. '
        'It does not treat the relationship as a rule for lower timeframes.', '',
        'The public YouTube watch and oEmbed endpoints returned200; the player title is '
        '“CUANDO SALDRÁ de ese RANGO BITCOIN..???” and playability is OK. Spanish captions were advertised, '
        'but both the advertised track request and plain timedtext returned200 with **zero bytes**. '
        'Web retrieval also failed. The four previously cached transcripts are different videos. '
        'No new vidIQ credits, login, hidden formula retrieval or paid service was used. '
        'An independent transcript of this segment and visual chart dates were **not recovered**. '
        'See [source audit](bitman_weekly_state_machine/source_audit.json).', '',
        '## 2. What is approximated, and unknown modified indicators', '',
        'AO is **OSCILLATOR_PROXY**. The production frozen BBWP formula is **BITMAN_VOLATILITY_PROXY**. '
        'The owner reports that Bitman describes his volatility indicator as modified. Exact settings/formula are unknown. '
        'Neither visual similarity, the public video title, nor another video naming AO proves parity for this chart. '
        'No values or parameters were adjusted to fit examples. Statistical conclusions below concern these proxies only.', '',
        '## 3. Dataset provenance and independence from PR #30', '',
        'Base `9c660035f912be4640f09cf6e2d4c48583c20b04`. '
        'Reuse only the public data snapshot, audit manifest, aggregation/validation helpers and immutable indicator function '
        'from [PR #30](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/pull/30), '
        'commit `c1c56bd1c4c87ad0f279616970ec9f13ae373302`. Its outputs/conclusion are unchanged. '
        'No new market download, outcome extension or venue substitution. The new episode labels/outcomes/results are independent files.', '',
        'Venue **BTCUSDT / BINANCE_USDM_PERPETUAL**. Source official '
        '[USD-M `/fapi/v1/klines`](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/market-data/rest-api/Kline-Candlestick-Data). '
        'Acquired2026-10-20T10:28:43.290321Z:15,584 closed4H bars, first2019-09-08T16:00Z, '
        'last close2026-10-18T23:59:59.999Z. Aggregate exactly42 contiguous4H bars per Monday00:00UTC week. '
        'Drop the first partial week; exclude the currently open week.371 complete weeks open2019-09-09 through2026-10-12. '
        f"Common warmup/lag eligibility leaves {result['valid_weeks']} weeks; first available {result['first_eligible']}. "
        'Matured opportunities at1/2/3/4W:262/261/260/259. This is reconstructed historical market data, **not real forward observed signal journals**.', '',
        'The inherited full comparison manifest is retained. All371 native REST1W H/L/C/timestamps match the4H weekly aggregation. '
        'One old open (2019-09-23:8061.98 vs10027.69) and five weeks of volume/taker fields differ:11 field differences total. '
        'Seven checksum-verified [official Vision USD-M](https://github.com/binance/binance-public-data) months/1,2784H bars '
        'match OHLC/times; four bars have volume-only differences. No discrepancy was silently repaired or blended. '
        'All eight AO/BBWP/ADX/DI arrays used in the prior audit were exactly identical between the native/aggregated series. '
        'The new study recalculates frozen math and checks all reused feature arrays/signs. ATR depends on matching H/L/C as well. '
        'Interval data consistency is not Bitman indicator parity.', '',
        'RAW4H SHA256 `ea8954f95f15f67eff041e506fc9e0539d5adb7422632b5f7d8246e88704e050`; '
        'aggregated weekly JSON SHA256 `8278c1f44c250c7073c0bb912533a335325cd7109a2a10af59227f2d68a811bc`. '
        'RAW files stay local/ignored. Versioned weekly CSVs, original request/checksum metadata and source hashes are public-only.', '',
        '## 4. Exact proxy formulas', '',
        'Unchanged `bitman_manual.frozen.indicators.calculate`: AO=SMA5((H+L)/2)−SMA34((H+L)/2); '
        'GREEN iff AO−previousAO>0, RED iff<0, FLAT iff=0. Zero sign is separate from color. '
        'BBwidth=4×population_std(close,7)/SMA(close,7). BBWP counts the100 prior widths strictly below current '
        'in a complete101-width window, producing0–100. Volatility slope=one-week difference. '
        'ATR=existing Wilder14 true-range average, fixed at signal time for outcomes. No fitted lengths/thresholds.', '',
        '## 5. Causal states, volatility turns and precedence', '',
        '[Protocol committed before new episode outcomes](BITMAN_WEEKLY_STATE_MACHINE_PROTOCOL.md), commit `60ddd9a`. '
        'Known history from PR #30 means this ordering is procedural discipline, **not** a virgin holdout.', '',
        table(['State', 'Closed-week conditions', 'Weeks'], [
            ['IMPULSE_UP', 'AO>0, GREEN, vol rising', result['state_counts'].get('IMPULSE_UP',0)],
            ['PULLBACK_UP', 'AO>0, RED, vol non-rising', result['state_counts'].get('PULLBACK_UP',0)],
            ['IMPULSE_DOWN', 'AO<0, RED, vol rising', result['state_counts'].get('IMPULSE_DOWN',0)],
            ['PULLBACK_DOWN', 'AO<0, GREEN, vol non-rising', result['state_counts'].get('PULLBACK_DOWN',0)],
            ['REACCELERATION_UP', 'Unbroken PULLBACK_UP run; RED→GREEN and non-rising→rising, no zero cross', result['state_counts'].get('REACCELERATION_UP',0)],
            ['REACCELERATION_DOWN', 'Mirror of UP', result['state_counts'].get('REACCELERATION_DOWN',0)],
            ['ZERO_CROSS_UP_EXPANSION', 'PreviousAO<0/currentAO>0; current vol rising', result['state_counts'].get('ZERO_CROSS_UP_EXPANSION',0)],
            ['ZERO_CROSS_DOWN_EXPANSION', 'PreviousAO>0/currentAO<0; current vol rising', result['state_counts'].get('ZERO_CROSS_DOWN_EXPANSION',0)],
            ['OTHER', 'Valid but no defined combination', result['state_counts'].get('OTHER',0)]]),
        'Reacceleration/zero-cross override base impulse labels. Exact zero is not a strict cross. '
        'An invalid/OTHER/opposite-sign week interrupts the immediate pullback run. '
        'Cross and expansion must coincide; no retrospectively matched delayed expansion. '
        'Uninterrupted corrective weeks, their resolution and frozen range form one episode. '
        'No requirement for an immediately preceding impulse was added: metadata records its presence, and none of these seven '
        'has an immediate same-side IMPULSE before its pullback/start. Older same-side impulse timestamps and all base-state runs '
        'are published. This is a limitation of correspondence to an ideal IMPULSE→PULLBACK→REACCELERATION illustration.', '',
        'ACTIVE_RISING: slope>0. TURN_UP: previous<=0/current>0. SUSTAINED_TURN: at least2 consecutive prior non-rising weeks/current>0. '
        'COOLING:<0; FLAT:=0. TURN flags nest inside ACTIVE_RISING. Level50 flags are reported for all opportunities and signal episodes; '
        'falling-through50 equals the predeclared downward cross plus negative slope, so it is deliberately redundant.', '',
        '## 6. Frozen range, breakout, important move and censoring', '',
        'Main range=last4 completely closed weekly highs/lows **including signal week**, frozen before future weeks. '
        'SensitivityN=2/8, all reported without choosing a winner. Including the signal candle ensures the anchor is inside '
        'and avoids credit for movement already completed before availability. It is a rolling range, not proof of congestion. '
        'Width/causalATR and descriptive width<=2ATR congestion are recorded; no fitted congestion filter.', '',
        'Primary breakout=first future weekly **close** strictly outside the range. Wicks are separate. '
        'If both boundaries are touched in one weekly candle, wick order is BOTH/ORDER_UNKNOWN. '
        'Primary large-breakout label=close breakout plus >=10% excursion from signal close in the same breaking direction within horizon. '
        'The threshold excursion can precede/follow the close breakout within that horizon; intrahorizon order is not asserted. '
        'This measures an event, not tradable returns or execution. All5/10/15/20% and1/1.5/2ATR excursion thresholds are retained.', '',
        'No break by4W is administratively censored for time-to-event; a not-yet-complete horizon is missing, not a failure. '
        'Report later close reentry/opposite-side return, end-close outside, and no-reentry persistence only with >=1 followup week. '
        'A breakout on the final horizon week cannot establish persistence.', '',
        '## 7. Individual sequential episodes', '',
        table(['Available UTC', 'State', 'Pullback weeks', '4W close break / time', 'Max excursion', 'Signed terminal', 'Large10'], [
            [e['end_at'][:10], e['state'], e['pullback_weeks'],
             ('UP' if e['outcome']['first_side']==1 else 'DOWN' if e['outcome']['first_side']==-1 else 'CENSORED')+
                 (' / '+str(int(e['outcome']['first_week']))+'W' if e['outcome']['first_week'] else ' / 4W'),
             fmt(e['outcome']['max_move'])+'%', fmt(e['side']*e['outcome']['forward'])+'%', int(e['outcome']['large_10'])] for e in episodes]),
        'Full `analysis.json` contains episode IDs, start/end, sign/color/proxy sequences, prior impulse metadata, range, '
        'all4W outcomes, and contiguous descriptive runs. `observations.csv` contains all3range×4horizon outcomes for every '
        'matured opportunity, including1/2/3W episode followup. No persistent expansion was counted as repeated signals.', '',
        '## 8. Magnitude, base rate, precision, recall and lift', '',
        'Precision=large labels at signal opportunities/signals. Recall=those true positives/all large-label opportunities. '
        'Base rate=large labels/all eligible opportunities in the same scope. These are **anchor-level**, not unique-market-move '
        'recall: nearby weekly anchors can reference the same future move. No independence or operational coverage claim.', '',
        table(['Horizon', 'Signals n', 'Large precision', 'Base rate', 'Recall', 'Lift', 'Close break', 'Wick break', 'Mean/median max %'], [
            [h, int(row(horizon=h)['n']), fmt(row(horizon=h)['precision'],True), fmt(row(horizon=h)['base_rate'],True),
             fmt(row(horizon=h)['recall'],True), fmt(row(horizon=h)['lift']), fmt(row(horizon=h)['breakout_mean'],True),
             fmt(row(horizon=h)['wick_breakout_mean'],True), fmt(row(horizon=h)['max_move_mean'])+' / '+fmt(row(horizon=h)['max_move_median'])]
            for h in (1,2,3,4)]),
        table(['Control (4W)', 'n', 'Large10 rate', 'Mean max %', 'Median max %', 'Mean max ATR', 'Signed mean %'], [
            [g, int(row(g)['n']), fmt(row(g)['precision'],True), fmt(row(g)['max_move_mean']), fmt(row(g)['max_move_median']),
             fmt(row(g)['max_atr_mean']), fmt(row(g)['signed_mean'])] for g in
            ('SIGNALS','ALL','VOL_TURN','VOL_RISING','VOL_FALLING','SIGN_POS','SIGN_NEG','COLOR_GREEN','COLOR_RED','PULLBACK_NO_REACCEL')]),
        'The pooled main signal is weaker than all-weeks and volatility-turn magnitude controls in this sample; '
        'the rarity of the sequence cannot be repaired by loosening its definition after seeing outcomes.', '',
        table(['4W metric', 'Signals', 'All weeks', 'Vol TURN_UP'],
            [[name, fmt(primary[key],prob), fmt(base[key],prob), fmt(turn[key],prob)] for name,key,prob in
             [('up excursion mean %','up_mean',False),('down excursion mean %','down_mean',False),
              ('distance beyond range mean ATR','beyond_atr_mean',False),
              *[(f'max excursion >= {p}%','move_'+str(p)+'_mean',True) for p in (5,10,15,20)],
              *[(f'max excursion >= {t} ATR','atr_'+str(t)+'_mean',True) for t in (1,1.5,2)],
              *[(f'close breakout + >= {p}%','large_'+str(p)+'_mean',True) for p in (5,10,15,20)]]]),
        'Only2/7 have a4W close breakout (UP,1W and3W);5 are censored. Both observed close breaks remain outside with '
        '3 and1 subsequent closed weeks, respectively, and no close reentry; **n=2**, not a persistence claim. '
        'Six have a wick breakout. The weekly OHLC cannot tell the order of same-week double touches.', '',
        '## 9. Direction is a separate endpoint', '',
        table(['Group', 'n', 'Signed mean %', 'Signed median %', 'Terminal hit', 'Correct first close-break / all', 'Conditional direction n / rate'], [
            [g, int(row(g)['n']), fmt(row(g)['signed_mean']), fmt(row(g)['signed_median']), fmt(row(g)['terminal_hit_mean'],True),
             fmt(row(g)['correct_breakout_mean'],True), str(int(row(g)['directional_n']))+' / '+fmt(row(g)['directional_mean'],True)]
            for g in ('SIGNALS','SIGNAL_UP','SIGNAL_DOWN',*sm.SIGNALS)]),
        'Direction uses episode side (equal to current oscillator sign for these states), not isolated GREEN/RED. '
        'Summary-table signed returns use current oscillator sign for every opportunity control, including color-only groups; '
        'the separate per-side comparisons instead fix UP or DOWN for both signal and matching-sign/color control. '
        'The2/2 conditional UP breaks omit five no-break outcomes and are not a100% directional success claim. '
        'Signed mean is driven by the2023-10 episode; pooled signed median is negative. '
        'Per-side paired contrasts versus same-sign, same-color, vol-turn and pullback controls are in `comparisons.csv`. '
        'Their episode n is below10: no reliable incremental directional conclusion or published bootstrap CI.', '',
        '## 10. Pullback duration and level50 — all predeclared cells', '',
        table(['Duration group', 'n', 'Large10', 'Mean max %', 'Signed mean %'], [
            [g, int(row(g)['n']), fmt(row(g)['precision'],True), fmt(row(g)['max_move_mean']), fmt(row(g)['signed_mean'])]
            for g in ('REACC_GE1','REACC_GE2','REACC_GE3','REACC_EXACT_1','REACC_EXACT_2','REACC_EXACT_3','REACC_EXACT_GE4')]),
        'Duration buckets above concern reacceleration, not zero-cross metadata. Empty cells stay NA. '
        'No duration or level50 cell is promoted to a rule.', '',
        table(['Level condition', 'All n / large10', 'Signal n / large10'], [
            [name, str(int(row('LEVEL_'+name)['n']))+' / '+fmt(row('LEVEL_'+name)['precision'],True),
             str(int(row('SIGNAL_LEVEL_'+name)['n']))+' / '+fmt(row('SIGNAL_LEVEL_'+name)['precision'],True)]
            for name in ('GT50','LE50','CROSS_UP50','CROSS_DOWN50','FALL_THROUGH50','TURN_LE50','TURN_GT50')]),
        '## 11. Falsification: failures and missed events', '',
        table(['Predeclared counterexample category', 'Count at4W/N4'], result['falsification_counts'].items()),
        'VOL_TURN_NO_LARGE means no close-range-exit plus10% label; VOL_TURN_NO_MOVE10 specifically means '
        'no10% excursion in either direction, regardless of range exit. These are different falsifications.', '',
        'Both UP reaccelerations finish lower at4W: available2023-06-26 and2025-10-06. '
        'The DOWN reacceleration available2026-06-08 finishes higher. These are terminal wrong-side outcomes; '
        'neither side has an opposite **close** breakout in its two reacceleration episodes, primarily because these four '
        'episodes have no close breakout at all. Zero opposite breaks therefore is not evidence of predictive direction.', '',
        'The2025-10-06 UP setup has17.752% downside excursion and a−10.477% terminal return: a large move can occur in '
        'the wrong direction and only via wick exit under the fixed range. '
        'The2022-09-19 DOWN reacceleration has max7.662% and no close exit. '
        'Every counterexample timestamp and measurement is published in `falsification.csv`; no cherry-picked success gallery. '
        'The128 overlapping positive-label opportunities include127 without a setup: these are anchor-level false negatives, '
        'not127 distinct crashes/rallies. Full falsification lists retain that distinction.', '',
        '## 12. Robustness, distributions and influence', '',
        'Fixed2,000 circular moving-block replicates, seed20261020, block8weeks. Calendar blocks include all weekly '
        'opportunities, not IID resampling of the seven episode rows. Paired contrasts preserve shared calendar draws. '
        'Block4/12 sensitivities are published in `analysis.json`. CI requires n>=10 and>=95% finite bootstrap replicates; '
        'therefore all main episode CIs are **NA / INSUFFICIENT FOR CONCLUSION**, not spuriously precise intervals. '
        'Baseline CIs and all unadjusted contrasts are in CSVs. n<30 cells are explicitly insufficient. '
        'Mean/median/sd/p10/p25/p75/p90 and best-event exclusions are published; these descriptive multiple comparisons '
        'have no virgin holdout or confirmatory significance.', '',
        table(['Baseline max %', 'Mean CI95', 'Median CI95', 'Large10 CI95'], [
            [g, fmt(row(g)['max_move_ci_low'])+' / '+fmt(row(g)['max_move_ci_high']),
             fmt(row(g)['max_move_median_ci_low'])+' / '+fmt(row(g)['max_move_median_ci_high']),
             fmt(row(g)['precision_ci_low'],True)+' / '+fmt(row(g)['precision_ci_high'],True)] for g in ('ALL','VOL_TURN','VOL_FALLING')]),
        table(['Removed by', 'k', 'n', 'Max mean %', 'Signed mean %', 'Precision', 'Excluded availability dates'], [
            [r['criterion'],r['excluded'],r['n'],fmt(r['max_move']),fmt(r['signed']),fmt(r['precision'],True),
             ', '.join(d[:10] for d in r['removed']) or 'none'] for r in result['influence']]),
        'Removing the best event reverses the pooled signed mean. Removing best3 leaves only4 episodes. '
        'This sensitivity is adverse evidence, not grounds to recalibrate a proxy or redefine the sequence.', '',
        table(['Range N', 'Horizon', 'n', 'Precision', 'Base', 'Lift', 'Close break'], [
            [n,h,int(row(horizon=h,length=n)['n']),fmt(row(horizon=h,length=n)['precision'],True),
             fmt(row(horizon=h,length=n)['base_rate'],True),fmt(row(horizon=h,length=n)['lift']),
             fmt(row(horizon=h,length=n)['breakout_mean'],True)] for n in (4,2,8) for h in (1,2,3,4)]),
        'Greedy first-event windows reject subsequent signals within4weeks; all seven already satisfy this separation '
        '(zero overlapping signal windows). Opportunity labels still overlap. Four fixed calendar phases and one-per-run '
        'same-sign/color/pullback controls are published. This is not equivalent to seven independent market regimes.', '',
        '## 13. Temporal stability and existing causal regimes', '',
        table(['Scope', 'Signal n', 'Large10 precision', 'Local base', 'Lift', 'Signed mean %', 'Mean max %'], [
            [scope,int(row(scope=scope)['n']),fmt(row(scope=scope)['precision'],True),fmt(row(scope=scope)['base_rate'],True),
             fmt(row(scope=scope)['lift']),fmt(row(scope=scope)['signed_mean']),fmt(row(scope=scope)['max_move_mean'])]
            for scope in ('2020-2022','2023-2024','2025-2026','BULL','BEAR')]),
        'Regime is the frozen causal4H close versus SMA200 observed at weekly availability, not retrospective bull/bear labels. '
        'Warmup removes2020 and most2021; the first requested era is substantially truncated. '
        'Each era has very few episodes. The sole large success is in2023–2024; no stability conclusion is supported.', '',
        table(['Horizon', 'Past-matured control pairs', 'Mean max-move difference pp', 'Mean large-label difference'], [
            [h,len([r for r in temporal if r['horizon']==h]),
             fmt(statistics.mean([r['max_move_difference'] for r in temporal if r['horizon']==h])) if any(r['horizon']==h for r in temporal) else 'NA',
             fmt(statistics.mean([r['large_difference'] for r in temporal if r['horizon']==h])) if any(r['horizon']==h for r in temporal) else 'NA'] for h in (1,2,3,4)]),
        'Temporal controls use only trailing52weekly anchors whose complete forward horizon was already known at signal '
        'availability (at least12controls). No future outcome matching. Their dependent small pair count does not warrant an IID CI.', '',
        '## 14. POST-HOC VISUAL CONSISTENCY CHECK', '',
        '**NOT ASSESSABLE.** No independently verified on-screen dates or indicator settings were recovered from the supplied '
        'video. The episodes in section7 are auditable proxy sequences but are **not asserted to be Bitman\'s shown examples**. '
        'Exact-video dates/screenshots plus reproducible public settings are missing. Source access limitations do not demonstrate '
        'PROXY MISMATCH, and no visual parity claim is made. Future dated comparisons must stay post-hoc and cannot calibrate these parameters.', '',
        '## 15. Comparison with PR #30', '',
        'PR #30 tested AO color×BBWP rising/falling snapshots and concluded **EXPANSION EFFECT FRAGILE**. '
        'That conclusion remains unchanged, including its positive descriptive expansion-start2W return finding. '
        'This study asks a different sequential, zero-sign-conditioned question and uses frozen-range/close-breakout targets. '
        'Seven sparse sequence signals cannot replace127 rising-volatility opportunities or be pooled with them to enlarge n. '
        'The prior market history was already inspected: **NO VIRGIN HOLDOUT**.', '',
        '## 16. Proxy and statistical limitations', '',
        'Unknown private oscillator/modified-volatility settings; unavailable independent target-video captions/visual dates; '
        'only seven episodes; no adequate era/side/duration sample; long BBWP warmup; strict simultaneous cross/expansion definition; '
        'signal-week range inclusion can absorb the large move already occurring on a weekly signal candle; historical API revisions; '
        'OHLC cannot resolve intrabar order; overlapping target opportunities; unadjusted multiple comparisons; no untouched test set. '
        'A range-close endpoint differs from a discretionary chart reading. Neither insufficient evidence nor proxy failures '
        'establish that the creator\'s undisclosed rule is false.', '',
        '## 17. CURRENT WEEKLY STATE — CURRENT OBSERVATION — NOT PART OF VALIDATION', '',
        f"Last fully closed week: {current['open_time']} → {current['available_at']}. Open week excluded.", '',
        '```text', 'Oscillator proxy: '+current['sign']+' ZERO / '+current['color'],
        'AO: '+fmt(current['oscillator'])+'; slope: '+fmt(current['oscillator_slope']),
        'Volatility proxy: '+fmt(current['volatility_previous'])+' → '+fmt(current['volatility'])+
            '; slope: '+fmt(current['volatility_slope']),
        'Volatility state: '+current['volatility_state'],
        'TURN_UP: '+str(current['turn_up'])+'; SUSTAINED_TURN: '+str(current['sustained_turn']),
        'Sequence: '+current['state'],
        'Frozen4W range: '+fmt(current['ranges']['4']['low'])+' → '+fmt(current['ranges']['4']['high']),
        'Large move watch: NOT VALIDATED', 'CURRENT OBSERVATION ONLY', '```', '',
        'Positive AO/GREEN with falling volatility is OTHER under the declared machine; it is not forced into IMPULSE_UP '
        'or PULLBACK_UP. The last six weekly states are OTHER. No current directional or operational signal is inferred.', '',
        '## 18. Conclusion and review artifacts', '',
        '**'+conclusion(primary['n'])+'**', '',
        'No robust incremental magnitude or direction evidence is established. **Do not integrate into runtime.** '
        'Any future specification remains HYPOTHESIS FOR FORWARD OBSERVATION; first obtain dated source/proxy evidence and '
        'a prospectively fixed observation protocol, without changing this historical study after outcomes.', '',
        'Artifacts: `analysis.json` (episodes/runs/current/influence/overlap), `states.csv`, `observations.csv`, '
        '`summaries.csv`, `comparisons.csv`, `temporal_controls.csv`, `falsification.csv`, source/data/artifact manifests '
        'under `research/results/bitman_weekly_state_machine/`. Offline replay: '
        '`python -m research.bitman_state_analysis`; report: `python -m research.bitman_state_reporting`. '
        'Artifact hashes normalize CRLF→LF only. All reused inputs have fixed hashes. No raw transcripts or sensitive exports committed.', '',
        'Only isolated research, new tests and a new research workflow are added. Frozen indicators/engine, operational gates, '
        'Guardian, acquisition service, V8, ML RSI, risk/execution, Telegram and Railway remain untouched. '
        'No automatic alerts. No orders. **TRADE AUTHORITY: NONE.**', '']
    return '\n'.join(lines)


def run():
    result = json.loads((sm.DEST/'analysis.json').read_text('utf-8'))
    read = lambda name: read_csv(sm.DEST, name)
    report = render(result, read('summaries'), read('comparisons'), read('temporal_controls'), read('falsification'))
    (sm.ROOT/'research/results/BITMAN_WEEKLY_STATE_MACHINE.md').write_text(report, encoding='utf-8')
    paths = sorted(p for p in sm.DEST.iterdir() if p.is_file() and p.name != 'artifact_manifest.json')
    manifest = dict(normalization='CRLF to LF only', sha256={p.name: sm.checksum(p) for p in paths})
    (sm.DEST/'artifact_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(conclusion=conclusion(result['episode_count']), episodes=result['episode_count'], artifacts=len(paths))))


if __name__ == '__main__':
    run()
