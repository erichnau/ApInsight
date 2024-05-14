import tkinter as tk
from tkinter import messagebox, filedialog, PhotoImage
import matplotlib.pyplot as plt
from PIL import Image, ImageTk
import os
from screeninfo import get_monitors
import numpy as np
import platform

from config_manager import ConfigurationManager
from GUI.CoordinatesLabel import CoordinatesLabel

monitors = get_monitors()
screen_res_primary = [monitors[0].height, monitors[0].width]

global window_width, window_height
window_width = int(screen_res_primary[1]*1)
window_height = int(screen_res_primary[0]*0.50)

class SectionView(tk.Toplevel):
    def __init__(self, section, depth_m, dist, project_file_path, sampling_interval, dtm_files, section_coor, pixelsize_z, frame_image, frame_left, top_frame, data_type, top_removed, bottom_removed, depth_table, frame_right):
        super().__init__()
        self.section = section

        self.title("Section View")
        if platform.system() =='Windows':
            self.iconbitmap('icon2.ico')
        else:
            icon_image = PhotoImage(file='icon2.png')
            self.iconphoto(True, icon_image)

        self.geometry("%dx%d+0+0" % (window_width, window_height))
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cleanup)

        self.config_manager = ConfigurationManager('config.ini')

        self.frame_image = frame_image
        self.frame_left = frame_left
        self.top_frame = top_frame
        self.frame_right = frame_right

        self.image_path = None
        self.height_profile = None
        self.depth_m = depth_m
        self.dist = dist
        self.project_file_path = project_file_path
        self.sampling_interval = sampling_interval
        self.dtm_files = dtm_files
        self.section_coor = section_coor
        self.pixelsize_z = pixelsize_z
        self.data_type = data_type
        self.file_name = self.frame_left.active_file_name
        self.top_removed = top_removed
        self.bottom_removed = bottom_removed
        self.depth_table = depth_table

        self.vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        self.vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))
        self.initial_window_size=False

        self.zoom_level = 1  # Track zoom level
        self.init_image_position = (0, 0)  # Initial image position

        self.x_axis = None
        self.mask_tag = None
        self.pan_offset_x = 0
        self.pan_offset_y = 0

        self.create_widgets()
        self.coordinates_label = CoordinatesLabel(self.section_canvas)
        self.create_temporary_folder()

        self.create_image_from_section()
        self.display_section(self.image_path)

    def create_widgets(self):
        # Create a top frame with buttons
        self.top_frame_section_window = tk.Frame(self)
        self.top_frame_section_window.pack(side="top", fill="x")

        # Add buttons or other widgets as needed
        # For example:
        save_button = tk.Button(self.top_frame_section_window, text="Export image", command=self.save_section)
        save_button.pack(side="left", padx=5, pady=5)

        topo_correction = tk.Button(self.top_frame_section_window, text='Add topography', command=self.add_topography)
        topo_correction.pack(side='left', padx=5, pady=5)

        clear_topo = tk.Button(self.top_frame_section_window, text='Clear topography', command=self.clear_topography)
        clear_topo.pack(side='left', padx=5, pady=5)

        # Create check buttons for drawing lines and communication
        self.draw_y_line_var = tk.BooleanVar(value=True)
        self.draw_x_line_var = tk.BooleanVar(value=True)
        self.communication_var = tk.BooleanVar(value=True)

        draw_x_line_checkbox = tk.Checkbutton(self.top_frame_section_window, text="Draw X Line", variable=self.draw_y_line_var)
        draw_x_line_checkbox.pack(side="left", padx=5, pady=5)

        draw_y_line_checkbox = tk.Checkbutton(self.top_frame_section_window, text="Draw Y Line", variable=self.draw_x_line_var)
        draw_y_line_checkbox.pack(side="left", padx=5, pady=5)

        communication_checkbox = tk.Checkbutton(self.top_frame_section_window, text="Enable Communication", variable=self.communication_var)
        communication_checkbox.pack(side="left", padx=5, pady=5)

        greyscale_frame = tk.Frame(self.top_frame_section_window, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        greyscale_frame.pack(side= 'left', padx=10, pady=5)

        greyscale_label = tk.Label(greyscale_frame, text='Greyscale range')
        greyscale_label.pack()

        # vmin entry and arrow buttons
        self.vmin_var = tk.IntVar(value=self.vmin)  # Assuming self.vmin is defined
        vmin_entry = tk.Entry(greyscale_frame, width=4, textvariable=self.vmin_var)
        vmin_entry.pack(side="left")
        vmin_up_button = tk.Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmin(1))
        vmin_up_button.pack(side="left")
        vmin_down_button = tk.Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmin(-1))
        vmin_down_button.pack(side="left")

        # vmax entry and arrow buttons
        self.vmax_var = tk.IntVar(value=self.vmax)  # Assuming self.vmax is defined
        vmax_entry = tk.Entry(greyscale_frame, width=4, textvariable=self.vmax_var)
        vmax_entry.pack(side="left")
        vmax_up_button = tk.Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmax(1))
        vmax_up_button.pack(side="left")
        vmax_down_button = tk.Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmax(-1))
        vmax_down_button.pack(side="left")

        default_button = tk.Button(greyscale_frame, text="Default", command=self.reset_to_default_greyscale)
        default_button.pack(side='left', padx=5, pady=5)

        # Bind entry updates
        vmin_entry.bind('<Return>', self.update_vmin_vmax)
        vmax_entry.bind('<Return>', self.update_vmin_vmax)

        # Calculate the size of the image frame
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        frame_width = int(window_width * 0.8)
        frame_height = int(window_height * 0.8)

        # Create an image frame with a canvas and a border
        image_frame = tk.Frame(self, width=frame_width, height=frame_height, relief="solid", borderwidth=1)
        image_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.pack_propagate(True)

        self.section_canvas = tk.Canvas(image_frame, bg="white")
        self.section_canvas.pack(fill="both", expand=True)

        self.y_labels = []  # list to store y-axis labels
        self.x_labels = []  # list to store x-axis labels
        self.secondary_y_labels = []
        self.additional_labels = []

        if 'DTMfromGPR' in self.file_name:
            topo_correction.config(state='disabled')
            clear_topo.config(state='disabled')

        self.create_zoom_controls()

    def create_zoom_controls(self):
        zoom_in_button = tk.Button(self.top_frame_section_window, text="+", command=self.zoom_in)
        zoom_in_button.pack(side="left", padx=5, pady=5)
        zoom_out_button = tk.Button(self.top_frame_section_window, text="-", command=self.zoom_out)
        zoom_out_button.pack(side="left", padx=5, pady=5)
        # Bind right-click drag for panning
        self.section_canvas.bind("<Button-3>", self.start_pan)
        self.section_canvas.bind("<B3-Motion>", self.pan_image)

    def start_pan(self, event):
        self.init_image_position = (event.x, event.y)  # Capture initial position

    def pan_image(self, event):
        dx = (event.x - self.init_image_position[0])
        dy = (event.y - self.init_image_position[1])

        self.pan_offset_x += dx
        self.pan_offset_y += dy

        actual_image_width = self.section_image.width()
        actual_image_height = self.section_image.height()

        current_pos = self.section_canvas.coords(self.canvas_image)
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

        self.section_canvas.move(self.canvas_image, dx, dy)
        self.init_image_position = (event.x, event.y)
        self.update_axes_based_on_pan(dx, dy)

    def update_axes_based_on_pan(self, dx, dy):
        # Adjust the x-axis labels based on the image movement, skip the last label
        for label in self.x_labels[:-1]:  # The '[:-1]' slice selects all but the last item
            self.section_canvas.move(label, dx, 0)

        # Adjust the y-axis labels based on the image movement, skip the last label
        for label in self.y_labels[:-1]:  # Similarly, '[:-1]' skips the last item
            self.section_canvas.move(label, 0, dy)

        # Do the same for secondary y-axis labels if present, skip the last label
        for label in self.secondary_y_labels[:-1]:
            self.section_canvas.move(label, 0, dy)

    def zoom_in(self, cursor_position=None):
        # Get the current center of the viewport or cursor position
        if cursor_position is None:
            viewport_center_x = self.section_canvas.canvasx(self.section_canvas.winfo_width() / 2)
            viewport_center_y = self.section_canvas.canvasy(self.section_canvas.winfo_height() / 2)
        else:
            viewport_center_x, viewport_center_y = cursor_position

        # Calculate the new dimensions
        new_width = int(self.section_image.width() * 1.1)
        new_height = int(self.section_image.height() * 1.1)

        self.zoom *= 1.1

        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        self.section_image = ImageTk.PhotoImage(resized_image)

        # Calculate the new position based on the zoom center
        current_pos = self.section_canvas.coords(self.canvas_image)
        new_x = viewport_center_x - (viewport_center_x - current_pos[0]) * 1.1
        new_y = viewport_center_y - (viewport_center_y - current_pos[1]) * 1.1

        # Apply boundary constraints
        new_x = min(max(new_x, self.secondary_y_axis_x - new_width), self.image_left_bound)
        new_y = min(max(new_y, self.x_axis_y - new_height), self.image_top_bound)

        # Update the image position and zoom
        self.section_canvas.itemconfig(self.canvas_image, image=self.section_image)
        self.section_canvas.coords(self.canvas_image, new_x, new_y)

        self.adjust_window_size(zoom=True)
        self.update_axes_after_zoom()

        fake_event = FakeEvent(viewport_center_x, viewport_center_y)
        self.pan_image(fake_event)

    def zoom_out(self, cursor_position=None):
        # Get the current center of the viewport or cursor position
        if cursor_position is None:
            viewport_center_x = self.section_canvas.canvasx(self.section_canvas.winfo_width() / 2)
            viewport_center_y = self.section_canvas.canvasy(self.section_canvas.winfo_height() / 2)
        else:
            viewport_center_x, viewport_center_y = cursor_position

        self.zoom /= 1.1

        # Calculate the new dimensions, ensuring they do not fall below the actual initial dimensions
        new_width = max(int(self.section_image.width() / 1.1), self.actual_image_width)
        new_height = max(int(self.section_image.height() / 1.1), self.actual_image_height)

        if new_width == self.actual_image_width:
            self.zoom = self.init_zoom

        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        self.section_image = ImageTk.PhotoImage(resized_image)

        # Calculate the new position to maintain the zoom center
        current_pos = self.section_canvas.coords(self.canvas_image)
        shift_x = (self.section_image.width() - new_width) / 2
        shift_y = (self.section_image.height() - new_height) / 2
        new_x = viewport_center_x - (viewport_center_x - current_pos[0]) * (1 / 1.1)
        new_y = viewport_center_y - (viewport_center_y - current_pos[1]) * (1 / 1.1)

        # Apply boundary constraints
        new_x = min(max(new_x, self.secondary_y_axis_x - new_width), self.image_left_bound)
        new_y = min(max(new_y, self.x_axis_y - new_height), self.image_top_bound)

        # Update the image position and zoom
        self.section_canvas.itemconfig(self.canvas_image, image=self.section_image)
        self.section_canvas.coords(self.canvas_image, new_x, new_y)

        self.adjust_window_size(zoom=True)
        self.update_axes_after_zoom()

        fake_event = FakeEvent(viewport_center_x, viewport_center_y)
        self.pan_image(fake_event)


    def update_axes_after_zoom(self):
        # Get the current canvas (or window) height and width
        canvas_width = self.section_canvas.winfo_width()
        canvas_height = self.section_canvas.winfo_height()

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
        self.section_canvas.coords(self.x_axis, self.y_axis_x, self.x_axis_y, self.secondary_y_axis_x, self.x_axis_y)
        self.section_canvas.coords(self.y_axis, self.y_axis_x, 10, self.y_axis_x, self.x_axis_y)
        self.section_canvas.coords(self.secondary_y_axis, self.secondary_y_axis_x, 10, self.secondary_y_axis_x,
                                   self.x_axis_y)

        # Recreate masks to fit the new dimensions
        self.create_masks()
        self.update_x_labels_for_full_image()
        self.update_y_labels_for_full_image(primary=True)
        self.update_y_labels_for_full_image(primary=False)
        self.update_label_positions()

    def update_x_labels_for_full_image(self):
        num_visible_labels = 5  # Number of labels always visible in the viewport

        # Calculate the visible width in pixels
        actual_x0 = self.section_canvas.coords(self.canvas_image)[0]
        canvas_width = self.section_canvas.winfo_width()
        visible_width_pixels = min(canvas_width - max(actual_x0, 0), self.section_image.width())

        # The ratio of pixels to meters for the full image
        pixel_to_meter_ratio = self.dist / self.section_image.width()

        # Calculate the interval in meters between labels for the visible part
        label_interval_pixels = visible_width_pixels / (num_visible_labels - 1)

        # Total number of labels needed for the entire image, based on the same interval
        total_labels_needed = int(self.section_image.width() / label_interval_pixels) + 2

        # Ensure there are enough labels, create more if needed
        while len(self.x_labels) < total_labels_needed:
            label = self.section_canvas.create_text(0, self.x_axis_y + 10, text="", anchor='n')
            self.x_labels.append(label)

        # Update positions and texts of all labels for the entire image width
        for i in range(total_labels_needed):
            label_x = actual_x0 + i * label_interval_pixels
            label_text = f"{i * label_interval_pixels * pixel_to_meter_ratio:.1f}"
            self.section_canvas.coords(self.x_labels[i], label_x, self.x_axis_y + 10)
            self.section_canvas.itemconfig(self.x_labels[i], text=label_text)

        # Remove excess labels if necessary
        for i in range(len(self.x_labels) - 1, total_labels_needed - 1, -1):
            self.section_canvas.delete(self.x_labels.pop(i))

        # Ensure all labels are raised to be visible
        for label in self.x_labels:
            self.section_canvas.tag_raise(label)

    def update_y_labels_for_full_image(self, primary=True):
        num_visible_labels = 5  # Desired number of labels in the visible area

        # Determine the visible height in pixels and calculate depth parameters
        visible_height_pixels = self.x_axis_y - 10
        total_height_pixels = self.section_image.height()

        actual_y0 = self.section_canvas.coords(self.canvas_image)[1]

        if self.topo_corrected:
            min_height = min(self.height_profile)
            max_height = max(self.height_profile)
            total_depth_meters = self.depth_m + max_height - min_height
        else:
            total_depth_meters = self.depth_m

        depth_per_pixel = total_depth_meters / total_height_pixels
        visible_depth_meters = visible_height_pixels * depth_per_pixel
        label_interval_meters = visible_depth_meters / (num_visible_labels - 1)
        total_labels_needed = int(total_height_pixels / (label_interval_meters / depth_per_pixel)) + 2

        # Choose which label list and axis position to use based on the 'primary' parameter
        labels = self.y_labels if primary else self.secondary_y_labels
        axis_x_position = self.y_axis_x - 5 if primary else self.secondary_y_axis_x + 5
        anchor = 'e' if primary else 'w'

        # Ensure there are enough labels
        while len(labels) < total_labels_needed:
            label = self.section_canvas.create_text(axis_x_position, 0, text="", anchor=anchor)
            labels.append(label)

        # Update positions and texts of all labels for the entire image height
        for i in range(total_labels_needed):
            label_y = actual_y0 + i * (label_interval_meters / depth_per_pixel)
            if self.topo_corrected:
                # For topo_corrected, calculate label based on elevation differences
                label_text = f"{max_height - i * label_interval_meters:.1f}"
            else:
                # Regular depth labels
                label_text = f"{i * label_interval_meters:.1f}"

            self.section_canvas.coords(labels[i], axis_x_position, label_y)
            self.section_canvas.itemconfig(labels[i], text=label_text)

        # Remove excess labels if necessary
        for i in range(len(labels) - 1, total_labels_needed - 1, -1):
            self.section_canvas.delete(labels.pop(i))

        # Raise all labels to ensure they are visible
        for label in labels:
            self.section_canvas.tag_raise(label)

    def update_label_positions(self):
        for i, label in enumerate(self.additional_labels):
            tag = self.section_canvas.gettags(label)[0]
            if tag == 'dist_label':
                distance_label_x = int((self.y_axis_x + self.secondary_y_axis_x) / 2)
                distance_label_y = self.x_axis_y + 25  # adjust the y-coordinate for the depth label as needed
                self.section_canvas.coords(label, distance_label_x, distance_label_y)

            elif tag == 'depth_label':
                depth_label_x = self.y_axis_x - 40
                depth_label_y = int((10 + self.x_axis_y) / 2)
                self.section_canvas.coords(label, depth_label_x, depth_label_y)

            elif tag == 'sec_depth_label':
                depth_label_x = self.secondary_y_axis_x + 40
                depth_label_y = int((10 + self.x_axis_y) / 2)
                self.section_canvas.coords(label, depth_label_x, depth_label_y)

        for label in self.additional_labels:
            self.section_canvas.tag_raise(label)

    def adjust_vmin(self, adjustment):
        new_vmin = self.vmin + adjustment
        if new_vmin < self.vmax:
            self.vmin = new_vmin
            self.vmin_var.set(int(self.vmin))
            self.regenerate_and_refresh_image()
        else:
            self.show_error_message("Invalid Adjustment", "vmin cannot be equal or greater than vmax.")

    def adjust_vmax(self, adjustment):
        new_vmax = self.vmax + adjustment
        if new_vmax > self.vmin:
            self.vmax = new_vmax
            self.vmax_var.set(int(self.vmax))
            self.regenerate_and_refresh_image()
        else:
            self.show_error_message("Invalid Adjustment", "vmax cannot be equal or less than vmin.")

    def update_vmin_vmax(self, event=None):
        try:
            vmin = int(self.vmin_var.get())
            vmax = int(self.vmax_var.get())

            if vmin < vmax:
                self.vmin = vmin
                self.vmax = vmax
                self.regenerate_and_refresh_image()
            else:
                self.show_error_message("Invalid Input", "Ensure that vmin is less than vmax.")
        except ValueError:
            self.show_error_message("Invalid Input", "Please enter numeric values for vmin and vmax.")

    def show_error_message(self, title, message):
        messagebox.showerror(title, message)
        self.focus_set()  # Set the focus back to the SectionView window
        self.lift()  # Bring the SectionView window to the front

    def regenerate_and_refresh_image(self):
        # Regenerate the image with the new vmin and vmax values
        if self.topo_corrected:
            self.save_topo_corrected_section()
        else:
            self.create_image_from_section()
            self.display_section(self.image_path, top_corr=self.topo_corrected, update_vmin_vmax=True)

    def reset_to_default_greyscale(self):
        # Retrieve vmin and vmax values from the configuration file
        default_vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        default_vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        # Update the entry widgets with default values
        self.vmin_var.set(default_vmin)
        self.vmax_var.set(default_vmax)

        self.update_vmin_vmax()

    def cleanup(self):
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

    def create_temporary_folder(self):
        # Get the directory and base name of the JSON file
        json_file_path = self.project_file_path
        json_dir = os.path.dirname(json_file_path)
        json_basename = os.path.basename(json_file_path)
        json_name, _ = os.path.splitext(json_basename)

        # Create a temporary folder path
        self.temp_folder_path = os.path.join(json_dir, json_name + "_temp")

        # Create the temporary folder if it doesn't exist
        os.makedirs(self.temp_folder_path, exist_ok=True)


    def display_section(self, image_path, top_corr=False, update_vmin_vmax=False, clear_topo=False):
        self.image = Image.open(image_path)
        self.section_image = ImageTk.PhotoImage(self.image)

        self.canvas_image = self.section_canvas.create_image(0, 0, anchor='nw', image=self.section_image)

        # Configure canvas scrollregion and update
        self.section_canvas.configure(scrollregion=self.section_canvas.bbox('all'))
        self.section_canvas.update()

        # Resize the image and update axes
        if not update_vmin_vmax:
            if top_corr:
                self.resize_image_to_canvas(top_corr=True)
                self.topo_corrected = True
            else:
                if clear_topo:
                    self.resize_image_to_canvas(clear_topo=True)
                    self.topo_corrected = False
                else:
                    self.resize_image_to_canvas()
                    self.topo_corrected = False
        else:
            if top_corr:
                self.resize_image_to_canvas(top_corr=True, update_vmin_vmax=True)
                self.topo_corrected = True
            else:
                self.resize_image_to_canvas(update_vmin_vmax=True)
                self.topo_corrected = False


    def resize_image_to_canvas(self, top_corr=False, update_vmin_vmax=False, clear_topo=False):
        # Get the size of the canvas and the scaled image
        canvas_width = self.section_canvas.winfo_width()
        canvas_height = self.section_canvas.winfo_height()
        image_width = self.section_image.width()
        image_height = self.section_image.height()

        # Calculate the available space for the image (canvas size minus axis)
        available_width = canvas_width - 120  # adjust based on the axis width
        available_height = canvas_height - 70  # adjust based on the axis height

        # Calculate the zoom level to fit the image in the available width and height
        zoom_x = available_width / image_width
        zoom_y = available_height / image_height

        if top_corr:
            # Calculate the required canvas height to accommodate the corrected section
            required_canvas_height = image_height + 70  # Account for axis height

            # Adjust the canvas height if necessary
            if required_canvas_height > canvas_height:
                self.section_canvas.config(height=required_canvas_height)

            self.resized_width = int(image_width * self.zoom)
            self.resized_height = int(image_height * self.zoom)

            self.resized_height_topo = self.resized_height
            resize_factor = self.resized_height_topo/self.image_height_orig

            resized_image = self.image.resize((self.resized_width, self.resized_height), Image.LANCZOS)
            resized_image.save(self.temp_folder_path + 'resized_topo_image.png')

            if not update_vmin_vmax:
                self.adjust_window_size()
        else:
            # Use the smaller of zoom_x and zoom_y for standard section
            self.zoom = min(zoom_x, zoom_y)
            self.init_zoom = self.zoom

            # Resize the image
            self.resized_width = int(image_width * self.zoom)
            self.resized_height = int(image_height * self.zoom)
            self.image_height_orig = self.resized_height

            resized_image = self.image.resize((self.resized_width, self.resized_height), Image.LANCZOS)
            resized_image.save(self.temp_folder_path + 'resized_image.png')

            if not update_vmin_vmax and not clear_topo:
                self.adjust_window_size()
                if not clear_topo:
                    self.orig_window_width = self.winfo_width()
                    self.orig_window_height = self.winfo_height()
            elif clear_topo:
                self.adjust_window_size(clear_topo=True)

        # Calculate the position to place the image (accounting for the axis)
        x_offset = 50  # adjust based on the axis width
        y_offset = 0  # adjust based on the axis height

        # Update the section image on the canvas
        self.section_image = ImageTk.PhotoImage(resized_image)
        self.section_canvas.itemconfig(self.canvas_image, image=self.section_image)
        self.section_canvas.coords(self.canvas_image, x_offset + 1, y_offset + 10)

        # Configure canvas scrollregion and update
        self.section_canvas.configure(scrollregion=self.section_canvas.bbox('all'))
        self.section_canvas.update_idletasks()

        if top_corr:
            self.update_axes(top_corr=True)
        else:
            self.update_axes()

        self.section_canvas.bind('<Motion>', self.draw_lines)

        self.init_image_pos = self.section_canvas.coords(self.canvas_image)

        self.actual_image_width = self.section_image.width()
        self.actual_image_height = self.section_image.height()

        self.image_left_bound = self.init_image_pos[0]
        self.image_right_bound = self.image_left_bound + self.actual_image_width
        self.image_top_bound = self.init_image_pos[1]
        self.image_bottom_bound = self.image_top_bound + self.actual_image_height


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


    def adjust_window_size(self, clear_topo=False, zoom=False):
        top_frame_width = self.calculate_frame_width(self.top_frame_section_window) + 50

        # Determine the width for the section image
        image_frame_width = self.resized_width + 200

        # Set the window width to the maximum of the two widths
        window_width = max(top_frame_width, image_frame_width)
        window_height = self.resized_height + 200

        if clear_topo:
            window_width = min(window_width, int(screen_res_primary[1]*1))
            self.geometry(f"{window_width}x{self.orig_window_height}")

        elif zoom:
            # Calculate maximum allowable dimensions
            max_width = int(screen_res_primary[1] * 1)
            max_height = int(screen_res_primary[0] * 0.55)

            current_image_width = self.section_image.width()
            current_image_height = self.section_image.height()

            # Determine the width for the section image including some padding
            image_frame_width = current_image_width + 200
            image_frame_height = current_image_height + 200

            # Calculate the total width and height required by the window
            top_frame_width = self.calculate_frame_width(self.top_frame_section_window) + 50
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

    def update_axes(self, top_corr=False):
        if self.x_axis is not None:
            self.section_canvas.delete(self.x_axis)
            self.section_canvas.delete(self.y_axis)
            self.section_canvas.delete(self.secondary_y_axis)

        self.x_axis = self.section_canvas.create_line(0, 0, 0, 0, fill='black', width=2)  # x-axis line
        self.y_axis = self.section_canvas.create_line(0, 0, 0, 0, fill='black', width=2)  # y-axis line
        self.secondary_y_axis = self.section_canvas.create_line(0, 0, 0, 0, fill='black', width=2)  # y-axis line

        # Calculate the positions for the x-axis and y-axis lines
        self.x_axis_y = self.section_image.height() + 12
        self.y_axis_x = 50  # adjust the x-coordinate for y-axis line as needed
        self.secondary_y_axis_x = self.section_image.width() + self.y_axis_x + 2

        self.create_masks()

        # Update the x-axis line
        self.section_canvas.coords(self.x_axis, self.y_axis_x, self.x_axis_y, self.secondary_y_axis_x, self.x_axis_y)

        # Update the y-axis line
        self.section_canvas.coords(self.y_axis, self.y_axis_x, 10, self.y_axis_x, self.x_axis_y)

        self.section_canvas.coords(self.secondary_y_axis, self.secondary_y_axis_x, 10, self.secondary_y_axis_x, self.x_axis_y)

        # Remove existing x-axis labels
        for label in self.x_labels:
            self.section_canvas.delete(label)
        self.x_labels = []  # list to store x-axis labels

        # Remove existing y-axis labels
        for label in self.y_labels:
            self.section_canvas.delete(label)
        self.y_labels = []  # list to store y-axis labels

        # Remove existing secondary y-axis labels
        for label in self.secondary_y_labels:
            self.section_canvas.delete(label)
        self.secondary_y_labels = []

        for label in self.additional_labels:
            self.section_canvas.delete(label)
        self.additional_labels = []

        # Calculate the depth and distance tick values
        if top_corr:
            # Calculate the number of depth ticks based on height profile length
            min_height = min(self.height_profile)
            max_height = max(self.height_profile)

            min_depth = min_height - self.depth_m

            num_depth_ticks = 5  # Adjust the number of ticks as needed
            height_ticks = np.linspace(max(self.height_profile), min(self.height_profile) - self.depth_m,
                                           num=num_depth_ticks)

            # Convert height ticks to depth based on height profile
            self.depth_ticks = max(self.height_profile) - height_ticks

            self.min_depth_new = min_depth
            self.max_depth_new = max_height
            self.depth_ticks = np.linspace(self.max_depth_new, self.min_depth_new, num=5)

        elif 'DTMfromGPR' in self.file_name:
            # Use the max and min depths from the frame_image
            min_depth = round((self.frame_left.min_depth/100), 2)
            max_depth = round((self.frame_left.max_depth/100), 2)

            self.min_depth_new = min_depth + self.bottom_removed*self.pixelsize_z
            self.max_depth_new = max_depth - self.top_removed*self.pixelsize_z

            # Calculate the depth ticks using max and min depths
            self.depth_ticks = np.linspace(self.max_depth_new, self.min_depth_new, num=5)

        else:
            self.depth_ticks = np.linspace(0, self.depth_m, num=5)

        distance_ticks = np.linspace(0, self.dist, num=5)  # Adjust the number of ticks as needed

        # Add new y-axis labels
        y_label_interval = (self.x_axis_y - 10) / (len(self.depth_ticks) - 1)
        for i, depth in enumerate(self.depth_ticks):
            label_y = 10 + i * y_label_interval

            if 'DTMfromGPR' in self.file_name:
                # Use depth value directly for DTMfromGPR case
                label_text = f"{depth:.1f}"
            elif top_corr:
                label_text = f"{depth:.1f}"
            else:
                label_text = f"{depth:.1f}"  # Use regular depth value for standard section

            label = self.section_canvas.create_text(self.y_axis_x - 5, label_y, anchor='e', text=label_text, tags='label_y')
            self.y_labels.append(label)

            secondary_label = self.section_canvas.create_text(self.secondary_y_axis_x + 5, label_y, anchor='w',
                                                                  text=str(label_text), tags='label_y')
            self.secondary_y_labels.append(secondary_label)

        # Add new x-axis labels
        x_label_interval = (self.secondary_y_axis_x - self.y_axis_x) / (len(distance_ticks) - 1)
        for i, distance in enumerate(distance_ticks):
            label_x = self.y_axis_x + i * x_label_interval
            label_text = f"{distance:.1f}"  # Format the distance value as needed
            label = self.section_canvas.create_text(label_x, self.x_axis_y + 10, anchor='n', text=label_text, tags='label_x')
            self.x_labels.append(label)

        self.init_y_x_labels = self.x_axis_y+10

        # Add distance label
        distance_label_x = int((self.y_axis_x + self.secondary_y_axis_x) / 2)
        distance_label_y = self.x_axis_y + 25  # adjust the y-coordinate for the depth label as needed
        distance_label = self.section_canvas.create_text(distance_label_x, distance_label_y, anchor='n',
                                                         text='Distance (m)', font=("Arial", 11, "bold"), tags='dist_label')
        self.additional_labels.append(distance_label)

        if 'DTMfromGPR' in self.file_name:
            # Add depth label
            depth_label_x = self.y_axis_x - 40
            depth_label_y = int((10 + self.x_axis_y) / 2)
        elif top_corr:
            # Add depth label
            depth_label_x = self.y_axis_x - 40
            depth_label_y = int((10 + self.x_axis_y) / 2)
        else:
            # Add depth label
            depth_label_x = self.y_axis_x - 35
            depth_label_y = int((10 + self.x_axis_y) / 2)

        if top_corr:
            depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        elif 'DTMfromGPR' in self.file_name:
            depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        else:
            depth_label_text = 'Depth (m)'  # Use regular label text for standard section

        depth_label = self.section_canvas.create_text(depth_label_x, depth_label_y, anchor='e',
                                                      text=depth_label_text, angle=90,
                                                      font=("Arial", 11, "bold"), tags='depth_label')
        self.additional_labels.append(depth_label)


        if 'DTMfromGPR' in self.file_name:
            # Add secondary depth label
            secondary_depth_label_x = self.secondary_y_axis_x + 40  # adjust the x-coordinate for the secondary depth label as needed
            secondary_depth_label_y = int((10 + self.x_axis_y) / 2)
        elif top_corr:
            secondary_depth_label_x = self.secondary_y_axis_x + 40  # adjust the x-coordinate for the secondary depth label as needed
            secondary_depth_label_y = int((10 + self.x_axis_y) / 2)
        else:
            secondary_depth_label_x = self.secondary_y_axis_x + 35  # adjust the x-coordinate for the secondary depth label as needed
            secondary_depth_label_y = int((10 + self.x_axis_y) / 2)

        if top_corr:
            secondary_depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        elif 'DTMfromGPR' in self.file_name:
            secondary_depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        else:
            secondary_depth_label_text = 'Depth (m)'  # Use regular label text for standard section

        secondary_depth_label = self.section_canvas.create_text(secondary_depth_label_x, secondary_depth_label_y,
                                                                anchor='e', text=secondary_depth_label_text, angle=90,
                                                                font=("Arial", 11, "bold"), tags='sec_depth_label')
        self.additional_labels.append(secondary_depth_label)

    def create_masks(self):
        # Assuming self.canvas is your Tkinter Canvas instance
        canvas_width = self.section_canvas.winfo_width()
        canvas_height = self.section_canvas.winfo_height()

        if self.mask_tag is not None:
            self.section_canvas.delete("mask")

        # Color to match the background or any color that indicates a non-visible area
        mask_color = 'white'
        self.mask_tag = 'mask'

        # Top mask
        self.section_canvas.create_rectangle(-100, -100, canvas_width + 100, 10, fill=mask_color, outline=mask_color,
                                             tags=self.mask_tag)

        # Bottom mask
        self.section_canvas.create_rectangle(-100, self.x_axis_y + 1, canvas_width + 100, canvas_height + 100,
                                             fill=mask_color,
                                             outline=mask_color, tags=self.mask_tag)

        # Left mask
        self.section_canvas.create_rectangle(-100, -100, self.y_axis_x - 2, canvas_height + 100, fill=mask_color,
                                             outline=mask_color, tags=self.mask_tag)

        # Right mask
        self.section_canvas.create_rectangle(self.secondary_y_axis_x + 1, -100, canvas_width + 100, canvas_height + 100,
                                             fill=mask_color,
                                             outline=mask_color, tags=self.mask_tag)

    def draw_lines(self, event):
        x, y = event.x, event.y

        # Get the current image position on the canvas
        current_image_pos = self.section_canvas.coords(self.canvas_image)
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

        #print('Image right and bottom: ', image_right, image_bottom)

        # Check if the cursor is within the visible part of the image
        if image_left <= x <= image_right and image_top <= y <= image_bottom:
            # Clear any previously drawn lines
            self.section_canvas.delete('x_line')
            self.section_canvas.delete('y_line')
            self.section_canvas.delete('height_profile_line')

            # Draw vertical line
            if self.draw_x_line_var.get():
                self.section_canvas.create_line(x, max(image_top, 0), x,
                                                min(image_bottom, self.section_canvas.winfo_height()), tags='x_line')

            # Draw horizontal line or plot height profile
            if self.draw_y_line_var.get():
                if self.topo_corrected:
                    self.plot_height_profile(y, x)
                else:
                    self.section_canvas.create_line(max(image_left, 0), y,
                                                    min(image_right, self.section_canvas.winfo_width()), y,
                                                    tags='y_line')

            if self.communication_var.get():
                self.update_depthslice_canvas(x_data, y_data)

        else:
            # Cursor is outside the image bounds, remove any previously drawn lines
            self.section_canvas.delete('x_line')
            self.section_canvas.delete('y_line')
            self.section_canvas.delete('height_profile_line')


    def get_closest_indx_height_profile(self, x_data):
        # Get the image top left corner coordinates
        image_left, image_top = self.section_canvas.coords(self.canvas_image)[0:2]

        # Calculate the total length of the downsampled height profile in meters
        total_length_meters = len(self.downsampled_height_profile) * self.sampling_interval

        # Calculate the scaling factor for converting x_data to index in the height profile array
        self.scale_factor = self.section_image.width() / total_length_meters

        closest_index = int(round((x_data - image_left) / (self.sampling_interval * self.scale_factor)))

        return closest_index

    def plot_height_profile(self, y_data, x_data):
        # Clear any previous height profile lines
        self.section_canvas.delete('height_profile_line')

        # Get the image top left corner coordinates
        image_left, image_top = self.section_canvas.coords(self.canvas_image)[0:2]

        min_height = min(self.downsampled_height_profile)
        max_height = np.argmax(self.downsampled_height_profile)

        # Calculate the total length of the downsampled height profile in meters
        total_length_meters = len(self.downsampled_height_profile) * self.sampling_interval

        # Calculate the scaling factor for converting x_data to index in the height profile array
        self.scale_factor = self.section_image.width() / total_length_meters

        height_points = []

        closest_index = int(round((x_data - image_left) / (self.sampling_interval * self.scale_factor)))
        self.height = self.downsampled_height_profile[closest_index-1]

        # Calculate the y-coordinate offset for this height point based on the closest index
        y_offset = (y_data + (self.downsampled_height_profile[closest_index - 1] - min_height) * self.scale_factor)

        # Iterate over each height value and its index in the height profile
        for i, height in enumerate(self.downsampled_height_profile):
            # Calculate the x-coordinate for this height point
            x_coord = image_left + (i * self.sampling_interval) * self.scale_factor

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

            self.y_coord_max_point = abs(((image_top - 10) / self.zoom)) + ((y_offset) - (self.downsampled_height_profile[max_height] - min_height) * self.scale_factor) / self.zoom

            # Create a line using the visible height points without the index
        self.section_canvas.create_line([(x, y) for x, y, _ in visible_height_points], fill='black',
                                        tags='height_profile_line')


    def plot_height_profile_from_ds(self, y_data):
        # Clear any previous height profile lines
        self.section_canvas.delete('height_profile_line')

        # Get the image top left corner coordinates
        image_left, image_top = self.section_canvas.coords(self.canvas_image)[0:2]

        min_height = min(self.downsampled_height_profile)
        max_height = np.argmax(self.downsampled_height_profile)

        # Calculate the total length of the downsampled height profile in meters
        total_length_meters = len(self.downsampled_height_profile) * self.sampling_interval

        # Calculate the scaling factor for converting x_data to index in the height profile array
        self.scale_factor = self.section_image.width() / total_length_meters

        height_points = []

        closest_index = np.argmax(self.downsampled_height_profile) + 1

        # Calculate the y-coordinate offset for this height point based on the closest index
        y_offset = (y_data + (self.downsampled_height_profile[closest_index - 1] - min_height) * self.scale_factor)

        # Iterate over each height value and its index in the height profile
        for i, height in enumerate(self.downsampled_height_profile):
            # Calculate the x-coordinate for this height point
            x_coord = image_left + (i * self.sampling_interval) * self.scale_factor

            # Calculate the y-coordinate for this height point
            y_coord = y_offset - (height - min_height) * self.scale_factor

            # Append the calculated (x, y) point to the height_points list
            height_points.append((x_coord, y_coord, i))  # Include index

        # Filter height_points to only include those within the visible x bounds
        visible_height_points = [point for point in height_points if
                                 self.y_axis_x <= point[0] <= self.secondary_y_axis_x]

            # Create a line using the visible height points without the index
        self.section_canvas.create_line([(x, y) for x, y, _ in visible_height_points], fill='black',
                                        tags='height_profile_line')


    def get_xy_from_section_coor(self, x):
        section_start = self.section_coor[0]  # Start point of the section
        section_stop = self.section_coor[1]  # Stop point of the section
        x /= round(self.section.shape[1]/self.dist)
        # Calculate the total distance along the section
        section_distance = ((section_stop[0] - section_start[0]) ** 2 + (
                    section_stop[1] - section_start[1]) ** 2) ** 0.5

        # Calculate the ratio of the given x_data relative to the total distance
        ratio = x / section_distance

        # Interpolate the x and y coordinates along the section
        x = round(section_start[0] + (section_stop[0] - section_start[0]) * ratio, 3)
        y = round(section_start[1] + (section_stop[1] - section_start[1]) * ratio, 3)

        return x, y

    def get_section_coor_from_xy(self, x, y):
        section_start = self.section_coor[0]  # Start point of the section
        section_stop = self.section_coor[1]  # Stop point of the section

        # Calculate the total distance along the section
        section_distance = ((section_stop[0] - section_start[0]) ** 2 + (
                section_stop[1] - section_start[1]) ** 2) ** 0.5

        # Calculate the distance from the start of the section to the given xy point
        distance_to_xy = ((x - section_start[0]) ** 2 + (y - section_start[1]) ** 2) ** 0.5

        # Calculate the ratio of the distance to the total distance along the section
        ratio = distance_to_xy / section_distance

        # Interpolate the x and y coordinates along the section
        section_x = round(ratio * self.section.shape[1])

        return section_x

    def update_x_line(self, x, y, for_labels=False):
        x_offset = 50
        canvas_height = self.section_canvas.winfo_height()

        x_pos = self.get_section_coor_from_xy(x, y)
        adjusted_x = (x_pos * self.zoom) + self.section_canvas.coords(self.canvas_image)[0]

        if for_labels:
            return adjusted_x

        if self.draw_x_line_var.get():
            self.section_canvas.delete('x_line')

            self.section_canvas.create_line(adjusted_x, 0, adjusted_x, canvas_height, tags='x_line')

    def get_depth_from_y_data(self, y_data):
        num_rows = len(self.section)
        depth_range = self.depth_m
        depth_value = int((y_data / num_rows) * depth_range * 100)  # Multiply by 100 to convert to centimeters
        depth_value = round(depth_value / (self.pixelsize_z * 100)) * (self.pixelsize_z * 100)   # Round to the nearest 5 cm step
        return depth_value

    def get_y_data_from_depth(self, depth):
        # Adjust y_data for zoom and pan
        num_rows = len(self.section)
        depth_range = self.depth_m
        y_data = (depth / (depth_range * 100)) * num_rows  # Calculate y_data based on depth value
        return y_data

    def get_y_data_from_depth_dtm(self, depth):
        num_rows = len(self.section)
        depth_range = self.max_depth_new - self.min_depth_new

        # Constrain the depth value within the range of max_depth_new and min_depth_new
        constrained_depth = min(max(depth, self.min_depth_new), self.max_depth_new)

        # Calculate the relative position based on the constrained depth
        relative_depth_position = (self.max_depth_new - constrained_depth) / depth_range

        # Calculate the y-coordinate in the section image
        y_data = relative_depth_position * num_rows

        return int(y_data)

    def get_depth_from_y_data_dtm(self, y_data):
        num_rows = len(self.section)
        depth_range = self.max_depth_new - self.min_depth_new

        # Calculate the relative position of y_data in the section
        relative_y_position = y_data / num_rows

        # Calculate the depth value based on the relative position
        depth_value = self.max_depth_new - (relative_y_position * depth_range)

        depth_value_rounded = round(depth_value*100 / int(self.pixelsize_z*100)) * int(self.pixelsize_z*100)

        return depth_value_rounded

    def get_depth_from_y_data_ft(self, y_data):
        # Existing code to calculate depth_value
        num_rows = len(self.section)
        depth_range = self.depth_m
        depth_value = int((y_data / num_rows) * depth_range * 100)  # Convert to centimeters
        depth_value = round(depth_value / (self.pixelsize_z * 100)) * (self.pixelsize_z * 100) / 100

        # Find the closest value in the first column of the table
        closest_idx = np.argmin(np.abs(self.depth_table[:, 0] - depth_value))
        closest_depth = self.depth_table[closest_idx, 0]

        return round(closest_depth, 3)

    def update_depthslice_canvas(self, x, y):
        x_coor, y_coor = self.get_xy_from_section_coor(x)

        if 'DTMfromGPR' in self.file_name:
            depth = self.get_depth_from_y_data_dtm(y)
        elif self.data_type == 2:
            if self.topo_corrected:
                depth = (self.get_depth_from_y_data(self.y_coord_max_point) - 5) / 100
            else:
                depth = self.get_depth_from_y_data_ft(y)

        elif self.topo_corrected:
            depth = self.get_depth_from_y_data(self.y_coord_max_point) - 5
        else:
            depth = self.get_depth_from_y_data(y)

        self.frame_image.section_coor(x_coor, y_coor)
        self.frame_left.update_image_selection(depth)

        elevation = None
        if self.data_type == 2:
            depth = depth*100
        if self.topo_corrected:
            elevation = self.height - depth/100
        if 'DTMfromGPR' in self.file_name:
            elevation = depth / 100
            depth = self.depth_from_ds

        self.frame_image.coordinates_label.update_coordinates(x_coor, y_coor)
        self.coordinates_label.update_coordinates(x_coor, y_coor, depth=depth, elevation=elevation)


    def set_depth_value(self, depth_start, elevation):
        self.depth_from_ds = depth_start
        self.elevation = elevation


    def update_coordinates_label_from_ds(self, x, y, depth):
        elevation = None
        if self.data_type == 2:
            depth = depth * 100
        if self.topo_corrected:
            x = self.update_x_line(x, y, for_labels=True)
            indx = self.get_closest_indx_height_profile(x)
            elevation = self.downsampled_height_profile[indx - 1] - depth / 100
        elif 'DTMfromGPR' in self.file_name:
            depth = self.depth_from_ds
            elevation = self.elevation

        self.coordinates_label.update_coordinates(x, y, depth=depth, elevation=elevation)

    def update_y_line(self, depth):
        if self.draw_y_line_var.get():

            if self.data_type == 2:
                depth = depth
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 10
            elif 'DTMfromGPR' in self.file_name:
                y_data = self.get_y_data_from_depth_dtm(depth)
                y_offset = 10
            elif self.topo_corrected:
                depth = depth - 5
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 0
            else:
                depth = depth-5
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 10


            if self.topo_corrected:
                y = (y_data * self.zoom) + self.section_canvas.coords(self.canvas_image)[1]
                self.plot_height_profile_from_ds(y)
            else:
                canvas_width = self.section_canvas.winfo_width()

                y = (y_data * self.zoom) + self.section_canvas.coords(self.canvas_image)[1]

                self.section_canvas.delete('y_line')

                self.section_canvas.create_line(0, y, canvas_width, y, tags='y_line')

    def create_image_from_section(self):
        self.image_path = os.path.join(self.temp_folder_path, "section_image_temp.png")

        dpi = 100
        xpixels, ypixels = self.section.shape[1], self.section.shape[0]
        figsize = xpixels / dpi, ypixels / dpi

        fig = plt.figure(figsize=figsize, dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')  # Turn off the axis

        ax.imshow(self.section, cmap='Greys', vmin=self.vmin, vmax=self.vmax, interpolation='bilinear')

        # Save the section as an image file
        plt.savefig(self.image_path, dpi=dpi, bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close()


    def get_visible_image_bounds(self):
        # Get the position of the image on the canvas
        img_x, img_y = self.section_canvas.coords(self.canvas_image)

        # Get the current size of the image displayed on the canvas
        current_image_width = self.section_image.width()
        current_image_height = self.section_image.height()

        # Determine the visible area bounds on the canvas
        left_bound = self.y_axis_x
        top_bound = 10
        right_bound = self.secondary_y_axis_x
        bottom_bound = self.x_axis_y

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

        # Calculate the visible bounds in image coordinates
        visible_bounds = self.get_visible_image_bounds()
        if not visible_bounds:
            return  # No visible bounds calculated

        visible_left, visible_top, visible_right, visible_bottom = visible_bounds

        # Check for the case where 'right' is less than 'left'
        if visible_right <= visible_left or visible_bottom <= visible_top:
            return None  # Return None to indicate there's no valid crop area

        # Crop the PIL image to the visible area
        self.cropped_image = self.apply_transformations(visible_left, visible_top, visible_right, visible_bottom)

        # Save the cropped image
        self.cropped_image.save(file_path, 'PNG')

        self.plot_image_with_labels(file_path=file_path)


    def plot_image_with_labels(self, file_path):
        # Gather data for each set of labels (currently commented out)
        # Convert the PIL image to a NumPy array for Matplotlib to handle
        image_array = np.array(self.cropped_image)

        xpixels, ypixels = image_array.shape[1], image_array.shape[0]
        dpi = 300
        plt.rcParams.update({'font.size': 10})
        figsize = ((xpixels * 3) / dpi, (ypixels * 3) / dpi)  # Adjust figsize calculation

        # Create the figure and axes using figsize
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.imshow(image_array)
        ax.set_aspect('auto')  # Adjust aspect ratio
        ax.set_xticks([])  # Remove x-axis tick marks
        ax.set_yticks([])  # Remove y-axis tick marks
        ax.set_xlabel('')
        ax.set_ylabel('')

        # Manually set the axes limits to exactly match the dimensions of the image
        ax.set_xlim([0, xpixels])
        ax.set_ylim([ypixels, 0])

        # Gather data for each set of labels
        x_label_data = self.get_label_data(self.x_labels)
        y_label_data = self.get_label_data(self.y_labels)
        secondary_y_label_data = self.get_label_data(self.secondary_y_labels)
        additional_label_data = self.get_label_data(self.additional_labels)

        # Find the maximum number of digits in y_labels
        max_digits = max(len(data['text']) for data in y_label_data)

        # Adjusting position for depth label based on digits
        depth_label_offset = 5  # default
        if max_digits >= 3:
            depth_label_offset += 5 * (max_digits - 2)  # Increase offset for each extra digit beyond 2

        vals_y = []
        labs_y = []
        for data in y_label_data:
            y = data['y']
            lab = data['text']
            vals_y.append(y)
            labs_y.append(lab)

        max_depth = max(vals_y)
        min_depth = min(vals_y)
        depth_ticks = np.linspace(max_depth, min_depth, num=5)
        ax.set_yticks(np.linspace(0, max_depth - min_depth, len(depth_ticks)))
        ax.set_yticklabels(labs_y)

        ax_sec = ax.twinx()

        vals_sec_y = []
        labs_sec_y = []
        for data in secondary_y_label_data:
            y = data['y']
            lab = data['text']
            vals_sec_y.append(y)
            labs_sec_y.append(lab)

        max_depth = max(vals_sec_y)
        min_depth = min(vals_sec_y)
        depth_ticks = np.linspace(max_depth, min_depth, num=5)
        ax_sec.set_yticks(np.linspace(0, max_depth - min_depth, len(depth_ticks)))
        ax_sec.set_yticklabels(labs_sec_y)
        ax_sec.invert_yaxis()

        vals_x = []
        labs_x = []

        for data in x_label_data:
            x = data['x']
            lab = data['text']
            vals_x.append(x)
            labs_x.append(lab)

        min_x = min(vals_x)
        max_x = max(vals_x)
        dist_ticks = np.linspace(max_x, min_x, num=5)
        ax.set_xticks(np.linspace(0, max_x - min_x, len(dist_ticks)))
        ax.set_xticklabels(labs_x)

        # Plotting additional labels
        for data in additional_label_data:
            if data['tag'] == 'dist_label':
                ax.text(data['x'] - self.y_axis_x, data['y'] - 5, data['text'], ha='center', va='top', color='black', fontweight='bold')
            elif data['tag'] == 'depth_label':
                ax.text(data['x'] - self.y_axis_x - depth_label_offset, data['y'] - 10, data['text'], rotation=90,
                        ha='center', va='center', color='black', fontweight='bold')
            elif data['tag'] == 'sec_depth_label':
                ax.text(data['x'] - self.y_axis_x + depth_label_offset, data['y'] - 10, data['text'], rotation=90,
                        ha='center', va='center', color='black', fontweight='bold')

        plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)  # Adjust subplot padding
        fig.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

        self.lift()

    def get_label_data(self, label_ids):
        label_data = []
        for label_id in label_ids:
            text = self.section_canvas.itemcget(label_id, 'text')
            coords = self.section_canvas.coords(label_id)
            tags = self.section_canvas.gettags(label_id)
            if coords:
                # Adjust positions if necessary, depending on the anchor and label positioning in your app
                x_pos, y_pos = coords[0], coords[1]
                tag = tags[0] if tags else None
                label_data.append({'text': text, 'x': x_pos, 'y': y_pos, 'tag': tag})

        if label_data[0]['tag'] == 'label_x' or label_data[0]['tag'] == 'label_y':
            label_data = self.recalculate_labels(label_data)

        return label_data

    def recalculate_labels(self, data):
        axis = data[0]['tag']

        if axis == 'label_x':
            data = [data for data in data if self.y_axis_x <= data['x'] <= self.secondary_y_axis_x]
        elif axis == 'label_y':
            data = [data for data in data if 10 <= data['y'] <= self.x_axis_y]

        lab1 = float(data[0]['text'])
        lab2 = float(data[1]['text'])

        if axis == 'label_x':
            lab1_pos = float(data[0]['x'])
            lab2_pos = float(data[1]['x'])
            min_pixel = self.y_axis_x  # Starting position in pixels
            max_pixel = self.secondary_y_axis_x  # Ending position in pixels
        elif axis == 'label_y':
            lab1_pos = float(data[0]['y'])
            lab2_pos = float(data[1]['y'])
            min_pixel = 10     # Starting position in pixels
            max_pixel = self.x_axis_y  # Ending position in pixels

        interval = lab2 - lab1
        interval_y = lab2_pos - lab1_pos

        pixel_per_meter = interval_y / interval

        start_value = lab1 - (lab1_pos - min_pixel) / pixel_per_meter  # Adjust this calculation based on your data setup

        num_labels = 5  # Total number of labels to display

        # Calculate the distance between each label in pixels
        total_pixel_distance = max_pixel - min_pixel
        pixel_interval = total_pixel_distance / (num_labels - 1)

        # Calculate new label interval and total range to cover
        total_range = interval * (num_labels - 1)
        label_interval = total_range / (num_labels - 1)

        label_data_new = []

        if axis == 'label_x':
            y = data[0]['y']
            tag = 'label_x'
            for i in range(num_labels):
                label_pos = min_pixel + i * pixel_interval
                label_value = round(start_value + i * label_interval, 1)  # Increment by 0.5 meters each time

                label_data_new.append({
                    'text': str(label_value),
                    'x': label_pos,
                    'y': y,
                    'tag': tag
                })
        elif axis == 'label_y':
            x = data[0]['x']
            tag = 'label_y'
            for i in range(num_labels):
                label_pos = min_pixel + i * pixel_interval
                label_value = round(start_value + i * label_interval, 1)  # Increment by 0.5 meters each time

                label_data_new.append({
                    'text': str(label_value),
                    'x': x,
                    'y': label_pos,
                    'tag': tag
                })

        return label_data_new


    def apply_transformations(self, visible_left, visible_top, visible_right, visible_bottom):
        # Example of applying transformations and updating the PIL and PhotoImage
        if self.topo_corrected:
            self.pil_section_image = Image.open(self.topo_image_path)
        else:
            self.pil_section_image = Image.open(self.image_path)

        width = self.section_image.width()
        height = self.section_image.height()

        self.pil_section_image = self.pil_section_image.resize((width, height), Image.LANCZOS)

        self.pil_section_image = self.pil_section_image.crop((visible_left, visible_top, visible_right, visible_bottom))  # Any transformation
        return self.pil_section_image


    def add_topography(self):
        self.clear_topography()
        if len(self.dtm_files) == 1:
            dtm_data = next(iter(self.dtm_files.values()))
            self.perform_topographic_correction(dtm_data)
            self.save_topo_corrected_section()
        elif len(self.dtm_files) > 1:
            dtm_data = self.select_dtm_file()
            if dtm_data:
                self.perform_topographic_correction(dtm_data[0])
                self.save_topo_corrected_section()
        else:
            messagebox.showinfo("No DTM File", "No DTM file available for topographic correction.")

        self.adjust_window_size()
        self.lift()
        self.init_image_position = (0, 0)

    def clear_topography(self):
        self.display_section(self.image_path, top_corr=False, clear_topo=True)
        self.display_section(self.image_path, top_corr=False, clear_topo=True)
        self.init_image_position = (0, 0)

    def select_dtm_file(self):
        dtm_file_options = list(self.dtm_files.keys())

        dtm_window = tk.Toplevel()
        dtm_window.title("Select DTM File")

        label = tk.Label(dtm_window, text="Multiple DTM files available. Please select the desired DTM file:")
        label.pack()

        # Create checkboxes for each DTM file option
        selected_dtm_files = []
        for dtm_file_key in dtm_file_options:
            dtm_file_path = self.dtm_files[dtm_file_key]

            var = tk.BooleanVar()

            # Create a checkbox for the DTM file option
            checkbox = tk.Checkbutton(dtm_window, text=dtm_file_key, variable=var)
            checkbox.dtm_file_path = dtm_file_path  # Store the DTM file path as an attribute of the checkbox
            checkbox.pack()

            # Add a command to handle checkbox selection
            checkbox.config(command=lambda cb=checkbox: self.toggle_dtm_file_selection(cb, selected_dtm_files))

        self.confirm_button = tk.Button(dtm_window, text="Confirm", command=lambda: dtm_window.destroy(), state='disabled')
        self.confirm_button.pack()

        dtm_window.wait_window(dtm_window)

        # Return the selected DTM data
        return [cb.dtm_file_path for cb in selected_dtm_files]

    def toggle_dtm_file_selection(self, checkbox, selected_dtm_files):
        for cb in selected_dtm_files:
            cb.deselect()
        selected_dtm_files.clear()
        selected_dtm_files.append(checkbox)
        checkbox.select()
        self.confirm_button.config(state='normal')

    def perform_topographic_correction(self, dtm_data):
        dtm = dtm_data

        coordinates = self.section_coor

        self.height_profile = dtm.create_height_profile(coordinates, self.section.shape[1])

        num_columns = self.section.shape[1]
        num_points = self.height_profile.shape[0]

        # Downsample the height profile to match the number of columns in self.section
        step_size = int(num_points / num_columns)
        self.downsampled_height_profile = self.height_profile[::step_size]


        max_elev_diff = int((np.max(self.downsampled_height_profile) - np.min(self.downsampled_height_profile)) * (1 / self.pixelsize_z))
        tshift = (np.max(self.downsampled_height_profile) - self.downsampled_height_profile) * (1 / self.pixelsize_z)

        # Adjust the time shifts so that the highest elevation becomes zero time

        tshift = tshift.astype(int)  # Convert each element of the array to integers

        # Create a new data matrix with NaN padding
        self.topo_corr_data = np.empty((self.section.shape[0] + max_elev_diff, num_columns))
        self.topo_corr_data[:] = np.nan

        for i in range(num_columns):
            shift_amount = tshift[i]

            # Add NaN padding to the bottom of the column
            padded_column = np.pad(self.section[:, i], (0, max_elev_diff), mode='constant', constant_values=np.nan)

            # Perform the roll operation
            shifted_column = np.roll(padded_column, shift_amount)

            # Insert the shifted column into newdata
            self.topo_corr_data[:, i] = shifted_column[:self.topo_corr_data.shape[0]]

    def save_topo_corrected_section(self):
        self.topo_image_path = os.path.join(self.temp_folder_path, "topo_section_image_temp.png")

        dpi = 100
        xpixels, ypixels = self.topo_corr_data.shape[1], self.topo_corr_data.shape[0]
        figsize = xpixels / dpi, ypixels / dpi

        fig = plt.figure(figsize=figsize, dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')  # Turn off the axis

        ax.imshow(self.topo_corr_data, cmap='Greys', vmin=self.vmin, vmax=self.vmax, interpolation='bicubic')

        # Save the section as an image file
        plt.savefig(self.topo_image_path, dpi=dpi, bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close()

        self.display_section(self.topo_image_path, top_corr=True)


class FakeEvent:
    def __init__(self, x, y):
        self.x = x
        self.y = y





