"""Pure text renderer. No Telegram transport, credentials, commands or poller."""
BANNERS={'UP':'🟢 BTC DIRECTION: UP','DOWN':'🔴 BTC DIRECTION: DOWN','TRANSITION':'🟡 BTC DIRECTION: TRANSITION',
    'UNCLEAR':'⚪ BTC DIRECTION: UNCLEAR','CONFLICT':'🛑 BTC DIRECTION: CONFLICT'}


def number(x):return 'NO DISPONIBLE' if x is None else f'{x:,.3f}'
def slope(x):return 'NO DISPONIBLE' if x is None else 'RISING' if x>0 else 'FALLING' if x<0 else 'STABLE'
def utc(t):
    from datetime import datetime,timezone
    return datetime.fromtimestamp(t/1000,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if isinstance(t,(float,int)) else 'NO DISPONIBLE'


def render(s):
    state=s.get('state','UNCLEAR');structure=s.get('structure',{});parts=s.get('components',{})
    lines=[BANNERS.get(state,BANNERS['UNCLEAR']),f"💪 STRENGTH: {s.get('strength','WEAK')}",
        f"🏷️ GRADE: {s.get('evidence_grade','C')} · coherencia visual, no probabilidad",
        '₿ BTCUSDT · contexto1D / confirmación4H / timing1H',
        'Referencia cerrada: '+number(s.get('reference_price')),
        'Fuente: '+s.get('venue','BINANCE PUBLIC / RESEARCH FIXTURE'),
        'Cierre conocido: '+utc(s.get('timestamp')),
        f"Lectura: {s.get('detail','DATOS_INSUFICIENTES')}"]
    if structure.get('nearest_resistance') is not None:
        lines+=['🧱 R '+str(structure.get('nearest_resistance_source','confirmada'))+': '+number(structure['nearest_resistance'])+
            ' · '+(f"{structure['resistance_distance_pct']*100:.2f}%" if structure.get('resistance_distance_pct') is not None else 'distancia no verificada')]
    if structure.get('nearest_support') is not None:
        lines+=['🧱 S '+str(structure.get('nearest_support_source','confirmado'))+': '+number(structure['nearest_support'])+
            ' · '+(f"{structure['support_distance_pct']*100:.2f}%" if structure.get('support_distance_pct') is not None else 'distancia no verificada')]
    if structure.get('opposing_up') or structure.get('opposing_down'):
        lines+=['🧱 ATENCIÓN: prueba de nivel mayor opuesto; dirección en conflicto.']
    for tf,icon in (('1D','📅'),('4H','🕓'),('1H','🕐')):
        p=parts.get(tf,{});ml=s.get('confirmed_mlrsi',{}).get(tf,{})
        lines+=['',f'{icon} {tf} · '+utc(p.get('last_closed_at')),f"Direction: {p.get('bias','UNKNOWN')}",
            f"AO: {number(p.get('ao'))} · {p.get('momentum','UNKNOWN')}",
            f"Pendiente: {number(p.get('ao_slope'))} · aceleración: {number(p.get('ao_acceleration'))}",
            f"Zero cross UP/DOWN: {bool(p.get('ao_cross_up'))}/{bool(p.get('ao_cross_down'))} · {p.get('ao_zero_motion','UNKNOWN')}",
            f"DI: {p.get('di_direction','UNKNOWN')} · +DI {number(p.get('di_plus'))} / -DI {number(p.get('di_minus'))}",
            f"ADX: {number(p.get('adx'))} · {slope(p.get('adx_slope'))} · TURN_UP {bool(p.get('adx_turn_up'))}",
            f"ADX delta: {number(p.get('adx_slope'))} · aceleración: {number(p.get('adx_acceleration'))}",
            f"ML RSI CONFIRMED: {ml.get('color','UNKNOWN')} (solo cache; no provisional)",
            f"Konkorde: {p.get('konkorde','UNKNOWN')}",
            f"Separación: {number(p.get('separation'))} · delta {number(p.get('separation_change'))}",
            f"Distancia cero: {number(p.get('distance_to_zero'))}",
            f"BBWP: {number(p.get('bbwp'))}% · {slope(p.get('bbwp_slope'))} · distancia50 {number(p.get('bbwp_distance50'))}"]
    lines+=['',f"🕐 TIMING: {s.get('timing_state','no_impulse')}",'🧱 STRUCTURE',
        f"Soporte: {number(structure.get('nearest_support'))}",f"Resistencia: {number(structure.get('nearest_resistance'))}",
        'Room upward: '+(f"{structure['resistance_distance_pct']*100:.2f}% · {number(structure.get('resistance_distance_atr'))} ATR1H" if structure.get('resistance_distance_pct') is not None else 'NO VERIFICABLE; ausencia de nivel no prueba espacio libre'),
        'Room downward: '+(f"{abs(structure['support_distance_pct'])*100:.2f}% · {number(structure.get('support_distance_atr'))} ATR1H" if structure.get('support_distance_pct') is not None else 'NO VERIFICABLE'),
        f"Contexto: {structure.get('state','INSUFFICIENT_CONFIRMED_LEVELS')}"]
    for tf,values in structure.get('scales',{}).items():
        for kind,v in values.items():
            if v['relationship'].startswith('CROSSED'):lines.append(f"⏳ {tf} {kind}: mark/referencia al otro lado; falta cierre {tf}.")
    tracker=s.get('extension_tracker',{})
    lines+=['','📈 LARGE MOVE TRACKER','DIRECTIONAL_10PCT_EXTENSION',
        'Status: '+tracker.get('status','PENDING_OBSERVATION'),
        'NOT A GUARANTEE · no es take profit',
        'EXACT BITMAN KONKORDE PARITY: NOT PROVEN',
        'GradeA/B/C no es evidencia estadística ni sizing.',
        'ML RSI1D: no existe en el observer actual. No se ha fabricado.',
        '👻 DIRECTIONAL RESEARCH ONLY','🚫 NOT A TRADE SIGNAL','🚫 TRADE AUTHORITY: NONE']
    return '\n'.join(lines)
