"""Present fixed directional evidence; no parameter or rule selection."""
import copy
import json
from pathlib import Path
from .spec import VERSION,BASE_SHA,CUTOFF,HORIZONS,PRIMARY_HORIZON
from .study import ART,write
from .core import decide
from .telegram import render


def pct(x):return 'NA' if x is None else f'{x*100:+.3f}%'
def rate(x):return 'NA' if x is None else f'{x*100:.2f}%'
def num(x):return 'NA' if x is None else f'{x:.2f}'
def table(headers,rows):return ['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows]
def val(d,key,stat='mean'):return d.get(key,{}).get(stat)


def samples():
    def part(side):
        sign=1 if side=='UP' else -1
        return dict(bias=side,ao_bias=side,ao=150.*sign,ao_slope=25.*sign,ao_acceleration=5.*sign,
            momentum='BULLISH_MOMENTUM' if sign==1 else 'BEARISH_MOMENTUM',ao_zero_motion='AWAY_FROM_ZERO',
            ao_cross_up=sign==1,ao_cross_down=sign==-1,di_direction='BULLISH' if sign==1 else 'BEARISH',
            di_plus=28. if sign==1 else 15.,di_minus=15. if sign==1 else 28.,adx=24.,adx_slope=.8,adx_acceleration=.2,
            adx_turn_up=True,bbwp=56.,bbwp_slope=3.,bbwp_distance50=6.,separation=4.,separation_change=1.,
            distance_to_zero=40.,konkorde='KONKORDE_BULLISH_INSIDE' if sign==1 else 'KONKORDE_BEARISH_CONTEXT',last_closed_at=1792022400000)
    outputs={}
    for label,d,h,q in (('UP','UP','UP','UP'),('DOWN','DOWN','DOWN','DOWN'),
        ('TRANSITION','DOWN','UP','UP'),('UNCLEAR','UP','DOWN','UNCLEAR'),('CONFLICT','UP','DOWN','UP')):
        parts={'1D':part(d),'4H':part(h),'1H':part(q)}
        if q=='UNCLEAR':
            for p in parts.values():p.update(momentum='MIXED',di_direction='NEUTRAL',ao=0.,ao_slope=0.,ao_acceleration=0.,
                ao_bias='NEUTRAL',bias='NEUTRAL',di_plus=20.,di_minus=20.,ao_cross_up=False,ao_cross_down=False,ao_zero_motion='STABLE')
        parts['1D']['adx_slope']=-.1  # synthetic BUILDING, not an assertion of STRONG evidence
        parts['1D']['adx_turn_up']=False
        structure=dict(nearest_support=80000.,nearest_resistance=86000.,support_distance_pct=-.02439,resistance_distance_pct=.04878,
            support_distance_atr=1.,resistance_distance_atr=2.,state='BETWEEN_LEVELS',opposing_up=False,opposing_down=False,scales={})
        ml={tf:dict(color='GREEN' if parts[tf]['bias']=='UP' else 'RED') for tf in ('1H','4H')}
        s=dict(version=VERSION,timestamp=1792022400000,reference_price=82000.,venue='BINANCE PUBLIC / SYNTHETIC FIXTURE',components=parts,confirmed_mlrsi=ml,structure=structure,**decide(parts,structure,ml))
        # UNCLEAR remains unassigned; all other labels derived by hierarchy, not a rendered trade request.
        outputs[label]=render(s)
    return outputs


def build():
    r=json.loads((ART/'results.json').read_text());canonical=json.loads((ART/'canonical_control_reporting.json').read_text())['canonical']
    timing=json.loads((ART/'timing_diagnostics.json').read_text());messages=samples();write(ART/'telegram_samples.json',messages)
    main=r['splits']['MTF'];rows=[]
    for period,states in main.items():
        for state,s in states.items():
            h=s['horizons']['72'];c=canonical['MTF'][period][state]['72'];kind='signed_lean_excess' if h['n_directional'] else 'raw_btc_excess';m=c[kind]
            rows.append((period,state,h['n_complete'],h['n_incomplete'],h['n_directional'],rate(h.get('directional_accuracy')),
                pct(val(h,'signed_return')),pct(val(h,'signed_return','median')),pct(h.get('raw_return_mean')),pct(m['mean']),
                ' / '.join(pct(x) for x in m['ci95'])))
    lines=['# I-GOD BITMAN BTC DIRECTION ENGINE v0.1','',f"**{r['classification']}**",'',
        'Esta investigación pregunta si BTC se desplaza después en la dirección anunciada; no prueba entradas/salidas '
        'ni maximiza PnL. No ha demostrado utilidad incremental suficientemente robusta. No recomendar Telegram '
        'de producción ni sustituir/silenciar V8 con este resultado.',
        '',f'Base: `{BASE_SHA}`; cutoff `{CUTOFF}`; versión `{VERSION}`.',
        'Phase2=REJECT; BITMAN REALv0.1=INCONCLUSIVE; Phase4=INCONCLUSIVE: todos intactos. '
        'Esto no pretende reparar esos resultados ni replicar toda la metodología privada de Bitman.',
        '', '## Respuesta práctica','',
        'TEST72h, núcleo público MTF: **UP n702, acierto50,85%, media firmada+0,591%, mediana+0,093%**. '
        'Exceso contra control−0,122pp, IC95[−0,920,+0,626]pp. '
        '**DOWN n697, acierto44,76%, media+0,009%, mediana−0,377%**; exceso+0,086pp, '
        'IC95[−0,643,+0,773]pp. No ventaja robusta. Muchos outcomes se solapan; n no es número de apuestas independientes.',
        '', 'Sin los mejores3 retornos72h: UP media+0,509% pero exceso−0,182pp; DOWN media−0,048% '
        'con exceso+0,035pp. No se rearman episodios para rellenar observaciones retiradas. '
        'No se interpretan medias brutas como dinero ganado ni como razón para entrar.',
        '', '**ML RSI confirmado: PENDING_ACTUAL_CONFIRMED_EXPORT.** No se recomputó el port ni se sustituyó '
        'por RSI clásico/research. El observer actual produce15m/1H/4H, no1D;15m no participa y1DML permaneceUNKNOWN. '
        'Por ello el histórico mide el **núcleo público sin confirmación ML real**, no una validación del motor completo.',
        '', 'Ruido histórico: **5,14 cambios de estado/día;7,89 firmas materiales/día**, frente0,164 de V8LONG/FLAT. '
        'El99,92% de las horas UP coinciden con V8LONG. No se demuestra información temporal distinta que justifique '
        'hacer visible este prototipo. No se cambia dedupe/reglas después de ver estos resultados.',
        '', '## Provenance / datos / metodología','',
        '[SOURCES.md](SOURCES.md) reutiliza las cuatro transcripciones vidIQ de Phase4, con hashes originales. '
        '**Cero llamadas/cargos nuevos vidIQ**. Los vídeos fundamentan conceptos, no constantes privadas, '
        'la jerarquía exacta ni un porcentaje de aciertos. KONKORDE_PROXY público; '
        '**EXACT BITMAN KONKORDE PARITY: NOT PROVEN**. RSI privado adaptado y Trend Speed no se inventan.',
        '', 'Binance USD-M perpetual público,61.723 velas1H completas con warmup2019-10, '
        'mismo checksum/manifiesto que el estudio previo.1D/4H agregados completos UTC, sin interpolación. '
        'MLcache existente es BinanceSPOT: diferencia de venue explícita. No acceso privado Bitunix/volúmenesRailway.',
        '', 'TRAIN2020–21; VALIDATION2022–23; TEST2024–cutoff, **reused OOS, NOT virgin**. '
        'Protocolo/código/calibración de controles congelados antes del análisis. No candidatos optimizados ni '
        'reglas seleccionadas por TEST. Cuartiles ATR1H/precio TRAIN sirven solo para matching. '
        'Walk-forward2022–26 mantiene reglas y usa calibración de matching previa a cada año.',
        '', '## Definiciones exactas y jerarquía','',
        *table(['Bloque','Función / definición'],[
            ('AO','SMA5(HL2)−SMA34(HL2). Contexto de signo; momentum requiere2 pendientes consecutivas del mismo signo O cruce de cero cerrado. Valor, pendiente, aceleración y acercamiento/alejamiento de cero visibles.'),
            ('ADX/DI','Wilder14/14. ADX_TURN_UP: pendiente previa<=0, actual>0. ACCELERATING: pendiente>0 y segunda diferencia>0. DI confirma sentido. ADX no asigna UP/DOWN.'),
            ('Koncorde','Proxy PR23 sin cambios. ENTRY/INSIDE positivos, EXIT, REENTRY<=3TFbars, contexto bajista PROXY. Distancia cero/separación continuas. EXIT no significa SHORT.'),
            ('ML RSI','Solo color confirmado de cache/export validadoLOW29/EMA4/PINE_PARITY_V4. Sin aproximación, provisional ni approaching. Lectura<=90s, vela cerrada válida. Opuesto4H conocido=>CONFLICT; ausente=>UNKNOWN.'),
            ('BBWP','CLOSE/SMA7/prior100. Percentil/subida/bajada/aceleración,cruce50 y distancia50; no puertas45/47/52 ni zonas optimizadas.'),
            ('Niveles','Helper puro Copilot2L/2R; ventana220TFbars, timestamps de confirmación, 1H/4H/1D independientes. Día/semanaUTCprevios completos. No modificar Copilot.'),
            ('1D MACRO_BIAS','UP siAO>0 y+DI>−DI; DOWN siAO<0 y−DI>+DI; TRANSITION si desacuerdo; NEUTRAL si empate; UNKNOWN sin datos.'),
            ('4H SWING_BIAS','Misma definición de contexto, confirma/contradice al diario; no voto equivalente.'),
            ('1H TIMING_STATE','Impulso sostenido AO/cero conDIcorrespondiente: impulse_up/down; desacuerdo:transition; resto:no_impulse. Contra contextoD/4H alineado=>pullback, no giro macro.')]),
        '', *table(['Estado principal','Regla / detalle conservado'],[
            ('UP','1DUP y4HUP. 1HUP=>UP_CONFIRMED;1HDOWN=>UP_WITH_1H_PULLBACK. No se invierte macro por una vela.'),
            ('DOWN','1DDOWN y4HDOWN. 1HDOWN=>DOWN_CONFIRMED;1HUP=>DOWN_WITH_1H_PULLBACK.'),
            ('TRANSITION','4H contradice macro y1H apoya al swing nuevo=>POSSIBLE_BULLISH/BEARISH_TRANSITION. Transición parcial con impulso1H=>EARLY_TRANSITION con lean explícito.'),
            ('UNCLEAR','Falta macro/swing verificable o no hay jerarquía confirmada. No se asigna artificialmente sentido.'),
            ('CONFLICT','Macro/swing opuestos sin timing que apoye transición, o prueba cerrada fallida de nivel mayor opuesto, oML4Hconfirmado opuesto. No es una orden.')]),
        '', 'Un test estructural requiere nivel4H/1D **ya conocido al cierre1H anterior**, rango1H tocándolo '
        'y cierre del lado original. Ningún live mark crea pivots/autoridad; un nivel cruzado por1H mientras4H/1D '
        'no ha cerrado conserva su tipo y muestra confirmación pendiente. No se usa distancia rentable optimizada.',
        '', 'STRONG: contexto1D/4Halineado yADX+BBWPsubiendo enambos. BUILDING: presión direccional con4HADX+BBWP '
        'subiendo, o impulso1Halineado congiroADX1H+BBWPsubiendo. RestoWEAK. '
        'GradeA: UP/DOWN alineado,STRONG y confirmaciónML4Hapoyando; B:direcciónUP/DOWN restante; C:transición/unclear/conflict. '
        'Es **coherencia visual**, no evidence grade estadístico, probabilidad, sizing ni permiso de entrada.',
        '', '## Episodios / métricas','',
        'Una dirección continua=un episodio aunque cambie strength/timing. Evento nuevo solo al cambiar estado. '
        'No evento artificial al empezar un split. TRANSITION conserva lean inicial cuando existe; UNCLEAR no tiene '
        'dirección y se describe en retorno BTCraw. CONFLICT puede conservar un lean para diagnóstico, nunca equivale aUP/DOWN.',
        '', 'Referencia=precio conocido al cierre; medir solo futuros1H completamente cerrados. LONGdir=futuro/ref−1; '
        'DOWNdir=1−futuro/ref. Acierto=retorno firmado>0 entre maduros, no tasa de trades ganadores. '
        'Sin entradas/salidas/fees/funding/margen: no se evalúa aquí rentabilidad de estrategia. '
        'MFE/MAE y barreras usan extremos OHLC cerrados; mismahoraambasbarreras=AMBIGUOUS, no éxito. '
        'No interpolar gaps; futuros/splits insuficientes permanecen incompletos.',
        '', 'Controles: hasta3 timestamps no-onset por año/mes/horaUTC, régimen4HSMA200 y cuartilvolatilidad. '
        'Misma madurez/split, selección por hash sin conocer outcomes. Bootstrap1000 bloques semanales,seed8192; '
        'solapamiento/multiplicidad/reutilizaciónTEST impiden afirmar prueba estadística definitiva.',
        '', '### Nota de agregación descriptiva','',
        'El artefacto primario se conserva. Para estados con mezcla de lean0 y±1, su campo matched agregado mezcla '
        'retorno BTCraw y retorno firmado y **no debe usarse como evidencia direccional**. '
        '[canonical_control_reporting.json](artifacts/canonical_control_reporting.json) separa ambos desde los mismos '
        'registros inmutables. Es una corrección de presentación, sin cambiar señales, outcomes, resultados primariosUP/DOWN '
        'ni clasificación. Las tablas siguientes usan controles lean solo en el subgrupo firmado; paraUNCLEAR usan raw.',
        '', '## MTF TRAIN / VALIDATION / TEST,72h','',
        *table(['Split','Estado','maduros','pendientes','con lean','acierto','media firmada','mediana firmada','media BTCraw','exceso control','IC95 exceso'],rows),
        '', '### Todos los horizontes MTF en TEST','',
        *table(['Estado','h','n maduros/total','acierto','media firmada','mediana','MFE mediana','MAE mediana'],[
            (state,h,f"{x['n_complete']}/{x['n_total']}",rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(val(x,'signed_return','median')),pct(val(x,'mfe','median')),pct(val(x,'mae','median')))
            for state,s in main['TEST'].items() for h,x in s['horizons'].items()]),
        '', '## Contexto1D / swing4H / timing1H: endpoints propios','',
        *table(['TF','Split','Estado','h','n maduros/total','acierto','media firmada','mediana','MFE mediana','MAE mediana'],[
            (tf,period,state,h,f"{x['n_complete']}/{x['n_total']}",rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(val(x,'signed_return','median')),pct(val(x,'mfe','median')),pct(val(x,'mae','median')))
            for tf in ('1H','4H','1D') for period,states in r['splits'][tf].items() for state,s in states.items() if state in ('UP','DOWN')
            for h,x in s['horizons'].items() if period=='TEST' or int(h)==PRIMARY_HORIZON[tf]]),
        '', 'Muestras diarias pequeñas (TEST30UP/29DOWN); no promoción ni conclusiones fuertes de subgrupos pequeños. '
        'Los JSON conservan todos los estados/horizontes y las dos versiones de controles.',
        '', '## DIRECTIONAL_10PCT_EXTENSION —2/5/10%, no take profit','',
        *table(['Estado','h','objetivo','n','toca favorable','toca adverso','favorable antes adverso','ambiguo','no resuelto','horas mediana si toca','adverso previo seguro','adverso incl.hora toque'],[
            (state,h,k+'%',x['n'],rate(x['favorable_hit_rate']),rate(x['adverse_hit_rate']),rate(x['race']['FAVORABLE_FIRST']),rate(x['race']['AMBIGUOUS']),rate(x['race']['UNRESOLVED']),num(x['median_hour_to_target']),pct(x['median_adverse_before_touch']),pct(x['median_adverse_including_touch_bar']))
            for state in ('UP','DOWN') for h in ('24','72','168','336') for k,x in main['TEST'][state]['horizons'][h].get('targets',{}).items()]),
        '', 'Tocar+10% en algún momento no equivale a cerrar+10%, hacerlo antes de−10%, hacerlo antes de un '
        'stop pequeño ni capturarlo en una operación. Adverso anterior al target se da como intervalo: '
        'solo barras anteriores son seguras; la hora del toque puede incluir una excursión de orden desconocido. '
        'El tracker runtime usa únicamente barras ya observadas. **NOT A GUARANTEE.**',
        '', '### Fuerza al inicio del episodio: extensión y retorno72h','',
        *table(['Strength','Lado','n','acierto','media','10% observado','adverso10%','MFE mediana','MAE mediana'],[
            (strength,state,x['n_directional'],rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),rate(x.get('targets',{}).get('10',{}).get('favorable_hit_rate')),rate(x.get('targets',{}).get('10',{}).get('adverse_hit_rate')),pct(val(x,'mfe','median')),pct(val(x,'mae','median')))
            for strength in ('WEAK','BUILDING','STRONG') for state,s in r['cohorts'][strength].items() for x in [s['horizons']['72']]]),
        '', '## Persistencia y false reversal','',
        'False reversal evaluativo: nuevo episodio direccional precedido por sentido opuesto y posterior vuelta al '
        'anterior dentro de3velasTF(1H3h/4H12h/1D72h; MTF24h). Etiqueta futura separada, nunca entrada del motor. '
        'Borde derecho censurado; no es tasa de trades perdedores ni prueba de giro estructural verdadero.',
        '',*table(['Stream','Estado','episodios','persistencia mediana horas','n evaluable reversal','false reversal'],[
            (name,state,s['n_episodes'],num(s['median_persistence_hours']),s['false_reversal_n'],rate(s['false_reversal_rate']))
            for name in ('1H','4H','1D','MTF') for state,s in r['splits'][name]['TEST'].items() if state in ('UP','DOWN')]),
        '', '### Pullback vs transición: diagnóstico temporal suplementario','',
        'Los cohorts primarios conservan el detalle al INICIO del episodio. Para no confundir eso con todos los '
        'pullbacks, [timing_diagnostics.json](artifacts/timing_diagnostics.json) mide además entradas en etiquetas '
        'de timing ya congeladas dentro de episodios. Son observaciones anidadas/solapadas, no nuevos episodios '
        'UP/DOWN, y no cambian reglas, selección o clasificación. Análisis descriptivo suplementario posterior '
        'a la evaluación primaria; no se usa para elegir una regla rentable.',
        '',*table(['Etiqueta','h','n','acierto según lean','media firmada','mediana','MFE mediana','MAE mediana'],[
            (tag,h,x['n_complete'],rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(val(x,'signed_return','median')),pct(val(x,'mfe','median')),pct(val(x,'mae','median')))
            for tag,s in timing['periods']['TEST'].items() for h,x in s['horizons'].items()]),
        '',*table(['Etiqueta','n maduros72h','impulso1H alineado en72h','horas mediana','macro cambia lado en72h'],[
            (tag,s['mature_72h_for_timing'],rate(s['aligned_hourly_impulse_within72h']),num(s['median_hours_to_aligned_impulse']),rate(s['macro_flip_within72h'])) for tag,s in timing['periods']['TEST'].items()]),
        '', 'El engine distingue semánticamente pullback de transición, pero estas etiquetas no garantizan '
        'continuación ni giro posterior. No ajustar sus definiciones para mejorar estas distribuciones.',
        '', '## Ablation informacional, sin estrategia ganadora','',
        'AO_ONLY yAO_DI recomputan jerarquía; ADX/BBWP/K son subgrupos condicionados de los mismos onsetsAO_DI, '
        'con los mismos controles originales. No son backtests ni se elige la fila de mayor retorno. '
        'ADX yBBWP no tienen autoridad para dar sentido contrario. El contextoK bajista es proxy, no EXIT=SHORT. '
        'La cadena+MLconfirmed está PENDING. La filaSTRUCTURE_NO_ML no pretende sustituir esa confirmación.',
        '',*table(['Split','Stage','Lado','n72h','acierto','media','exceso control'],[
            (period,name,state,x['n_directional'],rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(s['matched']['72']['mean']))
            for period,stages in r['ablation'].items() for name,states in stages.items() for state in ('UP','DOWN')
            for s in [states[state]] for x in [s['horizons']['72']]]),
        '',*table(['Jerarquía TEST','Lado','n72h','acierto','media','exceso'],[
            (name,state,x['n_directional'],rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(s['matched']['72']['mean']))
            for name in ('AO_ONLY','AO_DI','MTF','V8') for state,s in r['splits'][name]['TEST'].items() if state in ('UP','DOWN')
            for x in [s['horizons']['72']]]),
        '', 'Masks/no-ops idénticos no son replicaciones independientes. El contraste jerarquía vs subgrupo '
        'no estima por sí solo un efecto causal. V8FLAT no se convierte enDOWN.',
        '', '## Year-by-year /2026 y walk-forward fijo','',
        *table(['Año','Estado','n72h','acierto','media','mediana','exceso'],[
            (year,state,x['n_directional'],rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(val(x,'signed_return','median')),pct(s['matched']['72']['mean']))
            for year,states in r['yearly'].items() for state,s in states.items() if state in ('UP','DOWN') for x in [s['horizons']['72']]]),
        '', '2026 sigue separado y sin retuning. Mediana negativa aunque la media sea positiva puede mostrar '
        'asimetría/concentración, no una dirección fiable en la mayoría de ocasiones.',
        '',*table(['Fold','Estado','n72h','acierto','media','exceso','IC95 exceso'],[
            (year,state,x['n_directional'],rate(x.get('directional_accuracy')),pct(val(x,'signed_return')),pct(s['matched']['72']['mean']),' / '.join(pct(v) for v in s['matched']['72']['ci95']))
            for year,fold in r['walk_forward'].items() for state,s in fold['states'].items() if state in ('UP','DOWN') for x in [s['horizons']['72']]]),
        '', '## Soportes/resistencias','',
        'Se reutiliza read-only `guardian_signals.confirmed_structure` y se verifica equivalencia de la búsqueda '
        'bounded220 con `confirmed_level_scale`. Pivots se publican después de2velasderechas. Día/semana anteriores '
        'son periodosUTC completos; semana lunes. % usa precio cerrado conocido; ATR se expresa enATR1H.',
        'Las escalas conservan referenciaTF y timestamps de pivot/confirmación. R cruzada solo por1H durante4H/1D '
        'abierta no se relabela soporte. Falta deR/S no prueba espacio abierto. AT_SUPPORT/AT_RESISTANCE requieren '
        'toque real de rango cerrado a nivel ya conocido, no proximidad ajustada conTEST.',
        '',*table(['Estado','n conS','n conR','distS mediana','distR mediana','S ATRmediana','R ATRmediana'],[
            (state,sum(v['support'] is not None for v in q),sum(v['resistance'] is not None for v in q),
             _median(q,'support_distance_pct',pct),_median(q,'resistance_distance_pct',pct),_median(q,'support_distance_atr',num),_median(q,'resistance_distance_atr',num))
            for state,q in r['structure_context'].items()]),
        '', 'Detalle por episodio en JSON; no umbral de distancia seleccionado ni permisos de entrada.',
        '', '## Ruido / eficiencia / arquitectura','',
        '[LEGACY_NOISE_AUDIT.md](LEGACY_NOISE_AUDIT.md) distingue overlap de estado(99,92%UPconV8LONG) de '
        'overlap de onsets(8pares, mediana engine12hposterior aV8, muestra pequeña). '
        'Guardian KEEP_VISIBLE/KEEP_ACTIVE; V8 KEEP_VISIBLE; engine KEEP_INTERNAL research. '
        'No se silencian sistemas útiles por estética. ML/otros: duplicación real ylead/lagforwardPENDING. '
        'No cambios de alertas, servicios, variables ni producción.',
        '', '## Gates / clasificación','',
        *table(['Lado','Gates no superados'],[(side,', '.join(k for k,v in gates.items() if not v)) for side,gates in r['gates'].items()]),
        '', 'USEFUL exigía ambos lados con>=50episodiosTEST, media/exceso positivos eICsemanal inferior>0 a72h, '
        'estabilidad entre años/folds, sin dependencia mejores3 y evaluación realMLconfirmado disponible. '
        'No se cumplen. USEFUL tampoco significaría estrategia rentable, señal live ni autorización.',
        '', '## Telegram: muestras sintéticas, no enviadas','',
        'Renderer puro sin token, sender ni poller. Prototipo file-fed retorna strings y conserva estado/dedupe '
        'separado; bootstrap/restart/catch-up silenciosos. No está integrado ni arrancado en producción.',
        *sum(([f'### {state} — ILLUSTRATIVE','', '```text',text,'```',''] for state,text in messages.items()),[]),
        '## Validación / límites','',
        'Resultados congelados y replay reproducible, sin datasets grandes enGit. Ver '
        '[validation.json](artifacts/validation.json), [safety_audit.json](artifacts/safety_audit.json) y[README](README.md). '
        'No dependencias de ejecutores ni privateAPI, no MLmath nuevo, no mensajes reales. '
        'Forward real sigue PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR. '
        'La integración completa con confirmaciones reales debe evaluarse con sus timestamps de disponibilidad, '
        'sin backdating ni sustituir datos ausentes.',
        '', '**V8 UNCHANGED. GUARDIAN UNCHANGED. ML RSI MATH UNCHANGED. MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.**',
        '', '**NO MERGE. NO DEPLOY. NO REAL ORDERS. TRADE AUTHORITY: NONE.**',
        '',r['classification']]
    (Path(__file__).parent/'BITMAN_DIRECTION_ENGINE_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')


def _median(rows,key,format_):
    import numpy as np
    a=[r[key] for r in rows if r[key] is not None]
    return format_(float(np.median(a))) if a else 'NA'


if __name__=='__main__':build()
