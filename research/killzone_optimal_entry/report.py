"""Describe the frozen evaluation; no fitting, search or runtime integration."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from .data import HERE, HOUR, MINUTE, NY, iso, load_interval, window
from .evaluate import json_write
from .signals import METHODS


def number(v, digits=3):
    return '—' if v is None else f'{v:.{digits}f}'


def ci(values):
    return '[' + '; '.join(number(v) for v in values) + ']'


def plot_evidence(out, result, hours):
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.fonttype'] = 'none'
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from datetime import datetime, timezone

    trades = [t for t in result['trades'] if t['cost'] == 'PRIMARY']
    cycles = result['cycles']
    examples = []
    # First chronological net winner AND loser for each method/side, never best return.
    for method in METHODS:
        for side in (1, -1):
            for win in (True, False):
                selected = sorted((t for t in trades if t['method'] == method and t['side'] == side
                                   and (t['net_pnl'] > 0) == win), key=lambda t: t['entry_at'])
                if not selected:
                    continue
                t = selected[0]
                d = datetime.fromisoformat(t['cycle']).date()
                from .data import schedule
                s = schedule(d)
                h = window(hours, s['asia'], s['expiry'] + MINUTE)
                xs = (h[:, 0] - s['asia']) / HOUR
                fig, ax = plt.subplots(figsize=(12, 5))
                for x, b in zip(xs, h):
                    color = '#15803d' if b[4] >= b[1] else '#b91c1c'
                    ax.vlines(x, b[3], b[2], color=color, linewidth=1)
                    ax.add_patch(Rectangle((x-.28, min(b[1], b[4])), .56, max(abs(b[4]-b[1]), .05), facecolor=color))
                ledger = next(c for c in cycles if c['cost'] == 'PRIMARY' and c['method'] == method
                              and c['account_side'] == side and c['cycle'] == t['cycle'])
                a = window(hours, s['asia'], s['asia_end']); l = window(hours, s['london'], s['freeze'])
                for bars, color, label in ((a, '#f59e0b', 'Asia'), (l, '#6366f1', 'London')):
                    x0, x1 = (bars[0, 0]-s['asia'])/HOUR, (bars[-1, 0]+HOUR-s['asia'])/HOUR
                    ax.add_patch(Rectangle((x0-.4, bars[:, 3].min()), x1-x0, bars[:, 2].max()-bars[:, 3].min(),
                                           facecolor=color, alpha=.12, edgecolor=color, label=label))
                for key, color in (('HIGH', '#ca8a04'), ('LOW', '#ca8a04'), ('SUPERIOR', '#16a34a'), ('INFERIOR', '#dc2626')):
                    ax.hlines(ledger[key], (s['freeze']-s['asia'])/HOUR, xs[-1]+1, label=key, color=color, linestyle='--', linewidth=.8)
                for key, color, marker in (('entry', '#2563eb', '^'), ('stop', '#991b1b', 'x'), ('target', '#166534', '*')):
                    ax.scatter((t['entry_at']-s['asia'])/HOUR, t[key], color=color, marker=marker, label=key.upper(), s=70)
                ax.scatter((t['exit_at']-s['asia'])/HOUR, t['exit_price'], color='black', marker='o', label='EXIT', s=45)
                ax.axvline((t['signal_at']-s['asia'])/HOUR, color='#64748b', linestyle=':', label='SIGNAL AVAILABLE')
                side_name = 'LONG Spot cost scenario' if side == 1 else 'SHORT PRICE-ONLY, NOT FUTURES'
                ax.set_title(f"{t['cycle']} · {method} · {side_name}\nFirst {'net winner' if win else 'non-positive'} · net {t['net_pnl']:.2f} USDT · OFFLINE REPLAY")
                ax.set_xlabel('Hours since Asia open; exact UTC times are in example_manifest.json')
                ax.set_ylabel('BTCUSDT Spot price')
                ax.legend(fontsize=7, ncol=5, loc='best')
                ax.grid(alpha=.15)
                fig.tight_layout()
                name = f"example_{method}_{'LONG' if side == 1 else 'SHORT'}_{'winner' if win else 'loser'}.svg"
                fig.savefig(out / name)
                if not examples:
                    fig.savefig(out / 'first_example.png', dpi=140)
                plt.close(fig)
                examples.append(dict(file=name, selection='FIRST_CHRONOLOGICAL_NOT_BEST_RESULT',
                                     cycle=t['cycle'], method=method, side=side, signal_available_at=iso(t['signal_at']),
                                     entry_at=iso(t['entry_at']), exit_at=iso(t['exit_at']), net_pnl=t['net_pnl']))
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for ax, side in zip(axes, (1, -1)):
        for method in METHODS:
            rows = [c for c in cycles if c['cost'] == 'PRIMARY' and c['method'] == method and c['account_side'] == side]
            ax.plot([r['equity_after'] for r in rows], label=method, linewidth=1.2)
        ax.axhline(10000, color='black', linestyle=':', label='NO ENTRY')
        ax.set_title('LONG Spot cost assumptions' if side == 1 else 'SHORT hypothetical Spot price exposure — NOT executable futures')
        ax.set_ylabel('Simulated equity, USDT'); ax.legend(fontsize=8, ncol=3); ax.grid(alpha=.2)
    axes[-1].set_xlabel('Chronological calendar cycles; one initial capital allocation per account')
    fig.tight_layout(); fig.savefig(out / 'equity.svg'); fig.savefig(out / 'equity.png', dpi=140); plt.close(fig)
    json_write(out / 'example_manifest.json', examples)


def build(results_folder, cache, out):
    src, out = Path(results_folder), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ('data_quality.json', 'summary.json', 'cycles.csv', 'trades.csv', 'frozen_levels.csv', 'monthly.csv', 'results.json.gz'):
        if src.resolve() != out.resolve():
            shutil.copyfile(src / name, out / name)
    result = json.loads(gzip.decompress((out / 'results.json.gz').read_bytes()))
    s = result['summaries']; q = result['quality']
    primary = [r for r in s if r['cost'] == 'PRIMARY']
    limits = [t for t in result['trades'] if t['cost']=='PRIMARY' and t['is_limit']]
    off_tick = [dict(cycle=t['cycle'], side=t['side'], arithmetic_limit=t['entry']) for t in limits
                if abs(t['entry']*100-round(t['entry']*100)) > 1e-6]
    json_write(out / 'execution_limitations.json', dict(
        status='SCENARIO_FILLS_NOT_VERIFIED_EXCHANGE_EXECUTIONS',
        tick_reference='0.01_FROM_REUSED_REAL_PINE_RECORD_NOT_HISTORICAL_EXCHANGE_FILTER_AUDIT',
        primary_limit_fills=len(limits), arithmetic_limits_off_cent_tick=len(off_tick), cases=off_tick,
        no_posthoc_rounding_or_recalculation=True,
        quantity_step_and_min_notional='NOT_MODELED_WITH_HISTORIC_FILTERS',
        order_queue='NOT_VERIFIED_BY_OHLC', futures='BLOCKED_NO_EQUIVALENT_FUNDING_MARK_CONTRACT_DATA'))
    long_fail = sum(r['classification'] == 'NO EDGE' for r in primary if r['side'] == 1)
    promising = [r for r in primary if r['classification'] == 'PROMISING FOR FORWARD VALIDATION']
    lines = [
        '# I-GOD Killzone Optimal Entry Research V0', '',
        '**No hay método de entrada con ventaja neta demostrada en esta comparación.**',
        'Resultado de la familia: **INCONCLUSIVE**; dos brazos LONG son **NO EDGE**.',
        'No se recomienda activar señales, PAPER continuo ni integración operativa.', '',
        '## Qué se fijó antes de evaluar', '',
        'Protocolo commiteado en `cc74bb5`, antes de calcular los nuevos outcomes.',
        f"SHA256 del protocolo: `{q['protocol_sha256']}`.",
        'Se comparan cuatro candidatos y BASELINE, sin optimización o selección posterior.',
        'Nombre «Optimal» no significa que se haya encontrado un óptimo. PRICE no participa.',
        'Fechas, stop, 1,5R, latencia, costes y caducidad son convenciones de investigación predeclaradas.', '',
        '## Fuente y temporalidad', '',
        f"BTCUSDT **BINANCE SPOT**, {q['first_minute']} → {q['last_minute_available']} exclusivo.",
        f"{q['h1_rows']} H1 incluyendo octubre de 2025 para warmup; {q['m1_rows']} minutos; {q['h1_vs_m1_exact_checks']} agregaciones H1/60m exactas.",
        'Se releen 25 ZIP oficiales previamente auditados de PR #41 y se comprueban otra vez sus hashes locales contra los manifests preservados.',
        'No se descarga ningún dataset nuevo ni se reconsulta el checksum remoto actual. Sin gaps, duplicados, imputación o reparaciones.',
        f"{q['cycles_planned']} ciclos de calendario; {q['complete_cycles']} completos. El 08/03/2026 es incompleto: 02:00 NY no existe por DST.",
        'Timestamps del archive Spot en microsegundos → milisegundos enteros; no se redondea OHLC.',
        '[Fuente pública y convenciones de timestamps Binance](https://github.com/binance/binance-public-data).', '',
        '**NO VIRGIN HOLDOUT.** Esta historia ya se vio. Noviembre–febrero, marzo–junio y julio–octubre',
        'son particiones descriptivas cronológicas, no un nuevo test independiente. No hay reentrenamiento.',
        'Los 20 brazos método×lado×coste repiten los mismos ciclos; no son 7.300 observaciones independientes.', '',
        '## Geometría PINE_A y nuestras hipótesis separadas', '',
        'America/New_York con DST; Asia 20/21/22/23, Londres 02/03/04/05. Cuatro velas cerradas en cada sesión.',
        'Se reutiliza byte-a-byte `project`/ATR de PR #41. Tres registros reales Pine ya auditados se conservan como golden de fórmula;',
        'esto NO añade evidencia independiente nueva de TradingView ni valida entradas.',
        'HIGH=max(aHigh,lHigh); LOW=min(aLow,lLow); amplitud=HIGH−LOW.',
        'SUPERIOR=min(aHigh,lHigh)−0,03×altura_caja_superior+amplitud;',
        'INFERIOR=max(aLow,lLow)+0,03×altura_caja_inferior−amplitud.',
        'Se respetan empates, cajas solapadas y contenidas. No se usan diagonales ni extrapolaciones.',
        'Los niveles se calculan al disponer de las cuatro Londres a 06:00. Es un cálculo causal independiente;',
        'no se afirma identidad de la actualización visual `endLondon` del Pine, que puede esperar al cierre de la barra exterior.',
        'Paridad aquí significa fórmula auditada, no reproducción exacta del momento de dibujo de TradingView.', '',
        '| Método | Regla congelada |', '|---|---|',
        '| BASELINE | Dirección del cuerpo agregado Londres a 06:00; entrada siguiente minuto |',
        '| AFTER_LONDON | Cierre Londres fuera del rango Asia y cuerpo Londres alineado |',
        '| BREAKOUT | Primera H1 posterior con cuerpo completo estrictamente fuera de HIGH/LOW |',
        '| RETEST | Primera ruptura, después otra H1 toca su nivel y cierra del lado roto |',
        '| LIMIT_ZONE | Límite en midpoint Londres, conocido a 06:00, colocado 06:01 y sin repricing |',
        '| NO ENTRAR | Cero exposición y cero PnL |', '',
        'La confirmación por cuerpo completo y primera oportunidad por ciclo son nuestras convenciones, no las alertas originales close-only de PINE_A.',
        'TP = target teórico; **no** adelanto 200 OWNER_B ni franja visual 500.',
        'SL común = extremo opuesto Londres ±0,20 ATR14 congelado a 06:00. Nunca se amplía.',
        'Riesgo máximo estimado 0,25 %; R/R neto mínimo 1,5; nominal+fee dentro del equity; sin apalancamiento.',
        'Cada método/lado/coste mantiene su cuenta independiente desde 10.000, sin reinicios mensuales.', '',
        '## Resultados primarios, por lado', '',
        'Coste supuesto: 10 bps de comisión por lado; 2 bps adversos de mercado por lado.',
        'El límite se llena a su precio máximo/mínimo, sin slippage que viole ese límite. Son escenarios, no fees o fills de cuenta verificados.', '',
        '| Método | Lado | n | Neto USDT | Retorno % | Media R | IC95 R | PF | DD MTM % | Clasificación |',
        '|---|---|---:|---:|---:|---:|---|---:|---:|---|',
    ]
    for r in primary:
        lines.append(f"|{r['method']}|{'LONG' if r['side']==1 else 'SHORT*'}|{r['n']}|{r['net_pnl']:.2f}|{r['net_return_pct']:.2f}|{number(r['mean_net_r'])}|{ci(r['mean_net_r_ci95'])}|{number(r['profit_factor'])}|{r['mtm_drawdown']*100:.2f}|{r['classification']}|")
    lines += ['',
        '*SHORT representa exposición hipotética al precio Spot. No es una venta Spot ejecutable sin inventario/préstamo ni Binance/Bitunix Futures.',
        'No hay serie de funding/mark, borrow, spread/cola o reglas de contrato verificados; ese bloqueo impide declarar un SHORT prometedor ejecutable.',
        'Funding LONG Spot: no aplica. Funding de futuros: desconocido/no modelado, nunca asumido cero.', '',
        '## Activación, rechazos y TP frente a resultado neto', '',
        '| Método | Lado | Señales técnicas | Operaciones | Sin fill | Rechazadas | Neto positivo % | TP % | Ambiguas |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in primary:
        counts = r['ledger_status_counts']
        lines.append(f"|{r['method']}|{'LONG' if r['side']==1 else 'SHORT*'}|{r['signals']}|{r['n']}|{counts.get('UNFILLED',0)}|{counts.get('REJECTED',0)}|{number(None if r['net_win_rate'] is None else r['net_win_rate']*100,1)}|{number(None if r['tp_rate'] is None else r['tp_rate']*100,1)}|{r['ambiguous']}|")
    lines += ['',
        'Hay 267 primeras rupturas técnicas (135 UP,132 DOWN), pero solo una entrada pasa el stop/RR predeclarado.',
        'Hay 126 retests confirmados (63/63), pero ninguna entrada aceptada. No equivalen a inexistencia de rupturas o retests.',
        'Las causas exactas por método/lado están en summary.json: R/R insuficiente, target detrás, límite no pasivo o precio posterior ya inválido.',
        'RETEST no confirma en 141 de las secuencias con ruptura (72/69). No se cambió el nivel ni se buscó una segunda oportunidad.',
        'LIMIT_ZONE: 88 órdenes LONG que superan los filtros, 74 fills (84,09 %); 107 SHORT,86 fills (80,37 %).',
        'Las 35 órdenes sin activación caducan; no se imputan a ganadoras. Los fills no prueban ejecución en cola.',
        'Por tanto sí se puede calcular una zona antes de llegar, pero esta zona midpoint NO demuestra utilidad económica.', '',
        '## Ejecución y riesgo temporal', '',
        'Mercado: primer precio de apertura 1m un minuto después de conocer la señal, más slippage adverso; se revalida R/R sin mover SL/TP.',
        'Límite: orden fijada a 06:01, requiere penetración mínima de un tick (0,01), nunca solo toque; precio congelado.',
        'No se cuenta el TP de la vela confirmadora. En fill limitado con TP en el mismo minuto y orden desconocido no se acredita ese TP.',
        'SL/TP en la misma 1m: stop primero. Gap a través de límite/stop: no se omite la pérdida, se toma el precio adverso.',
        'Caducidad/salida temporal al open de 19:59 NY, antes de la siguiente Asia20:00. El high/low/close posterior de esa 1m no modifica el trade.',
        'MAE/MFE son cotas basadas en OHLC1m: el extremo puede anteceder al fill o suceder después de la salida intraminuto.',
        'Los límites de riesgo son estimaciones al stop, no garantía frente a gaps ni prioridad en el libro.', '',
        f"Auditoría de ejecutabilidad: {len(off_tick)}/{len(limits)} límites llenados tienen midpoint aritmético fuera del tick de referencia 0,01 de los logs Pine.",
        'No se redondean después de ver outcomes para rescatar la estrategia. Son fills de escenario, no órdenes probadas en exchange.',
        'Tampoco se cuantiza cantidad con filtros históricos de lot/minNotional ni se verifica cola. Esto limita cualquier afirmación de ejecutabilidad real, incluso LONG.',
        'El detalle está en execution_limitations.json. Una evaluación exacta de órdenes exigiría otro protocolo previo; no se modifica el actual retrospectivamente.', '',
        '## Incertidumbre, controles y estabilidad', '',
        'Bootstrap circular de 7 días, 2.000 réplicas, semilla fija. Días sin entrada mantienen cero.',
        'Se informa IC95 descriptivo e IC98,75 para cuatro comparaciones contra BASELINE, sin elegir al ganador.',
        'Métrica incremental: R sobre el presupuesto diario de equity emparejado por fecha/lado. Se separa de la media R condicional por trade.',
        'Menos pérdidas que un baseline perdedor NO prueba ventaja frente a NO ENTRAR.',
        'Con un único trade, el IC condicional puede colapsar: no es precisión estadística; el clasificador conserva INCONCLUSIVE por n insuficiente.', '',
        '| Método | Lado | Δ R/ciclo vs BASELINE | IC98,75 Δ | ex-best1 R | ex-best3 R | Neto stress USDT |',
        '|---|---|---:|---|---:|---:|---:|']
    for r in primary:
        stress = next(x for x in s if x['cost']=='STRESS' and x['method']==r['method'] and x['side']==r['side'])
        lines.append(f"|{r['method']}|{'LONG' if r['side']==1 else 'SHORT*'}|{r['paired_cycle_r_gain_vs_baseline']:.4f}|{ci(r['paired_cycle_r_gain_ci9875'])}|{number(r.get('ex_best1_mean_r'))}|{number(r.get('ex_best3_mean_r'))}|{stress['net_pnl']:.2f}|")
    lines += ['',
        'STRESS = 15 bps fee/lado y 5 bps slippage de mercado/lado; vuelve a aplicar exactamente el mismo filtro, por lo que puede cambiar n.',
        'No se elige el escenario más favorable. La expectativa primaria de los diez brazos es negativa o no estimable por ausencia de trades.',
        'Meses completos, distribución de R, MAE/MFE, duración y todas las particiones se conservan en monthly.csv y summary.json.', '',
        '## Particiones descriptivas', '',
        '| Método | Lado | Nov–Feb n / neto | Mar–Jun n / neto | Jul–Oct n / neto |', '|---|---|---|---|---|']
    for r in primary:
        cells = [f"{x['n']} / {x['net_pnl']:.2f}" for x in r['partitions'].values()]
        lines.append(f"|{r['method']}|{'LONG' if r['side']==1 else 'SHORT*'}|" + '|'.join(cells) + '|')
    lines += ['',
        '## Comparación con OWNER_B, sin reinterpretarlo', '',
        'PR #41 original: 365 ciclos,36 trades,−298,85 USDT; media −0,335R, IC95[−0,755;+0,114], INCONCLUSIVE.',
        'Su control close-only:63 trades,−817,69 USDT, NO EDGE. Se conservan sus resultados.',
        'OWNER_B usa UTC−4 fijo, Asia20–00/Londres01–04, TP±200 y stop junto a HIGH/LOW.',
        'Este estudio usa PINE_A con DST, Asia20–23/Londres02–05, TP teórico y stop opuesto de Londres.',
        'No son estrategias intercambiables ni un experimento que aísle un único cambio frente a OWNER_B.',
        'No se retocan sus reglas ni se presentan retornos cruzados como prueba de mejora causal.', '',
        '## Respuestas y decisión', '',
        '- ¿Hay entrada con ventaja demostrable? **No**. Ningún candidato supera el protocolo completo.',
        '- ¿Cuándo LONG/SHORT? Las condiciones técnicas están definidas, pero ninguna está validada como recomendación de entrada.',
        '- ¿NO ENTRAR? Es la decisión operativa prudente fuera de este laboratorio; las variantes no justifican activación.',
        '- ¿Zona calculable antes? **Sí, matemáticamente**: midpoint Londres y su zona están congelados a06:00. **No se ha probado ventaja**.',
        '- ¿Qué falta? Evidencia forward independiente, costes/fills/cola y una serie de futuros apropiada antes de interpretar SHORT ejecutables.',
        '- **NO-GO** para señales fiables o integración. Diseño de I-GOD Killzone Entry Radar solo como instrumentación research NO VALIDADA.', '',
        'No se construye ni activa un capturador forward, Pine operativo, Telegram, cliente exchange o nuevo servicio.',
        'Revisar primero estos resultados; cualquier futuro protocolo requiere aprobación separada y no puede importar esta historia como forward.', '',
        '## Evidencias consultables', '',
        '- cycles.csv: todos los ciclos, métodos, lados y costes, incluidos NO_SIGNAL, incompletos, rechazos y sin fill.',
        '- trades.csv y results.json.gz: cada fill simulado, TP/SL/tiempo, costes, cantidades y equity cronológico.',
        '- frozen_levels.csv: niveles y disponibilidad causal por ciclo; monthly.csv y summary.json: resultados completos.',
        '- equity.svg y example_manifest.json: primeros ganadores/perdedores cronológicos, no ejemplos escogidos por beneficio.',
        '- freeze_manifest.json y manifest de artifacts: procedencia y hashes; pruebas de aislamiento y causalidad.', '',
        '**SHADOW ONLY. TRADE AUTHORITY: NONE.**',
    ]
    (out / 'KILLZONE_OPTIMAL_ENTRY_RESEARCH.md').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
    plot_evidence(out, result, load_interval(cache, '1h'))
    # Matplotlib emits trailing spaces/CRLF in SVG paths on Windows. Normalize
    # presentation whitespace before hashing; never touch any market/result data.
    for chart in out.glob('*.svg'):
        text = chart.read_text(encoding='utf-8')
        chart.write_text('\n'.join(line.rstrip() for line in text.splitlines())+'\n', encoding='utf-8', newline='\n')
    manifest = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in sorted(out.iterdir()) if p.is_file() and p.name != 'artifact_manifest.json'}
    json_write(out / 'artifact_manifest.json', manifest)
    print(json.dumps(dict(report=str(out / 'KILLZONE_OPTIMAL_ENTRY_RESEARCH.md'), artifacts=len(manifest), promising=len(promising), long_no_edge=long_fail)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--results', required=True); p.add_argument('--cache', required=True)
    p.add_argument('--out', default=str(HERE / 'artifacts'))
    a = p.parse_args(); build(a.results, a.cache, a.out)


if __name__ == '__main__':
    main()
