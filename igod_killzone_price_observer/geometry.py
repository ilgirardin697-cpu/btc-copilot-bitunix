"""Exact audited PINE_A mathematical projection; no trading controls."""
import math

def project(aHigh, aLow, lHigh, lLow, topInsetPct=3.0, bottomInsetPct=3.0):
    vals = (aHigh, aLow, lHigh, lLow)
    if (any(not math.isfinite(x) or x <= 0 for x in vals)
            or aHigh < aLow or lHigh < lLow
            or not 0 <= topInsetPct <= 35 or not 0 <= bottomInsetPct <= 35):
        raise ValueError('INVALID_BOX_OR_INSET')
    # Zero-height, overlapping and nested boxes are legal Pine configurations.
    amplitude = max(aHigh, lHigh) - min(aLow, lLow)
    topInAsia = aHigh <= lHigh
    bottomInAsia = aLow >= lLow
    topBoxHeight = aHigh - aLow if topInAsia else lHigh - lLow
    bottomBoxHeight = aHigh - aLow if bottomInAsia else lHigh - lLow
    topAnchor = min(aHigh, lHigh) - topBoxHeight * topInsetPct / 100.0
    bottomAnchor = max(aLow, lLow) + bottomBoxHeight * bottomInsetPct / 100.0
    return dict(aHigh=aHigh, aLow=aLow, lHigh=lHigh, lLow=lLow,
                amplitude=amplitude, topInAsia=topInAsia, bottomInAsia=bottomInAsia,
                topBoxHeight=topBoxHeight, bottomBoxHeight=bottomBoxHeight,
                topAnchor=topAnchor, bottomAnchor=bottomAnchor,
                newTopTarget=topAnchor + amplitude, newBottomTarget=bottomAnchor - amplitude,
                highGuideValue=max(aHigh, lHigh), lowGuideValue=min(aLow, lLow))
