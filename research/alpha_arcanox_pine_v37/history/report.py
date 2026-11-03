"""Build reviewable historical artifacts from the fixed offline evaluation."""
import csv
import gzip
import hashlib
import io
import json
import statistics
from pathlib import Path
from .data import HERE,CACHE,iso,load_interval,spec,HOUR
from .stress import result as stress_result
from ..paper_review import json_default

ART=HERE/'artifacts'


def stable_gzip(raw):
    out=io.BytesIO()
    with gzip.GzipFile(fileobj=out,filename='',mode='wb',mtime=0) as f:f.write(raw)
    return out.getvalue()


def save_json(name,value):
    (ART/name).write_text(json.dumps(value,default=json_default,ensure_ascii=False,
        indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def csv_text(rows):
    if not rows:return ''
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows);return out.getvalue()


def reporting_audit(current):
    first_path=CACHE/'evaluation_first_pre_dd_reporting_fix.json'
    first_raw=(first_path.read_bytes() if first_path.exists() else
               gzip.decompress((ART/'first_result_before_dd_reporting_fix.json.gz').read_bytes()))
    first=json.loads(first_raw)
    differences=[]
    def walk(a,b,path=''):
        if isinstance(a,dict) and isinstance(b,dict):
            for key in set(a)|set(b):
                if key=='price_control_comparison' and key not in a:continue
                if key=='protocol_sha256' and path in ('/data/h1_manifest','/data/m1_manifest'):
                    # Re-download uses the final analysis protocol hash; the original
                    # download used the earlier pre-outcome source-selection freeze.
                    continue
                walk(a.get(key),b.get(key),path+'/'+key)
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):differences.append(path)
            else:
                for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
        elif a!=b:differences.append(path)
    walk(first,current)
    if any(not p.endswith('/adverse_minute_drawdown_upper_bound_pct') for p in differences):
        raise ValueError('UNEXPECTED_RESULT_CHANGE_AFTER_REPORTING_FIX')
    (ART/'first_result_before_dd_reporting_fix.json.gz').write_bytes(stable_gzip(first_raw))
    return dict(first_result_sha256=hashlib.sha256(first_raw).hexdigest(),
        final_result_sha256=hashlib.sha256((CACHE/'evaluation.json').read_bytes()).hexdigest(),
        changed_existing_fields=sorted(differences),trade_ledgers_and_fills_identical=True,
        cash_and_minute_close_equity_curves_identical=True,classifications_identical=True,
        reason='REPORTING_ONLY_BOUND_MUST_INCLUDE_EXIT_FEES_AND_WORST_UNKNOWN_INTRAMINUTE_EXTREME_ORDER',
        new_descriptive_comparison='PAIRED_WEEKLY_BLOCK_CI_SAME_FROZEN_BOOTSTRAP_NOT_NEW_TRADING_RULE')


