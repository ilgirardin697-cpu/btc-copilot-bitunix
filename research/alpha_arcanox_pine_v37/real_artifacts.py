"""Build source-backed tables and plots; no changes to signals or thresholds."""
import json
from datetime import datetime, timezone
from pathlib import Path
from .core import HOUR
from .evidence import analyze,bars_from_rows,load_evidence,utc
from .paper_review import review,json_default


def signal_figure(cycle,bars):
    s=cycle['signal'];levels=cycle['levels'];plan=s['plan_at_close']
    start=int(datetime.fromisoformat(cycle['asia_open_utc'].replace('Z','+00:00')).timestamp()*1000)
    expiry=int(datetime.fromisoformat(s['expiry_utc'].replace('Z','+00:00')).timestamp()*1000)
    selected=[b for b in bars if start-HOUR<=b.open_time<expiry]
    shown=[float(plan[k]) for k in ('theoretical_target','advanced_tp','stop','theoretical_entry')]
    high=max([b.high for b in selected]+shown);low=min([b.low for b in selected]+shown)
    span=high-low;high+=span*.06;low-=span*.06
    first=selected[0].open_time
    def x(t):return 65+(t-first)/HOUR*35
    def y(p):return 140+(high-p)/(high-low)*470
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="850">',
         '<rect width="1400" height="850" fill="#101a27"/><g font-family="Arial" font-size="14" fill="#e8f0f5">',
         '<text x="25" y="28">REAL TradingView BINANCE:BTCUSDT SPOT H1 — OWNER_B replay UTC−4 FIJO</text>',
         f'<text x="25" y="55">{cycle["asia_open_utc"][:10]} · {s["side"]} · cuerpo completo · RECHAZADA: R/R neto {plan["net_rr"]:.4f} &lt; 1.5</text>',
         '<text x="25" y="82">OHLC exportados; niveles OWNER_B calculados en Python. No señal original PINE_A, no operación ejecutada.</text>']
    for name,highkey,lowkey,color in (('asia','aHigh','aLow','#bfa055'),('london','lHigh','lLow','#af7cdc')):
        left,right=levels[name+'_left'],levels[name+'_right']
        out.append(f'<rect x="{x(left):.3f}" y="{y(levels[highkey]):.3f}" width="{x(right)-x(left):.3f}" height="{y(levels[lowkey])-y(levels[highkey]):.3f}" stroke="{color}" fill="{color}" fill-opacity=".12"/>')
        out.append(f'<text x="{x(left):.3f}" y="{y(levels[highkey])-8:.3f}" fill="{color}">{name.upper()}</text>')
    for b in selected:
        color='#40d398' if b.close>=b.open else '#ef6972'
        out.append(f'<line x1="{x(b.open_time):.3f}" x2="{x(b.open_time):.3f}" y1="{y(b.high):.3f}" y2="{y(b.low):.3f}" stroke="{color}"/>')
        out.append(f'<rect x="{x(b.open_time)-7:.3f}" y="{y(max(b.open,b.close)):.3f}" width="14" height="{max(1,abs(y(b.open)-y(b.close))):.3f}" fill="{color}"/>')
        if (b.open_time-first)//HOUR%3==0:
            hour=datetime.fromtimestamp(b.open_time/1000,timezone.utc).strftime('%d %H:%M')
            out.append(f'<text x="{x(b.open_time)-20:.3f}" y="645">{hour}Z</text>')
    for key,value,color in (('HIGH',levels['highGuideValue'],'#f1d45d'),('LOW',levels['lowGuideValue'],'#f1d45d'),
            ('TARGET ORIGINAL',float(plan['theoretical_target']),'#dba2f9'),
            ('TP ADELANTADO 200',float(plan['advanced_tp']),'#58cbe4'),('SL HIPOTETICO',float(plan['stop']),'#ff9870')):
        begin=x(levels['levels_available_at']) if key in ('HIGH','LOW','TARGET ORIGINAL') else x(int(datetime.fromisoformat(s['confirmed_at_utc'].replace('Z','+00:00')).timestamp()*1000))
        out.append(f'<line x1="{begin:.3f}" x2="1035" y1="{y(value):.3f}" y2="{y(value):.3f}" stroke="{color}" stroke-dasharray="6 4"/>')
        out.append(f'<text x="1050" y="{y(value)-4:.3f}" fill="{color}">{key}: {value:.4f}</text>')
    ct=int(datetime.fromisoformat(s['signal_bar_open_utc'].replace('Z','+00:00')).timestamp()*1000)
    out.append(f'<circle cx="{x(ct):.3f}" cy="{y(float(plan["theoretical_entry"])):.3f}" r="11" stroke="white" fill="none"/>')
    out.append(f'<text x="25" y="695">Vela marcada: abre {s["signal_bar_open_utc"]}; confirmación disponible SOLO al cierre {s["confirmed_at_utc"]}.</text>')
    path=s['reference_path']
    out.append(f'<text x="25" y="725">Orden posterior: SL en barra {path["sl_touch"]["bar_open_utc"]}; TP adelantado {path["advanced_tp_touch"]["bar_open_utc"]}.</text>')
    out.append(f'<text x="25" y="755">Target original: barra {path["theoretical_target_touch"]["bar_open_utc"]}. Visitar después el target NO es ganar la operación.</text>')
    out.append('<text x="25" y="790">Tiempos de hit = intervalos H1, no instante intrabar exacto. No se cuenta la vela confirmadora.</text>')
    out.append('<text x="25" y="825">MUESTRA POST-HOC · SIN HOLDOUT VIRGEN · SHADOW ONLY · TRADE AUTHORITY: NONE</text></g></svg>\n')
    return ''.join(out)


