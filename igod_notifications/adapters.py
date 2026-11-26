"""Presentation adapters. Consume existing decisions; never calculate a strategy."""
import math
import re
from .policy import identity


def event(source,kind,at,what_changed,**fields):
    value=dict(source=source,kind=kind,at=int(at),what_changed=what_changed,**fields)
    value['id']=identity(value)
    return value


def guardian_alert(key,text,now,notice=None):
    """Use explicit legacy alert keys, not changing mark/PnL text for dedupe."""
    family=key.split(':',1)[0]
    routine={'startup','copilot','aligned','conflict','new','manual'}
    if family in routine:
        return event('guardian','OBSERVATION',now,'Rutina conservada internamente',reason=family)
    if key=='blind:recovered':
        return event('guardian','RECOVERED',now,'Lectura privada recuperada',incident_id='guardian:private-read',severity=3,text=text)
    if family=='blind':
        stage=int(key.split(':')[1]) if key.split(':')[1].isdigit() else 3
        cause=notice.get('cause') if isinstance(notice,dict) else None
        cause=cause if isinstance(cause,str) and re.fullmatch(r'[A-Z0-9_]{1,80}',cause) else 'PRIVATE_READ_UNVERIFIED'
        return event('guardian','CRITICAL',now,'No se puede verificar el estado privado de Bitunix',
            incident_id='guardian:private-read',severity=max(1,min(3,stage)),material={'code':cause},text=text)
    if family=='risk':
        severity=3 if key.endswith('EMERGENCY') else 2 if key.endswith('DANGER') else 1
        entity=key.removeprefix('risk:')
        risk_state='UNKNOWN'
        for name in ('EMERGENCY','DANGER','WARNING','NORMAL'):
            if entity.endswith(name):entity=entity[:-len(name)];risk_state=name
        return event('guardian','RECOVERED' if risk_state=='NORMAL' else 'CRITICAL',now,'Cambio de riesgo de capital',incident_id='capital-risk:'+identity(entity),
            severity=severity,material={'code':'CAPITAL_RISK','state':risk_state},text=text)
    if family in {'tpsl','lockout','unresolved','closed','confirmed','intent','response','dry'}:
        material={'code':family}
        if family=='tpsl' and isinstance(notice,dict):
            material['orders_fingerprint']=identity(notice.get('orders'))
            material['target']=notice.get('target')
            material['risk']=notice.get('risk')
        return event('guardian','CRITICAL',now,'Cambio relevante de protección; requiere evidencia del exchange',
            incident_id='guardian:'+family+':'+identity(key.split(':',1)[-1]),severity=3 if family in {'unresolved','lockout'} else 2,
            material=material,text=text)
    # Unknown automatic warnings fail toward safety; they are never treated as
    # an experimental entry or blindly discarded by an opportunity mute.
    return event('guardian','CRITICAL',now,'Aviso automático pendiente de clasificar',
        incident_id='guardian:unclassified:'+identity(key),severity=2,material={'code':family},text=text)


def capital_message(text,now):
    """V2 native callback is safety-only. Never transform it into CONFIRMED."""
    lines=text.splitlines()
    status=lines[1] if len(lines)>1 else 'UNVERIFIED'
    if text.startswith('🚨 GUARDIAN CAPITAL V2:'):
        status='PROTECTION_UNVERIFIED'
    return event('guardian','CRITICAL',now,'Cambio del protector de capital',
        incident_id='capital-v2:'+identity(status),severity=3 if status in ('PROTECTION_UNVERIFIED','RECONCILIATION_REQUIRED') else 2,
        material={'status':status},text=text)


def v8_event(message,now):
    routine=(message.startswith('V8 SIGNAL ') or message=='V8 REAL DISARMED'
             or message=='V8 REAL BLOCKED — V8_LIVE_EXECUTION=false or DISARM')
    if routine:
        return event('v8','OBSERVATION',now,'Estado V8 registrado sin aviso automático',reason='V8_ROUTINE')
    reason=message.removeprefix('V8 REAL BLOCKED — ') if message.startswith('V8 REAL BLOCKED — ') else message
    return event('v8','CRITICAL',now,'Cambio de seguridad V8',incident_id='v8:'+identity(reason),
        severity=3 if ('unresolved' in reason or 'uncertainty' in reason or 'ARMED' in reason) else 2,
        material={'code':reason},text=message)


