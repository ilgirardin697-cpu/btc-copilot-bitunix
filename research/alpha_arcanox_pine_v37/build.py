"""Reproducible OFFLINE mechanics figures; no PnL or historical optimization."""
import csv
import hashlib
import json
from html import escape
from pathlib import Path
from .core import Candle, project
from .profiles import PINE_A, OWNER_B
from .replay import Replay
from .source_audit import audit, diagnostic_bytes

HERE = Path(__file__).resolve().parent
CASES = (
    ('staggered_asia_lower',100,90,120,110),
    ('staggered_london_lower',120,110,100,90),
    ('overlapping',110,90,120,100),
    ('asia_contains_london',120,80,110,90),
    ('london_contains_asia',110,90,120,80),
    ('identical',110,90,110,90),
    ('zero_height',100,100,100,100),
)


def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True,
                               allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def figure(name,levels):
    v=levels; high=max(v['newTopTarget'],v['highGuideValue'])+8
    low=min(v['newBottomTarget'],v['lowGuideValue'])-8
    def y(p): return 75+(high-p)*450/(high-low)
    items=[]
    def line(x1,p1,x2,p2,color,dash='',width=2):
        items.append(f'<line x1="{x1}" y1="{y(p1):.4f}" x2="{x2}" y2="{y(p2):.4f}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')
    def label(x,p,s,color):
        items.append(f'<text x="{x}" y="{y(p)-6:.4f}" fill="{color}">{escape(s)}</text>')
    for x,hi,lo,text in ((130,v['aHigh'],v['aLow'],'ASIA'),(350,v['lHigh'],v['lLow'],'LONDON')):
        items.append(f'<rect x="{x}" y="{y(hi):.4f}" width="150" height="{max(0,y(lo)-y(hi)):.4f}" fill="#8c652e" fill-opacity=".2" stroke="#edc651"/>')
        label(x,hi,text,'#edc651')
    # Original measurement uses the global extrema (source formula), no diagonal.
    line(75,v['highGuideValue'],75,v['lowGuideValue'],'#64a9ff')
    label(15,v['highGuideValue'],'H','#64a9ff')
    top_x=205 if v['topInAsia'] else 425
    bottom_x=205 if v['bottomInAsia'] else 425
    for x,anchor,target,color in ((top_x,v['topAnchor'],v['newTopTarget'],'#ff6e78'),
                                   (bottom_x,v['bottomAnchor'],v['newBottomTarget'],'#6fe09f')):
        line(x,anchor,x,target,color)
        for p in (anchor,target):
            items.append(f'<circle cx="{x}" cy="{y(p):.4f}" r="4" stroke="{color}" fill="none"/>')
        line(x-60,anchor,x+60,anchor,color,'5 3')
        line(x,target,750,target,color)
    for key,color in (('highGuideValue','#f0d05a'),('lowGuideValue','#f0d05a'),
                      ('newTopTarget','#ff6e78'),('newBottomTarget','#6fe09f')):
        line(90,v[key],750,v[key],color,'3 5')
        label(540,v[key],f'{key}: {v[key]:.4f}',color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="610">'
            '<rect width="1000" height="610" fill="#111b28"/><g font-family="Arial" font-size="13">'
            f'<text x="20" y="28" fill="white">SOURCE-FORMULA FIXTURE — {escape(name)}</text>'
            '<text x="20" y="51" fill="white">SYNTHETIC mechanics; NOT TradingView or Alpha source parity evidence.</text>'
            +''.join(items)+'<text x="20" y="580" fill="white">SHADOW ONLY · TRADE AUTHORITY: NONE · No price outcomes evaluated</text></g></svg>\n')


def main():
    art=HERE/'artifacts';art.mkdir(exist_ok=True)
    write_json(art/'source_audit.json',audit())
    (art/'Killzone_H1_v3_7_Lite_DIAGNOSTIC.pine').write_bytes(diagnostic_bytes())
    rows=[]
    for name,*prices in CASES:
        levels=project(*prices)
        rows.append(dict(case=name,evidence='SYNTHETIC_FORMULA_FIXTURE_NOT_TRADINGVIEW',**levels))
        (art/(name+'.svg')).write_text(figure(name,levels),encoding='utf-8',newline='\n')
    write_json(art/'geometry_cases.json',rows)
    public=HERE/'fixtures/public_sessions_demo.csv'
    bars=[]
    with public.open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            bars.append(Candle(int(r['open_time']),*(float(r[k]) for k in ('open','high','low','close'))))
    traces={}
    for profile in (PINE_A,OWNER_B):
        engine=Replay(profile)
        out=[engine.append(b,as_of=b.available_at) for b in bars]
        # Mechanics only: all measurements and technical confirmations; NO trade returns.
        traces[profile.name]=[x for x in out if x['measureNow'] or x['highConfirmed'] or x['lowConfirmed']]
    write_json(art/'public_mechanics.json',dict(role='PUBLIC_USDM_MECHANICS_NOT_SOURCE_PARITY_OR_PERFORMANCE',
               source_sha256=hashlib.sha256(public.read_bytes()).hexdigest(),profiles=traces))
    write_json(art/'parity_status.json',dict(source_formula_implementation='TESTED_WITH_OWN_FIXTURES',
               real_tradingview_records=0, independent_platform_parity='PENDING',
               alpha_arcanox_original_indicator_parity='NOT_PROVEN',
               old_78285_setup_binding='UNVERIFIED_NOT_USED',
               operational_paper='BLOCKED_PENDING_INDEPENDENT_PARITY',profitability='NOT_EVALUATED'))
    (art/'index.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Killzone Pine V3.7 — investigación</title><style>body{background:#111b28;color:white;font:16px Arial;margin:30px}a{color:#65dbff}img{width:100%;max-width:1000px}</style><h1>Fórmulas Pine V3.7: pruebas de geometría</h1><p>Ejemplos SINTÉTICOS de cajas; no capturas ni resultados TradingView. No prueban rentabilidad ni paridad Alpha.</p>'+''.join('<img alt="'+n+'" src="'+n+'.svg">' for n,*_ in CASES)+'<p><a href="../REPORT.md">Informe</a> · SHADOW ONLY · TRADE AUTHORITY: NONE</p></html>\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    main()
