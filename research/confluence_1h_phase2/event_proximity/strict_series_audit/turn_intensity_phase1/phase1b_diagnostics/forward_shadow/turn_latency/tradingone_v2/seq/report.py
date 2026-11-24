from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import csv,gzip,hashlib,json


def main():
    lab=Path(__file__).resolve().parent
    out=lab/'out'
    def read(name):
        with (out/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
    def when(stamp):return datetime.fromtimestamp(float(stamp)/1000,timezone.utc).astimezone(ZoneInfo('Europe/Madrid')).strftime('%d/%m %H:%M')
    def num(v,n=3):return f'{float(v):.{n}f}' if v not in (None,'','None') else 'UNKNOWN'
    s=json.loads((out/'summary.json').read_text())
    trades=read('trades.csv');events=read('events.csv');claims=read('claims.csv');rsi=read('rsi.csv')
    frames={k:read(k+'.csv') for k in ('1h','4h','1d','1w','2w')}
    evidence=[]
    def ev(key,source,author,stamp,lesson,missing,hypothesis):
        evidence.append(dict(id=key,source=source,author=author,reported_madrid=stamp,documented=lesson,
            verification_pending=missing,implementation_hypothesis=hypothesis,evidence_grade='DERIVED_NO_ORIGINAL_MESSAGE_OR_FRAME'))
    ev('FRED','dossier','Fred/Jose Luis','02Oct00:15-00:32;18Nov13:01','Parabola lisa; ejemplo invertido BTCUSD1D','Serie del area, curvatura, validacion y mercado','NO FRED signal; record all layer slopes/acceleration')
    ev('RECOVERY','dossier','Jose Luis/Joanga','18Nov12:50;23Nov10:01/15:19','Indicadores4H recuperan con poco precio','Original Bitman, media exacta','Separate AO/price/line displacement and structure, no fitted threshold')
    ev('VOL_EXIT','dossier','SLir Valdez/El','18Nov21:10;19Nov00:53','Salida/recorte por giro volatilidad1H','Linea/direccion exacta y fills','Cooling/exhaustion descriptive; fixed prior partial/BE/trail model')
    ev('TS_FRACTALS','dossier','El/Hermi','23Nov20:42-20:44;14Nov20:07','Cruce y regreso en TS/fractales; Hermi117/2.8/150/100','Version/ajustes de Bitman','Owner TSA119/2.8 and causal2+2 pivots; price-line rejection hypothesis')
    ev('FALSE_FORECAST','dossier','Jorge Ruiz','18Nov11:38-11:40','Esperaba66176 antes de short, no ocurrio en ventana auditada','Mensaje/fill','Retain as failed forecast; not backfilled as entry')
    ev('MISSED_TARGETS','dossier','miembros no identificados','18-19Nov','61611/59500 no alcanzados al corte19Nov, luego alcanzados','Timestamp/fuente de cada target','Horizon separation; do not reinterpret earlier failure')
    ev('LATE_CONFIRM','dossier','I-GOD auditado','18Nov16:00;24Nov05:00','ML RSI alineado tarde; rojo4H despues del minimo24Nov','Logs originales/config exacta','Separate source message time, close time, watch and confirmation')
    ev('EARLY_WARNING','dossier','Jose Garcia/El','23Nov20:40-20:45','Short comentado despues del rechazo y antes de otro tramo','Contrato, entrada, SL y fills','No claimed trade; compare modeled events and subsequent price')
    ev('WEEKLY_ZERO','directo','Bitman via subtitulos','23Nov;min23:31-26:15','Area volumen semanal cruza cero y supuesto minimo primera semana','Area exacta y cruce intravela vs cerrado','All pececillos/tendencia/tiburones zero crossings individually; no performance claim')
    ev('EXHAUST_SEQUENCE','directo','Bitman via subtitulos','23Nov;min36:42-40:19/97:00','Volatilidad diaria primero, AO verde, ADX enfriando, Konkorde','Formulas y velas aun abiertas','Timestamp each token; no simultaneity or directional ADX gate')
    ev('2W_AO','directo','Bitman via subtitulos','23Nov;min48:08-60:16','Posible convergencia alcista2W no confirmada','Anclaje2W/plataforma y futuras barras','Confirmed price-fractal/AO divergences only; experimental anchor')
    ev('FAILED_LOW','directo','Bitman via subtitulos','23Nov;min27:03-35:36','Nuevos minimos con extension debil y recuperacion','Umbral y ventana exactos','Retain measured extension/ATR and reclaim delay without fitted weak threshold')
    ev('RSI_NOV5','directo','Bitman via subtitulos','05Nov;min63:50-68:47','Afirma SHORT futuros cerca77k','Contrato, formula, candle time, live signal, fees/fills','Spot LOW27 ALMA4 diagnostic, all transitions including failures; not same signal')
    ev('RSI_NOV22','directo','Bitman via subtitulos','22Nov17:00Madrid;min63:50-68:47','Afirma LONG futuros cerca60k','Opening/closing time, contract and source config','Both opening and availability interpretations, not optimized identity')
    ev('FE','dossier','Paco','18Nov09:57-09:58','FE two lines with visual30/70','Source/author/parameters/license','Excluded, FE_UNVERIFIED')
    (lab/'evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    from collections import Counter
    counts=s['events'];sim=s['simulation']
    body=['# I-GOD — motor secuencial SHADOW V0','',
    '**Prototipo funcional; ninguna ventaja demostrada. No desplegado.**','',
    '## Fuentes y alcance',
    'Se leyeron completos los dos documentos aportados. Son auditorias derivadas y un resumen basado en subtitulos recuperados; no tenemos mensajes, capturas, subtitulos originales ni fills. El acceso directo al video no fue recuperable. No se atribuyen las hipotesis propias a Bitman. Ver evidence.json y los hashes de spec.json/sources.json. No se publican las secciones personales de posicion/cuenta del dossier.',
    '',
    'Base PR57 0017faf; declaracion daa8673 y addendum19a2f57 anteriores a resultados. Nuevo codigo solo bajo research. PR55 mantiene NO EDGE, PR50 NO TESTABLE y la paridad completa TradingOne permanece NO CERTIFICADA. No se alteran las investigaciones ni formulas previas.',
    '',
    '## Que se reutiliza y que falta',
    '| Elemento | Implementacion y limite |','|---|---|',
    '| AO/ADX/Konkorde | Kernels auditados: HL2 SMA5/34, DMI14/14, pececillos/tendencia/tiburones/EMA15 separadas. No proxies privados certificados. |',
    '| BBWP | CLOSE SMA13/252 y SMA5. Giro de fuerza/volatilidad no decide direccion. |',
    '| Trend Speed | Fuente TSA del propietario119/2.8/50/100, con licencia CC BY-NC-SA4.0. No es la configuracion117/2.8/150/100 de Hermi ni certificacion del TS de Bitman. |',
    '| Fred | No hay definicion cuantitativa suficiente. Se registran curvas/pendientes/cambios, pero NO se inventa una senal Fred. |',
    '| FE | No verificado, excluido. |',
    '| 2W | Anclaje lunes1970-01-05 declarado; no certificacion de calendario del grafico. Solo cierres; BBWP2W UNKNOWN por warmup insuficiente. |',
    '| Fractales | Hipotesis explicita2+2; confirmados dos barras despues. Nunca se operan retrospectivamente los vertices. |',
    '| Rechazo/retest | Niveles previamente disponibles, cierre y posterior retest; linea TSA del cierre anterior. Son reglas de investigacion. |',
    '',
    '## Motor de secuencias',
    'Contexto cerrado2W/1W/1D/4H/1H/15m por timestamp de disponibilidad. WATCH independiente por lado ante desaceleracion/giro AO1H; expiracion2h, oposicion invalida. Confirmacion requiere pendientes AO/pececillos alineadas y break/retest15m de fractal conocido. ADX, BBWP y contexto se registran sin imponer filtros direccionales nuevos. Agotamiento se registra por giro opuesto AO o enfriamiento ADX+BBWP; no se inventa una salida volatilidad literal del video.',
    '',
    'La recuperacion se registra en unidades del indicador y desplazamiento del precio/ATR por separado. Las secuencias diarias guardan timestamps de giros, sin afirmar que el orden historico constituya una senal validada. Cada senal conserva razones, precios y latencia. Todas las prealertas fallidas y oportunidades rechazadas permanecen en el ledger.',
    '',
    '## Datos y coherencia temporal',
    'Binance BTCUSDT Spot publico, GET sin credenciales. Corte24Nov2026 09UTC (10Madrid). Replay18Nov00UTC–24Nov09UTC:612 barras15m,153 horas. No es todo el24Nov. Calentamiento:3200x15m,1800x1H,600x4H,600x1D,480x1W;240x2W derivados. OHLCV, horarios, continuidad, cierre y SHA verificados. Recibos originales y URLs en d/.',
    f'Concordancia de agregacion15m: {s["concordance"]}. Los cambios de marco se conocen solo al cerrar. Las marcas de disponibilidad son modeladas, no emisiones reales de esos dias. No se usa la vela actualmente abierta.',
    '',
    'Documentacion oficial: [klines Binance](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market) y [limites de repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/). Las limitaciones de carga/recarga de TradingOne/ML RSI de PR57 permanecen vigentes.',
    '',
    '## Contraste de afirmaciones de mercado del dossier',
    '| Disponibilidad Madrid | Serie | Informe | Replay | Diferencia |','|---|---|---:|---:|---:|']
    for r in claims:body.append(f'| {when(r["available_at"])} | {r["frame"]} {r["field"]} | {num(r["reported"],5)} | {num(r["replayed"],5)} | {num(r["difference"],8)} |')
    body += ['', '8/8 referencias de precio/AO coinciden al redondeo informado. Esto contrasta esos valores de mercado, NO certifica los otros indicadores, mensajes o resultados de una operacion.', '',
    '## Contexto cerrado final y cruce semanal','| Marco / disponible Madrid | AO / pendiente | ADX / pendiente | Pececillos / roja | BBWP / pendiente |','|---|---|---|---|']
    for name,rows in frames.items():
        r=rows[-1]
        body.append(f'| {name} · {when(r["available_at"])} | {num(r["ao"])} / {num(r["ao_slope"])} | {num(r["adx"])} / {num(r["adx_slope"])} | {num(r["pececillos"])} / {num(r["roja"])} | {num(r["bbwp"])} / {num(r["bbwp_slope"])} |')
    w=frames['1w'][-1]
    body += ['',f'Ultimo1W: pececillos={num(w["pececillos"])} y zero_event={w["pececillos_zero"]}; tendencia={num(w["tendencia"])} y zero_event={w["tendencia_zero"]}; tiburones={num(w["tiburones"])} y zero_event={w["tiburones_zero"]}. El cruce de pececillos descendente esta disponible23Nov00UTC. No identifica por si solo el area privada usada en el directo ni certifica que el minimo ocurra en esa semana.',
    '', 'En2W el minimo de la ultima vela no tiene dos velas derechas cerradas: no se declara un pivote ni una convergencia confirmada sobre ese extremo. Una lectura visual provisional sigue siendo provisional.',
    '', '## RSI1H del5 y22 de noviembre',
    'Se reconstruye el original LOW27/ALMA4/sigma1/offset0, con1800 cierres de inicializacion declarados, no OPT. El directo habla de futuros: este replaySpot no prueba ni refuta esa senal privada. rsi.csv contiene TODOS los cambios y las48 horas de los dos dias, no solo ejemplos favorables. No se calcula tasa de acierto sobre ellos.',
    '', '| Fecha disponible Madrid | Valor | Bandas | Color / cambio | Cierre Spot |','|---|---:|---|---|---:|']
    selected=[r for r in rsi if (r['available_utc'].startswith('2026-11-22T') and r['available_utc'][11:13] in ('15','16','17')) or (r['available_utc'].startswith('2026-11-05T') and r['is_transition']=='True')]
    for r in selected:
        body.append(f'| {when(r["available_at"])} | {num(r["value"])} | {num(r["lower"])}/{num(r["upper"])} | {r["color"]} / {r["is_transition"]} | {num(r["close"],2)} |')
    body += ['', 'La marca22Nov17Madrid puede describir apertura o disponibilidad. Se muestran16/17/18Madrid disponibles (y todas las horas enCSV), sin escoger la interpretacion que encaje. Faltan contrato, ajustes y log contemporaneo para certificar coincidencia.',
    '', 'En nuestro replaySpot LOW27/ALMA4 el22Nov cambia aGREEN a13UTC (14Madrid), no aparece un nuevo cambio de color a17Madrid. El5Nov cambia aRED a17UTC (18Madrid). El directo no da la hora exacta del5 y utiliza futuros; no se declara identidad ni se atribuyen sus porcentajes de exito a este perfil.',
    '', '## Resultado tecnico del replay, no evaluacion de edge',
    '| Registro | N |','|---|---:|']
    for k in ('WATCH','CONFIRMED','INVALIDATED','EXPIRED','EXHAUSTION','SIM_ENTRY','SIM_REJECTED','SIM_FILL','SIM_STOP_UPDATE','SIM_CLOSED'):
        body.append(f'| {k} | {counts.get(k,0)} |')
    lat=[float(r['latency_ms'])/60000 for r in events if r['kind']=='CONFIRMED']
    body += ['',f'Latencia WATCH→confirmacion: mediana {sorted(lat)[len(lat)//2]:g}min; rango {min(lat):g}–{max(lat):g}min. Los cambios de precio consumidos en cada espera quedan registrados en WATCH_PROGRESS y CONFIRMED; no se supone una entrada en el extremo.',
    '', f'{counts["INVALIDATED"]+counts["EXPIRED"]} de{counts["WATCH"]} vigilancias terminaron invalidadas o caducadas:{100*(counts["INVALIDATED"]+counts["EXPIRED"])/counts["WATCH"]:.2f}% de falsas alarmas bajo esta vida util, NO una tasa de operaciones perdedoras. El motor no capturo automaticamente toda la caida hasta55130 y puede confirmar tarde o entrar antes de una invalidacion. Se conserva ese fallo, sin modificar el detector para corregir el episodio.',
    '', '### Operaciones sinteticas completas, todas incluidas',
    '| Entrada Madrid | Lado hipotetico | Salida | TP1 | Neto USDT | R modelada |','|---|---|---|---|---:|---:|']
    for r in trades:body.append(f'| {when(r["entry_at"])} | {"LONG" if r["side"]=="1" else "SHORT"} | {r["exit_reason"]} | {r["tp1"]} | {num(r["net"],2)} | {num(r["net_R"])} |')
    body += ['',f'{sim["completed"]} cierres:{sim["long"]}LONG/{sim["short"]}SHORT. Capital sintetico10000→{sim["marked_equity"]:.2f}; neto{sim["net_realized"]:.2f}; drawdown maximo entre marcas de apertura/cierre{100*sim["max_close_drawdown"]:.3f}%. No hay posicion censurada al final de este replay. Son{sim["completed"]} casos seleccionados temporalmente por el dossier: no una muestra suficiente/independiente ni prueba de rentabilidad. La tasa de acierto no compensa el resultado negativo.',
    '', 'Reglas sin busqueda: riesgo.5%, stop mas lejano entre1.5ATR y fractal con.2ATR, TP1+1%precio/50%, BE neto, trailing1.5ATR y salida24h. Comision.1% y slippage.05% cada fill son supuestos conservadores de investigacion. No se ampliaron configuraciones tras ver el resultado.',
    '', 'Entrada al siguiente open15m mas slippage: latencia de proceso adicional no modelada, no fill garantizado. Si TP/SL coinciden dentro15m, stop primero; hora exacta del fill desconocida y marcada como intervalo. MAE/MFE son cotas de barra, pueden contener recorrido posterior al fill. No se usaron datos1m en este prototipo.',
    '', 'FundingSpot NOT_APPLICABLE; SHORT sintetico sin prestamo ni costes/mark/liquidacion de futuros. No llamar a estos numeros rentabilidad ejecutableBitunix. Modo futuros bloqueado hasta disponer de los datos del contrato. No se simula apalancamiento ni se usa liquidacion como stop.',
    '', '## Riesgo acumulado, promedios y seguridad',
    'Una sola posicion; nuevas entradas con posicion abierta se rechazan. La funcion exposure() permite auditar lotes hipoteticos agregados, promedio, resultado neto al stop y perdida realizada previa; no aumenta cantidad ni reinicia un presupuesto. Stops nunca se ensanchan. El drawdown simulado5% se enclava y no se restablece por una reentrada. No garantiza perdida maxima intrabar o en gaps.',
    '', 'No hay clientes privados, red dentro del motor, Telegram, scheduler, servicio ni acceso a /data. Los archivos de salida locales se crean en un destino nuevo. La cadena de hashes detecta cambios al contrastarla con summary/manifest; no se presenta como journal forward con anclaje externo.',
    '', 'Correccion tecnica: el primer replay renovaba una prealerta caducada durante el mismo tramo AO. Se corrigio para cumplir FIRST de la regla previa, sin cambiar parametros; dos tests cubren rearme/expiracion. Replay preliminar9/-134.24 conservado en research/cache/seq_preliminary, EXCLUIDO como implementacion incorrecta. Ver correction.json. No cambio de protocolos previos.',
    '', '## Evidencia posterior necesaria',
    'Revision independiente del codigo, parametros definitivos de las fuentes y un nuevo corte congelado anterior a datos realmente nuevos. Registrar entonces todas las decisiones antes de outcomes, compararlas con referencias inclusivas por regimen y conservar costes/errores. Nada de esto se ha iniciado ni autorizado como servicio en esta tarea.',
    '', 'Conclusion: **MOTOR EXPERIMENTAL IMPLEMENTADO; EDGE NO DEMOSTRADO.** El replay incluye perdidas y no justifica operaciones reales ni despliegue continuo. Fred, contratoRSI, versionTS y calendario2W siguen parcialmente sin verificar.',
    '', '![Secuencias y simulacion](overview.png)', '', '![Caso23–24](case23.png)', '', '![Todas las operaciones, incluidas perdidas](trades.png)', '', 'SHADOW ONLY. TRADE AUTHORITY: NONE.']
    (out/'REPORT.md').write_text('\n'.join(body)+'\n',encoding='utf-8')
    # Static scientific figures from saved observations; no synthetic market prices.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as md
    with gzip.open(lab/'d/15m.csv.gz','rt') as f:base=list(csv.DictReader(f))
    base_prices={int(float(r['open_time']))+900000:float(r['close']) for r in base}
    def graph(filename,start,end):
        h=[r for r in frames['1h'] if start<=float(r['available_at'])<=end]
        x=[datetime.fromtimestamp(float(r['available_at'])/1000,timezone.utc) for r in h]
        fig,ax=plt.subplots(4,1,figsize=(13,11),sharex=True)
        prices=[(t,c) for t,c in base_prices.items() if start<=t<=end]
        ax[0].plot([datetime.fromtimestamp(t/1000,timezone.utc) for t,c in prices],[c for t,c in prices],label='Spot 15m close',c='black')
        for kind,color,marker in [('WATCH','orange','.'),('CONFIRMED','blue','^'),('INVALIDATED','red','x')]:
            e=[r for r in events if r['kind']==kind and start<=float(r['available_at'])<=end]
            ys=[]
            for r in e:
                ys.append(base_prices[int(float(r['available_at']))])
            ax[0].scatter([datetime.fromtimestamp(float(r['available_at'])/1000,timezone.utc) for r in e],ys,c=color,marker=marker,s=20,label=kind)
        ax[1].plot(x,[float(r['ao']) for r in h],label='AO');ax[1].axhline(0,c='gray',lw=.5)
        ax[2].plot(x,[float(r['bbwp']) for r in h],label='BBWP13/252');ax[2].plot(x,[float(r['adx']) for r in h],label='ADX14/14')
        eq=read('equity.csv');e=[r for r in eq if start<=float(r['available_at'])<=end]
        ax[3].plot([datetime.fromtimestamp(float(r['available_at'])/1000,timezone.utc) for r in e],[float(r['equity']) for r in e],label='Synthetic equity after assumed costs')
        for a in ax:a.grid(alpha=.2);a.legend(loc='best')
        ax[-1].xaxis.set_major_formatter(md.DateFormatter('%d %H:%M',tz=timezone.utc))
        fig.suptitle('I-GOD sequential V0 | engineering replay, NOT validation | UTC')
        fig.tight_layout();fig.savefig(out/filename,dpi=130);plt.close(fig)
    graph('overview.png',s['window_start'],s['end_exclusive'])
    graph('case23.png',1795392000000,s['end_exclusive'])
    with gzip.open(out/'ledger.gz','rt',encoding='utf-8') as f:ledger=[json.loads(x) for x in f]
    fig,axes=plt.subplots((len(trades)+2)//3,3,figsize=(16,3.5*((len(trades)+2)//3)))
    for ax,tr in zip(axes.flat,trades):
        lo=float(tr['entry_at'])-3600000;hi=float(tr['exit_at'])+3600000
        bars=[r for r in base if lo<=float(r['open_time'])<=hi]
        tx=[datetime.fromtimestamp((float(r['open_time'])+900000)/1000,timezone.utc) for r in bars]
        ax.plot(tx,[float(r['close']) for r in bars],c='black',lw=1)
        entry=next(r for r in ledger if r['kind']=='SIM_ENTRY' and r['trade_id']==tr['id'])
        ax.axhline(entry['entry'],label='entry',c='blue',lw=.8)
        ax.axhline(entry['stop'],label='initial stop',c='red',lw=.8)
        ax.axhline(entry['target'],label='TP1',c='green',lw=.8)
        updates=[r for r in ledger if r['kind']=='SIM_STOP_UPDATE' and r['trade_id']==tr['id']]
        if updates:
            ax.step([datetime.fromtimestamp(r['effective_at']/1000,timezone.utc) for r in updates],[r['new'] for r in updates],where='post',label='BE/trail',c='orange')
        stamp=datetime.fromtimestamp(float(tr['entry_at'])/1000,timezone.utc).strftime('%d/%m %H:%M')
        ax.set_title(f'{stamp} UTC {"L" if tr["side"]=="1" else "S"} net {float(tr["net"]):+.2f}',fontsize=9)
        ax.xaxis.set_major_formatter(md.DateFormatter('%d %H:%M',tz=timezone.utc));ax.tick_params(axis='x',rotation=25,labelsize=7)
        ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7)
    for ax in list(axes.flat)[len(trades):]:ax.set_visible(False)
    fig.suptitle(f'ALL {len(trades)} synthetic trades, costs included | UTC | NOT performance validation')
    fig.tight_layout();fig.savefig(out/'trades.png',dpi=120);plt.close(fig)
    print(json.dumps(dict(report=str(out/'REPORT.md'),trades=len(trades),market_claims=len(claims),matched=sum(r['matches_rounded_2dp']=='True' for r in claims))))


if __name__=='__main__':
    main()
