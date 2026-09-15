"""Diagnostic fixed-shift test on exported NPZs. Requires numpy/scipy/matplotlib.
No input modifications, amplitude normalization, or spatial interpolation.
Distances are along A's exported trajectory, NOT the polysection.
Calibration/validation are adjacent blocks and are not statistically independent.
Channel and loop-pass effects remain confounded. Quality flags are not in these NPZs.
"""
from pathlib import Path
import argparse, csv, json
import numpy as np
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

INPUT = Path('D:/05_sites/Keldur/processing/PreProcData/nomig/B_10072022_nomig_0003_source_diagnostics')
# Edit these intervals in acquisition-trajectory metres, not polysection metres.
TRAIN = (9.70, 9.90)
TEST = (9.95, 10.20)
VARIABLE = (8.00, 8.60)
WINDOWS = {'early': (25,90), 'middle': (140,210), 'late': (210,450)}
MAX_LAG = 8

def corr(x,y):
    ok=np.isfinite(x)&np.isfinite(y)
    if ok.sum()<20: return np.nan
    x=x[ok]-x[ok].mean(); y=y[ok]-y[ok].mean()
    d=np.linalg.norm(x)*np.linalg.norm(y)
    return float(x@y/d) if d else np.nan

def score(a,b,lo,hi,k):
    # Identical central A samples and length for every candidate lag.
    return corr(a[lo+MAX_LAG:hi-MAX_LAG],b[lo+MAX_LAG+k:hi-MAX_LAG+k])

def advance(b,k):
    out=np.full(len(b),np.nan)
    if k>0: out[:-k]=b[k:]
    elif k<0: out[-k:]=b[:k]
    else: out[:]=b
    return out

def read(path):
    with np.load(path,allow_pickle=False) as f: d={k:f[k].copy() for k in f.files}
    n=len(d['trace_numbers'])
    if d['amplitudes'].shape!=(n,512): raise ValueError(f'{path}: expected (traces,512) amplitudes')
    if not np.isfinite(np.c_[d['x'],d['y']]).all(): raise ValueError('Nonfinite XY')
    return d

