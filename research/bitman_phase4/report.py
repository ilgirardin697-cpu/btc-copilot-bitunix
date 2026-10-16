"""Render frozen artifacts; never selects or changes a candidate."""
import json
from pathlib import Path
from .spec import BASE_SHA,VERSION,CUTOFF
from .telegram import render

ART=Path(__file__).parent/'artifacts'


def pct(x):return 'NA' if x is None else f'{x*100:+.2f}%'
def num(x):return 'NA' if x is None else f'{x:.3f}'
def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows]


def samples(classification):
    base=dict(timeframe='4H',family='C4_K_SEPARATION',research_classification=classification,
        ao=141.,ao_slope=24.,anchor='ZERO_CROSS',anchor_age=2,adx=24.1,adx_slope=.7,
        di_plus=27.2,di_minus=16.4,bbwp=55.,bbwp_slope=3.,
        konkorde='KONKORDE_PROXY: dentro de montaña positiva; separación aumentando')
    output={state:render(dict(base,state=state,reasons=reason)) for state,reason in (
        ('LONG',['Hipótesis LONG: ancla AO alcista seguida por giro ADX; +DI apoya.',
                 'BBWP aumenta; separación Konkorde positiva en expansión.']),
        ('SHORT',['Hipótesis SHORT independiente: AO negativo empeora; ADX gira; -DI apoya.',
                  'No se invierte la geometría inside LONG.']),
        ('FORMING',['AO ha cruzado cero; aún falta giro posterior ADX/confirmación DI.']),
        ('WAIT',['No existe una secuencia completa nueva en velas cerradas.']),
        ('BLOCKED',['Datos insuficientes/no verificados; no emitir nueva observación.']))}
    output['SHORT']=render(dict(base,state='SHORT',family='C2_K_CONTEXT',ao=-141.,ao_slope=-24.,
        di_plus=16.4,di_minus=27.2,konkorde='KONKORDE_PROXY: EXIT reciente; fuera y montaña decreciente',
        reasons=['Hipótesis SHORT independiente: AO negativo empeora; ADX gira; -DI apoya.',
                 'No se invierte la geometría inside LONG.']))
    return output


