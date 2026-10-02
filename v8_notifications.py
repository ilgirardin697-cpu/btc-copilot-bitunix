"""Pure text renderer. No strategy, state writer or execution capability."""


def render_v8_notification(message, configuration_enabled=False, disarm_file=False):
    separate = 'ℹ️ Esta es la estrategia V8. NO es la decisión del Manual Copilot.'
    disarmed = not configuration_enabled or disarm_file
    if message.startswith('V8 SIGNAL '):
        side = message.removeprefix('V8 SIGNAL ')
        directions = {'LONG': '🟢 LONG detectado', 'SHORT': '🔴 SHORT detectado',
                      'FLAT': '⚪ FLAT detectado — objetivo sin exposición'}
        signal = directions.get(side, '⚫ Señal no interpretable')
        status = ('🔒 EJECUCIÓN REAL DESARMADA\n❌ V8 NO HA ABIERTO UNA OPERACIÓN POR ESTA SEÑAL.' if disarmed else
                  '⚠️ Ejecución real habilitada por configuración, sujeta a los gates V8.\n'
                  'Esta señal NO confirma que se haya ejecutado una operación.')
        return '\n\n'.join(['🤖 V8 STRATEGY SIGNAL', signal, status, separate])
    if message in ('V8 REAL LONG OPENED', 'V8 REAL SHORT OPENED'):
        return '🤖 V8 REAL\n✅ APERTURA REAL CONFIRMADA\n\n' + separate
    if message == 'V8 REAL POSITION CLOSED':
        return '🤖 V8 REAL\n✅ CIERRE REAL CONFIRMADO\n\n' + separate
    if message == 'V8 REAL ARMED':
        return '🤖 V8 REAL\n⚠️ EJECUCIÓN REAL ARMADA\nEste estado NO confirma una apertura.\n\n' + separate
    if message == 'V8 REAL DISARMED':
        return '🤖 V8 REAL\n🔒 EJECUCIÓN REAL DESARMADA\nNo afirma que posiciones anteriores hayan desaparecido.\n\n' + separate
    if message.startswith('V8 REAL BLOCKED — '):
        disabled_gate = message == 'V8 REAL BLOCKED — V8_LIVE_EXECUTION=false or DISARM'
        status = '🔒 EJECUCIÓN REAL DESARMADA' if disabled_gate or disarmed else '⚠️ GATES V8 BLOQUEARON LA ACTUACIÓN'
        return ('🤖 V8 — ACTUACIÓN BLOQUEADA\n' + status
                + '\nEsta notificación NO confirma ejecución ni cierre de órdenes pendientes.\n'
                'Una incertidumbre requiere reconciliación de lectura.\n\n' + separate)
    return '🤖 V8 STRATEGY STATUS\nEstado no interpretable; consultar el journal V8.\n\n' + separate
