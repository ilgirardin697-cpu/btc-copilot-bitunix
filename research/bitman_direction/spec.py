"""Frozen informational hypotheses. No strategy or PnL objective."""
BASE_SHA='7fc762522be9bae6bd1ac799dbcc2a9ab9e512c7'
VERSION='BITMAN_BTC_DIRECTION_ENGINE_0_1'
HOUR=3600000
CUTOFF='2026-10-15T19:00:00Z'
TIMEFRAMES={'1H':HOUR,'4H':4*HOUR,'1D':24*HOUR}
HORIZONS={'1H':(4,12,24),'4H':(12,24,48,72),'1D':(24,72,168,336),'MTF':(12,24,48,72,168,336)}
PRIMARY_HORIZON={'1H':12,'4H':24,'1D':72,'MTF':72}
FALSE_REVERSAL_HOURS={'1H':3,'4H':12,'1D':72,'MTF':24}
FROZEN_FILES=('spec.py','core.py','levels.py','confirmed.py','evaluation.py','study.py','noise.py','observer.py')
MLRSI_SHA='55c1c988df1dbfea80ed02fd13965f34f1727f14'
MLRSI_CONFIG='CAPTURE_LOW29_EMA4_PINE_PARITY_V4'


def protocol():
    return dict(version=VERSION,base_sha=BASE_SHA,cutoff=CUTOFF,
        objective='Directional information, NOT executable trade/PnL optimization',timeframes=TIMEFRAMES,
        prior_results='Phase2 REJECT; v0.1 INCONCLUSIVE; Phase4 INCONCLUSIVE; immutable',
        math='Unchanged PR23 KONKORDE_PROXY, AO5/34 HL2, ADX/DI14, BBWP CLOSE/SMA7/prior100',
        ao='Sign context; sustained momentum requires two consecutive same-sign slopes OR confirmed zero cross. '
            'Single histogram color alone is insufficient. Acceleration and toward/away zero descriptive.',
        tf_bias='AO_ONLY: sign. AO_DI: UP when AO>0 and+DI>-DI; DOWN when AO<0 and-DI>+DI; '
            'TRANSITION when nonzero AO and DI disagree, NEUTRAL on ties, UNKNOWN on unavailable required data. '
            'ADX never assigns direction.',
        hierarchy='1D macro,4H swing,1H timing; never three equal votes. Macro/swing aligned =>UP/DOWN, '
            'opposite1H impulse is PULLBACK. Opposite4H plus1H agreeing with4H=>TRANSITION with explicit lean; '
            'opposite4H and1H agreeing withmacro=>CONFLICT. Partial transitions=>TRANSITION only with a timing lean, '
            'otherwise UNCLEAR. Missing macro/swing=>UNCLEAR.',
        timing='Sustained AO momentum/zero cross with matching DI=>impulse_up/down; mixed momentum/DI=>transition; '
            'otherwise no_impulse. Aligned macro/swing and opposite impulse=>pullback, retaining pullback direction.',
        strength='STRONG: aligned macro/swing plus ADX rising and BBWP rising on BOTH1D/4H. '
            'BUILDING: candidate direction and4H ADX+BBWP rising OR aligned1H impulse with1H ADXturn+BBWP rising. '
            'Otherwise WEAK. No ADX magnitude threshold, points, fitted score or volatility zones.',
        grade='A: UP/DOWN, alignedmacro/swing,STRONG,no missing/opposite4H ML confirmation; '
            'B: UP/DOWN otherwise; C:TRANSITION/UNCLEAR/CONFLICT or known opposite ML. '
            'Visual coherence grade, not statistical proof/probability/sizing.1D ML is unavailable in existing observer.',
        mlrsi='READ ONLY confirmed cache from unchanged LOW29/EMA4 PINE_PARITY_V4 BinanceSPOT observer. '
            'No imports/math/threshold recomputation; provisional/approaching ignored. '
            'Known opposite4H confirmed ML=>CONFLICT; missing ML never fabricated neutral. '
            'Historical ML ablation PENDING without actual recorded confirmed states.1D unsupported, UNKNOWN.',
        konkorde='Inside geometry unchangedPR23. Positive ENTRY/inside,EXIT,quickREENTRY<=3TFbars, '
            'negative/fallingoutside bearish PROXY context. EXIT never automaticallySHORT. '
            'Distance/separation continuous, no zero proximity entry threshold.',
        levels='READ ONLY ManualCopilot confirmed_structure2L/2R; bounded220TFbars matching existing market history scale. '
            '1H/4H/1D pivots available only at confirmation close; independent scales frozen until nextTFclose. '
            'PreviousUTCday/week(Monday) highs/lows from complete periods. Nearest S/R across confirmed levels; '
            'crossed4H/1D levels remain original type awaiting thatTFclose. No distance optimization.',
        structure_conflict='UP/DOWN=>CONFLICT only if latest closed1H range touches an opposing4H/1D pivot '
            'already known at previous1H close and closes back on original side; no intrabar/live mark authority. '
            'AT_SUPPORT/AT_RESISTANCE are actual range-touch labels, otherwise BETWEEN_LEVELS; '
            'OPEN_SPACE_UP/DOWN not claimed when no finite set proves absence of farther levels.',
        episodes='One continuous finalstate=one episode regardless strength/detail changes; newevent only on state change. '
            'No synthetic split-start event; missing-data state breaks episode. '
            'Separate TF AO_DI andAO_ONLY episodes; transitions retain lean separately, unclear has no direction.',
        outcomes=dict(horizons=HORIZONS,primary=PRIMARY_HORIZON,
            reference='Known closed reference; future PUBLIC1H closed bars only. No fill/fees/PnL model or trading claim.',
            barriers='Directional favorable/adverse2/5/10%; SHORT1-price/ref. '
                'Same1Hbar touchingboth=>AMBIGUOUS, never favorable victory. '
                'Adverse-before-target bounded by prior bars and inclusive targetbar, no invented intrabar order.',
            censoring='Split-end/gap/unmature stays incomplete. No interpolation or counting pending as loss.',
            false_reversal='Directional episode preceded by opposite last directional episode and then reverting '
                'within configured3TFbars(MTF24h); evaluative future labels only, censored at right edge.',
            false_reversal_hours=FALSE_REVERSAL_HOURS),
        splits=dict(TRAIN='2020-2021',VALIDATION='2022-2023',TEST='2024-cutoff; REUSED OOS, NOT VIRGIN'),
        controls='Up to3 deterministic non-episode-start timestamps matching UTCyear/month/hour, '
            'lastclosed4H SMA200 regime and volatility quartile; TRAIN ATR1H/price cutpoints for TEST. '
            'Samehorizon maturity in same split; no return-based choice; require at least1. '
            'For nondirectional states report rawBTC descriptive only, not signed directional accuracy.',
        bootstrap='Weekly calendar blocks1000 seed8192 of paired excess; overlapping outcomes not independent. '
            'No multiplicity-corrected significance claim.',
        walk_forward='2022..2026 fixed rules, no selection/refit; matching volatility cutpoints fitted only through prior year. '
            'Do not pick a family or alter parameters with TEST.',
        ablation='AO_ONLY hierarchy; AO_DI hierarchy; conditional same AO_DI episodes with4H ADXrising, '
            'then BBWPrising, then directionalKcontext; then confirmedMLaligned if real input available; '
            'structure adds opposing-level test context on public hierarchy. '
            'Conditional subsamples not new strategies; no-op/identical masks reported, not independent replications.',
        noise='Historical engine/V8 onsets only: nearest one-to-one UPevent match within24h, '
            'signed latency engine minusV8; overlap +hourlystate agreement/transitionrate. '
            'V8FLAT is NOT DOWN. Other actualforward overlap/false anticipation PENDING without journals.',
        classification='USEFUL DIRECTION ENGINE only if UP andDOWN each >=50TESTepisodes, positive signedmean '
            'and pairedexcess with weekly95%CIabove0 at72h; >=2positiveTESTyears each and>=3positiveWFyears each; '
            'no best3 dependence; actual confirmedML incremental evaluation available and structure-safe evaluation. '
            'NO DIRECTIONAL VALUE if both directions >=50 and nonpositiveTESTmean/excess; otherwise INCONCLUSIVE DIRECTION ENGINE. '
            'No trading profitability or authorization conclusion.',
        actual_forward_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',
        private_parity='EXACT BITMAN KONKORDE PARITY: NOT PROVEN',shadow_only=True,trade_authority=False,
        paid_source_calls=0,production_integration=False)
