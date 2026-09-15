"""Compare exported ApPPD channel NPZs; no spatial interpolation or corrections.
Run: python diagnose_loop_overlap.py --input PATH_TO_NPZS
Requires numpy, scipy, matplotlib. Windows use stored sample indices [start, stop).
Positive lag means group B occurs later. Z is recorded elevation, not antenna clearance.
Channel and pass effects are confounded in these comparisons.
"""
from pathlib import Path
import argparse
import csv
import json
import numpy as np
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

WINDOWS = {'early': (25, 90), 'middle': (140, 210), 'late': (210, 450)}
PAIRS = [(13, 0), (14, 1), (15, 2)]


def correlation(x, y):
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 20:
        return np.nan
    x, y = x[valid], y[valid]
    x, y = x-x.mean(), y-y.mean()
    norm = np.linalg.norm(x)*np.linalg.norm(y)
    return float(x@y/norm) if norm > 0 else np.nan


def metrics(x, y, max_lag):
    # Fixed-length central support for every lag; demean each comparison.
    n = len(x)
    u = x[max_lag:n-max_lag]
    scores = np.array([correlation(u, y[max_lag+k:n-max_lag+k])
                       for k in range(-max_lag, max_lag+1)])
    if not np.isfinite(scores).any():
        return np.nan, np.nan, np.nan, np.nan, False
    best = int(np.nanargmax(scores))
    lag = best-max_lag
    valid = np.isfinite(x) & np.isfinite(y)
    xx, yy = x[valid], y[valid]
    rms_x = np.std(xx) if len(xx) else np.nan
    ratio = float(np.std(yy)/rms_x) if rms_x > 0 else np.nan
    return lag, scores[max_lag], scores[best], ratio, abs(lag) == max_lag


def load(path):
    with np.load(path, allow_pickle=False) as f:
        d = {k: f[k].copy() for k in f.files}
    n = len(d['trace_numbers'])
    if d['amplitudes'].ndim != 2 or d['amplitudes'].shape[0] != n:
        raise ValueError(f'{path}: expected amplitudes shaped (traces, samples)')
    for key in ('x', 'y', 'z', 'time_zero'):
        if np.asarray(d[key]).shape != (n,):
            raise ValueError(f'{path}: expected {key} with one value per trace')
    if not np.isfinite(np.c_[d['x'], d['y']]).all():
        raise ValueError(f'{path}: nonfinite XY coordinates')
    return d


def run(folder, out, tolerance, max_lag):
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for ca, cb in PAIRS:
        a = load(folder/f'T2943_CH{ca:02}.npz')
        b = load(folder/f'T7491_CH{cb:02}.npz')
        xy_a, xy_b = np.c_[a['x'], a['y']], np.c_[b['x'], b['y']]
        dist, nearest = cKDTree(xy_b).query(xy_a)
        _, reverse = cKDTree(xy_a).query(xy_b)
        ids = np.flatnonzero((dist <= tolerance) & (reverse[nearest] == np.arange(len(dist))))
        if not len(ids):
            print(f'CH{ca}/CH{cb}: no reciprocal matches within {tolerance} m'); continue
        along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy_a, axis=0), axis=1))]
        rows = []
        for i in ids:
            j = int(nearest[i])
            for name, (lo, hi) in WINDOWS.items():
                if hi > min(a['amplitudes'].shape[1], b['amplitudes'].shape[1]):
                    raise ValueError('Window exceeds available samples')
                lag, zero, peak, ratio, boundary = metrics(a['amplitudes'][i,lo:hi], b['amplitudes'][j,lo:hi], max_lag)
                rows.append(dict(window=name, start_sample=lo, stop_sample=hi,
                    trace_a=int(a['trace_numbers'][i]), trace_b=int(b['trace_numbers'][j]),
                    channel_a=ca, channel_b=cb, distance_along_a_m=float(along[i]),
                    x_a=float(a['x'][i]), y_a=float(a['y'][i]), z_a=float(a['z'][i]),
                    x_b=float(b['x'][j]), y_b=float(b['y'][j]), z_b=float(b['z'][j]),
                    separation_m=float(dist[i]), dz_b_minus_a_m=float(b['z'][j]-a['z'][i]),
                    time_zero_a=float(a['time_zero'][i]), time_zero_b=float(b['time_zero'][j]),
                    lag_samples=lag, correlation_zero=zero, correlation_best=peak,
                    rms_ratio_b_over_a=ratio, search_boundary=boundary))
        stem=f'CH{ca:02}_CH{cb:02}'
        with (out/f'{stem}.csv').open('w', newline='') as f:
            w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        fig, axes=plt.subplots(5,1,figsize=(12,13),sharex=True,layout='constrained')
        for color, name in zip(('tab:blue','tab:orange','tab:green'),WINDOWS):
            r=[v for v in rows if v['window']==name]
            x=np.array([v['distance_along_a_m'] for v in r])
            for ax, key in zip(axes[:4], ('lag_samples','correlation_zero','correlation_best','rms_ratio_b_over_a')):
                ax.scatter(x,[v[key] for v in r],s=12,color=color,label=f'{name} {WINDOWS[name]}')
            bad=[v for v in r if v['search_boundary']]
            axes[0].scatter([v['distance_along_a_m'] for v in bad], [v['lag_samples'] for v in bad],marker='x',color='red',s=45)
            summary.append(dict(pair=stem,window=name,matches=len(r),
                median_lag=float(np.nanmedian([v['lag_samples'] for v in r])),
                median_correlation_zero=float(np.nanmedian([v['correlation_zero'] for v in r])),
                median_correlation_best=float(np.nanmedian([v['correlation_best'] for v in r]))))
        r=rows[::len(WINDOWS)]
        x=[v['distance_along_a_m'] for v in r]
        axes[4].scatter(x,[100*v['separation_m'] for v in r],s=12,label='XY separation')
        axes[4].scatter(x,[100*v['dz_b_minus_a_m'] for v in r],s=12,label='Z: B minus A')
        for ax,label in zip(axes,('Lag (samples)','Correlation: no shift','Correlation: best lag','RMS B / A','Difference (cm)')):
            ax.set_ylabel(label);ax.grid(alpha=.25)
        axes[0].legend(ncol=3,fontsize=8)
        axes[0].axhline(0,color='grey',lw=.6)
        axes[1].set_ylim(-1,1);axes[2].set_ylim(-1,1)
        axes[3].axhline(1,color='grey',lw=.6);axes[4].legend()
        axes[4].set_xlabel('Distance along exported group A trajectory (m; not polysection distance)')
        fig.suptitle(f'T2943 CH{ca} versus T7491 CH{cb}: {len(ids)} reciprocal XY matches ≤ {100*tolerance:g} cm\nStored samples; positive lag = B later; red crosses = search limit; no correction applied')
        fig.savefig(out/f'{stem}.png',dpi=160);plt.close(fig)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)

    p.add_argument(
        '--input',
        type=Path,
        default=Path(
            'D:/05_sites/Keldur/processing/PreProcData/nomig/'
            'B_10072022_nomig_0003_source_diagnostics'
        ),
    )
    p.add_argument('--output', type=Path, default=None)
    p.add_argument('--max-distance', type=float, default=.05)
    p.add_argument('--max-lag', type=int, default=8)

    args = p.parse_args()

    if args.max_distance <= 0 or not 1 <= args.max_lag <= 20:
        p.error(
            'max-distance must be positive; '
            'max-lag must be between 1 and 20'
        )

    run(
        args.input,
        args.output or args.input / 'loop_overlap_diagnostics',
        args.max_distance,
        args.max_lag,
    )