"""Predeclared observational definitions. No strategy or parameter selection."""
from dataclasses import dataclass

VERSION='BITMAN_REAL_OBSERVER_0_1'
BASE_SHA='9d0024a45d8e40193162a3864a876ca5ab61d1da'
REJECTED_PHASE2_SHA='44029b4768e2b4bc47643bb51bf8a28432623a39'
MLRSI_SHA='55c1c988df1dbfea80ed02fd13965f34f1727f14'
V8_SHA='724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6'
HOUR=3600000
TIMEFRAMES={'1H':HOUR,'4H':4*HOUR,'1D':24*HOUR}
HORIZONS=(1,4,12,24,48,72)
REENTRY_WINDOWS=(1,2,3,5)  # all reported; NONE selected/recommended using returns
CUTOFF='2026-10-15T19:00:00Z'
SHORT_PROVEN=False


@dataclass(frozen=True)
class Config:
    # Required explicit presentation setting, not a fitted strategy parameter.
    reentry_max_bars: int
    mountain_ma: int=15

    def __post_init__(self):
        if type(self.reentry_max_bars) is not int or not 1<=self.reentry_max_bars<=100:
            raise ValueError('REENTRY_WINDOW_INVALID')
        if self.mountain_ma!=15: raise ValueError('UNREGISTERED_PROXY_PRESET')


def protocol():
    return dict(version=VERSION,source='KONKORDE_PROXY',exact_bitman_parity='NOT PROVEN',
        phase2_status='REJECT',phase2_sha=REJECTED_PHASE2_SHA,base_sha=BASE_SHA,cutoff=CUTOFF,
        timeframes=TIMEFRAMES,horizons_hours=HORIZONS,reentry_windows=REENTRY_WINDOWS,
        proxy='OHLC4; WilderRSI14; HLC3-MFI14; BB25 SMA/populationSTD multiplier2; '
              'OHLC4 Stochastic21 SMA3; mountain=(RSI+MFI+BollOsc+Stoch/3)/2; MA=EMA15.',
        seed='Wilder SMA of14 valid changes; EMA starts at first finite value; undefined ratios=>NaN.',
        geometry='inside: min(0,mountain)<MA<max(0,mountain). Boundary equality is outside. '
                 'ENTRY outside->inside, EXIT inside->outside; first valid state/gap recovery is context only.',
        reentry='ENTRY with prior EXIT in same continuous valid segment, age1..configuredTFbars. '
                'REENTRY is an ENTRY subset, not independent extra observations. All1/2/3/5 reported.',
        distance_to_zero='abs(MA), continuous indicator units; also abs(mountain). No entry threshold.',
        separation='abs(mountain-MA) while inside; relevant edge=outer mountain, not PVI/NVI. '
                   'Strength compares consecutive inside bars only; first inside=NEW_INSIDE.',
        complementary=dict(adx='Wilder ADX14 / DI14; rising diagnostic, no absolute entry threshold',
            ao='SMA5(HL2)-SMA34(HL2); zero, slope, consecutive-slope color',
            bbwp='CLOSE SMA7 populationSTD width; rank strictly lower against PRIOR100 finite widths. '
                 'EXPANDING/CONTRACTING/STABLE are slope labels, no fitted compression zones',
            trend_speed='NOT IMPLEMENTED / FORMULA NOT VERIFIED;117/2.7/150/100/From start metadata only'),
        direction='LONG is descriptive positive mountain+inside+DI+>DI-, not entry permission; '
                  'AO/ADX/BBWP are reasons/context, NOT mandatory filters. '
                  'SETUP_FORMING: positive inside withoutDIalignment, or positive rising mountain outside. '
                  'Negative mountain with bearishDI/AO => BLOCKED/SHORT_LOGIC_NOT_PROVEN; otherwise WAIT. '
                  'Missing evidence => BLOCKED. No score, no SHORT inversion.',
        outcomes='Gross price observations at reference closedTFclose; future COMPLETE1H candles only. '
                 'No assumed fill, costs, funding, sizing, account profit or executable strategy. '
                 'Forward returns/MFE/MAE always raw BTC orientation, including EXIT.',
        first_passage='Independent+1/-1/+2/-2 hit times and symmetric1/1,2/2 race; same1Hbar=>AMBIGUOUS, '
                      'unresolved=>UNRESOLVED. Not invented intrabar ordering.',
        splits=dict(TRAIN='2020-2021',VALIDATION='2022-2023',TEST='2024-cutoff; reused OOS'),
        cohorts='TRAIN tertiles fixed perTF for continuous distance/separation; no profitable cutoff search. '
                'ADX favorable=slope>0; DI/AO aligned for LONG interpretation, EXIT bearish diagnostic only. '
                'BBWP expanding=slope>0. Cohorts not gates; overlapping observations not independent.',
        control='Deterministic non-event controls sameUTCmonth/hour, same trailing24TFbar trend sign; '
                'exclude all technical events, no return-based matching; missing exact match excluded explicitly.',
        inference='Primary endpoint24h event-minus-control return,7day block bootstrap500 seed9821. '
                  'ENTRY positive / EXIT negative are descriptive hypotheses, not SHORT trades. '
                  'No multiple-testing significance claim for secondary tables.',
        classification='USEFUL OBSERVER only if >=2TF have ENTRY/EXIT n>=100 matched24h, '
                       'both directional CI95 lower>0 and positive directional excess in2024/2025/2026. '
                       'NO EDGE if neither1H nor4H has both primary signs favorable with adequate samples; '
                       'otherwise INCONCLUSIVE. No live promotion classification.',
        forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',
        shadow_only=True,trade_authority=False)
