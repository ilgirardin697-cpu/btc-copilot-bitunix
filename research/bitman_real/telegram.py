"""Pure text renderer. No sending, Telegram credentials, or polling."""
from datetime import datetime,timezone
from .config import SHORT_PROVEN

BANNERS={'LONG':'🟢 LONG','SHORT':'🔴 SHORT','SETUP_FORMING':'🟡 SETUP FORMING',
         'WAIT':'⚪ WAIT','BLOCKED':'🛑 BLOCKED'}


def num(x):return 'UNAVAILABLE' if x is None else f'{x:,.4f}'


def sign(x):return 'UNAVAILABLE' if x is None else 'RISING' if x>0 else 'FALLING' if x<0 else 'STABLE'


def render(s):
    state=s.get('state','BLOCKED')
    if state=='SHORT' and not SHORT_PROVEN:state='BLOCKED'
    event=s.get('event')
    title={'KONKORDE_ENTRY':'🟢📊 BITMAN KONKORDE ENTRY','KONKORDE_EXIT':'🔴📊 BITMAN KONKORDE EXIT',
           'KONKORDE_REENTRY':'🟡🔁 BITMAN KONKORDE REENTRY'}.get(event,'⚪ BITMAN WAIT')
    stamp=s.get('candle_close')
    when=datetime.fromtimestamp(stamp/1000,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if stamp else 'UNAVAILABLE'
    inside=s.get('inside')
    di='UNAVAILABLE' if s.get('di_plus') is None or s.get('di_minus') is None else 'BULL' if s['di_plus']>s['di_minus'] else 'BEAR' if s['di_plus']<s['di_minus'] else 'NEUTRAL'
    location='INSIDE MOUNTAIN' if inside else 'OUTSIDE MOUNTAIN' if inside is not None else 'UNAVAILABLE'
    if event in ('KONKORDE_ENTRY','KONKORDE_REENTRY'):location='ENTERED MOUNTAIN ✅'
    if event=='KONKORDE_EXIT':location='LEFT MOUNTAIN'
    lines=[BANNERS.get(state,BANNERS['BLOCKED']),title,'',f"₿ BTCUSDT · {s.get('timeframe','UNKNOWN')}",
        '📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY',f'Cierre: {when}',f"Precio: {num(s.get('close'))}",
        '', '📦 KONKORDE',f'Media: {location}',f"Montaña: {num(s.get('mountain'))} · EMA15: {num(s.get('ma'))}",
        f"Distance to zero (EMA): {num(s.get('distance_to_zero'))}",
        f"Reentry: {'YES' if s.get('reentry') else 'NO'} · ventana explícita: {s.get('reentry_max_bars','UNSET')} velas",
        f"Mountain/MA separation: {num(s.get('separation'))}",f"Strength: {s.get('strength','UNAVAILABLE')}",
        '', '💪 ADX / DI — CONTEXTO',f"ADX14: {num(s.get('adx'))}",
        f"+DI: {num(s.get('di_plus'))} · -DI: {num(s.get('di_minus'))}",f'DI direction: {di}',f"Slope: {num(s.get('adx_slope'))}",
        '', '⚡ AO — CONTEXTO',f"Value: {num(s.get('ao'))}",
        'State: '+('UNAVAILABLE' if s.get('ao') is None else 'POSITIVE' if s['ao']>0 else 'NEGATIVE' if s['ao']<0 else 'ZERO'),
        f"Slope: {num(s.get('ao_slope'))} ({sign(s.get('ao_slope'))})",
        '', '🌡️ BBWP · CLOSE/SMA7/100',f"Value: {num(s.get('bbwp'))}%",
        'State: '+('UNAVAILABLE' if s.get('bbwp_slope') is None else 'EXPANDING' if s['bbwp_slope']>0 else 'CONTRACTING' if s['bbwp_slope']<0 else 'STABLE'),
        f"Slope: {num(s.get('bbwp_slope'))} · sin zonas optimizadas",
        '', '🧭 Trend Speed','NOT IMPLEMENTED / FORMULA NOT VERIFIED',
        '', '👀 RAZONES']
    lines+=s.get('reasons',['DATOS INSUFICIENTES'])
    lines+=['SHORT_LOGIC_NOT_PROVEN','LONG/SHORT aquí describen contexto; NO permiso de entrada.',
            'EXIT no abre SHORT ni cierra ninguna posición.',
            '', 'EXACT BITMAN KONKORDE PARITY: NOT PROVEN',
            '✅ CLOSED CANDLES ONLY','👻 MODE: SHADOW ONLY','🚫 REAL ORDER: NO','🚫 TRADE AUTHORITY: NONE']
    return '\n'.join(lines)
