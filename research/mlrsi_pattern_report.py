"""Descriptive report/controls for the already frozen, completed study. No search."""
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
from research import mlrsi_pattern_backtest as s


def pct(value):
    return '—' if value is None else f'{value * 100:+.3f}%'


def num(value):
    return '—' if value is None else f'{value:.3f}'


def table(lines, headers, rows):
    lines += ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    lines += ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows]
    lines.append('')


def report():
    root = s.ROOT
    test = json.loads((root / 'test_results.json').read_text('utf-8'))
    dev = json.loads((root / 'development_results.json').read_text('utf-8'))
    frozen = json.loads((root / 'frozen_selection.json').read_text('utf-8'))
    manifest = json.loads((root / 'data_manifest.json').read_text('utf-8'))
    for data in (test, dev, frozen):
        if data['code_sha256'] != s.digest(s.__file__) or data['prereg_sha256'] != s.digest(root / 'preregistered.json'):
            raise ValueError('FROZEN_ARTIFACT_MISMATCH')
    path = s.CACHE / 'spot_5m.npz'
    if s.digest(path) != test['dataset_sha256']:
        raise ValueError('DATASET_MISMATCH')
    base = s.validate(np.load(path)['bars'], cutoff=test['cutoff'])
    f = dict(np.load(s.CACHE / f"features-{s.digest(path)[:16]}-test-{s.feature_signature()}.npz"))
    diagnostics = dict(code_sha256=s.digest(__file__), study_code_sha256=s.digest(s.__file__),
                       prereg_sha256=test['prereg_sha256'], data_sha256=test['dataset_sha256'], results={})
    # Original preregistered controls/exit baselines, evaluated descriptively.
    # No changes to selection, parameters, classification or event detection.
    for confirm in (1, 2):
        events = s.event_rows(f, confirm)
        controls = s.controls(f, events)
        for name in s.EVENTS:
            key = f'{name}:{confirm}'
            sample = [e for e in events if e['event'] == name and e['period'] == 'TEST']
            matched = [e for e in controls if e['event'] == name and e['period'] == 'TEST']
            models = {}
            for m in s.candidates():
                if m.stop_pct != .003:
                    continue
                rows = s.evaluate_events(base, f, matched, m, s.Costs(), test['cutoff'])
                models[m.key()] = s.summarize(rows)
            primary = s.evaluate_events(base, f, sample, s.Management(), s.Costs(), test['cutoff'])
            color_rows = s.evaluate_events(base, f, sample, s.Management('opposite'), s.Costs(), test['cutoff'])
            diagnostics['results'][key] = dict(controls=models,
                opposite_bootstrap=s.bootstrap(color_rows),
                opposite_stress=s.summarize(s.evaluate_events(base, f, sample, s.Management('opposite'), s.Costs(6, 5, 10), test['cutoff'])),
                opposite_yearly={str(y): s.summarize([r for r in color_rows if r['year'] == y]) for y in (2024, 2025, 2026)},
                primary_yearly={str(y): s.summarize([r for r in primary if r['year'] == y]) for y in (2024, 2025, 2026)},
                primary_regimes={r: s.summarize([t for t in primary if t['regime'] == r]) for r in ('BULL', 'BEAR', 'SIDEWAYS')},
                primary_volatility={v: s.summarize([t for t in primary if t['volatility'] == v]) for v in ('LOW', 'MEDIUM', 'HIGH')},
                primary_recent_descriptive=s.summarize([t for t in primary if t['entry_time'] >= 1759276800000]))
    (root / 'diagnostics.json').write_text(json.dumps(diagnostics, indent=2, allow_nan=False), encoding='utf-8')
    primary_key = s.Management().key()
    primary = lambda key: test['results'][key]['models'][primary_key]['TEST']['metrics']
    lines = ['# ML RSI 15m LOW27 EMA4 — estudio congelado', '',
             '**Clasificación: NO EDGE.** El runner TP1→breakeven→$500 no tiene expectativa neta positiva fuera de muestra. '
             'La falta de paridad exacta con BackQuant bloquea además toda promoción. No se creó un observer SHADOW.', '',
             '## 1. Paridad y alcance', '',
             'No existe paridad numérica verificada. La fuente oficial devolvió HTTP 401; la copia atribuida no prueba la versión instalada. '
             'Ver [PARITY_AUDIT.md](PARITY_AUDIT.md) y [source_manifest.json](source_manifest.json). '
             'Los fixtures son matemáticos independientes, **no exports de TradingView**. '
             'El estudio usa el port causal existente sin modificarlo: LOW, RSI27, EMA4, tres clusters, rolling 3000, máximo 1000 iteraciones.', '',
             '## 2. Datos y metodología', '',
             f"BTCUSDT **Binance spot**, {manifest['rows']:,} velas 5m, "
             + datetime.fromtimestamp(manifest['first_timestamp'] / 1000, timezone.utc).isoformat() + ' → '
             + datetime.fromtimestamp(manifest['as_of'] / 1000, timezone.utc).isoformat() + '.', '',
             f"Se verificaron los checksums de archivos públicos. Hay {manifest['gap_count']} huecos entre velas; no se interpolan. "
             'Solo se agregan grupos completos 15m/1H. Un trade que cruza un hueco se censura, no se convierte en éxito. '
             'Manifest con URLs, hashes, filas y timestamps en [data_manifest.json](data_manifest.json). Datasets y caches grandes quedan fuera de Git.', '',
             'TRAIN 2020–2021; VALIDATION 2022–2023; TEST 2024–último cierre verificado. Se fuerza cierre/censura en límites de split, '
             'sin usar resultados del siguiente período. El protocolo, código y selección quedan unidos por hashes. '
             'Solo tres runners con stop 0.30% eran elegibles para selección: $500, 0.75 ATR1H, 1 ATR1H; score mínimo de expectativa '
             'TRAIN/VALIDATION con n≥100 en ambos. TEST no entra en `choose()`. '
             'Los restantes stops/exits son controles vecinos predefinidos, no candidatos elegidos usando TEST. '
             'Ver [preregistered.json](preregistered.json) y [frozen_selection.json](frozen_selection.json).', '',
             'CROSS dispara una vez al cambiar al color (incluye transición directa desde color opuesto). '
             'RESUME exige el mismo color en ambas velas y reset de pendiente dentro de ese episodio; luego un solo impulso. '
             'Dos barras: CROSS espera dos pendientes del signo nuevo dentro del mismo episodio; RESUME espera dos tras el reset. '
             'Un cambio de color o hueco cancela la confirmación pendiente.', '',
             'Entrada principal: siguiente apertura 15m con slippage adverso. Close-fill es sensibilidad separada y nunca rellena dentro '
             'de la vela de señal. Gestión simulada sobre 5m cerradas: stop primero si se tocan stop y TP; TP1/BE ambiguo sale el runner '
             'a BE conservador. El trailing se actualiza al cierre 5m y se aplica desde la próxima barra, nunca retroactivamente. '
             'ATR1H se congela al señal. Stop nunca se amplía. Todos los modelos tienen límite predefinido 48h; el runner control '
             'sale por color opuesto/48h tras TP1 y BE. La salida simple por color no tiene el stop porcentual y no es comparable en riesgo.', '',
             'Base: taker **5 bps por fill**, slippage 2 bps, stop slippage 5 bps. Stress: 6/5/10 bps. '
             'Entrada, TP parcial y runner pagan costes proporcionales. Supuesto VIP1 publicado en la '
             '[tabla oficial](https://www.bitunix.com/service/handling-fee), no una afirmación del tier real del usuario. '
             'Se puede configurar fee en CLI, congelando el mismo coste en desarrollo y TEST. '
             '**Funding, basis spot/perpetual y fills reales Bitunix no están incluidos**: son retornos teóricos del subyacente con '
             'fees/slippage, no rentabilidad ejecutable de una cuenta futures. Gross retira fricciones del mismo camino/targets, '
             'no vuelve a simular un camino de órdenes distinto.', '',
             'Métricas por evento pueden solaparse; MaxDD/retorno secuencial usan separadamente 1x, una sola posición simulada y '
             'rechazan entradas mientras está ocupada. No hay leverage ni modelo de liquidación. '
             'Win/loss/BE neto usa ±1 bp; precio BE no significa BE neto. MFE/MAE son excursiones conservadoras de las barras '
             'completadas antes de la salida más sus fills; no se atribuyen extremos posteriores al cierre intrabar.', '',
             '## 3. Expectativa por split ($500 / stop 0.30%)', '']
    rows = []
    for key in test['results']:
        values = [dev['results'][key]['models'][primary_key][p]['metrics'] for p in ('TRAIN', 'VALIDATION')] + [primary(key)]
        rows.append([key] + [f"{v['trades']} / {pct(v['mean_net'])}" for v in values])
    table(lines, ['Evento:barras', 'TRAIN n / net medio', 'VALIDATION n / net medio', 'TEST n / net medio'], rows)
    lines += ['## 4. TEST neto y bruto por evento (gestión primaria)', '']
    table(lines, ['Evento:barras', 'Señales/trades', 'Gross medio', 'Net medio', 'Net mediano', 'R', 'PF', 'MaxDD 1x', 'Hold h'],
          [[k, f"{primary(k)['signals']}/{primary(k)['trades']}", pct(primary(k)['mean_gross']), pct(primary(k)['mean_net']),
            pct(primary(k)['median_net']), num(primary(k)['expectancy_r']), num(primary(k)['profit_factor']),
            pct(primary(k)['max_dd']), num(primary(k)['average_hold_hours'])] for k in test['results']])
    table(lines, ['Evento:barras', 'Win', 'Loss', 'BE neto', 'TP1 / move BE', 'Stop antes TP1', 'Salida precio BE', 'Trailing', 'MFE med', 'MAE med', 'Fees/gross profit'],
          [[k] + [pct(primary(k)[field]) for field in ('win_rate', 'loss_rate', 'breakeven_rate', 'tp1_rate',
             'stopped_before_tp1', 'price_be_exit_rate', 'trailing_exit_rate', 'median_mfe', 'median_mae', 'fees_pct_gross_profit')]
           for k in test['results']])
    lines += ['## 5. LONG / SHORT combinados (primario)', '']
    table(lines, ['Barras', 'Cohorte', 'Eventos', 'Net medio', 'R', 'PF', 'Trades secuenciales', 'Retorno secuencial', 'MaxDD'],
          [[c, name, data['primary_fixed500']['trades'], pct(data['primary_fixed500']['mean_net']),
            num(data['primary_fixed500']['expectancy_r']), num(data['primary_fixed500']['profit_factor']),
            data['primary_fixed500']['sequential_trades'], pct(data['primary_fixed500']['sequential_net_return']),
            pct(data['primary_fixed500']['max_dd'])] for c, groups in test['combined'].items() for name, data in groups.items()])
    lines += ['## 6. Baselines y controles emparejados', '',
              'Un timestamp cerrado no-evento por señal, emparejado por mes/año, tendencia 1H, volatilidad y hora UTC; seed773, con reemplazo. '
              'Los denominadores evaluables pueden variar por huecos/fin de datos. No se interpreta una media positiva como edge frente a drift.', '']
    table(lines, ['Evento:barras', 'Salida', 'Señal n/net', 'Control n/net', 'Diferencia descriptiva'],
          [[k, m, f"{v['models'][m]['TEST']['metrics']['trades']} / {pct(v['models'][m]['TEST']['metrics']['mean_net'])}",
            f"{control['trades']} / {pct(control['mean_net'])}",
            pct(v['models'][m]['TEST']['metrics']['mean_net'] - control['mean_net'])]
           for k, v in test['results'].items() for m, control in diagnostics['results'][k]['controls'].items()])
    lines += ['La salida por color tiene otro perfil de riesgo: no usa SL .30%. Sus medias positivas GREEN son un '
              'resultado descriptivo del port causal, no validación del Pine del usuario ni del runner. Se auditan también por año, '
              'stress y bootstrap para no ocultar esta diferencia.', '']
    table(lines, ['Evento:barras', 'Color 2024 net', '2025 net', '2026 net', 'Stress net', 'Color bootstrap 95% net'],
          [[k] + [pct(d['opposite_yearly'][str(y)]['mean_net']) for y in (2024, 2025, 2026)]
           + [pct(d['opposite_stress']['mean_net']), ' / '.join(pct(x) for x in d['opposite_bootstrap']['mean_net_ci95'])]
           for k, d in diagnostics['results'].items()])
    lines += ['## 7. Robustez, costes y concentración', '']
    table(lines, ['Evento:barras', 'Stop .25%', '.30%', '.40%', '.50%', 'ATR .75, stop .30%', 'ATR1, stop .30%'],
          [[k] + [pct(v['models'][m]['TEST']['metrics']['mean_net']) for m in
             ('fixed500_0.0025', 'fixed500_0.003', 'fixed500_0.004', 'fixed500_0.005', 'atr_0.003_0.75', 'atr_0.003_1')]
           for k, v in test['results'].items()])
    table(lines, ['Evento:barras', 'Stress primario net', 'Close-fill net', 'Sin top3 R', 'Sin worst3 R', 'Top3/ganancias netas', 'Bootstrap semanal 95% net'],
          [[k, pct(v['primary_stress']['mean_net']), pct(v['close_fill']['mean_net']), num(primary(k)['without_top3_expectancy_r']),
            num(primary(k)['without_worst3_expectancy_r']), pct(primary(k)['top3_share_net_positive']),
            ' / '.join(pct(x) for x in v['primary_bootstrap']['mean_net_ci95'])] for k, v in test['results'].items()])
    lines += ['Todos los vecinos runner siguen negativos. Dos pendientes, ATR y close-fill no rescatan la hipótesis primaria. '
              'Quitar los mejores o peores tres no la vuelve rentable. El resultado no es una dependencia de un ganador enorme: '
              'es una gestión con expectativa negativa. Los intervalos bootstrap son descriptivos de eventos por bloques semanales, '
              'no una prueba de paridad ni corrección exhaustiva por comparaciones múltiples.', '',
              'La gestión no mejora de manera robusta los baselines. Tomar 30% en +0.30% y salir el 70% al precio de entrada '
              'produce aproximadamente +0.09% bruto; los fees roundtrip rondan 0.10% antes del slippage de salida. '
              'Por eso precio BE puede producir una pérdida neta. Los baselines GREEN por color opuesto tienen medias positivas, '
              'pero distinta exposición/riesgo. En GREEN el año 2025 es negativo y los intervalos bootstrap del baseline '
              'por color incluyen cero: no hay estabilidad suficiente para afirmar edge. No justifican el runner propuesto ni automatización.', '',
              '## 8. Año, tendencia y volatilidad; reciente descriptivo', '',
              'Diagnósticos de contexto sin gating: SMA200 1H ±1% define BULL/BEAR/SIDEWAYS; ATR1H/close define LOW<0.5%, '
              'HIGH≥1%, MEDIUM entre ambos. No se añaden indicadores a sistemas operativos. Desde 2025-10-01 es una vista '
              'reciente descriptiva, no reemplaza TEST ni selecciona parámetros.', '']
    for section, groups in (('Año', ('2024', '2025', '2026')), ('Tendencia', ('BULL', 'BEAR', 'SIDEWAYS')),
                            ('Volatilidad', ('LOW', 'MEDIUM', 'HIGH'))):
        field = {'Año': 'primary_yearly', 'Tendencia': 'primary_regimes', 'Volatilidad': 'primary_volatility'}[section]
        lines.append('### ' + section + '\n')
        table(lines, ['Evento:barras'] + [g + ' n / net' for g in groups],
              [[k] + [f"{d[field][g]['trades']} / {pct(d[field][g]['mean_net'])}" for g in groups]
               for k, d in diagnostics['results'].items()])
    table(lines, ['Evento:barras', 'Reciente n', 'Net medio'],
          [[k, d['primary_recent_descriptive']['trades'], pct(d['primary_recent_descriptive']['mean_net'])]
           for k, d in diagnostics['results'].items()])
    lines += ['## 9. Capturas: sanity checks, nunca etiquetas de entrenamiento', '',
              'Interpretación Europe/Madrid (CEST=UTC+2). «Evening» no identifica una vela única: se muestra 20:00 como referencia '
              'descriptiva, sin reclamar que sea la captura exacta. Sin símbolo/venue/export del usuario no se atribuyen coincidencias al Pine real.', '']
    for observation in test['screenshots_diagnostic_only']:
        state = {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}[observation['state']]
        nearby = ', '.join(e['event'] + ' ' + datetime.fromtimestamp(e['timestamp'] / 1000, timezone.utc).strftime('%H:%M UTC')
                           for e in observation['nearby_events']) or 'ninguno ±1h'
        lines.append(f"- {observation['label']}: port causal {state}, RSI={observation['rsi']:.2f}; eventos cercanos: {nearby}.")
    lines += ['', '## Reproducción y seguridad', '',
              '```powershell', 'python -m research.mlrsi_pattern_data --cutoff 1791057600000 --refresh',
              'python -m research.mlrsi_pattern_backtest --phase development --cutoff 1791057600000',
              'python -m research.mlrsi_pattern_backtest --phase test --cutoff 1791057600000',
              'python -m research.mlrsi_pattern_report', 'python -m unittest research.test_mlrsi_pattern -v', '```', '',
              'Para un clon sin caches, reconstruir el dataset original con el downloader público ya existente '
              '`python -m research.early_breakout_data --as-of 2026-10-02T16:05:00+00:00`, sin arrancar Early Breakout. '
              'Luego el script de datos de este estudio verifica archives y añade su cola congelada. '
              'REST histórico puede cambiar: comparar el manifest; si difiere, no afirmar reproducción de los mismos bytes. '
              'Dependencias explícitas: numpy y requests. No hay APIs de cuenta, credenciales, funciones de órdenes, POST o observer desplegado. '
              'Manual Copilot, Guardian, forward audit, V8 y Early Breakout no se modificaron. '
              'El runner usa solamente el módulo matemático puro existente; no depende de mutaciones Guardian.', '',
              'Métricas completas y conteos de censura para todos los vecinos: [development_results.json](development_results.json), '
              '[test_results.json](test_results.json), [diagnostics.json](diagnostics.json). '
              'El bootstrap no crea probabilidades de éxito inventadas. **NO EDGE significa que no se cumple el estándar de promoción; '
              'no demuestra que toda posible versión del Pine original carezca de información.**']
    (root / 'RESULTS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Descriptive controls/report complete; frozen selection unchanged', flush=True)


if __name__ == '__main__':
    report()
