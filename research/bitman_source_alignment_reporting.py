"""Separate POST-HOC source-alignment report; strict numerical files untouched."""
import json

from research import bitman_weekly_state_machine as sm
from research import bitman_state_source_alignment as aligned
from research.bitman_state_reporting import read_csv, fmt, table

REPORT = sm.ROOT/'research/results/BITMAN_WEEKLY_SOURCE_ALIGNMENT_ADDENDUM.md'


def render(result, metrics, influence):
    def row(model, scope='FULL', group='ALL_SIGNALS', horizon=4, length=4):
        return next(r for r in metrics if r['model']==model and r['scope']==scope and r['group']==group and
                    r['horizon']==horizon and r['range_weeks']==length)
    models=result['models']
    lines=['# BITMAN weekly source-alignment addendum', '',
        '**POST-HOC SOURCE ALIGNMENT — NOT PREDECLARED VALIDATION. NO VIRGIN HOLDOUT.**', '',
        '**'+result['transcript_review']+'**', '',
        '**'+result['conclusion']+'**', '',
        'The original **PREDECLARED STRICT SAME-WEEK MODEL** remains intact with its original **INCONCLUSIVE** conclusion. '
        'This addendum reports all requested lag windows (0, <=1, <=2), without selecting a winner or recommending runtime integration.', '',
        '## 1. Corrected source audit and limits of access', '',
        'After the original analysis, the owner reports recovering an independent transcript of '
        '[the source video](https://www.youtube.com/watch?v=v8d3OxE1-_c), especially from approximately minute20 onward. '
        'This agent has **no direct access** to that recovered transcript. The following points are attributed to the '
        'owner\'s external review; they are paraphrases, not invented quotations or independent verification by this agent.', '',
        '- The explanation applies specifically to WEEKLY candles and centers on oscillator plus volatility.',
        '- ADX is set aside in this explanation; volatility may help anticipate an ADX turn. That is a reported conceptual claim, '
        'not an ADX lead/lag result measured here. No ADX gate was added.',
        '- Above zero, GREEN with growing volatility describes impulse; RED with falling volatility describes correction.',
        '- Below zero, RED with growing volatility describes bearish impulse; GREEN with falling volatility describes correction.',
        '- After corrective weeks, momentum can resume without crossing zero, or zero can be crossed before expansion in the new direction.',
        '- The review reports approximately1–2 weeks between oscillator change and volatility recovery, motivating this timing sensitivity.', '',
        'The source audit now marks transcript recovery as **external**, with `agent_direct_transcript_access=false`, '
        '`part_of_predeclared_protocol=false`, and the exact external-review status above. It retains the original audit\'s '
        'false recovery flag inside `predeclared_audit_state`, rather than rewriting what was known then. '
        'No full transcript, long quotes, new paid retrieval or vidIQ credits. Verbal alignment can now be assessed against '
        'the supplied external review; on-screen dates/settings and private formulas still cannot.', '',
        '**EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN**', '',
        '**EXACT BITMAN VOLATILITY PARITY: NOT PROVEN**', '',
        'The oscillator remains AO as OSCILLATOR_PROXY; frozen BBWP remains BITMAN_VOLATILITY_PROXY. '
        'The transcript review does not establish formula equivalence, statistical predictive value, or an untouched holdout.', '',
        '## 2. What changed, and the fixed causal interpretation', '',
        '[Post-hoc definitions](BITMAN_WEEKLY_SOURCE_ALIGNMENT_PROTOCOL.md) were recorded before calculating these new lag outcomes, '
        'after the original history/results were already known. That does **not** make this a predeclared out-of-sample experiment.', '',
        'At an observed oscillator color return after a pullback or strict zero crossing, latch one candidate. '
        'If volatility already meets the original condition at that close, emit immediately. Otherwise wait at most1or2 '
        'subsequent closed weeks for the first TURN_UP. A delayed event is timestamped at that confirmation, with its range, '
        'close and ATR frozen then. Price movement during the wait is excluded from forward outcomes. '
        'This is oscillator-first, non-negative lag; no symmetric retrospective match or event backdating.', '',
        'A reacceleration candidate must keep its zero sign and returned impulse color; a new correction cancels that return. '
        'A zero-cross candidate must retain its new strict zero sign. No independent color gate is added to zero-cross resolution '
        'because the original zero-cross definition did not have one; its resolution color is published. '
        'Invalid weeks, zero/opposite sign and expiry cancel pending candidates. An expired candidate is never reanimated. '
        'A pending zero-cross owns its resolution over a same-side color-return activation, preventing duplicate episodes. '
        'These are explicit formalization choices, not claimed transcript-exact private rules.', '',
        'Lag0 is tested against the original seven timestamps, sides and types. The original zero-cross accepts '
        'already ACTIVE_RISING at the cross even without a fresh TURN_UP; this is preserved. Only delayed resolution requires '
        'a fresh TURN_UP. No lag3/4/5, new lengths, thresholds, indicator fitting, or winning-window selection.', '',
        '## 3. Same dataset and unchanged outcomes', '',
        'Reuse the same audited BTCUSDT BINANCE_USDM_PERPETUAL snapshot:371 closed Monday-UTC weekly candles,263 eligible '
        'weeks, first eligible availability2021-10-11, cutoff2026-10-19T00:00UTC. No new market data or venue substitution. '
        'The original strict protocol, classifier, outcome math and numerical artifacts are hash-frozen (14files in '
        '`bitman_weekly_source_alignment/strict_baseline.json`). Only source documentation/metadata and separate addendum outputs change.', '',
        'Primary endpoint remains N=4 trailing closed weeks including the confirmation candle, horizon4W, weekly CLOSE '
        'exit plus >=10% excursion from confirmation close in the same breaking direction. All original N=2/4/8 and1/2/3/4W '
        'combinations are published, with the existing5/10/15/20% and ATR outcome fields. No endpoint recalibration. '
        'Partial forward horizons stay missing. Recall/false negatives concern overlapping weekly **anchors**, not distinct market moves.', '',
        '## 4. Episode counts — why the strict model found only seven', '',
        table(['Model','Total','REACC_UP','REACC_DOWN','ZERO_CROSS_UP','ZERO_CROSS_DOWN','Actual lag0/1/2'],[
            [m['name'],m['episode_count'],*[m['family_counts'][k] for k in sm.SIGNALS],
             '/'.join(str(m['actual_lag_counts'].get(str(k),0)) for k in (0,1,2))] for m in models]),
        'The strict timing requirement does exclude additional proxy episodes: four first confirm one week after oscillator '
        'activation and two first confirm two weeks after. It is therefore part of the reason for n=7, but it does not by itself '
        'explain missing private-indicator examples or establish that a longer lag predicts better. All strict events are retained '
        'in both sensitivities on this dataset. Counts from separate models must never be pooled into31 independent signals.', '',
        table(['Sensitivity','New confirmation UTC','Family'],[
            [m['name'],event['confirmed_at'][:10],event['kind']] for m in models[1:] for event in m['new_resolutions']]),
        'Each activation/confirmation pair, actual lag, correction duration, complete proxy sequence, cancellation/expiry '
        'and ignored duplicate activation is in `analysis.json`. Every model has one event per resolved sequence and no '
        'same-timestamp duplicates. Greedy non-overlap4W counts are '+
        ', '.join(m['name']+':'+str(m['nonoverlap_count']) for m in models)+'. Opportunity labels still overlap.', '',
        '## 5. All three models — primary4W results', '',
        table(['Model','n','Precision','Base rate','Lift','Recall','TP','FP','FN'],[
            [m['name'],int(row(m['name'])['n']),fmt(row(m['name'])['precision'],True),
             fmt(row(m['name'])['base_rate'],True),fmt(row(m['name'])['lift']),fmt(row(m['name'])['recall'],True),
             int(row(m['name'])['true_positive']),int(row(m['name'])['false_positive']),int(row(m['name'])['false_negative'])] for m in models]),
        table(['Model','Max mean/median %','Signed mean/median %','Terminal directional hit','Conditional first-break accuracy (n)','Unconditional correct break'],[
            [m['name'],fmt(row(m['name'])['max_move_mean'])+' / '+fmt(row(m['name'])['max_move_median']),
             fmt(row(m['name'])['signed_mean'])+' / '+fmt(row(m['name'])['signed_median']),
             fmt(row(m['name'])['terminal_hit_mean'],True),
             fmt(row(m['name'])['direction_accuracy'],True)+' ('+str(int(row(m['name'])['direction_accuracy_n']))+')',
             fmt(row(m['name'])['unconditional_direction_accuracy'],True)] for m in models]),
        'Direction is measured separately from magnitude. Conditional first-break accuracy excludes no-close-break '
        'observations and must be read with its small denominator; the unconditional rate includes those censored/non-breaking '
        'opportunities. A large move in the wrong direction can satisfy the magnitude label without directional success.', '',
        table(['Model','Precision CI95','Signed mean CI95 %','Signed median %','Sample status'],[
            [m['name'],fmt(row(m['name'])['precision_ci_low'],True)+' / '+fmt(row(m['name'])['precision_ci_high'],True),
             fmt(row(m['name'])['signed_ci_low'])+' / '+fmt(row(m['name'])['signed_ci_high']),
             fmt(row(m['name'])['signed_median']),row(m['name'])['sample_status']] for m in models]),
        'Original2000 circular8-week calendar-block bootstrap retained, root seed20261020 plus horizon. '
        'Shared calendar draws are used for each model; no IID resampling of episode rows. Main strict n7 intervals remain '
        'NA under the original minimum n10 rule. Both sensitivity signed-return intervals include zero; all model n are below30. '
        'Intervals are descriptive/unadjusted, not post-hoc validation.', '',
        '## 6. UP/DOWN and family results', '',
        table(['Model','Group','n','Precision','Signed mean %','Terminal hit'],[
            [m['name'],g,int(row(m['name'],group=g)['n']),fmt(row(m['name'],group=g)['precision'],True),
             fmt(row(m['name'],group=g)['signed_mean']),fmt(row(m['name'],group=g)['terminal_hit_mean'],True)]
            for m in models for g in ('UP','DOWN',*sm.SIGNALS)]),
        '## 7. Best-event influence — both fixed criteria', '',
        table(['Model','Rank by','Remove','n left','Max mean %','Signed mean %','Precision','Removed confirmation dates'],[
            [r['model'],r['criterion'],int(r['excluded']),int(r['n']),fmt(r['max_move']),fmt(r['signed']),
             fmt(r['precision'],True),r['removed']] for r in influence if r['scope']=='FULL']),
        'Both magnitude-ranked and signed-return-ranked best1/best3 exclusions are reported, including their dates; '
        'none is selected as a preferred interpretation. Per-era/per-regime influence rows are also published.', '',
        '## 8. Eras and original causal regimes', '',
        table(['Model','Scope','n','Precision','Local base','Lift','Signed mean %','Max mean %'],[
            [m['name'],scope,int(row(m['name'],scope=scope)['n']),fmt(row(m['name'],scope=scope)['precision'],True),
             fmt(row(m['name'],scope=scope)['base_rate'],True),fmt(row(m['name'],scope=scope)['lift']),
             fmt(row(m['name'],scope=scope)['signed_mean']),fmt(row(m['name'],scope=scope)['max_move_mean'])]
            for m in models for scope in ('2020-2022','2023-2024','2025-2026','BULL','BEAR')]),
        'The first era is truncated by long weekly warmup (no eligible2020 and only late2021 onward). Bull/bear remains '
        'the original last closed4H close versus causal SMA200 at confirmation time, not retrospective market labels. '
        'Small side/era cells cannot establish stable predictive value.', '',
        '## 9. Horizon/range sensitivity — no winning cell', '',
        table(['Model','N','Horizon W','n','Precision','Base','Lift','Max mean %','Signed mean %'],[
            [m['name'],n,h,int(row(m['name'],length=n,horizon=h)['n']),fmt(row(m['name'],length=n,horizon=h)['precision'],True),
             fmt(row(m['name'],length=n,horizon=h)['base_rate'],True),fmt(row(m['name'],length=n,horizon=h)['lift']),
             fmt(row(m['name'],length=n,horizon=h)['max_move_mean']),fmt(row(m['name'],length=n,horizon=h)['signed_mean'])]
            for m in models for n in (4,2,8) for h in (1,2,3,4)]),
        'All outcome fields and cohort counts are available in `metrics.csv` and per-episode `observations.csv`. '
        'Original proxy and range-definition limitations remain; no open weeks, future pivots or forward-filled candles.', '',
        '## 10. Current closed-week classification — no signal', '',
        '**CURRENT OBSERVATION — NOT PART OF VALIDATION**', '',
        'Last closed week remains2026-10-12 →2026-10-19UTC. The current open week is excluded. '
        'AO above zero/GREEN10698.622, slope+348.994; volatility proxy41→30, slope−11, COOLING/noTURN_UP. '
        'The fixed4W range remains79732.3–87385.1.', '',
        table(['Model','Current state','Pending candidate','LARGE MOVE WATCH'],[
            [m['name'],m['current']['state'],'NONE' if m['current']['pending'] is None else str(m['current']['pending']),
             'NOT VALIDATED'] for m in models]),
        '**LARGE MOVE WATCH: NOT VALIDATED**. No directional, operational or trade signal is emitted.', '',
        '## 11. Interpretation and preserved strict result', '',
        '**'+result['conclusion']+'**', '',
        'Temporal tolerance recovers additional historically observed proxy configurations and improves the descriptive '
        'precision versus strict. It remains below the same four-week base rate for both sensitivity models, with small n '
        'and signed-return intervals spanning zero. The source review improves fidelity to the reported verbal timing, '
        'not evidence of private formula parity or validated prediction. No best lag is recommended.', '',
        'The original strict conclusion remains **INCONCLUSIVE** and all strict numerical files are unchanged. '
        '**POST-HOC SOURCE ALIGNMENT. NO VIRGIN HOLDOUT.** Any further step would require a separately fixed forward '
        'observation protocol, not runtime integration from these historical outcomes.', '',
        'Reproduce offline: `python -m research.bitman_state_source_alignment`, then '
        '`python -m research.bitman_source_alignment_reporting`. Original report/source-audit metadata updates can be '
        'regenerated with `python -m research.bitman_state_reporting`; the old strict numerical analysis need not be rerun.', '',
        'No changes to production modules, frozen engine, operational gates, renderer, Guardian, V8, ML RSI, market data, '
        'Telegram, risk/execution or Railway. No merge. No deployment. No orders. **TRADE AUTHORITY: NONE.**', '']
    return '\n'.join(lines)


def run():
    aligned.verify_strict()
    result=json.loads((aligned.DEST/'analysis.json').read_text('utf-8'))
    metrics=read_csv(aligned.DEST,'metrics')
    influence=read_csv(aligned.DEST,'influence')
    REPORT.write_text(render(result,metrics,influence),encoding='utf-8')
    paths=sorted(p for p in aligned.DEST.iterdir() if p.is_file() and p.name!='artifact_manifest.json')
    manifest=dict(normalization='CRLF to LF only',sha256={p.name:sm.checksum(p) for p in paths},
                  report_sha256=sm.checksum(REPORT))
    (aligned.DEST/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(conclusion=result['conclusion'],counts={m['name']:m['episode_count'] for m in result['models']})))


if __name__=='__main__':
    run()
