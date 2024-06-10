import os
from tkinter import BooleanVar
import rasterio
import xarray as xr
import numpy as np
from scipy.ndimage import gaussian_filter
import matplotlib.pyplot as plt

from data.data_structure import load_json
from GPR_func import read_fld
from config_manager import ConfigurationManager

from GPR_func._2D_vertical import filter_nan_and_zero_rows
from GUI._3DViewer import _3DViewer


class ProjectData:
    def __init__(self, frame_right):
        self.projects = []  # List to store individual Project objects
        self.frame_right = frame_right

    def load_project_from_json(self, json_file):
        data = load_json(json_file)

        # Extract project data
        project_data = data.get("projects", {})
        self.sections_data = data.get("sections", {})

        # Clear existing projects and load new ones from project_data
        self.projects.clear()
        for project_key, project_info in project_data.items():
            project = Project(project_info)
            self.projects.append(project)

        # Return only the project data
        return project_data

    def load_sections(self):
        last_select_name = None
        if self.sections_data:
            self.frame_right.sections.clear()
            self.frame_right.clear_all_sections()

            for section_name, section_info in self.sections_data.items():
                start_coords = tuple(section_info['start'])
                end_coords = tuple(section_info['end'])
                select = section_info['select']
                self.frame_right.add_section(start_coords, end_coords, section_name, from_json=True, select=select)
                if select:
                    last_select_name = section_name
            if last_select_name:
                self.frame_right.focus_section(last_select_name)

    def clear_project(self):
        self.projects = []

    def update_frame_right(self, frame_right):
        self.frame_right = frame_right

class Project:
    def __init__(self, project_data):
        self.config_manager = ConfigurationManager('config.ini')
        self.use_compiled_exe = self.config_manager.get_boolean_option('Application', 'use_compiled_exe')

        self.ap_prj_file = project_data.get('ap_prj_file')
        self.fld_file = self._create_fld_data(project_data.get('fld_file'))
        self.DTM_files = {}
        dtm_file_data = project_data.get('DTM_file')

        if dtm_file_data and dtm_file_data != 'None':
            if isinstance(dtm_file_data, list):
                for DTM_file_path in dtm_file_data:
                    dtm_data = DTMData(DTM_file_path)
                    self.DTM_files[dtm_data.file_name] = dtm_data
            elif isinstance(dtm_file_data, str):
                dtm_data = DTMData(dtm_file_data)
                self.DTM_files[dtm_data.file_name] = dtm_data

        self.npy_file = project_data.get('npy_file')
        self.depthslice_folder = project_data.get('depthslice_folder')

    def _create_fld_data(self, fld_file_path):
        if fld_file_path:
            return FldData(fld_file_path, self.use_compiled_exe)
        return None

    def _create_dtm_data(self, dtm_file_path):
        if dtm_file_path:
            return DTMData(dtm_file_path)
        return None


class DTMData:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file_name = self.extract_file_name(file_path)
        self.dtm_data = None
        self.transform = None
        self.resolution = None

        self.load_DTM_file()

    def extract_file_name(self, file_path):
        return os.path.splitext(os.path.basename(file_path))[0]

    def load_DTM_file(self):
        with rasterio.open(self.file_path) as dataset:
            self.dtm_data = dataset.read(1)
            pixel_width = abs(dataset.transform[0])
            pixel_height = abs(dataset.transform[4])
            self.resolution = (pixel_width + pixel_height) / 2.0

            self.transform = dataset.transform

    def create_height_profile(self, coordinates, samples):
        height_profile = self.extract_height_profile(coordinates)
        resampled_height_profile = self.resample_height_profile(height_profile, samples)
        smoothed_height_profile = self.smooth_height_profile(resampled_height_profile)

        return smoothed_height_profile

    def extract_height_profile(self, coordinates):
        start_coordinates = coordinates[0]
        stop_coordinates = coordinates[1]

        # Calculate the number of points based on the sampling interval
        num_points = int(
            np.ceil(np.linalg.norm(np.array(stop_coordinates) - np.array(start_coordinates)) / self.resolution)) + 1

        # Increase the number of points for lower resolution DTMs
        if self.resolution > 0.5:  # Threshold of 50 cm
            num_points *= int(self.resolution / 0.1)  # Scale up points based on resolution

        # Generate the step size for the distance array
        step = np.linalg.norm(np.array(stop_coordinates) - np.array(start_coordinates)) / (num_points - 1)

        # Generate the distance array
        distance = np.arange(0, num_points * step, step)

        # Generate the global x and y coordinates for each point along the distance array
        global_x = np.interp(distance, [0, num_points * step], [start_coordinates[0], stop_coordinates[0]])
        global_y = np.interp(distance, [0, num_points * step], [start_coordinates[1], stop_coordinates[1]])

        # Convert global coordinates to local pixel coordinates
        indices = rasterio.transform.rowcol(self.transform, global_x, global_y)

        # Extract the row and column indices
        indices_row = indices[0]
        indices_col = indices[1]

        # Get the elevations from the DTM data array
        elevations = self.dtm_data[indices_row, indices_col]

        # Filter out zero values from the elevations
        valid_elevations = elevations[elevations != 0]

        return valid_elevations

    def resample_height_profile(self, height_profile, num_samples):
        # Calculate the original number of points
        original_num_points = len(height_profile)

        # Calculate the resampling factor
        resampling_factor = original_num_points / num_samples

        # Resample the height profile
        resampled_profile = np.interp(
            np.arange(0, original_num_points, resampling_factor),
            np.arange(0, original_num_points),
            height_profile
        )

        return resampled_profile

    def smooth_height_profile(self, height_profile):
        # Adjust sigma based on the resolution
        if self.resolution > 0.5:  # Threshold of 50 cm
            sigma = 10 * (self.resolution / 0.1)
        else:
            sigma = 10

        smoothed_profile = gaussian_filter(height_profile, sigma)

        return smoothed_profile

