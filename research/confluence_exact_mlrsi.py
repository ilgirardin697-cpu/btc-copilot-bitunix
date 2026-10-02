"""Limited BackQuant-style rolling ML RSI experiment. Public cached data only.

Run: python -m research.confluence_exact_mlrsi
No change to the first investigation or any production module.
Independent implementation of the algorithm specified by the user; not a
verbatim redistribution of Pine, nor a claim of TradingView chart parity.
"""
from __future__ import annotations

from collections import deque
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from research import confluence_engine_backtest as common

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'exact_mlrsi_artifacts'
SPLITS = {'TRAIN': (common.START, common.TRAIN_END),
          'VALIDATION': (common.TRAIN_END, common.TEST_START),
          'TEST': (common.TEST_START, common.ASOF),
          'ALL': (common.START, common.ASOF)}
SPEC = {
    'name': 'I-GOD CONFLUENCE ENGINE — causal BackQuant ML RSI',
    'rsi_lengths': [14, 27], 'source': 'close', 'smooth': True,
    'smoothing': 'EMA', 'smoothing_length': 4,
    'maxData': 3000, 'maxIter': 1000, 'clusters': 3,
    'initialization_percentiles': [25, 50, 75],
    'distance': 'absolute', 'update': 'arithmetic mean',
    'ties': 'lowest centroid index', 'empty_cluster': 'retain prior centroid',
    'minimum_valid_observations': 4,
    'rolling': 'last maxData finite smoothed RSI samples through current close',
    'convergence': 'unchanged assignment boundaries or exact centroid equality',
    'trigger_minutes': 60, 'regime_minutes': 60, 'sma_length': 200,
    'modes': ['STATE', 'EVENT'], 'systems': ['M', 'RM', 'LM', 'RLM'],
    'taker_thresholds': [0.55, 0.60, 0.65],
    'exits': ['opposite', 'atr'], 'atr_length': 14, 'atr_multiplier': 2,
    'cost_per_side': 0.001, 'cost_sensitivity': [0.0005, 0.001, 0.002],
    'sizing': 'fixed quantity sized 1x equity at entry; effective exposure can drift',
    'selection': 'LONG at fixed 60% taker only, TRAIN >=20 trades and positive expectancy; VALIDATION >=20 trades, highest Sharpe then expectancy then TRAIN Sharpe; thresholds 55/65 diagnostics only; TEST absent',
    'short': 'diagnostic RLM mirror only, never promoted',
    'test_start': common.TEST_START, 'as_of': common.ASOF,
    'promotion': {'test_positive': True, 'test_expectancy_positive': True,
                  'remove_best_and_top3_positive': True,
                  'all_taker_neighbors_test_positive': True,
                  'both_rsi_presets_same_selected_mode_system_exit_test_positive': True,
                  'opposite_mode_not_destructive': 'TEST return >= -10%',
                  'probability_1_before_1': '24h TEST >=55%, 7-day block-bootstrap lower 95% bound >50%, and exceeds all-hour control by >=2 percentage points',
                  'max_drawdown': 'TEST and ALL >= -35%',
                  '20bps': 'TEST and ALL net return positive'},
    'bootstrap': {'replicates': 500, 'seed': 773, 'block_days': 7},
    'source_urls': ['https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/',
                    'https://tradingmike.blogspot.com/2025/06/2025-06-13rsi.html',
                    'https://www.tradingview.com/pine-script-docs/language/arrays/'],
}


def pine_rsi(close, length):
    """Wilder RMA seeded by the first length price changes, not the first bar."""
    close = np.asarray(close, float)
    result = np.full(len(close), np.nan)
    if len(close) <= length:
        return result
    changes = np.diff(close)
    gain = np.maximum(changes, 0)
    loss = np.maximum(-changes, 0)
    up, down = float(gain[:length].mean()), float(loss[:length].mean())
    for i in range(length, len(close)):
        if i > length:
            up = (up * (length - 1) + gain[i - 1]) / length
            down = (down * (length - 1) + loss[i - 1]) / length
        result[i] = 100 * up / (up + down) if up + down else np.nan
    return result


def pine_ema(values, length=4):
    """First finite value initializes EMA; unavailable leading values stay NaN."""
    result = np.full(len(values), np.nan)
    previous = np.nan
    alpha = 2 / (length + 1)
    for i, value in enumerate(values):
        if np.isfinite(value):
            previous = value if not np.isfinite(previous) else alpha * value + (1 - alpha) * previous
            result[i] = previous
    return result


