import struct
import concurrent.futures
import numpy as np
import os
import rasterio
from rasterio.transform import from_origin

from cpp_fld_to_npy import fld_to_npy
from GUI.error_handling import confirm_python_processing

def define_fld_parameters_cpp(file_path, overwrite=False):
    base_name = os.path.splitext(file_path)[0]  # Get the path without the extension
    output_npy = base_name + '.npy'

    if not os.path.exists(output_npy) or overwrite:
        print('Using C++ version for processing.')
        fld_to_npy.process_fld_with_cpp(file_path, output_npy)
        print('FLD preprocessed.')
    else:
        print(f"File {output_npy} already exists. Skipping...")

    fld_data = np.load(output_npy, mmap_mode='r')

    with open(file_path, mode='rb') as f:
        file_content = f.read()

    xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, pixelsize_z = read_fld_header(file_content)
    data_start, data_type, pixelsize_z, depth_table, time_table, _ = read_fld_data_specs(file_content, zpixels)

    return fld_data, xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, pixelsize_z, data_type, depth_table, time_table


def get_expected_npy_size(x, y, z):
    x = np.int64(x)
    y = np.int64(y)
    z = np.int64(z)

    exp_size = ((x * y * z) * 4) + 128

    return exp_size

def define_fld_parameters(file_path, overwrite=False):
    base_name = os.path.splitext(file_path)[0]
    output_npy = base_name + '.npy'

    with open(file_path, mode='rb') as f:
        file_content = f.read()

    xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, pixelsize_z = read_fld_header(file_content)

    if not os.path.exists(output_npy):
        data_start, data_type, pixelsize_z, depth_table, time_table, _ = read_fld_data_specs(file_content, zpixels)
        start_bits, stop_bits, number_of_values = get_start_stop_bits(file_content, zpixels, data_start)

        read_fld_with_threads(file_content, xpixels, ypixels, zpixels, start_bits, stop_bits,
                                         number_of_values, output_npy)
    else:
        if overwrite:
            data_start, data_type, pixelsize_z, depth_table, time_table, _ = read_fld_data_specs(file_content, zpixels)
            start_bits, stop_bits, number_of_values = get_start_stop_bits(file_content, zpixels, data_start)

            read_fld_with_threads(file_content, xpixels, ypixels, zpixels, start_bits, stop_bits,
                                  number_of_values, output_npy)
        else:
            data_start, data_type, pixelsize_z, depth_table, time_table, _ = read_fld_data_specs(file_content, zpixels)
            print(f"File {output_npy} already exists. Skipping...")

    fld_data = np.load(output_npy, mmap_mode='r')

    return fld_data, xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, pixelsize_z, data_type, depth_table, time_table

def read_fld_size(file_path):
    with open(file_path, mode='rb') as f:
        file_content = f.read()

    xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, _ = read_fld_header(file_content)
    _, data_type, pixelsize_z, depth_table, time_table, z_vals = read_fld_data_specs(file_content, zpixels)

    return zpixels, pixelsize_z, x_coor, y_coor, pixelsize, depth_table, time_table, data_type, z_vals, xpixels, ypixels

def read_fld_header(file_content):
    header_data = np.frombuffer(file_content[:40], dtype=np.dtype('>i4, >i4, >i4, >i4, >i4, >i4, >i4, >i4, >i4, >i4'))
    _, xpixels, ypixels, zpixels, x_start, x_end, _, _, z_start, z_end = header_data[0]

    pixelsize = ((x_end-x_start) / xpixels) / 100
    pixelsize_z = ((z_end - z_start) / zpixels) / 100

    x_coor = np.frombuffer(file_content[198:206], dtype='>f8')[0]
    y_coor = np.frombuffer(file_content[214:222], dtype='>f8')[0]

    return xpixels, ypixels, zpixels, pixelsize, y_coor, x_coor, pixelsize_z