class FldData:
    def __init__(self, file_path, use_compiled_exe):
        self.file_path = file_path
        self.file_name = self.extract_file_name(file_path)
        self.use_compiled_exe = use_compiled_exe

        self.fld_dset = None
        self.xpixels = None
        self.ypixels = None
        self.zpixels = None
        self.pixelsize = None
        self.x_coor = None
        self.y_coor = None
        self.pixelsize_z = None
        self.data_type = None
        self.depth_table = None
        self.time_table = None

        self.selected = BooleanVar()
        self.image_folder = self.get_image_folder()
        self.load_fld_file()

    def load_fld_file(self):
        if self.use_compiled_exe:
            fld_dset, self.xpixels, self.ypixels, self.zpixels, self.pixelsize, self.y_coor, self.x_coor, self.pixelsize_z, self.data_type, self.depth_table, self.time_table = read_fld.define_fld_parameters_cpp(
                self.file_path)
        else:
            fld_dset, self.xpixels, self.ypixels, self.zpixels, self.pixelsize, self.y_coor, self.x_coor, self.pixelsize_z, self.data_type, self.depth_table, self.time_table = read_fld.define_fld_parameters(
                self.file_path)

        x_coords = np.linspace(self.x_coor, self.x_coor + self.pixelsize * (fld_dset.shape[2] - 1),
                               fld_dset.shape[2])
        y_coords = np.linspace(self.y_coor + self.ypixels * self.pixelsize, self.y_coor, fld_dset.shape[1])
        num_z_values = fld_dset.shape[0]

        z_coords = np.linspace(0, -self.pixelsize_z * (num_z_values - 1), num=num_z_values)

        self.fld_dset = xr.DataArray(fld_dset, coords={"x": x_coords, "y": y_coords, "z": z_coords},
                                  dims=("z", "y", "x"))

        if 'DTMfromGPR' in self.file_name:
            layers_to_keep = ~np.all(np.isnan(fld_dset) | (fld_dset == 0), axis=(1,2))
            top_removed = np.argmax(layers_to_keep)
            self.bottom_zeros = fld_dset.shape[0] - (len(layers_to_keep) - np.argmax(layers_to_keep[::-1])) - top_removed


    def extract_file_name(self, file_path):
        return os.path.basename(file_path)

    def get_image_folder(self):
        folder_path = os.path.dirname(self.file_path)
        file_name = os.path.splitext(os.path.basename(self.file_path))[0]
        image_folder = os.path.join(folder_path, f"NetCDF_img_{file_name}")
        return image_folder

    def create_arbitrary_section(self, start_x, start_y, stop_x, stop_y):
        dist = np.sqrt(((start_x - stop_x) ** 2) + ((start_y - stop_y) ** 2))
        if self.data_type == 2:
            self.pixelsize_z = 0.01
        n = round(dist / self.pixelsize_z)

        course = np.column_stack((np.linspace(start_x, stop_x, n), np.linspace(start_y, stop_y, n)))

        section = self.fld_dset.interp(x=('along_course', course[:, 0]), y=('along_course', course[:, 1]), method='linear')
        section_data = np.array(section)

        valid_section_data = filter_nan_and_zero_rows(section_data)

        if 'DTMfromGPR' in self.file_name:
            # Identify rows to keep (non-zero and non-nan)
            rows_to_keep = ~np.all(np.isnan(section_data) | (section_data == 0), axis=1)
            rows_kept_count = np.sum(rows_to_keep)

            top_removed = np.argmax(rows_to_keep)
            bottom_removed = section_data.shape[0] - (len(rows_to_keep) - np.argmax(rows_to_keep[::-1])) - top_removed - self.bottom_zeros
        else:
            top_removed = None
            bottom_removed = None

        if 'DTMfromGPR' in self.file_name:
            depth_m = self.pixelsize_z * valid_section_data.shape[0]
        else:
            depth_m = self.depth_table[valid_section_data.shape[0]-1][0] + self.depth_table[valid_section_data.shape[0]-1][1]

        return dist, valid_section_data, depth_m, self.pixelsize_z, self.data_type, top_removed, bottom_removed, self.depth_table

    def create_3d_subset(self, coordinates):
        # Retrieve the corner points of the rectangle from self.rectangle_data
        start_coords = coordinates["start_coords"]
        perp_start_coords = coordinates["perp_start_coords"]
        perp_stop_coords = coordinates["perp_stop_coords"]
        stop_coords = coordinates["stop_coords"]

        # Convert coordinates to pixel indices or array indices depending on your data structure
        # Determine the bounding box of the rectangle
        min_x = min(start_coords[0], perp_start_coords[0], perp_stop_coords[0], stop_coords[0])
        max_x = max(start_coords[0], perp_start_coords[0], perp_stop_coords[0], stop_coords[0])
        min_y = min(start_coords[1], perp_start_coords[1], perp_stop_coords[1], stop_coords[1])
        max_y = max(start_coords[1], perp_start_coords[1], perp_stop_coords[1], stop_coords[1])

        # Convert spatial coordinates to pixel indices
        min_x_index = int((min_x - self.x_coor) / self.pixelsize)
        max_x_index = int((max_x - self.x_coor) / self.pixelsize)
        max_y_index = int(((self.y_coor + self.ypixels*self.pixelsize) - min_y) / self.pixelsize)
        min_y_index = int(((self.y_coor + self.ypixels*self.pixelsize) - max_y) / self.pixelsize)

        # Slice the dataset
        subset_data = self.fld_dset[:, min_y_index:max_y_index + 1, min_x_index:max_x_index + 1]
        print(self.fld_dset.coords['x'].values, self.fld_dset.coords['y'].values)
        subset_clean = self.clean_subset(subset=subset_data, coordinates=coordinates, x_coords=subset_data.coords['x'].values, y_coords=subset_data.coords['y'].values)

        return subset_clean

    def is_point_in_rectangle(self, point, vertices):
        """Check if a point is inside the rectangle using the ray-casting algorithm."""
        x, y = point
        n = len(vertices)
        inside = False

        p1x, p1y = vertices[0]
        for i in range(n + 1):
            p2x, p2y = vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def clean_subset(self, subset, coordinates, x_coords, y_coords, nan_value=np.nan):
        """Set values outside the arbitrary rectangle to NaNs."""
        start_coords = coordinates["start_coords"]
        perp_start_coords = coordinates["perp_start_coords"]
        perp_stop_coords = coordinates["perp_stop_coords"]
        stop_coords = coordinates["stop_coords"]

        # Define the rectangle vertices
        vertices = [start_coords, perp_start_coords, perp_stop_coords, stop_coords]

        # Make a writable copy of the subset
        subset_copy = subset.copy()

        # Iterate over the subset and set values outside the rectangle to nan_value
        for i in range(subset_copy.shape[1]):  # y dimension
            for j in range(subset_copy.shape[2]):  # x dimension
                if not self.is_point_in_rectangle((x_coords[j], y_coords[i]), vertices):
                    subset_copy[:, i, j] = nan_value

        return subset_copy

    def calc_index_from_coor(self, x, y):
        # Calculate the indices as before
        x_index = np.round((x - self.x_coor) / self.pixelsize).astype(int)
        y_index = np.round(((self.y_coor+ (self.ypixels*self.pixelsize))-y) / self.pixelsize).astype(int)

        return x_index, y_index

    def moving_average(self, data, window_size):
        # Create a convolution kernel for the moving average
        kernel = np.ones(window_size) / window_size

        # Apply the moving average filter along the horizontal axis (axis 1)
        smoothed_data = np.apply_along_axis(lambda x: np.convolve(x, kernel, mode='same'), axis=1, arr=data)

        return smoothed_data

    def moving_average_z(self, data, window_size):
        # Create a convolution kernel for the moving average
        kernel = np.ones(window_size) / window_size

        # Apply the moving average filter along the depth axis
        smoothed_data = np.apply_along_axis(lambda x: np.convolve(x, kernel, mode='same'), axis=0, arr=data)

        return smoothed_data


