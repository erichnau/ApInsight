import struct
import numpy as np


class ApPPDReader:

    def __init__(self, filename):
        self.filename = filename
        self.traces = []

    def read(self):

        with open(self.filename, "rb") as f:

            # ---- FILE IDENTIFIER ----

            file_identifier = f.read(32).decode("ascii").strip()
            file_number = struct.unpack("<i", f.read(4))[0]
            version = struct.unpack("<h", f.read(2))[0]

            # ---- GENERAL HEADER ----

            data_format = struct.unpack("<h", f.read(2))[0]
            date = struct.unpack("<i", f.read(4))[0]
            num_channels = struct.unpack("<h", f.read(2))[0]
            num_traces = struct.unpack("<i", f.read(4))[0]
            num_points = struct.unpack("<h", f.read(2))[0]
            data_saved_as_short = struct.unpack("<h", f.read(2))[0]
            antenna_freq = struct.unpack("<h", f.read(2))[0]
            antenna_sep = struct.unpack("<h", f.read(2))[0]
            time_window = struct.unpack("<f", f.read(4))[0]

            section_length = struct.unpack("<i", f.read(4))[0]
            epsg = struct.unpack("<i", f.read(4))[0]

            multichannel = struct.unpack("<h", f.read(2))[0]
            time_triggered = struct.unpack("<h", f.read(2))[0]

            trace_distance = struct.unpack("<h", f.read(2))[0]
            trace_time_interval = struct.unpack("<h", f.read(2))[0]

            time_zero_adjusted = struct.unpack("<h", f.read(2))[0]

            x_min = struct.unpack("<d", f.read(8))[0]
            x_max = struct.unpack("<d", f.read(8))[0]
            y_min = struct.unpack("<d", f.read(8))[0]
            y_max = struct.unpack("<d", f.read(8))[0]
            z_min = struct.unpack("<d", f.read(8))[0]
            z_max = struct.unpack("<d", f.read(8))[0]

            f.read(32)  # reserved

            header = {
                "channels": num_channels,
                "points_per_trace": num_points,
                "time_window": time_window,
                "epsg": epsg,
                "data_format_short": data_saved_as_short,
                "x_min": x_min,
                "y_min": y_min,
                "z_min": z_min,
                "trace_distance": trace_distance,
                "antenna_sep": antenna_sep,
                "time_zero_adjusted": time_zero_adjusted
            }

            print("Header:", header)

            # ---- GLOBAL TRACE COUNTER ----
            gid = 0

            # ---- CHANNELS ----

            for ch in range(num_channels):

                channel_number = struct.unpack("<h", f.read(2))[0]
                traces_in_channel = struct.unpack("<i", f.read(4))[0]
                length = struct.unpack("<i", f.read(4))[0]

                time_zero = struct.unpack("<h", f.read(2))[0]
                first_zero = struct.unpack("<h", f.read(2))[0]
                second_zero = struct.unpack("<h", f.read(2))[0]

                section_incorrect = struct.unpack("<h", f.read(2))[0]

                f.read(32)  # reserved

                print(f"Channel {channel_number}, traces:", traces_in_channel)

                # ---- TRACES ----

                for tr in range(traces_in_channel):

                    trace_start = f.tell()

                    velocity = struct.unpack("<h", f.read(2))[0]
                    gps_flags = struct.unpack("<h", f.read(2))[0]

                    x = struct.unpack("<f", f.read(4))[0]
                    y = struct.unpack("<f", f.read(4))[0]
                    z = struct.unpack("<f", f.read(4))[0]

                    # convert relative → absolute
                    x_abs = x + x_min
                    y_abs = y + y_min
                    z_abs = z

                    data_offset = f.tell()

                    if data_saved_as_short == 1:
                        f.seek(4 + num_points * 2, 1)
                    else:
                        f.seek(num_points * 4, 1)

                    self.traces.append({
                        "gid": gid,
                        "channel": channel_number,
                        "trace": tr,
                        "x": x_abs,
                        "y": y_abs,
                        "z": z_abs,
                        "data_offset": data_offset,
                        "time_zero": time_zero,
                        "first_zero": first_zero,
                        "second_zero": second_zero,
                        "section_incorrect": section_incorrect,
                        "time_zero_adjusted": time_zero_adjusted,
                        "gps_flags": gps_flags & 0xFFFF
                    })

                    gid += 1

        print("Total traces:", len(self.traces))

        return header, self.traces

    def read_trace_samples(self, trace, header):
        num_points = int(header["points_per_trace"])

        with open(self.filename, "rb") as f:
            # Keep data_offset pointing to the start of the trace-data
            # block: the conversion factor for short-format records.
            f.seek(int(trace["data_offset"]))

            if header["data_format_short"] == 1:
                factor_bytes = f.read(4)

                if len(factor_bytes) != 4:
                    raise ValueError("Incomplete trace conversion factor.")

                factor = struct.unpack("<f", factor_bytes)[0]

                if not np.isfinite(factor):
                    raise ValueError("Non-finite trace conversion factor.")

                samples = np.fromfile(
                    f, dtype="<i2", count=num_points
                )

                if len(samples) != num_points:
                    raise ValueError("Incomplete short-format trace.")

                return samples.astype(np.float32) * factor

            elif header["data_format_short"] == 0:
                samples = np.fromfile(
                    f, dtype="<f4", count=num_points
                )

                if len(samples) != num_points:
                    raise ValueError("Incomplete float-format trace.")

                return samples

            else:
                raise ValueError("Unknown ApPPD sample storage format.")

    def build_radargram(self, header, channel=None):

        traces = [t for t in self.traces if t["channel"] == channel]

        num_points = header["points_per_trace"]
        num_traces = len(traces)

        data = np.zeros((num_points, num_traces), dtype=np.float32)

        for i, t in enumerate(traces):
            samples = self.read_trace_samples(t, header)
            data[:, i] = samples

        return data, traces
