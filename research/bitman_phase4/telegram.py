"""Presentation only: no transport, bot, poller, account or sizing capability."""

BANNERS={'LONG':'🟢 BITMAN LONG','SHORT':'🔴 BITMAN SHORT','FORMING':'🟡 BITMAN FORMING',
         'WAIT':'⚪ BITMAN WAIT','BLOCKED':'🛑 BITMAN BLOCKED'}


def number(x):return 'UNAVAILABLE' if x is None else f'{x:,.3f}'


def render(s):
    state=s.get('state','BLOCKED');classification=s.get('research_classification','INCONCLUSIVE')
    # No forward sample exists in this phase. A cannot be fabricated by a caller.
    grade='B' if classification=='PROMISING FOR SHADOW' else 'C'
    lines=[BANNERS.get(state,BANNERS['BLOCKED']),f"₿ BTCUSDT · {s.get('timeframe','UNKNOWN')}",
        '🧪 DIRECTIONAL CONFLUENCE · HIPÓTESIS RESEARCH',f"Familia: {s.get('family','UNAVAILABLE')}",
        '', '📦 Konkorde',s.get('konkorde','KONKORDE_PROXY · contexto no disponible'),
        'EXACT BITMAN KONKORDE PARITY: NOT PROVEN',
        '', '⚡ Oscillator',f"AO: {number(s.get('ao'))} · pendiente: {number(s.get('ao_slope'))}",
        f"Ancla: {s.get('anchor','UNAVAILABLE')} · retraso ADX: {s.get('anchor_age','UNAVAILABLE')} velas",
        '', '💪 ADX / DI',f"ADX14: {number(s.get('adx'))} · pendiente: {number(s.get('adx_slope'))}",
        f"+DI: {number(s.get('di_plus'))} · -DI: {number(s.get('di_minus'))}",
        '', '🌡️ BBWP',f"CLOSE/SMA7/100: {number(s.get('bbwp'))}% · pendiente: {number(s.get('bbwp_slope'))}",
        '50 es referencia pública; paridad del indicador privado de volatilidad NO probada.',
        '', '🧠 RSI: PRIVATE / PARITY NOT PROVEN · EXCLUIDO',
        '🧭 Trend Speed: NOT IMPLEMENTED / FORMULA NOT VERIFIED',
        '',f'📚 EVIDENCE GRADE: {grade}',
        'B = evidencia histórica que supera gates; C = evidencia insuficiente/rechazada.',
        'A requiere validación forward independiente: NO DISPONIBLE.',
        'El grade NO es probabilidad y NO controla sizing.',
        '', '👀 RAZONES']+s.get('reasons',['Datos o evidencia no suficientes'])
    lines+=['',f'Resultado research: {classification}',
        'No es la decisión del Manual Copilot ni una señal V8.',
        '👻 SHADOW ONLY · NO permiso de entrada', '🚫 REAL ORDER: NO','🚫 TRADE AUTHORITY: NONE']
    return '\n'.join(lines)
