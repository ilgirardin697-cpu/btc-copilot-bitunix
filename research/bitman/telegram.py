"""Pure SHADOW renderer. No Telegram transport, token, poller or order function."""
import math

BANNERS={
    'LONG':'🟢🔥 BITMAN LONG CONFIRMED 🚀',
    'SHORT':'🔴🔥 BITMAN SHORT CONFIRMED 📉',
    'SETUP_FORMING':'🟡👀 BITMAN SETUP FORMING',
    'WAIT':'⚪⏳ BITMAN WAIT — ESPERAR',
    'BLOCKED':'🛑 BITMAN BLOCKED',
    'DATA_RISK_ERROR':'⚠️ BITMAN DATA/RISK ERROR',
}


def number(value,decimals=2):
    return f'{value:,.{decimals}f}' if isinstance(value,(int,float)) and math.isfinite(value) else 'NA'


def render(snapshot):
    state=snapshot.get('state','DATA_RISK_ERROR')
    lines=[BANNERS.get(state,BANNERS['DATA_RISK_ERROR']), '', '₿ BTCUSDT · 1H',
           '📡 Source: BINANCE USD-M PERPETUAL', '🔬 PUBLIC BITMAN-INSPIRED PROXY', '']
    lines+=['🧭 TREND']
    for tf in ('1H','4H','1D'):
        trend=snapshot.get('trend',{}).get(tf,'UNKNOWN')
        lines.append(f"{tf} "+{'BULL':'🟢 BULL','BEAR':'🔴 BEAR'}.get(trend,'⚫ UNKNOWN'))
    lines+=['',f"🧠 RSI CLOUD: {snapshot.get('cloud','UNKNOWN')}",
        f"💪 ADX14: {number(snapshot.get('adx'),1)} {snapshot.get('adx_arrow','?')}",
        f"⚡ MOMENTUM: {snapshot.get('momentum','UNKNOWN')}",
        f"🌡️ BBWP: {snapshot.get('bbwp_state','UNKNOWN')} ({number(snapshot.get('bbwp'),1)}%)",
        f"🏗️ STRUCTURE: {snapshot.get('structure','UNKNOWN')}",
        f"📍 VPOC PROXY: {snapshot.get('vpoc','UNAVAILABLE')}",
        f"🤖 ML RSI 1H: {snapshot.get('mlrsi','UNAVAILABLE')} (diagnóstico salvo filtro explícito)", '']
    conditions=snapshot.get('conditions',{})
    if conditions:
        passed=sum(value is True for value in conditions.values())
        lines+=['🔥 CONFLUENCE — bloques activos',
                ''.join('🟩' if v is True else '⬜' for v in conditions.values()),f'{passed} / {len(conditions)}']
        if state in ('SETUP_FORMING','WAIT','BLOCKED'):
            lines+=['', '👀 QUÉ FALTA']+[('✅ ' if v is True else '❌ ')+name for name,v in conditions.items()]
    if state in ('LONG','SHORT') and all(isinstance(snapshot.get(k),(int,float)) and math.isfinite(snapshot[k]) and snapshot[k]>0 for k in ('entry','atr')):
        direction=1 if state=='LONG' else -1
        entry=snapshot['entry']; distance=snapshot['atr']*snapshot.get('stop_atr',2.)
        lines+=['',f'💰 ENTRY REFERENCE: {number(entry)}',f'🛡️ SL TEÓRICO: {number(entry-direction*distance)}',
                f'🎯 TP1 TEÓRICO (30%): {number(entry+direction*distance)}',
                f'🎯 TP2 TEÓRICO (30%): {number(entry+direction*2*distance)}',
                f"🏃 RUNNER (40%): {number(snapshot.get('trail_atr',2.),1)} ATR trailing",
                f'📊 Riesgo teórico SL a1x: {distance/entry*100:.2f}% antes de costes/gaps',
                'Referencia al cierre; fill de investigación: siguiente apertura adversa.']
    if snapshot.get('reason'): lines+=['',str(snapshot['reason'])]
    lines+=['', '✅ CLOSED 1H CANDLES ONLY', '👻 MODE: SHADOW ONLY',
            '🚫 REAL ORDER: NO', '🚫 TRADE AUTHORITY: NONE',
            'No es la decisión del Manual Copilot ni modifica Guardian/V8.']
    return '\n'.join(lines)