def ledgers(arm):
    cycles=[];trades=[]
    for c in arm['cycles']:
        f=c['levels'];p=c.get('price',{});r=c.get('close_plan',{});t=c.get('trade',{})
        row=dict(date=c['date'],variant=arm['variant'],status=c['status'],
            reasons='|'.join(c.get('reasons',[])),side=c.get('side',''),
            signal_bar_open=iso(c['signal_time']) if 'signal_time' in c else '',
            confirmation_available=iso(c['available_at']) if 'available_at' in c else '',
            expiry=iso(c['expiry']),aHigh=f['aHigh'],aLow=f['aLow'],lHigh=f['lHigh'],lLow=f['lLow'],
            HIGH=f['highGuideValue'],LOW=f['lowGuideValue'],SUPERIOR=f['newTopTarget'],INFERIOR=f['newBottomTarget'],
            theoretical_entry=c.get('signal_close',''),atr14=c.get('atr14',''),
            advanced_tp=p.get('advanced_tp',''),stop=p.get('stop',''),net_rr_at_close=r.get('net_rr',''),
            close_filter_passed=c.get('close_filter_passed',False),capital_before=c['capital_before'],
            target_ahead=p.get('target_ahead',''),price_event_order=p.get('order',p.get('coverage','')),
            theoretical_touch=iso(p['theoretical_touch']) if p.get('theoretical_touch') is not None else '',
            sl_touch=iso(p['sl_touch']) if p.get('sl_touch') is not None else '',
            advanced_touch=iso(p['advanced_touch']) if p.get('advanced_touch') is not None else '',
            entry_reference=c.get('next_open_check',{}).get('reference_entry',''),
            net_rr_at_next_open=c.get('next_open_check',{}).get('net_rr',''),
            quantity_btc=t.get('quantity_btc',''),outcome=t.get('outcome',''),
            net_pnl=t.get('net_pnl',''),net_R=t.get('net_R',''),fees=(float(t['entry_fee'])+float(t['exit_fee'])) if t else '',
            funding=t.get('funding',''),ambiguous=t.get('ambiguous_same_minute',''))
        cycles.append(row)
        if t:
            trades.append(dict(date=c['date'],variant=arm['variant'],side=c['side'],
                entry_time=iso(t['entry_time']),exit_minute=iso(t['exit_minute']),exit_known_at=iso(t['exit_known_at']),
                **{k:t[k] for k in ('entry_reference','entry_scenario','exit_scenario','quantity_btc','capital_before',
                    'capital_after','gross_before_costs','slippage_cost','entry_fee','exit_fee','funding','net_pnl',
                    'net_R','outcome','holding_minutes_upper','mae_price_bound','mfe_price_bound','ambiguous_same_minute',
                    'estimated_stop_risk','risk_budget','realized_loss_exceeds_budget')}))
    return cycles,trades


def equity_figure(arms):
    lines=[];series=[]
    for arm,color in zip(arms,('#54d6aa','#f5a56a')):
        points=[]
        for c in arm['cycles']:
            equity=float(c['trade']['capital_after']) if 'trade' in c else float(c['capital_before'])
            points.append(equity)
        series.append((arm['variant'],color,points))
    low=min(min(x[2]) for x in series)-50;high=max(max(x[2]) for x in series)+50
    for name,color,values in series:
        pts=' '.join(f'{70+i*1080/(len(values)-1):.2f},{100+(high-v)/(high-low)*420:.2f}' for i,v in enumerate(values))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="650"><rect width="1300" height="650" fill="#101b28"/>'
        '<g fill="white" font-family="Arial" font-size="16"><text x="30" y="35">KILLZONE — equity REALIZADA simulada, sin reinicios</text>'
        '<text x="30" y="65">2025-11-01 → 2026-10-31 · Binance Spot · 10000 escala inicial · no fills reales</text>'+
        ''.join(lines)+f'<text x="20" y="110">{high:.0f}</text><text x="20" y="520">{low:.0f}</text>'+
        ''.join(f'<text x="{70+i*1080/364:.2f}" y="540" font-size="10">{c["month"]}</text>'
                for i,c in enumerate(arms[0]['cycles']) if c['date'].endswith('-01'))+
        '<text x="70" y="555" fill="#54d6aa">OWNER_B: cuerpo completo</text><text x="580" y="555" fill="#f5a56a">Control cierre simple; mismas sesiones/niveles</text>'
        '<text x="30" y="605">SHADOW ONLY · SHORT hipotético, sin préstamo verificado · TRADE AUTHORITY: NONE</text></g></svg>\n')