def cluster_three(values, max_iter=1000):
    """Lloyd iteration for 1D absolute-distance assignment and mean update.

    Sorted partitions and prefix sums are mathematically equivalent to assigning
    every sample individually. Every candle REINITIALIZES at p25/p50/p75.
    Summation order can differ from Pine by machine precision. Empty clusters
    retain their prior centroid (explicit deterministic degenerate-data policy).
    """
    values = np.sort(np.asarray(values, float))
    if len(values) < 4 or not np.all(np.isfinite(values)):
        raise ValueError('Need at least four finite RSI observations')
    if max_iter < 1:
        raise ValueError('maxIter must be positive')
    centers = np.quantile(values, [.25, .5, .75], method='linear')
    sums = np.r_[0., np.cumsum(values)]
    previous_boundaries = None
    for iteration in range(max_iter):
        # Midpoint belongs to earlier/lower centroid on an exact distance tie.
        boundaries = tuple(np.searchsorted(values, (centers[:-1] + centers[1:]) / 2, side='right'))
        if boundaries == previous_boundaries:
            return centers, iteration, True
        limits = (0, *boundaries, len(values))
        updated = centers.copy()
        for k in range(3):
            start, end = limits[k:k + 2]
            if end > start:
                updated[k] = (sums[end] - sums[start]) / (end - start)
        if np.array_equal(updated, centers):
            return updated, iteration + 1, True
        centers = updated
        previous_boundaries = boundaries
    return centers, max_iter, False


def states_and_events(rsi, short_threshold, long_threshold):
    valid = np.isfinite(rsi) & np.isfinite(short_threshold) & np.isfinite(long_threshold)
    state = np.zeros(len(rsi), np.int8)
    state[valid & (rsi > long_threshold)] = 1
    state[valid & (rsi < short_threshold)] = -1
    prior_valid = np.r_[False, valid[:-1]]
    prior_neutral = np.r_[False, state[:-1] == 0] & prior_valid
    return state, valid & prior_neutral & (state == 1), valid & prior_neutral & (state == -1), valid


def rolling_mlrsi(close, length=14, max_data=3000, max_iter=1000):
    if max_data < 4:
        raise ValueError('maxData must be at least four')
    smoothed = pine_ema(pine_rsi(close, length), 4)
    centers = np.full((len(close), 3), np.nan)
    counts = np.zeros(len(close), int)
    iterations = np.zeros(len(close), int)
    converged = np.zeros(len(close), bool)
    history = deque(maxlen=max_data)
    for i, value in enumerate(smoothed):
        if np.isfinite(value):
            history.append(value)
        counts[i] = len(history)
        if len(history) >= 4 and np.isfinite(value):
            centers[i], iterations[i], converged[i] = cluster_three(history, max_iter)
    state, green, red, valid = states_and_events(smoothed, centers[:, 0], centers[:, 2])
    return {'rsi': smoothed, 'centroids': centers, 'short_threshold': centers[:, 0],
            'long_threshold': centers[:, 2], 'state': state, 'green_event': green,
            'red_event': red, 'valid': valid, 'window_count': counts,
            'iterations': iterations, 'converged': converged}


def hourly_inputs(base):
    a = common.aggregate(base, 60)
    sma = common.rolling(a[:, 4], 200)
    regime = np.where(np.isfinite(sma), np.where(a[:, 4] > sma, 1, -1), 0)
    c = a[:, 4]
    previous = common.shift(c)
    tr = np.maximum(a[:, 2] - a[:, 3], np.maximum(abs(a[:, 2] - previous), abs(a[:, 3] - previous)))
    tr[0] = a[0, 2] - a[0, 3]
    atr = common.ema(tr, 1 / 14)
    ratio = np.divide(a[:, 6], a[:, 5], out=np.full(len(a), .5), where=a[:, 5] > 0)
    return a, regime, atr, ratio


def entry_signal(ml, regime, ratio, system, mode, threshold=.60, side=1):
    signal = (ml['state'] == side) & ml['valid'] if mode == 'STATE' else ml['green_event' if side == 1 else 'red_event'].copy()
    if 'R' in system:
        signal &= regime == side
    if 'L' in system:
        signal &= ratio >= threshold if side == 1 else ratio <= 1 - threshold
    return signal


def execution_features(ml, regime, atr, system, side):
    # Non-regime strategies have no hidden SMA filter in their exits.
    reg = regime == 1 if 'R' in system else np.full(len(atr), side == 1)
    return {'reg': reg, 'state': ml['state'], 'atr': atr,
            'low': np.full(len(atr), np.nan), 'high': np.full(len(atr), np.nan)}


def simulate(a, ml, regime, atr, ratio, funding, row, lo, hi, cost=.001):
    f = execution_features(ml, regime, atr, row['system'], row['side'])
    sig = entry_signal(ml, regime, ratio, row['system'], row['mode'], row['threshold'], row['side'])
    return common.simulate(a, f, sig, funding, 60, row['exit'], row['side'], cost=cost, lo=lo, hi=hi)