class ArbSectionData():
    def __init__(self, section_data, depth_m, dist, sampling_intervael, dtm_files, section_coor, pixelsize_z, data_type, top_removed, bottom_removed, depth_table):
        self.section_data = section_data
        self.depth_m = depth_m
        self.dist = dist
        self.sampling_interval = sampling_intervael
        self.dtm_files = dtm_files
        self.section_coor = section_coor
        self.pixelsize_z = pixelsize_z
        self.data_type = data_type
        self.top_removed = top_removed
        self.bottom_removed = bottom_removed
        self.depth_table = depth_table


    def create_image_from_section(self, temp_folder_path, vmin, vmax):
        image_path = os.path.join(temp_folder_path, "section_image_temp.png")

        dpi = 100
        xpixels, ypixels = self.section_data.shape[1], self.section_data.shape[0]
        figsize = xpixels / dpi, ypixels / dpi

        fig = plt.figure(figsize=figsize, dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')  # Turn off the axis

        ax.imshow(self.section_data, cmap='Greys', vmin=vmin, vmax=vmax, interpolation='bilinear')

        # Save the section as an image file
        plt.savefig(image_path, dpi=dpi, bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close()

        return image_path

    def perform_topographic_correction(self, dtm_data, folder_path, vmin, vmax):
        downsampled_height_profile, height_profile = self.topographic_correction(dtm_data)
        topo_image_path = self.save_topo_corrected_section(folder_path, vmin, vmax)

        return self.topo_corr_data, downsampled_height_profile, height_profile, topo_image_path

    def topographic_correction(self, dtm_data):
        dtm = dtm_data

        height_profile = dtm.create_height_profile(self.section_coor, self.section_data.shape[1])

        num_columns = self.section_data.shape[1]
        num_points = height_profile.shape[0]

        # Downsample the height profile to match the number of columns in self.section
        step_size = int(num_points / num_columns)
        downsampled_height_profile = height_profile[::step_size]


        max_elev_diff = int((np.max(downsampled_height_profile) - np.min(downsampled_height_profile)) * (1 / self.pixelsize_z))
        tshift = (np.max(downsampled_height_profile) - downsampled_height_profile) * (1 / self.pixelsize_z)

        # Adjust the time shifts so that the highest elevation becomes zero time
        tshift = tshift.astype(int)  # Convert each element of the array to integers

        # Create a new data matrix with NaN padding
        self.topo_corr_data = np.empty((self.section_data.shape[0] + max_elev_diff, num_columns))
        self.topo_corr_data[:] = np.nan

        for i in range(num_columns):
            shift_amount = tshift[i]

            # Add NaN padding to the bottom of the column
            padded_column = np.pad(self.section_data[:, i], (0, max_elev_diff), mode='constant', constant_values=np.nan)

            # Perform the roll operation
            shifted_column = np.roll(padded_column, shift_amount)

            # Insert the shifted column into newdata
            self.topo_corr_data[:, i] = shifted_column[:self.topo_corr_data.shape[0]]

        return downsampled_height_profile, height_profile

    def save_topo_corrected_section(self, folder_path, vmin, vmax):
        topo_image_path = os.path.join(folder_path, "topo_section_image_temp.png")

        dpi = 100
        xpixels, ypixels = self.topo_corr_data.shape[1], self.topo_corr_data.shape[0]
        figsize = xpixels / dpi, ypixels / dpi

        fig = plt.figure(figsize=figsize, dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')  # Turn off the axis

        ax.imshow(self.topo_corr_data, cmap='Greys', vmin=vmin, vmax=vmax, interpolation='bicubic')

        # Save the section as an image file
        plt.savefig(topo_image_path, dpi=dpi, bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close()

        return topo_image_path
