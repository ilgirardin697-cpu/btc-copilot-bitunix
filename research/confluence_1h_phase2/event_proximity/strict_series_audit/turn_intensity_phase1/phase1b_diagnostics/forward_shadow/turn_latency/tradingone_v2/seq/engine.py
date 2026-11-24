"""Timestamped causal memories. These are declared hypotheses, not Bitman rules."""
from copy import deepcopy
import hashlib,json,math
from .maths import H


def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


class Ledger:
    """Deterministic replay ledger; not falsely labeled a live forward journal."""
    def __init__(self):
        self.rows=[]
        self.tip='0'*64

    def add(self,kind,when,**fields):
        r=dict(index=len(self.rows),kind=kind,available_at=int(when),**deepcopy(fields))
        r['prev_hash']=self.tip
        r['record_hash']=hashlib.sha256(canonical(r)).hexdigest()
        self.tip=r['record_hash']
        self.rows.append(r)
        return deepcopy(r)

    @staticmethod
    def verify(rows):
        prev='0'*64
        for i,record in enumerate(rows):
            r=deepcopy(record)
            digest=r.pop('record_hash',None)
            if r.get('index')!=i or r.get('prev_hash')!=prev or hashlib.sha256(canonical(r)).hexdigest()!=digest:
                raise ValueError('REPLAY_LEDGER_INVALID')
            prev=digest
        return prev


class Engine:
    def __init__(self,ledger=None):
        self.log=ledger if ledger is not None else Ledger()
        self.watch={1:None,-1:None}
        self.last_h1=None
        self.states={1:'IDLE',-1:'IDLE'}
        self.seen_frames={}
        self.tokens={}
        self.active={}
        self.last_when=None
        self.ao_run_sign=0
        self.deceleration_seen=False

    def emit(self,state,side,when,**data):
        self.states[side]=state
        return self.log.add(state,when,side=side,**data)

    def consume(self,context):
        base=context['15m']
        when=base['available_at']
        if self.last_when is not None and when!=self.last_when+H//4:
            raise ValueError('SEQUENTIAL_CLOCK_GAP_OR_REPLAY')
        if any(r['available_at']>when for r in context.values()):
            raise ValueError('FUTURE_CONTEXT')
        self.last_when=when
        for frame,row in context.items():
            if self.seen_frames.get(frame)==row['available_at']:
                continue
            self.seen_frames[frame]=row['available_at']
            # All fields are observations; no context field becomes an order.
            self.log.add('FRAME',row['available_at'],frame=frame,snapshot=row)
            if frame=='1d':
                for key in ('ao','adx','pececillos','bbwp'):
                    if row.get(key+'_turn'):
                        self.tokens[key]=dict(at=row['available_at'],turn=row[key+'_turn'])
                self.log.add('DAILY_SEQUENCE',when,tokens=self.tokens,
                             attribution='SOURCE_PROXY_OBSERVATION_NOT_SIGNAL')
        h=context['1h']
        new_h=self.last_h1!=h['available_at']
        if new_h:
            self.last_h1=h['available_at']
            ao=h.get('ao_slope')
            accel=h.get('ao_acceleration')
            if ao is not None and accel is not None:
                run_sign=1 if ao>0 else -1 if ao<0 else 0
                if run_sign!=self.ao_run_sign:
                    self.ao_run_sign=run_sign
                    self.deceleration_seen=False
                for side in (1,-1):
                    # Declining positive slope warns SHORT; inverse warns LONG.
                    slowing=side*ao<0 and side*accel>0
                    pre=slowing and not self.deceleration_seen
                    if slowing:
                        self.deceleration_seen=True
                    turn=h.get('ao_turn')==side
                    if self.watch[side] is None and (pre or turn):
                        self.watch[side]=dict(start=when,price=h['close'],indicator=h['ao'],
                            cause='AO_DECELERATION' if pre else 'AO_TURN',turn_at=when if turn else None)
                        self.emit('WATCH',side,when,episode=deepcopy(self.watch[side]),
                            context_at={k:v['available_at'] for k,v in context.items()})
                    elif self.watch[side] is not None and turn:
                        self.watch[side]['turn_at']=when
            for side,episode in list(self.active.items()):
                if h.get('ao_turn')==-side or (h.get('adx_turn')==-1 and h.get('bbwp_slope') is not None and h['bbwp_slope']<0):
                    self.emit('EXHAUSTION',side,when,confirmation_at=episode['at'],
                              reason='AO_OPPOSES_OR_STRENGTH_AND_VOLATILITY_COOLING',
                              note='DESCRIPTIVE_NO_AUTOMATIC_EXIT')
                    self.active.pop(side)
        plans=[]
        complete=all(context[f]['warmup_complete'] for f in ('1w','1d','4h','1h','15m'))
        if not complete:
            self.log.add('DATA_INCOMPLETE',when,reason='REQUIRED_FRAME_WARMUP',
                         two_week_bbwp=context['2w'].get('bbwp'))
            for side in (1,-1):
                if self.watch[side]:
                    self.emit('INVALIDATED',side,when,reason='DATA_INCOMPLETE',episode=self.watch[side])
                    self.watch[side]=None
            return plans
        for side in (1,-1):
            w=self.watch[side]
            if w is None:
                continue
            opposite='BREAK_DOWN' if side==1 else 'BREAK_UP'
            if (new_h and h.get('ao_turn')==-side) or opposite in base['structure']:
                self.emit('INVALIDATED',side,when,reason='OPPOSITE_TURN_OR_STRUCTURE',episode=w)
                self.watch[side]=None
                continue
            if when-w['start']>2*H:
                self.emit('EXPIRED',side,when,reason='WATCH_2H',episode=w)
                self.watch[side]=None
                continue
            changes=dict(price_change=base['close']-w['price'],
                         price_change_atr=(base['close']-w['price'])/h['atr'],
                         ao_change=h['ao']-w['indicator'])
            self.log.add('WATCH_PROGRESS',when,side=side,episode_at=w['start'],**changes,
                         recovered_indicator_without_price=bool(side*changes['ao_change']>0 and side*changes['price_change']<=0))
            wanted=('BREAK_UP','RETEST_UP') if side==1 else ('BREAK_DOWN','RETEST_DOWN')
            aligned=side*h['ao_slope']>0 and side*h['pececillos_slope']>0
            if aligned and any(s in base['structure'] for s in wanted):
                r=self.emit('CONFIRMED',side,when,episode=w,latency_ms=when-w['start'],
                    source_price=base['close'],conditions=dict(ao_aligned=True,pececillos_aligned=True,price_structure=True),
                    descriptive=dict(adx_slope=h['adx_slope'],bbwp=h['bbwp'],bbwp_slope=h['bbwp_slope']),
                    **changes)
                stop_pivot=base['known_low'] if side==1 else base['known_high']
                plans.append(dict(id=r['record_hash'][:20],side=side,at=when,signal_price=base['close'],
                    atr=h['atr'],pivot=stop_pivot['price'] if stop_pivot else None,
                    thesis_level=stop_pivot['price'] if stop_pivot else None))
                self.active[side]=dict(at=when)
                self.watch[side]=None
        return plans
