"""Closed-bar-only, chronological reproduction of mathematical/signal Pine state.

Display history based on last_bar_time is intentionally NOT signal logic.
No diagonal triggers, no box-order rejection, no extension-based expiry.
"""
from copy import deepcopy
from .core import ATR14, HOUR, project, session_member
from .profiles import PINE_A


class Replay:
    def __init__(self, profile=PINE_A):
        self.profile = profile
        self.prev_asia = self.prev_london = False
        self.aHigh = self.aLow = self.lHigh = self.lLow = None
        self.aStart = self.aEnd = self.lStart = None
        self.aLast = self.lLast = None
        self.aCount = self.lCount = 0
        self.asiaReady = self.pairReady = self.fired = False
        self.highAlerted = self.lowAlerted = False
        self.direction = 0
        self.signal_index = None
        self.topZoneHit = self.bottomZoneHit = False
        self.frozen = None
        self.index = -1
        self.previous_time = None
        self.last_asia_time = None
        self.cycle_contiguous = True
        self.cycle_id = None
        self.atr = ATR14()

    def preview(self, bar, as_of):
        # A caller cannot accidentally commit an incomplete candle.
        return deepcopy(self).append(bar, as_of=as_of)

    def append(self, bar, as_of=None):
        if as_of is not None and bar.available_at > as_of:
            raise ValueError('OPEN_CANDLE_NOT_ACCEPTED')
        if self.previous_time is not None and bar.open_time <= self.previous_time:
            raise ValueError('NON_CHRONOLOGICAL_OR_DUPLICATE_CANDLE')
        p = self.profile
        ia = session_member(bar, p, p.asia_start, p.asia_candles)
        il = session_member(bar, p, p.london_start, p.london_candles)
        sa, ea = ia and not self.prev_asia, not ia and self.prev_asia
        sl, el = il and not self.prev_london, not il and self.prev_london
        self.index += 1
        if sa:
            self.aHigh, self.aLow = bar.high, bar.low
            self.aStart = bar.open_time
            self.aCount, self.asiaReady = 1, False
            self.cycle_id = f'{p.name}:{bar.open_time}'
            self.cycle_contiguous = True
        elif ia:
            self.aHigh = max(bar.high, self.aHigh if self.aHigh is not None else bar.high)
            self.aLow = min(bar.low, self.aLow if self.aLow is not None else bar.low)
            self.aCount += 1
        if self.aStart is not None and not sa and self.previous_time is not None:
            if bar.open_time - self.previous_time != HOUR:
                self.cycle_contiguous = False
        if ia:
            self.aLast = bar.open_time
        if ea:
            self.aEnd = bar.open_time - HOUR // 2
            self.asiaReady = self.aCount == p.asia_candles
        validLondonStart = sl and self.asiaReady
        if sa:
            self.lHigh = self.lLow = self.lStart = self.lLast = None
            self.lCount = 0
        elif validLondonStart:
            self.lHigh, self.lLow, self.lStart = bar.high, bar.low, bar.open_time
            self.lCount = 1
        elif il and self.asiaReady:
            self.lHigh = max(bar.high, self.lHigh if self.lHigh is not None else bar.high)
            self.lLow = min(bar.low, self.lLow if self.lLow is not None else bar.low)
            self.lCount += 1
        if not sa and il and self.asiaReady:
            self.lLast = bar.open_time
        measureNow = (el and self.asiaReady and self.lCount == p.london_candles
                      and self.aHigh is not None and self.lHigh is not None)
        values = None
        if None not in (self.aHigh, self.aLow, self.lHigh, self.lLow):
            values = project(self.aHigh, self.aLow, self.lHigh, self.lLow,
                             p.top_inset_pct, p.bottom_inset_pct)
            if not measureNow:
                # Literal Pine: amplitude=na, nz(amplitude,0)=0 outside measureNow.
                values['amplitude'] = None
                values['newTopTarget'] = values['topAnchor']
                values['newBottomTarget'] = values['bottomAnchor']
        if sa:
            self.frozen = None
            self.pairReady = self.fired = self.highAlerted = self.lowAlerted = False
            self.direction, self.signal_index = 0, None
            self.topZoneHit = self.bottomZoneHit = False
        elif measureNow:
            self.frozen = dict(values)
            self.frozen.update(levels_available_at=bar.open_time,
                               asia_left=self.aStart-HOUR//2, asia_right=self.aEnd,
                               london_left=self.lStart-HOUR//2, london_right=bar.open_time-HOUR//2,
                               futureTime=bar.open_time+p.forward_bars*HOUR,
                               data_complete=self.cycle_contiguous)
            for prefix, in_asia in (('top',values['topInAsia']), ('bottom',values['bottomInAsia'])):
                left = self.aStart-HOUR//2 if in_asia else self.lStart-HOUR//2
                right = self.aEnd if in_asia else bar.open_time-HOUR//2
                self.frozen[prefix+'XTime'] = int((left+right)/2.0)
            self.pairReady = True
        gh = None if not self.frozen else self.frozen['highGuideValue']
        gl = None if not self.frozen else self.frozen['lowGuideValue']
        eligible = self.pairReady and (p.independent_sides or not self.fired)
        highConfirmed = bool(eligible and not self.highAlerted and (
            min(bar.open,bar.close) > gh if p.whole_body else bar.close > gh))
        lowConfirmed = bool(eligible and not self.lowAlerted and (
            max(bar.open,bar.close) < gl if p.whole_body else bar.close < gl))
        longBreak, shortBreak = highConfirmed and not self.fired, lowConfirmed and not self.fired
        self.highAlerted |= highConfirmed
        self.lowAlerted |= lowConfirmed
        if longBreak or shortBreak:
            self.fired = True
            self.direction = 1 if longBreak else -1
            self.signal_index = self.index
        after_signal = self.signal_index is not None and self.index > self.signal_index
        tt = None if not self.frozen else self.frozen['newTopTarget']
        tb = None if not self.frozen else self.frozen['newBottomTarget']
        upperTouch = bool(self.direction == 1 and not self.topZoneHit and after_signal
                          and bar.high >= tt-p.top_band)
        lowerTouch = bool(self.direction == -1 and not self.bottomZoneHit and after_signal
                          and bar.low <= tb+p.bottom_band)
        self.topZoneHit |= upperTouch
        self.bottomZoneHit |= lowerTouch
        # Additional diagnostics are NOT Pine target alerts. Same-bar hits are excluded.
        exactTop = bool(after_signal and self.direction == 1 and bar.high >= tt)
        exactBottom = bool(after_signal and self.direction == -1 and bar.low <= tb)
        self.prev_asia, self.prev_london = ia, il
        self.previous_time = bar.open_time
        out = dict(profile=p.name, cycle_id=self.cycle_id, time=bar.open_time,
                   available_at=bar.available_at, inAsia=ia, inLondon=il,
                   startAsia=sa, endAsia=ea, startLondon=sl, endLondon=el,
                   validLondonStart=validLondonStart, aHigh=self.aHigh, aLow=self.aLow,
                   lHigh=self.lHigh, lLow=self.lLow, aCount=self.aCount, lCount=self.lCount,
                   asiaReady=self.asiaReady, measureNow=measureNow, pairReady=self.pairReady,
                   globalHigh=gh, globalLow=gl, targetTop=tt, targetBottom=tb,
                   highConfirmed=highConfirmed, lowConfirmed=lowConfirmed,
                   longBreak=longBreak, shortBreak=shortBreak, direction=self.direction,
                   highAlerted=self.highAlerted, lowAlerted=self.lowAlerted, fired=self.fired,
                   upperTouch=upperTouch, lowerTouch=lowerTouch,
                   exactTopTouch=exactTop, exactBottomTouch=exactBottom,
                   atr14=self.atr.append(bar), data_complete=self.cycle_contiguous,
                   frozen=deepcopy(self.frozen))
        for key in ('amplitude','topInAsia','bottomInAsia','topBoxHeight','bottomBoxHeight',
                    'topAnchor','bottomAnchor','newTopTarget','newBottomTarget',
                    'highGuideValue','lowGuideValue'):
            out[key] = None if values is None else values[key]
        if values is None:
            # Pine v6 bool comparisons with na evaluate false, not nullable bools.
            out['topInAsia'] = out['bottomInAsia'] = False
        return out