def example_figure(c,hours):
    t=c['trade'];p=c['price'];bars=[b for b in hours if c['cycle_open']<=b.open_time<c['expiry']]
    levels=[p['theoretical_target'],p['advanced_tp'],p['stop'],float(t['entry_scenario'])]
    hi=max([b.high for b in bars]+levels);lo=min([b.low for b in bars]+levels);pad=(hi-lo)*.08;hi+=pad;lo-=pad
    x=lambda ms:70+(ms-c['cycle_open'])/HOUR*35
    y=lambda value:110+(hi-float(value))/(hi-lo)*380
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="650"><rect width="1300" height="650" fill="#101b28"/><g font-family="Arial" font-size="14" fill="white">',
        f'<text x="25" y="30">OWNER_B {c["date"]} {c["side"]} · {t["outcome"]} · PnL neto {float(t["net_pnl"]):.4f} USDT simulados</text>',
        '<text x="25" y="60">Ejemplo elegido: primero cronológicamente de su lado y signo de PnL. No seleccionado por estética.</text>']
    for b in bars:
        color='#40d39a' if b.close>=b.open else '#ef737e'
        out.append(f'<line x1="{x(b.open_time):.2f}" x2="{x(b.open_time):.2f}" y1="{y(b.high):.2f}" y2="{y(b.low):.2f}" stroke="{color}"/>')
        out.append(f'<rect x="{x(b.open_time)-7:.2f}" y="{y(max(b.open,b.close)):.2f}" width="14" height="{max(1,abs(y(b.open)-y(b.close))):.2f}" fill="{color}"/>')
    for name,value,color in (('HIGH',c['levels']['highGuideValue'],'#edcd64'),('LOW',c['levels']['lowGuideValue'],'#edcd64'),
            ('TARGET ORIGINAL',p['theoretical_target'],'#caa0f3'),('TP ADELANTADO',p['advanced_tp'],'#4fc8db'),('SL',p['stop'],'#ff9b70')):
        out.append(f'<line x1="{x(c["available_at"]):.2f}" x2="940" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke="{color}" stroke-dasharray="5 4"/>')
        out.append(f'<text x="955" y="{y(value)-4:.2f}" fill="{color}">{name}: {float(value):.4f}</text>')
    out.append(f'<circle cx="{x(c["signal_time"]):.2f}" cy="{y(c["signal_close"]):.2f}" r="11" stroke="white" fill="none"/>')
    out.extend([f'<text x="25" y="540">Confirmación disponible {iso(c["available_at"])}; entrada posterior {iso(t["entry_time"])}.</text>',
        f'<text x="25" y="570">Salida en intervalo 1m desde {iso(t["exit_minute"])}; comisión total {float(t["entry_fee"])+float(t["exit_fee"]):.4f}.</text>',
        '<text x="25" y="605">Velas H1 para contexto; cronología calculada con minutos. Fills hipotéticos. SHADOW ONLY / NONE.</text></g></svg>\n'])
    return ''.join(out)


