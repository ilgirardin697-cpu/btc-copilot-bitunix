"""Stateful evaluation of the unchanged public formulas; exact-parity gated."""
from bisect import bisect_left,bisect_right,insort
from collections import deque
import numpy as np
from research.confluence_1h.indicators import pine_rightmost

HOUR=3600000
NAN=np.float64('nan')


def div(a,b):return np.divide(a,b) if b!=0 else NAN


class Smoother:
    def __init__(self,n,kind):self.n=n;self.kind=kind;self.last=NAN;self.seed=[]
    def step(self,v):
        if not np.isfinite(v):return self.last
        if not np.isfinite(self.last):
            if self.kind=='ema':self.last=v
            else:
                self.seed.append(v)
                if len(self.seed)<self.n:return NAN
                self.last=float(np.mean(self.seed))
        else:
            alpha=2/(self.n+1) if self.kind=='ema' else 1/self.n
            self.last=alpha*v+(1-alpha)*self.last
        return self.last


class Rank:
    def __init__(self):self.raw=deque();self.ordered=[]
    def step(self,v):
        r=(bisect_left(self.ordered,v)+bisect_right(self.ordered,v))/(2*720) if len(self.raw)==len(self.ordered)==720 and np.isfinite(v) else NAN
        self.raw.append(v)
        if np.isfinite(v):insort(self.ordered,float(v))
        if len(self.raw)>720:
            x=self.raw.popleft()
            if np.isfinite(x):self.ordered.pop(bisect_left(self.ordered,x))
        return r


class Indicator:
    def __init__(self):
        self.i=0;self.previous=None;self.buffers={};self.smoothers={};self.last={}
        self.pvi=np.float64(1);self.nvi=np.float64(1);self.width_raw=deque();self.width_order=[]
    def roll(self,key,v,n,method='mean',partial=False):
        b=self.buffers.setdefault(key,deque(maxlen=n));b.append(v)
        return getattr(np,method)(np.asarray(b,float)) if len(b)==n or partial else NAN
    def smooth(self,key,v,n,kind='rma'):
        return self.smoothers.setdefault(key,Smoother(n,kind)).step(v)
    def step(self,row):
        t,o,h,l,c,v=np.asarray(row,float);i=self.i;prev=self.previous
        p=(o+h+l+c)/4;typical=(h+l+c)/3;change=p-self.last.get('p',NAN)
        up=self.smooth('up',np.maximum(change,0),14);down=self.smooth('down',np.maximum(-change,0),14)
        rsi=100*div(up,up+down);money=typical*v;delta=typical-self.last.get('typical',NAN)
        pos=self.roll('positive',money if delta>0 else 0,14,'sum');neg=self.roll('negative',money if delta<0 else 0,14,'sum')
        mfi=100*div(pos,pos+neg);base=self.roll('p25',p,25);std=self.roll('std25',p,25,'std')
        boll=100*div(p-base,4*std);low=self.roll('low21',l,21,'min');high=self.roll('high21',h,21,'max')
        k=100*div(p-low,high-low);stoch=self.roll('stoch3',k,3);trend=(rsi+mfi+boll+stoch/3)/2
        signal=self.smooth('red',trend,15,'ema')
        if prev is not None:
            self.pvi=self.pvi*(c/prev[4] if v>prev[5] else 1)
            self.nvi=self.nvi*(c/prev[4] if v<prev[5] else 1)
        layers={}
        for name,x in [('pvi',self.pvi),('nvi',self.nvi)]:
            average=self.smooth(name,x,15,'ema')
            span=self.roll(name+'high',average,90,'max',True)-self.roll(name+'low',average,90,'min',True)
            layers.update({name:x,name+'_ema':average,name+'_osc':100*div(x-average,span)})
        previous=prev[4] if prev is not None else NAN
        tr=np.maximum(h-l,np.maximum(abs(h-previous),abs(l-previous)))
        atr=self.smooth('atr',h-l if i==0 else tr,14)
        plus=h-prev[2] if prev is not None else NAN;minus=prev[3]-l if prev is not None else NAN
        pdm=plus if plus>minus and plus>0 else np.float64(0);mdm=minus if minus>plus and minus>0 else np.float64(0)
        if i==0:pdm=mdm=NAN
        dmitr=self.smooth('dmitr',tr,14);pdi=100*div(self.smooth('pdm',pdm,14),dmitr);mdi=100*div(self.smooth('mdm',mdm,14),dmitr)
        total=pdi+mdi;dx=100*div(abs(pdi-mdi),1 if total==0 else total);adx=self.smooth('adx',dx,14)
        median=(h+l)/2;ao=self.roll('median5',median,5)-self.roll('median34',median,34)
        width=2*div(self.roll('cstd7',c,7,'std'),self.roll('c7',c,7));rank=NAN
        if i>=7 and np.isfinite(width):
            if self.width_order:rank=pine_rightmost(self.width_order,width)*100/len(self.width_order)
            insort(self.width_order,float(width));self.width_raw.append(float(width))
            if len(self.width_raw)>100:
                old=self.width_raw.popleft();self.width_order.pop(pine_rightmost(self.width_order,old))
        result=dict(time=t,kon_trend=trend,kon_signal=signal,rsi=rsi,mfi=mfi,boll=boll,stoch=stoch,
                    minnows=trend+layers['pvi_osc'],sharks=layers['nvi_osc'],atr=atr,plus_di=pdi,minus_di=mdi,
                    adx=adx,ao=ao,bbw=width,bbwp=rank,**layers)
        for name in ('adx','ao','bbwp','kon_trend'):result[name+'_slope']=result[name]-self.last.get(name,NAN)
        self.roll('close200',c,200)
        self.last.update(result,p=p,typical=typical);self.previous=np.asarray(row,float).copy();self.i+=1
        return result
    def context(self,available):
        f=self.last;n=self.i;p=self.previous;ma=np.mean(self.buffers['close200']) if n>=200 else None
        def val(k,minimum):return float(f[k]) if n>=minimum and np.isfinite(f[k]) else None
        ao=val('ao',34)
        return dict(closed=True,rows=n,available_at=int(available),state='UNKNOWN' if ao is None else 'AO_ABOVE_ZERO' if ao>0 else 'AO_BELOW_ZERO' if ao<0 else 'AO_ZERO',
                    open_time=int(p[0]),close=float(p[4]),ao=ao,ao_slope=val('ao_slope',35),adx=val('adx',28),plus_di=val('plus_di',28),minus_di=val('minus_di',28),
                    pececillos=val('minnows',90),bbwp=val('bbwp',108),price_sma200=float(ma) if ma is not None else None,
                    price_regime='UNKNOWN' if ma is None else 'ABOVE' if p[4]>ma else 'BELOW' if p[4]<ma else 'AT')


