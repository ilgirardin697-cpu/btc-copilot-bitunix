"""Offline SVG and FUTURE manual-command text; no Telegram transport or poller."""
from decimal import Decimal
from html import escape
from .core import HOUR, LEVEL_NAMES, iso

COLORS={'HIGH':'#ead067','LOW':'#ead067','SUPERIOR':'#f75d70','INFERIOR':'#42d890'}


def command_preview(snapshot,market):
    p=snapshot['pair'];c=snapshot['confirmation'];r=snapshot['risk']
    lines=['🧭 /killzone — DISEÑO OFFLINE, NO INTEGRADO',market,
           'Reloj: UTC−4 FIJO · velas 1H cerradas',
           'Asia: 5 velas 20–00 · Londres: 4 velas 01–04',
           'Sesiones: '+('COMPLETAS' if p else 'PENDIENTES / DATOS INCOMPLETOS')]
    for name in LEVEL_NAMES:
        v=getattr(snapshot['levels'],name,None)
        lines.append(f'{name}: '+(str(v) if v is not None and snapshot['levels_verified'] else 'NO VERIFICADO'))
    lines.append('Confirmación: '+(c['side']+' · TECHNICAL ONLY' if c else 'NO DETERMINABLE / PENDIENTE'))
    a=snapshot['atr14_context']
    lines.append('ATR14 1H cerrado: '+(str(a['value']) if a and a['value'] is not None else 'UNKNOWN'))
    lines += ['Entrada teórica al cierre: '+(str(c['theoretical_entry']) if c else 'UNKNOWN'),
              'SL: '+(str(r['stop']) if r and r['stop'] is not None else 'UNKNOWN'),
              'TP: '+(str(r['target']) if r else 'UNKNOWN'),
              'B/R neto estimado: '+(str(r['net_rr']) if r and r['net_rr'] is not None else 'UNKNOWN'),
              'PAPER: '+snapshot['paper_decision'],
              'Motivos: '+', '.join(snapshot['reason_codes']),
              'Datos disponibles hasta: '+iso(snapshot['as_of']),
              'Precio ejecutable / latencia: NO OBSERVADOS',
              'SHADOW ONLY · NOT AN ORDER · TRADE AUTHORITY: NONE']
    return '\n'.join(lines)+'\n'


def reference_svg(reference):
    values={k:Decimal(v['value']) for k,v in reference['levels'].items()}
    lo,hi=Decimal('76900'),Decimal('78900')
    y=lambda p:150+float((hi-p)/(hi-lo))*420
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="800" viewBox="0 0 1100 800">',
       '<rect width="1100" height="800" fill="#101824"/>',
       '<style>text{font:18px Arial;fill:#edf1f7}</style>',
       '<text x="30" y="40">ALPHA ARCANOX — transcripción visual de los cuatro niveles</text>',
       '<text x="30" y="77">NO es cálculo del indicador. Sin OHLC, ticker exacto o timestamps verificados.</text>']
    for name in ('SUPERIOR','HIGH','LOW','INFERIOR'):
        p=values[name]
        s += [f'<line x1="110" y1="{y(p):.3f}" x2="770" y2="{y(p):.3f}" stroke="{COLORS[name]}" stroke-width="3"/>',
              f'<text x="790" y="{y(p)+6:.3f}" style="fill:{COLORS[name]}">{name} {p}</text>']
    s += ['<text x="30" y="625">Ninguna vela, entrada o ATR se reconstruye a partir de píxeles.</text>',
          '<text x="30" y="662">Confirmación, entrada, SL y B/R del ejemplo: NO VERIFICABLES.</text>',
          '<text x="30" y="700">Los valores se leen de las etiquetas; las cuatro fórmulas siguen NO VERIFICADAS.</text>',
          '<text x="30" y="752">PAPER BLOQUEADO · SHADOW ONLY · TRADE AUTHORITY: NONE</text>', '</svg>']
    return '\n'.join(s)+'\n'