def write_artifacts(art):
    p=analyze();b=review();bars=bars_from_rows(load_evidence())
    def save(name,data):
        (art/name).write_text(json.dumps(data,default=json_default,ensure_ascii=False,
            sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    save('real_tradingview_parity_20261103.json',p)
    save('owner_b_64_review.json',b)
    text=['# Paridad REAL TradingView / Python — 2026-11-03','',
        'Fuente: exportación del propietario, BINANCE:BTCUSDT Spot H1. No es una fixture sintética.',
        'Se valida la reproducción contra el Pine exportado, no autenticidad de autoría del indicador privado.','',
        f'**{p["status"]}: 64 filas de entrada; 33 comparadas; 31 iniciales excluidas; 2 pares de sesiones completos; 0 discrepancias.**',
        f'Máximo error absoluto medido: {p["max_abs_error"]}; tolerancia: {p["absolute_tolerance"]}.',
        'Intervalo comparado por apertura de barra: 2026-11-02 11:00Z → 2026-11-03 19:00Z.',
        'No se inyectaron aHigh/aLow/asiaReady ni valores agregados para validar el primer ciclo.','',
        f'SHA256 logs: `{p["source_log_sha256"]}`.',
        f'SHA256 revisión externa: `{p["external_revision_sha256"]}`.',
        'El CSV anterior a esta conversión no se adjuntó: su hash solo está DECLARADO por la revisión externa.','',
        '## Diferencias por campo','',
        '| Campo | Comparaciones | Pares numéricos | Pares nulos | Error máximo | Discrepancias |',
        '|---|---:|---:|---:|---:|---:|']
    for key,s in p['by_field'].items():
        text.append(f'| {key} | {s["compared"]} | {s["numeric_pairs"]} | {s["null_pairs"]} | {s["max_abs_error"]} | {s["mismatches"]} |')
    text+=['','Los booleanos se comparan exactamente; los pares nulos no se cuentan como mediciones numéricas.','',
           '## Señales PINE_A','',
           '| Lado | Apertura UTC | Confirmación al cierre UTC | Replay comprobado | Cuerpo completo en niveles A |',
           '|---|---|---|---|---|']
    for s in p['logged_PINE_A_signals']:
        text.append(f'| {s["side"]} | {s["bar_open_utc"]} | {s["confirmed_at_utc"]} | {s["replay_validated"]} | {s["whole_body_on_PINE_A_levels"]} |')
    text+=['','Dos señales están comprobadas por replay; la del primer ciclo SOLO consta en el export.',
           'Las tres primeras señales close-only dejan parte del cuerpo dentro. Esto NO implica que OWNER_B no confirme después.','',
           '## El ejemplo de los cuatro niveles','',
           '| Fecha del par PINE_A | HIGH | LOW | SUPERIOR | INFERIOR | Replay OHLC completo |',
           '|---|---:|---:|---:|---:|---|']
    for m in p['measurement_records']:
        text.append(f'| {m["measure_bar_open"]} | {m["HIGH"]} | {m["LOW"]} | {m["SUPERIOR"]} | {m["INFERIOR"]} | {m["complete_ohlc_replay_validated"]} |')
    text+=['','El 1-Nov coincide NUMÉRICAMENTE con las cuatro etiquetas antiguas: SUPERIOR78653.4351 se muestra78653.44.',
           'Su álgebra desde los extremos guardados coincide, pero no se han reconstruido sus velas de Asia ausentes.',
           'Esto vincula los números a un ciclo de BINANCE:BTCUSDT/PINE_A; no autentica por sí solo el gráfico privado original.','',
           '## DST del 1 de noviembre','',
           '05:00Z = 01:00 EDT (UTC−4); 06:00Z = 01:00 EST (UTC−5). Ambas barras existen, separadas1H real.',
           'PINE_A: Londres02–05 EST son aperturas07–10Z; measureNow en11Z, primer cierre confirmable12Z.',
           'OWNER_B mantiene UTC−4: Londres01–04 son05–08Z; niveles en09Z y primera barra externa cierra10Z.',
           'La parte del fold y el primer ciclo solo se auditan desde el export; los dos pares posteriores son los replays completos.','',
           '## GO / NO-GO','',
           '**GO para evaluación PAPER exclusivamente offline con OWNER_B y sus propios niveles.**',
           'NO-GO para activación continua, integración productiva o trading real. Dos pares no prueban rentabilidad.',
           'SHADOW ONLY. TRADE AUTHORITY: NONE.']
    (art/'REAL_TRADINGVIEW_PARITY_20261103.md').write_text('\n'.join(text)+'\n',encoding='utf-8',newline='\n')
    doc=['# OWNER_B: revisión offline de los 64 registros reales','',
         '**POST-HOC. NO VIRGIN HOLDOUT. NO FORWARD OBSERVATIONS. NO PROFITABILITY CONCLUSION.**','',
         'Se conserva el primer ciclo parcial como EXCLUIDO; no se recupera Asia desde agregados PINE_A.',
         'Hay2 pares OWNER_B completos,2 primeras confirmaciones con cuerpo completo y0 entradas aceptadas.',
         'Se han usado sus horarios UTC−4, Asia20–00 (5), Londres01–04 (4), y fórmulas fuente3%.','',
         '## Escenario congelado antes de outcomes','',
         'Checkpoint Git4e070b4. TP±200, SL±0.20 ATR14, mínimo1.5R, riesgo máximo0.25%, nominal<=capital.',
         f'Hash del escenario: `{b["protocol_sha256"]}`.',
         'Capital10000 es escala de simulación, NO saldo del propietario. Comisión0.1% por lado como referencia',
         'Spot regular sin descuento; slippage2bps por lado como SUPUESTO, no observado.',
         '[Referencia de tarifas](https://www.binance.com/en/fee/trading). No son las comisiones del usuario ni de Bitunix.',
         'Funding0 pertenece a esta serie SPOT; no se importa a USD-M. SHORT es exposición direccional',
         'hipotética: no hay inventario/borrow verificados y no se afirma ejecución al contado sin ellos.',
         'ATR14 usa el seed SMA de los primeros14 TR de ESTE export y RMA posterior. No hay ATR de TradingView',
         'en el Pine diagnóstico; la equivalencia de su ATR no se ha demostrado. Para estudio largo debe congelarse',
         'un histórico previo amplio con manifiesto/seed, sin seleccionar el warmup por sus resultados.','',
         '## Primeras confirmaciones y filtro','',
         '| Lado | Vela abre UTC | Disponible al cerrar UTC | Cierre referencia | TP teórico | TP adelantado | SL | R/R neto cierre | Decisión |',
         '|---|---|---|---:|---:|---:|---:|---:|---|']
    for c in b['cycles'][1:]:
        s=c['signal'];r=s['plan_at_close']
        doc.append(f'| {s["side"]} | {s["signal_bar_open_utc"]} | {s["confirmed_at_utc"]} | {r["theoretical_entry"]} | {r["theoretical_target"]:.6f} | {r["advanced_tp"]:.6f} | {r["stop"]:.6f} | {r["net_rr"]:.6f} | RECHAZADA, &lt;1.5R |')
    doc+=['','Los ejemplos de12:00Z/13:00Z se refieren a APERTURAS. Solo son confirmaciones al cierre13:00Z/14:00Z.',
          'Aquí sí aparecen bajo OWNER_B, comprobado por separado; no se ha inferido a partir de PINE_A.','',
          '## Primera entrada posterior y secuencia de precio','',
          '| Lado | Siguiente apertura de referencia UTC | Precio sin slippage | R/R neto allí | Primer SL (barra UTC) | TP adelantado (barra UTC) | Target original (barra UTC) |',
          '|---|---|---:|---:|---|---|---|']
    for c in b['cycles'][1:]:
        s=c['signal'];path=s['reference_path']
        doc.append(f'| {s["side"]} | {s["next_open_reference_utc"]} | {s["next_open_reference_price"]} | {s["next_open_check"]["net_rr"]:.6f} | {path["sl_touch"]["bar_open_utc"]} | {path["advanced_tp_touch"]["bar_open_utc"]} | {path["theoretical_target_touch"]["bar_open_utc"]} |')
    doc+=['','Las aperturas posteriores existen en los datos, pero OHLC no acredita una cotización ejecutable',
          'tras latencia ni un fill real. Solo permite simular un escenario de apertura+slippage.',
          'Ambas señales YA se rechazaron al confirmar; la revisión de la apertura no las resucita.',
          '**En ambos recorridos se toca SL antes del TP adelantado y del target original.**',
          'Los hitos posteriores son contrafactuales de precio, no operaciones ganadoras.',
          'Se excluye totalmente la vela confirmadora. Los tiempos de hit tienen resolución de barra H1,',
          'conocidos al cierre posterior; no se inventa el minuto/segundo intrabar.',
          'Si una barra toca ambos extremos se aplica SL primero y se marca ambigüedad; los gaps al stop',
          'usan la apertura peor. El horizonte es el siguiente inicio de Asia, ya descrito en el protocolo previo.',
          'El 3-Nov termina la cobertura a20:00Z, antes de caducidad00:00Z; los hits listados sí constan,',
          'pero una ausencia posterior de evento quedaría censurada, no se contaría como fracaso.','',
          '## Evidencia e interpretación','',
          '2/2 recorridos alcanzan después el target en esta muestra seleccionada; también2/2 tocan primero',
          'el SL propuesto. Ningún porcentaje con n=2 demuestra la hipótesis de que "suele buscar" el target.',
          'Entradas aceptadas0, operaciones maduras0, PnL de operaciones0 porque NO HUBO OPERACIONES.',
          'Win rate, profit factor, drawdown de una estrategia invertida y esperanza: NO ESTIMABLES con0 entradas.',
          'No presentar el capital simulado sin cambios como evidencia de seguridad o edge.','',
          '## Siguiente evaluación, sin optimización','',
          'GO a preparar historia más amplia y observación prospectiva offline con protocolo/hash fijados,',
          'sin usar estos2 casos para variar horarios, TP200, buffer0.20, 1.5R o costes hasta que pase el filtro.',
          'Registrar TODOS los ciclos, sin señal, descartes, pérdidas, targets no alcanzados y censura.',
          'Mantener por separado entrada al cierre (referencia), primera entrada posterior, escenarios de coste,',
          'fills hipotéticos y targets observados. Para datos intrabar conservar procedencia y resolver cronología',
          'sin usar futuro. El diseño forward no importa estos ejemplos como señales prospectivas.',
          'No se crea ni activa observer; no Railway/Telegram/cuentas/órdenes. Guardian y V8 intactos.','',
          'SHADOW ONLY. TRADE AUTHORITY: NONE.']
    (art/'OWNER_B_64_REVIEW.md').write_text('\n'.join(doc)+'\n',encoding='utf-8',newline='\n')
    for c in b['cycles'][1:]:
        (art/('owner_b_'+c['asia_open_utc'][:10]+'.svg')).write_text(signal_figure(c,bars),encoding='utf-8',newline='\n')
    return p,b