class MTF:
    def __init__(self):self.indicators={k:Indicator() for k in ('4H','1D','1W')};self.pending={};self.views={}
    def step(self,row,base):
        t=int(row[0]);self.views['1H']=base.context(t+HOUR)
        for name,size,offset in [('4H',4*HOUR,0),('1D',24*HOUR,0),('1W',168*HOUR,96*HOUR)]:
            start=(t-offset)//size*size+offset;b=self.pending.setdefault(name,[])
            if b and int(b[0][0])//size!=(t//size) and name!='1W':b.clear()
            if b and t!=b[-1][0]+HOUR:b.clear()
            if not b and t!=start:continue
            b.append(np.asarray(row,float).copy())
            if len(b)==size//HOUR:
                a=np.asarray(b);c=[start,a[0,1],a[:,2].max(),a[:,3].min(),a[-1,4],a[:,5].sum()]
                self.indicators[name].step(c);self.views[name]=self.indicators[name].context(start+size);b.clear()
        return {k:self.views.get(k,dict(closed=True,rows=0,available_at=None,state='UNKNOWN')) for k in ('1H','4H','1D','1W')}


class Tape:
    def __init__(self):self.n=0;self.capacity=256;self.rows=np.full((256,6),np.nan);self.data={};self.one={}
    def append(self,row,f,one):
        if self.n==self.capacity:
            cap=self.capacity*2;a=np.full((cap,6),np.nan);a[:self.n]=self.rows[:self.n];self.rows=a
            for collection in (self.data,self.one):
                for k,v in collection.items():x=np.full(cap,np.nan);x[:self.n]=v[:self.n];collection[k]=x
            self.capacity=cap
        self.rows[self.n]=row
        for collection,values in ((self.data,f),(self.one,one)):
            for k,v in values.items():
                if k not in collection:collection[k]=np.full(self.capacity,np.nan)
                collection[k][self.n]=v
        self.n+=1
    def past(self,key,k=1):return self.data[key][self.n-k] if self.n>=k else NAN
    def views(self):
        f={k:v[:self.n] for k,v in self.data.items()};one=dict(f);one.update({k:v[:self.n] for k,v in self.one.items()})
        return self.rows[:self.n],{'TURN22_FORWARD_V1':f,'TURN11_EXPLORATORY_V1':one}


class Incremental:
    def __init__(self):self.base=Indicator();self.tape=Tape();self.ranks={};self.mtf=MTF();self.contexts={}
    def rank(self,k,v):return self.ranks.setdefault(k,Rank()).step(v)
    def step(self,row):
        if self.tape.n and row[0]!=self.tape.rows[self.tape.n-1,0]+HOUR:raise ValueError('CONTIGUOUS_H1_REQUIRED')
        f=self.base.step(row);self.contexts=self.mtf.step(row,self.base);past=self.tape.past
        f['pece_slope']=f['minnows']-past('minnows');d=f['adx_slope']
        f['adx_curve']=abs((d+past('adx_slope')-past('adx_slope',2)-past('adx_slope',3))/2)
        f['ao_intensity']=abs(f['ao']-past('ao',2))/row[4];f['ao_level_normalized']=abs(f['ao'])/row[4];f['ao_slope_normalized']=f['ao_slope']/row[4]
        f['pece_intensity']=abs(f['minnows']-past('minnows',2))
        for name in ('adx','adx_curve','ao_intensity','pece_intensity'):f[name+'_rank']=self.rank(name,f[name])
        f['vol_rank']=self.rank('vol',f['atr']/row[4])
        for name,key in [('regime4h','4H'),('regime1d','1D')]:
            state=self.contexts[key].get('price_regime');f[name]=1. if state=='ABOVE' else -1. if state=='BELOW' else 0. if state=='AT' else NAN
        one=dict(adx_curve=abs(d-past('adx_slope')),ao_intensity=abs(f['ao']-past('ao'))/row[4],pece_intensity=abs(f['minnows']-past('minnows')))
        for name in tuple(one):one[name+'_rank']=self.rank('one_'+name,one[name])
        self.tape.append(row,f,one);return self.tape.views()
