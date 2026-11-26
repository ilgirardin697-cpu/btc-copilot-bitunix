"""Pure manual presentation. No clients, environment, stores or order authority."""
from datetime import datetime,timezone
from decimal import Decimal
from .model import ERROR_CODES

FOOTER='\n\nSHADOW ONLY · LECTURA ÚNICAMENTE\nProtección automática DESARMADA\nTRADE AUTHORITY: NONE'
LABELS={'ABSENT':'❌ SIN STOP registrado','INSUFFICIENT':'🟠 STOP INSUFICIENTE',
        'UNVERIFIABLE':'⚠️ STOP NO VERIFICABLE','FULL_REGISTERED':'🛡️ Cantidad cubierta por SL registrado'}

def price(value):
    return 'No disponible' if value is None else f'{Decimal(str(value)):,.2f}'

def render_view(command,view,now):
    if not isinstance(view,dict):return '⚠️ Lectura HEDGE/CROSS no disponible'+FOOTER
    stamp=view.get('completed_at');age=now-stamp if isinstance(stamp,(int,float)) else -1
    if view.get('read_complete') is not True or not 0<=age<=30:
        code=view.get('error','READ_STALE')
        return ('⚠️ LECTURA HEDGE/CROSS NO VERIFICABLE\nNo se afirma que la cuenta esté protegida.\n'
            +'Código: '+(code if code in ERROR_CODES else 'READ_UNAVAILABLE')+FOOTER)
    rows=[p for p in view['positions'] if p['symbol']=='BTCUSDT'];a=view['account'];risk=view['risk']
    title='💼 POSICIONES BTCUSDT' if command=='/position' else '🛡️ RIESGO BTCUSDT Y CUENTA USDT'
    lines=[title,'Lectura Bitunix · cuenta principal · '+a['position_mode'],
        'UTC: '+datetime.fromtimestamp(stamp,timezone.utc).strftime('%d/%m %H:%M:%S')+f' · hace {age:.0f}s']
    if not rows:lines.append('\nSin posición BTCUSDT abierta; no se inventa exposición.')
    for p in rows:
        c=p['coverage'];lines+=['\n'+('🟢 ' if p['side']=='LONG' else '🔴 ')+p['side']+' · ID '+p['position_id'],
            f"{p['margin_mode']} · {p['leverage']}x · {p['qty']} BTC · entrada {price(p['entry'])}",
            f"Mark {price(p['mark'])} · margen {price(p['margin'])} USDT",
            f"Realizado* {price(p['realized'])} · flotante {price(p['unrealized'])} USDT",
            'Liquidación informada: '+price(p['liquidation'])]
        if p['liquidation_state']=='DOCUMENTED_NO_CURRENT_ESTIMATE':lines.append('Sin estimación actual según API (≤0); no es garantía de seguridad.')
        elif p['liquidation_state']=='DIRECTIONAL_INTERPRETATION_UNVERIFIED':lines.append('⚠️ Referencia CROSS no interpretable como liquidación aislada.')
        elif p['liquidation_distance'] is not None:lines.append(f"Distancia a referencia: {p['liquidation_distance']:.2%}")
        lines.append(LABELS[c['status']]+f" · {min(c['covered_qty'],p['qty'])}/{p['qty']} BTC")
        for kind,label in (('tp','TP'),('sl','SL')):
            orders=c[kind]
            lines.append(label+': '+('; '.join(f"ID {o['id']} @ {price(o['price'])} · {o['qty']} BTC · {o['trigger']}/{o['type']}" for o in orders) if orders else 'ninguno verificable'))
        if c['issues']:lines.append('⚠️ '+', '.join(c['issues']))
    btc_gross=sum((p['qty'] for p in rows),Decimal(0));btc_net=sum((p['qty']*(1 if p['side']=='LONG' else -1) for p in rows),Decimal(0))
    lines+=['\n📊 EXPOSICIÓN Y CUENTA',f'BTCUSDT bruta {btc_gross} BTC · neta {btc_net} BTC',
        'Bruta USDT (todas las posiciones): '+price(view['gross_notional']),
        'Neta BTCUSDT: '+price(view['net_notional_by_symbol'].get('BTCUSDT',0))+' USDT',
        'Margen utilizado cuenta: '+price(a['margin'])+' · congelado órdenes: '+price(a['frozen']),
        'Disponible informado: '+price(a['available'])+' USDT',
        'Disponible + PnL CROSS: '+price(a['available_plus_cross_pnl'])+' USDT',
        'Equity por componentes*: '+price(a['equity_components'])+' USDT',
        'PnL flotante cuenta: '+price(a['crossUnrealizedPNL']+a['isolationUnrealizedPNL'])+' USDT',
        'Cuadre PnL cuenta/posiciones: '+('SÍ' if view['pnl_reconciled'] else 'NO VERIFICADO'),
        'Realizado posiciones abiertas*: '+price(view['position_sums']['realized'])+' USDT',
        'Comisiones informadas: '+price(view['position_sums']['fees'])+' · funding firmado: '+price(view['position_sums']['funding']),
        '\n⚠️ RIESGO AGREGADO: '+risk['status'],
        ', '.join(risk['reasons']) if risk['reasons'] else 'Cobertura registrada; riesgo de liquidación global no certificado.',
        'CROSS comparte colateral. Neto pequeño/cero no implica riesgo cero.',
        'TP no sustituye SL. Una orden pendiente no garantiza fill ante gaps.',
        '*Realizado excluye costes; ya está en el saldo. Equity suma componentes una vez.',
        'Lecturas no atómicas; no se inventa margen de mantenimiento ni liquidación agregada.']
    text='\n'.join(lines)+FOOTER
    if len(text)>3900:
        # Never silently select the first/largest side to make a message fit.
        return ('⚠️ PANEL HEDGE/CROSS EXCEDE EL LÍMITE\n'+str(len(rows))+' posiciones BTCUSDT; no se oculta ni se selecciona un lado.\n'
            +'Riesgo agregado: '+risk['status']+'\nDetalle completo requiere revisión. Protección no certificada.'+FOOTER)
    return text