def main():
    ART.mkdir(exist_ok=True)
    raw=(CACHE/'evaluation.json').read_bytes();r=json.loads(raw);s=r['protocol'];a,b=r['arms']
    save_json('reporting_fix_audit.json',reporting_audit(r))
    save_json('summary.json',dict(protocol_sha256=r['protocol_sha256'],data=r['data'],
        arms=[dict(variant=x['variant'],classification=x['classification'],summary=x['summary']) for x in r['arms']],
        price_control_comparison=r['price_control_comparison']))
    save_json('stress_40x_status.json',stress_result())
    (ART/'study_results.json.gz').write_bytes(stable_gzip(raw))
    monthly=[]
    for arm in r['arms']:
        cycles,trades=ledgers(arm);name=arm['variant']
        (ART/f'cycles_{name}.csv').write_text(csv_text(cycles),encoding='utf-8',newline='\n')
        (ART/f'trades_{name}.csv').write_text(csv_text(trades),encoding='utf-8',newline='\n')
        for month,values in arm['summary']['monthly'].items():
            v=values['strategy'];q=values['price']
            monthly.append(dict(month=month,variant=name,cycles=values['cycles'],no_signal=values['no_confirmation'],
                confirmations=q['confirmations'],target_eligible=q['target_eligible'],target_hits=q['target_hits'],
                entries=v['accepted_entries'],net_pnl=v['net_pnl'],ending_equity=v['ending_realized_equity'],
                monthly_net_return_pct=v['net_return_pct'],minute_close_mtm_dd_pct=v['minute_close_mtm_max_drawdown_pct']))
    (ART/'monthly.csv').write_text(csv_text(monthly),encoding='utf-8',newline='\n')
    hours,hm=load_interval('1h')
    hrows=[dict(open_time=b.open_time,open=b.open,high=b.high,low=b.low,close=b.close) for b in hours]
    (ART/'hourly_input.csv.gz').write_bytes(stable_gzip(csv_text(hrows).encode('utf-8')))
    (ART/'equity.svg').write_text(equity_figure(r['arms']),encoding='utf-8',newline='\n')
    selected=[]
    for side in ('LONG','SHORT'):
        for win in (True,False):
            c=next((c for c in a['cycles'] if 'trade' in c and c['side']==side and (float(c['trade']['net_pnl'])>0)==win),None)
            if c:
                filename=f'first_{side}_{"winner" if win else "loser"}.svg'
                (ART/filename).write_text(example_figure(c,hours),encoding='utf-8',newline='\n');selected.append(filename)
    write_reports(r,selected)
    save_json('artifact_manifest.json',dict(files={path.name:dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(ART.iterdir())
        if path.is_file() and path.name!='artifact_manifest.json'}))
    print(json.dumps(dict(status='ARTIFACTS_READY',primary=a['classification'],control=b['classification'],stress='BLOCKED_NOT_EVALUABLE')))


