"""Pure prospective contracts on supplied fixtures; no observer, IO or scheduler."""
import hashlib
import math

VERSION='BITMAN_ENTRY_FORWARD_RESEARCH_V0_DESIGN'
HOUR=3600000
M5=300000
HOLD=48*HOUR
CANDIDATES=('AO_ONLY','AO_CONTEXT','AO_FE')
COSTS={'BASE':(.0005,.0001),'CONSERVATIVE':(.00075,.0003),'STRESS':(.001,.0005)}

def finite(*values):
    return all(type(v) in (int,float) and math.isfinite(v) for v in values)

def validate_clock(s):
    required=('candle_open_ms','available_at','observed_at','activation_at','h4_available_at','d1_available_at')
    if any(type(s.get(k)) is not int for k in required):raise ValueError('OBSERVATION_CLOCK')
    if any(s[k]<0 for k in required):raise ValueError('OBSERVATION_CLOCK')
    if s['candle_open_ms']%HOUR or s['available_at']!=s['candle_open_ms']+HOUR:raise ValueError('CLOSED_HOUR_REQUIRED')
    if s['observed_at']<s['available_at']:raise ValueError('OPEN_CANDLE')
    for key,width in (('h4_available_at',4*HOUR),('d1_available_at',24*HOUR)):
        if s[key]>s['available_at'] or s['available_at']-s[key]>=width or s[key]%width:
            raise ValueError('NONCAUSAL_OR_STALE_CONTEXT')