def read_fld_data_specs(file_content, z_size):
    start_b = 246
    start_num = start_b + z_size * 4 + 4
    stop_num = start_num + 4

    b = file_content[start_b - 48:start_b]
    c = np.frombuffer(b, dtype='>d')
    xstart, xend, ystart, yend, zstart, zend = c
    z_vals = [zstart, zend]

    data_type = np.frombuffer(file_content[start_num - 4:start_num], dtype=np.dtype('>i4'))[0]
    num_dt = np.frombuffer(file_content[start_num:stop_num], dtype=np.dtype('>i4'))[0]

    z_pixels = abs(np.frombuffer(file_content[stop_num+4:stop_num+8], dtype='>f4')[0])

    # Calculate the start and stop indices for the depth table
    depth_table_start = stop_num
    depth_table_stop = depth_table_start + num_dt * 8  # Each entry is 8 bytes



    # Extract the depth table
    depth_table = np.frombuffer(file_content[depth_table_start:depth_table_stop], dtype='>f4').reshape(-1, 2)

    time_table_start = depth_table_stop
    time_table_stop = time_table_start + num_dt * 8

    time_table = np.frombuffer(file_content[time_table_start:time_table_stop], dtype='>f4').reshape(-1, 2)

    start_num_velo = time_table_stop
    stop_num_velo = start_num_velo + 4

    num_velo = np.frombuffer(file_content[start_num_velo:stop_num_velo], dtype=np.dtype('>i4'))[0]

    data_start = stop_num_velo + num_velo * 2 * 4 + 4

    return data_start, data_type, z_pixels, depth_table, time_table, z_vals
def get_start_stop_bits(file_content, number_of_layers, data_start):
    start_bits = []
    stop_bits = []
    number_of_values = []

    for layer_index in range(number_of_layers):
        # Determine the size of the layer
        number_of_values_layer = struct.unpack('q', file_content[data_start:data_start + 8])[0]
        number_of_values.append(number_of_values_layer)

        # Determine the end position of the layer data
        data_stop = np.int64(data_start + 16 + number_of_values_layer * 2)

        start_bits.append(data_start)
        stop_bits.append(data_stop)

        # Update the start position for the next layer
        data_start = data_stop

    return start_bits, stop_bits, number_of_values

def process_layer(layer_index, file_content, x_size, y_size, start_bits, stop_bits, number_of_values):
    data_start = start_bits[layer_index]
    data_stop = stop_bits[layer_index]

    min1, max1 = struct.unpack('>f', file_content[data_start + 8:data_start + 12])[0], \
        struct.unpack('>f', file_content[data_start + 12:data_start + 16])[0]

    data_values = np.frombuffer(file_content[data_start + 16:data_stop], dtype='>i2')
    data_values = np.where(data_values > 0, min1 + (data_values - 1) * ((max1 - min1) / 32760), data_values)
    data_unpacked = []

    for value in data_values:
        if value < 0 and value.is_integer():
            data_unpacked.extend([0] * int(abs(value)))
        else:
            data_unpacked.append(value)
    data_unpacked = np.asarray(data_unpacked, dtype=float)

    data_unpacked = data_unpacked.reshape(y_size, x_size)

    return layer_index, data_unpacked

def read_fld_with_threads(file_content, x_size, y_size, number_of_layers, start_bits, stop_bits, number_of_values, output_npy):
    data = np.empty((number_of_layers, y_size, x_size), dtype=np.float32)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_layer, layer_index, file_content, x_size, y_size, start_bits, stop_bits, number_of_values) for layer_index in range(number_of_layers)]

        for future in concurrent.futures.as_completed(futures):
            layer_index, data_unpacked = future.result()
            data[layer_index, :, :] = data_unpacked

    data = data.transpose((0, 1, 2))
    data = np.flip(data, axis=1)

    np.save(output_npy, data)

    return data

