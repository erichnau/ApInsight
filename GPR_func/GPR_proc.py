import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from tqdm import tqdm
import pandas as pd

def dewow(trace_collection):
    data2 = np.load(trace_collection)
    data = np.asmatrix(data2, dtype=int)

    totsamps = data.shape[0]
    window = 25
    # If the window is larger or equal to the number of samples,
    # then we can do a much faster dewow
    if (window >= totsamps):
        newdata = data - np.matrix.mean(data, 0)
    else:
        newdata = np.asmatrix(np.zeros(data.shape))
        halfwid = int(np.ceil(window / 2.0))

        # For the first few samples, it will always be the same
        avgsmp = np.matrix.mean(data[0:halfwid + 1, :], 0)
        newdata[0:halfwid + 1, :] = data[0:halfwid + 1, :] - avgsmp

        # for each sample in the middle
        for smp in tqdm(range(halfwid, totsamps - halfwid + 1)):
            winstart = int(smp - halfwid)
            winend = int(smp + halfwid)
            avgsmp = np.matrix.mean(data[winstart:winend + 1, :], 0)
            newdata[smp, :] = data[smp, :] - avgsmp

        # For the last few samples, it will always be the same
        avgsmp = np.matrix.mean(data[totsamps - halfwid:totsamps + 1, :], 0)
        newdata[totsamps - halfwid:totsamps + 1, :] = data[totsamps - halfwid:totsamps + 1, :] - avgsmp


    ax = plt.subplot(1, 2, 1)
    plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%dns'))
    plt.gca().xaxis.set_major_formatter(FormatStrFormatter('%dm'))

    scale = 4

    img = ax.imshow(data, cmap='gray', vmin=-1500, vmax=1500)  # ,extent=[0, data.shape[1] / scale, max(self.depth), 0])

    # ax.set_xticks(self.ticks_list)
    # ax.set_xticklabels(self.label_list, fontsize=8)
    # ax.tick_params(axis='y', labelsize=8)
    # ax.set_ylabel('Time', fontsize=10)

    ax = plt.subplot(1, 2, 2)
    plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%dns'))
    plt.gca().xaxis.set_major_formatter(FormatStrFormatter('%dm'))

    img = ax.imshow(newdata, cmap='gray', vmin=-1500,
                    vmax=1500)  # extent=[0, newdata_DC_shift.shape[1] / scale, max(self.depth), 0])
    # ax.set_xticks(self.ticks_list)
    # ax.set_xticklabels(self.label_list, fontsize=8)
    # ax.tick_params(axis='y', labelsize=8)
    # ax.set_ylabel('Time', fontsize=10)

    plt.show()

    return newdata

def timezero_adjust(trace_collection):
    data = np.load(trace_collection)

    maxlen = data.shape[0]
    newdata_timezero = np.asmatrix(np.zeros(data.shape))

    # Go through all traces to find maximum spike
    maxind = np.zeros(data.shape[1], dtype=int)

    for tr in range(0, data.shape[1]):
        maxind[tr] = int(np.argmax(data[:, tr]))

    # Find the mean spike point
    meanind = int(np.round(np.mean(maxind)))

    # Shift all traces. If max index is smaller than
    # mean index, then prepend zeros, otherwise append
    for tr in range(0, data.shape[1]):
        if meanind > maxind[tr]:
            differ = int(meanind - maxind[tr])
            newdata_timezero[:, tr] = np.reshape(np.concatenate([np.zeros((differ)), data[0:(maxlen - differ), tr]]),
                                                 (512, 1))
        elif meanind <= maxind[tr]:
            differ = maxind[tr] - meanind
            # newdata_aligned = np.append(newdata_aligned, np.concatenate([data[differ:maxlen, tr], np.zeros((differ))]), axis=1)
            newdata_timezero[:, tr] = np.reshape(np.concatenate([data[differ:maxlen, tr], np.zeros((differ))]),
                                                 (512, 1))

    x1 = data[:, 0]
    x2 = data[:, 1]
    x3 = data[:, 2]
    x4 = data[:, 3]
    x5 = data[:, 4]
    y = range(512, 0, -1)

    plt.subplot(1, 2, 1)
    plt.plot(x1, y)
    plt.plot(x2, y)
    plt.plot(x3, y)
    plt.plot(x4, y)
    plt.plot(x5, y)

    x1_timezero = newdata_timezero[:, 0]
    x2_timezero = newdata_timezero[:, 1]
    x3_timezero = newdata_timezero[:, 2]
    x4_timezero = newdata_timezero[:, 3]
    x5_timezero = newdata_timezero[:, 4]

    plt.subplot(1, 2, 2)
    plt.plot(x1_timezero, y)
    plt.plot(x2_timezero, y)
    plt.plot(x3_timezero, y)
    plt.plot(x4_timezero, y)
    plt.plot(x5_timezero, y)

    plt.show()

    np.save('trace_collection.npy', newdata_timezero)