def main(folder,out,tolerance):
    out.mkdir(parents=True,exist_ok=True); summaries=[]
    for ca,cb in [(13,0),(14,1),(15,2)]:
        a=read(folder/f'T2943_CH{ca:02}.npz'); b=read(folder/f'T7491_CH{cb:02}.npz')
        xa=np.c_[a['x'],a['y']]; xb=np.c_[b['x'],b['y']]
        dist,j=cKDTree(xb).query(xa); _,rev=cKDTree(xa).query(xb)
        s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xa,axis=0),axis=1))]
        ids=np.flatnonzero((dist<=tolerance)&(rev[j]==np.arange(len(j))))
        def subset(interval): return ids[(s[ids]>=interval[0])&(s[ids]<=interval[1])]
        train=subset(TRAIN); test=subset(TEST); variable=subset(VARIABLE)
        if len(train)<3 or len(test)<3: raise ValueError(f'CH{ca}: insufficient train/test matches; widen configured intervals')
        # Estimate ONE lag from middle-window calibration traces only.
        candidates=np.arange(-MAX_LAG,MAX_LAG+1)
        objectives=np.array([np.median([score(a['amplitudes'][i],b['amplitudes'][j[i]],140,210,int(k)) for i in train]) for k in candidates])
        if not np.isfinite(objectives).all(): raise ValueError('Undefined calibration correlations')
        best=np.flatnonzero(np.isclose(objectives,objectives.max(),atol=1e-10,rtol=0))
        k=int(candidates[best[np.argmin(abs(candidates[best]))]])
        stem=f'CH{ca:02}_CH{cb:02}'; rows=[]
        for region,idx in [('calibration',train),('held_out',test),('variable',variable)]:
            for i in idx:
                for window,(lo,hi) in WINDOWS.items():
                    aa=a['amplitudes'][i].astype(float);bb=b['amplitudes'][j[i]].astype(float)
                    c0=score(aa,bb,lo,hi,0);c1=score(aa,bb,lo,hi,k)
                    rows.append(dict(region=region,window=window,trace_a=int(a['trace_numbers'][i]),trace_b=int(b['trace_numbers'][j[i]]),distance_m=float(s[i]),xy_separation_m=float(dist[i]),dz_m=float(b['z'][j[i]]-a['z'][i]),time_zero_a=float(a['time_zero'][i]),time_zero_b=float(b['time_zero'][j[i]]),fixed_lag=k,correlation_before=c0,correlation_after=c1,change=c1-c0))
        with (out/f'{stem}.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
        result=dict(pair=stem,fixed_lag=k,search_limit=abs(k)==MAX_LAG,calibration_count=len(train),held_out_count=len(test),variable_count=len(variable),metrics=[])
        for region in ('held_out','variable'):
            for name in WINDOWS:
                rr=[r for r in rows if r['region']==region and r['window']==name]
                if rr: result['metrics'].append(dict(region=region,window=name,median_before=float(np.nanmedian([r['correlation_before'] for r in rr])),median_after=float(np.nanmedian([r['correlation_after'] for r in rr]))))
        summaries.append(result)
        fig,axes=plt.subplots(3,1,figsize=(12,10),layout='constrained')
        axes[0].plot(candidates,objectives,'o-');axes[0].axvline(k,color='red',ls='--');axes[0].set(xlabel='Candidate lag (positive = B later)',ylabel='Median calibration correlation')
        for name,color in zip(WINDOWS,('tab:blue','tab:orange','tab:green')):
            rr=[r for r in rows if r['window']==name and r['region']!='calibration']
            axes[1].scatter([r['distance_m'] for r in rr],[r['change'] for r in rr],label=name,color=color,s=18)
        axes[1].axhline(0,color='grey');axes[1].legend();axes[1].set(xlabel='Distance along A (m)',ylabel='Correlation change: fixed shift')
        axes[2].plot(s,dist*100,label='Nearest XY distance (all A traces)')
        axes[2].axhline(tolerance*100,color='grey',ls='--',label='Matching threshold')
        centre_a=int(np.argmin(abs(a['trace_numbers']-2943))); centre_b=int(np.argmin(abs(b['trace_numbers']-7491)))
        # Nearest vertex approximation, explicitly labelled.
        projected=int(cKDTree(xa).query(xb[centre_b])[1])
        axes[2].axvline(s[centre_a],color='black',label='A centre T2943')
        axes[2].axvline(s[projected],color='purple',ls=':',label='B centre T7491 nearest A position')
        for interval,color,label in [(TRAIN,'green','Calibration'),(TEST,'blue','Held out'),(VARIABLE,'orange','Variable')]: axes[2].axvspan(*interval,color=color,alpha=.15,label=label)
        axes[2].set(xlabel='Distance along full exported A trajectory (m)',ylabel='XY separation (cm)');axes[2].legend(fontsize=8,ncol=2)
        for ax in axes: ax.grid(alpha=.2)
        fig.suptitle(f'{stem}: one fixed shift = {k:+d} samples; middle-window calibration only')
        fig.savefig(out/f'{stem}_validation.png',dpi=150);plt.close(fig)
        # Deterministic representatives, chosen by distance, never by best fit.
        fig,axes=plt.subplots(4,2,figsize=(14,12),sharex=True,layout='constrained')
        for row,(region,idx,frac) in enumerate([('held_out',test,.25),('held_out',test,.75),('variable',variable,.25),('variable',variable,.75)]):
            if not len(idx):
                for ax in axes[row]: ax.text(.5,.5,'No matches',transform=ax.transAxes)
                continue
            i=idx[round((len(idx)-1)*frac)];aa=a['amplitudes'][i];bb=b['amplitudes'][j[i]];shifted=advance(bb,k)
            for col,yy in enumerate((bb,shifted)):
                axes[row,col].plot(aa,label=f'A CH{ca} T{a["trace_numbers"][i]}',lw=1)
                axes[row,col].plot(yy,label=f'B CH{cb} T{b["trace_numbers"][j[i]]}',lw=1,alpha=.8)
                axes[row,col].set_title(f'{region}, {s[i]:.2f} m — '+('original' if col==0 else f'B advanced {k:+d} samples'))
                axes[row,col].legend(fontsize=7);axes[row,col].set_ylabel('Decoded amplitude');axes[row,col].grid(alpha=.2)
            limits=axes[row,0].get_ylim();axes[row,1].set_ylim(limits)
        for ax in axes[-1]: ax.set_xlabel('Stored sample index (no time-zero subtraction)')
        fig.suptitle(f'{stem}: full waveforms; identical amplitude scale within each row; no normalization')
        fig.savefig(out/f'{stem}_waveforms.png',dpi=150);plt.close(fig)
    (out/'summary.json').write_text(json.dumps(dict(train=TRAIN,test=TEST,variable=VARIABLE,windows=WINDOWS,pairs=summaries),indent=2))
    for r in summaries: print(r)
    print('Saved to',out.resolve())

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=INPUT)
    p.add_argument('--output',type=Path)
    p.add_argument('--max-distance',type=float,default=.05)
    args=p.parse_args()
    if not np.isfinite(args.max_distance) or args.max_distance<=0: p.error('max-distance must be finite and positive')
    main(args.input,args.output or args.input/'constant_shift_test',args.max_distance)
