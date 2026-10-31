"""Existing Guardian process only. Disabled by default; no second Telegram poller."""
import os
from pathlib import Path
from .client import Client
from .controller import Controller
from .global_policy import POLICY_HASH,APPROVAL_PHRASE,PROPOSAL
from .journal import Journal


def enabled():
    return os.getenv('GUARDIAN_CAPITAL_V2_ENABLED','false')=='true'


def before_guardian_cycle(guardian):
    if not enabled():return  # No client, network, storage or log work while disabled.
    try:
        execute=os.getenv('GUARDIAN_CAPITAL_V2_EXECUTION','false')=='true'
        if execute and (os.getenv('GUARDIAN_CAPITAL_V2_POLICY_HASH')!=POLICY_HASH
                        or os.getenv('GUARDIAN_CAPITAL_V2_AUTHORIZATION')!=APPROVAL_PHRASE
                        or guardian.config.armed('SL') or guardian.config.armed('CLOSE')):
            if getattr(guardian,'_capital_v2',None) is not None:
                guardian._capital_v2.client.execution=False
            raise ValueError('CAPITAL_GLOBAL_APPROVAL_REQUIRED_OR_DUAL_EXECUTOR')
        controller=getattr(guardian,'_capital_v2',None)
        if controller is None:
            client=Client(guardian.client._key,guardian.client._secret,execution=execute,
                          approval_hash=POLICY_HASH if execute else '')
            journal=Journal(Path(guardian.config.state_dir)/'capital_protection_v2.jsonl')
            controller=Controller(client,journal,notify=guardian.telegram.send)
            guardian._capital_v2=controller
        controller.client.execution=execute
        controller.client.approval_hash=POLICY_HASH if execute else ''
        controller.client.begin_cycle(PROPOSAL['cycle_time_budget_seconds'])
        controller.step()
        guardian._capital_v2_error=False
    except Exception:
        # Never expose exchange payloads/credentials, and never stop classic Guardian.
        if not getattr(guardian,'_capital_v2_error',False):
            guardian._capital_v2_error=True
            try:
                print('GUARDIAN_CAPITAL_V2_DEGRADED',flush=True)
            except Exception:
                pass
            try:
                guardian.telegram.send('🚨 GUARDIAN CAPITAL V2: protección automática no verificable.\n'
                                       'No se enviarán órdenes a ciegas. Revisa Bitunix.\n'
                                       'Un SL previamente registrado permanece en el exchange.')
            except Exception:
                pass


def owner_reply(guardian):
    original=guardian.telegram.send_owner
    if not enabled():return original
    def reply(text):
        if text.startswith('🛡️ RIESGO DE TU POSICIÓN'):
            controller=getattr(guardian,'_capital_v2',None)
            status=controller.status if controller is not None else 'UNAVAILABLE'
            active=bool(controller and controller.client.execution)
            phase={'RESIDUAL_PROTECTED':'🟢 TESIS VÁLIDA · exposición protegida',
                   'REDUCTION_VERIFIED':'🟡 RECORTE VERIFICADO EN BITUNIX',
                   'CLOSE_VERIFIED':'🔴 CIERRE PROTECTOR VERIFICADO',
                   'STOP_VERIFIED':'🛡️ STOP NATIVO VERIFICADO',
                   'RECONCILIATION_REQUIRED':'⚠️ Acción pendiente de verificación; sin reintentos a ciegas'}.get(status,status)
            text+='\n\n🛡️ CAPITAL V2: '+phase+'\nEjecución protectora: '+('ON' if active else 'OFF')
            text+='\nMotor clásico separado; entradas automáticas: NUNCA.'
        return original(text)
    return reply
