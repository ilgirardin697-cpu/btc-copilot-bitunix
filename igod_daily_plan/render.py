"""Unicode Telegram-safe text; the existing sender needs no parse-mode change."""
from datetime import datetime, timezone

FOOTER = '\n👀 SHADOW ONLY · MANUAL ONLY\n🚫 NOT AN ORDER · TRADE AUTHORITY: NONE\n🧪 Hipótesis experimental; rentabilidad no validada.'


def price(value):
    return f'{value:,.2f}' if isinstance(value, (int, float)) else 'UNKNOWN'


def render(plan, mode='full', now_ms=None):
    now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    if not plan or plan.get('bias') == 'UNKNOWN':
        return '📊 I-GOD | PLAN DIARIO BTCUSDT\n🟡 ESPERAR\n⚠️ Datos fiables no disponibles; sin entradas ni niveles verificados.' + FOOTER
    stamp = datetime.fromisoformat(plan['asof_utc']).timestamp() * 1000
    age = max(0, int((now_ms - stamp) / 60_000))
    if now_ms < stamp or age > 20:
        return '📊 I-GOD | PLAN DIARIO BTCUSDT\n🟡 ESPERAR\n⚠️ Plan desactualizado; vuelve a consultar /diario.' + FOOTER
    bias = plan['bias']
    title = '🟢 LONG — ESCENARIO CONDICIONAL' if bias == 'SCENARIO_LONG' else '🔴 SHORT — ESCENARIO CONDICIONAL' if bias == 'SCENARIO_SHORT' else '🟡 ESPERAR'
    lines = ['📊 I-GOD | PLAN DIARIO BTCUSDT', title,
             '🕒 ' + plan['asof_utc'] + f' · cálculo hace {age} min',
             'Fuente: BTCUSDT · BINANCE_USDM_PERPETUAL · CLOSED ONLY']
    if plan.get('reference_closed_at_utc'):
        closed = datetime.fromisoformat(plan['reference_closed_at_utc']).timestamp() * 1000
        lines += ['Datos 15m: ' + plan['reference_closed_at_utc'] + f' · hace {max(0,int((now_ms-closed)/60000))} min']
    cycle = plan.get('cycle') or {}
    lines += ['\n🔄 CICLO DIARIO: ' + cycle.get('phase', 'UNKNOWN')]
    if cycle.get('countertrend_rebound'):
        lines += ['⚠️ Rebote contra tendencia; cambio de tendencia NO confirmado.']
    if cycle.get('phase') == 'POSIBLE REVERSIÓN':
        lines += ['Giro posible con ruptura diaria; comprobar 4H/1H y 15m.']
    if mode == 'summary':
        lines += ['Sesgo: ' + bias, 'Confirmación entrada 15m: PENDIENTE',
                  'Detalle /diario · niveles /niveles · avisos /alertas']
        return '\n'.join(lines) + FOOTER
    if mode != 'levels':
        for key, label in (('weekly', '📆 SEMANAL'), ('daily', '📉 DIARIO')):
            v = plan.get('indicators', {}).get(key)
            if v:
                lines += ['\n' + label + ' · cierre ' + v['closed_at'],
                          f"AO {v['ao']:.2f} · Δ {v['ao']-v['ao_previous']:+.2f}",
                          f"ADX {v['adx']:.2f} · Δ {v['adx']-v['adx_previous']:+.2f} · fuerza, no dirección",
                          f"+DI {v['plus_di']:.2f} / −DI {v['minus_di']:.2f}",
                          f"BBWP proxy {v['bbwp_previous']:.1f} → {v['bbwp']:.1f}"]
        lines += ['\n🔍 4H / 1H']
        for tf in ('4h', '1h'):
            v = plan.get('timeframe_context', {}).get(tf, {})
            lines += [tf.upper() + ': tendencia ' + v.get('sma200_bias', 'UNKNOWN') + ' · estructura ' + v.get('confirmed_pivot_structure', 'UNKNOWN')]
    levels = plan.get('structural_levels', {})
    lines += ['\n📏 SOPORTES: ' + (' · '.join(price(x['price']) for x in levels.get('supports', [])[:2]) or 'UNKNOWN'),
              '📏 RESISTENCIAS: ' + (' · '.join(price(x['price']) for x in levels.get('resistances', [])[:2]) or 'UNKNOWN')]
    for i, leg in enumerate(plan.get('entries', []), 1):
        tp = next((t for t in plan.get('targets', []) if t['for_entry'] == leg['name']), {})
        lines += [f"\n🎯 ENTRADA {leg['name']}: {price(leg['entry_zone_center'])}",
                  f"TP{i} (tramo {leg['name']}): {price(tp.get('structural_take_profit'))}",
                  'Condicional: nueva vela 15m cerrada y estructura válida.']
    if not plan.get('entries'):
        lines += ['\n🎯 ENTRADAS A/B + TP1/TP2: SIN ESCENARIO CONFIRMADO']
    invalidation = plan.get('invalidation') or {}
    lines += ['\n🛑 STOP / INVALIDACIÓN: ' + price(invalidation.get('hard_stop_both_legs'))]
    risk = plan.get('risk')
    if risk:
        lines += [f"🛡️ RIESGO CONJUNTO MODELADO: {risk['max_risk_pct']}% / {risk['maximum_combined_estimated_loss_usdt']} USDT",
                  'Capital de ejemplo: 140 USDT; no saldo de cuenta. Gaps/funding no garantizados.']
    else:
        lines += ['🛡️ Sin tamaño autorizado; riesgo del ejemplo ≤0,5% conjunto, pendiente de niveles.']
    lines += ['\n❌ Cancelar si rompe invalidación, pierde estructura, faltan datos o desaparece confluencia.',
              'No promediar pérdidas ni añadir el tramo B tras invalidación.']
    if plan.get('reason_no_trade'):
        lines += ['Motivo: ' + plan['reason_no_trade']]
    lines += ['Paridad exacta Bitman AO/volatilidad: NOT PROVEN.']
    return '\n'.join(lines)[:3900-len(FOOTER)] + FOOTER
