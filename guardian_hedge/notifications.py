"""Same-writer notification reconciliation, never account or execution control."""
import json
import re
from igod_notifications.adapters import event

def apply(policy,facts,now):
    if not isinstance(facts,dict) or type(facts.get('at')) is not int or not 0<=now-facts['at']<=30000:
        raise ValueError('HEDGE_NOTIFICATION_EVIDENCE_STALE')
    if type(facts.get('verified')) is not bool:raise ValueError('HEDGE_NOTIFICATION_EVIDENCE_INVALID')
    previous=policy.producer('hedge_readonly') or {}
    if facts['at']<previous.get('at',0):return []
    at=facts['at'];out=[]
    def record(kind,iid,code,severity=3,material=None,text=None):
        if iid=='guardian:private-read' and kind=='CRITICAL':
            current=policy.db.execute('SELECT * FROM incidents WHERE id=?',(iid,)).fetchone()
            if current and current['active'] and json.loads(current['material']).get('code')!='AMBIGUOUS_POSITIONS':
                return  # Never relabel a real authentication/transport failure as ambiguity.
        value=event('guardian',kind,at,text or 'Cambio verificado en lectura HEDGE/CROSS',incident_id=iid,severity=severity,
            material=material or {'code':code},text=text or ('Lectura HEDGE/CROSS: '+code+'. SHADOW ONLY · Sin órdenes automáticas.'))
        out.append(policy.ingest(value,now))
    with policy.transaction():
        if not facts['verified']:
            if facts.get('legacy_cause')=='AMBIGUOUS_POSITIONS' or previous.get('managed'):
                record('CRITICAL','guardian:private-read','AMBIGUOUS_POSITIONS',text='No hay lectura HEDGE/CROSS completa y fresca. Protección no verificable; no se enviarán órdenes.')
            policy.producer('hedge_readonly',dict(previous,at=at))
            return out  # No resolution, no deletion of prior IDs, no fake flat state.
        if type(facts.get('managed')) is not bool or not isinstance(facts.get('positions'),list):raise ValueError('HEDGE_NOTIFICATION_SCHEMA')
        observed=facts.get('observed_at')
        if type(observed) is not int or observed>at or not 0<=now-observed<=30000:
            raise ValueError('HEDGE_NOTIFICATION_OLDEST_COMPONENT_STALE')
        ids=[]
        for p in facts['positions']:
            if not isinstance(p,dict) or not re.fullmatch('[0-9a-f]{64}',p.get('ref','')) or p.get('coverage') not in ('ABSENT','INSUFFICIENT','UNVERIFIABLE','FULL_REGISTERED'):
                raise ValueError('HEDGE_NOTIFICATION_POSITION_INVALID')
            if p.get('side') not in ('LONG','SHORT') or not isinstance(p.get('symbol'),str) or not re.fullmatch('[A-Z0-9]{2,24}USDT',p['symbol']):
                raise ValueError('HEDGE_NOTIFICATION_DIRECTION_INVALID')
            ids.append(p['ref'])
        if len(set(ids))!=len(ids):raise ValueError('HEDGE_NOTIFICATION_POSITION_DUPLICATE')
        managed=facts['managed'] or previous.get('managed',False)
        if not managed:return []
        if facts.get('account_confirmed') is not True and facts.get('legacy_cause')=='AMBIGUOUS_POSITIONS':
            record('CRITICAL','guardian:private-read','AMBIGUOUS_POSITIONS',text='Lectura HEDGE/CROSS pendiente de cuadre financiero estable. No se retira AMBIGUOUS_POSITIONS ni se afirma protección.')
        private=policy.db.execute('SELECT * FROM incidents WHERE id=?',('guardian:private-read',)).fetchone()
        if (facts.get('account_confirmed') is True and facts.get('legacy_cause')=='AMBIGUOUS_POSITIONS' and private and at>=private['event_at']
                and json.loads(private['material']).get('code')=='AMBIGUOUS_POSITIONS'):
            record('RECOVERED','guardian:private-read','READ_ONLY_HEDGE_VERIFIED',text='Lectura de ambas posiciones verificada en modo lectura. Esto NO verifica su stop ni habilita protección automática.')
        wanted={}
        for p in facts['positions']:
            iid='guardian:hedge-stop:'+p['ref']
            if p['coverage']!='FULL_REGISTERED':
                label={'ABSENT':'SIN SL EN TP/SL CONSULTADOS','INSUFFICIENT':'STOP INSUFICIENTE','UNVERIFIABLE':'STOP NO VERIFICABLE'}[p['coverage']]
                wanted[iid]=('STOP_'+p['coverage'],3,{'code':'STOP_'+p['coverage'],'coverage_fingerprint':p.get('coverage_fingerprint')},
                    p['side']+' '+p['symbol']+' · ref '+p['ref'][:12]+': '+label+'. Otras modalidades no verificadas.\nSHADOW ONLY · Sin órdenes automáticas. Consulta /risk.')
        reasons=facts.get('risk_reasons',[])
        if not isinstance(reasons,list) or any(not isinstance(r,str) or not re.fullmatch('[A-Z0-9_]{1,80}',r) for r in reasons):raise ValueError('HEDGE_NOTIFICATION_RISK_INVALID')
        # A PnL mismatch is visible on /risk; its cause is not presumed to be
        # timing. No price/PnL/account amount is used for notification dedupe.
        meaningful=sorted(set(reasons)-{'PNL_ACCOUNT_POSITION_MISMATCH','CROSS_LIQUIDATION_SCOPE_UNVERIFIED','STOP_ABSENT','STOP_INSUFFICIENT','STOP_UNVERIFIABLE'})
        if meaningful:
            severity=3 if set(meaningful)&{'NONPOSITIVE_ACCOUNT_RESOURCES','LIQUIDATION_REFERENCE_WITHIN_2_PERCENT'} else 2
            wanted['guardian:hedge-account-risk']=('ACCOUNT_RISK_UNVERIFIED',severity,{'code':'ACCOUNT_RISK_UNVERIFIED','reasons':meaningful},
                'Cuenta USDT · riesgo agregado no verificable: '+', '.join(meaningful)+'.\nSHADOW ONLY · Sin órdenes automáticas. Consulta /risk.')
        # Existing legacy risk notices can be resolved by verified ABSENCE of
        # their position, never by choosing another HEDGE side or inventing NORMAL.
        for row in policy.db.execute("SELECT * FROM incidents WHERE active=1 AND (id LIKE 'capital-risk:%' OR id LIKE 'guardian:tpsl:%')").fetchall():
            if row['id'].split(':')[-1] not in ids and at>=row['event_at']:
                record('RECOVERED',row['id'],'POSITION_ABSENCE_VERIFIED',row['severity'],text='Lectura completa verificó la ausencia de la posición de este aviso anterior. No se ocultó un lado HEDGE.')
        for row in policy.db.execute("SELECT * FROM incidents WHERE active=1 AND (id LIKE 'guardian:hedge-stop:%' OR id='guardian:hedge-account-risk')").fetchall():
            if row['id'] not in wanted and at>=row['event_at']:
                record('RECOVERED',row['id'],'READ_ONLY_NOTICE_RESOLVED',row['severity'],text='Nueva lectura completa resolvió este aviso específico HEDGE/CROSS; no certifica riesgo global ni autoriza órdenes.')
        failed=policy.db.execute("SELECT * FROM incidents WHERE id='guardian:hedge-notifications' AND active=1").fetchone()
        if failed and facts.get('account_confirmed') is True and at>=failed['event_at']:
            record('RECOVERED',failed['id'],'HEDGE_NOTIFICATIONS_RECONCILED',failed['severity'],text='Conciliación de notificaciones HEDGE/CROSS recuperada. No certifica protección del exchange.')
        for iid,(code,severity,material,text) in wanted.items():record('CRITICAL',iid,code,severity,material,text)
        policy.producer('hedge_readonly',dict(at=at,managed=managed,position_refs=ids))
    return out
