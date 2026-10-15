"""Predeclared Phase 2 design. This module never accesses market/account data."""
from dataclasses import asdict, dataclass, replace

BASE_SHA = 'c1e015802f59baafbf04ee52228f216a391ead93'
CUTOFF = '2026-10-15T19:00:00Z'
START = '2020-01-01T00:00:00Z'
TRAIN_END = '2022-01-01T00:00:00Z'
TEST_START = '2024-01-01T00:00:00Z'
OBSERVER_SHA = '55c1c988df1dbfea80ed02fd13965f34f1727f14'
CONFLUENCE_SHA = '6f83f9ab2451dd3ef33e9ca7ab90b2d15dd95258'
FROZEN_FILES = ('spec.py', 'core.py', 'engine.py', 'run.py', 'mlrsi.py', 'data.py')


@dataclass(frozen=True)
class Candidate:
    name: str = 'C00_BASE'
    cloud: str = 'A'
    rsi_length: int = 89
    cloud_fast: int = 9
    cloud_slow: int = 21
    ema_fast: int = 10
    ema_slow: int = 55
    trend: str = '1h'
    slope: bool = False
    midpoint: bool = False
    oscillator: str = 'AO'
    momentum: str = 'state'
    dmi: str = 'threshold'
    adx_level: float = 20.
    structure: str = 'none'
    volatility: str = 'none'
    stop_atr: float = 2.
    trail_atr: float = 2.
    exit: str = 'runner'
    fusion: tuple = ()
    disabled: tuple = ()


def candidates():
    base = Candidate()
    return [base,
        replace(base, name='C01_CLOUD_B', cloud='B', rsi_length=500, cloud_fast=36, cloud_slow=84),
        replace(base, name='C02_HTF4', trend='4h'),
        replace(base, name='C03_HTF4D', trend='1d'),
        replace(base, name='C04_SLOPE', slope=True),
        replace(base, name='C05_RSI50', midpoint=True),
        replace(base, name='C06_SQZ_STATE', oscillator='SQZ'),
        replace(base, name='C07_AO_CROSS', momentum='cross'),
        replace(base, name='C08_AO_SLOPE', momentum='slope'),
        replace(base, name='C09_AO_ACCEL', momentum='acceleration'),
        replace(base, name='C10_SQZ_ACCEL', oscillator='SQZ', momentum='acceleration'),
        replace(base, name='C11_ADX_RISING', dmi='rising'),
        replace(base, name='C12_DI_ONLY', dmi='direction'),
        replace(base, name='C13_ADX_BOTH', dmi='both'),
        replace(base, name='C14_STRUCTURE', structure='trend'),
        replace(base, name='C15_BBWP', volatility='expansion'),
        replace(base, name='C16_RETEST', structure='retest'),
        replace(base, name='C17_COLOR_EXIT', exit='opposite')]


def neighbors(base):
    """One factor at a time, +/-20%; never selected using TEST."""
    changes = []
    for factor in (.8, 1.2):
        changes += [dict(ema_fast=round(base.ema_fast*factor)),
                    dict(ema_slow=round(base.ema_slow*factor)),
                    dict(rsi_length=round(base.rsi_length*factor)),
                    dict(cloud_fast=round(base.cloud_fast*factor), cloud_slow=round(base.cloud_slow*factor)),
                    dict(stop_atr=base.stop_atr*factor)]
        if base.dmi in ('threshold','both'): changes.append(dict(adx_level=base.adx_level*factor))
        if base.exit=='runner': changes.append(dict(trail_atr=base.trail_atr*factor))
    return [replace(base, name=f'{base.name}_N{i:02}', **change) for i,change in enumerate(changes)]


FUSIONS = ((), ('MLRSI',), ('BBWP',), ('FLOW',), ('STRUCTURE',),
           ('MLRSI', 'BBWP'), ('MLRSI_RESUME',), ('VPOC',))


def protocol():
    return dict(version='BITMAN_PUBLIC_PROXY_V1', audit_base=BASE_SHA, cutoff=CUTOFF,
        timeframes=['1h', '4h', '1d'], timing_15m='not used in Phase2; avoid extra search',
        candidates=[asdict(c) for c in candidates()], fusion_additions=FUSIONS,
        development_periods=['2020-2021', '2022-2023'], test_period='2024-cutoff; reused OOS',
        selection='Each direction independently: >=30 TRAIN and VALIDATION trades, positive net expectancy both; '
                  'top3 by min(Sharpe)-1.5*worstDD, then choose parent by neighbor lower-quartile score. '
                  'If none eligible, same ranking diagnostic fallback, never promote fallback.',
        fusion_selection='Only after CLASSIC is frozen; same eligibility and score on development, no TEST.',
        costs=dict(base=dict(fee_bps=5, slip_bps=2, stop_slip_bps=5),
                   stress=dict(fee_bps=6, slip_bps=5, stop_slip_bps=10)),
        execution='Closed 1H signal; next 1H open adverse slip; qty=entry equity/entry fill, no rebalancing/pyramiding/reverse.',
        exits='Initial2ATR frozen at signal. Runner: TP1 1R 30%, economic BE total trade, TP2 2R 30%, '
              '40% runner trailing2ATR; trail changes next bar. Opposite trend/cloud exits next open; max168h. '
              'Alternative: opposite with initial stop only. Stop first; after TP1 ambiguous BE before TP2.',
        funding='Historical signed settlements at current remaining qty, nearest 1H open mark proxy. '
                'Pre-order holdings charged at boundary; no claiming actual venue fills or exchange liquidation.',
        structure='Strict2-left2-right pivots available after confirmation close. Retest within3 closed bars after prior-level breakout.',
        bbwp='BBW20 SMA/population std, percentile strictly lower vs PRIOR252 closed widths; '
             'COMPRESSION<15, EXTREME>=90, EXPANSION rising and15..90, otherwise NORMAL.',
        flow='Signed taker pressure >0 (ratio>.5 LONG, <.5 SHORT) and improving over prior3h mean; no .60 gate.',
        vpoc='Proxy: prior72h hourly typical-price volume histogram24 fixed bins, not true volume-at-price.',
        mlrsi='Byte-identical LOW29 EMA4 PINE_PARITY_V4 from observer; causal yearly Jan1 sessions, '
              'bootstrap <=3200 preceding available closed1H, persistent array within year. No exact TV parity claim.',
        diagnostics=['yearly fixed-parameter walk-forward', '2026 behavior, no tuning', 'long/short separately',
                     'one-block ablation', 'neighbors14', 'stress', 'remove top1/top3', 'weekly bootstrap500 seed773',
                     'bull/bear/range', 'high/low volatility by TRAIN median', 'pattern proxies diagnostic only'],
        promotion=dict(test_expectancy_positive=True, pf_gt=1.20, sharpe_gt=.75, maxdd_lt=.20,
                       min_test_trades=100, positive_neighbors_fraction=.8, stress_positive=True,
                       without_best3_positive=True),
        forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',
        shadow_only=True, trade_authority=False)
