"""Deterministic Markdown report from public, versioned research artifacts."""
import argparse
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path

from research.bitman_weekly_expansion import EPOCHS, HORIZONS, iso, load_snapshot

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/'research/results/bitman_weekly_expansion'


def number(value):
    return '—' if value is None else f'{value:.2f}'


def percent(value):
    return '—' if value is None else f'{100*value:.1f}%'


def ci(row,key):
    a,b=row.get(key+'_ci_low'),row.get(key+'_ci_high')
    return '—' if a is None or b is None else f'[{a:.2f}, {b:.2f}]'


def generate(directory=ARTIFACTS):
    directory=Path(directory)
    result=json.loads((directory/'analysis.json').read_text('utf-8'))
    manifest=json.loads((directory/'data_manifest.json').read_text('utf-8'))
    # Narrative below is reviewed for this fixed study snapshot, not a generic
    # report that may silently reuse old conclusions after a source revision.
    if manifest['four_hour.json']['sha256']!='ea8954f95f15f67eff041e506fc9e0539d5adb7422632b5f7d8246e88704e050':
        raise ValueError('SOURCE_SNAPSHOT_CHANGED_REVIEW_REPORT_NARRATIVE')
    if result['decision']['conclusion']!='EXPANSION EFFECT FRAGILE':
        raise ValueError('CONCLUSION_CHANGED_REVIEW_REPORT_NARRATIVE')
    with (directory/'summaries.csv').open(encoding='utf-8',newline='') as stream:
        summaries=[]
        for record in csv.DictReader(stream):
            summaries.append({k:(v if k in ('scope','event','stratum','sample_status') else None if not v else float(v)) for k,v in record.items()})
    index={(r['scope'],r['event'],r['stratum'],int(r['horizon'])):r for r in summaries}
    get=lambda event,color='ALL',h=4,scope='FULL':index[scope,event,color,h]
    f=load_snapshot(directory)
    meta=result['metadata']
    lines=[]
    add=lines.append

    def table(headers,rows):
        add('| '+' | '.join(headers)+' |')
        add('| '+' | '.join('---' for _ in headers)+' |')
        for row in rows:
            add('| '+' | '.join(str(v).replace('|',' / ') for v in row)+' |')
        add('')

    def event_table(names,colors=('ALL','GREEN','RED')):
        table(['Evento','AO','h semanas','n','µ R','µ firmado','IC95 firmado','Hit','µ abs','µ max abs','MFE','MAE','Observaciones/año'],
            ([name,color,h,int(r['n']),number(r['forward_mean']),number(r['signed_mean']),ci(r,'signed'),percent(r['hit']),
              number(r['absolute_mean']),number(r['max_move_mean']),number(r['mfe_mean']),number(r['mae_mean']),number(r['annual_frequency'])]
             for name in names for color in colors for h in HORIZONS for r in [get(name,color,h)]))

    add('# BITMAN — Weekly AO × BBWP expansion research')
    add('')
    add('**EXPANSION EFFECT FRAGILE — RECOMENDACIÓN: NO INTEGRAR.**')
    add('')
    add('RESEARCH ONLY · HISTORICAL BACKTEST / EVENT STUDY · NO REAL FORWARD OBSERVED SIGNALS.')
    add('No estrategia de trading, órdenes, automatización ni cambios del motor. TRADE AUTHORITY: NONE.')
    add('')
    add('## 1. Hipótesis y protocolo previo')
    add('')
    add('Se separan dos preguntas: (A) si la expansión de BBWP anticipa magnitud futura y (B) si el color del AO añade dirección incremental. ADX/DI es exclusivamente secundario. Ningún N, bucket o porcentaje se eligió por sus resultados.')
    add('')
    add('El [protocolo](BITMAN_WEEKLY_EXPANSION_PROTOCOL.md) se fijó en el commit `a9d428e` antes de descargar/evaluar el histórico completo; solo hubo una petición mínima previa de conectividad/boundary, sin outcomes. SHA256 del protocolo normalizado: `'+meta['protocol_sha256']+'`. Base exacta: `9c660035f912be4640f09cf6e2d4c48583c20b04`.')
    add('')
    add('## 2. Provenance y auditoría de datos')
    add('')
    add('Venue invariable: **BTCUSDT BINANCE_USDM_PERPETUAL**. Fuente principal: GET público [Binance USD-M REST `/fapi/v1/klines`](https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/market.py), desde el PC autorizado; no Railway, Spot, proxy, VPN ni credenciales. Vision se usa solo como contraste independiente, nunca para rellenar o sustituir filas.')
    add('')
    table(['Campo','Valor'],[['Descarga UTC',manifest['acquired_at']],['Primer open 4H REST',iso(manifest['first_4h_open'])],
        ['Último close 4H incluido',iso(manifest['last_4h_close'])],['Filas 4H',manifest['rows_4h']],['Semanas completas',manifest['weeks']],
        ['Primera semana completa',iso(manifest['first_week_open'])],['Último close semanal',iso(manifest['last_week_close'])],
        ['Cutoff exclusivo',iso(manifest['cutoff'])],['SHA256 dataset 4H JSON',manifest['four_hour.json']['sha256']],
        ['SHA256 dataset semanal JSON',manifest['weekly.json']['sha256']]])
    add('El [manifest](bitman_weekly_expansion/data_manifest.json) conserva URLs, parámetros exactos, status, bytes y SHA256 de cada respuesta/ZIP, además de las diferencias numéricas completas. Las respuestas RAW quedan local-only/gitignored. Los CSV versionados contienen solo mercado público y permiten reproducción offline de los resultados.')
    add('')
    weekly=manifest['weekly_rest_comparison']
    count=Counter(d['field'] for d in weekly['differences'])
    table(['Campo solicitado','Filas comparadas 1w','Diferencias exactas 4H→1W vs REST 1w'],
          ([key,weekly['rows'],count[key]] for key in ('open_time','open','high','low','close','base_volume','close_time','taker_buy_base_volume')))
    add('No se afirma paridad de los ocho campos. Una apertura de 2019-09-23 difiere (REST 1w 8,061.98; agregado 4H 10,027.69), y cinco semanas presentan diferencias de volumen/taker. No se atribuye una causa no verificada. **High, low, close y timestamps coinciden en las 371 semanas**. Los ocho arrays utilizados (AO, delta AO, BBWP, delta BBWP, ADX, delta ADX, +DI, −DI) resultan exactamente iguales, NaN incluidos, al calcularlos por separado sobre ambas series. No dependen de open ni volumen. No se mezclaron las fuentes.')
    add('')
    add('El repositorio oficial [Binance Public Data](https://github.com/binance/binance-public-data#klines-1) identifica los klines USD-M de Vision con `/fapi/v1/klines` y documenta CHECKSUM y posibles revisiones posteriores. Se compararon todos los campos solicitados en siete meses disponibles (2019-09 no disponible), con CHECKSUM verificado:')
    add('')
    table(['Mes Vision','Status','Filas','Campos diferentes','Barras diferentes'],
          ([r['month'],r['status'],r.get('rows',0),len(r.get('differences',[])),len({d['open_time'] for d in r.get('differences',[])})] for r in manifest['vision_comparisons']))
    add('Son 1,278 barras de contraste. Solo hay diferencias en volumen/taker: tres barras de marzo 2024 y una de enero 2025; cero diferencias de OHLC/timestamps. Se documentan los deltas exactos en el manifest. Histórico recuperado hoy puede contener revisiones: no equivale a datos point-in-time ni a alertas realmente observadas en esas fechas.')
    add('')
    add('## 3. Definición semanal causal')
    add('')
    add('Semana = lunes 00:00 UTC → siguiente lunes 00:00 UTC, anclada a 1970-01-05 (no al jueves del Unix epoch). Requiere 42 barras 4H contiguas, ordenadas y cerradas; open primero, high máximo, low mínimo, close último, volúmenes sumados con Decimal. Se excluye la semana inicial parcial del 2019-09-02, que solo tiene dos barras 4H. No se rellenan huecos.')
    add('Las 15,584 filas REST pasan schema de 12 columnas, OHLC/volúmenes finitos válidos, closeTime=openTime+4H−1, orden y contigüidad: cero gaps o duplicados en la serie descargada.')
    add('')
    add('La semana abierta 2026-10-19 no está descargada ni calculada. La última cerrada abre 2026-10-12 y finaliza 2026-10-18 23:59:59.999 UTC; su información está disponible en el límite 2026-10-19 00:00 UTC. Las épocas se asignan por ese tiempo de disponibilidad.')
    add('')
    add('## 4. Fórmulas exactas, eventos y outcomes')
    add('')
    add('Se reutiliza sin editar `bitman_manual/frozen/indicators.py::calculate`: AO = SMA5((H+L)/2) − SMA34((H+L)/2), ao_slope = AO[t]−AO[t−1]. GREEN iff slope>0; RED iff slope<0; cero es FLAT. Color no equivale al signo del AO ni a la clasificación multibarra del motor de dirección.')
    add('')
    add('BBW = 4×std poblacional(C,7)/SMA(C,7). BBWP[t] = número de los 100 BBW anteriores estrictamente menores que BBW[t], dentro de 101 valores finitos. Empates no suman; rango 0..100. bbwp_slope = BBWP[t]−BBWP[t−1]. El primer BBWP necesita 107 semanas; la pendiente 108; la cohorte común que requiere la pendiente previa para START necesita 109. Se excluyen '+str(meta['warmup_excluded'])+' semanas iniciales de la cohorte común. No se acorta el ranking.')
    add('')
    add('A: slope>0; B: slope<0; C: slope previo<=0 → actual>0. D: C después de >=2/3/4 slopes previos consecutivos<=0 (subconjuntos anidados). E: C según BBWP previo [0,10], (10,20], (20,30], (30,50], >50. F: cruce estricto actual>50/previo<=50, actual<50 rising y actual>50 rising. Exactamente 50 no se redondea a ninguno de estos dos últimos lados.')
    add('')
    add('Ancla de evaluación = close de la semana del evento, sin afirmar un fill ejecutable. R[h]=100×(C[t+h]/C[t]−1). Signed=R para GREEN, −R para RED. Hit=signed>0; empates no ganan. MFE/MAE son excursiones favorables/adversas no negativas relativas al AO, usando exclusivamente máximos/mínimos de las semanas futuras t+1..t+h. Max abs=max(excursión arriba, excursión abajo). **|R terminal| y max abs intrahorizonte son métricas diferentes**, ambas con frecuencias >=3/5/10/15%. No se incluyen high/low de la propia semana del evento.')
    add('En stratum ALL, firmado sigue el color AO de cada observación, no un lado fijo universal; los retornos raw y las excursiones sin dirección se publican por separado. BBWP es un ranking relativo: su subida/bajada no garantiza por identidad matemática que suba/baje la anchura absoluta de bandas. STARTING/ACTIVE/COOLING describen los eventos BBWP definidos, no una medición causal de volatilidad absoluta.')
    add('')
    add('ADX/DI: TR y DM direccional de H/L/C, Wilder RMA14, ±DI=100×RMA14(±DM)/ATR14; DX=100×|+DI−−DI|/(+DI+−DI); ADX=RMA14(DX). Semilla y NaN iniciales son exactamente los del frozen source. Contexto bull/bear = signo(close 4H−SMA200 4H) de la última 4H cerrada al cierre semanal, igual que el régimen causal existente; no se recalcula usando precios futuros.')
    add('')
    add('IC95 = bootstrap circular de bloques de 8 semanas, 2,000 réplicas, seed 20261020+h. Se remuestrean pares originales semana/outcome, no secuencias de velas inventadas. Intervalos descriptivos, sin corrección por multiplicidad. n<10 o <95% réplicas finitas → IC omitido; n<30 → **INSUFFICIENT FOR CONCLUSION**. El denominador anual usa semanas elegibles de la época/régimen; las fases no solapadas usan la duración calendario completa.')
    add('Entorno de cálculo: Python '+meta['python_version']+', NumPy '+meta['numpy_version']+'. Los CSV incluyen también IC por época/régimen cuando la muestra lo permite; las cuatro fases temporales se muestran como control descriptivo.')
    add('')
    add('## 5. Número de observaciones y cobertura útil')
    add('')
    table(['Dato','Valor'],[['Semanas completas',meta['weeks']],['Semanas con BBWP, slope y slope previo válidos',meta['valid_weeks']],
        ['Primer BBWP disponible',meta['first_bbwp_at']],['Primer evento común disponible',meta['first_valid_at']],
        ['Semanas AO FLAT / AO exactamente cero',str(meta['ao_flat'])+' / '+str(meta['ao_zero'])],['Semanas BBWP slope=0',meta['bbwp_flat']],
        ['Observaciones con futuro 1/2/4 semanas',' / '.join(str(int(get('ALL',h=h)['n'])) for h in HORIZONS)]])
    add('2020 y los cierres hasta el disponible el 2021-10-04 son warmup para la cohorte común, no evidencia evaluable. No se introduce Spot para alargarlo. Una semana con varios eventos aparece en varias tablas, no representa observaciones independientes adicionales. Los últimos horizontes incompletos se censuran, nunca se convierten en retornos cero.')
    add('')
    add('## 6. AO solo y sus cuatro cuadrantes')
    add('')
    event_table(['ALL'],('GREEN','RED','GREEN_POS','RED_POS','GREEN_NEG','RED_NEG'))
    add('Se mantienen por separado AO>0 GREEN, AO>0 RED, AO<0 GREEN y AO<0 RED. Las medias/hits son condicionamientos históricos; no se equipara AO<0 GREEN con una orden alcista. Las distribuciones completas (p10/p25/mediana/p75/p90, sd, extremos) están en `summaries.csv`.')
    add('')
    add('## 7. BBWP solo: magnitud, no dirección')
    add('')
    table(['Grupo','h','n','µ |R|','Mediana |R|','IC95 µ |R|','µ max abs','IC95 µ max abs','P(up)','P(down)'],
          ([name,h,int(r['n']),number(r['absolute_mean']),number(r['absolute_median']),ci(r,'absolute'),number(r['max_move_mean']),ci(r,'max_move'),percent(r['up']),percent(r['down'])]
           for name in ('ALL','A_RISING','B_FALLING','C_START') for h in HORIZONS for r in [get(name,h=h)]))
    table(['Rising − falling','h','n rising/falling','Lift pp','IC95 lift','Ex mejor 1','Ex mejores 3'],
          ([r['metric'],r['horizon'],str(r['n_event'])+'/'+str(r['n_reference']),number(r['difference']),
            '['+number(r['ci_low'])+', '+number(r['ci_high'])+']',number(r['ex_best1_difference']),number(r['ex_best3_difference'])]
           for r in result['contrasts'] if r['kind']=='MAGNITUDE'))
    add('No se demuestra que rising anticipe más magnitud que falling. A 1 semana el pequeño lift de max abs (+0.24 pp) tiene IC cruzando cero y pasa a −0.19 pp al excluir los mejores tres. A 4 semanas, max abs medio es 16.26% rising frente a 18.91% falling; esto contradice la generalización visual, sin justificar una regla inversa nueva. La conclusión FRAGILE describe ese indicio positivo débil, no un efecto expansivo validado.')
    add('')
    add('### Frecuencias de movimiento fuerte: ambas definiciones, todos los umbrales')
    add('')
    table(['Evento','AO','h','n','|R|≥3','≥5','≥10','≥15','max≥3','≥5','≥10','≥15'],
        ([name,color,h,int(r['n']),*[percent(r[k+'_ge_'+str(t)]) for k in ('terminal','move') for t in (3,5,10,15)]]
         for name in ('ALL','A_RISING','B_FALLING','C_START') for color in ('ALL','GREEN','RED') for h in HORIZONS for r in [get(name,color,h)]))
    add('Todos los demás eventos/buckets también incluyen las ocho frecuencias en el CSV completo; no se selecciona un porcentaje objetivo.')
    add('')
    add('## 8. Interacción AO × BBWP y valor incremental')
    add('')
    event_table(['A_RISING','B_FALLING'],('GREEN','RED'))
    table(['AO','h','Referencia','Métrica','n evento/control','Lift','IC95','Ex mejores 3'],
        ([r['color'],r['horizon'],r['reference'],r['metric'],str(r['n_event'])+'/'+str(r['n_reference']),
          number(100*r['difference'] if r['metric']=='hit' else r['difference']),
          '['+number(100*r['ci_low'] if r['metric']=='hit' and r['ci_low'] is not None else r['ci_low'])+', '+number(100*r['ci_high'] if r['metric']=='hit' and r['ci_high'] is not None else r['ci_high'])+']',
          number(100*r['ex_best3_difference'] if r['metric']=='hit' else r['ex_best3_difference'])]
         for r in result['contrasts'] if r['kind']=='DIRECTION'))
    add('Los controles CONSTANT_SIDE usan el mismo lado fijo (+R GREEN, −R RED) en todas las semanas rising; así no se confunde drift alcista con información del AO. SAME_COLOR elimina la condición BBWP. Las diferencias de hit están en pp; las demás, pp de retorno. Ningún lift firmado AO-vs-constant-side tiene IC95 positivo a los tres horizontes. El caso RED+rising tiene medias firmadas negativas en 1/2/4 semanas, con IC amplios: no se concluye valor direccional bajista.')
    add('')
    event_table(['A_RISING','B_FALLING'],('GREEN_POS','RED_POS','GREEN_NEG','RED_NEG'))
    add('')
    add('## 9. Expansion start')
    add('')
    event_table(['C_START'])
    table(['h','Métrica de magnitud','Referencia','n','Lift','IC95','Ex mejores 3'],
        ([r['horizon'],r['metric'],r['reference'],r['n_event'],number(r['difference']),
          '['+number(r['ci_low'])+', '+number(r['ci_high'])+']',number(r['ex_best3_difference'])]
         for r in result['contrasts'] if r['kind']=='EVENT_MAGNITUDE' and r['event']=='C_START'))
    add('Hay 50 starts con futuro completo; GREEN 20 y RED 30. GREEN START tiene media firmada 4W +5.58%, pero IC95 [−3.38,+14.07] y n=20: **INSUFFICIENT FOR CONCLUSION**. RED START no valida dirección bajista. Las comparaciones por color contra START sin AO y SAME_COLOR, con todos sus IC, están en `contrasts.csv`; una diferencia positiva de magnitud en un horizonte no satisface los criterios robustos del protocolo ni valida dirección.')
    add('Indicio exploratorio que sí aparece: START a 2W tiene |R| medio 9.29% frente a 7.47% en ALL; lift +1.82 pp, IC95 [0.23,3.46]. Frente a falling, su IC cruza cero; tampoco se reproduce en todos los horizontes ni en max abs. Es una comparación nominal entre muchas, no evidencia suficiente para STRONG MOVE WATCH. Se conserva como hallazgo descriptivo, sin seleccionar una regla 2W.')
    add('')
    add('## 10. Contracción previa: N=2, 3 y 4 sin elegir ganador')
    add('')
    event_table(['D_PRIOR_2','D_PRIOR_3','D_PRIOR_4'])
    add('Los tres N se muestran siempre. Son subconjuntos anidados del start; no se suman sus n. Las celdas pequeñas no permiten seleccionar el mejor N ni sugerir que su media establezca una regla. Comparaciones completas contra ALL/falling, mismo color y evento sin AO: `contrasts.csv`.')
    add('')
    add('## 11. Expansion start por BBWP previo')
    add('')
    event_table(['E_0_10','E_10_20','E_20_30','E_30_50','E_GT50'])
    add('Buckets disjuntos del BBWP **anterior**, con extremos documentados en §4. Todos se publican, incluidos n=0 e IC omitidos; ninguna ausencia de outcome se trata como fallo direccional. No se elige un bucket por rentabilidad aparente.')
    add('')
    add('## 12. Zona 50, descriptiva')
    add('')
    event_table(['F_CROSS50','F_BELOW50_RISING','F_ABOVE50_RISING'])
    add('Semanas válidas exactamente BBWP=50 y rising: '+str(int(((f['bbwp']==50)&(f['bbwp_slope']>0)&f['valid']).sum()))+'. Se conserva el cruce estricto >50 del frozen feature. No se interpreta 50 como predictivo sin evidencia incremental estable.')
    add('')
    add('## 13. ADX/DI secundario — no entra en la hipótesis principal')
    add('')
    secondary=[r for r in summaries if r['scope']=='ADX_SECONDARY']
    table(['AO','BBWP / ADX / DI','h','n','µ firmado','IC95','Hit','µ max abs','P(max≥10)'],
        ([r['stratum'],r['event'],int(r['horizon']),int(r['n']),number(r['signed_mean']),ci(r,'signed'),percent(r['hit']),number(r['max_move_mean']),percent(r['move_ge_10'])] for r in secondary))
    add('Foco solicitado: RED+rising BBWP+−DI leads+ADX falling y el equivalente GREEN/+DI. El lift firmado respecto al mismo AO/BBWP, y respecto a ADX rising con el mismo DI, es:')
    add('')
    table(['AO','h','Referencia','n evento/control','Lift firmado','IC95','Ex mejores 3'],
        ([r['color'],r['horizon'],r['reference'],str(r['n_event'])+'/'+str(r['n_reference']),number(r['difference']),
          '['+number(r['ci_low'])+', '+number(r['ci_high'])+']',number(r['ex_best3_difference'])]
         for r in result['contrasts'] if r['kind']=='ADX_SECONDARY' and r['metric']=='signed' and
         (r['color'],r['event']) in (('RED','A_RISING|ADX_FALLING|DI_BEARISH'),('GREEN','A_RISING|ADX_FALLING|DI_BULLISH'))))
    add('Esto admite observar movimientos mientras ADX cae sin convertir ADX en dirección. La tabla no prueba precedencia causal de ADX ni una nueva condición: cohortes pequeñas, solapamiento y múltiples comparaciones. No se optimiza ni se añade ADX a la regla.')
    add('')
    add('## 14. Robustez temporal, régimen y controles causales')
    add('')
    table(['Época','h','n rising/falling','Lift |R|','Lift max abs','GREEN rising n / µ firmado','RED rising n / µ firmado'],
        ([epoch,h,str(int(a['n']))+'/'+str(int(b['n'])),number(a['absolute_mean']-b['absolute_mean']),number(a['max_move_mean']-b['max_move_mean']),
          str(int(g['n']))+' / '+number(g['signed_mean']),str(int(r['n']))+' / '+number(r['signed_mean'])]
         for epoch in EPOCHS for h in HORIZONS for a,b,g,r in [(get('A_RISING',h=h,scope=epoch),get('B_FALLING',h=h,scope=epoch),get('A_RISING','GREEN',h,epoch),get('A_RISING','RED',h,epoch))]))
    add('2020–2022 significa realmente desde 2021-10-11 en esta cohorte. Los signos de las diferencias cambian entre épocas. 2024+ fue reutilizado en estudios previos: **TEST REUSED / NO VIRGIN HOLDOUT**. Ninguna regla se selecciona mirando una supuesta muestra test nueva.')
    add('')
    table(['Régimen causal 4H','h','n rising/falling','Lift |R|','Lift max abs','GREEN n / firmado','RED n / firmado'],
        ([regime,h,str(int(a['n']))+'/'+str(int(b['n'])),number(a['absolute_mean']-b['absolute_mean']),number(a['max_move_mean']-b['max_move_mean']),
          str(int(g['n']))+' / '+number(g['signed_mean']),str(int(r['n']))+' / '+number(r['signed_mean'])]
         for regime in ('BULL','BEAR') for h in HORIZONS for a,b,g,r in [(get('A_RISING',h=h,scope=regime),get('B_FALLING',h=h,scope=regime),get('A_RISING','GREEN',h,regime),get('A_RISING','RED',h,regime))]))
    add('Fases de observaciones no solapadas: las cuatro se publican, sin elegir la más favorable. La fase se fija por índice semanal desde la primera semana completa. Para h<=4, cada fase usa anclas separadas por cuatro semanas.')
    add('')
    table(['Fase','h','n all / rising / falling','Lift |R|','Lift max abs','GREEN rising firmado','RED rising firmado'],
        ([phase,h,' / '.join(str(int(x['n'])) for x in (base,a,b)),number(a['absolute_mean']-b['absolute_mean']),number(a['max_move_mean']-b['max_move_mean']),number(g['signed_mean']),number(r['signed_mean'])]
         for phase in range(4) for h in HORIZONS for base,a,b,g,r in [(get('ALL',h=h,scope='NONOVERLAP_'+str(phase)),get('A_RISING',h=h,scope='NONOVERLAP_'+str(phase)),get('B_FALLING',h=h,scope='NONOVERLAP_'+str(phase)),get('A_RISING','GREEN',h,'NONOVERLAP_'+str(phase)),get('A_RISING','RED',h,'NONOVERLAP_'+str(phase)))]))
    add('Control local sin lookahead: media de >=12 outcomes ya maduros de las 52 semanas previas (j+h<=i). Exceso del evento frente a esa media observable en su cierre:')
    add('')
    table(['Evento','AO','h','Métrica','n','Exceso medio pp','IC95'],
        ([r['event'],r['color'],r['horizon'],r['metric'],r['n'],number(r['mean_excess']),'['+number(r['ci_low'])+', '+number(r['ci_high'])+']'] for r in result['temporal']))
    add('Los CSV contienen además cada evento/bucket por todas las épocas y ambos regímenes; no se extrapola una celda de época/régimen al conjunto del mercado.')
    add('')
    add('## 15. Sensitivity: ex-best-1 y ex-best-3')
    add('')
    table(['Evento','AO','h','n','Firmado mediana / p10 / p90','|R| mediana / p10 / p90','Max abs mediana / p10 / p90'],
        ([name,color,h,int(r['n']),*[' / '.join(number(r[key+suffix]) for suffix in ('_median','_p10','_p90')) for key in ('signed','absolute','max_move')]]
         for name in ('ALL','A_RISING','B_FALLING','C_START') for color in ('ALL','GREEN','RED') for h in HORIZONS for r in [get(name,color,h)]))
    table(['Evento','AO','h','n','Firmado all / ex1 / ex3','|R| all / ex1 / ex3','Max abs all / ex1 / ex3'],
        ([name,color,h,int(r['n']),*[' / '.join(number(r[key+suffix]) for suffix in ('_mean','_ex_best1_mean','_ex_best3_mean')) for key in ('signed','absolute','max_move')]]
         for name in ('ALL','A_RISING','B_FALLING','C_START') for color in ('ALL','GREEN','RED') for h in HORIZONS for r in [get(name,color,h)]))
    add('Cada métrica elimina sus propios mejores eventos; no se elige una fecha conveniente para todas. Los controles permanecen sin recortar en los lifts de `contrasts.csv`. `analysis.json::influence` publica fechas y valores de los mejores tres en **todos** los eventos y cuadrantes. Las demás celdas contienen ambas sensibilidades en `summaries.csv`. Un n pequeño tras recortar sigue siendo insuficiente, no una estimación estable.')
    add('La columna n es la muestra completa; ex1 y ex3 usan n−1 y n−3 observaciones finitas respectivamente. Si n<=k, el resultado ex-best-k es UNKNOWN (—), no un cero.')
    add('')
    add('## 16. Limitaciones y reproducción')
    add('')
    add('Validación software local (Python 3.12): **797 tests passed, 0 failed, 0 skipped** en discovery completo; **43 tests research** pasan también por separado. Audit existente: `MLRSI_SAFETY_AUDIT_OK`. El guard compara 61 fuentes/configs existentes con su SHA256 de producción y rechaza imports directos, relativos, alias o referencias dinámicas a este research desde cualquier módulo productivo. Se añade un workflow offline sin cambiar los siete anteriores.')
    add('')
    add('- 371 semanas de mercado, pero solo 263 semanas con todos los lags; 262/261/259 outcomes maduros. La muestra efectiva es menor por solapamiento y episodios persistentes. Muchos starts/buckets/ADX tienen n<30 o n<10.')
    add('- Solo una venue/instrumento y un histórico revisable. Source disagreements documentados: no se afirma equivalencia de open/volume ni disponibilidad histórica point-in-time. No eventos forward observados, ML RSI ni ejecución simulada.')
    add('- La observación visual original pudo estar influida por este histórico: análisis descriptivo, no confirmación independiente. TEST reutilizado, sin holdout virgen; no search, retuning ni reglas seleccionadas.')
    add('- Bootstrap de bloques de longitud fija es aproximado: no estacionariedad, dependencia más larga y colas gruesas pueden afectar cobertura. IC no simultáneos/multiplicidad; una celda favorable no demuestra significancia general.')
    add('- Medir magnitud desde el close no predice disponibilidad de un fill, recorridos intravela ni first-touch. Max move usa extremos semanales, no orden temporal de hits. Sin costes/PnL porque esto estudia información direccional y magnitud.')
    add('- Un movimiento ocurrido dentro de la propia semana que hace girar AO/BBWP no cuenta como anticipación: ya pasó al cerrar el evento. La lectura visual puede incluir ese tramo; este estudio exige movimiento posterior.')
    add('- N/D/E se reportan completos; las diferencias entre grupos no son una prueba de causalidad económica. ADX falling no equivale a ausencia de movimiento ni determina por sí mismo el lado.')
    add('- Retroceso/corrección no tiene una etiqueta causal congelada adicional en este estudio. B identifica contracción de BBWP, no demuestra por sí solo que toda corrección reduzca volatilidad; no se inventó una definición usando el futuro.')
    add('')
    add('Reproducción con RAW locales o nueva descarga explícita (podría cambiar por revisiones de fuente):')
    add('')
    add('```text\npython -m research.bitman_weekly_data --cache research/cache/new_weekly_download\npython -m research.bitman_weekly_expansion --cache research/cache/new_weekly_download\npython -m research.bitman_weekly_reporting\npython -m unittest test_bitman_weekly_expansion test_bitman_weekly_boundary -v\n```')
    add('')
    add('Reproducción offline sin RAW, red, escrituras ni cuenta: `python -m research.bitman_weekly_expansion --replay research/results/bitman_weekly_expansion`. Recalcula los indicadores frozen desde `weekly_bars.csv`, verifica su coincidencia y consume el contexto 4H versionado (close, SMA200 y timestamp de disponibilidad; verifica la etiqueta y que no haya lookahead). La procedencia completa de ese contexto se verifica con el RAW 4H y su hash. Los tests reproducen todas las tablas, n, medias e intervalos con tolerancia numérica 1e-8. El generador de narrativa está fijado al hash de este snapshot; una revisión de fuente obliga a revisar el texto, no reutiliza conclusiones silenciosamente.')
    add('')
    add('## 17. Conclusión y recomendación de integración')
    add('')
    add('**'+result['decision']['conclusion']+'**')
    add('')
    add('**NO INTEGRAR.** No se demuestra valor incremental robusto de magnitud para BBWP rising ni dirección incremental para AO. El pequeño indicio positivo de excursión 1W depende de extremos y contradice épocas; el resto no convierte esta hipótesis en una señal validada. Los starts merecen como máximo observación research, sin promover un N, bucket ni dirección favorable.')
    add('')
    add('No se propone un bloque semanal para runtime ni una nueva condición de READY_LONG/READY_SHORT. Tampoco procede activar STRONG MOVE WATCH, ni siquiera con dirección UNKNOWN, porque el efecto expansivo robusto requerido no ha quedado demostrado. En investigación, STARTING=C, ACTIVE=A fuera de C, COOLING=B son etiquetas descriptivas; COMPRESSION necesita una definición independiente previamente fijada y validada, no un umbral inventado en este estudio.')
    add('')
    add('## Último cierre: CURRENT OBSERVATION — NOT PART OF VALIDATION')
    add('')
    current=result['current']
    add('```text\nWEEK OPEN: '+current['week_open']+'\nCLOSED / AVAILABLE: '+current['available_at']+
        '\nWEEKLY AO: '+current['ao_color']+'\nAO LEVEL: '+number(current['ao'])+' (>0)'+
        '\nAO SLOPE: '+number(current['ao_slope'])+'\nBBWP: '+number(current['previous_bbwp'])+' → '+number(current['bbwp'])+
        '\nBBWP SLOPE: '+number(current['bbwp_slope'])+' (FALLING)\nEXPANSION: '+current['expansion']+
        '\nSTRONG MOVE WATCH: UNKNOWN — NOT VALIDATED\nCURRENT OBSERVATION ONLY\nNOT AN ORDER\nTRADE AUTHORITY: NONE\n```')
    add('')
    add('GREEN aquí significa que AO sube, mientras BBWP cae: **no hay expansión start ni active** en el último cierre. COOLING no afirma volatilidad absoluta baja: solo describe slope negativo. La semana abierta no se usa. Este punto no tiene outcomes futuros completos en ninguno de los tres horizontes y no entra en validación.')
    add('')
    add('Production unchanged: frozen engine, indicadores/thresholds, gates, Guardian, market-data, V8, ML RSI, risk/execution y Telegram. NO MERGE · NO DEPLOY · NO RAILWAY CHANGES.')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',default=str(ARTIFACTS))
    args=parser.parse_args()
    report=generate(args.directory)
    output=ROOT/'research/results/BITMAN_WEEKLY_EXPANSION.md'
    output.write_text(report,encoding='utf-8')
    print(json.dumps(dict(report=str(output.relative_to(ROOT)),bytes=len(report.encode()),sha256=hashlib.sha256(report.encode()).hexdigest())))
