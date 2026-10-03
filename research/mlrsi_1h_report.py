"""Render already-frozen results. No parameter selection or trading capability."""
import json
from datetime import datetime, timezone
import numpy as np
from research import mlrsi_1h_core as s
from research.mlrsi_1h_run import code_hash


def pct(x):
    return '—' if x is None else f'{100 * x:+.3f}%'


def probability(x):
    return '—' if x is None else f'{100 * x:.1f}%'


def num(x):
    return '—' if x is None else f'{x:.3f}'


def interval(ci):
    return '—' if not ci else '[' + ', '.join(pct(x) for x in ci['mean_ci95']) + ']'


def table(lines, headers, rows):
    lines += ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    lines += ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows]
    lines.append('')


def load(name):
    return json.loads((s.ROOT / name).read_text('utf-8'))


def diagnostics(test, frozen):
    """Same pre-registered model across confirmations; NEVER reselect."""
    path = s.CACHE / 'spot_5m.npz'
    if s.digest(path) != frozen['dataset_sha256']:
        raise ValueError('DIAGNOSTIC_DATASET_MISMATCH')
    base = s.validate(np.load(path)['bars'], cutoff=test['cutoff'])
    feature = s.CACHE / f"features-{frozen['dataset_sha256'][:12]}-{frozen['code_sha256'][:12]}-test.npz"
    f = dict(np.load(feature))
    sets = {c: s.event_rows(f, c, frozen['volatility_cutpoints']) for c in (1, 2)}
    all_events = sets[1] + sets[2]
    costs = s.Costs(**test['base_costs'])
    stress = s.Costs(**test['stress_costs'])
    result = dict(study_code_sha256=code_hash(), reporter_sha256=s.digest(__file__),
                  selections_unchanged=True, diagnostic_only=True, results={})
    for c in (1, 2):
        controls = s.matched_controls(f, sets[c], all_events, frozen['volatility_cutpoints'])
        for name in s.EVENTS:
            e = [r for r in sets[c] if r['event'] == name and r['period'] == 'TEST']
            control = [r for r in controls if r['event'] == name and r['period'] == 'TEST']
            entry = {}
            for model in (s.Management('color', 0), s.Management('color', 1), s.Management()):
                rows = s.evaluate(base, f, e, model, costs, test['cutoff'])
                cr = s.evaluate(base, f, control, model, costs, test['cutoff'])
                entry[model.key()] = dict(metrics=s.summarize(rows), bootstrap=s.bootstrap(rows),
                    stress=s.summarize(s.evaluate(base, f, e, model, stress, test['cutoff'])),
                    paired_advantage=s.pair_advantage(e, control, rows, cr),
                    yearly={str(y): s.summarize([r for r in rows if r['year'] == y]) for y in (2024, 2025, 2026)})
            key = f'{name}:{c}'
            cache = dict(np.load(s.CACHE / f'outcomes-{name}-{c}.npz'))
            forward = [json.loads(r) for r in cache['forward']]
            entry['forward_excursion_means'] = {str(h): {
                'mean_mfe': float(np.mean([r['mfe'] for r in forward if r['horizon'] == h and r['status'] == 'COMPLETE'])),
                'mean_mae': float(np.mean([r['mae'] for r in forward if r['horizon'] == h and r['status'] == 'COMPLETE']))}
                for h in s.HORIZONS}
            result['results'][key] = entry
    s.save(s.ROOT / 'diagnostics.json', result)
    return result