def copilot_snapshot(policy,snapshot,now):
    """Map existing WAIT_RECLAIM/CONFIRMED_RECLAIM display facts only.

    No new thresholds, indicator calculation, order or operability-gate access.
    An already-GOOD startup does not invent a prior prealert.
    """
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('data'),dict):
        return None
    data=snapshot['data'];stamp=data.get('last_closed_1h')
    levels=data.get('market_levels') or {}
    reference=levels.get('reference_time')
    if type(stamp) is not int or type(reference) is not int or max(stamp,reference)>now or now-reference>=1800000:
        return None
    bias=data.get('bias');side={'LONG_ALLOWED':'LONG','SHORT_ALLOWED':'SHORT'}.get(bias)
    previous=policy.producer('manual_copilot')
    active=policy.active(previous['slot']) if previous.get('slot') else None
    result=[]
    quality=data.get('entry_quality');reason=data.get('entry_reason')
    level=data.get('entry_level')
    known_level=isinstance(level,(int,float)) and not isinstance(level,bool) and math.isfinite(level) and level>0
    candidate=bool(side and known_level and quality=='CAUTION' and reason=='WAIT_RECLAIM')
    anchor=str(level) if known_level else ''
    factors=['CONTEXTO_4H_1H'] if side else []
    expected_momentum='GREEN' if side=='LONG' else 'RED'
    expected_structure='BULLISH' if side=='LONG' else 'BEARISH'
    expected_flow='BUY' if side=='LONG' else 'SELL'
    if side and data.get('momentum')==expected_momentum:factors.append('ML_RSI_EXISTENTE')
    if side and data.get('structure')==expected_structure:factors.append('ESTRUCTURA_CERRADA')
    if side and data.get('flow')==expected_flow:factors.append('FLUJO_EXISTENTE')
    pending=['Reclaim 15m cerrado del nivel ya confirmado']
    if side and data.get('structure')!=expected_structure:pending.append('Estructura 15m alineada')
    if side and data.get('momentum')!=expected_momentum:pending.append('Momentum alineado')
    common=dict(source='manual_copilot',at=reference,what_changed='',side=side or previous.get('side','LONG'),
        timeframe='15m',context={'4H':data.get('trend4','UNKNOWN'),'1H':data.get('trend1','UNKNOWN')},
        factors=factors,closed=True,pending=pending,price_confirmed=False)
    if active:
        common.update(opportunity_id=active['id'],slot=active['slot'],side=active['side'])
        if side!=active['side'] or quality=='POOR':
            common.update(kind='INVALIDATED',what_changed='La condición observada perdió alineación o calidad',reason=reason or 'CONTEXT_CHANGED')
            result.append(common)
        elif quality=='GOOD' and reason=='CONFIRMED_RECLAIM' and active['phase'].startswith('PRE_'):
            common.update(kind='CONFIRMED',what_changed='Reclaim confirmado por el cálculo existente',pending=[],price_confirmed=True)
            result.append(common)
    elif candidate and (not previous.get('candidate') or previous.get('anchor')!=anchor):
        slot='manual-copilot:BTCUSDT:15m:'+side
        common.update(kind='PRE_'+side,opportunity_id=identity(slot,anchor,reference),slot=slot,
            what_changed='Confluencia existente en vigilancia; falta confirmación de precio')
        result.append(common)
    slot=result[-1]['slot'] if result else previous.get('slot')
    memory=dict(candidate=candidate,anchor=anchor,slot=slot,side=side,reference=reference)
    for item in result:item['id']=identity(item)
    return dict(events=result,memory=memory,previous=previous)


def safety_facts(snapshot,position_id,now):
    """Copied notification evidence only. Never infer recovery from missing data."""
    if not isinstance(snapshot,dict) or snapshot.get('position_verified') is not True:return None
    stamp=snapshot.get('timestamp')
    if not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or not 0<=now-int(stamp*1000)<=30000:return None
    flat=snapshot.get('position') is None
    if not flat and (not isinstance(position_id,str) or not position_id):return None
    statuses=snapshot.get('sl_status')
    return dict(verified=True,at=int(stamp*1000),flat=flat,position_ref=None if flat else identity(position_id),
        risk=(snapshot.get('risk') or {}).get('state'),
        stop_notice_cleared=isinstance(statuses,list) and bool(statuses) and all(x=='EXISTING_SAFER_SL_UNTOUCHED' for x in statuses))


def safety_recoveries(policy,facts,now):
    if not isinstance(facts,dict) or facts.get('verified') is not True or type(facts.get('flat')) is not bool or type(facts.get('at')) is not int or not 0<=now-facts['at']<=30000:return []
    if not facts['flat'] and (not isinstance(facts.get('position_ref'),str) or not re.fullmatch('[0-9a-f]{64}',facts['position_ref']) or facts.get('risk') not in ('NORMAL','WARNING','DANGER','EMERGENCY')):return []
    out=[]
    for row in policy.db.execute('SELECT * FROM incidents WHERE active=1').fetchall():
        iid=row['id'];risk=iid.startswith('capital-risk:');stop=iid.startswith('guardian:tpsl:')
        if not (risk or stop) or facts['at']<row['event_at']:continue
        same=iid.split(':')[-1]==facts.get('position_ref')
        resolved=facts.get('flat') is True or not same or (risk and facts.get('risk')=='NORMAL') or (stop and facts.get('stop_notice_cleared') is True)
        if resolved:
            out.append(event('guardian','RECOVERED',facts['at'],'Cambio verificado del aviso de riesgo',
                incident_id=iid,severity=row['severity'],text='El ciclo privado verificado resolvió este aviso de riesgo o cambió la posición. No certifica por sí solo cobertura del stop.'))
    return out
