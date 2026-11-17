"""Literal user-supplied BackQuant V5 control flow, MPL-2.0, © BackQuant.

No OPT, Lloyd substitution, centroid shortcuts, eviction or repaired NA arrays.
Built-in NA/percentile semantics follow the previously audited PineV5 reference;
TradingOne's interpreter still requires independent numerical evidence.
"""
import copy
import math


def percentile(values, pct):
    a=sorted(v for v in values if v is not None and math.isfinite(v))
    if not a:return None
    rank=(len(a)-1)*pct/100
    lo,hi=math.floor(rank),math.ceil(rank)
    return a[lo]+(a[hi]-a[lo])*(rank-lo)


def avg(values):
    a=[v for v in values if v is not None and math.isfinite(v)]
    return sum(a)/len(a) if a else None


def equal_v5(left,right):
    if len(left)!=len(right):return False
    for a,b in zip(left,right):
        # `if na != value` is not true in the original PineV5 condition.
        if a is not None and b is not None and a!=b:return False
    return True


def minimum_index(values):
    finite=[v for v in values if v is not None and math.isfinite(v)]
    if not finite:return 0  # all-NA case; irrelevant to finite thresholds, unverified externally
    return values.index(min(finite))


class OriginalMLRSI:
    def __init__(self,last_bar_index,*,length=27,ma='ALMA',period=4,sigma=1,max_data=3000,max_iter=1000):
        if type(last_bar_index) is not int or last_bar_index<0:raise ValueError('LOAD_ANCHOR_REQUIRED')
        if length not in (27,29) or ma not in ('ALMA','EMA') or period!=4 or sigma!=1:
            raise ValueError('EXPLICIT_AUDITED_PROFILE_ONLY')
        self.anchor=last_bar_index;self.length=length;self.ma=ma;self.period=period;self.sigma=sigma
        self.max_data=max_data;self.max_iter=max_iter;self.count=0;self.previous=None
        self.seed=[];self.gain=self.loss=None;self.smoothed=None;self.raw_window=[]
        self.values=[];self.centroids=[None]*3;self.cluster_plots=[None]*3
        self.factors=list(range(10,91,5))  # source creates this but does not consume it later

    def push(self,low):
        low=float(low)
        if not math.isfinite(low) or low<=0:raise ValueError('LOW_INVALID')
        i=self.count;raw=None
        if self.previous is not None:
            d=low-self.previous;up,down=max(d,0),max(-d,0)
            if self.gain is None:
                self.seed.append((up,down))
                if len(self.seed)==self.length:
                    self.gain=sum(x[0] for x in self.seed)/self.length
                    self.loss=sum(x[1] for x in self.seed)/self.length
            else:
                self.gain=self.gain*(1-1/self.length)+up/self.length
                self.loss=self.loss*(1-1/self.length)+down/self.length
            if self.gain is not None and self.gain+self.loss:
                raw=100*self.gain/(self.gain+self.loss)
        self.previous=low;self.count+=1
        self.raw_window.append(raw);self.raw_window=self.raw_window[-self.period:]
        value=None
        if self.ma=='EMA':
            if raw is not None:
                self.smoothed=raw if self.smoothed is None else .4*raw+.6*self.smoothed
                value=self.smoothed
        elif len(self.raw_window)==self.period and all(v is not None for v in self.raw_window):
            # ta.alma(raw,4,0,1): oldest-first Gaussian, offset m=0, s=4.
            weights=[math.exp(-(j*j)/(2*(self.period/self.sigma)**2)) for j in range(self.period)]
            value=sum(w*v for w,v in zip(weights,self.raw_window))/sum(weights)
            self.smoothed=value
        eligible=max(self.anchor,i)-i<=self.max_data
        if eligible:self.values.append(value)
        if len(self.values)>100000:raise ValueError('PINE_ARRAY_LIMIT')
        if len(self.values)>3:
            for j,p in enumerate((25,50,75)):self.centroids[j]=percentile(self.values,p)
        iterations=0
        # Literally construct three leading NA distances/centroids before push.
        for _ in range(self.max_iter+1):
            iterations+=1;groups=[[],[],[]]
            for v in self.values:
                distances=[None,None,None]
                for c in self.centroids:
                    distances.append(None if v is None or c is None else abs(v-c))
                idx=minimum_index(distances)
                groups[0 if idx==0 else 1 if idx==1 else 2].append(v)
            updated=[None,None,None]
            for g in groups:updated.append(avg(g))
            if equal_v5(updated,self.centroids):break
            self.centroids=updated
        low_s,high_s=self.centroids[0],self.centroids[2]
        if value is not None:
            distances=[None,None,None]
            for c in self.centroids:distances.append(None if c is None else abs(value-c))
            idx=minimum_index(distances)
            self.cluster_plots=[value if idx==j else None for j in range(3)]
        valid=value is not None and low_s is not None and high_s is not None
        color='UNKNOWN' if value is None else 'GREEN' if high_s is not None and value>high_s else 'RED' if low_s is not None and value<low_s else 'NEUTRAL'
        return dict(raw=raw,value=value,lower=low_s,upper=high_s,middle=self.centroids[1],color=color,
                    valid=valid,samples=len(self.values),iterations=iterations,eligible=eligible,
                    cluster1=self.cluster_plots[0],cluster2=self.cluster_plots[1],cluster3=self.cluster_plots[2])

    def preview(self,low):
        return copy.deepcopy(self).push(low)

    def state(self):
        return copy.deepcopy(self.__dict__)