def session_svg(bars,snapshot,title):
    p=snapshot['pair']
    if p is None:raise ValueError('NO_CLOSED_SESSION_PAIR_TO_DRAW')
    visible=[b for b in bars if p.asia.start<=b.open_time and b.available_at<=snapshot['as_of']]
    if not visible:raise ValueError('NO_CLOSED_CANDLES_TO_DRAW')
    t0,t1=p.asia.start,snapshot['as_of']+HOUR
    low=min(b.low for b in visible);high=max(b.high for b in visible)
    verified=snapshot['levels_verified']
    levels=snapshot['levels']
    if verified:
        low=min(low,levels.INFERIOR);high=max(high,levels.SUPERIOR)
        if snapshot['risk'] and snapshot['risk']['stop'] is not None:
            low=min(low,snapshot['risk']['stop']);high=max(high,snapshot['risk']['stop'])
    pad=max((high-low)/Decimal(6),high/Decimal(1000));low-=pad;high+=pad
    x=lambda t:90+(t-t0)/(t1-t0)*1180
    y=lambda v:590-float((v-low)/(high-low))*400
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="870" viewBox="0 0 1400 870">',
       '<rect width="1400" height="870" fill="#101824"/>',
       '<style>text{font:15px Arial;fill:#edf1f7}</style>',
       f'<text x="30" y="40">{escape(title)}</text>',
       '<text x="30" y="77">DEMO DE SESIONES, NO ES EL EJEMPLO ALPHA · sin fórmula inferida ni señal inventada</text>',
       f'<text x="30" y="112">UTC−4 fijo · Asia 5 velas · Londres 4 velas · as_of {iso(snapshot["as_of"])}</text>']
    for i in range(6):
        v=low+(high-low)*Decimal(i)/5
        s += [f'<path d="M90 {y(v):.3f} H1270" stroke="#29394b"/>',
              f'<text x="5" y="{y(v)+5:.3f}">{float(v):,.2f}</text>']
    for box,color in ((p.asia,'#ead067'),(p.london,'#66bde7')):
        s += [f'<rect x="{x(box.start):.3f}" y="{y(box.high):.3f}" width="{x(box.end)-x(box.start):.3f}" height="{max(1,y(box.low)-y(box.high)):.3f}" fill="{color}" fill-opacity=".12" stroke="{color}"/>',
              f'<text x="{x(box.start)+5:.3f}" y="{y(box.high)-12:.3f}">{box.name} ({len(box.candles)})</text>']
    for b in visible:
        color='#40cf92' if b.close>=b.open else '#f1787d'
        s += [f'<line x1="{x(b.open_time):.3f}" y1="{y(b.high):.3f}" x2="{x(b.open_time):.3f}" y2="{y(b.low):.3f}" stroke="{color}"/>',
              f'<rect x="{x(b.open_time)-6:.3f}" y="{y(max(b.open,b.close)):.3f}" width="12" height="{max(1,y(min(b.open,b.close))-y(max(b.open,b.close))):.3f}" fill="{color}"/>']
    if verified:
        for name in LEVEL_NAMES:
            price=getattr(levels,name)
            s += [f'<line x1="90" y1="{y(price):.3f}" x2="1270" y2="{y(price):.3f}" stroke="{COLORS[name]}" stroke-dasharray="6 4"/>',
                  f'<text x="1040" y="{y(price)-7:.3f}">{name} {price}</text>']
    c=snapshot['confirmation'];r=snapshot['risk']
    if c:
        s += [f'<circle cx="{x(c["candle_open"]):.3f}" cy="{y(c["theoretical_entry"]):.3f}" r="12" fill="none" stroke="#fff"/>',
              f'<text x="30" y="162">{c["side"]}: disponible {iso(c["available_at"])}; entrada teórica {c["theoretical_entry"]}, NO fill real</text>']
    if r and r['stop'] is not None:
        s += [f'<line x1="90" y1="{y(r["stop"]):.3f}" x2="1270" y2="{y(r["stop"]):.3f}" stroke="#fc9c9c"/>',
              f'<text x="800" y="{y(r["stop"])-8:.3f}">SL {r["stop"]}</text>',
              f'<text x="30" y="735">TP {r["target"]} | B/R neto estimado {r["net_rr"]}</text>']
    for t in range(t0,t1,2*HOUR):
        s.append(f'<text x="{x(t)-13:.3f}" y="620">{iso(t)[11:16]}</text>')
    s += ['<text x="90" y="650">Eje UTC. La vela de apertura 00:00 local pertenece a ASIA, no a LONDRES.</text>',
          '<text x="30" y="700">'+('Niveles de una fórmula registrada.' if verified else 'HIGH / LOW / SUPERIOR / INFERIOR: NO VERIFICADOS para este día.')+'</text>',
          '<text x="30" y="780">PAPER: '+snapshot['paper_decision']+' — '+escape(', '.join(snapshot['reason_codes']))+'</text>',
          '<text x="30" y="830">SHADOW ONLY · NO TELEGRAM · NO ORDERS · TRADE AUTHORITY: NONE</text>', '</svg>']
    return '\n'.join(s)+'\n'
