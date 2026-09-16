"""MALA-compatible signed 16-bit RD3 and ASCII RAD, for ReflexW import."""
from pathlib import Path
import json
import numpy as np


def export_mala_rd3(path,data,distance,dt_ns,heights=None,settings=None):
    a=np.asarray(data,float);x=np.asarray(distance,float)
    if a.ndim!=2 or len(a)<2 or a.shape[1]!=len(x) or len(x)<2 or not np.isfinite(x).all() or not np.isfinite(dt_ns) or dt_ns<=0:
        raise ValueError('Invalid data, distances or sample interval.')
    dx=np.diff(x);step=float(np.median(dx));trim=False
    if step<=0 or np.any(dx<=0):raise ValueError('Distances must increase.')
    if not np.allclose(dx,step,rtol=1e-5,atol=1e-8):
        if len(dx)>1 and np.allclose(dx[:-1],step,rtol=1e-5,atol=1e-8) and dx[-1]<step:
            a=a[:,:-1];x=x[:-1];trim=True
        else:raise ValueError('RD3 requires regular trace spacing.')
    valid=np.isfinite(a)
    if not valid.any():raise ValueError('No finite amplitudes to export.')
    peak=float(np.max(abs(a[valid])));scale=peak/32760 if peak else 1.
    quant=np.rint(np.where(valid,a,0.)/scale).astype('<i2')
    nt,nx=a.shape;path=Path(path)
    # FREQUENCY is sampling frequency in MHz, not antenna centre frequency.
    header={'SAMPLES':nt,'FREQUENCY':1000/dt_ns,'FREQUENCY STEPS':1,'SIGNAL POSITION':0,
        'RAW SIGNAL POSITION':0,'DISTANCE FLAG':1,'TIME FLAG':0,'PROGRAM FLAG':0,
        'EXTERNAL FLAG':0,'TIME INTERVAL':0,'DISTANCE INTERVAL':step,'OPERATOR':'ApInsight export',
        'CUSTOMER':'','SITE':'Processed polysection','ANTENNAS':'Unknown',
        'ANTENNA ORIENTATION':'Unknown','ANTENNA SEPARATION':0,'COMMENT':'Processed data; see companion metadata',
        'TIMEWINDOW':(nt-1)*dt_ns,'STACKS':1,'STACK EXPONENT':0,
        'STACKING TIME':0,'LAST TRACE':nx,'STOP POSITION':float(x[-1]-x[0]),'SYSTEM CALIBRATION':0}
    quant.T.copy().tofile(path)
    path.with_suffix('.rad').write_text(''.join(f'{k}: {v}\n' for k,v in header.items()),encoding='ascii')
    np.savez_compressed(str(path)+'.metadata.npz',valid=valid,amplitude_scale=scale,distance=x,
        dt_ns=dt_ns,height=np.asarray(heights)[:nx] if heights is not None else np.array([]),
        settings_json=json.dumps(settings or {}),trimmed_final_interval=trim,
        note='RD3 amplitudes times amplitude_scale approximate input. Missing samples zero-filled. Export precedes topographic placement.')
    return dict(scale=scale,trimmed=trim)
