"""Mechanical diagnostic tables; no thresholds, signal selection or training."""
import csv,gzip,io,json
from collections import Counter
import numpy as np
from .replay import HERE
from ..evaluate import write_csv


def read(name):
    raw=(HERE/'artifacts'/name).read_bytes()
    if name.endswith('.gz'):raw=gzip.decompress(raw)
    return list(csv.DictReader(io.StringIO(raw.decode())))


def pct(v):return '—' if v in (None,'') else f'{100*float(v):+.3f}%'


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',*['| '+' | '.join(str(v) for v in r)+' |' for r in rows]])


def generate():
    out=HERE/'artifacts';meta=json.loads((out/'results.json').read_text())
    funnels=read('funnel.csv');nov=read('november.csv');delay=read('delay.csv');power=read('power_MDE.csv');costs=read('cost_summary.csv')
    ev=[r for r in funnels if r['stage']=='EVALUATION']
    first=table(['Patrón/lado','ADX simple/2+2','AO simple/2+2','Pece simple/2+2','Simultáneos2+2','Ventana2h'],
        [[r['pattern']+' '+('LONG' if r['side']=='1' else 'SHORT'),r['individual_adx_simple']+'/'+r['individual_adx22'] if r['adx_required']=='True' else 'No exigido; pico '+r['individual_adx_simple_peak']+'/'+r['individual_adx22_peak']+'; suelo '+r['individual_adx_simple_trough']+'/'+r['individual_adx22_trough'],
          r['individual_ao_simple']+'/'+r['individual_ao22'],r['individual_pece_simple']+'/'+r['individual_pece22'],r['simultaneous22'],r['within2h_raw']] for r in ev])
    last=table(['Patrón/lado','Ventana2h','Tras alineación/signo/DMI','Tokens efectivos','Cooldown','ALL','Q75','Q90'],
        [[r['pattern']+' '+r['side'],r['within2h_raw'],r['after_dmi_ok'],r['complete_stateful_before_cooldown'],r['cooldown'],r['ALL'],r['Q75'],r['Q90']] for r in ev])
    reasons=table(['Patrón/lado','Signo actualAO','Signo en eventoAO','PendienteAO','Pendientepece','PendienteADX','DMI','Tokens'],
        [[r['pattern']+' '+r['side'],*[r[k] for k in ('ordered_drop_ao_sign_ok','ordered_drop_ao_event_sign_ok','ordered_drop_ao_slope_ok','ordered_drop_pece_slope_ok','ordered_drop_adx_slope_ok','ordered_drop_dmi_ok','ordered_drop_stateful_tokens')]] for r in ev])
    overlapping=table(['Patrón/lado','Fallo signoAO','Signo en eventoAO','PendienteAO','Pendientepece','PendienteADX','DMI'],
        [[r['pattern']+' '+r['side'],*[r['nonexclusive_'+k+'_fail'] for k in ('ao_sign_ok','ao_event_sign_ok','ao_slope_ok','pece_slope_ok','adx_slope_ok','dmi_ok')]] for r in ev])
    sample=[r for r in nov if r['available_madrid'].startswith('2026-11-15T05:00:00')]
    point=table(['Venue','DisponibilidadMadrid','ADX','AO','Pececillos','Δ previas2+2, cronológicas','ADX/AO/pece2+2','Confirmación'],
        [[r['venue'],r['available_madrid'],f"{float(r['adx']):.6f}",f"{float(r['ao']):.6f}",f"{float(r['pececillos']):.6f}",
          ' / '.join(f"{float(r['pece_delta_lag'+str(j)]):+.6f}" for j in (3,2,1,0)),
          r['adx_22_down']+'/'+r['ao_22_up']+'/'+r['pece_22_up'],r['confirmed_events']] for r in sample])
    late=[r for r in nov if r['available_madrid'].startswith('2026-11-15T16:00:00')]
    timing=[r for r in delay if r['pattern']=='P1_PEAK_EXHAUSTION' and r['side']=='1' and r['ao22_available']=='2026-11-15T04:00:00Z']
    time_table=table(['Venue','Etapa','DisponibleUTC','Precio referencia / entrada','Movimiento desde ref no causal','Posterior12h precio','Estado'],
        [[r['venue'],r['stage'],r['signal_available'] or 'NO CAUSAL',r['entry_reference'] or '—',pct(r.get('move_from_hindsight_ref')),pct(r.get('post_12h_price_fraction')),r['status']] for r in timing])
    power_table=table(['Patrón/lado','n desarrollo','Sigma neto','N MDE0.10pp PRIMARY','N MDE0.30pp','N MDE0.50pp'],
        [[p+' '+s,next(r['development_matched_n'] for r in power if r['pattern']==p and r['side']==s),
          next(r['sigma_sample_ddof1'] for r in power if r['pattern']==p and r['side']==s),
          *[next(r['required_effective_n'] for r in power if r['pattern']==p and r['side']==s and np.isclose(float(r['MDE_pp']),m)) for m in (.1,.3,.5)]]
          for p,s in dict.fromkeys((r['pattern'],r['side']) for r in power)])
    primary=[r for r in costs if r['stage']=='EVALUATION' and r['stratum']=='Q75' and r['horizon']=='12' and r['scenario']=='CONSERVATIVE']
    cost_table=table(['Patrón/lado','n/matched','Bruto precio sin fricción (todos)','Bruto con slippage (todos)','Neto conservador (matched)','Neto VIP0 supuesto (matched)'],
        [[r['pattern']+' '+r['side'],r['n']+'/'+r['matched'],pct(r['raw_gross_mean']),pct(r['gross_after_slip_mean']),pct(r['net_paired_mean']),
          pct(next(x['net_paired_mean'] for x in costs if x['pattern']==r['pattern'] and x['side']==r['side'] and x['stratum']=='Q75' and x['stage']=='EVALUATION' and x['horizon']=='12' and x['scenario']=='BITUNIX_VIP0_TAKER_ASSUMPTION'))] for r in primary])
    rr=read('cost_rows.csv.gz');examples=[]
    for p,s in dict.fromkeys((r['pattern'],r['side']) for r in primary):
        cohort=sorted([r for r in rr if r['pattern']==p and r['side']==s and r['stage']=='EVALUATION' and r['stratum']=='Q75' and r['horizon']=='12' and r['scenario']=='CONSERVATIVE'],key=lambda r:r['available_at'])
        for positive in (True,False):
            row=next((r for r in cohort if (float(r['net_conservative_funding'])>0)==positive),None)
            if row:examples.append(dict(selection='FIRST_CHRONOLOGICAL_POSITIVE' if positive else 'FIRST_CHRONOLOGICAL_NEGATIVE',**row))
    write_csv(out/'cases.csv',examples)
    totals=Counter()
    for r in ev:
        for k in ('ALL','Q75','Q90','within2h_raw','cooldown'):totals[k]+=int(r[k])
    early=read('early_turns.csv')
    early_table=table(['Venue','Serie','Primer giro','Previas<2','Falla siguiente','Confirma2+2','Censurado'],
        [[v,s,len(xs),*[sum(x['later22_status']==k for x in xs) for k in ('PRIOR_RUN_LT2','NEXT_SLOPE_FAILED','CONFIRMED22','CENSORED')]]
         for v in ('SPOT','USDM') for s in ('ADX','AO','PECECILLOS') for xs in [[r for r in early if r['venue']==v and r['series']==s]]])
    text=f'''# I-GOD — Fase1B: diagnóstico del detector de giros

**PR50 permanece intacta. Conclusión original: NO TESTABLE. No se propone una variante ganadora ni se cambia ninguna regla.**

Base exacta `a48af422f485554dd28ee8da45a3cf1aa0a01929`. Plan de diagnóstico registrado en `da9cd29` antes de generar estas tablas. Instrumentación de solo lectura mediante `sys.settrace`: se ejecuta la función original, no una traducción aproximada. Su SHA normalizado es `{meta['frozen_detector_sha256']}`. Eventos y audit son idénticos con/sin observación y los36 recuentos de etapa/patrón/lado/intensidad reproducen los publicados. Los CSV originales y el protocolo no se editan.

## 1. Embudo completo

Evaluación original enero2025–septiembre2026, mismas purgas y separación temporal. Desarrollo se conserva por separado en CSV. Un giro simple significa cambio estricto del signo de pendiente;2+2 exige dos pendientes anteriores opuestas y dos posteriores alineadas. Son definiciones distintas, no discrepancia numérica de los indicadores.

{first}

Los conteos individuales son universos paralelos, no etapas anidadas. P3 no exige ADX: se muestra su giro como dato descriptivo, nunca se añade como filtro. Simultaneidad y ventana2h también son dos conteos descriptivos: la ventana incluye coincidencias no simultáneas. **No se han simulado operaciones con esas oportunidades alternativas.**

{last}

Las oportunidades en2h se forman con los últimos eventos2+2 de cada serie. Después se aplica el orden explícito de diagnóstico: signo actualAO, signo exigido durante el eventoAO, pendienteAO, pendientepececillos, pendienteADX y DMI cuando corresponden. La última columna de descartes representa diferencia frente al estado real de tokens, no un nuevo filtro. Los conteos reales incluyen expiración, consumo, invalidación y cooldown de la función congelada.

{reasons}

Fallos **no excluyentes**, incluidos los candidatos que incumplen varias condiciones:

{overlapping}

Estas columnas no se suman entre sí. Un descarte marginal DMI de0 puede coexistir con fallos DMI no excluyentes: aquellos candidatos ya se descartaron por una condición anterior. No se interpreta como ausencia de efecto del DMI.

**Qué elimina más:** pececillos pierde aproximadamente59% de sus giros simples al exigir2+2; AO y ADX pierden aproximadamente33–34%. La coincidencia conjunta es otro cuello de botella; no se atribuye su pérdida a un solo indicador. Dentro de las oportunidades2h, el signo de AO domina P3, y la alineación de pececillos es importante en P2. El filtro final Q75 deja {totals['Q75']} de {totals['ALL']} episodios/celda ALL ({100*(1-totals['Q75']/totals['ALL']):.1f}% eliminados), sumando las seis celdas sin llamarlas operaciones independientes. En P1 LONG:87 oportunidades2h→54 coincidencias con tokens efectivos→49 tras cooldown→2 Q75. En P2 SHORT:115→71→63→4. P3 SHORT:363→91→74→12. Ningún porcentaje justifica relajar las reglas tras verlos.

`trace.csv.gz` contiene todas las filas de estado válido por hora/patrón/lado: tokens antes y después, campos fallidos simultáneos, estados y eventos. `opportunities.csv.gz` conserva las oportunidades estáticas. Las invalidaciones/expiraciones de bundles pendientes no tienen el mismo denominador que las oportunidades completas: se publican sin sumarlas indebidamente como pérdidas de señales. Los descartes marginales dependen del orden declarado; las columnas no excluyentes evitan atribuir causalidad artificial a ese orden.

Q75 aplica `min(rangos de componentes aplicables) >=0.75`, y Q90 aplica>=0.90. **No seleccionan el25%/10% más intenso de los episodios**: son cortes conjuntos de rangos marginales calculados en720 horas anteriores. Esa exigencia compuesta explica parte de la reducción93.8%; no se cambia ahora la definición para obtener más señales.

## 2. Auditoría del12–15noviembre: Spot y USD-M separados

Velas cerradas BTCUSDT con el prefijo original de septiembre preservado, más cuatro GET públicos (hora y klines por mercado). En cada uno, tres velas cerradas de solapamiento coinciden con el fixture anterior. No se incorpora2019 ni otra ampliación histórica. Orígenes/horas reales de recepción/SHA están en `fixtures/`. Las limitaciones de atestación de las primeras descargas antiguas se mantienen: conservar bytes no inventa un recibo HTTP original.

Se dispone de velas hasta cierre UTC22:00 del15nov (23:00 Madrid), **no de todo el día ni de sus horizontes futuros**. `november.csv` contiene cada hora disponible: OHLC, ADX/DMI, AO signo/color, pececillos, EMA roja, cuatro pendientes, giros, cruces, tokens faltantes, confirmaciones y siguiente apertura. La disponibilidad es el primer cierre que permite calcularlo; `actual_original_emitted_at=null`: esto es replay histórico contaminado, no captura forward.

**Actualización separada al retomar el16nov:** `november_full.csv` completa la última hora solicitada con96 velas por venue,192 filas, hasta23:00UTC del15nov (00:00Madrid del16). Los nuevos recibos tienen su fecha real del16nov. El primer corte190 filas y sus artifacts permanecen conservados; `completion.json` verifica el prefijo y eventos anteriores idénticos. `delay_full.csv` añade esa hora a la misma medición sin cambiar reglas ni inventar horizontes posteriores. Los cuatro gráficos utilizan esta cobertura completa. Son datos históricos recuperados después, nunca predicciones forward originales. La primera consulta de ampliación encontró un fallo transitorio DNS; el reintento funcionó sin cambiar DNS, host ni mecanismo de acceso.

### 15nov,05:00 Madrid

{point}

**Sí: la falta de las dos pendientes anteriores de pececillos descarta este rebote en PR50.** En Spot la secuencia cronológica es+7.689883,−12.926630,+27.433752,+27.786542. Hay una sola pendiente previa negativa, no dos. ADX/AO sí confirman2+2, y pececillos cruza la roja en esa vela, pero un cruce no sustituye el giro2+2 congelado. Igual conclusión en USD-M. No es una prueba de que un filtro más laxo ganaría dinero.

El caso de agotamiento de la tarde sigue separado: a16:00 Madrid pececillos cae pero sigue sobre la EMA roja, AO está negativo con barra roja y el ADX desciende. Los valores por mercado y las horas intermedias están completos en CSV y gráficos; no se fuerza la observación aproximada14:00 para hacerla coincidir. Ausencia de confirmación no es un error de cálculo por sí misma: puede ser efecto deliberado de condiciones más estrictas que la observación visual.

## 3. Retraso y movimiento ya ocurrido

{time_table}

El extremo de referencia es el low/high de la vela del vértice del AO, identificado retrospectivamente. **No es un fill posible ni se afirma que sea el mínimo/máximo global del precio.** Su instante intrabar exacto es desconocido. Primer giro observable significa cierre de la primera pendiente nueva, y entrada modelada significa apertura siguiente; confirmar2+2 exige otro cierre. La coincidencia completa solo se vincula si el evento original conserva exactamente el mismo tokenAO, nunca a una señal futura distinta.

En este ejemplo, una parte grande de la subida ocurre dentro de la vela que permite observar la primera recuperación. No se contabiliza como beneficio obtenido por una confirmación posterior. `delay.csv` registra todos los girosAO2+2 del intervalo, ambos lados y patrones asociados, con movimiento desde la referencia, excursión favorable previa, movimiento restante hasta un endpoint común de24h desde el vértice y retornos de precio4/12/24h. Campos sin horizonte completo quedan CENSORED/null, no0.

**Sesgo de selección importante:** la comparación temprana dentro de esa tabla está condicionada a que posteriormente exista2+2. No valida una entrada al primer giro. Para no esconder los giros tempranos que fracasan, `early_turns.csv` conserva **todos** los primeros cambios observables, incluidos los que no sobreviven o ya incumplen las dos pendientes previas:

{early_table}

Estas referencias comparan disponibilidad y movimiento, no estrategias ejecutables. No se mezclan sus retornos de precio sin costes con la simulación neta histórica.
Los retornos direccionales SHORT sobre Spot son referencias matemáticas; no representan una venta en contado ejecutable sin préstamo o inventario. No existe paridad externa completa certificada de TradingOne por reconstruir estos gráficos públicos.

## 4. Sigma, potencia e inferencia

Sigma se reconstruye con los excesos netosQ75/12h de DESARROLLO: retorno de cada episodio menos media de sus tres controles originales. Desviación muestral `ddof=1`. Cada entrada y control están en `dev_variance.csv`; las seis sigma y los N primarios reproducen exactamente el artifact congelado.

Fórmula de planificación: `ceil(((z(1−.05/6)+z(.8))*sigma/MDE)^2)`, unilateral, potencia80%, planificación conservadora para la familiaHolm. Es N efectivo requerido, no se trata como número de velasH1 independientes. Se conserva la estimación original de dependencia por bloques de7d y el mínimo20 bloques ocupados.

{power_table}

La sensibilidad0.30/0.50pp no altera el primario0.10pp ni su conclusión. Solo2–7 parejas de desarrollo por celda estiman sigma: es una limitación muy seria de la planificación, no una precisión certificada. Los IC/p de bootstrap con celdas tan pequeñas son descriptivos y no calibración fiable de una ventaja. Un p bruto favorable no supera el bloqueo de muestra: Holm mantiene p=1 para las celdas no testables.

Auditoría estática adicional de la inferencia original: el bucle procesa ALL antes de estimar sigmaQ75; ALL usa la sigma fallback de todos los retornos horarios de desarrollo (combinando lados para esa estimación de varianza), y Q90 hereda sigmaQ75. Esta asimetría secundaria se documenta, **no se corrige retrospectivamente ni se usa para elegir otro primario**. La reconstrucciónQ75 aquí no usa evaluación para estimar sigma. El bloque llamado evaluación ya fue inspeccionado: NO VIRGIN HOLDOUT.

## 5. Bruto, neto y coste separadoVIP0

{cost_table}

Se distingue bruto de precio sin fricción de bruto entre fills con slippage. Las dos primeras medias utilizan todos los episodios de la celda; las dos últimas el mismo subconjunto emparejado para reproducir PR50. `cost_summary.csv` conserva además netos de todos los episodios y exceso frente a controles en ambos supuestos.

Supuesto conservador: comisión0.10%/lado; sensibilidadVIP0 taker0.06%/lado publicada en la [tabla oficial Bitunix](https://www.bitunix.com/service/handling-fee), revisada15nov2026. No se verifica el nivel personal ni se supone comisión maker. Ambos mantienen slippage adverso0.05%/lado y exactamente las mismas liquidaciones de funding de Binance USD-M, marcas faltantes y bandas temporales. **No son resultados reales Bitunix ni se traslada su funding de venue.** El menor coste no añade confirmaciones ni cambia el filtro de intensidad o la declaración NO TESTABLE.

ALL yQ90 aparecen completos, junto a4/24h y desarrollo/evaluación, como exploratorios. No se recogen sus mejores celdas como sustitutos deQ75. `cases.csv` selecciona mecánicamente primer caso neto positivo y negativo cronológico por celdaQ75 en evaluación, preservando todos los demás en los CSV completos; no se escogen ejemplos favorables del gráfico.

## 6. Entrega y decisión

Código nuevo solo bajo `phase1b_diagnostics/`; ningún archivo anterior cambia. Pruebas de identidad con/sin instrumentación, causalidad temporal, censura, asociación de tokens, costes/funding, separación de mercados y guardas de fuente. ZIP incluye código, datos públicos originales, ambos fixtures, CSV, configuraciones y hashes; instrucciones para reproducir sin Railway ni cuentas.

**Diagnóstico logrado; no habilita aún una prueba de gestión ni automatización.** El detector representa una coincidencia estricta2+2, no todo giro visible. El ejemplo15nov se pierde por una condición concreta comprobada; eso no prueba una regla alternativa rentable. PR50 conserva NO TESTABLE. No TP1, BE, trailing, órdenes, merge, deploy ni cambios productivos.

**SHADOW ONLY. TRADE AUTHORITY: NONE.**
'''
    (HERE/'REPORT.md').write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps(dict(evaluation_counts=totals,november_rows=len(nov),power_rows=len(power))))


if __name__=='__main__':generate()
