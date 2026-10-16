"""Causal geometry/events and descriptive direction. No entry permission."""
import hashlib
import json
import math
import numpy as np
from .config import TIMEFRAMES,VERSION,SHORT_PROVEN
from .indicators import calculate
from .market import aggregate


def finite(v):return float(v) if v is not None and math.isfinite(v) else None


def direction(s):
    required=('mountain','ma','di_plus','di_minus','ao','adx','bbwp')
    if any(s.get(k) is None for k in required):
        return 'BLOCKED',['DATOS INSUFICIENTES'], 'SHORT_LOGIC_NOT_PROVEN'
    if s['mountain']<0 and s['di_minus']>s['di_plus'] and s['ao']<0:
        return 'BLOCKED',['Contexto bajista observado','SHORT_LOGIC_NOT_PROVEN'], 'SHORT_LOGIC_NOT_PROVEN'
    if s['inside'] and s['mountain']>0:
        if s['di_plus']>s['di_minus']:
            return 'LONG',['Media dentro de montaña positiva','+DI supera -DI',
                           'Contexto observacional; NO permiso de entrada'], 'SHORT_LOGIC_NOT_PROVEN'
        return 'SETUP_FORMING',['Media dentro de montaña positiva','Falta alineación de DI'], 'SHORT_LOGIC_NOT_PROVEN'
    if s['mountain']>0 and (s.get('mountain_slope') or 0)>0:
        return 'SETUP_FORMING',['Montaña positiva creciendo','Media fuera de la montaña'], 'SHORT_LOGIC_NOT_PROVEN'
    return 'WAIT',['Sin contexto LONG completo','EXIT no equivale a señal SHORT'], 'SHORT_LOGIC_NOT_PROVEN'


def geometry(f):
    mountain=f['mountain'];ma=f['ma']
    valid=np.isfinite(mountain)&np.isfinite(ma)
    inside=valid&(ma>np.minimum(0,mountain))&(ma<np.maximum(0,mountain))
    separation=np.where(inside,abs(mountain-ma),np.nan)
    return valid,inside,separation


def snapshots(frame,tf,config):
    if tf not in TIMEFRAMES:raise ValueError('TIMEFRAME_NOT_SUPPORTED')
    f=calculate(frame);valid,inside,separation=geometry(f)
    last_inside=None;last_exit=None;rows=[]
    for i in range(len(frame)):
        stamp=int(frame[i,0]+TIMEFRAMES[tf]);kind=None;age=None
        if not valid[i]:last_inside=None;last_exit=None
        elif last_inside is not None:
            if inside[i] and not last_inside:
                kind='KONKORDE_ENTRY'
                age=i-last_exit if last_exit is not None else None
            elif last_inside and not inside[i]:kind='KONKORDE_EXIT';last_exit=i
        if valid[i]:last_inside=bool(inside[i])
        delta=separation[i]-separation[i-1] if i and inside[i] and inside[i-1] else np.nan
        strength='UNAVAILABLE' if not inside[i] else 'NEW_INSIDE' if not np.isfinite(delta) else 'EXPANDING' if delta>0 else 'CONTRACTING' if delta<0 else 'STABLE'
        row={key:finite(f[key][i]) for key in ('close','mountain','ma','mountain_slope','rsi','mfi','boll','stoch',
            'atr','adx','adx_slope','di_plus','di_minus','ao','ao_slope','bbwp','bbwp_slope')}
        row.update(timeframe=tf,symbol='BTCUSDT',candle_open=int(frame[i,0]),candle_close=stamp,
            inside=bool(inside[i]) if valid[i] else None,distance_to_zero=finite(abs(f['ma'][i])),
            mountain_distance_to_zero=finite(abs(f['mountain'][i])),separation=finite(separation[i]),
            separation_change=finite(delta),strength=strength,technical_event=kind,exit_age_bars=age,
            reentry=bool(kind=='KONKORDE_ENTRY' and age is not None and 1<=age<=config.reentry_max_bars),
            reentry_max_bars=config.reentry_max_bars,proxy='KONKORDE_PROXY',version=VERSION,
            trend_speed='NOT IMPLEMENTED / FORMULA NOT VERIFIED',
            venue='BINANCE_USDM_PERPETUAL',shadow_only=True,trade_authority=False)
        row['event']='KONKORDE_REENTRY' if row['reentry'] else kind
        row['state'],row['reasons'],row['short_logic']=direction(row)
        row['event_id']=hashlib.sha256(f'{VERSION}|{tf}|{stamp}|{kind}'.encode()).hexdigest() if kind else None
        rows.append(row)
    return rows


def analyze(hourly,tf,now_ms,config):
    if tf not in TIMEFRAMES:raise ValueError('TIMEFRAME_NOT_SUPPORTED')
    frame=aggregate(hourly,TIMEFRAMES[tf],now_ms)
    if not len(frame):return []
    return snapshots(frame,tf,config)
