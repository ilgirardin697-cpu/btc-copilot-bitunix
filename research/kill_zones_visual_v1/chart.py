"""Deterministic standalone SVG; all candles are supplied, never fabricated here."""
from html import escape
from .model import HOUR, iso


def svg_chart(bars, result, title, preview_side='UP'):
    setup = result.get('setup')
    if setup is None:
        return unavailable_chart(bars, result, title)
    conf = result['confirmation']
    side = conf['side'] if conf else preview_side
    if side not in ('UP', 'DOWN'):
        raise ValueError('SIDE_INVALID')
    copy = conf['copy'] if conf else setup.projection(side)
    target = copy.b.p if side == 'UP' else copy.a.p
    visible = [b for b in bars if setup.asia.start - HOUR <= b.open_time < setup.expires_at
               and b.open_time + HOUR <= result['as_of']]
    if not visible:
        raise ValueError('NO_CLOSED_BARS_TO_DRAW')
    points = [setup.measurement.a, setup.measurement.b, copy.a, copy.b]
    tlo = min([b.open_time for b in visible] + [p.t for p in points]) - HOUR
    thi = max([b.open_time for b in visible] + [p.t for p in points]) + 2 * HOUR
    lows = [float(b.low) for b in visible] + [float(p.p) for p in points]
    highs = [float(b.high) for b in visible] + [float(p.p) for p in points]
    plo, phi = min(lows), max(highs)
    pad = max((phi - plo) * .14, phi * .001)
    plo, phi = plo - pad, phi + pad
    x = lambda t: 95 + (t - tlo) / (thi - tlo) * 1210
    y = lambda p: 590 - (float(p) - plo) / (phi - plo) * 420
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="830" viewBox="0 0 1400 830">',
             '<rect width="1400" height="830" fill="#101824"/>',
             '<style>text{fill:#edf1f7;font-family:Arial,sans-serif;font-size:14px}</style>',
             '<defs><clipPath id="plot"><rect x="95" y="170" width="1210" height="420"/></clipPath></defs>']

    def text(tx, ty, label, color=None, size=14):
        parts.append(f'<text x="{tx:.2f}" y="{ty:.2f}" style="font-size:{size}px;fill:{color or "#edf1f7"}">{escape(str(label))}</text>')

    def line(t1, p1, t2, p2, color, dash='', width=2):
        parts.append(f'<line x1="{x(t1):.3f}" y1="{y(p1):.3f}" x2="{x(t2):.3f}" y2="{y(p2):.3f}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')

    text(35, 35, title, size=20)
    text(35, 62, 'SINGLE MEASUREMENT + TRANSLATED COPY | LINE-BREAK HYPOTHESIS | NOT VIDEO PARITY', '#f8c15d')
    text(35, 89, f'Day {setup.day} | America/New_York | linear price | 1H closed only | as_of {iso(result["as_of"])}')
    text(35, 116, 'Magenta: original segment | cyan: one clone | orange dashed: extension of SAME segment | yellow: sessions')
    for i in range(6):
        p = plo + (phi - plo) * i / 5
        parts.append(f'<path d="M95 {y(p):.3f} H1305" stroke="#273648"/>')
        text(8, y(p) + 4, f'{p:,.2f}')
    parts.append('<g clip-path="url(#plot)">')
    for b in (setup.asia, setup.london):
        parts.append(f'<rect x="{x(b.start):.3f}" y="{y(b.high):.3f}" width="{x(b.end)-x(b.start):.3f}" height="{y(b.low)-y(b.high):.3f}" fill="#ead067" fill-opacity=".10" stroke="#ead067" stroke-width="2"/>')
        text(x(b.start) + 3, y(b.high) - 6, b.name, '#ead067')
    for b in visible:
        color = '#37cf91' if b.close >= b.open else '#f37b79'
        line(b.open_time, b.low, b.open_time, b.high, color, width=1)
        top, bottom = y(max(b.open, b.close)), y(min(b.open, b.close))
        width = min(14, (x(b.open_time + HOUR) - x(b.open_time)) * .65)
        parts.append(f'<rect x="{x(b.open_time)-width/2:.3f}" y="{top:.3f}" width="{width:.3f}" height="{max(1,bottom-top):.3f}" fill="{color}"/>')
    m = setup.measurement
    line(tlo, m.at(tlo), thi, m.at(thi), '#f8a54e', '7 5')
    for segment, color, labels in ((m, '#f061b1', ('A', 'B')), (copy, '#5ad8ec', ("A'", "B'"))):
        line(segment.a.t, segment.a.p, segment.b.t, segment.b.p, color, width=4)
        for p, label in zip((segment.a, segment.b), labels):
            parts.append(f'<circle cx="{x(p.t):.3f}" cy="{y(p.p):.3f}" r="5" fill="{color}"/>')
            text(x(p.t) + 8, y(p.p) - 8, label, color)
    line(setup.available_at, target, thi, target, '#5ad8ec', '4 4')
    if conf:
        parts.append(f'<circle cx="{x(conf["candle_open"]):.3f}" cy="{y(conf["signal_close"]):.3f}" r="12" fill="none" stroke="#fff" stroke-width="2"/>')
        line(conf['available_at'], conf['stop'], thi, conf['stop'], '#f37b79', '5 5')
        plan = result['plan']
        if 'reference_entry' in plan:
            parts.append(f'<circle cx="{x(plan["entry_at"]):.3f}" cy="{y(plan["reference_entry"]):.3f}" r="5" fill="#fff"/>')
    parts.append('</g>')
    for t in range((tlo // (3 * HOUR) + 1) * 3 * HOUR, thi, 3 * HOUR):
        text(x(t) - 20, 614, iso(t)[11:16])
    text(95, 642, 'Horizontal axis: UTC bar OPEN; confirmation becomes available one hour later.')
    text(35, 677, f'{result["status"]} | copy {side} | projected target {target}' + (' | GEOMETRY PREVIEW, NO SIGNAL' if not conf else ''))
    if conf:
        text(35, 706, f'Confirmed at {iso(conf["available_at"])} | next-open plan: {result["plan"]["status"]} | SL {conf["stop"]}')
    else:
        text(35, 706, 'No qualifying closed-body line crossing. No confirmation or simulated entry invented.')
    text(35, 745, 'Target time component preserves the clone vector; it does NOT predict a time-to-target.', '#f8c15d')
    text(35, 774, 'NO PERFORMANCE EVALUATION | NO VIRGIN HOLDOUT | SHADOW ONLY | TRADE AUTHORITY: NONE', '#f8c15d')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def unavailable_chart(bars, result, title):
    """Show the actual boxes/candles without inventing unresolved geometry."""
    boxes = result.get('session_boxes')
    if not boxes:
        raise ValueError('NO_CLOSED_SESSIONS_TO_DRAW')
    lo, hi = boxes[0].start - HOUR, min(result['as_of'], result['expires_at'])
    visible = [b for b in bars if lo <= b.open_time < hi and b.open_time + HOUR <= result['as_of']]
    floor, ceiling = min(b.low for b in visible), max(b.high for b in visible)
    pad = (ceiling-floor)/10
    floor, ceiling = floor-pad, ceiling+pad
    x = lambda t: 90 + (t-lo)/(hi-lo)*1200
    y = lambda p: 590-float((p-floor)/(ceiling-floor))*410
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="750" viewBox="0 0 1400 750">',
         '<rect width="1400" height="750" fill="#101824"/>',
         '<style>text{fill:#edf1f7;font:15px Arial}</style>',
         f'<text x="35" y="40">{escape(title)}</text>',
         f'<text x="35" y="75">UNAVAILABLE: {escape(result["reason"])}</text>',
         '<text x="35" y="110">Boxes retained; no segment, clone, confirmation or entry forced.</text>']
    for b in boxes:
        s.append(f'<rect x="{x(b.start):.3f}" y="{y(b.high):.3f}" width="{x(b.end)-x(b.start):.3f}" height="{y(b.low)-y(b.high):.3f}" fill="#ead067" fill-opacity=".12" stroke="#ead067"/>')
        s.append(f'<text x="{x(b.start):.3f}" y="{y(b.high)-10:.3f}">{b.name}</text>')
    for b in visible:
        c = '#37cf91' if b.close >= b.open else '#f37b79'
        s.append(f'<line x1="{x(b.open_time):.3f}" y1="{y(b.high):.3f}" x2="{x(b.open_time):.3f}" y2="{y(b.low):.3f}" stroke="{c}"/>')
        s.append(f'<rect x="{x(b.open_time)-5:.3f}" y="{y(max(b.open,b.close)):.3f}" width="10" height="{max(1,y(min(b.open,b.close))-y(max(b.open,b.close))):.3f}" fill="{c}"/>')
    s.extend([f'<text x="35" y="630">UTC: {iso(lo)} to {iso(hi)} | 1H closed candles | linear price</text>',
              '<text x="35" y="670">HISTORICAL GEOMETRY AUDIT ONLY | NO PERFORMANCE EVALUATION</text>',
              '<text x="35" y="705">SHADOW ONLY | TRADE AUTHORITY: NONE</text>', '</svg>'])
    return '\n'.join(s)+'\n'
