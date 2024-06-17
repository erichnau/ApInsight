import tkinter as tk
from tkinter import filedialog, PhotoImage
import matplotlib.pyplot as plt
from PIL import Image
import os
from screeninfo import get_monitors
import numpy as np
import platform

from config_manager import ConfigurationManager
from GUI.SectionViewer.TopFrameTools import TopFrameTools
from GUI.SectionViewer.TopFrameToolsVelocity import TopFrameToolsVelocity
from GUI.SectionViewer.SectionCanvas import SectionCanvas

monitors = get_monitors()
screen_res_primary = [monitors[0].height, monitors[0].width]

global window_width, window_height
window_width = int(screen_res_primary[1]*1)
window_height = int(screen_res_primary[0]*0.50)


class SectionView(tk.Toplevel):
    def __init__(self, arb_section=None, project_file_path=None, frame_image=None, frame_left=None, top_frame=None, frame_right=None, mode='arbitrary'):
        super().__init__()
        self.mode = mode
        self.section = arb_section

        self.title("Section View")
        if platform.system() == 'Windows':
            self.iconbitmap('icon2.ico')
        else:
            icon_image = PhotoImage(file='icon2.png')
            self.iconphoto(True, icon_image)

        self.geometry("%dx%d+0+0" % (window_width, window_height))
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cleanup)

        self.config_manager = ConfigurationManager('config.ini')

        if mode == 'arbitrary':
            self.frame_image = frame_image
            self.frame_left = frame_left
            self.top_frame = top_frame
            self.frame_right = frame_right

            self.project_file_path = project_file_path
            self.file_name = self.frame_left.active_file_name

            self.create_temporary_folder(self.mode)
            self.create_top_frame()
            self.create_widgets()
            self._set_image_canvas()
            self._set_section_window()

            self.image_path = self.section.create_image_from_section(self.temp_folder_path, self.tf.vmin, self.tf.vmax)
            self.section_canvas.display_section(self.image_path)

            self._set_canvas_variables()

        elif mode == 'velocity':
            self.create_top_frame_velocity()
            self.create_temporary_folder(self.mode)
            self.create_widgets()
            self._set_image_canvas()


    def create_top_frame(self):
        self.tf = TopFrameTools(self, self.section.section_data)
        self.tf.pack(side="top", fill="x")
        self.frame_left.set_top_frame_tools(self.tf)


    def create_top_frame_velocity(self):
        self.tf = TopFrameToolsVelocity(self, self.display_gpr_data, self.velo_pan, self.velo_zoom, self.velo_home)
        self.tf.pack(side='top', fill='x')

    def velo_home(self):
        self.section_canvas.velo_home()

    def velo_zoom(self):
        self.section_canvas.velo_zoom()

    def velo_pan(self):
        self.section_canvas.velo_pan()

    def display_gpr_data(self, data, info, vmax, vmin):
        self.section_canvas.display_gpr_data(data, info, vmax, vmin)


    def _set_image_canvas(self):
        self.tf.section_canvas = self.section_canvas
        self.section_canvas.tf = self.tf


    def _set_section_window(self):
        self.section_canvas.section_window = self
        self.section_canvas.tf = self.tf
        self.section_canvas.frame_left = self.frame_left


    def _set_canvas_variables(self):
        self.tf.canvas_image = self.section_canvas.canvas_image
        self.tf.x_axis_y = self.section_canvas.x_axis_y
        self.tf.y_axis_x = self.section_canvas.y_axis_x
        self.tf.secondary_y_axis_x = self.section_canvas.secondary_y_axis_x
        self.tf.zoom = self.section_canvas.zoom
        self.tf.section_image = self.section_canvas.section_image
        self.tf.section_window = self
        self.tf.image = self.section_canvas.image
        self.tf.set_zoom_controls()


    def create_widgets(self):
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        frame_width = int(window_width * 0.8)
        frame_height = int(window_height * 0.8)

        image_frame = tk.Frame(self, width=frame_width, height=frame_height, relief="solid", borderwidth=1)
        image_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.pack_propagate(True)

        self.section_canvas = SectionCanvas(image_frame, self.section, self.temp_folder_path, mode=self.mode, bg="white")
        self.section_canvas.pack(fill="both", expand=True)


    def cleanup(self):
        if self.mode == 'arbitrary':
            self.section_canvas.unbind('<Motion>')

            self.frame_left.section_view_active = False
            self.frame_image.section_view_active = False
            self.frame_right.section_view_active = False
            if self.frame_image.marker:
                self.frame_image.clear_marker()
            self.top_frame.section_view_active = False

            self.frame_right.section_view_window = None
            self.frame_right.section_view_active = False
            self.frame_right.enable_section_button()
            self.frame_right.enable_focus_buttons()
            self.frame_right.enable_keep_checkbuttons()
            self.frame_right.toggle_communication_button()

            self.frame_left.enable_project_checkboxes()

        self.destroy()


    def create_temporary_folder(self, mode):
        if mode == 'arbitrary':
            # Get the directory and base name of the JSON file
            json_file_path = self.project_file_path
            json_dir = os.path.dirname(json_file_path)
            json_basename = os.path.basename(json_file_path)
            json_name, _ = os.path.splitext(json_basename)

            # Create a temporary folder path
            self.temp_folder_path = os.path.join(json_dir, json_name + "_temp")
        elif mode == 'velocity':
            self.temp_folder_path = 'c:/temp/apinsight/'

        # Create the temporary folder if it doesn't exist
        os.makedirs(self.temp_folder_path, exist_ok=True)


    def calculate_frame_width(self, frame):
        max_width = 0

        for widget in frame.winfo_children():
            widget.update_idletasks()  # Ensure the widget layout is updated

            # If the widget is a frame, recursively calculate its width
            if isinstance(widget, tk.Frame):
                width = self.calculate_frame_width(widget)
            else:
                width = widget.winfo_width()

            # Update the maximum width found
            max_width += width

        return max_width


    def adjust_window_size(self, resized_width, resized_height, clear_topo=False, zoom=False):
        top_frame_width = self.calculate_frame_width(self.tf) + 50

        # Determine the width for the section image
        image_frame_width = resized_width + 200

        # Set the window width to the maximum of the two widths
        window_width = max(top_frame_width, image_frame_width)
        window_height = resized_height + 200

        if clear_topo:
            window_width = min(window_width, int(screen_res_primary[1]*1))
            self.geometry(f"{window_width}x{self.orig_window_height}")
        elif zoom:
            # Calculate maximum allowable dimensions
            max_width = int(screen_res_primary[1] * 1)
            max_height = int(screen_res_primary[0] * 0.55)

            current_image_width = self.section_canvas.section_image.width()
            current_image_height = self.section_canvas.section_image.height()

            # Determine the width for the section image including some padding
            image_frame_width = current_image_width + 200
            image_frame_height = current_image_height + 200

            # Calculate the total width and height required by the window
            top_frame_width = self.calculate_frame_width(self.tf) + 50
            total_width = max(top_frame_width, image_frame_width)
            total_height = image_frame_height

            # Ensure the window does not exceed the screen size
            width = min(total_width, max_width)
            height = min(total_height, max_height)

            final_height = max(height, self.orig_window_height)
            final_width = max(width, self.orig_window_width)

            if final_height == max_height:
                self.max_height_reached = True
            else:
                self.max_height_reached = False

            self.geometry(f"{final_width}x{final_height}")
        else:
            # Resize the window
            self.geometry(f"{window_width}x{window_height}")
            self.orig_window_width = window_width
            self.orig_window_height = window_height
            # Set the canvas size to match the new window size or a specific area

        self.section_canvas.configure(scrollregion=self.section_canvas.bbox('all'))
        self.section_canvas.update_idletasks()


    def get_closest_indx_height_profile(self, x_data):
        # Get the image top left corner coordinates
        image_left, image_top = self.section_canvas.coords(self.section_canvas.canvas_image)[0:2]

        # Calculate the total length of the downsampled height profile in meters
        total_length_meters = len(self.section_canvas.downsampled_height_profile) * self.section.sampling_interval

        # Calculate the scaling factor for converting x_data to index in the height profile array
        self.scale_factor = self.section_canvas.section_image.width() / total_length_meters

        closest_index = int(round((x_data - image_left) / (self.section.sampling_interval * self.scale_factor)))

        return closest_index


    def get_section_coor_from_xy(self, x, y):
        section_start = self.section.section_coor[0]  # Start point of the section
        section_stop = self.section.section_coor[1]  # Stop point of the section

        # Calculate the total distance along the section
        section_distance = ((section_stop[0] - section_start[0]) ** 2 + (
                section_stop[1] - section_start[1]) ** 2) ** 0.5

        # Calculate the distance from the start of the section to the given xy point
        distance_to_xy = ((x - section_start[0]) ** 2 + (y - section_start[1]) ** 2) ** 0.5

        # Calculate the ratio of the distance to the total distance along the section
        ratio = distance_to_xy / section_distance

        # Interpolate the x and y coordinates along the section
        section_x = round(ratio * self.section.section_data.shape[1])

        return section_x


    def update_x_line(self, x, y, for_labels=False):
        x_offset = 50
        canvas_height = self.section_canvas.winfo_height()

        x_pos = self.get_section_coor_from_xy(x, y)
        adjusted_x = (x_pos * self.section_canvas.zoom) + self.section_canvas.coords(self.section_canvas.canvas_image)[0]

        if for_labels:
            return adjusted_x

        if self.tf.draw_x_line_var.get():
            self.section_canvas.delete('x_line')

            self.section_canvas.create_line(adjusted_x, 0, adjusted_x, canvas_height, tags='x_line')


    def get_y_data_from_depth(self, depth):
        # Adjust y_data for zoom and pan
        num_rows = len(self.section.section_data)
        depth_range = self.section.depth_m
        y_data = (depth / (depth_range * 100)) * num_rows  # Calculate y_data based on depth value
        return y_data


    def get_y_data_from_depth_dtm(self, depth):
        num_rows = len(self.section.section_data)
        depth_range = self.section_canvas.max_depth_new - self.section_canvas.min_depth_new

        # Constrain the depth value within the range of max_depth_new and min_depth_new
        constrained_depth = min(max(depth, self.section_canvas.min_depth_new), self.section_canvas.max_depth_new)

        # Calculate the relative position based on the constrained depth
        relative_depth_position = (self.section_canvas.max_depth_new - constrained_depth) / depth_range

        # Calculate the y-coordinate in the section image
        y_data = relative_depth_position * num_rows

        return int(y_data)


    def get_depth_from_y_data_dtm(self, y_data):
        num_rows = len(self.section.section_data)
        depth_range = self.section_canvas.max_depth_new - self.section_canvas.min_depth_new

        # Calculate the relative position of y_data in the section
        relative_y_position = y_data / num_rows

        # Calculate the depth value based on the relative position
        depth_value = self.section_canvas.max_depth_new - (relative_y_position * depth_range)

        depth_value_rounded = round(depth_value*100 / int(self.section.pixelsize_z*100)) * int(self.section.pixelsize_z*100)

        return depth_value_rounded


    def get_depth_from_y_data_ft(self, y_data):
        # Existing code to calculate depth_value
        num_rows = len(self.section.section_data)
        depth_range = self.section.depth_m
        depth_value = int((y_data / num_rows) * depth_range * 100)  # Convert to centimeters
        depth_value = round(depth_value / (self.section.pixelsize_z * 100)) * (self.section.pixelsize_z * 100) / 100

        # Find the closest value in the first column of the table
        closest_idx = np.argmin(np.abs(self.section.depth_table[:, 0] - depth_value))
        closest_depth = self.section.depth_table[closest_idx, 0]

        return round(closest_depth, 3)


    def set_depth_value(self, depth_start, elevation):
        self.depth_from_ds = depth_start
        self.elevation = elevation


    def update_coordinates_label_from_ds(self, x, y, depth):
        elevation = None
        if self.section.data_type == 2:
            depth = depth * 100
        if self.tf.topo_corrected:
            x = self.update_x_line(x, y, for_labels=True)
            indx = self.get_closest_indx_height_profile(x)
            elevation = self.section_canvas.downsampled_height_profile[indx - 1] - depth / 100
        elif 'DTMfromGPR' in self.file_name:
            depth = self.depth_from_ds
            elevation = self.elevation

        self.section_canvas.coordinates_label.update_coordinates(x, y, depth=depth, elevation=elevation)


    def update_y_line(self, depth):
        if self.tf.draw_y_line_var.get():

            if self.section.data_type == 2:
                depth = depth
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 10
            elif 'DTMfromGPR' in self.file_name:
                y_data = self.get_y_data_from_depth_dtm(depth)
                y_offset = 10
            elif self.tf.topo_corrected:
                depth = depth - 5
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 0
            else:
                depth = depth-5
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 10


            if self.tf.topo_corrected:
                y = (y_data * self.section_canvas.zoom) + self.section_canvas.coords(self.section_canvas.canvas_image)[1]
                self.section_canvas.plot_height_profile(y_data=y, use_ds=True)
            else:
                canvas_width = self.section_canvas.winfo_width()

                y = (y_data * self.section_canvas.zoom) + self.section_canvas.coords(self.section_canvas.canvas_image)[1]

                self.section_canvas.delete('y_line')

                self.section_canvas.create_line(0, y, canvas_width, y, tags='y_line')


    def get_visible_image_bounds(self):
        # Get the position of the image on the canvas
        img_x, img_y = self.section_canvas.coords(self.section_canvas.canvas_image)

        # Get the current size of the image displayed on the canvas
        current_image_width = self.section_canvas.section_image.width()
        current_image_height = self.section_canvas.section_image.height()

        # Determine the visible area bounds on the canvas
        left_bound = self.section_canvas.y_axis_x
        top_bound = 10
        right_bound = self.section_canvas.secondary_y_axis_x
        bottom_bound = self.section_canvas.x_axis_y

        # Convert canvas coordinates to image coordinates
        visible_left = int(max(0, left_bound - img_x))
        visible_top = int(max(0, top_bound - img_y))
        visible_right = int(min(current_image_width, right_bound - img_x))
        visible_bottom = int(min(current_image_height, bottom_bound - img_y))

        # Check for the case where 'right' is less than 'left'
        if visible_right <= visible_left or visible_bottom <= visible_top:
            return None  # Return None to indicate there's no valid crop area

        return visible_left, visible_top, visible_right, visible_bottom


    def save_section(self):
        file_path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG Image', '*.png')])
        if not file_path:
            return  # User cancelled the save operation

        visible_bounds = self.get_visible_image_bounds()
        if not visible_bounds:
            return  # No visible bounds calculated

        visible_left, visible_top, visible_right, visible_bottom = visible_bounds

        if visible_right <= visible_left or visible_bottom <= visible_top:
            return None  # Return None to indicate there's no valid crop area

        self.cropped_image = self.apply_transformations(visible_left, visible_top, visible_right, visible_bottom)
        self.cropped_image.save(file_path, 'PNG')

        self.plot_image_with_labels(file_path)


    def apply_transformations(self, visible_left, visible_top, visible_right, visible_bottom):
        image_path = self.section_canvas.topo_image_path if self.tf.topo_corrected else self.section_canvas.image_path
        pil_section_image = Image.open(image_path)
        pil_section_image = pil_section_image.resize(
            (self.section_canvas.section_image.width(), self.section_canvas.section_image.height()), Image.LANCZOS)
        return pil_section_image.crop((visible_left, visible_top, visible_right, visible_bottom))


    def plot_image_with_labels(self, file_path):
        image_array = np.array(self.cropped_image)
        xpixels, ypixels = image_array.shape[1], image_array.shape[0]
        dpi = 300
        plt.rcParams.update({'font.size': 10})
        figsize = ((xpixels * 3) / dpi, (ypixels * 3) / dpi)

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.imshow(image_array)
        ax.set_aspect('auto')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_xlim([0, xpixels])
        ax.set_ylim([ypixels, 0])

        self._plot_labels(ax, ax.twinx())

        plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        fig.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        self.lift()


    def _plot_labels(self, ax, ax_sec):
        x_label_data = self.get_label_data(self.section_canvas.x_labels)
        y_label_data = self.get_label_data(self.section_canvas.y_labels)
        secondary_y_label_data = self.get_label_data(self.section_canvas.secondary_y_labels)
        additional_label_data = self.get_label_data(self.section_canvas.additional_labels)

        max_digits = max(len(data['text']) for data in y_label_data)
        depth_label_offset = 5 + 5 * (max_digits - 2) if max_digits >= 3 else 5

        self._configure_axis(ax, y_label_data, 'y')
        self._configure_axis(ax_sec, secondary_y_label_data, 'sec_y', invert=True)
        self._configure_axis(ax, x_label_data, 'x')

        for data in additional_label_data:
            self._plot_additional_labels(ax, data, depth_label_offset)


    def _configure_axis(self, ax, label_data, axis, invert=False):
        vals, labs = [], []
        for data in label_data:
            pos = data['y'] if axis in ['y', 'sec_y'] else data['x']
            lab = data['text']
            vals.append(pos)
            labs.append(lab)

        max_val = max(vals)
        min_val = min(vals)
        ticks = np.linspace(max_val, min_val, num=5)

        if axis in ['y', 'sec_y']:
            ax.set_yticks(np.linspace(0, max_val - min_val, len(ticks)))
            ax.set_yticklabels(labs)
            if invert:
                ax.invert_yaxis()
        elif axis == 'x':
            ax.set_xticks(np.linspace(0, max_val - min_val, len(ticks)))
            ax.set_xticklabels(labs)


    def _plot_additional_labels(self, ax, data, depth_label_offset):
        if data['tag'] == 'dist_label':
            ax.text(data['x'] - self.section_canvas.y_axis_x, data['y'] - 5, data['text'], ha='center', va='top',
                    color='black', fontweight='bold')
        elif data['tag'] == 'depth_label':
            ax.text(data['x'] - self.section_canvas.y_axis_x - depth_label_offset, data['y'] - 10, data['text'],
                    rotation=90, ha='center', va='center', color='black', fontweight='bold')
        elif data['tag'] == 'sec_depth_label':
            ax.text(data['x'] - self.section_canvas.y_axis_x + depth_label_offset, data['y'] - 10, data['text'],
                    rotation=90, ha='center', va='center', color='black', fontweight='bold')


    def get_label_data(self, label_ids):
        label_data = []
        for label_id in label_ids:
            text = self.section_canvas.itemcget(label_id, 'text')
            coords = self.section_canvas.coords(label_id)
            tags = self.section_canvas.gettags(label_id)
            if coords:
                x_pos, y_pos = coords[0], coords[1]
                tag = tags[0] if tags else None
                label_data.append({'text': text, 'x': x_pos, 'y': y_pos, 'tag': tag})

        if label_data and (label_data[0]['tag'] == 'label_x' or label_data[0]['tag'] == 'label_y'):
            label_data = self.recalculate_labels(label_data)

        return label_data


    def recalculate_labels(self, data):
        axis = data[0]['tag']
        min_pixel, max_pixel, pixel_interval = self._calculate_pixel_intervals(axis)
        label_data_new = []

        start_value, total_range, label_interval = self._calculate_label_intervals(data, min_pixel)

        for i in range(5):
            label_pos = min_pixel + i * pixel_interval
            label_value = round(start_value + i * label_interval, 1)
            if axis == 'label_x':
                label_data_new.append({'text': str(label_value), 'x': label_pos, 'y': data[0]['y'], 'tag': axis})
            elif axis == 'label_y':
                label_data_new.append({'text': str(label_value), 'x': data[0]['x'], 'y': label_pos, 'tag': axis})

        return label_data_new


    def _calculate_pixel_intervals(self, axis):
        if axis == 'label_x':
            min_pixel = self.section_canvas.y_axis_x
            max_pixel = self.section_canvas.secondary_y_axis_x
        elif axis == 'label_y':
            min_pixel = 10
            max_pixel = self.section_canvas.x_axis_y

        total_pixel_distance = max_pixel - min_pixel
        pixel_interval = total_pixel_distance / 4

        return min_pixel, max_pixel, pixel_interval


    def _calculate_label_intervals(self, data, min_pixel):
        axis = data[0]['tag']
        lab1 = float(data[0]['text'])
        lab2 = float(data[1]['text'])

        if axis == 'label_x':
            lab1_pos = float(data[0]['x'])
            lab2_pos = float(data[1]['x'])
        elif axis == 'label_y':
            lab1_pos = float(data[0]['y'])
            lab2_pos = float(data[1]['y'])

        interval = lab2 - lab1
        interval_y = lab2_pos - lab1_pos

        pixel_per_meter = interval_y / interval
        start_value = lab1 - (lab1_pos - min_pixel) / pixel_per_meter
        total_range = interval * 4
        label_interval = total_range / 4

        return start_value, total_range, label_interval


    def update_depthslice_canvas(self, x, y):
        x_coor, y_coor = self.get_xy_from_section_coor(x)

        if 'DTMfromGPR' in self.file_name:
            depth = self.get_depth_from_y_data_dtm(y)
        elif self.section.data_type == 2:
            if self.tf.topo_corrected:
                depth = (self.get_depth_from_y_data(self.section_canvas.y_coord_max_point) - 5) / 100
            else:
                depth = self.get_depth_from_y_data_ft(y)

        elif self.tf.topo_corrected:
            depth = self.get_depth_from_y_data(self.section_canvas.y_coord_max_point) - 5
        else:
            depth = self.get_depth_from_y_data(y)

        self.frame_image.section_coor(x_coor, y_coor)
        self.frame_left.update_image_selection(depth)

        elevation = None
        if self.section.data_type == 2:
            depth = depth*100
        if self.tf.topo_corrected:
            elevation = self.section_canvas.height - depth/100
        if 'DTMfromGPR' in self.file_name:
            elevation = depth / 100
            depth = self.depth_from_ds

        self.frame_image.coordinates_label.update_coordinates(x_coor, y_coor)
        self.section_canvas.coordinates_label.update_coordinates(x_coor, y_coor, depth=depth, elevation=elevation)


    def get_xy_from_section_coor(self, x):
        section_start = self.section.section_coor[0]  # Start point of the section
        section_stop = self.section.section_coor[1]  # Stop point of the section
        x /= round(self.section.section_data.shape[1]/self.section.dist)
        # Calculate the total distance along the section
        section_distance = ((section_stop[0] - section_start[0]) ** 2 + (
                    section_stop[1] - section_start[1]) ** 2) ** 0.5

        # Calculate the ratio of the given x_data relative to the total distance
        ratio = x / section_distance

        # Interpolate the x and y coordinates along the section
        x = round(section_start[0] + (section_stop[0] - section_start[0]) * ratio, 3)
        y = round(section_start[1] + (section_stop[1] - section_start[1]) * ratio, 3)

        return x, y


    def get_depth_from_y_data(self, y_data):
        num_rows = len(self.section.section_data)
        depth_range = self.section.depth_m
        depth_value = int((y_data / num_rows) * depth_range * 100)  # Multiply by 100 to convert to centimeters
        depth_value = round(depth_value / (self.section.pixelsize_z * 100)) * (self.section.pixelsize_z * 100)   # Round to the nearest 5 cm step
        return depth_value





