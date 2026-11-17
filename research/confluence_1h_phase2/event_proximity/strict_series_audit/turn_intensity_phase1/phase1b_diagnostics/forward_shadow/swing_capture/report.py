"""Presentation only: no detector/simulator changes or parameter selection."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,gzip,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
H=3600000
def read(p):
    op=gzip.open if p.suffix=='.gz' else open
    with op(p,'rt',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def number(v):return float(v) if v not in (None,'','null') else None
def fmt(v,places=3):return '—' if number(v) is None else f'{number(v):.{places}f}'
def table(rows,columns):
    return '\n| '+' | '.join(label for _,label in columns)+' |\n| '+' | '.join('---' for _ in columns)+' |\n'+''.join('| '+' | '.join(str(row.get(k,'—')).replace('|','/') for k,_ in columns)+' |\n' for row in rows)+'\n'
def short(k):return k.replace('TP0.005','TP0,5%').replace('TP0.01','TP1%').replace('TP0.02','TP2%').replace('_SL',' / SL').replace('_RISK0.005',' / riesgo0,5%').replace('_RISK0.01',' / riesgo1%')
def build(out,data):
    meta=json.loads((out/'results.json').read_text());summary=read(out/'summary.csv');subs=read(out/'subgroups.csv');comparisons=read(out/'comparisons.csv');trades=read(out/'trades.csv');curve=read(out/'equity.csv.gz');fills=read(out/'fills.csv');stops=read(out/'stop_updates.csv');diagnostic=read(out/'diagnostic_20261116.csv');years=read(out/'calendar_account.csv')
    figures=out/'figures';figures.mkdir(exist_ok=True);plt.rcParams.update({'font.size':9,'figure.dpi':120})
    fig,ax=plt.subplots(3,2,figsize=(13,10),sharex=True)
    for n,(tp,sl) in enumerate((tp,sl) for tp in (.005,.01,.02) for sl in (1.5,2.5)):
        panel=ax.flat[n]
        for risk,color in ((.005,'#1d659c'),(.01,'#bd4c2d')):
            cfg=f'TP{tp:g}_SL{sl:g}_RISK{risk:g}';rows=[r for r in curve if r['config']==cfg]
            x=[datetime.fromtimestamp(int(r['open_ms'])/1000,timezone.utc) for r in rows];panel.plot(x,[float(r['equity']) for r in rows],color=color,label=f'Riesgo{risk*100:g}%')
        panel.axhline(10000,color='gray',lw=.6);panel.set_title(f'TP1: {tp*100:g}% · SL{sl:g}ATR');panel.set_ylabel('Equity (USDT)');panel.legend();panel.grid(alpha=.2)
    fig.suptitle('Confluence Swing Capture · equity simulada neta · todos los escenarios');fig.tight_layout();fig.savefig(figures/'equity_all.png');plt.close(fig)
    fig,ax=plt.subplots(3,2,figsize=(13,10))
    for n,(tp,sl) in enumerate((tp,sl) for tp in (.005,.01,.02) for sl in (1.5,2.5)):
        panel=ax.flat[n]
        for risk,color in ((.005,'#1d659c'),(.01,'#bd4c2d')):
            cfg=f'TP{tp:g}_SL{sl:g}_RISK{risk:g}';v=[float(r['net_R']) for r in trades if r['config']==cfg]
            panel.hist(v,bins=40,histtype='step',label=f'{risk*100:g}%',color=color)
        panel.axvline(0,color='gray',lw=.6);panel.set_title(f'TP1: {tp*100:g}% · SL{sl:g}ATR');panel.set_xlabel('Resultado neto / riesgo inicial planificado');panel.set_ylabel('Operaciones');panel.legend()
    fig.tight_layout();fig.savefig(figures/'net_R_distribution.png');plt.close(fig)
    with np.load(data,allow_pickle=False) as z:a=z['bars']
    # First-in-time positive/negative trade of each side, always the first frozen
    # scenario. This never selects the most profitable configuration or example.
    cfg=summary[0]['config'];chosen=[]
    for side in (1,-1):
        for outcome in ('POSITIVE','NEGATIVE'):
            candidates=[r for r in trades if r['config']==cfg and int(r['side'])==side and (float(r['net'])>0 if outcome=='POSITIVE' else float(r['net'])<0)]
            if not candidates:continue
            tr=min(candidates,key=lambda r:int(r['entry_i']));chosen.append(dict(tr,selection='FIRST_'+outcome+'_'+str(side)))
            start=max(0,int(tr['entry_i'])-8);end=min(len(a),int(tr['exit_i'])+5);b=a[start:end];xx=b[:,0]/H
            fig,panel=plt.subplots(figsize=(12,4));panel.vlines(xx,b[:,3],b[:,2],color='#687586',lw=.7);panel.plot(xx,b[:,4],color='#1d659c',lw=1,label='Cierre H1')
            panel.scatter([int(tr['entry_at'])/H],[float(tr['entry_fill'])],marker='^' if side==1 else 'v',color='#087f5b',label='Entrada modelada')
            entry=float(tr['entry_fill']);unit=float(tr['risk_usdt'])/float(tr['qty'])
            initial=(entry*1.001-unit)/(.9995*.999) if side==1 else (unit+entry*.999)/(1.0005*1.001)
            panel.hlines([initial,entry*(1+side*.005)],int(tr['entry_at'])/H,(int(tr['exit_hour'])+H)/H,colors=['#b84545','#087f5b'],linestyles='dashed',lw=.8,label='SL inicial / TP1')
            for fill in fills:
                if fill['config']==cfg and fill['signal_id']==tr['signal_id']:panel.scatter([int(fill['window_start'])/H],[float(fill['fill'])],color='#ba3434',s=22);panel.annotate(fill['kind'],(int(fill['window_start'])/H,float(fill['fill'])),fontsize=8)
            updates=[r for r in stops if r['config']==cfg and r['signal_id']==tr['signal_id']]
            if updates:panel.step([int(r['effective_at'])/H for r in updates],[float(r['level']) for r in updates],where='post',color='#cb8b12',label='BE/trailing efectivo siguiente H1')
            panel.set_title('Ejemplo '+outcome+' '+('LONG' if side==1 else 'SHORT')+' · neto'+fmt(tr['net'])+'USDT · '+cfg)
            ticks=np.linspace(xx[0],xx[-1],6);panel.set_xticks(ticks,[datetime.fromtimestamp(v*H/1000,timezone.utc).strftime('%m-%d %H:%M') for v in ticks]);panel.set_xlabel('UTC; fills dentro de su intervalo registrado');panel.legend();fig.tight_layout()
            fig.savefig(figures/(outcome.lower()+'_'+str(side)+'.png'));plt.close(fig)
    plot_diagnostic(out,figures)
    performance=[];management=[];dollars=[];reference_rows=[];side_rows=[]
    for s,c in zip(summary,comparisons):
        n=int(s['n']);counts=json.loads(s['counts']);performance.append(dict(config=short(s['config']),n=n,long=s['long_n'],short=s['short_n'],win=fmt(s['win_rate_pct'],2),exp=fmt(s['expectancy_R']),pf=fmt(s['profit_factor']),return_pct=fmt(s['account_return_pct'],2),dd=fmt(s['max_close_drawdown_pct'],2)))
        management.append(dict(config=short(s['config']),tp1=fmt(100*int(s['tp1_n'])/n,2) if n else '—',BE=s['be_exit_n'],trail=s['trailing_exit_n'],initial=s['initial_stop_n'],end=s['forced_end_n'],ambiguous=s['m1_ambiguous'],h1=s['h1_ambiguous'],resolved=s['resolved_m1'],reject=counts['leverage_required'],busy=counts['skipped_position']))
        dollars.append(dict(config=short(s['config']),win=fmt(s['mean_win'],2),loss=fmt(s['mean_loss'],2),exp=fmt(s['net_expectancy'],2),streak=s['max_losing_streak'],mfe=fmt(s['mean_mfe_pct']),mae=fmt(s['mean_mae_pct']),worst=fmt(s['worst_trade_R'])))
        reference_rows.append(dict(config=short(s['config']),actual=fmt(c['expectancy_R_actual']),q05=fmt(c['expectancy_R_reference_q5']),median=fmt(c['expectancy_R_reference_q50']),q95=fmt(c['expectancy_R_reference_q95']),n=s['n'],nmed=fmt(c['n_reference_q50'],0)))
    for r in subs:
        if r['group']=='side':side_rows.append(dict(config=short(r['config']),side='LONG' if r['value']=='1' else 'SHORT',n=r['n'],win=fmt(r['win_rate_pct'],2),exp=fmt(r['expectancy_R']),pf=fmt(r['profit_factor']),net=fmt(r['net_total'],2)))
    positive=sum(number(s['expectancy_R']) is not None and number(s['expectancy_R'])>0 for s in summary)
    label='NO EDGE EN LOS ESCENARIOS ESTUDIADOS' if positive==0 else 'INCONCLUSO — RESULTADOS HISTÓRICOS, NO VALIDADOS'
    text=f'''# I-GOD — Confluence Swing Capture V0

**{label}. SHADOW ONLY. TRADE AUTHORITY: NONE.**

Se han evaluado exactamente12 configuraciones, sin elegir una ganadora ni cambiar parámetros después de ver resultados. {positive}/12 tienen esperanza neta observada positiva. Esto no demuestra ausencia universal de efecto ni valida una variante: estudia esta formalización causal y esta gestión concreta.

## Qué se congeló y qué se está probando

Plan previo a resultados: commit `{meta['seal']['frozen_plan_commit']}`, SHA256 `{meta['plan_hash']}`. AO5/34, ADX/DMI14, pececillos del proxy público original, roja EMA15(tendencia), BBWP7/100 y ATR14 no se modificaron. No certificamos paridad con indicadores privados Bitman/TradingOne.

Cuatro giros nuevos en una ventana máxima2h. AO y pececillos1+1 deben coincidir en lado y seguir con esa pendiente; ADX y BBWP pueden girar a cualquier lado y se anotan como fase. No se exigen cruces de cero, Q75,2+2 ni contexto superior. Los tokens expiran/se invalidan y se consumen una vez; no hay cooldown extra. Se conservan todos los intentos fallidos y señales bloqueadas.

TP1:0,5/1/2% desde el fill; SL:1,5/2,5ATR de la señal; parcial50%; runner con BE neto y trailing1,5ATR. La referencia entra en la apertura H1 posterior con slippage: **no es un fill real observado**. Un solo trade; no se invierte automáticamente por señal contraria. No hay nuevo TP2 ni salida temporal arbitraria; cierre forzoso al final del archivo identificado aparte.

BE/trailing se actualizan al cierre H1 y son efectivos en la hora siguiente. No protegen retrospectivamente dentro de la vela TP1. Esta granularidad conservadora puede diferir de un gestor que reaccione inmediatamente intraminuto; no se cambió tras los resultados. Stops nunca se amplían. El BE protege la porción restante sin gastar el beneficio TP1; gaps/funding posterior pueden dejar pérdidas aunque el motivo de salida sea BE.

## Datos y ejecución

BTCUSDT **Binance USD-M perpetual**, no Spot ni Bitunix. Histórico2022-11-01 a2026-10-31; calentamiento desde2022-09-01. NPZ H1 auditado:`{meta['history_sha256']}`. {meta['study_hours']:,} cierres de estudio; {meta['raw_signals']:,} señales, {meta['long_signals']}LONG y{meta['short_signals']}SHORT. Todo el histórico ya estaba examinado: **NO VIRGIN HOLDOUT**. No hay observación prospectiva.

{meta['minute_rows']:,} velas1m oficiales con checksum. {meta['verified_minute_hours']:,} horas reproducen exactamente el OHLC H1 y su volumen dentro de tolerancia numérica fijada. La fuente minuto es la misma venue. En una vela que toca TP1 y SL se usa el orden1m; si ambos aparecen en el mismo minuto, primero el resultado adverso. Horas incompletas/incompatibles usan H1 adverso y quedan contadas. Las excursiones MFE/MAE usan rangos de las barras mantenidas, incluida la barra de salida: **son cotas de barra, no extremos intratick certificados antes del fill**.

Comisión conservadora0,1% por fill y slippage adverso0,05% por fill. Son supuestos, no tarifas personales Bitunix ni prueba de ejecución allí. Funding real USD-M con su timestamp completo:1.657 pagos tienen offsets1–29ms. No se redondean a la hora. Si un fill coincide con su intervalo, se conserva el rango de BTC que pudo estar abierto. Marks ausentes usan los límites H1 previamente auditados, no cero. Se contabiliza al cierre H1: los rangos aún abiertos no afectan a tamaño/stop intrahora. `funding.csv` conserva cada cargo y sus límites.

Capital inicial independiente10.000USDT por configuración; se utiliza el restante cronológico, sin reinicio ni aportaciones. Riesgo planificado0,5/1% hasta el stop **incluyendo comisiones y slippage**. El funding futuro/gaps puede superar ese presupuesto. Si el tamaño requerido excede capital totalmente colateralizado1x, se rechaza `LEVERAGE_REQUIRED`; no se reduce el tamaño y se dice que cumple riesgo constante. No se usa liquidación como stop ni se simula que abrir SHORT Spot sin préstamo sea ejecutable. No se certifican mínimos/tiers ni liquidación histórica de Bitunix.

## Resultados completos — orden fijo predeclarado

Drawdown = máximo de equity marcado a cierres H1, incluidos PnL flotante/costes/funding. No equivale al peor drawdown intratick. Ganador = resultado neto positivo, no simplemente haber tocado TP1. Beneficio/pérdida media y esperanza en USDT varían con el equity cronológico; R se refiere exclusivamente al presupuesto inicial calculado al stop.
'''
    text+=table(performance,[('config','Configuración'),('n','Trades'),('long','LONG'),('short','SHORT'),('win','Acierto %'),('exp','Esperanza neta R'),('pf','PF'),('return_pct','Cuenta %'),('dd','DD cierre %')])
    text+='\n![Equity de todos los escenarios](figures/equity_all.png)\n'
    costrows=[]
    for s in summary:
        tt=[r for r in trades if r['config']==s['config']];ff=[r for r in fills if r['config']==s['config']]
        sides={t['signal_id']:int(t['side']) for t in tt};exit_reference=sum(sides[r['signal_id']]*float(r['qty'])*float(r['reference']) for r in ff)
        raw=exit_reference-sum(int(t['side'])*float(t['qty'])*a[int(t['entry_i']),1] for t in tt)
        gross=sum(float(t['gross']) for t in tt);fees=sum(float(t['entry_fee'])+float(t['exit_fees']) for t in tt);fund=sum(float(t['funding_high']) for t in tt)
        costrows.append(dict(config=short(s['config']),raw=fmt(raw,2),slip=fmt(raw-gross,2),fees=fmt(fees,2),fund=fmt(fund,2),net=fmt(sum(float(t['net']) for t in tt),2)))
    text+='\n### Descomposición del mismo ledger de fills\n\nEl bruto sin fricciones conserva las cantidades y decisiones simuladas; no es una estrategia alternativa ejecutada sin costes. Funding negativo significa crédito. No se rebajan costes para buscar una configuración positiva.\n'
    text+=table(costrows,[('config','Configuración'),('raw','PnL precio antes fricción USDT'),('slip','Slippage USDT'),('fees','Comisiones USDT'),('fund','Funding conservador USDT'),('net','PnL neto USDT')])
    text+=table(dollars,[('config','Configuración'),('win','Ganancia media USDT'),('loss','Pérdida media USDT'),('exp','Esperanza USDT'),('streak','Racha pérdidas'),('mfe','MFE media % cota'),('mae','MAE media % cota'),('worst','Peor trade R')])
    text+='\n![Distribuciones netas](figures/net_R_distribution.png)\n\n## Parciales y salidas\n\nBE y trailing armados no garantizan beneficio; el resultado es el neto real del ledger simulado.\n'
    text+=table(management,[('config','Configuración'),('tp1','TP1 %'),('BE','Salida BE'),('trail','Salida trailing'),('initial','SL inicial'),('end','Final archivo'),('resolved','Orden resuelto1m'),('ambiguous','Ambiguo1m adverso'),('h1','H1 adverso sin1m'),('reject','Rechazo capital1x'),('busy','Posición ya abierta')])
    text+='\n## LONG y SHORT separados\n'+table(side_rows,[('config','Configuración'),('side','Lado'),('n','N'),('win','Acierto %'),('exp','Esperanza R'),('pf','PF'),('net','Neto total USDT')])
    text+='\n## Referencias inclusivas por régimen — misma gestión\n\n100 semillas fijas. Igual número de señales brutas por lado/mes/régimen4H/tercil causal de volatilidad; universo incluye eventos y vecinos. Muestreo sin reemplazo por celda, sin consultar retornos. Las colisiones opuestas se descartan. Cada calendario usa el mismo motor, capital, costes, funding, intrabar, parciales y restricciones. Ocupación/duración/capital pueden cambiar el N ejecutado: se publica, no se finge emparejamiento uno-a-uno de trades ejecutados.\n\nLos percentiles5/50/95 son dispersión de100 calendarios de referencia en la misma historia; **no son IC95, p-valores ni100 historias independientes**. No se escoge una semilla por su resultado.\n'
    text+=table(reference_rows,[('config','Configuración'),('actual','R observado'),('q05','Referencia P5'),('median','Referencia mediana'),('q95','Referencia P95'),('n','N real'),('nmed','N referencia mediana')])
    stronger=sum(float(r['expectancy_R_actual'])>float(r['expectancy_R_reference_q95']) for r in comparisons)
    text+=f'\n{stronger}/12 expectativas observadas superan el percentil95 de los calendarios de referencia. Es una comparación descriptiva de esta simulación, no una prueba de significación ni validación independiente.\n'
    text+='\n## Estabilidad por años, regímenes y contexto\n\n2022 contiene solo noviembre/diciembre y2026 enero/octubre. `subgroups.csv` agrupa trades por año de entrada/lado/régimen/fase ADX-BBWP y contextos4H/diario/semanal; siempre con N. `calendar_account.csv` muestra retorno/drawdown de cuenta por año natural, conservando equity entre años; trades que cruzan año impiden equiparar su suma a estadísticas por año de entrada. El contexto solo usa velas completamente cerradas; semanas lunes00UTC. UNKNOWN no filtra señales. SMA200 semanal solo está disponible al final de este histórico. No se promueve un subgrupo favorable a filtro nuevo.\n'
    annual=[dict(config=short(r['config']),year=r['year'],ret=fmt(r['return_pct'],2),dd=fmt(r['max_close_drawdown_pct'],2),eq=fmt(r['equity_end'],2)) for r in years]
    text+='<details><summary>Todos los años y escenarios</summary>\n\n'+table(annual,[('config','Configuración'),('year','Año'),('ret','Cuenta anual %'),('dd','DD anual cierre %'),('eq','Equity final USDT')])+'\n</details>\n'
    regime=[dict(config=short(r['config']),regime=r['value'],n=r['n'],exp=fmt(r['expectancy_R']),pf=fmt(r['profit_factor'])) for r in subs if r['group']=='regime4h']
    text+=table(regime,[('config','Configuración'),('regime','4H cierre−SMA200 signo'),('n','N'),('exp','Esperanza R'),('pf','PF')])
    text+='\n## Ejemplo16/11/2026 alrededor23Madrid — diagnóstico, no calibración\n\nSe estudian apertura y cierre por separado: en noviembre Madrid=UTC+1. Fuente USD-M; no se dispone de exportación/captura con ticker/configuración original suficientes para certificar paridad visual. A las23Madrid de disponibilidad no hay nueva confluencia LONG de las cuatro vueltas de este detector. AO/pececillos ya recuperaban antes; ADX estaba subiendo, pero sin un nuevo giro dentro de la ventana. La máquina sí registra SHORT a las02Madrid del17/11. **No se cambió la ventana ni el giro para forzar la coincidencia visual.** No se incluye este ejemplo en los resultados de2022–octubre2026.\n'
    dd=[dict(open=r['open_madrid'],available=r['available_madrid'],ao=fmt(r['ao_slope']),pece=fmt(r['pece_slope']),adx=fmt(r['adx_slope']),bbwp=fmt(r['bbwp_slope']),turns=r['ao_turn']+'/'+r['pece_turn']+'/'+r['adx_turn']+'/'+r['bbwp_turn'],side=r['confluence_side']) for r in diagnostic]
    text+=table(dd,[('open','Apertura Madrid'),('available','Disponible Madrid'),('ao','ΔAO'),('pece','Δpece'),('adx','ΔADX'),('bbwp','ΔBBWP'),('turns','Giros AO/K/ADX/B'),('side','Confluencia')])
    text+='\n![Diagnóstico de pendientes y valores](figures/diagnostic_20261116.png)\n\n## Ejemplos de operaciones favorables y adversas\n\nPrimer trade cronológico neto positivo y negativo de cada lado, exclusivamente primera configuración del orden congelado (no la mejor). No se eligen extremos de precio retrospectivos como entradas.\n'
    for tr in chosen:
        side=int(tr['side']);outcome='positive' if 'FIRST_POSITIVE' in tr['selection'] else 'negative';text+='\n!['+tr['selection']+'](figures/'+outcome+'_'+str(side)+'.png)\n'
    text+='''
## Auditoría y reproducción

El plan original y su hash permanecen intactos. Dos fallos técnicos detuvieron intentos antes de producir trades: columnas heterogéneas del CSV y rechazo de timestamps reales de funding no alineados exactamente. `export_amendment.json` y `funding_amendment.json` preservan sellos previos, cambios de fuente y motivos; no hubo ajuste de señales o parámetros por PnL. El detector permaneció idéntico. No se afirma paridad con una captura sin datos originales.

`trades.csv`, `fills.csv`, `stop_updates.csv`, `funding.csv` y `opportunities.csv` conservan todas las operaciones reales simuladas y descartes. `detector_audit.csv.gz` conserva pendientes/cancelaciones. `reference_schedules.csv.gz` y `references.csv` conservan todas las semillas y resultados, sin borrar desfavorables. El ledger completo de todas las referencias se retiene localmente con checksum; muestra auditada de la primera semilla y receta de reproducción se publican sin cargar cientos de MB duplicados al repo.

Reproducir con Python3.12.12/NumPy2.3.5: ejecutar el módulo `swing_capture.study` con `--data <NPZ auditado> --minutes <minutes.npz> --market-folder <archivos públicos> --out <carpeta nueva>`. Los archivos y URLs/checksums están en `minute_manifest.json`. El script de descarga histórica puntual se incluye en el paquete de auditoría, sin scheduler/servicio. El motor verifica su sello y dependencias auditadas antes de calcular.

Esta investigación completa una simulación concreta; no establece rentabilidad futura, validez estadística independiente ni seguridad de ejecución real. No se integra ni activa ningún detector/observer/colector. No se modifican Guardian/V8/ML RSI/Bitman/Railway/Bitunix/Telegram, los controles operativos existentes ni PRs previas. Sin merge, deploy, órdenes o autoridad de trading.
'''
    (out/'SWING_CAPTURE_RESULTS.md').write_text(text,encoding='utf-8',newline='\n')
    (HERE/'README.md').write_text('# Confluence Swing Capture — offline research\n\nRead [SPEC.md](SPEC.md), [plan.json](plan.json) and [the complete results](results/SWING_CAPTURE_RESULTS.md). The original sources and closed observer PRs are unchanged. No runtime imports this package. No service or live capture.\n\nSHADOW ONLY. TRADE AUTHORITY: NONE.\n',newline='\n')
    return dict(conclusion=label,positive_configurations=positive,total_configurations=len(summary),report=str(out/'SWING_CAPTURE_RESULTS.md'),matplotlib=matplotlib.__version__)

def plot_diagnostic(out,figures):
    rows=read(out/'diagnostic_20261116.csv');fig,axes=plt.subplots(5,1,figsize=(12,10),sharex=True);x=np.arange(len(rows))
    for panel,key,color in zip(axes,('close','ao','pece','adx','bbwp'),('#263747','#1b7b5a','#9b922f','#b84545','#6c60a3')):
        panel.plot(x,[float(r[key]) for r in rows],marker='o',ms=3,color=color);panel.set_ylabel(key);panel.grid(alpha=.2)
    axes[-1].set_xticks(x,[r['available_madrid'][5:16].replace('T',' ') for r in rows],rotation=40);axes[-1].set_xlabel('Disponibilidad del cierre H1 · Europe/Madrid');fig.tight_layout();fig.savefig(figures/'diagnostic_20261116.png');plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'results');p.add_argument('--data',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.out,a.data)))
