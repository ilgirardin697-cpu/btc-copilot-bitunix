"""Mechanical tables of all results; no parameter selection or new signals."""
import csv
import gzip
import hashlib
import io
import json
from .evaluate import HERE, write_csv
from .risk_stress import illustrative_scenarios


def percent(value):
    return '—' if value is None else f'{100*float(value):+.3f}%'


def generate():
    out=HERE/'artifacts'; r=json.loads((out/'results.json').read_text())
    rows=list(csv.DictReader((out/'comparisons.csv').open(newline='',encoding='utf-8')))
    deals=list(csv.DictReader(io.StringIO(gzip.decompress((out/'outcomes.csv.gz').read_bytes()).decode())))
    stress=illustrative_scenarios(); write_csv(out/'risk_stress_illustrative.csv',stress)
    examples=[]
    for pattern in sorted(set(d['pattern'] for d in deals)):
        for side in ('1','-1'):
            subset=sorted([d for d in deals if d['pattern']==pattern and d['side']==side and d['stratum']=='Q75' and d['hours']=='12'],key=lambda d:d['signal_available'])
            for label,positive in [('FIRST_POSITIVE',True),('FIRST_NEGATIVE',False)]:
                match=next((d for d in subset if (float(d['net_fraction'])>0)==positive),None)
                if match:examples.append(dict(selection='FIRST_CHRONOLOGICAL_'+label,**match))
    write_csv(out/'objective_favorable_unfavorable_examples.csv',examples)
    table=['| Patrón/lado | Válidos | Emparejados | Neto12h medio emparejado | Exceso frente a controles | n efectivo / requerido | Resultado |',
           '|---|---:|---:|---:|---:|---:|---|']
    for cell in r['primary']:
        table.append(f"| {cell['pattern']} {'LONG' if cell['side']==1 else 'SHORT'} | {cell['valid_episodes']} | {cell['matched']} | {percent(cell['net_mean'])} | {percent(cell.get('mean'))} | {cell['effective_n']:.2f} / {cell['required_effective_n']} | {cell['classification']} |")
    counts=['| Patrón/lado | ALL | Q75 primario | Q90 |','|---|---:|---:|---:|']
    for pattern in sorted(set(x['pattern'] for x in rows)):
        for side in ('1','-1'):
            cells=[next(x for x in rows if x['stage']=='EVALUATION' and x['pattern']==pattern and x['side']==side and x['horizon']=='12' and x['stratum']==s) for s in ('ALL','Q75','Q90')]
            counts.append(f"| {pattern} {'LONG' if side=='1' else 'SHORT'} | "+' | '.join(x['valid_episodes'] for x in cells)+' |')
    n=int(sum(x['valid_episodes'] for x in r['primary'])); m=int(sum(x['matched'] for x in r['primary']))
    text=f'''# I-GOD — ADX + AO giros1H: resultado de Fase1

**Conclusión: NO TESTABLE. No se demuestra ventaja y no se autoriza pasar a gestión o automatización.**

Seis comparaciones primarias Q75/12h: {n} episodios/celda en evaluación, {m} con 3 controles compatibles; ninguna alcanza potencia/muestra efectiva. Esa suma no representa {n} operaciones independientes: pueden coincidir patrones y la inferencia permanece separada por celda. No se cambia a ALL, Q90,4h,24h ni otro patrón para obtener una conclusión positiva.

## Registro previo y datos

- Protocolo anterior a la medición: commit `a6b3cfb`; SHA256 `{r['protocol_sha256']}`.
- Detector/evaluador previos a medición: `887317f`. Se corrigieron después dos fallos de serialización/metadatos (clave side duplicada y nombre de lista de fuentes), y la descripción de celdas de un solo evento. No se cambiaron fórmulas, reglas, percentiles, comparaciones, fechas ni criterios tras medir.
- BTCUSDT **BINANCE_USDM_PERPETUAL**, H1 cerradas; {r['data_rows']} barras con warmup, {r['raw_sources_checked']} fuentes públicas revalidadas. NPZ SHA256 `{r['data_sha256']}`.
- Desarrollo noviembre2022–diciembre2024; evaluación enero2025–septiembre2026, embargo24h por lado y purga de salidas. Octubre/noviembre no se puntúan. Todo este histórico ya fue examinado: **NO VIRGIN HOLDOUT**.
- Fuente matemática auditada, sin editar PR46–49. Pececillos es la serie elegida; recuperación de pendiente no exige cruce con EMA roja. Color AO no equivale a signo. Paridad propietaria y paridad externa completa NO PROVEN.

## Prueba principal: seis celdas,12h después de entrada ejecutable modelada

{chr(10).join(table)}

Los controles son del **mismo lado**, mes, régimen4H confirmado y tercil de volatilidad causal. No se cambian estratos para completar muestra. Las medias de la tabla corresponden al subconjunto emparejado; `comparisons.csv` conserva además media de todos los episodios, ausencias y cobertura. LONG/SHORT espejo son controles predeclarados, no permisos de operar.

Todos los p incorporados a Holm son1 por falta de testabilidad. Los IC/p brutos del bootstrap son descriptivos y **no interpretables como confirmación con2–12 eventos**; incluso un p bruto pequeño no supera este bloqueo. La varianza de desarrollo y la diferencia mínima de0.10 puntos porcentuales netos exigen muestras efectivas muy superiores. La estimación de potencia es aproximada y especialmente incierta cuando desarrollo tiene pocas parejas; no se corrige seleccionando un efecto mínimo más favorable.

## Intensidad, comparaciones secundarias y frecuencia

{chr(10).join(counts)}

Q75/Q90 son cortes marginales conjuntos de intensidad pasada; no porcentajes obligatorios del número de señales. Separan giros importantes de pequeñas oscilaciones sin fijar umbrales para capturar9–15 de noviembre. Los valores actuales nunca entran en su propia distribución720h. La severidad explica parte de la escasa frecuencia; no se relaja después de verla.

`comparisons.csv` incluye las108 combinaciones de etapa×patrón×lado×intensidad×horizonte; no son108 pruebas principales. `monthly.csv` conserva todos los meses con eventos, y `sensitivity_ex_best.csv` elimina mecánicamente el mejor1/3 por exceso neto, sin modificar señales. `p3_context_secondary.csv` separa coincidencia4H/1D y desconocidos; no convierte un subgrupo atractivo en regla principal. Meses sin filas tienen cero episodios, no datos inventados. Las cohortes y duplicaciones entre intensidades/horizontes no se consideran muestras independientes.

No se expresan retornos enR: no existe stop en Fase1. Se guardan porcentaje neto y equivalente de precio normalizado por ATR. Funding con marks ausentes o simultaneidad de settlement/apertura tiene bandas conservadora/optimista y neto exacto nulo; se preserva el dato faltante. Primera apertura posterior con slippage es un supuesto ejecutable idealizado, **no un fill observado ni garantizado**. No hay PnL desde el vértice ni desde la vela de confirmación.

## Fase2 y estrés: no saltar etapas

No se ejecuta backtest de TP1/break-even/trailing. Antes se necesita una señal testable y luego una especificación nueva del stop y salidas. `risk_stress_illustrative.csv` compara dimensionalmente riesgo fijo1% con50% de margen a10x usando precios/capital sintéticos expresamente identificados; no son operaciones del histórico.

Un nocional5×equity transforma5% de movimiento adverso en25% de pérdida bruta. Un stop ancho puede quedar detrás de la liquidación condicional. Gaps, comisiones y funding pueden superar el riesgo planificado. La documentación oficial y las dos respuestas públicas actuales se encuentran en `BITUNIX_OFFICIAL_AUDIT.md`; no acreditan un simulador de liquidaciones históricas de Bitunix. Se documenta una inconsistencia aritmética de su ejemplo oficial, sin inventar una corrección operativa.

## Forward shadow congelado, no iniciado

Ventana17/11/2026–17/11/2027 UTC,12 meses fijos. Muestra objetivo por celda fijada en `power_frozen_from_development.json`; cobertura horaria verificable mínima95%; resultados finales solo al terminar y madurar24h. No se para porque aparezcan beneficios ni se prolonga para alcanzar significación. Si la frecuencia observada continúa, un año probablemente no bastaría: la finalización será NO TESTABLE, no una relajación. Una activación tardía deja huecos documentados, sin mover fechas. Hace falta autorización separada de captura y paridad externa suficiente; **no existe un observer activo ni se importaron históricos como forward**.

## Reproducción, casos favorables y desfavorables

El ZIP contiene código, protocolo, fuentes públicas/recibos, NPZ y153 archivos originales, CSV completos y hashes. El evaluador se ejecuta offline y debe reproducir los artifacts. `objective_favorable_unfavorable_examples.csv` selecciona primer retorno positivo y negativo cronológico por patrón/lado Q75, sin seleccionar círculos ni movimientos extraordinarios. Son ejemplos exploratorios, no validación independiente. El CSV de outcomes contiene además todos los demás resultados.

Limitaciones: número muy pequeño de episodios intensos, coincidencia temporal estricta declarada, controles con cobertura incompleta, dependencia/estacionariedad del bootstrap, potencia incierta, histórico conocido, costes asumidos, funding parcialmente acotado, apertura posterior idealizada y ausencia de exportación completa externa. **No prueba que todo giro sea inútil; impide afirmar que estas reglas tengan edge.**

Producción, Guardian, V8, ML RSI, los900 estados de operabilidad, market-data y protocolo/journal semanal permanecen sin cambios. No merge, deploy, alertas ni órdenes.

**SHADOW ONLY. TRADE AUTHORITY: NONE.**
'''
    (HERE/'PHASE1_RESULTS.md').write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps(dict(primary_events=n,matched=m,conclusion=r['conclusion'],protocol_sha=r['protocol_sha256'])))


if __name__=='__main__':generate()