def write_reports(r,examples):
    a,b=r['arms'];q=a['summary']['price'];v=a['summary']['strategy'];c=b['summary']['strategy'];cmp=r['price_control_comparison']
    med=statistics.median(q['time_to_target_minutes_upper']) if q['time_to_target_minutes_upper'] else None
    before=q['orders'].get('TARGET_FIRST',0)+q['orders'].get('TARGET_ONLY',0)
    slfirst=q['orders'].get('SL_FIRST',0)+q['orders'].get('SL_ONLY_NO_TARGET',0)
    text=['# Killzone OWNER_B — evaluación histórica offline de 12 meses','',
        f'**Conclusión principal: {a["classification"]}. No hay ventaja neta demostrada.**',
        f'Control cierre simple: **{b["classification"]}**. OWNER_C 40x: **INCONCLUSIVE / BLOCKED_NOT_EVALUABLE**.','',
        '## Fechas, protocolo y datos','',
        'Periodo: 2025-11-01 00:00 UTC → 2026-11-01 00:00 UTC exclusivo (365 ciclos de Londres).',
        'Octubre de 2025 completo inicializa ATR14; sus outcomes no entran en la evaluación.',
        'Fechas, fuente, costes y reglas congelados en046491f ANTES de descargar y analizar.',
        'Precisión de caducidad en b725a2d, después de descargar pero ANTES de calcular outcomes:',
        'el siguiente inicio de Asia se refiere al ciclo vigente. Una confirmación justo en su caducidad',
        'se registra pero no tiene ventana para entrar. El helper antiguo de64 registros no se modifica;',
        'su igualdad de hora avanzaba al día posterior, sin afectar a aquellos dos casos previos.',
        'Los manifests de descarga conservan el hash del primer protocolo; el hash de análisis incluye la precisión.',
        f'Hash final del protocolo: `{r["protocol_sha256"]}`.',
        'Binance Spot BTCUSDT oficial, 13 ZIP H1 y12 ZIP1m con25 checksums SHA256 oficiales.',
        '9504 horas incluyendo warmup;525600 minutos;8760 horas evaluadas coinciden EXACTAMENTE',
        'con sus60 minutos. Sin huecos, duplicados, imputación o velas abiertas.',
        'Los timestamps Spot de estos archivos están en microsegundos, normalizados explícitamente a ms.',
        '[Fuente y formatos oficiales](https://github.com/binance/binance-public-data/blob/master/README.md).',
        'Raw ZIP local en research/cache; manifests/URLs/checksums en summary.json; OHLC H1 público comprimido incluido.',
        'NO VIRGIN HOLDOUT. La ventana ya comparte historia de mercado vista en otros estudios; los64 logs',
        'posteriores se usaron para matemática, no para validar rentabilidad. No se tocaron fórmulas ni indicadores.','',
        '## Reglas y escenarios que se mantienen','',
        'OWNER_B: UTC−4 fijo, Asia20–00 (5), Londres01–04 (4), cuerpo COMPLETO, primera confirmación.',
        'Proyecciones fuente con inset3%; TP LONG=SUPERIOR−200 / SHORT=INFERIOR+200.',
        'SL HIGH−0.20 ATR14 / LOW+0.20 ATR14; mínimo1.5R neto; máximo0.25% de riesgo estimado',
        'y nominal<=equity, sin apalancamiento. El presupuesto y el nominal se recalculan con el capital restante.',
        '10000 USDT es solo escala inicial. No se reinicia entre meses o pérdidas ni hay fondos externos.',
        'Comisión0.1% por lado y slippage2bps por lado: escenarios conservados del estudio previo,',
        'NO tarifas históricas verificadas de la cuenta ni fills observados. Funding no aplica a esta serie Spot.',
        'SHORT es una exposición direccional hipotética: no hay préstamo/inventario ni sus costes verificados.',
        'No representa Bitunix Futures, ni una venta Spot ejecutable sin inventario o préstamo.','',
        '## A. Hipótesis del precio — todas las primeras confirmaciones','',
        f'- Ciclos totales:365; sin confirmación:{a["summary"]["no_confirmation"]}; con confirmación:{q["confirmations"]}.',
        f'- Casos con target aún por delante y tiempo posterior:{q["target_eligible"]}.',
        f'- Alcanzan el target teórico:{q["target_hits"]}/{q["target_eligible"]} = {q["target_hit_rate"]*100:.2f}%.',
        f'- No llegan antes de caducar:{q["no_target_by_expiry"]}; mediana entre los que llegan:{med} minutos.',
        f'- Target antes de SL o sin tocar SL:{before}; SL antes del target o sin target posterior:{slfirst}.',
        f'- De ellos,{q["sl_before_later_target"]} llegan al target DESPUÉS de haber tocado SL.',
        f'- Ninguno de ambos hasta caducar:{q["orders"].get("NEITHER_BY_EXPIRY",0)}.',
        f'- Target ya detrás al confirmar:{q["target_not_ahead"]}; sin tiempo posterior:{q["orders"].get("NO_POST_CONFIRMATION_TIME",0)}.',
        'Las dos últimas categorías se solapan:2 señales están en ambas. Se conservan todas en el ledger;',
        'no se cuentan como predicciones exitosas targets ya alcanzados durante la vela confirmadora.',
        'Hitos registrados al minuto, con tiempo a target como límite superior de1m. Horizonte finito:',
        'siguiente inicio de Asia. No se busca indefinidamente hasta encontrar un target futuro.',
        'Estos conteos incluyen señales rechazadas por riesgo; no son un win rate de operaciones.','',
        '## B. Estrategia — solo entradas que pasan el filtro','',
        f'- Superan el cálculo al cierre:{v["accepted_at_close"]}; entradas vigentes aceptadas:{v["accepted_entries"]}.',
        'Dos que pasan el cálculo no tienen ventana posterior antes de caducar. No se fabrican fills.',
        f'- Resultado bruto antes de costes:{v["gross_before_costs"]:.4f} USDT; comisiones:{v["fees"]:.4f}; slippage:{v["slippage_cost"]:.4f}.',
        f'- Neto:{v["net_pnl"]:.4f} USDT ({v["net_return_pct"]:.4f}%); equity final:{v["ending_realized_equity"]:.4f}.',
        f'- Expectativa:{v["mean_net_R"]:.6f} R/trade; IC95 por bloques7d:{v["mean_net_R_block_ci95"]}.',
        f'- Win rate neto:{v["win_rate"]*100:.2f}%; profit factor monetario neto:{v["profit_factor"]:.6f}.',
        f'- Drawdown realizado:{v["realized_max_drawdown_pct"]:.4f}%; MTM a cierre1m:{v["minute_close_mtm_max_drawdown_pct"]:.4f}%.',
        f'- Cota adversa intraminuto:{v["adverse_minute_drawdown_upper_bound_pct"]:.4f}% (supone orden extremo favorable→adverso).',
        f'- Salidas:{v["outcomes"]}; ambigüedades dentro del mismo minuto:{v["ambiguous_same_minute"]}.',
        f'- Exposición temporal superior:{v["exposure_pct_upper"]:.4f}%; pérdidas sobre presupuesto por gaps:{v["losses_beyond_risk_budget"]}.',
        f'- Ex-best1:{v["ex_best_one_mean_R"]:.6f} R; meses positivos:{v["positive_months"]}/12; segundo semestre:{v["second_half_net_pnl"]:.4f} USDT.',
        'La clasificación estaba fijada antes de outcomes: con36 entradas y un IC que cruza cero corresponde',
        'INCONCLUSIVE, aunque el punto estimado sea negativo. No es PROMISING y no recomienda activación.',
        'Las entradas son escenarios de primera apertura posterior+slippage, no fills reales acreditados.',
        'Se revalida el R/R allí sin mover SL/TP. Una barra1m que toque ambos aplica SL primero y se marca.',
        'Los gaps al stop usan la apertura peor; un gap hacia TP no obtiene un precio mejor gratuitamente.',
        'La propia vela que confirma queda totalmente fuera del outcome. Comisión de salida se carga una sola vez.','',
        '## Mensual — OWNER_B (capital nunca reiniciado)','',
        '| Mes | Ciclos | Sin señal | Confirmaciones | Targets/eligibles | Entradas | Neto USDT | Equity final | DD MTM1m % |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for month,x in a['summary']['monthly'].items():
        z=x['strategy'];p=x['price']
        text.append(f'| {month} | {x["cycles"]} | {x["no_confirmation"]} | {p["confirmations"]} | {p["target_hits"]}/{p["target_eligible"]} | {z["accepted_entries"]} | {z["net_pnl"]:.4f} | {z["ending_realized_equity"]:.4f} | {z["minute_close_mtm_max_drawdown_pct"]:.4f} |')
    text+=['','## LONG / SHORT — simulación separada por lado','',
        '| Lado | n | Neto USDT | Media R | Win rate | PF neto |','|---|---:|---:|---:|---:|---:|']
    for side,x in v['by_side'].items():
        text.append(f'| {side} | {x["n"]} | {x["net_pnl"]:.4f} | {x["mean_net_R"]:.6f} | {x["win_rate"]*100:.2f}% | {x["profit_factor"]:.6f} |')
    text+=['','## Sensibilidad: cierre simple con las MISMAS sesiones y niveles OWNER_B','',
        'No es PINE_A. Se verifica igualdad exacta de fechas y niveles de los365 ciclos; solo cambia cuerpo→cierre.',
        '| Modelo | Confirmaciones | Targets/eligibles | Entradas | Neto USDT | Media R | IC95 R | PF | Clasificación |',
        '|---|---:|---:|---:|---:|---:|---|---:|---|']
    for arm in r['arms']:
        q0=arm['summary']['price'];v0=arm['summary']['strategy']
        text.append(f'| {arm["variant"]} | {q0["confirmations"]} | {q0["target_hits"]}/{q0["target_eligible"]} | {v0["accepted_entries"]} | {v0["net_pnl"]:.4f} | {v0["mean_net_R"]:.6f} | {v0["mean_net_R_block_ci95"]} | {v0["profit_factor"]:.6f} | {arm["classification"]} |')
    text += ['',f'Visita al target: cuerpo {cmp["body_target_rate"]*100:.2f}% vs cierre {cmp["close_only_target_rate"]*100:.2f}%.',
        f'Diferencia emparejada:{cmp["body_minus_close_percentage_points"]:.4f} puntos; IC95 bloques:{cmp["paired_block_ci95_percentage_points"]}.',
        'Esperar cuerpo completo cambia también la hora y precio de la primera entrada, y a veces su lado.',
        'No interpretar36 vs63 como simplemente eliminar27 operaciones idénticas. No se escoge ganador',
        'ni se cambia la estrategia porque el control salga peor. Mensual de ambos:monthly.csv.','',
        '## Control de calidad y limitaciones','',
        'Primer resultado conservado con hash en reporting_fix_audit.json. Se corrigió exclusivamente la',
        'cota de drawdown para incluir comisión de salida y extremos intraminuto con orden desconocido.',
        'El auditor comprueba que ledgers, fills, PnL, curvas MTM observadas, CI y clasificaciones son idénticos.',
        'El IC95 es incertidumbre histórica condicionada a este año y costes, no garantía de distribución futura.',
        'Los fees son escenario, el slippage no está observado, faltan spread/latencia y costes de borrow SHORT.',
        'El drawdown bajo depende en parte de poca exposición y tamaño limitado, no demuestra edge.',
        'No hay live paper, orders, Telegram o Railway. Guardian, V8, ML RSI y protocolos intactos.','',
        '## Datos y gráficos para revisar','',
        '[Equity](equity.svg) · [Monthly CSV](monthly.csv) · [Resumen y manifests](summary.json)',
        '[Todos los ciclos B](cycles_OWNER_B.csv) · [Todos los trades B](trades_OWNER_B.csv)',
        '[Stress40x y bloqueo](STRESS_40X_NO_SL.md) · [Resultados completos comprimidos](study_results.json.gz)','']
    text += [f'- [Ejemplo objetivo: {name}]({name})' for name in examples]
    text+=['','SHADOW ONLY. TRADE AUTHORITY: NONE.']
    (ART/'KILLZONE_OWNER_B_HISTORY_12M.md').write_text('\n'.join(text)+'\n',encoding='utf-8',newline='\n')
    stress_doc='''# OWNER_C_STRESS_40X_NO_SL — evaluación bloqueada

**INCONCLUSIVE / BLOCKED_NOT_EVALUABLE. No se han fabricado liquidaciones, PnL,
drawdown o probabilidades de ruina. Campos numéricos históricos: null, no0.**

## Escenario solicitado, separado de OWNER_B

Se conservan sesiones, fórmulas, cuerpo completo, primer evento y TP±200. No SL
voluntario y NO filtro1.5R. Capital inicial10000 solo escala; cada operación
utilizaría margen inicial del50% del equity restante, 40x, aislado sin auto-add.
Cross sería una corrida independiente, con toda la cuenta respaldando una única
posición. No se abren otras mientras una siga activa; los ciclos se registran
como POSITION_ACTIVE. Sin aportaciones externas ni reset después de pérdidas.

Un stop voluntario ausente no impide liquidación. El fin de datos censuraría
una posición abierta con su pasivo/MTM, no la declararía ganadora o inmortal.
El escenario no se ha ejecutado porque falla el gate de procedencia/riesgo.

## Exchange elegido y motivo exacto del bloqueo

Candidato: Binance USD-M BTCUSDT, distinto de la serie Binance Spot usada para
señales. La liquidación depende del MARK y del margen de mantenimiento vigente,
no del último precio Spot. Los precios Spot no se usan como proxy del mark.

No se dispone de una tabla oficial VERIFICADA con vigencias completas de tiers,
maintenance amounts, límites de40x y reglas/comisiones de liquidación para
2025-11→2026-10. La API oficial de leverage brackets es USER_DATA firmada y
devuelve brackets del usuario actuales, no una historia completa con vigencias.
No se solicitaron credenciales ni se llamó a cuentas privadas. Una tabla actual
o el anuncio de2021 no demuestra que los tiers fueran esos durante todo el año.

Existen fuentes públicas oficiales de mark/trades/funding, pero no se descargan
para producir resultados falsamente exactos mientras el requisito anterior falla.
Además harían falta: sincronización intrabar trade/mark, funding real y su mark,
fee/clearance rules, lot/min-notional, modo de cuenta y resolución TP/liquidación.
Si ambos eventos estuvieran en el mismo intervalo sin secuencia fiable, el caso
seguiría ambiguo. No asumir liquidation=1/40 ni que28 SL de B equivalen a28
liquidaciones C. Tampoco106 visitas Spot al target equivalen a106 TP apalancados.

Fuentes oficiales:

- [Brackets (USER_DATA)](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account).
- [Liquidación y mark](https://www.binance.com/en-KZ/support/faq/detail/360033525271).
- [Ejemplo oficial de cambio de tiers,2021](https://www.binance.com/en/support/announcement/detail/f55d25695ca8453ab4c132c1fd4dc36a).

## Lo que sí puede calcularse sin inventar un modelo de exchange

40×50% del equity = nominal20 veces el equity. Con equity10000, margen5000
y nominal200000, un movimiento adverso del1% implica−2000 de PnL bruto,
un20% de la cuenta, antes de costes. Una comisión r cuesta20r del equity por lado.

Ignorando mantenimiento, fees y funding, agotar el margen aislado corresponde
a un movimiento adverso bruto del2.5%; agotar toda la cuenta con esa misma
posición cross,5%. **Son distancias algebraicas de insolvencia bruta, NO precios
de liquidación.** Mantenimiento y costes cambian el umbral y pueden activarlo antes.

Si hipotéticamente cada pérdida consumiera exactamente50% del equity total:

| Pérdidas hipotéticas50% | Equity restante de10000 |
|---:|---:|
|0|10000|
|1|5000|
|2|2500|
|3|1250|
|5|312.50|
|10|9.765625|

Esta tabla recalcula desde capital restante y no es una simulación histórica de
liquidaciones, no incluye fees y NO asigna probabilidad. La probabilidad de ruina
no puede inferirse ni de esta identidad ni de un único camino histórico sin
definir modelo y costes. El cierre práctico por mínimos de negociación también
requeriría las reglas verificadas del contrato.

## Comparación solicitada

| Métrica | OWNER_B Spot, escenario sin apalancamiento | C aislado40x | C cross40x |
|---|---|---|---|
|TP / liquidaciones|B_TP; liquidación no aplica al modelo B sin apalancamiento|NO EVALUABLE|NO EVALUABLE|
|PnL neto / drawdown MTM1m|B_PNL / B_DD|NO EVALUABLE|NO EVALUABLE|
|Riesgo de ruina|No inferir garantía de la muestra B|NO EVALUABLE|NO EVALUABLE|

El modelo C queda bloqueado, separado y sin botón, runner o integración. No se
ha suavizado el gate ni sustituido mark por Spot para conseguir una tabla numérica.

SHADOW ONLY. TRADE AUTHORITY: NONE.
'''
    stress_doc=stress_doc.replace('B_TP',str(v['outcomes'].get('TP',0))+' TP PAPER de '+str(v['accepted_entries'])+' operaciones')
    stress_doc=stress_doc.replace('B_PNL',f'{v["net_pnl"]:.4f} USDT').replace('B_DD',f'{v["minute_close_mtm_max_drawdown_pct"]:.4f}%')
    (ART/'STRESS_40X_NO_SL.md').write_text(stress_doc,encoding='utf-8',newline='\n')


if __name__=='__main__':main()