def assess(s,last_anchor_at=None):
    validate_clock(s)
    result=dict(protocol_version=VERSION,shadow_only=True,trade_authority=False,source_venue='BINANCE_USDM_PERPETUAL',
        signal_available_at=s['available_at'],observed_at=s['observed_at'],classification='POST_HOC_HYPOTHESIS_NOT_VALIDATED',
        scope='OFFLINE_CONTRACT_FIXTURE',hypothetical_side=None,anchor=False,candidates={},diagnostics={},
        source_input_sha256=s.get('source_input_sha256'))
    if s.get('venue')!='BINANCE_USDM_PERPETUAL':raise ValueError('VENUE_REQUIRED')
    if s['candle_open_ms']<s['activation_at']:
        return dict(result,observation_class='WARMUP_NOT_FORWARD')
    if s['observed_at']>=s['available_at']+HOUR:
        return dict(result,observation_class='LATE_RECOVERY_NOT_PROSPECTIVE')
    numeric=('ao','ao_previous','ao_previous2','ao_slope','ao_slope_previous','ao_slope_previous2','atr',
        'h4_ao','d1_ao','h4_regime','signal_close','prior_high3','prior_low3','prior_high6','prior_low6')
    if not finite(*(s.get(k) for k in numeric)) or s['atr']<=0:
        return dict(result,observation_class='FEATURES_UNAVAILABLE')
    side=0
    for sign in (1,-1):
        if (all(sign*s[k]>0 for k in ('ao','ao_previous','ao_previous2'))
            and sign*s['ao_slope']>0 and sign*s['ao_slope_previous']<0 and sign*s['ao_slope_previous2']<0):
            side=sign
    if not side:return dict(result,observation_class='NO_AO_RECOVERY')
    if last_anchor_at is not None:
        if type(last_anchor_at) is not int or last_anchor_at>=s['available_at']:raise ValueError('ANCHOR_ORDER')
        if s['available_at']-last_anchor_at<HOLD:return dict(result,observation_class='COOLDOWN_REFERENCE')
    present=dict(ao_recovery=True,macro_ao=side*s['d1_ao']>0,swing_ao=side*s['h4_ao']>0,
        price_reclaim=s['signal_close']>s['prior_high3'] if side==1 else s['signal_close']<s['prior_low3'],
        fe_available=finite(s.get('fe'),s.get('fe_previous')),
        fe_falling=finite(s.get('fe'),s.get('fe_previous')) and s['fe']<s['fe_previous'])
    requirements={'AO_ONLY':('ao_recovery',),'AO_CONTEXT':('ao_recovery','macro_ao','swing_ao','price_reclaim'),
        'AO_FE':('ao_recovery','macro_ao','swing_ao','price_reclaim','fe_available','fe_falling')}
    candidates={name:dict(conditions={k:bool(present[k]) for k in keys},
        missing=[k for k in keys if not present[k]],selected=all(present[k] for k in keys)) for name,keys in requirements.items()}
    adx_turn=finite(s.get('adx_slope'),s.get('adx_slope_previous')) and s['adx_slope']>0 and s['adx_slope_previous']<=0
    dmi=finite(s.get('di_plus'),s.get('di_minus')) and side*(s['di_plus']-s['di_minus'])>0
    stop=s['prior_low6']-.25*s['atr'] if side==1 else s['prior_high6']+.25*s['atr']
    return dict(result,observation_class='PROSPECTIVE_ANCHOR_CONTRACT',anchor=True,hypothetical_side='LONG' if side==1 else 'SHORT',
        candidates=candidates,side=side,conditions=present,diagnostics=dict(adx_turn_up=bool(adx_turn),dmi_supporting=bool(dmi)),
        next_paper_open_ms=(s['observed_at']//M5+1)*M5,stop=stop,atr=s['atr'],target=None,
        frozen_features={k:s.get(k) if finite(s.get(k)) else None for k in numeric+('adx','adx_slope','adx_slope_previous','di_plus','di_minus','fe','fe_previous')})

def paper_entry(assessment,opening_ms,price,recorded_at,plan_committed_at):
    if not assessment.get('anchor'):raise ValueError('NO_PRECOMMITTED_ANCHOR')
    if (opening_ms!=assessment['next_paper_open_ms'] or plan_committed_at<assessment['observed_at']
        or plan_committed_at>=opening_ms or recorded_at<opening_ms):raise ValueError('ENTRY_CAUSALITY')
    if not finite(price) or price<=0:raise ValueError('ENTRY_PRICE')
    side=assessment['side'];risk=side*(price-assessment['stop']);atr=assessment['atr']
    if not .5*atr<=risk<=4*atr:
        return dict(kind='ENTRY_INVALIDATED',reason='STRUCTURAL_RISK_OUTSIDE_FROZEN_BOUNDS',created_at=recorded_at)
    target=price+side*2*risk
    if min(price,assessment['stop'],target)<=0:return dict(kind='ENTRY_INVALIDATED',reason='NONPOSITIVE_PAPER_LEVEL',created_at=recorded_at)
    return dict(kind='PAPER_ENTRY',entry_time=opening_ms,entry_price=price,entry_recorded_at=recorded_at,
        planned_before_open=True,source_venue='BINANCE_USDM_PERPETUAL',side=side,risk=risk,stop=assessment['stop'],
        target=target,outcome_due=opening_ms+HOLD,shadow_only=True,trade_authority=False)

def costs(entry,exit_price,funding_per_unit=None):
    if entry.get('kind')!='PAPER_ENTRY' or not finite(exit_price) or exit_price<=0:raise ValueError('PAPER_RESULT')
    gross=entry['side']*(exit_price-entry['entry_price'])
    return {name:dict(gross_R=gross/entry['risk'],
        net_R=(gross-funding_per_unit-(fee+slip)*(entry['entry_price']+exit_price))/entry['risk']
            if finite(funding_per_unit) else None,funding_status='KNOWN_OR_LABELLED_ESTIMATE' if finite(funding_per_unit) else 'UNKNOWN')
        for name,(fee,slip) in COSTS.items()}

def mature(entry,now_ms,path_open_times,funding_complete):
    if entry.get('kind')!='PAPER_ENTRY' or now_ms<entry['outcome_due']:raise ValueError('OUTCOME_NOT_MATURE')
    expected=list(range(entry['entry_time'],entry['outcome_due'],M5))
    if list(path_open_times)!=expected:return dict(kind='CENSORED',reason='MISSING_OR_REVISED_MARKET_PATH')
    return dict(kind='OUTCOME_MATURED',net_status='AVAILABLE' if funding_complete else 'UNKNOWN_FUNDING',
        evidence='INSUFFICIENT_NOT_AUTOMATICALLY_VALIDATED')

def control_slots(start_ms,end_ms,seed):
    if not isinstance(seed,str) or not seed:raise ValueError('CONTROL_SEED')
    # Monday/Thursday 00UTC, >=72h apart; predetermined side independent of price.
    day=24*HOUR;first=((start_ms+day-1)//day)*day;out=[]
    for t in range(first,end_ms,day):
        if (t//day+3)%7 in (0,3):
            digest=hashlib.sha256((seed+':'+str(t)).encode()).digest()
            out.append(dict(available_at=t,side=1 if digest[0]%2 else -1))
    return out