def build():
    r=json.loads((ART/'results.json').read_text());lock=json.loads((ART/'selection_lock.json').read_text())
    msg=samples(r['classification']);(ART/'telegram_samples.json').write_text(json.dumps(msg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    lines=['# BITMAN REAL — PHASE4: DIRECTIONAL CONFLUENCE','',f"**Resultado: {r['classification']}. Evidencia C; no recomendar Telegram automático con estas reglas.**",'',
        'PR23 permanece **INCONCLUSIVE** e inmutable. Este resultado corresponde exclusivamente a las familias '
        'públicas/proxy aquí preregistradas; no rechaza la metodología completa ni demuestra paridad privada.',
        '',f'Base exacta: `{BASE_SHA}`. Versión: `{VERSION}`. Cutoff: `{CUTOFF}`.',
        'Histórico público Binance USD-M perpetual: 61,723 velas 1H completas desde octubre2019 (warmup), '
        '7,440 registros históricos de settlement funding. Datos verificados por checksum heredado. '
        '1H/4H señales, 1D contexto causal; ningún 15m/5m/1m. No son datos privados Bitunix.',
        '', '**FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR**. '
        'No hay validación forward, uso de PnL del usuario ni reconstrucción de eventos de producción.',
        '', '## Lectura práctica','',
        'El caso LONG4H con separación Konkorde creciente registra TEST +59.80%, PF1.680, Sharpe0.928 '
        'y DD−25.07%, pero solo53 trades. Sin sus mejores3: −8.32% compuesto, expectancy−0.085%/trade. '
        'IC95 semanal de expectancy: −0.583% a +2.685%. Exceso de evento24h contra control: −0.288 puntos '
        'porcentuales (57 pares); no aporta ventaja de evento demostrada. Ninguno de sus vecinos es un nuevo ganador seleccionado.',
        '', 'En TEST quitar Konkorde a ese caso baja el retorno de59.80% a29.27%; quitar ADX/DI lo baja a32.19%, '
        'quitar BBWP a35.08%, quitar AO a53.12%. Es evidencia descriptiva incremental en este intervalo, '
        '**insuficiente**: el incremento frente C0 no fue positivo en ambos DEV y el resultado depende de pocos ganadores. '
        'El benchmark V8 conserva +66.55%, Sharpe0.732, DD−32.01%; no se ha demostrado sustitución superior.',
        '', '2026 del padre LONG4H: +17.41%, PF2.037,13 trades; muy pocos casos. '
        'No se optimizó para 2026. Los SHORT diagnósticos1H/4H registran −41.90%/−16.92% en TEST. '
        'El LONG1H registra −9.85%. No existe una justificación para activar SHORT ni promocionar toda la confluencia.',
        '', '## Evidencia nueva y protocolo','',
        '[SOURCES.md](SOURCES.md) separa las cuatro transcripciones primarias de las decisiones numéricas del experimento. '
        'Se realizaron cuatro llamadas vidIQ (5 créditos nominales cada una, máximo autorizado20); cargo efectivo no devuelto. '
        'No se publican las transcripciones completas ni se afirma haber verificado visualmente sus gráficos.',
        '', 'Protocolo y código congelados **antes** de DEV/TEST; selección de eventos bloqueada antes del chequeo neto. '
        'TRAIN2020–2021; VALIDATION2022–2023; TEST2024–cutoff **OOS reutilizado, no virgin**. '
        'Ninguna familia resultó elegible en TRAIN/VALIDATION. Los cuatro casos siguientes son fallbacks '
        'diagnósticos deterministas, **no ganadores ni candidatos promocionables**. No se hizo reranking tras ver el neto.',
        '', '### Reglas exactas','',
        'Ancla AO5/34: cruce de cero o reanudación dentro del mismo signo tras reinicio genuino de pendiente. '
        'LONG: cruce `prev<=0, now>0` o pendiente `prev<=0, now>0` con AO positivo continuo. '
        'SHORT: cruce `prev>=0, now<0` o pendiente `prev>=0, now<0` con AO negativo continuo. '
        'Después del ancla, ADX14 debe girar de pendiente no positiva a positiva entre edades0..6 velas TF. '
        'DI puede alinearse posteriormente dentro de esa ventana mientras ADX sube. Al disparar, AO debe conservar '
        'signo y mejorar en esa dirección. Ancla consumida una vez antes de los filtros BBWP/K; sin señal en cada vela.',
        '', *table(['Familia','LONG','SHORT'],[
            ('C0_IMPULSE','Secuencia AO→ADX/+DI y BBWP creciente','Secuencia AO→ADX/-DI y BBWP creciente'),
            ('C1_BBWP50','C0 + BBWP>=50','C0 + BBWP>=50'),
            ('C2_K_CONTEXT','C0 + montaña positiva/MA dentro','C0 + EXIT reciente<=6, fuera y montaña decreciente'),
            ('C3_K_TRANSITION','C0 + ENTRY reciente<=6, montaña positiva/dentro','C0 + EXIT en la misma vela cerrada'),
            ('C4_K_SEPARATION','C0 + dentro de montaña positiva, separación creciente','NO IMPLEMENTADO: geometría no justificada'),
            ('C5_K_REENTRY','C0 + REENTRY reciente<=6, salida/entrada<=3 velas','NO IMPLEMENTADO: geometría no justificada')]),
        '', 'BBWP es el proxy congelado CLOSE/SMA7/prior100; no paridad demostrada con la volatilidad privada del vídeo. '
        '50 es la única referencia candidata explícita; vecinos40/60 son diagnóstico, no selección. '
        'Las ventanas6/3 son hipótesis de implementación declaradas, no constantes reveladas por Bitman.',
        '', 'KONKORDE_PROXY no cambia: OHLC4; WilderRSI14; HLC3-MFI14; BB25/SMA/std poblacional; '
        'stochastic21/SMA3; montaña=(RSI+MFI+BollOsc+Stoch/3)/2; mediaEMA15; dentro estrictamente entre cero y montaña. '
        'ENTRY fuera→dentro; EXIT dentro→fuera. Fórmula/provenance completa: [PR23](../bitman_real/SOURCES.md). '
        '**EXACT BITMAN KONKORDE PARITY: NOT PROVEN**. RSI privado excluido; Trend Speed NOT IMPLEMENTED / FORMULA NOT VERIFIED.',
        '', 'Selección porTF/lado: >=30 eventos24h emparejados tanto TRAIN como VALIDATION; media direccional y exceso '
        'contra control positivos ambos. Ranking por peor exceso de ambos periodos, luego n y nombre. '
        'Control determinista no-evento emparejado por año/mes/horaUTC y signo de tendencia24 velasTF; '
        'sin elegir retornos futuros, excluyendo unión de eventos candidatos. No reemplaza un ensayo aleatorio; '
        'hay solapamiento/selección múltiple y reutilización OOS. IC bootstrap semanal500, seed6241, descriptivos.',
        '', '## Estudio de eventos (antes de gestionar salidas)','',
        'Cada celda: n eventos / media direccional24h / exceso24h contra control. Brutos de mercado, '
        'sin costes; no son rentabilidad de estrategia. Horizonte incompleto censurado. SHORT reflejado correctamente.',
        '',*table(['TF/lado/familia','TRAIN','VALIDATION','TEST'],[
            (key+'/'+fam,*[f"{s[p]['n_events']} / {pct(s[p]['directional24h_mean'])} / {pct(s[p]['matched24h']['mean'])}" for p in ('TRAIN','VALIDATION','TEST')])
            for key,families in r['events'].items() for fam,s in families.items()]),
        '', '### Selecciones diagnósticas congeladas: horizontes TEST','',
        *table(['Caso','h','n maduro/total','retorno medio','mediana','MFE mediana','MAE mediana','+1 antes -1','+2 antes -2'],[
            (key,h,f"{d['n_complete']}/{d['n_total']}",pct(d.get('forward_return',{}).get('mean')),pct(d.get('forward_return',{}).get('median')),
             pct(d.get('mfe',{}).get('median')),pct(d.get('mae',{}).get('median')),
             pct(d.get('race_1pct',{}).get('UP_FIRST')),pct(d.get('race_2pct',{}).get('UP_FIRST')))
            for key,v in r['selected'].items() for h,d in r['events'][key][v['parameters']['family']]['TEST']['directional_horizons'].items()]),
        '', 'Ambas barreras tocadas dentro de una misma vela1H = AMBIGUOUS, nunca victoria. '
        'UP_FIRST se divide por todos los casos maduros, incluidos no resueltos/ambiguos. '
        'Los JSON conservan también horas/alcances individuales, datos BTC sin reflejar y dirección reflejada.',
        '', '### Referencias de eventos TEST','',
        *table(['Caso/control','n','media24h','exceso24h','IC95 exceso'],[
            (key+'/'+name,s['TEST']['n_events'],pct(s['TEST']['directional24h_mean']),pct(s['TEST']['matched24h']['mean']),
             ' / '.join(pct(x) for x in s['TEST']['matched24h']['ci95'])) for key,controls in r['event_comparators'].items() for name,s in controls.items()]),
        '', '## Simulación neta de las selecciones congeladas','',
        'Libro académico1x nominal al abrir, cantidad fija; LONG/SHORT separados, no sumar curvas1x. '
        'Entrada en siguiente apertura TF después del cierre conocido, slippage adverso. '
        'Stop inicial2ATR14 del TF de señal, congelado; salida en apertura tras AO contrario confirmado o máximo168h. '
        'Stops/gaps comprobados en1H, prioridad conservadora; no TP ni pirámides. Cierre forzado al final de cada split. '
        'Base: taker5bps/fill, slip2bps, stopslip5bps. Stress:6/5/10bps. Funding histórico firmado sobre cantidad fija '
        'y precio de apertura1H proxy; holdings previos al settlement antes de entrada/salida de frontera. '
        'No simulación exacta de Bitunix, margen/liquidación ni basis entre venues. Insolvencia académica queda a cero y se declara.',
        '', 'PF = suma de retornos porcentuales positivos por trade / abs(suma negativos), '
        'no PF monetario ponderado por equity. CAGR/Sharpe/Sortino/DD usan equity horaria marcada a mercado '
        'y anualización365.25d. Expectancy/media de trade y retorno compuesto son cantidades distintas.',
        '',*table(['Caso/familia','Split','retorno','CAGR','Sharpe','Sortino','MaxDD','PF','n','expectancy','win','payoff'],[
            (key+'/'+v['parameters']['family'],period,pct(m['total_return']),pct(m['cagr']),num(m['sharpe']),num(m['sortino']),pct(m['max_dd']),num(m['profit_factor']),m['trades'],pct(m['expectancy']),pct(m['win_rate']),num(m['payoff_ratio']))
            for key,v in r['selected'].items() for period,m in v['splits'].items()]),
        '', '### Benchmark común TEST','',
        *table(['Caso/control','retorno','Sharpe','MaxDD','PF','n','expectancy'],[
            (key+'/'+name,pct(m['total_return']),num(m['sharpe']),pct(m['max_dd']),num(m['profit_factor']),m['trades'],pct(m['expectancy']))
            for key,controls in r['comparators'].items() for name,splits in controls.items() for m in [splits['TEST']]]),
        '', 'AO_ADX: primer estado AO con signo, ADX creciente, DI alineado. EMA_TREND: cruceEMA10/55. '
        'AO_ONLY: anclas AO. KONKORDE_ENTRY: entrada con salida común AO/stop/168h; '
        'KONKORDE_NATIVE: ENTRY/EXIT propios, mismo stop2ATR/168h. Ambos LONG exclusivamente; '
        'no se inventa SHORT aislado. V8: último4H cerrado close>SMA200 LONG/FLAT, sin stopATR/168h, mismos costes/funding. '
        'V81H/4H debe ser idéntico (comprobación de benchmark).',
        '', '## Aportación incremental / ablation TEST','',
        'Eliminar AO suprime ancla/signo y usa giroADX+DI. Eliminar ADX_DI usa anclasAO sin ese filtro. '
        'Eliminar BBWP suprime subida y referencia50; eliminarK solo la geometríaK. '
        'Salidas idénticas. QuitarK a C0/C1 es **no-op**, no evidencia independiente.',
        '',*table(['Caso/ablación','n','retorno','Sharpe','PF','expectancy'],[
            (key+'/sin '+name,m['trades'],pct(m['total_return']),num(m['sharpe']),num(m['profit_factor']),pct(m['expectancy']))
            for key,v in r['selected'].items() for name,m in v['ablation'].items()]),
        '', '## Robustez: vecinos, concentración, costes','',
        'Vecinos son diagnóstico de padres congelados, nunca se elige un nuevo ganador con TEST. '
        'Máscaras idénticas se deduplican y no cuentan como validaciones independientes. '
        '**Muestra pequeña:** LONG4H tiene53 trades y SHORT4H21; no se promocionan subgrupos pequeños.',
        '',*table(['Caso/vecino','n','expectancy','retorno','MaxDD'],[
            (key+'/'+(str(n['parameters']) if 'parameters' in n else 'stopATR='+str(n['stop_atr'])),n['metrics']['trades'],pct(n['metrics']['expectancy']),pct(n['metrics']['total_return']),pct(n['metrics']['max_dd']))
            for key,v in r['selected'].items() for n in v['neighbors']]),
        '',*table(['Caso','duplicados excluidos','sin mejor: exp/ret','sin mejores3: exp/ret','IC95 expectancy','stress exp/ret','trail3ATR exp/ret'],[
            (key,len(v['duplicate_neighbors']),pct(v['without_best']['expectancy'])+' / '+pct(v['without_best']['total_return']),
             pct(v['without_best3']['expectancy'])+' / '+pct(v['without_best3']['total_return']),
             ' / '.join(pct(x) for x in v['bootstrap']['ci95']),pct(v['stress']['expectancy'])+' / '+pct(v['stress']['total_return']),
             pct(v['alternate_trailing']['expectancy'])+' / '+pct(v['alternate_trailing']['total_return'])) for key,v in r['selected'].items()]),
        '', 'Quitar trades anula sus intervalos originales, sin volver a entrar oportunistamente. '
        'El trail3ATR alternativo usa ATR de entrada congelado y se actualiza después del cierre1H para la siguiente vela; '
        'diagnóstico no seleccionado y no rescata el modelo primario.',
        '',*table(['Caso','fee/fill bps','retorno','expectancy','fees equity inicial','slippage','funding firmado','turnover'],[
            (key,fee,pct(m['total_return']),pct(m['expectancy']),num(m['fees']),num(m['slippage']),num(m['funding']),num(m['turnover']))
            for key,v in r['selected'].items() for fee,m in v['costs'].items()]),
        '', '### Año por año, incluido2026 (padres globales congelados)','',
        *table(['Caso','Año','n','retorno','Sharpe','MaxDD','PF','expectancy'],[
            (key,year,m['trades'],pct(m['total_return']),num(m['sharpe']),pct(m['max_dd']),num(m['profit_factor']),pct(m['expectancy']))
            for key,v in r['selected'].items() for year,m in v['yearly'].items()]),
        '', '### Walk-forward anual separado','',
        'Cada fold selecciona usando únicamente pasado: TRAIN anclado2020..año-2; VALIDATIONaño-1. '
        'La elegibilidad neta DEV no provoca reranking. Los folds pueden incorporar años antes usados como OOS '
        'cuando ya son pasado; no cambian la selección global TEST. No desplegar los fallbacks no elegibles.',
        '',*table(['Año','Caso','Familia','DEV elegible','n','retorno','Sharpe','MaxDD','expectancy'],[
            (year,key,v['selected']['family'],v['strategy_eligible'],v['metrics']['trades'],pct(v['metrics']['total_return']),num(v['metrics']['sharpe']),pct(v['metrics']['max_dd']),pct(v['metrics']['expectancy']))
            for year,fold in r['walk_forward'].items() for key,v in fold.items()]),
        '', '### Regímenes de operaciones TEST','',
        'BULL/BEAR: último4H cerrado contraSMA200; RANGE:ADX<20, solo descriptivo. '
        'HIGH/LOW_VOL: mediana TRAIN del ATR/precioTF; no cuantiles elegidos para rentabilidad. '
        'Alineación1D usa su SMA200 cerrada; warmup desconocido no se trata como BEAR.',
        '',*table(['Caso/cohorte','n','expectancy','win'],[
            (key+'/'+tag,c['n'],pct(c['expectancy']),pct(c['win_rate'])) for key,v in r['selected'].items() for tag,c in v['cohorts'].items()]),
        '', '### Cercanía a cero, separación y divergencias (eventos TEST24h)','',
        'Los límites LOW/MID/HIGH son los terciles TRAIN **heredados de PR23**, sin ajustarlos. '
        'No son umbrales de entrada. Divergencias AO se detectan con pivots estrictos2izquierda/2derecha '
        'y solo aparecen en la vela de confirmación. Se registran como contexto, no familias elegibles.',
        '',*table(['Caso/cohorte','n','media','mediana'],[
            (key+'/'+tag,c['n'],pct(c['mean']),pct(c['median'])) for key,v in r['selected'].items()
            for tag,c in r['events'][key][v['parameters']['family']]['TEST']['descriptive_cohorts24h'].items()]),
        '', '## Gates y decisión','',
        *table(['Caso','Clasificación','Gates fallidos'],[(key,v['classification'],', '.join(k for k,ok in v['gates'].items() if not ok)) for key,v in r['selected'].items()]),
        '', 'PROMISING FOR SHADOW requería elegibilidadDEV, expectancyTEST positiva,PF>1.20,Sharpe>0.75,DD<25%,n>=100, '
        '>=75% vecinos positivos,stress positivo,sin mejores3 positivo,>=2 añosTEST positivos,ventaja contra control, '
        '>=3 folds positivos y ventaja frente AO_ADX; una familiaK debía mejorar el exceso de C0 en ambos DEV. '
        'Ninguna supera todo. Una submuestra rentable no justifica cambiar la clasificación ni limpiar sistemas existentes.',
        '', '## Telegram preparado, sin envío ni integración','',
        'Ejemplos **sintéticos**, no señales históricas ni permiso de entrada. A requiere forward independiente '
        'no disponible; B solo si todos los gates históricos se superan; C en el resultado actual. '
        'El grade no es probabilidad ni controla sizing. Renderer puro sin token, transporte ni poller. '
        'No se inicia ningún observer ni se cambia dedupe/Telegram de producción.',
        *sum(([f'### {state} (fixture)','', '```text',text,'```',''] for state,text in msg.items()),[]),
        '## Reproducción y validación','',
        'Ver [README.md](README.md), [validation.json](artifacts/validation.json) y '
        '[safety_audit.json](artifacts/safety_audit.json). Datos grandes fuera de Git. '
        'Artefactos: protocolo/hash, manifiesto, locksDEV, resultados, eventos/outcomes comprimidos y trades netos. '
        'Reejecución determinista compara JSON descomprimidos, no cabeceras gzip con timestamps.',
        '', '**V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI UNCHANGED. '
        'MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.**',
        '', '**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDERS. NO production Telegram changes.**']
    (Path(__file__).parent/'PHASE4_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':build()
