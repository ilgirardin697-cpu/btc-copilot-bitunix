"""Frozen proxy geometry only; no legacy observer, events or trading labels."""
import numpy as np

def geometry(f):
    mountain=f['mountain'];ma=f['ma']
    valid=np.isfinite(mountain)&np.isfinite(ma)
    inside=valid&(ma>np.minimum(0,mountain))&(ma<np.maximum(0,mountain))
    separation=np.where(inside,abs(mountain-ma),np.nan)
    return valid,inside,separation