def remMeanTrace(data, ntraces):
    data = np.asmatrix(data)
    tottraces = data.shape[1]
    # For ridiculous ntraces values, just remove the entire average
    if ntraces >= tottraces:
        newdata = data - np.matrix.mean(data, 1)
    else:
        newdata = np.asmatrix(np.zeros(data.shape))
        halfwid = int(np.ceil(ntraces / 2.0))

        # First few traces, that all have the same average
        avgtr = np.matrix.mean(data[:, 0:halfwid + 1], 1)
        newdata[:, 0:halfwid + 1] = data[:, 0:halfwid + 1] - avgtr

        # For each trace in the middle
        for tr in tqdm(range(halfwid, tottraces - halfwid + 1)):
            winstart = int(tr - halfwid)
            winend = int(tr + halfwid)
            avgtr = np.matrix.mean(data[:, winstart:winend + 1], 1)
            newdata[:, tr] = data[:, tr] - avgtr

        # Last few traces again have the same average
        avgtr = np.matrix.mean(data[:, tottraces - halfwid:tottraces + 1], 1)
        newdata[:, tottraces - halfwid:tottraces + 1] = data[:, tottraces - halfwid:tottraces + 1] - avgtr

    print('done with removing mean trace')
    return newdata

def remMeanTrace_arb(tracecollection):
    data = np.asmatrix(tracecollection)
    tottraces = data.shape[1]

    newdata = data - np.matrix.mean(data, 1)

    return newdata

def bin_by(x, y, nbins=30, bins=None):
    """
    calculates the mean, median, and several percentiles of input data
    Divide the x axis into sections and return groups of y based on its x value
    Input:
    x - position of a reflection hyperbola in a GPR dataset, equals to depth in ns
    y - signal velocity of the analysed reflection hyperbola

    Output:
    df - pandas dataframe containing the mean, median ect.
    """
    if bins is None:
        bins = np.linspace(min(x), max(x), nbins)

    bin_space = (bins[-1] - bins[0]) / (len(bins) - 1) / 2

    indices = np.digitize(x, bins + bin_space)

    output = []
    for i in range(0, len(bins)):
        output.append(y[indices == i])
    #
    # prepare a dataframe with cols: median; mean; 1up, 1dn, 2up, 2dn, 3up, 3dn
    df_names = ['mean', 'median', '5th', '95th', '10th', '90th', '25th', '75th']
    df = pd.DataFrame(columns=df_names)
    to_delete = []
    # for each bin, determine the std ranges
    for y_set in output:
        if y_set.size > 0:
            av = y_set.mean()
            intervals = np.percentile(y_set, q=[50, 5, 95, 10, 90, 25, 75])
            res = [av] + list(intervals)
            df = pd.concat([df, pd.DataFrame([res], columns=df_names)], ignore_index=True)
        else:
            # just in case there are no elements in the bin
            to_delete.append(len(df) + 1 + len(to_delete))

    # add x values
    bins = np.delete(bins, to_delete)
    df['x'] = bins

    return df



