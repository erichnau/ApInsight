import numpy as np


# ------------------------------------------------------------
# AGC GAIN
# ------------------------------------------------------------

def agc_gain(radar, window=50):

    radar = radar.copy()
    n_samples, n_traces = radar.shape

    for tr in range(n_traces):

        trace = radar[:, tr]

        energy = np.sqrt(
            np.convolve(
                trace**2,
                np.ones(window)/window,
                mode="same"
            )
        )

        energy[energy == 0] = 1e-6

        radar[:, tr] = trace / energy

    return radar


# ------------------------------------------------------------
# DEPTH TAPER
# ------------------------------------------------------------

def depth_taper(radar):

    radar = radar.copy()
    n_samples, _ = radar.shape

    depth = np.linspace(0,1,n_samples)

    taper = 1/(1 + 4*depth**4)

    radar *= taper[:,None]

    return radar


# ------------------------------------------------------------
# VERTICAL SMOOTHING
# ------------------------------------------------------------

def vertical_smoothing(radar):

    radar = radar.copy()

    kernel = np.array([1,2,3,2,1]) / 9

    n_samples, n_traces = radar.shape

    for tr in range(n_traces):
        radar[:,tr] = np.convolve(
            radar[:,tr],
            kernel,
            mode="same"
        )

    return radar


# ------------------------------------------------------------
# DYNAMIC RANGE CLIPPING
# ------------------------------------------------------------

def clip_amplitude(radar, percentile=98):
    if radar is None or radar.size == 0:
        print("[WARNING] Empty radar passed to clip_amplitude → skipping")
        return radar

    radar = radar.copy()

    vmax = np.percentile(np.abs(radar), percentile)

    radar = np.clip(radar, -vmax, vmax)

    radar /= vmax

    return radar


# ------------------------------------------------------------
# ML NORMALIZATION
# ------------------------------------------------------------

def normalize_radar(radar):

    radar = radar.copy()

    radar -= np.mean(radar)

    std = np.std(radar)

    if std > 0:
        radar /= std

    return radar


# ------------------------------------------------------------
# COMPLETE PROCESSING PIPELINE
# ------------------------------------------------------------

def process_radargram(radar):

    radar = agc_gain(radar, window=120)

    radar = depth_taper(radar)

    radar = vertical_smoothing(radar)

    radar = clip_amplitude(radar, percentile=98)

    radar = normalize_radar(radar)

    return radar