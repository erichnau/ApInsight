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

def _read_reflex_layout(file_name):
    """Read the two ReflexW/ApRadar binary layouts supported by ApInsight.

    Offsets are in bytes, little endian. The older layout uses int16 counts
    and float32 metadata; the newer export uses int32 counts and float64
    metadata. DAT records consist of a trace header followed by samples.
    """
    filename = str(file_name) + '.par'
    with open(filename, 'rb') as header_file:
        header = header_file.read()
    if len(header) < 524:
        raise ValueError(f"{filename}: PAR header is too short ({len(header)} bytes).")

    # In the old layout the trace count immediately follows the int16 sample
    # count. In the new layout these two bytes are the high half of int32
    # samples (zero for ordinary radar traces).
    legacy_samples, legacy_traces = struct.unpack_from('<hh', header, 420)
    if legacy_samples > 0 and legacy_traces > 0:
        nr_sample, nr_traces = legacy_samples, legacy_traces
        trace_increment, time_increment = struct.unpack_from('<ff', header, 460)
        antenna_separation = struct.unpack_from('<f', header, 520)[0]
        trace_header_bytes, sample_dtype = 62, np.dtype('<i2')
    else:
        if len(header) < 620:
            raise ValueError(f"{filename}: invalid legacy counts or incomplete new PAR header.")
        nr_sample, nr_traces = struct.unpack_from('<ii', header, 420)
        trace_increment, time_increment = struct.unpack_from('<dd', header, 492)
        antenna_separation = struct.unpack_from('<d', header, 612)[0]
        trace_header_bytes, sample_dtype = 158, np.dtype('<f4')

    if nr_sample <= 0 or nr_traces <= 0:
        raise ValueError(f"{filename}: invalid sample/trace counts ({nr_sample}, {nr_traces}).")
    if not np.isfinite(time_increment) or time_increment <= 0:
        raise ValueError(f"{filename}: invalid time increment {time_increment}.")
    if not np.isfinite(trace_increment) or not np.isfinite(antenna_separation):
        raise ValueError(f"{filename}: non-finite trace increment or antenna separation.")

    # Keep the existing public tuple order and antenna-separation rounding.
    info = (trace_increment, time_increment, nr_traces, nr_sample,
            round(antenna_separation, 2))
    return info, trace_header_bytes, sample_dtype


def read_par(file_name):
    """Read ReflexW/ApRadar PAR metadata; file_name excludes the extension.

    Returns (trace_increment, time_increment, nr_traces, nr_sample,
    antenna_separation), as in earlier versions of ApInsight.
    """
    return _read_reflex_layout(file_name)[0]


def read_dat(file_name):
    """Read legacy int16 or newer float32 ReflexW/ApRadar DAT records.

    Returns a matrix with samples in rows and traces in columns. The POS
    sidecar is optional and is not needed to decode amplitudes or PAR metadata.
    """
    info, trace_header_bytes, sample_dtype = _read_reflex_layout(file_name)
    _, _, nr_traces, nr_sample, _ = info
    filename = str(file_name) + '.dat'
    record_bytes = trace_header_bytes + nr_sample * sample_dtype.itemsize
    expected_bytes = nr_traces * record_bytes

    with open(filename, 'rb') as data_file:
        actual_bytes = data_file.seek(0, 2)
        if actual_bytes != expected_bytes:
            raise ValueError(
                f"{filename}: DAT size {actual_bytes} bytes does not match PAR "
                f"dimensions ({nr_traces} traces x {nr_sample} samples; "
                f"expected {expected_bytes} bytes, {sample_dtype.name} samples, "
                f"{trace_header_bytes}-byte trace headers). "
                "The file may be incomplete, mismatched, or an unsupported export layout."
            )
        data_file.seek(0)
        record_dtype = np.dtype([
            ('header', 'V' + str(trace_header_bytes)),
            ('samples', sample_dtype, (nr_sample,)),
        ])
        records = np.fromfile(data_file, dtype=record_dtype, count=nr_traces)
    if len(records) != nr_traces:
        raise ValueError(f"{filename}: DAT file ended before all traces were read.")
    data = records['samples'].copy()
    if sample_dtype.kind == 'i':
        # Preserve the legacy reader's amplitude clipping. Float32 exports
        # retain their original amplitudes and fractional precision.
        np.clip(data, -32767, 32766, out=data)
    return np.asmatrix(data.T)
