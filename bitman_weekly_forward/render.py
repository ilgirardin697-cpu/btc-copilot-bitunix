"""Optional manual research context; never changes the existing decision text."""
from datetime import datetime,timezone
import math

HEADER='📅 WEEKLY FORWARD OBSERVER — RESEARCH ONLY'
NOTES=('⚪ LARGE MOVE WATCH: NOT VALIDATED\n🧪 NOT USED BY OPERABILITY\n'
       'HYPOTHESIS FOR FORWARD OBSERVATION\nOBSERVER ONLY · SHADOW ONLY · NO AUTO ALERTS\n'
       'EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN\n'
       'EXACT BITMAN VOLATILITY PARITY: NOT PROVEN')
STATES={'OTHER','UNKNOWN','IMPULSE_UP','IMPULSE_DOWN','PULLBACK_UP','PULLBACK_DOWN',
        'REACCELERATION_UP','REACCELERATION_DOWN','ZERO_CROSS_UP_EXPANSION','ZERO_CROSS_DOWN_EXPANSION'}
STATES.update('PENDING_'+x for x in ('REACCELERATION_UP','REACCELERATION_DOWN','ZERO_CROSS_UP_EXPANSION','ZERO_CROSS_DOWN_EXPANSION'))


def stamp(value):
    return datetime.fromtimestamp(value/1000,timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def block(view):
    if view is None:return ''
    if view.get('status')=='OBSERVER_JOURNAL_INVALID':
        return HEADER+'\n⚠️ Journal no verificable\nResearch observer unavailable'
    if view.get('status')!='HEALTHY':
        return HEADER+'\n⚠️ Research observer unavailable\n'+NOTES
    try:
        s=view['snapshot'];models=s['models']
        if s['ao_color'] not in ('GREEN','RED','FLAT') or s['ao_sign'] not in ('ABOVE','BELOW','ZERO'):raise ValueError
        if s['volatility'] not in ('COOLING','FLAT','ACTIVE_RISING'):raise ValueError
        if any(type(s[k]) not in (int,float) or not math.isfinite(s[k]) or not 0<=s[k]<=100 for k in ('bbwp','prior_bbwp')):raise ValueError
        if any(type(view[k]) is not int or not 0<=view[k]<=10000000 for k in ('active','matured')):raise ValueError
        color='🟢' if s['ao_color']=='GREEN' else '🔴' if s['ao_color']=='RED' else '⚪'
        lines=[HEADER,'Closed week: '+stamp(s['available_at']),
            'Oscillator proxy: '+color+' '+s['ao_color']+' · '+s['ao_sign']+' ZERO',
            'Volatility proxy: '+str(s['bbwp'])+' · '+s['volatility']+' (previous '+str(s['prior_bbwp'])+')']
        pending=[]
        for name,label in (('STRICT_SAME_WEEK','STRICT'),('SOURCE_ALIGNED_LAG_LE1','LAG≤1'),('SOURCE_ALIGNED_LAG_LE2','LAG≤2')):
            state=models[name]['state']
            if state not in STATES:raise ValueError
            lines.append(label+': '+state)
            if models[name]['pending'] is not None:pending.append(label)
        lines.append('Pending: '+(', '.join(pending) if pending else 'NONE'))
        latest=view.get('latest_event')
        if latest is not None:
            if latest['kind'] not in ('REACCELERATION_UP','REACCELERATION_DOWN','ZERO_CROSS_UP_EXPANSION','ZERO_CROSS_DOWN_EXPANSION'):raise ValueError
            if type(latest['actual_lag']) is not int or latest['actual_lag'] not in (0,1,2):raise ValueError
            label={'STRICT_SAME_WEEK':'STRICT','SOURCE_ALIGNED_LAG_LE1':'LAG≤1','SOURCE_ALIGNED_LAG_LE2':'LAG≤2'}[latest['model']]
            lines+=['⚡ FORWARD EVENT RECORDED',label+' · '+latest['kind'],
                'Activation: '+stamp(latest['activation_week']+604800000),
                'Confirmation: '+stamp(latest['confirmation_week']+604800000)+' · lag '+str(latest['actual_lag'])+'W']
        lines+=['Forward events: '+str(int(view['active']))+' active / '+str(int(view['matured']))+' matured',
                'H1/H2/H3/H4 matured: '+' / '.join(str(int(view['horizons'][str(h)])) for h in (1,2,3,4)),
                'FORWARD EVIDENCE: INSUFFICIENT',NOTES]
        return '\n'.join(lines)
    except Exception:
        return HEADER+'\n⚠️ Research observer unavailable\n'+NOTES


def append_context(text,view):
    extra=block(view)
    marker='\n\n⚠️ Directional research context'
    if not extra or marker not in text:return text
    start,footer=text.rsplit(marker,1)
    candidate=start+'\n\n'+extra+marker+footer
    if len(candidate.encode('utf-16-le'))//2<3900:return candidate
    compact=HEADER+'\nResearch context omitted: panel size\n'+NOTES
    candidate=start+'\n\n'+compact+marker+footer
    return candidate if len(candidate.encode('utf-16-le'))//2<3900 else text
