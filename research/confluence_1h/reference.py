"""Independent scalar public-formula audit, not an execution of TradingView Pine.

Deliberately separate loops/arithmetic from indicators.py. These fixtures test
the audited mathematical specification, never independent platform/feed parity.
"""
import math
import numpy as np


def mean(a):return math.fsum(a)/len(a)
def average(a,n):return [mean(a[max(0,i-n+1):i+1]) if i>=n-1 else float('nan') for i in range(len(a))]
def rms(a,n,ema=False):
    result=[];old=None;seed=[]
    for value in a:
        if math.isfinite(value):
            if old is None:
                if ema:old=value
                else:
                    seed.append(value)
                    if len(seed)==n:old=mean(seed)
            else:old=old+(2/(n+1) if ema else 1/n)*(value-old)
        result.append(float('nan') if old is None else old)
    return result


def calculate_scalar(bars):
    t,o,h,l,c,v=map(list,np.asarray(bars,float).T);n=len(c);nan=float('nan')
    def ratio(a,b):return a/b if b!=0 else nan
    mid=[(a+b)/2 for a,b in zip(h,l)];fast=average(mid,5);slow=average(mid,34)
    ao=[a-b for a,b in zip(fast,slow)];p=[sum(x)/4 for x in zip(o,h,l,c)];typical=[sum(x)/3 for x in zip(h,l,c)]
    tr=[nan]+[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,n)]
    atr=rms([h[0]-l[0]]+tr[1:],14);dtr=rms(tr,14)
    pdm=[nan];mdm=[nan]
    for i in range(1,n):
        u=h[i]-h[i-1];d=l[i-1]-l[i];pdm.append(u if u>d and u>0 else 0.);mdm.append(d if d>u and d>0 else 0.)
    plus=[100*ratio(x,y) for x,y in zip(rms(pdm,14),dtr)];minus=[100*ratio(x,y) for x,y in zip(rms(mdm,14),dtr)]
    dx=[100*abs(x-y)/(x+y if x+y else 1) for x,y in zip(plus,minus)];adx=rms(dx,14)
    up=[nan]+[max(0,p[i]-p[i-1]) for i in range(1,n)];dn=[nan]+[max(0,p[i-1]-p[i]) for i in range(1,n)]
    rsi=[100*ratio(a,a+b) for a,b in zip(rms(up,14),rms(dn,14))]
    mfip=[];mfin=[]
    for i in range(n):
        change=typical[i]-typical[i-1] if i else 0
        mfip.append(typical[i]*v[i] if change>0 else 0);mfin.append(typical[i]*v[i] if change<0 else 0)
    pos=average(mfip,14);neg=average(mfin,14);mfi=[100*ratio(a,a+b) for a,b in zip(pos,neg)]
    boll=[];stoch=[];width=[]
    for i in range(n):
        if i>=24:
            z=p[i-24:i+1];mu=mean(z);sd=math.sqrt(mean([(a-mu)**2 for a in z]));boll.append(100*ratio(p[i]-mu,4*sd))
        else:boll.append(nan)
        stoch.append(100*ratio(p[i]-min(l[i-20:i+1]),max(h[i-20:i+1])-min(l[i-20:i+1])) if i>=20 else nan)
        if i>=6:
            z=c[i-6:i+1];mu=mean(z);width.append(2*math.sqrt(mean([(a-mu)**2 for a in z]))/mu)
        else:width.append(nan)
    sm=average(stoch,3);trend=[(a+b+z+w/3)/2 for a,b,z,w in zip(rsi,mfi,boll,sm)]
    bbwp=[]
    for i in range(n):
        past=width[max(7,i-100):i]
        if i<7 or not past:bbwp.append(nan);continue
        lower=sum(x<width[i] for x in past);equal=sum(x==width[i] for x in past)
        index=lower+equal-1 if equal else lower;bbwp.append(100*index/len(past))
    return {k:np.asarray(x) for k,x in dict(ao=ao,adx=adx,plus_di=plus,minus_di=minus,atr=atr,
        rsi=rsi,mfi=mfi,boll=boll,stoch=sm,kon_trend=trend,kon_signal=rms(trend,15,True),bbwp=bbwp).items()}