def select(rows):
    """Fixed 60% primary preset selection. No TEST field is ever accessed."""
    eligible = [r for r in rows if r['side'] == 1 and r['threshold'] == .60
                and r['TRAIN']['trades'] >= 20 and r['VALIDATION']['trades'] >= 20
                and r['TRAIN']['expectancy'] > 0]
    if not eligible:
        return None
    return max(eligible, key=lambda r: (r['VALIDATION']['Sharpe'], r['VALIDATION']['expectancy'], r['TRAIN']['Sharpe'], r['id']))


def specifications():
    rows = []
    for length in (14, 27):
        for mode in ('STATE', 'EVENT'):
            # SHORT is the requested three-block mirror only, not a second search.
            for side, systems in ((1, ('M', 'RM', 'LM', 'RLM')), (-1, ('RLM',))):
                for system in systems:
                    for threshold in ((.55, .60, .65) if 'L' in system else (.60,)):
                        for exit_kind in ('opposite', 'atr'):
                            rows.append({'id': f'RSI{length}_{mode}_{system}_{threshold:.2f}_{exit_kind}_{side}',
                                         'length': length, 'mode': mode, 'system': system,
                                         'threshold': threshold, 'exit': exit_kind, 'side': side})
    return rows


def block_bootstrap(returns, tf=60):
    rr = np.asarray(returns)
    rng = np.random.default_rng(773)
    block = 7 * 24 * 60 // tf
    estimates = []
    for _ in range(500):
        starts = rng.integers(0, len(rr), size=(len(rr) + block - 1) // block)
        indices = np.concatenate([(np.arange(block) + s) % len(rr) for s in starts])[:len(rr)]
        estimates.append(common.performance(rr[indices], tf)['CAGR'])
    return {'CAGR_95_interval': np.quantile(estimates, [.025, .975]).tolist(),
            'probability_CAGR_positive': float(np.mean(np.array(estimates) > 0))}


def probability_bootstrap(base, times):
    """24h +1/-1 all-signal outcomes, resample calendar 7-day blocks."""
    times = times[(times >= common.TEST_START) & (times + 24 * 3600000 <= common.ASOF)]
    days = int((common.ASOF - common.TEST_START) // 86400000)
    wins = np.zeros(days)
    counts = np.zeros(days)
    for t in times:
        i = np.searchsorted(base[:, 0], t)
        path = base[i:i + 288]
        entry = path[0, 1]
        good = np.flatnonzero(path[:, 2] >= entry * 1.01)
        bad = np.flatnonzero(path[:, 3] <= entry * .99)
        day = int((t - common.TEST_START) // 86400000)
        counts[day] += 1
        wins[day] += bool(len(good) and (not len(bad) or good[0] < bad[0]))
    rng = np.random.default_rng(773)
    estimates = []
    for _ in range(500):
        starts = rng.integers(0, days, size=(days + 6) // 7)
        indices = np.concatenate([(np.arange(7) + s) % days for s in starts])[:days]
        denominator = counts[indices].sum()
        if denominator:
            estimates.append(float(wins[indices].sum() / denominator))
    return {'n': int(counts.sum()), 'probability': float(wins.sum() / counts.sum()) if counts.sum() else None,
            '95_interval': np.quantile(estimates, [.025, .975]).tolist() if estimates else [],
            'method': '500 circular 7-day calendar block resamples; overlapping signals remain dependent; no multiplicity correction'}


def outcomes(base, a, signal, side):
    times = a[1:, 0][signal[:-1]]
    return {label: common.excursions(base, times[(times >= lo) & (times < hi)], side, hi)
            for label, (lo, hi) in SPLITS.items() if label != 'ALL'}


def evaluate():
    OUT.mkdir(exist_ok=True)
    frozen = json.dumps(SPEC, indent=2, ensure_ascii=False)
    (OUT / 'frozen_spec.json').write_bytes(frozen.encode('utf-8'))
    base, funding = common.load_data()
    a, regime, atr, ratio = hourly_inputs(base)
    prepared = {}
    for length in (14, 27):
        prepared[length] = rolling_mlrsi(a[:, 4], length)
        print(f'Causal clustering complete: RSI{length}', flush=True)
    # All indicators are pointwise causal despite computing the full price array.
    rows = specifications()
    for row in rows:
        ml = prepared[row['length']]
        for label in ('TRAIN', 'VALIDATION'):
            lo, hi = SPLITS[label]
            row[label] = simulate(a, ml, regime, atr, ratio, funding, row, lo, hi)['metrics']
    best = select(rows)
    eligible = best is not None
    if best is None:
        # Report one fixed diagnostic; do not invent a TEST-selected fallback.
        best = next(r for r in rows if r['id'] == 'RSI14_STATE_RLM_0.60_opposite_1')
    lock = {'selected_id': best['id'], 'eligible': eligible,
            'spec_sha256': hashlib.sha256(frozen.encode()).hexdigest(),
            'selection_inputs': [{k: row[k] for k in ('id', 'length', 'mode', 'system', 'threshold', 'side', 'TRAIN', 'VALIDATION')} for row in rows]}
    (OUT / 'selection_lock.json').write_text(json.dumps(lock, indent=2))
    print(f'Frozen selection before TEST: {best["id"]}', flush=True)
    outcome_cache = {}
    selected_simulation = None
    for number, row in enumerate(rows):
        ml = prepared[row['length']]
        for label in ('TEST', 'ALL'):
            lo, hi = SPLITS[label]
            sim = simulate(a, ml, regime, atr, ratio, funding, row, lo, hi)
            row[label] = sim['metrics']
            if label == 'ALL':
                if row['id'] == best['id']:
                    selected_simulation = sim
                treturns = np.array([t['return'] for t in sim['trades']])
                ranked = np.argsort(treturns)[::-1]
                row['without_best_trades'] = {str(n): float(np.prod(1 + np.delete(treturns, ranked[:n])) - 1) for n in (1, 3)}
                row['bootstrap_ALL'] = block_bootstrap(sim['returns'])
        row['by_year'] = {}
        for year in (2024, 2025, 2026):
            lo = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            hi = min(common.ASOF, int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000))
            row['by_year'][str(year)] = simulate(a, ml, regime, atr, ratio, funding, row, lo, hi)['metrics']
        row['costs'] = {}
        for bps in (5, 10, 20):
            row['costs'][str(bps)] = {label: simulate(a, ml, regime, atr, ratio, funding, row, lo, hi, bps / 10000)['metrics']
                                    for label, (lo, hi) in SPLITS.items() if label in ('TEST', 'ALL')}
        key = (row['length'], row['mode'], row['system'], row['threshold'], row['side'])
        if key not in outcome_cache:
            sig = entry_signal(ml, regime, ratio, row['system'], row['mode'], row['threshold'], row['side'])
            outcome_cache[key] = outcomes(base, a, sig, row['side'])
        row['outcomes'] = outcome_cache[key]
        if number % 8 == 0:
            print(f'Frozen TEST/robustness: {number + 1}/{len(rows)}', flush=True)
    ml = prepared[best['length']]
    sig = entry_signal(ml, regime, ratio, best['system'], best['mode'], best['threshold'])
    times = a[1:, 0][sig[:-1]]
    prob = probability_bootstrap(base, times)
    control_times = a[1:, 0]
    control = probability_bootstrap(base, control_times)
    def counterparts(field, values):
        return [next(r for r in rows if all(r[k] == best[k] for k in ('length', 'mode', 'system', 'exit', 'side', 'threshold') if k != field) and r[field] == value)
                for value in values]
    neighbors = counterparts('threshold', (.55, .60, .65)) if 'L' in best['system'] else [best]
    presets = counterparts('length', (14, 27))
    modes = counterparts('mode', ('STATE', 'EVENT'))
    lower = prob['95_interval'][0] if prob['95_interval'] else 0
    gates = {'selection_eligible': eligible,
             'TEST_positive': best['TEST']['total_return'] > 0,
             'TEST_expectancy_positive': best['TEST']['expectancy'] > 0,
             'without_top1_top3': all(v > 0 for v in best['without_best_trades'].values()),
             'taker_stability': all(r['TEST']['total_return'] > 0 and r['TEST']['expectancy'] > 0 for r in neighbors),
             'RSI14_RSI27_stability': all(r['TEST']['total_return'] > 0 and r['TEST']['expectancy'] > 0 for r in presets),
             'STATE_EVENT_stability': all(r['TEST']['total_return'] >= -.10 for r in modes),
             '1_before_1': prob['probability'] is not None and prob['probability'] >= .55 and lower > .50 and prob['probability'] >= (control['probability'] or 1) + .02,
             'drawdown': best['ALL']['MaxDD'] >= -.35 and best['TEST']['MaxDD'] >= -.35,
             '20bps': all(best['costs']['20'][label]['total_return'] > 0 for label in ('ALL', 'TEST'))}
    conclusion = 'PROMOTE TO SHADOW' if all(gates.values()) else ('PROMISING — MORE RESEARCH' if best['TEST']['total_return'] > 0 and best['TEST']['expectancy'] > 0 else 'REJECT')
    result = {'spec': SPEC, 'selected': best['id'], 'selection_eligible': eligible,
              'best': best, 'rows': rows, 'promotion_gates': gates, 'conclusion': conclusion,
              'matched_RSI_presets': [r['id'] for r in presets], 'matched_modes': [r['id'] for r in modes],
              'matched_thresholds': [r['id'] for r in neighbors],
              'TEST_probability_bootstrap': prob, 'TEST_all_hours_control': control,
              'V8_benchmark': json.loads((common.OUT / 'benchmark.json').read_text())['V8'],
              'clustering_diagnostics': {str(length): {'valid_bars': int(prepared[length]['valid'].sum()), 'not_converged': int(np.sum(prepared[length]['valid'] & ~prepared[length]['converged'])), 'max_iterations_used': int(prepared[length]['iterations'].max())} for length in (14, 27)},
              'data_manifest_sha256': hashlib.sha256((common.OUT / 'data_manifest.json').read_bytes()).hexdigest()}
    result['matched_confluence_thresholds'] = [r['id'] for r in rows if r['system']=='RLM' and r['length']==best['length'] and r['mode']==best['mode'] and r['exit']==best['exit'] and r['side']==1]
    result['matched_four_systems'] = [r['id'] for r in rows if r['length']==best['length'] and r['mode']==best['mode'] and r['exit']==best['exit'] and r['threshold']==.60 and r['side']==1]
    (OUT / 'results.json').write_text(json.dumps(common.clean(result), indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    with gzip.open(OUT / 'hourly_centroids.csv.gz', 'wt', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['open_timestamp', 'available_at_close', 'preset', 'smoothed_rsi', 'low', 'mid', 'high', 'state', 'green_event', 'red_event', 'window_count', 'iterations'])
        for length, values in prepared.items():
            for i in range(len(a)):
                writer.writerow([int(a[i, 0]), int(a[i, 0] + 3600000), length, values['rsi'][i], *values['centroids'][i], int(values['state'][i]), int(values['green_event'][i]), int(values['red_event'][i]), int(values['window_count'][i]), int(values['iterations'][i])])
    with gzip.open(OUT / 'selected_trades.csv.gz', 'wt', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['entry_time', 'exit_time', 'return', 'reason', 'side'])
        writer.writeheader()
        writer.writerows(selected_simulation['trades'])
    write_report(result)
    print(json.dumps({'selected': best['id'], 'conclusion': conclusion, 'TEST': best['TEST'], 'probability': prob}, indent=2), flush=True)


def write_report(d):
    best = d['best']
    lines = ['# I-GOD CONFLUENCE ENGINE — segunda pasada ML RSI', '', f'**{d["conclusion"]}**', '',
             f'Selección bloqueada antes de TEST: `{best["id"]}`. Exclusivamente trigger/régimen 1H; no búsqueda de nuevos timeframes.', '',
             '## Reproducción del indicador', '',
             'Implementación independiente del algoritmo solicitado: RSI Wilder con semilla SMA de las primeras 14 o 27 variaciones, EMA4, últimos 3000 RSI suavizados finitos disponibles, tres centroides reinicializados p25/p50/p75 en cada cierre, asignación por distancia absoluta y actualización por media. Máximo 1000 iteraciones. GREEN estrictamente sobre el centroide alto; RED estrictamente bajo el bajo; igualdad es NEUTRAL. EVENT requiere una barra previa válida NEUTRAL y la actual GREEN/RED, excluyendo saltos directos RED↔GREEN.', '',
             'La ventana contiene el RSI de la vela actual cerrada. Se recalcula en cada vela desde cero, sin warm-start ni centroides del futuro. Usamos cuatro observaciones válidas como mínimo; no exigimos 3000 para arrancar. Empates van al cluster de menor índice; los clusters vacíos conservan su centroide anterior. La partición ordenada y sumas acumuladas son equivalentes matemáticamente a asignar cada observación, con diferencias de redondeo posibles frente a Pine.', '',
             'Adaptación CAUSAL rolling de BackQuant, no paridad literal con TradingView: se elimina la condición dependiente de last_bar_index y su ventana anclada al final del gráfico. La copia pública tiene arrays de tamaño 3 seguidos de push y una función ma ausente; no se ejecutan esas anomalías. La página oficial confirma el método, pero no hemos validado una exportación numérica del indicador desde TradingView. Para comprobar tu configuración concreta faltan confirmación de fuente close, smooth=true/EMA, maxData=3000, maxIter=1000 y timeframe 1H; en ambos presets se asumen estos valores. No hay thresholds RSI fijos 55/45 en este experimento.', '',
             'Fuentes: [BackQuant oficial](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/), [copia pública atribuida](https://tradingmike.blogspot.com/2025/06/2025-06-13rsi.html), [semántica de arrays Pine](https://www.tradingview.com/pine-script-docs/language/arrays/). No redistribuimos el Pine. Fuente de parámetros: instrucciones del usuario y copia atribuida, con las reservas anteriores.', '',
             '## Diseño cerrado y contabilidad', '',
             'Cuatro entradas LONG: M, RM, LM, RLM. STATE o NEUTRAL→GREEN; RSI14 o RSI27; taker 55/60/65 solo en sistemas que lo utilizan. Dos salidas: estado ML RSI contrario (y régimen invalidado cuando la entrada incorpora R), o ATR14 2x trailing. NEUTRAL no es señal contraria. SHORT únicamente RLM espejo diagnóstico, sin promoción. Las estrategias M/LM no incorporan un filtro de régimen oculto en su salida.', '',
             'TRAIN 2020–2021, VALIDATION 2022–2023, TEST 2024–2026 hasta 2026-10-02 UTC. 710.208 velas cerradas 5m y 7.398 funding históricos del cache verificado del PR #4, agregadas a 59.184 velas 1H. Sin descarga ni uso de datos actuales. Taker comprador es volumen base taker buy / volumen total; vendedor es su complemento. El nuevo código conserva intactos V8, Railway, el backtest anterior y los artefactos del PR #4.', '',
             'Selección LONG solamente entre variantes al 60%, con >=20 trades en TRAIN y VALIDATION y expectancy TRAIN positiva, usando Sharpe VALIDATION y desempates predefinidos. 55/65 son vecinos diagnósticos, nunca seleccionables. La selección se persiste antes de calcular métricas TEST; TEST no participa. Si no hay elegibles, se informa una combinación fija RSI14/STATE/RLM/60%/opposite como diagnóstico, sin seleccionar desde TEST.', '',
             'Ejecutamos en apertura siguiente al cierre de señal. Capital 1x al entrar, cantidades fijas, sin rebalanceo ni liquidación de exchange: el funding puede hacer variar la exposición efectiva. Coste taker+slippage de 5/10/20 bps por lado, mitad fees y mitad slippage; funding firmado histórico. Stops ya conocidos al inicio de la vela y trailing actualizado al cierre para la vela siguiente; gap ejecutado conservadoramente. DD sobre equity al cierre. Los splits cierran posiciones y no comparten holdings; los indicadores sí pueden utilizar historia causal anterior al split.', '',
             'Probabilidades y MFE/MAE usan todas las señales, incluso solapadas, con entrada a siguiente apertura 1H y recorrido real de velas 5m. Si ambos niveles se tocan en la misma vela 5m se cuenta primero adverso; no alcanzar el objetivo dentro del horizonte es fallo. Los recorridos no cruzan splits. Probabilidades de precio excluyen costes; métricas de trading los incluyen. Un 50% no es automáticamente el azar de BTC a horizonte finito: incluimos además un control de todas las aperturas 1H de TEST. El bootstrap de calendario conserva dependencia local, pero no corrige toda la multiplicidad de selección.', '',
             '## Resultados completos por preset/sistema/modo/salida', '',
             '| Preset | Modo | Sistema | Taker | Salida | L/S | CAGR ALL | Sharpe ALL | MaxDD ALL | Expectancy ALL | PF ALL | Trades ALL | Streak ALL | TEST return | TEST expectancy |',
             '|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in d['rows']:
        m = row['ALL']; t = row['TEST']; pf = m['profit_factor']
        lines.append(f"| RSI{row['length']} | {row['mode']} | {row['system']} | {row['threshold']:.0%} | {row['exit']} | {'L' if row['side']==1 else 'S'} | {m['CAGR']:.2%} | {m['Sharpe']:.3f} | {m['MaxDD']:.2%} | {m['expectancy']:.4%} | {format(pf,'.3f') if pf is not None else 'NA'} | {m['trades']} | {m['longest_losing_streak']} | {t['total_return']:.2%} | {t['expectancy']:.4%} |")
    lines += ['', '## Probabilidades TEST a 24h, todas las entradas', '', '| Preset | Modo | Sistema | Taker | L/S | n | +0.5/-0.5 | +1/-0.5 | +1/-1 | +2/-1 | +3/-1 |', '|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|']
    seen = set()
    for row in d['rows']:
        key = (row['length'], row['mode'], row['system'], row['threshold'], row['side'])
        if key in seen: continue
        seen.add(key)
        item = row['outcomes']['TEST']['24']; p = item['first_passage']
        values = [p[k] for k in ('0.005/0.005', '0.01/0.005', '0.01/0.01', '0.02/0.01', '0.03/0.01')]
        lines.append(f"| RSI{row['length']} | {row['mode']} | {row['system']} | {row['threshold']:.0%} | {'L' if row['side']==1 else 'S'} | {item['n']} | " + ' | '.join(f'{v:.2%}' if v is not None else 'NA' for v in values) + ' |')
    lines += ['', '## Comparaciones emparejadas, sin cambiar selección', '', '| Variante | TEST CAGR | TEST Sharpe | TEST DD | TEST return | +1/-1 24h | +2/-1 24h |', '|---|---:|---:|---:|---:|---:|---:|']
    ids = set(d['matched_RSI_presets'] + d['matched_modes'] + d['matched_thresholds'] + d.get('matched_confluence_thresholds', []) + d.get('matched_four_systems', []))
    for row in d['rows']:
        if row['id'] not in ids: continue
        t = row['TEST']; p = row['outcomes']['TEST']['24']['first_passage']
        probs = [f'{p[k]:.2%}' if p[k] is not None else 'NA' for k in ('0.01/0.01', '0.02/0.01')]
        lines.append(f"| {row['id']} | {t['CAGR']:.2%} | {t['Sharpe']:.3f} | {t['MaxDD']:.2%} | {t['total_return']:.2%} | {probs[0]} | {probs[1]} |")
    lines += ['', '## Señales TEST: cinco horizontes', '', '| Horas | n | MFE media | MAE media | +0.5/-0.5 | +1/-0.5 | +1/-1 | +2/-1 | +3/-1 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for horizon, item in best['outcomes']['TEST'].items():
        p = item['first_passage']; values = [p[k] for k in ('0.005/0.005', '0.01/0.005', '0.01/0.01', '0.02/0.01', '0.03/0.01')]
        means = [f'{item[k]:.2%}' if item[k] is not None else 'NA' for k in ('MFE_mean', 'MAE_mean')]
        lines.append(f"| {horizon} | {item['n']} | {means[0]} | {means[1]} | " + ' | '.join(f'{v:.2%}' if v is not None else 'NA' for v in values) + ' |')
    lines += ['', '## Robustez del seleccionado', '', f"Sin mejor trade: {best['without_best_trades']['1']:.2%}; sin tres mejores: {best['without_best_trades']['3']:.2%}. Bootstrap CAGR: {best['bootstrap_ALL']}.", '', f"Bootstrap +1% antes de -1% en 24h TEST: {d['TEST_probability_bootstrap']}. Control todas las horas: {d['TEST_all_hours_control']}.", '', '| Año | Return | Expectancy | DD |', '|---|---:|---:|---:|']
    for year, m in best['by_year'].items(): lines.append(f"| {year} | {m['total_return']:.2%} | {m['expectancy']:.4%} | {m['MaxDD']:.2%} |")
    lines += ['', 'La tabla anterior son ejecuciones anuales independientes, flat en sus límites; no se debe multiplicar sus returns para reconstruir TEST.']
    if 'by_year_continuous_TEST' in best:
        lines += ['', '| Año, equity continua de TEST | Return | Sharpe | DD |', '|---|---:|---:|---:|']
        for year, m in best['by_year_continuous_TEST'].items(): lines.append(f"| {year} | {m['total_return']:.2%} | {m['Sharpe']:.3f} | {m['MaxDD']:.2%} |")
    lines += ['', '| Bps/lado | ALL return | TEST return | TEST expectancy |', '|---|---:|---:|---:|']
    for bps, value in best['costs'].items(): lines.append(f"| {bps} | {value['ALL']['total_return']:.2%} | {value['TEST']['total_return']:.2%} | {value['TEST']['expectancy']:.4%} |")
    lines += ['', 'Gates predefinidos:', '', *[f'- {name}: {value}' for name, value in d['promotion_gates'].items()], '',
              '## Artefactos y reproducción', '',
              '`python -m research.confluence_exact_mlrsi`; `python -m unittest discover -v`; `git diff --check`.', '',
              '`exact_mlrsi_artifacts/results.json` incluye todos los splits, probabilidades de las cinco combinaciones solicitadas, MFE/MAE de cinco horizontes, vecinos, costes, años, bootstrap y eliminación de trades para cada configuración. `hourly_centroids.csv.gz` conserva RSI, los tres centroides, states/events, tamaño de ventana y timestamp de disponibilidad para ambos presets. `selection_lock.json` no contiene TEST. Reutilizamos el manifest/checksum de datos del primer PR y guardamos su hash en los resultados. No API privada, órdenes, merge ni deploy.']
    if 'L' not in best['system']:
        lines += ['', 'El seleccionado no utiliza taker: su gate de estabilidad taker es vacuo, no evidencia de liquidez/orderflow. La tabla emparejada muestra separadamente RLM con 55/60/65 y las cuatro entradas al preset/modo/salida seleccionados. No se atribuye a confluencia el rendimiento del ML RSI solo.']
    if 'without_best_trades_TEST' in best:
        lines += ['', f"**Dependencia de TEST: sin su mejor operación, return {best['without_best_trades_TEST']['1']:.2%}; sin sus tres mejores, {best['without_best_trades_TEST']['3']:.2%}.** El gate inicial de eliminación de operaciones corresponde a ALL; esta comprobación adicional TEST tiene prioridad en la interpretación. No hay promoción."]
    if best['system'] == 'M':
        modes = [r for r in d['rows'] if r['id'] in d['matched_modes']]
        if len(modes) == 2 and modes[0]['TEST']['total_return'] == modes[1]['TEST']['total_return']:
            lines += ['', 'Con ML RSI solo y salida opposite, STATE y EVENT producen el mismo P&L TEST: las señales repetidas GREEN llegan con una posición ya abierta. Sus probabilidades posteriores no son iguales porque STATE incluye cada cierre verde y EVENT solamente el cambio NEUTRAL→GREEN. No puede atribuirse una ventaja económica al evento a partir de una tasa de acierto por señal más alta; las cohortes y tamaños son diferentes. En RLM, STATE permite confirmar taker durante un tramo verde posterior, mientras EVENT exige coincidencia en la barra de transición.']
            if modes[0]['VALIDATION']['Sharpe'] == modes[1]['VALIDATION']['Sharpe']:
                lines += ['', 'STATE/EVENT también empatan en Sharpe VALIDATION en el seleccionado: STATE se informa por desempate determinista del ID, no porque haya demostrado un Sharpe superior a EVENT.']
    if 'selected_bootstrap_TEST' in d:
        lines += ['', f"Bootstrap CAGR TEST del seleccionado: {d['selected_bootstrap_TEST']}."]
    (ROOT / 'CONFLUENCE_EXACT_MLRSI_RESULTS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def supplemental_report():
    """Additional matched bookkeeping, without reranking or changing parameters."""
    d = json.loads((OUT / 'results.json').read_text(encoding='utf-8'))
    base, funding = common.load_data()
    a, regime, atr, ratio = hourly_inputs(base)
    with gzip.open(OUT / 'hourly_centroids.csv.gz', 'rt') as stream:
        recorded = np.genfromtxt(stream, delimiter=',', skip_header=1)
    prepared = {}
    for length in (14, 27):
        r = recorded[recorded[:, 2] == length]
        if len(r) != len(a) or not np.array_equal(r[:, 0], a[:, 0]):
            raise ValueError('Clustering artifact does not match input candle timestamps')
        valid = np.isfinite(r[:, 4]) & np.isfinite(r[:, 6])
        prepared[length] = {'state': r[:, 7].astype(int), 'green_event': r[:, 8].astype(bool),
                            'red_event': r[:, 9].astype(bool), 'valid': valid}
    best = next(r for r in d['rows'] if r['id'] == d['selected'])
    d['matched_confluence_thresholds'] = [r['id'] for r in d['rows'] if r['system'] == 'RLM' and all(r[k] == best[k] for k in ('length', 'mode', 'exit', 'side'))]
    d['matched_four_systems'] = [r['id'] for r in d['rows'] if r['threshold'] == .60 and all(r[k] == best[k] for k in ('length', 'mode', 'exit', 'side'))]
    for row in d['rows']:
        test_sim = simulate(a, prepared[row['length']], regime, atr, ratio, funding, row, common.TEST_START, common.ASOF)
        calendar = a[(a[:, 0] >= common.TEST_START) & (a[:, 0] + 3600000 <= common.ASOF), 0]
        rr = np.array(test_sim['returns'])
        row['by_year_continuous_TEST'] = {}
        for year in (2024, 2025, 2026):
            begin = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            end = min(common.ASOF, int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000))
            row['by_year_continuous_TEST'][str(year)] = common.performance(rr[(calendar >= begin) & (calendar < end)], 60)
        compounded = np.prod([1 + m['total_return'] for m in row['by_year_continuous_TEST'].values()]) - 1
        if not np.isclose(compounded, row['TEST']['total_return'], atol=1e-10):
            raise ValueError('Continuous annual returns do not reconstruct TEST equity')
        returns = np.array([t['return'] for t in test_sim['trades']])
        ranked = np.argsort(returns)[::-1]
        row['without_best_trades_TEST'] = {str(n): float(np.prod(1 + np.delete(returns, ranked[:n])) - 1) for n in (1, 3)}
        if row['id'] == best['id']:
            d['selected_bootstrap_TEST'] = block_bootstrap(test_sim['returns'])
    # Do not revise the frozen mechanical gates after observing TEST. These
    # stronger bookkeeping checks are reported separately, not used to rerank.
    d['best'] = best
    d['supplemental_TEST_trade_removal_passes'] = all(v > 0 for v in best['without_best_trades_TEST'].values())
    (OUT / 'results.json').write_text(json.dumps(common.clean(d), indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    write_report(d)
    with (ROOT / 'CONFLUENCE_EXACT_MLRSI_RESULTS.md').open('a', encoding='utf-8') as stream:
        stream.write(f"\nComprobación suplementaria TEST sin mejor trade: {best['without_best_trades_TEST']['1']:.2%}; sin los tres mejores: {best['without_best_trades_TEST']['3']:.2%}. No se modifica la selección ni se retocan parámetros. Bootstrap TEST del seleccionado: {d['selected_bootstrap_TEST']}.\n")


if __name__ == '__main__':
    evaluate()
    supplemental_report()
