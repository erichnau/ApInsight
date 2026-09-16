"""Reversible display processing; input arrays are samples x positions."""
import numpy as np
from scipy.ndimage import uniform_filter1d


def agc_display(data, window=50, strength=1., floor_fraction=.05):
    """NaN-aware RMS AGC, global RMS target, blended in log gain."""
    a = np.asarray(data, dtype=float)
    if a.ndim != 2 or not 1 <= window <= len(a):
        raise ValueError('AGC window must be between 1 and the sample count.')
    if not 0 <= strength <= 1 or not 0 < floor_fraction <= 1:
        raise ValueError('Strength must be 0–1; RMS floor fraction must be >0 and <=1.')
    valid = np.isfinite(a)
    count = uniform_filter1d(valid.astype(float), int(window), axis=0, mode='constant')
    energy = uniform_filter1d(np.where(valid, a, 0.)**2, int(window), axis=0, mode='constant')
    rms = np.sqrt(np.divide(energy, count, out=np.zeros_like(a), where=count>0))
    target = np.sqrt(np.mean(a[valid]**2)) if valid.any() else 0.
    if target == 0 or strength == 0:
        return a.copy()
    gain = (target / np.maximum(rms, target*floor_fraction))**strength
    return np.where(valid, a*gain, np.nan)


def topographic_display(data, dt_ns, heights, velocity=.1, antenna_offset=0.):
    """Vertical datum shift, constant velocity; not topographic migration.
    Positive antenna_offset is subtracted from recorded z to estimate ground z.
    Returns padded amplitudes, elevation centres and ground heights.
    """
    a = np.asarray(data, float); h = np.asarray(heights, float)-antenna_offset
    if h.shape != (a.shape[1],) or not np.isfinite(h).any():
        raise ValueError('No usable per-column source elevations.')
    if not np.isfinite(dt_ns) or dt_ns<=0 or not 0<velocity<=.3 or not np.isfinite(antenna_offset):
        raise ValueError('Positive sample interval and velocity <=0.3 m/ns required.')
    dz = dt_ns*velocity/2.; datum = np.nanmax(h)
    shifts = (datum-h)/dz
    extra = int(np.ceil(np.nanmax(shifts)))
    if extra>100000 or (len(a)+extra)*a.shape[1]>50_000_000:
        raise ValueError('Elevation range would create an excessive display; check height units.')
    t = np.arange(len(a)+extra); out = np.full((len(t),a.shape[1]),np.nan)
    for j in np.flatnonzero(np.isfinite(h)):
        out[:,j] = np.interp(t-shifts[j],np.arange(len(a)),a[:,j],left=np.nan,right=np.nan)
    return out, datum-t*dz, h


def edges(centres):
    c=np.asarray(centres,float)
    if len(c)<2 or not np.isfinite(c).all() or np.any(np.diff(c)==0):
        raise ValueError('At least two distinct finite coordinates required.')
    return np.r_[c[0]-(c[1]-c[0])/2, (c[:-1]+c[1:])/2, c[-1]+(c[-1]-c[-2])/2]


def smooth_heights(heights, distance, radius_m=.35):
    """Median despiking then Gaussian local-linear smoothing; radius_m is sigma.
    Uses +/-3 sigma support; preserves a linear slope at section ends.
    Missing heights split runs. Zero disables the operation.
    """
    h=np.asarray(heights,float);x=np.asarray(distance,float);out=h.copy()
    if not np.isfinite(radius_m) or radius_m<0:raise ValueError('Height smoothing sigma must be >=0.')
    if radius_m==0:return out
    ids=np.flatnonzero(np.isfinite(h))
    gap=max(.1,3*np.median(np.diff(x))) if len(x)>1 else .1
    runs=np.split(ids,np.flatnonzero((np.diff(ids)>1)|(np.diff(x[ids])>gap))+1)
    for run in runs:
        if not len(run):continue
        # Residual median preserves regional slope better than a raw running median.
        baseline=np.interp(x[run],[x[run[0]],x[run[-1]]],[h[run[0]],h[run[-1]]]) if len(run)>1 else h[run]
        residual=h[run]-baseline
        med=np.array([np.median(residual[abs(x[run]-x[j])<=radius_m]) for j in run])+baseline
        for j in run:
            dx=x[run]-x[j];use=abs(dx)<=3*radius_m;d=dx[use];v=med[use]
            w=np.exp(-.5*(d/radius_m)**2)
            design=np.column_stack((np.ones(len(d)),d))
            fit=np.linalg.lstsq(design*np.sqrt(w[:,None]),v*np.sqrt(w),rcond=None)[0]
            out[j]=fit[0]
    return out


def late_smoothing(data, dt_ns, start_ns=35., ramp_ns=5., strength=.5):
    """NaN-aware 3x3 mean, softly blended below a user-selected time."""
    from scipy.ndimage import uniform_filter
    a=np.asarray(data,float)
    if not np.isfinite([start_ns,ramp_ns,strength]).all() or start_ns<0 or ramp_ns<=0 or not 0<=strength<=1:
        raise ValueError('Late smoothing: start >=0, ramp >0, strength 0–1.')
    valid=np.isfinite(a);w=uniform_filter(valid.astype(float),3,mode='nearest')
    avg=np.divide(uniform_filter(np.where(valid,a,0.),3,mode='nearest'),w,out=a.copy(),where=w>0)
    blend=strength*np.clip((np.arange(len(a))*dt_ns-start_ns)/ramp_ns,0,1)[:,None]
    return np.where(valid,(1-blend)*a+blend*avg,np.nan)
