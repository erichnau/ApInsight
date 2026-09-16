"""Documented ReflexW ASCII-3COLUMS import format (not native DAT/PAR)."""
from pathlib import Path
import numpy as np


def export_reflex_ascii(path,data,distance,dt_ns):
    a=np.asarray(data,float);x=np.asarray(distance,float)
    if a.ndim!=2 or a.shape[1]!=len(x) or len(x)<2 or not np.isfinite(x).all() or not np.isfinite(dt_ns) or dt_ns<=0:
        raise ValueError('Invalid section geometry/time sampling.')
    dx=np.diff(x);step=float(np.median(dx));trim=False
    if step<=0 or np.any(dx<=0):raise ValueError('Distances must increase.')
    if not np.allclose(dx,step,rtol=1e-5,atol=1e-8):
        if len(dx)>1 and np.allclose(dx[:-1],step,rtol=1e-5,atol=1e-8) and dx[-1]<step:
            a=a[:,:-1];x=x[:-1];trim=True
        else:raise ValueError('ReflexW export requires regular distance sampling.')
    valid=np.isfinite(a);t=np.arange(len(a))*dt_ns;path=Path(path)
    with path.open('w',encoding='ascii') as f:
        f.write('distance_m time_ns amplitude\n')
        for j,d in enumerate(x):
            np.savetxt(f,np.column_stack((np.full(len(t),d),t,np.where(valid[:,j],a[:,j],0.))),fmt='%.12g')
    np.savez_compressed(str(path)+'.validity.npz',valid=valid,distance=x,time_ns=t)
    Path(str(path)+'.import.txt').write_text(
        'ReflexW import: ASCII-3COLUMS; time dimension ns; use floating-point storage.\n'
        f'Traces: {len(x)}; samples: {len(t)}; dt: {dt_ns:.12g} ns; dx: {step:.12g} m.\n'
        'One overall header line; trace-major rows containing distance, time, amplitude.\n'
        'Data are current AGC/smoothing amplitudes BEFORE topographic placement.\n'
        f'Missing samples filled with zero: {np.count_nonzero(~valid)}; mask in .validity.npz.\n'
        f'Short nonuniform last interval omitted: {trim}.\n'
        'Not a native ReflexW DAT/PAR file. Import and save in ReflexW.\n'
        'Specification: https://www.sandmeier-geo.de/Download/reflexw_manual.pdf (ASCII-3COLUMS).\n',encoding='utf8')