def render():
    dev, test, frozen = [load(n) for n in ('development_results.json', 'test_results.json', 'frozen_selection.json')]
    manifest = load('data_manifest.json')
    for a in (dev, test, frozen):
        if a['code_sha256'] != code_hash() or a['spec_sha256'] != s.digest(s.ROOT / 'preregistered.json'):
            raise ValueError('FROZEN_ARTIFACT_MISMATCH')
        if a['dataset_sha256'] != manifest['dataset_sha256']:
            raise ValueError('DATASET_ARTIFACT_MISMATCH')
    extra = diagnostics(test, frozen)
    date = lambda x: datetime.fromtimestamp(x / 1000, timezone.utc).isoformat()
    lines = ['# ML RSI 1H LOW27 EMA4 — investigación independiente', '',
        f"**Clasificación: {test['classification']}.**", '',
        '**Exact BackQuant TradingView parity is NOT proven.** Se reutiliza sin cambios la función matemática '
        '`guardian_signals.rolling_mlrsi`: LOW/RSI27/EMA4, tres centroides inicializados p25/p50/p75, '
        'asignación por distancia absoluta, actualización por medias, últimos 3000 RSI finitos, máximo 1000 pasos. '
        'No se afirma reproducir la versión instalada en TradingView. Ver la auditoría de '
        '[PR #19](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/pull/19). '
        '**15M = NO EDGE for tested hypothesis** permanece intacto.', '',
        'El candidato más interesante es GREEN_RESUME de una barra con salida por color sin stop: '
        'TEST n=228, media neta +0.727%, PF1.534; tras eliminar las mejores3 queda +0.473%. '
        'Su ventaja frente al control es positiva, pero el IC95 semanal de su propia expectativa '
        '[-0.404%, +1.805%] incluye cero. El equity secuencial toma solo71 eventos no solapados: '
        '+7.183% total y MaxDD31.604% al cierre de trades. Los vecinos con stop cambian mucho el resultado. '
        'Por ello **no alcanza PROMISING** ni justifica una propuesta de observer todavía.', '',
        '## Datos, protocolo y seguridad', '',
        f"{manifest['rows']:,} velas BTCUSDT Binance **spot** públicas 5m desde {date(manifest['first_timestamp'])} "
        f"hasta {date(manifest['as_of'])}; {manifest['hourly_rows']:,} horas completas. "
        f"{manifest['gap_count']} huecos no interpolados. Se verificaron nuevamente todos los archivos de origen. "
        'Cada hora necesita doce barras contiguas y cerradas. Las horas/días/4H incompletos se descartan. '
        'Los indicadores avanzan sobre observaciones reales disponibles; no se sintetizan RSI ni precios de barras ausentes. '
        'Un hueco cancela un evento pendiente y censura cualquier horizonte/trade que lo atraviese.', '',
        'TRAIN 2020–2021; VALIDATION 2022–2023; TEST 2024–cutoff congelado. '
        'El proceso development recorta físicamente las barras a 2024-01-01; fija selección, quartiles TRAIN '
        'y hashes antes del proceso TEST. TEST rechaza código/protocolo/dataset/costes/cutoff distintos. '
        'No se eligieron filtros usando TEST. Artefactos: [preregistered.json](preregistered.json), '
        '[frozen_selection.json](frozen_selection.json), [data_manifest.json](data_manifest.json). '
        'El hash del dataset incluye el archivo entero para identificarlo; ninguna etiqueta/estadística TEST entra '
        'en la selección. Los datasets grandes permanecen en cache ignorada.', '',
        'Una primera ejecución no pudo serializar un booleano NumPy. Se cambió únicamente el tipo de salida '
        'a bool Python; se repitió desarrollo y se verificó igualdad exacta de selecciones y quartiles antes '
        'del TEST completado. [freeze_receipt.json](freeze_receipt.json) conserva ambas congelaciones. '
        'No cambió ninguna fórmula, modelo ni parámetro por este arreglo.', '',
        'CROSS: estado previo distinto del color actual. RESUME: reset de pendiente dentro del mismo color y '
        'posterior pendiente favorable; una señal, no una por barra. Las variantes de dos barras requieren '
        'dos pendientes favorables consecutivas y disparan al cierre posterior. Las salidas por color usan '
        'el primer cierre 1H con color opuesto, independientemente de la confirmación de entrada.', '',
        'Entrada: próxima apertura 1H más slippage adverso. Close-fill es sensibilidad separada al límite de '
        'vela, no una ejecución favorable dentro del pasado. Caminos simulados y horizontes usan 5m cerradas. '
        'Todos los modelos tienen límite predefinido 72h. Salida de color sin stop no tiene el mismo riesgo '
        'que la versión con stop. R en esa variante se normaliza por 1 ATR virtual, no por una pérdida máxima.', '',
        'Gestión: 16 modelos, vecinos de un factor; seis runners económicos ATR, un control BE ingenuo, '
        'cinco color exits con/sin stop, tres R:R y un runner con salida por color. '
        'Se elige por evento/confirmación maximizando el mínimo retorno medio neto TRAIN/VALIDATION, con '
        '100 trades completos en ambos. Solo color sin stop y color stop1 son elegibles de esa familia; '
        'otros stops y BE ingenuo son controles. Si falta muestra, se conserva el preset ATR1/trail1.5. '
        'Ningún modelo es una orden ni una estrategia aplicada a la cuenta.', '',
        'ATR14 Wilder 1H congelado en el cierre de señal. TP1 +1R cierra 30%. Runner 70%. '
        'Trailing sobre extremo favorable de 5m cerrado, nivel nuevo activo desde la siguiente barra; '
        'nunca se amplía un stop. Si una 5m toca SL y TP, SL primero; si TP1 y BE pueden colisionar, '
        'se sale conservadoramente por BE. Un gap de precio llena el stop a la apertura adversa. '
        'No se asume un fill rentable cuando el BE calculado ya estaría por encima del TP1 LONG/por debajo SHORT.', '',
        '**BE económico = PnL neto total de la operación igual a cero**, incluyendo TP1 ya cobrado, '
        'entrada/TP1/runner fees y slippage esperado de stop. Por acreditar el beneficio realizado de TP1 '
        'puede quedar debajo de entry LONG o encima SHORT. No es BE del runner aislado ni garantía de '
        'salir sin pérdidas durante gaps. Fórmula: con side s=±1, fee f, entry E, '
        'TP1 efectivo P, w=.3 y stop slip u: '
        '`BE_trigger = E * (((s+f)/(s-f) - w*P/E)/(1-w)) / (1-s*u)`. '
        'El stop nunca se amplía respecto al nivel inicial.', '',
        f"Costes base {test['base_costs']}; stress {test['stress_costs']}. "
        '5 bps taker es un supuesto configurable VIP1-like, no una certificación del tier del usuario. '
        'Fees parciales ponderadas por cantidad/notional. Gross elimina fricciones de ese mismo camino, '
        'no reoptimiza fills. **Funding, basis spot/perpetual y fills reales Bitunix excluidos**; '
        'no es rentabilidad ejecutable/realizada de futures ni retorno de la cuenta.', '',
        'Los eventos pueden solaparse. MaxDD/retorno de gestión son aparte una equity 1x secuencial sin '
        'posiciones simultáneas, medida al cierre de trades; no incluyen drawdown intratrade marcado a mercado. '
        'MFE/MAE de gestión son extremos conservadores de barras completas antes de la salida y sus fills, '
        'no extremos posteriores al cierre intrabar. Win/loss/BE neto usan tolerancia ±1bp.', '',
        '## 1. Señal antes de gestionar — TEST por horizonte', '',
        'Retorno direccional desde entry con slippage: LONG=future/entry−1, SHORT=1−future/entry. '
        'La columna net añade salida taker/slippage normal a ese horizonte. MFE/MAE desde entry; '
        'no son pagos obtenibles simultáneamente. First passage: porcentaje sobre horizontes completos; '
        'si ambos límites tocan la misma 5m se cuenta fracaso conservador y se informa ambigüedad. '
        'Neither es censura dentro del horizonte, no éxito. Horizonte con falta de datos/split censurado completo.', '']
    for key, r in test['results'].items():
        lines += [f'### {key}', '']
        rows = []
        for h, v in r['forward']['TEST']['UNFILTERED'].items():
            passage = lambda k: probability(v['passages'].get(k, {}).get('probability'))
            rows.append([h, v['complete'], v['incomplete'], pct(v.get('mean')), pct(v.get('median')),
                pct(v.get('mean_net')), pct(v.get('median_mfe')), pct(v.get('median_mae')),
                passage('+0.5/-0.5'), passage('+1/-1'), passage('+2/-1'), passage('+3/-1.5'), passage('+5/-2')])
        table(lines, ['h', 'n', 'incomp.', 'media', 'mediana', 'net', 'MFE med.', 'MAE med.',
                      '+.5/-.5', '+1/-1', '+2/-1', '+3/-1.5', '+5/-2'], rows)
        table(lines, ['h', 'control n', 'control media', 'ventaja pareada n', 'ventaja', 'IC95 semanal ventaja'],
            [[h, v['complete'], pct(v.get('mean')), r['forward_advantage'][h]['n'],
              pct(r['forward_advantage'][h]['mean_advantage']), interval(r['forward_advantage'][h]['bootstrap'])]
             for h, v in r['forward_controls']['UNFILTERED'].items()])
        if r['signals'] < 100:
            lines += ['⚠️ TEST tiene menos de 100 eventos de este tipo; muestra insuficiente para promover.', '']
    lines += ['## 2. Gestión seleccionada ANTES de TEST', '',
              'Estos son los modelos elegidos en desarrollo, no el mejor resultado descubierto en TEST.', '']
    rows = []
    for key, r in test['results'].items():
        model = r['selected']['key']
        t = r['models'][model]['TEST']['metrics']
        tr = dev['results'][key]['models'][model]['TRAIN']['metrics']
        va = dev['results'][key]['models'][model]['VALIDATION']['metrics']
        rows.append([key, model, f"{tr['trades']}/{va['trades']}/{t['trades']}", pct(tr['mean_net']),
            pct(va['mean_net']), pct(t['mean_gross']), pct(t['mean_net']), num(t['expectancy_r']),
            num(t['profit_factor']), probability(t['max_dd']), interval(r['bootstrap'])])
    table(lines, ['evento:confirm', 'modelo', 'n T/V/TEST', 'TRAIN net', 'VAL net', 'TEST gross', 'TEST net',
                  'R', 'PF', 'MaxDD sec.', 'IC95 media net'], rows)
    table(lines, ['confirm', 'lado', 'n', 'net medio', 'PF', 'MaxDD sec.', 'retorno sec.'],
          [[c, label, m['trades'], pct(m['mean_net']), num(m['profit_factor']), probability(m['max_dd']),
            pct(m.get('sequential_net_return'))] for c, group in test['combined'].items() for label, m in group.items()])
    lines += ['## 3. Alineación HTF, descriptiva: no filtro seleccionado', '',
        '4H y 1D usan SOLO cierres completos y SMA200. Igualdad no cuenta como alineación. '
        '1D tiene warmup insuficiente al inicio de TRAIN, marcado UNKNOWN. Quartiles de ATR/close '
        'se fijaron con TRAIN: ' + ', '.join(pct(x) for x in frozen['volatility_cutpoints']) + '.', '']
    table(lines, ['evento:confirm', 'cohorte', 'n gestión', 'gestión net', 'PF', 'n 24h', '24h media', '24h +1/-1'],
        [[key, cohort, m['trades'], pct(m['mean_net']), num(m['profit_factor']),
          r['forward']['TEST'][cohort]['24']['complete'], pct(r['forward']['TEST'][cohort]['24'].get('mean')),
          probability(r['forward']['TEST'][cohort]['24']['passages'].get('+1/-1', {}).get('probability'))]
         for key, r in test['results'].items() for cohort, m in r['alignment'].items()])
    lines += ['## 4. Robustez y efecto de costes/BE', '']
    table(lines, ['evento:confirm', 'n', 'stress net', 'close-fill net', 'sin mejores3 net', 'sin peores3 net',
                  'top3/beneficios', 'econ BE net', 'naive BE net', 'control net', 'ventaja pareada', 'IC95 ventaja'],
        [[key, (m := r['models'][r['selected']['key']]['TEST']['metrics'])['trades'], pct(r['stress']['mean_net']),
          pct(r['close_fill']['mean_net']), pct(m.get('without_best3_mean_net')), pct(m.get('without_worst3_mean_net')),
          probability(m.get('top3_share_positive')), pct(r['economic_vs_naive']['economic']['mean_net']),
          pct(r['economic_vs_naive']['naive']['mean_net']), pct(r['controls']['mean_net']),
          pct(r['paired_control_advantage']['mean_advantage']), interval(r['paired_control_advantage']['bootstrap'])]
         for key, r in test['results'].items()])
    lines += ['### Una vs dos barras, MISMA gestión (diagnóstico, no reselección)', '',
        'El preset de fallback GREEN de dos barras es ATR, por falta de n desarrollo. Compararlo '
        'directamente con la selección color de una barra confundiría gestión y confirmación. '
        'Esta tabla mantiene la misma gestión en ambos; GREEN_RESUME color de dos barras también '
        'es positivo, mientras sus runners ATR siguen negativos. Ver [diagnostics.json](diagnostics.json).', '']
    table(lines, ['evento:confirm', 'modelo fijo', 'n', 'net', 'PF', 'stress', 'IC95 net', 'ventaja control', 'IC95 ventaja'],
        [[key, model, v['metrics']['trades'], pct(v['metrics']['mean_net']), num(v['metrics']['profit_factor']),
          pct(v['stress']['mean_net']), interval(v['bootstrap']), pct(v['paired_advantage']['mean_advantage']),
          interval(v['paired_advantage']['bootstrap'])]
         for key, r in extra['results'].items() for model, v in r.items() if model != 'forward_excursion_means'])
    lines += ['### Todos los vecinos y baselines pre-registrados', '']
    table(lines, ['evento:confirm', 'modelo', 'n', 'net', 'PF', 'R'],
          [[key, model, (m := v['TEST']['metrics'])['trades'], pct(m['mean_net']), num(m['profit_factor']),
            num(m['expectancy_r'])] for key, r in test['results'].items() for model, v in r['models'].items()])
    lines += ['### Año, tendencia 4H y volatilidad (selección congelada)', '']
    table(lines, ['evento:confirm', 'desglose', 'n', 'net', 'PF'],
          [[key, f'{label}:{value}', m['trades'], pct(m['mean_net']), num(m['profit_factor'])]
           for key, r in test['results'].items() for label in ('yearly', 'regime4', 'volatility')
           for value, m in r[label].items()])
    lines += ['## 5. Controles y límites de inferencia', '',
        'Un timestamp no-evento por señal, seed773, muestreo con reemplazo. Coincidencia exacta '
        'año/mes, hora UTC, régimen4H y quartil TRAIN. Se excluye unión de eventos de una/dos barras. '
        'No se relajan strata ausentes. Se informa número emparejado y timestamps únicos en JSON. '
        'Cada control recibe la misma dirección/modelo/calendario de futuros cambios de color que el evento. '
        'Los controles de alineación 1D no están emparejados por 1D: son descriptivos. Bootstrap semanal '
        '1000 draws seed773, bloques que contienen señales; no hay ajuste por múltiples eventos/horizontes. '
        'Los resultados de controles tienen incertidumbre de una extracción fija; no son prueba definitiva de causalidad.', '',
        'Regímenes, años, CROSS/RESUME, lados y horizontes completos están separados en JSON. '
        'Reciente desde 2025-10-01 es descriptivo, nunca reemplaza TEST. No se usan screenshots como etiquetas. '
        'Comparación con 15m: aquel experimento usaba SL0.30%/$500 y cap48h; éste ATR/cap72h. '
        'Una diferencia de retornos no prueba que cambiar únicamente el timeframe sea la causa.', '',
        '## 6. Criterios y clasificación', '',
        'Los criterios se fijaron antes de TEST en protocolo; basta un fallo para impedir PROMISING. '
        'INTERESTING significa retorno seleccionado positivo sin evidencia suficiente, no permiso de operar.', '']
    table(lines, ['evento:confirm', 'clasificación', 'criterios que FALLAN'],
          [[key, r['classification'], ', '.join(k for k, v in r['promotion_gates'].items() if not v)]
           for key, r in test['results'].items()])
    lines += [f"**Conclusión única del estudio: {test['classification']}.**", '',
        'Sin órdenes, account APIs, secretos, leverage, deployment o habilitación. Manual Copilot, '
        'Guardian, Forward Audit, V8 y Early Breakout permanecen intactos. '
        'La incertidumbre de paridad sigue explícita; cualquier futuro shadow debe identificarse como port causal.', '',
        '## Reproducción', '', '```powershell',
        '# Dataset PR19 verificado + tail público fijado; no datos gigantes en Git',
        f"python -m research.mlrsi_1h_data --cutoff {test['cutoff']} --refresh",
        f"python -m research.mlrsi_1h_run --phase development --cutoff {test['cutoff']}",
        '# frozen_selection.json queda escrito ANTES de TEST',
        f"python -m research.mlrsi_1h_run --phase test --cutoff {test['cutoff']}",
        'python -m research.mlrsi_1h_report', 'python -m unittest research.test_mlrsi_1h -v',
        'python -m unittest discover -v', '```', '',
        'La preparación parte del dataset cache de PR19; en un checkout limpio reconstruir primero '
        'ese dataset siguiendo sus URLs/checksums. `input_manifest.json` conserva su provenance exacta. '
        'El manifest final identifica el tail fijado y su hash; se pueden reusar respuestas cacheadas '
        'para evitar depender de red. Ninguna CLI accede a cuentas.', '']
    (s.ROOT / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Report rendered; frozen models unchanged:', test['classification'], flush=True)


if __name__ == '__main__':
    render()