def create_depthslice_images(vmin, vmax, npy_file_path, zpixels, pixelsize_z, pixelsize_x, x_coor, y_coor, depth_table, time_table, data_type, z_vals):
    pixelsize_z = round(pixelsize_z * 100)

    radar_data = np.load(npy_file_path)
    npy_base_name = os.path.splitext(os.path.basename(npy_file_path))[0]
    working_directory = os.path.dirname(npy_file_path)

    base_images_directory = os.path.join(working_directory, npy_base_name)
    if data_type == 2:
        images_directory = os.path.join(base_images_directory, f"01cm")
    else:
        images_directory = os.path.join(base_images_directory, f"{pixelsize_z:02d}cm")
    images_directory = images_directory.replace('\\', '/')
    os.makedirs(images_directory, exist_ok=True)

    if 'DTMfromGPR' in npy_base_name:
        z_start, z_end = z_vals  # Get overall max and min heights from z_vals
        z_start_cm = int(z_end * 100)  # Convert meters to centimeters

        for depth in range(zpixels):
            depth_slice = radar_data[depth, :, :]
            # Rescale the data to the desired grayscale range
            depth_slice = np.clip(depth_slice, vmin, vmax)
            depth_slice = (depth_slice - vmin) / (vmax - vmin) * 255  # Rescale to 0-255 for grayscale
            depth_slice = 255 - depth_slice  # Invert the grayscale

            z_stop_cm = int((z_start_cm - pixelsize_z))  # Calculate stop value in centimeters

            # Format values, add 'm' for negative values
            z_start_str = f"m{-z_start_cm:03d}" if z_start_cm < 0 else f"{z_start_cm:03d}"
            z_stop_str = f"m{-z_stop_cm:03d}" if z_stop_cm < 0 else f"{z_stop_cm:03d}"

            image_name = f"{npy_base_name}_{z_start_str}-{z_stop_str}.tif"
            image_path = os.path.join(images_directory, image_name)

            # Update z_start_cm for next iteration
            z_start_cm = z_stop_cm

            image_path = os.path.join(images_directory, image_name)

            adjusted_x_coor = x_coor + depth_slice.shape[0] * pixelsize_x
            nodata_value = 255

            # Define the raster's transformation and CRS
            transform = from_origin(y_coor, adjusted_x_coor, pixelsize_x, pixelsize_x)

            # Write the data to a GeoTIFF file
            with rasterio.open(
                    image_path,
                    'w',
                    driver='GTiff',
                    height=depth_slice.shape[0],
                    width=depth_slice.shape[1],
                    count=1,
                    compress='lzw',
                    dtype=depth_slice.dtype,
                    nodata=nodata_value,
                    transform=transform
            ) as dst:
                dst.write(depth_slice, 1)

    else:
        for depth in range(zpixels):
            depth_slice = radar_data[depth, :, :]

            # Rescale the data to the desired grayscale range
            depth_slice = np.clip(depth_slice, vmin, vmax)
            depth_slice = (depth_slice - vmin) / (vmax - vmin) * 255  # Rescale to 0-255 for grayscale
            depth_slice = 255 - depth_slice  # Invert the grayscale

            if data_type == 2:
                depth_info = depth_table[depth]
                time_info = time_table[depth]
                depth_start = depth_info[0]
                time_start = time_info[0]

                # Format the filename with time_start and depth_start
                # Formatting to ensure the required number of digits before and after the decimal point
                if time_start < 10:
                    time_str = f"0{time_start:.3f}ns"
                else:
                    time_str = f"{time_start:.3f}ns"
                depth_str = f"{depth_start:.3f}" + "m"
                image_name = f"{npy_base_name}_{time_str}_{depth_str}.tif"
            else:
                depth_start = depth * pixelsize_z
                depth_end = (depth + 1) * pixelsize_z
                image_name = f"{npy_base_name}_{depth_start:03d}-{depth_end:03d}.tif"

            image_path = os.path.join(images_directory, image_name)

            adjusted_x_coor = x_coor + depth_slice.shape[0] * pixelsize_x
            nodata_value = 255

            # Define the raster's transformation and CRS
            transform = from_origin(y_coor, adjusted_x_coor, pixelsize_x, pixelsize_x)

            # Write the data to a GeoTIFF file
            with rasterio.open(
                image_path,
                'w',
                driver='GTiff',
                height=depth_slice.shape[0],
                width=depth_slice.shape[1],
                count=1,
                compress = 'lzw',
                dtype=depth_slice.dtype,
                nodata=nodata_value,
                transform=transform
                ) as dst:
                dst.write(depth_slice, 1)

    return images_directory
