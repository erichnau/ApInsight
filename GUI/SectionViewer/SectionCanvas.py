import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
from tkinter import messagebox
import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from GUI.CoordinatesLabel import CoordinatesLabel
from GUI.SectionViewer.DTMFileSelector import DTMFileSelector


class SectionCanvas(tk.Canvas):
    def __init__(self, master, section, temp_folder_path, mode, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.section = section
        self.temp_folder_path = temp_folder_path
        self.mode = mode

        self.height_profile = None
        self.image_path = None
        self.section_image = None
        self.canvas_image = None
        self.zoom = 1
        self.init_zoom = 1
        self.init_image_position = (0, 0)
        self.section_window = None
        self.tf = None
        self.frame_left = None

        self.pan_offset_x = 0
        self.pan_offset_y = 0

        self.x_axis = None
        self.mask_tag = None

        self.y_labels = []  # list to store y-axis labels
        self.x_labels = []  # list to store x-axis labels
        self.secondary_y_labels = []
        self.additional_labels = []

        if self.mode == 'arbitrary':
            self.bindings()
            self.coordinates_label = CoordinatesLabel(self)
        elif self.mode =='velocity':
            self.figure = None


    def bindings(self):
        self.bind("<ButtonPress-1>", self.start_pan)
        self.bind("<B1-Motion>", self.pan_image)

    def display_gpr_data(self, data, info, vmax, vmin):
        self.trace_increment = float(info[0])
        self.time_increment = float(info[1])
        self.nr_traces = info[2]
        self.nr_samples = info[3]
        self.antenna_separation = info[4]

        timewindow = float(info[1]) * float(info[3])

        self.profilePos = (float(info[0]) / 2) * np.arange(0, (data.shape[1] * 2))
        self.twtt = np.linspace(0, timewindow, info[3])

        self.yrng = [np.min(self.twtt), np.max(self.twtt)]
        self.xrng = [np.min(self.profilePos), np.max(self.profilePos)]

        dx = self.profilePos[3] - self.profilePos[2]
        dt = self.twtt[3] - self.twtt[2]

        if self.figure is None:
            canvas_width = self.winfo_width()
            canvas_height = self.winfo_height()

            left_margin = 50 / canvas_width
            right_margin = 1 - 50 / canvas_width
            top_margin = 1 - 10 / canvas_height
            bottom_margin = 75 / canvas_height

            self.figure = Figure(figsize=(canvas_width / 100, canvas_height / 100), dpi=100)
            self.figure.subplots_adjust(left=left_margin, right=right_margin, top=top_margin, bottom=bottom_margin)

            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.toolbar = NavigationToolbar2Tk(self.canvas, self)
            self.toolbar.update()
            self.toolbar.pack_forget()
            self.canvas.get_tk_widget().place(x=0, y=0)

        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        self.ax.imshow(data, cmap='gray', vmax=vmax, vmin=vmin,
                       extent=[min(self.profilePos) - dx / 2.0, max(self.profilePos) + dx / 2.0,
                               max(self.twtt) + dt / 2.0, min(self.twtt) - dt / 2.0],
                       aspect='auto')

        self.ax.set_ylim(self.yrng)
        self.ax.set_xlim(self.xrng)
        self.ax.set_ylabel("two-way travel time [ns]", fontsize=mpl.rcParams['font.size'])
        self.ax.invert_yaxis()

        self.ax.get_xaxis().set_visible(True)
        self.ax.get_yaxis().set_visible(True)
        self.ax.set_xlabel("profile position [m]", fontsize=mpl.rcParams['font.size'])

        self.canvas.draw()

    def velo_pan(self):
        self.toolbar.pan()

    def velo_home(self):
        self.toolbar.home()

    def velo_zoom(self):
        self.toolbar.zoom()

    def start_pan(self, event):
        self.init_image_position = (event.x, event.y)

    def pan_image(self, event):
        dx = (event.x - self.init_image_position[0])
        dy = (event.y - self.init_image_position[1])

        self.pan_offset_x += dx
        self.pan_offset_y += dy

        actual_image_width = self.section_image.width()
        actual_image_height = self.section_image.height()

        current_pos = self.coords(self.canvas_image)
        new_x = current_pos[0] + dx
        new_y = current_pos[1] + dy

        if new_x > self.image_left_bound:
            dx = self.image_left_bound - current_pos[0]
        if new_x + actual_image_width < self.secondary_y_axis_x:
            dx = self.secondary_y_axis_x - 1 - (current_pos[0] + actual_image_width)

        if new_y > self.image_top_bound:
            dy = self.image_top_bound - current_pos[1]
        elif new_y + actual_image_height < self.x_axis_y:
            dy = self.x_axis_y - 2 - (current_pos[1] + actual_image_height)

        self.move(self.canvas_image, dx, dy)
        self.init_image_position = (event.x, event.y)
        self.update_axes_based_on_pan(dx, dy)


    def update_axes_based_on_pan(self, dx, dy):
        # Adjust the x-axis labels based on the image movement, skip the last label
        for label in self.x_labels[:-1]:  # The '[:-1]' slice selects all but the last item
            self.move(label, dx, 0)

        # Adjust the y-axis labels based on the image movement, skip the last label
        for label in self.y_labels[:-1]:  # Similarly, '[:-1]' skips the last item
            self.move(label, 0, dy)

        # Do the same for secondary y-axis labels if present, skip the last label
        for label in self.secondary_y_labels[:-1]:
            self.move(label, 0, dy)

    def display_section(self, image_path, top_corr=False, update_vmin_vmax=False, clear_topo=False):
        if top_corr == False:
            self.image_path = image_path
        self.image = Image.open(image_path)
        self.section_image = ImageTk.PhotoImage(self.image)

        # Remove the old image if it exists
        if self.canvas_image:
            self.delete(self.canvas_image)

        # Create a new image on the canvas
        self.canvas_image = self.create_image(0, 0, anchor='nw', image=self.section_image)
        self.configure(scrollregion=self.bbox('all'))
        self.update()

        self.resize_image_to_canvas(top_corr, update_vmin_vmax, clear_topo)

    def resize_image_to_canvas(self, top_corr=False, update_vmin_vmax=False, clear_topo=False):
        canvas_width, canvas_height = self.winfo_width(), self.winfo_height()
        image_width, image_height = self.section_image.width(), self.section_image.height()

        available_width, available_height = self._calculate_available_space(canvas_width, canvas_height)
        zoom_x, zoom_y = available_width / image_width, available_height / image_height

        if top_corr:
            self._resize_topographic_image(image_width, image_height, zoom_x, zoom_y, update_vmin_vmax)
        else:
            self._resize_standard_image(image_width, image_height, zoom_x, zoom_y, update_vmin_vmax, clear_topo)

        self._place_image_on_canvas()
        self._update_canvas_properties(top_corr)

    def _calculate_available_space(self, canvas_width, canvas_height):
        available_width = canvas_width - 120  # adjust based on the axis width
        available_height = canvas_height - 70  # adjust based on the axis height
        return available_width, available_height

    def _resize_topographic_image(self, image_width, image_height, zoom_x, zoom_y, update_vmin_vmax):
        required_canvas_height = image_height + 70  # Account for axis height
        if required_canvas_height > self.winfo_height():
            self.config(height=required_canvas_height)

        self._calculate_zoom_level(image_width, image_height, zoom_x, zoom_y)
        self.resized_height_topo = self.resized_height
        self._resize_and_save_image('resized_topo_image.png')

        if not update_vmin_vmax:
            self.section_window.adjust_window_size(self.resized_width, self.resized_height)

    def _resize_standard_image(self, image_width, image_height, zoom_x, zoom_y, update_vmin_vmax, clear_topo):
        self.zoom = min(zoom_x, zoom_y)
        self.init_zoom = self.zoom

        self.resized_width = int(image_width * self.zoom)
        self.resized_height = int(image_height * self.zoom)
        self.image_height_orig = self.resized_height

        self._resize_and_save_image('resized_image.png')

        if not update_vmin_vmax and not clear_topo:
            self.section_window.adjust_window_size(resized_width=self.resized_width, resized_height=self.resized_height)
            self.orig_window_width = self.winfo_width()
            self.orig_window_height = self.winfo_height()
        elif clear_topo:
            self.section_window.adjust_window_size(clear_topo=True, resized_width=self.resized_width,
                                                   resized_height=self.resized_height)

    def _calculate_zoom_level(self, image_width, image_height, zoom_x, zoom_y):
        self.zoom = min(zoom_x, zoom_y)
        self.resized_width = int(image_width * self.zoom)
        self.resized_height = int(image_height * self.zoom)

    def _resize_and_save_image(self, filename):
        resized_image = self.image.resize((self.resized_width, self.resized_height), Image.LANCZOS)
        resized_image.save(self.temp_folder_path + filename)
        self.section_image = ImageTk.PhotoImage(resized_image)

    def _place_image_on_canvas(self):
        x_offset, y_offset = 50, 0  # adjust based on the axis dimensions
        self.itemconfig(self.canvas_image, image=self.section_image)
        self.coords(self.canvas_image, x_offset + 1, y_offset + 10)

    def _update_canvas_properties(self, top_corr):
        self.configure(scrollregion=self.bbox('all'))
        self.update_idletasks()

        self.update_axes(top_corr)

        self.bind('<Motion>', self.draw_lines)

        self.init_image_pos = self.coords(self.canvas_image)

        self.actual_image_width = self.section_image.width()
        self.actual_image_height = self.section_image.height()

        self.image_left_bound = self.init_image_pos[0]
        self.image_right_bound = self.image_left_bound + self.actual_image_width
        self.image_top_bound = self.init_image_pos[1]
        self.image_bottom_bound = self.image_top_bound + self.actual_image_height

    def update_axes(self, top_corr=False):
        self._delete_existing_axes()
        self._create_axes_lines()

        self._calculate_axis_positions()

        self.create_masks()

        self._update_axes_lines()

        self._clear_existing_labels()

        self._calculate_tick_values(top_corr)
        self._add_y_axis_labels()
        self._add_x_axis_labels()
        self._add_distance_labels()
        self._add_depth_labels(top_corr)

    def _delete_existing_axes(self):
        if self.x_axis is not None:
            self.delete(self.x_axis)
            self.delete(self.y_axis)
            self.delete(self.secondary_y_axis)

    def _create_axes_lines(self):
        self.x_axis = self.create_line(0, 0, 0, 0, fill='black', width=2)
        self.y_axis = self.create_line(0, 0, 0, 0, fill='black', width=2)
        self.secondary_y_axis = self.create_line(0, 0, 0, 0, fill='black', width=2)

    def _calculate_axis_positions(self):
        self.x_axis_y = self.section_image.height() + 12
        self.y_axis_x = 50
        self.secondary_y_axis_x = self.section_image.width() + self.y_axis_x + 2

    def _update_axes_lines(self):
        self.coords(self.x_axis, self.y_axis_x, self.x_axis_y, self.secondary_y_axis_x, self.x_axis_y)
        self.coords(self.y_axis, self.y_axis_x, 10, self.y_axis_x, self.x_axis_y)
        self.coords(self.secondary_y_axis, self.secondary_y_axis_x, 10, self.secondary_y_axis_x, self.x_axis_y)

    def _clear_existing_labels(self):
        for label in self.x_labels:
            self.delete(label)
        self.x_labels = []

        for label in self.y_labels:
            self.delete(label)
        self.y_labels = []

        for label in self.secondary_y_labels:
            self.delete(label)
        self.secondary_y_labels = []

        for label in self.additional_labels:
            self.delete(label)
        self.additional_labels = []

    def _calculate_tick_values(self, top_corr):
        if top_corr:
            min_height = min(self.height_profile)
            max_height = max(self.height_profile)
            min_depth = min_height - self.section.depth_m
            num_depth_ticks = 5
            height_ticks = np.linspace(max(self.height_profile), min(self.height_profile) - self.section.depth_m,
                                       num=num_depth_ticks)
            self.depth_ticks = max(self.height_profile) - height_ticks
            self.min_depth_new = min_depth
            self.max_depth_new = max_height
            self.depth_ticks = np.linspace(self.max_depth_new, self.min_depth_new, num=5)
        elif 'DTMfromGPR' in self.section_window.file_name:
            min_depth = round((self.frame_left.min_depth / 100), 2)
            max_depth = round((self.frame_left.max_depth / 100), 2)
            self.min_depth_new = min_depth + self.section.bottom_removed * self.section.pixelsize_z
            self.max_depth_new = max_depth - self.section.top_removed * self.section.pixelsize_z
            self.depth_ticks = np.linspace(self.max_depth_new, self.min_depth_new, num=5)
        else:
            self.depth_ticks = np.linspace(0, self.section.depth_m, num=5)
        self.distance_ticks = np.linspace(0, self.section.dist, num=5)

    def _add_y_axis_labels(self):
        y_label_interval = (self.x_axis_y - 10) / (len(self.depth_ticks) - 1)
        for i, depth in enumerate(self.depth_ticks):
            label_y = 10 + i * y_label_interval
            if 'DTMfromGPR' in self.section_window.file_name:
                label_text = f"{depth:.1f}"
            elif self.tf.topo_corrected:
                label_text = f"{depth:.1f}"
            else:
                label_text = f"{depth:.1f}"
            self._create_y_axis_label(label_y, label_text)

    def _create_y_axis_label(self, label_y, label_text):
        label = self.create_text(self.y_axis_x - 5, label_y, anchor='e', text=label_text, tags='label_y')
        self.y_labels.append(label)
        secondary_label = self.create_text(self.secondary_y_axis_x + 5, label_y, anchor='w', text=label_text,
                                           tags='label_y')
        self.secondary_y_labels.append(secondary_label)

    def _add_x_axis_labels(self):
        x_label_interval = (self.secondary_y_axis_x - self.y_axis_x) / (len(self.distance_ticks) - 1)
        for i, distance in enumerate(self.distance_ticks):
            label_x = self.y_axis_x + i * x_label_interval
            label_text = f"{distance:.1f}"
            self._create_x_axis_label(label_x, label_text)

    def _create_x_axis_label(self, label_x, label_text):
        label = self.create_text(label_x, self.x_axis_y + 10, anchor='n', text=label_text, tags='label_x')
        self.x_labels.append(label)

    def _add_distance_labels(self):
        distance_label_x = int((self.y_axis_x + self.secondary_y_axis_x) / 2)
        distance_label_y = self.x_axis_y + 25
        distance_label = self.create_text(distance_label_x, distance_label_y, anchor='n', text='Distance (m)',
                                          font=("Arial", 11, "bold"), tags='dist_label')
        self.additional_labels.append(distance_label)

    def _add_depth_labels(self, top_corr):
        depth_label_x = self._calculate_depth_label_x()
        depth_label_y = int((10 + self.x_axis_y) / 2)
        depth_label_text = 'Elevation (m)' if 'DTMfromGPR' in self.section_window.file_name or top_corr else 'Depth (m)'
        self._create_depth_label(depth_label_x, depth_label_y, depth_label_text)
        secondary_depth_label_x = self._calculate_secondary_depth_label_x(top_corr)
        secondary_depth_label_text = depth_label_text
        self._create_secondary_depth_label(secondary_depth_label_x, depth_label_y, secondary_depth_label_text)

    def _calculate_depth_label_x(self):
        if 'DTMfromGPR' in self.section_window.file_name or self.tf.topo_corrected:
            return self.y_axis_x - 40
        else:
            return self.y_axis_x - 35

    def _calculate_secondary_depth_label_x(self, top_corr):
        if 'DTMfromGPR' in self.section_window.file_name or top_corr:
            return self.secondary_y_axis_x + 40
        else:
            return self.secondary_y_axis_x + 35

    def _create_depth_label(self, x, y, text):
        depth_label = self.create_text(x, y, anchor='e', text=text, angle=90, font=("Arial", 11, "bold"),
                                       tags='depth_label')
        self.additional_labels.append(depth_label)

    def _create_secondary_depth_label(self, x, y, text):
        secondary_depth_label = self.create_text(x, y, anchor='e', text=text, angle=90, font=("Arial", 11, "bold"),
                                                 tags='sec_depth_label')
        self.additional_labels.append(secondary_depth_label)

    def create_masks(self):
        # Assuming self.canvas is your Tkinter Canvas instance
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        if self.mask_tag is not None:
            self.delete("mask")

        # Color to match the background or any color that indicates a non-visible area
        mask_color = 'white'
        self.mask_tag = 'mask'

        # Top mask
        self.create_rectangle(-100, -100, canvas_width + 100, 10, fill=mask_color, outline=mask_color,
                                             tags=self.mask_tag)

        # Bottom mask
        self.create_rectangle(-100, self.x_axis_y + 1, canvas_width + 100, canvas_height + 100,
                                             fill=mask_color,
                                             outline=mask_color, tags=self.mask_tag)

        # Left mask
        self.create_rectangle(-100, -100, self.y_axis_x - 2, canvas_height + 100, fill=mask_color,
                                             outline=mask_color, tags=self.mask_tag)

        # Right mask
        self.create_rectangle(self.secondary_y_axis_x + 1, -100, canvas_width + 100, canvas_height + 100,
                                             fill=mask_color,
                                             outline=mask_color, tags=self.mask_tag)


    def add_topography(self):
        self.clear_topography()
        if len(self.section.dtm_files) == 1:
            dtm_data = next(iter(self.section.dtm_files.values()))
            self.topo_corr_data, self.downsampled_height_profile, self.height_profile, self.topo_image_path = self.section.perform_topographic_correction(dtm_data, self.temp_folder_path, self.tf.vmin, self.tf.vmax)
            self.display_section(self.topo_image_path, top_corr=True)
        elif len(self.section.dtm_files) > 1:
            dtm_selector = DTMFileSelector(self, self.section.dtm_files)
            selected_files = dtm_selector.get_selected_dtm_files()
            if selected_files:
                self.topo_corr_data, self.downsampled_height_profile, self.height_profile, self.topo_image_path = self.section.perform_topographic_correction(
                    selected_files[0], self.temp_folder_path, self.tf.vmin, self.tf.vmax)
                self.display_section(self.topo_image_path, top_corr=True)
        else:
            messagebox.showinfo("No DTM File", "No DTM file available for topographic correction.")

        self.tf.topo_corrected = True
        self.section_window.lift()
        self.init_image_position = (0, 0)


    def regenerate_and_refresh_image(self):
        # Regenerate the image with the new vmin and vmax values
        if self.tf.topo_corrected:
            self.section.save_topo_corrected_section(self.temp_folder_path, self.tf.vmin, self.tf.vmax)
        else:
            self.image_path = self.section.create_image_from_section(self.temp_folder_path, self.tf.vmin, self.tf.vmax)
            self.display_section(self.image_path, top_corr=self.tf.topo_corrected, update_vmin_vmax=True)


    def clear_topography(self):
        self.display_section(self.image_path, top_corr=False, clear_topo=True)
        self.init_image_position = (0, 0)
        self.tf.topo_corrected = False

    def draw_lines(self, event):
        x, y = event.x, event.y

        # Get the current image position on the canvas
        current_image_pos = self.coords(self.canvas_image)
        image_left, image_top = current_image_pos[0], current_image_pos[1]

        if x <= self.y_axis_x:
            x = self.y_axis_x
        elif x >= self.secondary_y_axis_x:
            x = self.secondary_y_axis_x

        if y <= 10:
            y = 10
        elif y >= self.x_axis_y:
            y = self.x_axis_y

        x_data = (x - image_left) / self.zoom
        y_data = (y - image_top) / self.zoom

        # Ensure the calculations do not go beyond the image dimensions
        x_data = max(0, min(self.section_image.width() / self.zoom, x_data))
        y_data = max(0, min(self.section_image.height() / self.zoom, y_data))

        # Bounds for drawing the lines based on the visible part of the image
        image_right = image_left + self.section_image.width()# * self.zoom
        image_bottom = image_top + self.section_image.height()# * self.zoom

        # Check if the cursor is within the visible part of the image
        if image_left <= x <= image_right and image_top <= y <= image_bottom:
            # Clear any previously drawn lines
            self.delete('x_line')
            self.delete('y_line')
            self.delete('height_profile_line')

            # Draw vertical line
            if self.tf.draw_x_line_var.get():
                self.create_line(x, max(image_top, 0), x,
                                                min(image_bottom, self.winfo_height()), tags='x_line')

            # Draw horizontal line or plot height profile
            if self.tf.draw_y_line_var.get():
                if self.tf.topo_corrected:
                    self.plot_height_profile(y, x)
                else:
                    self.create_line(max(image_left, 0), y,
                                                    min(image_right, self.winfo_width()), y,
                                                    tags='y_line')

            if self.tf.communication_var.get():
                self.section_window.update_depthslice_canvas(x_data, y_data)

        else:
            # Cursor is outside the image bounds, remove any previously drawn lines
            self.delete('x_line')
            self.delete('y_line')
            self.delete('height_profile_line')


    def plot_height_profile(self, y_data, x_data=None, use_ds=False):
        # Clear any previous height profile lines
        self.delete('height_profile_line')

        # Get the image top left corner coordinates
        image_left, image_top = self.coords(self.canvas_image)[0:2]

        min_height = min(self.downsampled_height_profile)
        max_height = np.argmax(self.downsampled_height_profile)

        # Calculate the total length of the downsampled height profile in meters
        total_length_meters = len(self.downsampled_height_profile) * self.section.sampling_interval

        # Calculate the scaling factor for converting x_data to index in the height profile array
        self.scale_factor = self.section_image.width() / total_length_meters

        height_points = []

        if use_ds:
            closest_index = np.argmax(self.downsampled_height_profile) + 1
        else:
            closest_index = int(round((x_data - image_left) / (self.section.sampling_interval * self.scale_factor)))
            self.height = self.downsampled_height_profile[closest_index - 1]

        # Calculate the y-coordinate offset for this height point based on the closest index
        y_offset = (y_data + (self.downsampled_height_profile[closest_index - 1] - min_height) * self.scale_factor)

        # Iterate over each height value and its index in the height profile
        for i, height in enumerate(self.downsampled_height_profile):
            # Calculate the x-coordinate for this height point
            x_coord = image_left + (i * self.section.sampling_interval) * self.scale_factor

            # Calculate the y-coordinate for this height point
            y_coord = y_offset - (height - min_height) * self.scale_factor

            # Append the calculated (x, y) point to the height_points list
            height_points.append((x_coord, y_coord, i))  # Include index

        # Filter height_points to only include those within the visible x bounds
        visible_height_points = [point for point in height_points if
                                 self.y_axis_x <= point[0] <= self.secondary_y_axis_x]

        if visible_height_points:
            max_height_point = min(visible_height_points, key=lambda point: point[1])
            y_data_max_height = max_height_point[1]
            self.y_max_height = y_data_max_height / self.zoom

            self.y_coord_max_point = abs(((image_top - 10) / self.zoom)) + ((y_offset) - (
                        self.downsampled_height_profile[max_height] - min_height) * self.scale_factor) / self.zoom

        # Create a line using the visible height points without the index
        self.create_line([(x, y) for x, y, _ in visible_height_points], fill='black',
                                        tags='height_profile_line')


    def zoom_section(self, direction='in', cursor_position=None):
        # Determine the zoom factor
        if direction == 'in':
            zoom_factor = 1.1
        elif direction == 'out':
            zoom_factor = 1 / 1.1
        else:
            raise ValueError("Invalid zoom direction. Use 'in' or 'out'.")

        # Get the current center of the viewport or cursor position
        if cursor_position is None:
            viewport_center_x = self.canvasx(self.winfo_width() / 2)
            viewport_center_y = self.canvasy(self.winfo_height() / 2)
        else:
            viewport_center_x, viewport_center_y = cursor_position

        # Calculate the new dimensions
        new_width = int(self.section_image.width() * zoom_factor)
        new_height = int(self.section_image.height() * zoom_factor)

        if direction == 'in':
            self.zoom *= zoom_factor
        else:
            self.zoom /= zoom_factor

        # Ensure dimensions do not fall below the actual initial dimensions when zooming out
        if direction == 'out':
            new_width = max(new_width, self.actual_image_width)
            new_height = max(new_height, self.actual_image_height)
            if new_width == self.actual_image_width:
                self.zoom = self.init_zoom

        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        self.section_image = ImageTk.PhotoImage(resized_image)

        # Calculate the new position based on the zoom center
        current_pos = self.coords(self.canvas_image)
        if direction == 'in':
            new_x = viewport_center_x - (viewport_center_x - current_pos[0]) * zoom_factor
            new_y = viewport_center_y - (viewport_center_y - current_pos[1]) * zoom_factor
        else:
            shift_x = (self.section_image.width() - new_width) / 2
            shift_y = (self.section_image.height() - new_height) / 2
            new_x = viewport_center_x - (viewport_center_x - current_pos[0]) * (1 / zoom_factor)
            new_y = viewport_center_y - (viewport_center_y - current_pos[1]) * (1 / zoom_factor)

        # Apply boundary constraints
        new_x = min(max(new_x, self.secondary_y_axis_x - new_width), self.image_left_bound)
        new_y = min(max(new_y, self.x_axis_y - new_height), self.image_top_bound)

        # Update the image position and zoom
        self.itemconfig(self.canvas_image, image=self.section_image)
        self.coords(self.canvas_image, new_x, new_y)

        self.section_window.adjust_window_size(new_width, new_height, zoom=True)
        self.update_axes_after_zoom()

        fake_event = FakeEvent(viewport_center_x, viewport_center_y)
        self.pan_image(fake_event)


    def update_axes_after_zoom(self):
        # Get the current canvas (or window) height and width
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        # Calculate maximum allowed positions for the axes based on the canvas dimensions
        max_x_axis_y = canvas_height - 80  # Subtracting 50 for padding
        max_secondary_y_axis_x = canvas_width - 50  # Subtracting 50 for padding

        # Calculate new positions for the axes based on the zoomed image dimensions
        proposed_x_axis_y = self.section_image.height() + 12
        proposed_secondary_y_axis_x = self.y_axis_x + self.section_image.width()

        # Apply the maximum constraints
        self.x_axis_y = min(proposed_x_axis_y, max_x_axis_y)
        self.secondary_y_axis_x = min(proposed_secondary_y_axis_x, max_secondary_y_axis_x)

        # Update the axes lines to the new positions
        self.coords(self.x_axis, self.y_axis_x, self.x_axis_y, self.secondary_y_axis_x, self.x_axis_y)
        self.coords(self.y_axis, self.y_axis_x, 10, self.y_axis_x, self.x_axis_y)
        self.coords(self.secondary_y_axis, self.secondary_y_axis_x, 10, self.secondary_y_axis_x,
                                   self.x_axis_y)

        # Recreate masks to fit the new dimensions
        self.create_masks()
        self.update_labels_for_full_image(axis='x')
        self.update_labels_for_full_image(axis='y')
        self.update_labels_for_full_image(axis='secondary_y')
        self.update_label_positions()

    def update_labels_for_full_image(self, axis='x'):
        if axis not in ['x', 'y', 'secondary_y']:
            raise ValueError("Axis must be 'x', 'y', or 'secondary_y'")

        if axis == 'x':
            num_visible_labels = 5  # Number of labels always visible in the viewport
            actual_start = self.coords(self.canvas_image)[0]
            canvas_size = self.winfo_width()
            image_size = self.section_image.width()
            axis_pos = self.x_axis_y + 10
            labels = self.x_labels
            pixel_to_unit_ratio = self.section.dist / image_size
            axis_direction = 'horizontal'
            anchor = 'n'
        elif axis == 'y':
            num_visible_labels = 5  # Desired number of labels in the visible area
            actual_start = self.coords(self.canvas_image)[1]
            canvas_size = self.x_axis_y - 10
            image_size = self.section_image.height()
            axis_pos = self.y_axis_x - 5
            labels = self.y_labels
            if self.tf.topo_corrected:
                min_height = min(self.height_profile)
                max_height = max(self.height_profile)
                total_depth_meters = self.section.depth_m + max_height - min_height
            else:
                total_depth_meters = self.section.depth_m
            pixel_to_unit_ratio = total_depth_meters / image_size
            axis_direction = 'vertical'
            anchor = 'e'
        elif axis == 'secondary_y':
            num_visible_labels = 5  # Desired number of labels in the visible area
            actual_start = self.coords(self.canvas_image)[1]
            canvas_size = self.x_axis_y - 10
            image_size = self.section_image.height()
            axis_pos = self.secondary_y_axis_x + 5
            labels = self.secondary_y_labels
            if self.tf.topo_corrected:
                min_height = min(self.height_profile)
                max_height = max(self.height_profile)
                total_depth_meters = self.section.depth_m + max_height - min_height
            else:
                total_depth_meters = self.section.depth_m
            pixel_to_unit_ratio = total_depth_meters / image_size
            axis_direction = 'vertical'
            anchor = 'w'

        visible_pixels = min(canvas_size - max(actual_start, 0), image_size)
        label_interval_pixels = visible_pixels / (num_visible_labels - 1)
        total_labels_needed = int(image_size / label_interval_pixels) + 2

        self.ensure_labels_count(labels, total_labels_needed, axis_pos, anchor)
        self.update_label_positions_and_texts(labels, total_labels_needed, actual_start, label_interval_pixels,
                                              pixel_to_unit_ratio, axis_pos, axis_direction)
        self.remove_excess_labels(labels, total_labels_needed)
        self.raise_labels(labels)

    def ensure_labels_count(self, labels, total_labels_needed, axis_pos, anchor):
        while len(labels) < total_labels_needed:
            label = self.create_text(axis_pos, 0, text="", anchor=anchor)
            labels.append(label)

    def update_label_positions_and_texts(self, labels, total_labels_needed, actual_start, label_interval_pixels,
                                         pixel_to_unit_ratio, axis_pos, axis_direction):
        for i in range(total_labels_needed):
            label_pos = actual_start + i * label_interval_pixels
            label_text = f"{i * label_interval_pixels * pixel_to_unit_ratio:.1f}"

            if axis_direction == 'horizontal':
                self.coords(labels[i], label_pos, axis_pos)
            else:
                if self.tf.topo_corrected and axis_direction == 'vertical':
                    max_height = max(self.height_profile)
                    label_text = f"{max_height - i * label_interval_pixels * pixel_to_unit_ratio:.1f}"
                self.coords(labels[i], axis_pos, label_pos)
            self.itemconfig(labels[i], text=label_text)

    def remove_excess_labels(self, labels, total_labels_needed):
        for i in range(len(labels) - 1, total_labels_needed - 1, -1):
            self.delete(labels.pop(i))

    def raise_labels(self, labels):
        for label in labels:
            self.tag_raise(label)

    def update_label_positions(self):
        for i, label in enumerate(self.additional_labels):
            tag = self.gettags(label)[0]
            if tag == 'dist_label':
                distance_label_x = int((self.y_axis_x + self.secondary_y_axis_x) / 2)
                distance_label_y = self.x_axis_y + 25  # adjust the y-coordinate for the depth label as needed
                self.coords(label, distance_label_x, distance_label_y)

            elif tag == 'depth_label':
                depth_label_x = self.y_axis_x - 40
                depth_label_y = int((10 + self.x_axis_y) / 2)
                self.coords(label, depth_label_x, depth_label_y)

            elif tag == 'sec_depth_label':
                depth_label_x = self.secondary_y_axis_x + 40
                depth_label_y = int((10 + self.x_axis_y) / 2)
                self.coords(label, depth_label_x, depth_label_y)

        for label in self.additional_labels:
            self.tag_raise(label)

    def is_cursor_on_image(self):
        """
        Check if the cursor is on the image canvas.
        """
        mouse_x, mouse_y = self.winfo_pointerxy()
        canvas_x = self.canvasx(mouse_x - self.winfo_rootx())
        canvas_y = self.canvasy(mouse_y - self.winfo_rooty())

        current_image_pos = self.coords(self.canvas_image)
        image_left, image_top = current_image_pos[0], current_image_pos[1]
        image_right = image_left + self.section_image.width()
        image_bottom = image_top + self.section_image.height()

        return image_left <= canvas_x <= image_right and image_top <= canvas_y <= image_bottom


class FakeEvent:
    def __init__(self, x, y):
        self.x = x
        self.y = y
