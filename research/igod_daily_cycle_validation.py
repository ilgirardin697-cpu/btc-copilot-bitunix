"""Pre-specified descriptive cycle validation; never imported by any service."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import time
import requests
from igod_daily_plan.core import normalize
from igod_daily_plan.cycle import cycle_series

DAY=86400_000
OUT=Path('research/results')
CACHE=Path('research/cache/daily_cycle')


def acquire():
    CACHE.mkdir(parents=True,exist_ok=True)
    path=CACHE/'daily_usdm.json'
    if path.exists():
        return json.loads(path.read_text())
    session=requests.Session()
    session.trust_env=False
    end=int(time.time()*1000)//DAY*DAY
    start=int(datetime(2019,9,1,tzinfo=timezone.utc).timestamp()*1000)
    rows=[]
    while start<end:
        response=session.get('https://fapi.binance.com/fapi/v1/klines',
            params=dict(symbol='BTCUSDT',interval='1d',startTime=start,endTime=end-1,limit=1500),
            timeout=(3,15),allow_redirects=False)
        if response.status_code!=200:
            raise RuntimeError('PUBLIC_HTTP_'+str(response.status_code))
        page=response.json()
        if not isinstance(page,list) or not page:
            raise RuntimeError('PUBLIC_INCOMPLETE')
        rows+=page
        following=page[-1][0]+DAY
        if following<=start:
            raise RuntimeError('PUBLIC_PAGINATION')
        start=following
    value=dict(asof=int(time.time()*1000),rows=rows,venue='BINANCE_USDM_PERPETUAL',
               source='https://fapi.binance.com/fapi/v1/klines',symbol='BTCUSDT',interval='1d')
    normalize(rows,'1d',value['asof'],330)
    path.write_text(json.dumps(value,separators=(',',':')),encoding='utf-8')
    return value


def summary(events):
    direction=[x for x in events if x['signed'] is not None]
    return dict(n=len(events),n_directional=len(direction),
                mean_signed=statistics.mean(x['signed'] for x in direction) if direction else None,
                median_signed=statistics.median(x['signed'] for x in direction) if direction else None,
                mean_abs=statistics.mean(x['absolute'] for x in events) if events else None,
                false_signals=sum(x['signed']<=0 for x in direction))


def run():
    raw=acquire()
    bars=normalize(raw['rows'],'1d',raw['asof'],330)
    features=cycle_series(bars)
    events=[]
    previous=None
    for i,f in enumerate(features):
        if f is None:
            continue
        new=f['phase']!=previous
        previous=f['phase']
        if not new or f['phase']=='INDETERMINADO':
            continue
        # Exhaustion/compression do not supply direction. A labelled rebound is
        # separately hypothesized from AO slope, never from falling ADX.
        side=(1 if f['pressure']=='LONG' else -1 if f['pressure']=='SHORT' else 0) if f['phase'] in ('POSIBLE INICIO','ACELERACIÓN','POSIBLE REVERSIÓN') else (1 if f['ao_slope']>0 else -1) if f['countertrend_rebound'] else 0
        for horizon in (1,3,5):
            if i+horizon>=len(bars):
                continue
            entry=bars[i+1]['o']
            future=bars[i+1:i+horizon+1]
            terminal=future[-1]['c']/entry-1
            absolute=max(max(r['h']/entry-1,1-r['l']/entry) for r in future)
            events.append(dict(index=i,available_at=f['available_at'],phase=f['phase'],side=side,horizon=horizon,
                               signed=side*terminal if side else None,absolute=absolute,forward=terminal,
                               era='2020-2022' if datetime.fromtimestamp(f['available_at']/1000,timezone.utc).year<=2022 else '2023-2024' if datetime.fromtimestamp(f['available_at']/1000,timezone.utc).year<=2024 else '2025-2026'))
    tables={}
    for phase in sorted(set(x['phase'] for x in events)):
        for h in (1,3,5):
            tables[phase+' / H'+str(h)]=summary([x for x in events if x['phase']==phase and x['horizon']==h])
    benchmarks=[]
    for cost in (.0018,.0036):
        for phase in sorted(set(x['phase'] for x in events)):
            selected=[]
            next_index=-1
            equity=peak=1.
            drawdown=0.
            for e in [x for x in events if x['phase']==phase and x['horizon']==5 and x['side']]:
                if e['index']<next_index:
                    continue
                next_index=e['index']+6
                net=e['signed']-cost
                equity*=max(0,1+net)
                peak=max(peak,equity)
                drawdown=max(drawdown,1-equity/peak)
                selected.append(net)
            benchmarks.append(dict(phase=phase,cost_bps=cost*10000,n=len(selected),
                mean_net=statistics.mean(selected) if selected else None,
                median_net=statistics.median(selected) if selected else None,
                losing=sum(x<=0 for x in selected),equity_1x=equity,max_terminal_drawdown=drawdown))
    eras={era:summary([x for x in events if x['era']==era and x['horizon']==5]) for era in ('2020-2022','2023-2024','2025-2026')}
    manifest={k:v for k,v in raw.items() if k!='rows'}
    manifest.update(first_open=bars[0]['ts'],last_closed=bars[-1]['close_ts'],rows=len(bars),
        data_sha256=hashlib.sha256(json.dumps(raw['rows'],separators=(',',':')).encode()).hexdigest(),
        no_virgin_holdout=True,funding='EXCLUDED_NOT_ACCOUNT_PNL')
    result=dict(manifest=manifest,tables=tables,benchmarks=benchmarks,eras=eras,
                current_observation=features[-1],conclusion='INCONCLUSIVE — FORWARD OBSERVATION REQUIRED')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'IGOD_DAILY_CYCLE_VALIDATION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# I-GOD Daily Cycle V1 — validación exploratoria','',
           '**SHADOW ONLY. TRADE AUTHORITY: NONE. NO VIRGIN HOLDOUT.**','',
           'Definiciones fijadas en docs/IGOD_DAILY_SPECIFICATION.md antes de ejecutar estos outcomes. No búsqueda de parámetros.',
           'Datos: BTCUSDT Binance USD-M perpetual, daily REST público, velas cerradas.',
           f"n velas={len(bars)}; primer open={bars[0]['ts']}; último cierre={bars[-1]['close_ts']}; SHA256={manifest['data_sha256']}",'',
           '## Episodios de fase','',
           '| Fase / horizonte | n | n direccional | media signed | mediana signed | falsos (signed≤0) | excursión abs media |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for key,v in tables.items():
        lines.append(f"| {key} | {v['n']} | {v['n_directional']} | {v['mean_signed']} | {v['median_signed']} | {v['false_signals']} | {v['mean_abs']} |")
    lines+=['','## Benchmark descriptivo no solapado, 5 días','',
            'Entrada al siguiente open teórico y salida a cinco cierres. NO es el plan de dos tramos ni una entrada observada en producción.',
            'Equity normalizada 1×, sin stop/TP/funding. DD solo entre salidas; subestima riesgo intratrade.',
            'ADX descendente no determina el lado. Compresión sin presión direccional se excluye del benchmark firmado.','',
            '| Fase | bps ida/vuelta | n | media net | mediana net | pérdidas | equity 1× | DD terminal |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for b in benchmarks:
        lines.append(f"| {b['phase']} | {b['cost_bps']} | {b['n']} | {b['mean_net']} | {b['median_net']} | {b['losing']} | {b['equity_1x']} | {b['max_terminal_drawdown']} |")
    lines+=['','## Estabilidad temporal','',json.dumps(eras,ensure_ascii=False),'',
            '## Conclusión y límites','',
            '**INCONCLUSIVE — FORWARD OBSERVATION REQUIRED.** No se declara un edge ni se selecciona la fase más rentable.',
            'Hay falsas señales y costes. No hay holdout virgen, corrección por selección histórica previa, intervalos inferenciales independientes ni validación prospectiva madura.',
            'El benchmark no valida la geometría A/B, rechazos 15m futuros, funding, fills o riesgo conjunto del plan. Eso requiere observación adicional independiente.',
            'Las observaciones forward del nuevo servicio comienzan en activación; no se importan estos episodios al journal prospectivo.','',
            '## CURRENT OBSERVATION — NOT PART OF VALIDATION','',json.dumps(features[-1],ensure_ascii=False),'',
            'Esta lectura usa exclusivamente el último día cerrado. No es una orden ni una garantía.']
    (OUT/'IGOD_DAILY_CYCLE_VALIDATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(rows=len(bars),episodes_5d=sum(x['horizon']==5 for x in events),conclusion=result['conclusion'])))


if __name__=='__main__':
    run()
