import re
import struct

import numpy as np

def readMALA(file_name):
    """
    Reads the MALA .rd3 data file and the .rad header. Can also be used
    to read .rd7 files but I'm not sure if they are really organized
    the same way.
    INPUT:
    file_name     data file name without the extension!
    OUTPUT:
    data          data matrix whose columns contain the traces
    info          dict with information from the header
    """
    # First read header
    info = readGPRhdr(file_name + '.rad')
    try:
        filename = file_name + '.rd3'
        data = np.fromfile(filename, dtype=np.int16)
    except:
        # I'm not sure what the format of rd7 is. Just assuming it's the same
        filename = file_name + '.rd7'
        data = np.fromfile(filename, dtype=np.int32)

    nrows = int(len(data) / int(info['SAMPLES']))

    data = (np.asmatrix(data.reshape(nrows, int(info['SAMPLES'])))).transpose()

    print(data, info)

    return data, info

def readGPRhdr(filename):
    """
    Reads the MALA header
    INPUT:
    filename      file name for header with .rad extension

    OUTPUT:
    info          dict with information from the header
    """
    # Read in text file
    info = {}
    with open(filename) as f:
        for line in f:
            strsp = line.split(':')
            info[strsp[0]] = strsp[1].rstrip()
    return info

def readdt1(filename):
    """
    Reads the Sensors&Software .dt1 data file and the .HD header.
    INPUT:
    file_name     data file name
    OUTPUT:
    data          data matrix whose columns contain the traces
    """

    headlen = 32
    with open(filename, "rb") as datafile:
        datafile.seek(8, 0)  # 0 is beginning of file
        samples, = struct.unpack('f', datafile.read(4))
        samples = int(samples)
        dimtrace = samples * 2 + 128
        datafile.seek(-dimtrace, 2)  # 2 stands for end of file
        # print(datafile.tell())
        max_traces, = struct.unpack('f', datafile.read(4))
        max_traces = int(max_traces)
        # Initialize matrix
        data_temp = np.zeros((samples, max_traces))
        head = np.zeros((headlen, max_traces))
        # Set the reader to the beginning of the file
        datafile.seek(0, 0)
        for j in range(0, max_traces):
            for k in range(0, headlen):
                info, = struct.unpack('f', datafile.read(4))
                head[k, j] = info
                # Now the actual data
            for k in range(0, samples):
                # 2 is the size of short, 'h' is the symbol
                pnt, = struct.unpack('h', datafile.read(2))
                data_temp[k, j] = pnt
            datafile.seek(dimtrace * (j + 1), 0)
        data = np.asmatrix(data_temp)

    return data

def readdt1Header(filename):
    """
    Reads the Sensors&Software GPR header
    INPUT:
    filename      file name for header with .HD extension

    OUTPUT:
    info          dict with information from the header
    """
    info = {}
    with open(filename, "r", newline='\n') as datafile:
        datafile.readline().strip()
        info["system"] = datafile.readline().strip()
        info["date"] = datafile.readline().strip()
        string = datafile.readline().strip()
        var = re.match(r'NUMBER OF TRACES   = (.*)', string)
        info["N_traces"] = int(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'NUMBER OF PTS/TRC  = (.*)', string)
        info["N_pts_per_trace"] = int(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'TIMEZERO AT POINT  = (.*)', string)
        info["TZ_at_pt"] = float(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'TOTAL TIME WINDOW  = (.*)', string)
        info["Total_time_window"] = float(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'STARTING POSITION  = (.*)', string)
        info["Start_pos"] = float(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'FINAL POSITION     = (.*)', string)
        info["Final_pos"] = float(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'STEP SIZE USED     = (.*)', string)
        info["Step_size"] = float(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'POSITION UNITS     = (.*)', string)
        info["Pos_units"] = str(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'NOMINAL FREQUENCY  = (.*)', string)
        info["Freq"] = float(var.group(1))
        string = datafile.readline().strip()
        var = re.match(r'ANTENNA SEPARATION = (.*)', string)
        info["Antenna_sep"] = float(var.group(1))
        # If you need more of the header info, you can just continue as above
        # Transform feet to meters
        if info['Pos_units'] == 'ft':
            info["Start_pos"] = info["Start_pos"] * 0.3048
            info["Final_pos"] = info["Final_pos"] * 0.3048
            info["Step_size"] = info["Step_size"] * 0.3048
            info["Antenna_sep"] = info["Antenna_sep"] * 0.3048
            info['Pos_units'] = 'm'

    sampling_frequency = info["N_pts_per_trace"] / info["Total_time_window"] * 1000
    timewindow = info["Total_time_window"]
    number_of_samples = info["N_pts_per_trace"]
    nr_traces = info["N_traces"]

    return sampling_frequency, timewindow, number_of_samples, nr_traces

def read_par(file_name):
    """
    Reads the ReflexW par file (header information)
    INPUT:
    filename      file name for header with .rad extension

    OUTPUT:
    info          dict with information from the header
    """
    filename = file_name + '.par'
    '____________________________________________________________'
    data1 = np.fromfile(filename, dtype=np.float32)
    value_list = []
    data2 = data1.tolist()
    for i in data2:
        value_list.append(f'{round(i, 7):.8f}')

    time_increment = value_list[116]
    trace_increment = value_list[115]
    antenna_separation = round(float(value_list[130]), 2)
    '_______________________________________________________'

    data3 = np.fromfile(filename, dtype=np.int16)
    list2 = []
    data4 = data3.tolist()
    for i in data4:
        list2.append(i)


    nr_sample = list2[210]
    nr_traces = list2[211]

    info = trace_increment, time_increment, nr_traces, nr_sample, antenna_separation

    return info

def read_dat(file_name):
    """
    Reads the ReflexW data file .dat and the .par header.
    INPUT:
    file_name     data file name without the extension!
    OUTPUT:
    data          data matrix whose columns contain the traces
    """
    trace_increment, time_increment, nr_traces, nr_sample, antenna_separation = read_par(file_name)

    filename = file_name + '.dat'
    gpr_data = np.fromfile(filename, dtype=np.int16)

    delete_list = []
    x = 0
    for i in range(nr_traces):
        x = i * (nr_sample + 31)
        delete_list.append(x)

    delete_list_final = []

    for element in delete_list:
        for i in range(31):
            x = element + i
            delete_list_final.append(x)

    data_ex = np.delete(gpr_data, delete_list_final)

    data = np.asmatrix(data_ex.reshape(nr_traces, nr_sample)).T


    return data