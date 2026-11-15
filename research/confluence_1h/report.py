"""Render the actual artifacts, never invented trades or validation claims."""
import csv
import hashlib
import json
from pathlib import Path
from .data import HERE
from .evaluate import json_write


def render(out=None):
    out=Path(out or HERE/'artifacts');r=json.loads((out/'results.json').read_text());m=json.loads((out/'data_manifest.json').read_text())
    funnel=list(csv.DictReader((out/'signal_funnel.csv').open()));sens=list(csv.DictReader((out/'sensitivity.csv').open()))
    incident=list(csv.DictReader((out/'incident_20261115.csv').open()))
    audit=json.loads((out/'indicator_audit.json').read_text());diff=audit['supplied_zip_comparison']
    lines=['# I-GOD — Confluencia 1H: auditoría y evaluación offline',
        '', '**INCONCLUSO — NO-GO para integración o trading.**',
        '', f'Con las reglas base se detectan **{r["long_signals"]} LONG y {r["short_signals"]} SHORT** en {r["evaluation_bars"]:,} horas evaluadas. '
        'No existe una muestra de operaciones con la que estimar rentabilidad. No se relajan los filtros para obtenerla.',
        '', 'SHADOW ONLY. TRADE AUTHORITY: NONE.',
        '', '## 1. Fuentes y alcance',
        '', '- ZIP y dos fuentes adjuntas conservados byte a byte en `reference_sources/`; hashes en `source_manifest.json`.',
        '- Rama independiente desde `9d40020d539033cefb8f01734db8c6a6fdbba2e3`. Los 151 archivos base protegidos conservan sus hashes. No se cambia producción.',
        '- Fórmulas del proxy público, no indicadores propietarios de Bitman. **EXACT BITMAN PARITY: NOT PROVEN**.',
        '- La serie usada para el cruce es `tendencia` contra `ma_trend` (EMA15), no `pececillos` ni `tiburones`.',
        '', '## 2. Congelamiento antes de resultados',
        '', f'- Protocolo original: commit `{r["freeze_commit"]}`, SHA256 `{r["protocol_sha256"]}`.',
        '- Addenda de datos previos a toda evaluación: `fe29923` (dos huecos de mark), `a077a0b` (mark de settlement exacto), `85ec9ba` (incertidumbre explícita por marks ausentes). No cambian señales ni umbrales.',
        '- Implementación del estudio fijada en `e5fb1d6` antes del primer resultado. Las adaptaciones posteriores son reporting, diagnóstico, formatos REST y tests; ninguna selección de parámetros.',
        '- Dos TP coprimarios 2R/3R; sensibilidad de un factor ADX35/45 o BBWP80/90. No búsqueda ni selección del mejor resultado.',
        '- **NO VIRGIN HOLDOUT**: una separación cronológica no convierte mercado previamente examinado en datos vírgenes. Cero evidencia prospectiva de esta estrategia.',
        '', '## 3. Dataset verificable',
        '', '| Campo | Resultado |','|---|---|',
        f'| Mercado principal | {m["venue"]}, BTCUSDT |',
        '| Evaluación | 01/11/2022 00:00 UTC → 01/11/2026 exclusivo, cuatro años |',
        f'| Velas H1 | {m["bars"]:,} totales; {r["warmup_bars"]:,} warmup; {r["evaluation_bars"]:,} evaluadas |',
        f'| Archives ZIP/checksums oficiales | {sum(x["family"]!="fundingRateREST" for x in m["archives"])} verificados, incluidos dos diarios de recuperación |',
        f'| Funding | {m["funding_settlements"]:,} rates, contrastados contra REST público |',
        f'| Mark exacto ausente | {m["exact_funding_marks_missing"]:,} settlements; nunca se sustituyen silenciosamente |',
        '| Huecos finales de trade-price / imputación | 0 / 0 |',
        '', 'Los 48 huecos de mark price de los mensuales (24/02/2023 y 29/06/2026) se recuperaron de archivos diarios oficiales de la misma venue, con checksums. No se interpolaron.',
        'Los rates son reales; un mark de settlement vacío continúa siendo desconocido. El escenario acotado usa high/low del mark H1, se identifica en cada trade y no se presenta como un precio exacto.',
        'Al no haber trades base, esta limitación no crea pérdidas/beneficios ficticios: los métricos de rendimiento siguen N/D.',
        '', '[Provenance y checksums Binance](https://github.com/binance/binance-public-data) · [REST funding](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).',
        '', '## 4. Auditoría matemática y ejecución',
        '', 'La auditoría completa está en [AUDIT.md](../AUDIT.md).',
        '', '- Koncorde: RSI14 sobre OHLC4, MFI14 sobre HLC3, oscilador BB25×2, estocástico21/SMA3, EMA15. PVI/NVI y capas se calculan, pero no son filtros añadidos.',
        '- AO = SMA5(HL2) − SMA34(HL2). Color/pendiente no equivale a signo respecto a cero.',
        '- ADX/DMI14/14: se separa la semilla de true range de DMI de ATR14. La normalización inicial de DI cambia respecto al ZIP; no se modifica la lógica de dirección.',
        '- BBWP SMA7 / previas100: `binary_search_rightmost` devuelve un índice, no siempre count(<=). Se conserva el comportamiento literal en empates. El ZIP no es idéntico a esa fuente.',
        f'- Diferencias de señales ZIP versus port auditado en todo el input: LONG={diff["long_flags_changed"]}, SHORT={diff["short_flags_changed"]}. No se ha ejecutado su selector de 18 configuraciones.',
        '- Referencia escalar local independiente: pasa los campos verificables con tolerancia 1e-8/1e-9. **No es una ejecución de Pine**.',
        '- Pine diagnóstico completo y comparador entregados. Registros reales de este nuevo Pine: **0**. Compilación y paridad TradingView: **NO VERIFICADAS**.',
        '- El Pine v5 original usa 3000 ticks fijos de slippage, tamaño al cierre previo y salida `immediately` al cierre. Python usa porcentaje por fill y una salida temporal simulable a la siguiente apertura. No se declara equivalencia entre brokers.',
        '', '## 5. Qué condición descarta las coincidencias',
        '', '| Condiciones acumuladas | LONG | SHORT |','|---|---:|---:|']
    for gate in ('KON_CROSS_AND_PREVIOUS_SIGN','PLUS_LAGGED_ADX_DECLINE','PLUS_AO_TWO_SLOPES','PLUS_BBWP_ABOVE85'):
        values={x['side']:x['n'] for x in funnel if x['year']=='ALL' and x['gate']==gate}
        lines.append(f'| {gate} | {values["LONG"]} | {values["SHORT"]} |')
    lines += ['', 'El filtro ADX es literalmente `ADX[t−1] < ADX[t−2]` y `ADX[t−2] >40`. No exige un suelo actual, un giro al alza, ni siquiera que el valor de t−2 sea un máximo local frente a t−3. Tampoco exige dominancia +DI/−DI.',
        'Esta implementación ensaya la coincidencia concreta del ZIP, no cualquier parecido visual entre líneas. No se declara que sea la única formalización posible del concepto de confluencia.',
        '', '## 6. Simulación y costes fijados',
        '', '- Entrada en apertura posterior al cierre confirmado, con 0,05% adverso. SL=1,5ATR14 conocido al emitir; TP=2R/3R bruto. Salida tras 24 barras completas a apertura posterior.',
        '- Una posición simultánea por cuenta. COMBINED es principal; LONG_ONLY/SHORT_ONLY son cuentas contrafactuales separadas, nunca asignaciones simultáneas de una cuenta real.',
        '- Comisión 0,1% por lado, slip0,05% por lado, funding separado. Son escenarios de costes pedidos por el usuario; no tarifas/fills autenticados.',
        '- Equity inicial200 USDT; presupuesto al stop incluyendo fees/slip1%; nominal+fee<=equity. Sin multiplicador de apalancamiento. Gaps/funding futuro pueden superar el presupuesto; se registran breaches.',
        '- Stop primero si ambos niveles se tocan dentro de una H1 sin orden intrabar conocido. Una apertura ya fuera de un nivel se procesa antes que las mechas posteriores.',
        '- MFE/MAE de wicks son cotas H1; no se inventa el orden del precio después de la salida. DD a cierre y cota adversa separados.',
        '', '## 7. IS/OOS y walk-forward',
        '', f'Corte70/30 bruto: **{r["split_at_utc"]}**. IS termina24h antes y TEST empieza24h después. Purga adicional de señales sin horizonte completo de hasta24h y apertura de salida dentro de la ventana.',
        'Cuatro ventanas expansivas30→40,40→50,50→60,60→70% dentro del desarrollo. Parámetros fijos: no entrenamiento/selección de un ganador en cada fold.',
        '', '| TP | Libro | IS operaciones | TEST operaciones | Win rate / PF / expectancy / Sharpe |','|---|---|---:|---:|---|']
    for target in (2.,3.):
        for book in ('COMBINED','LONG_ONLY','SHORT_ONLY'):
            isr=next(x for x in r['metrics'] if x['window']=='DEVELOPMENT' and x['book']==book and x['target_r']==target)
            test=next(x for x in r['metrics'] if x['window']=='TEST' and x['book']==book and x['target_r']==target)
            lines.append(f'| {target:g}R | {book} | {isr["n"]} | {test["n"]} | N/D: sin muestra |')
    lines += ['', 'Los cuatro folds, los años y los regímenes tienen cero trades base. `year_side_regime.csv` y `metrics.csv` los conservan. La curva200→200, retorno0% y DD0% son consecuencia mecánica de no operar: **no miden seguridad ni capacidad predictiva**.',
        'Controles: el runner de 200 semillas por libro/TP empareja mes, lado y régimen causal4H SMA200. Con cero candidatos son controles vacíos; no existe una comparación estadística ni p-value útil.',
        'Bootstrap predeclarado por bloques calendario7d (2000 réplicas), incluyendo días sin eventos. Con cero operaciones el IC es `null`, no [0,0]. No se fabrica una distribución de resultados ni ex-best1/3.',
        '', '## 8. Sensibilidad sin seleccionar ganador',
        '', '| Vecino predeclarado | TP | Libro combinado TEST n | Neto escenario | Expectancy |','|---|---|---:|---:|---:|']
    for x in sens:
        if x['book']=='COMBINED' and x['window']=='TEST' and x['variant'] in ('BASE','ADX35','ADX45','BBWP80','BBWP90'):
            exp='N/D' if not x['expectancy_r'] else f'{float(x["expectancy_r"]):.3f}R'
            lines.append(f'| {x["variant"]} | {float(x["target_r"]):g}R | {x["n"]} | {float(x["net_usdt"]):.2f} USDT | {exp} |')
    lines += ['', 'El único evento de los vecinos BBWP80 es SHORT perdedor: −1R en ambos TP. No cambia la regla principal85 ni demuestra nada con n=1. No se adopta ningún vecino. Stress de costes15bps fee/10bps slip: igualmente sin operaciones base.',
        '', '## 9. Giro 15/11/2026: separado y causal',
        '', '**POST-HOC OBSERVATION — NOT PART OF VALIDATION.** 02:00 Europe/Madrid =01:00 UTC. Se distinguen apertura de vela y disponibilidad al cierre; los gráficos del incidente usan x=available_at.',
        '', '| Venue | Disponible Madrid | AO | ΔAO | ADX | ΔADX | BBWP | Cruce Kon LONG | Señal completa |','|---|---|---:|---:|---:|---:|---:|---|---|']
    for x in incident:
        if x['available_at_utc'] not in ('2026-11-15T01:00:00Z','2026-11-15T03:00:00Z'):continue
        lines.append(f'| {x["venue"]} | {x["available_at_madrid"]} | {float(x["ao"]):.3f} | {float(x["ao_slope"]):.3f} | {float(x["adx"]):.3f} | {float(x["adx_slope"]):.3f} | {float(x["bbwp"]):.0f} | {x["kon_long"]} | NO |')
    lines += ['', 'A las02:00 Madrid no existe la confluencia completa. El cruce Kon posterior, disponible04:00 Madrid, no cumple la caída ADX pasada ni dos pendientes AO ascendentes. El rebote posterior no se acredita como trade ni se cambian reglas para capturarlo.',
        'Solo velas realmente cerradas recibidas de las APIs públicas Spot y USD-M, conservadas por separado con SHA256. No se completa un outcome24h aún inmaduro. Algunos RAW se reutilizaron después de corregir un parser de timestamps REST int: no se inventa received_at histórico; esa limitación se marca en su manifest.',
        '', '## 10. Archivos, gráficos y reproducción',
        '', '- `signals_all.csv.gz`: todas las35064 horas, valores y gates (descomprimir para CSV). `signals_all.jsonl.gz`: mismo contenido estructurado.',
        '- `trades_all.csv`: esquema con cero operaciones base; `sensitivity_trades.csv`: también conserva las pérdidas de sensibilidad.',
        '- `equity_all.csv.gz`, `metrics.csv`, `random_controls.csv`, `sensitivity.csv`, `year_side_regime.csv`, `signal_funnel.csv`.',
        '- `all_signals_equity.png`, `development_test.png`: todo el periodo. Sin marcadores/SL/TP base porque no existen entradas aceptadas.',
        '- `rejected_1.png`…: primeros cruces/rechazos cronológicos por reglas objetivas, **no trades perdedores o ganadores inventados**. `example_selection.json` confirma que no hay ejemplos de trades base.',
        '- `incident_BINANCE_SPOT.png` y `incident_BINANCE_USDM_PERPETUAL.png`: episodio real, separado.',
        '- `data_manifest.json`, `indicator_audit.json`, `artifact_checksums.json`, hashes de fuentes y protocolo. Los RAW públicos permanecen en cache ignorada; descarga reproducible con checksums.',
        '', 'Desde la raíz del worktree, con Python3.12 y dependencias research:',
        '', '```powershell',
        'python -m research.confluence_1h.data',
        'python -m research.confluence_1h.evaluate',
        'python -m research.confluence_1h.incident',
        'python -m research.confluence_1h.report',
        'python -m unittest test_confluence_1h_research -v',
        '```',
        '', 'Las evaluaciones con datos ya descargados no requieren red. No hay entrenamiento ni selección automática. No ejecutar el driver original del ZIP como sustituto: cambia datos/selección/semántica de simulación.',
        '', '## 11. Limitaciones y decisión',
        '', '**INCONCLUSO. NO-GO para detector operativo o integración en I-GOD.**',
        '', 'No hay evidencia de edge ni evidencia suficiente para estimar un rendimiento negativo de las reglas base: no generan operaciones en esta muestra. La definición auditada no sirve todavía como candidato con frecuencia observable.',
        'Falta paridad real del Pine y una muestra prospectiva adecuada. No se afirma que un parecido visual de indicadores garantice una entrada rentable. Las reglas no se recalibran con este histórico.',
        'Guardian V2, V8, ML RSI, la capa de operabilidad, market-data, Telegram, Railway y BITMAN_WEEKLY_FORWARD_V1 permanecen intactos. Ningún módulo productivo importa este laboratorio. Sin merge ni deploy.',
        '', '**SHADOW ONLY. TRADE AUTHORITY: NONE.**','']
    (out/'IGOD_CONFLUENCE_1H_RESEARCH.md').write_text('\n'.join(lines),encoding='utf-8')
    json_write(out/'artifact_checksums.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='artifact_checksums.json'})


if __name__=='__main__':render()
