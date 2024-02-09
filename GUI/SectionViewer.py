import tkinter as tk
from tkinter import messagebox, filedialog, PhotoImage
import matplotlib.pyplot as plt
from PIL import Image, ImageTk
import os
from screeninfo import get_monitors
import numpy as np
import platform

from config_manager import ConfigurationManager

monitors = get_monitors()
screen_res_primary = [monitors[0].height, monitors[0].width]

global window_width, window_height
window_width = int(screen_res_primary[1]*1)
window_height = int(screen_res_primary[0]*0.45)

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

        self.create_widgets()
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

        self.x_axis = self.section_canvas.create_line(0, 0, 0, 0, fill='black', width=2)  # x-axis line
        self.y_axis = self.section_canvas.create_line(0, 0, 0, 0, fill='black', width=2)  # y-axis line
        self.secondary_y_axis = self.section_canvas.create_line(0, 0, 0, 0, fill='black', width=2)  # y-axis line
        self.x_labels = []  # list to store x-axis labels
        self.y_labels = []  # list to store y-axis labels
        self.secondary_y_labels = []

        if 'DTMfromGPR' in self.file_name:
            topo_correction.config(state='disabled')
            clear_topo.config(state='disabled')

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


    def adjust_window_size(self, clear_topo=False):
        top_frame_width = self.calculate_frame_width(self.top_frame_section_window) + 50

        # Determine the width for the section image
        image_frame_width = self.resized_width + 200

        # Set the window width to the maximum of the two widths
        window_width = max(top_frame_width, image_frame_width)
        window_height = self.resized_height + 200

        if clear_topo:
            self.geometry(f"{window_width}x{self.orig_window_height}")
        else:
            # Resize the window
            self.geometry(f"{window_width}x{window_height}")

        self.section_canvas.update_idletasks()

    def update_axes(self, top_corr=False):
        # Calculate the positions for the x-axis and y-axis lines
        x_axis_y = self.section_image.height() + 12
        self.y_axis_x = 50  # adjust the x-coordinate for y-axis line as needed
        self.secondary_y_axis_x = self.section_image.width() + self.y_axis_x + 2

        # Update the x-axis line
        self.section_canvas.coords(self.x_axis, self.y_axis_x, x_axis_y, self.secondary_y_axis_x, x_axis_y)

        # Update the y-axis line
        self.section_canvas.coords(self.y_axis, self.y_axis_x, 10, self.y_axis_x, x_axis_y)

        self.section_canvas.coords(self.secondary_y_axis, self.secondary_y_axis_x, 10, self.secondary_y_axis_x, x_axis_y)

        # Remove existing x-axis labels
        for label in self.x_labels:
            self.section_canvas.delete(label)

        # Remove existing y-axis labels
        for label in self.y_labels:
            self.section_canvas.delete(label)

        # Remove existing secondary y-axis labels
        for label in self.secondary_y_labels:
            self.section_canvas.delete(label)
        self.secondary_y_labels = []

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
        y_label_interval = (x_axis_y - 10) / (len(self.depth_ticks) - 1)
        for i, depth in enumerate(self.depth_ticks):
            label_y = 10 + i * y_label_interval

            if 'DTMfromGPR' in self.file_name:
                # Use depth value directly for DTMfromGPR case
                label_text = f"{depth:.1f}"
            elif top_corr:
                label_text = f"{depth:.1f}"


            else:
                label_text = f"{depth:.1f}"  # Use regular depth value for standard section

            label = self.section_canvas.create_text(self.y_axis_x - 5, label_y, anchor='e', text=label_text)
            self.y_labels.append(label)

            secondary_label = self.section_canvas.create_text(self.secondary_y_axis_x + 5, label_y, anchor='w',
                                                                  text=str(label_text))
            self.secondary_y_labels.append(secondary_label)

        # Add new x-axis labels
        x_label_interval = (self.secondary_y_axis_x - self.y_axis_x) / (len(distance_ticks) - 1)
        for i, distance in enumerate(distance_ticks):
            label_x = self.y_axis_x + i * x_label_interval
            label_text = f"{distance:.1f}"  # Format the distance value as needed
            label = self.section_canvas.create_text(label_x, x_axis_y + 10, anchor='n', text=label_text)
            self.x_labels.append(label)

        # Add distance label
        distance_label_x = int((self.y_axis_x + self.secondary_y_axis_x) / 2)
        distance_label_y = x_axis_y + 25  # adjust the y-coordinate for the depth label as needed
        distance_label = self.section_canvas.create_text(distance_label_x, distance_label_y, anchor='n',
                                                         text='Distance (m)', font=("Arial", 11, "bold"))
        self.y_labels.append(distance_label)

        if 'DTMfromGPR' in self.file_name:
            # Add depth label
            depth_label_x = self.y_axis_x - 40
            depth_label_y = int((10 + x_axis_y) / 2)
        elif top_corr:
            # Add depth label
            depth_label_x = self.y_axis_x - 40
            depth_label_y = int((10 + x_axis_y) / 2)
        else:
            # Add depth label
            depth_label_x = self.y_axis_x - 35
            depth_label_y = int((10 + x_axis_y) / 2)

        if top_corr:
            depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        elif 'DTMfromGPR' in self.file_name:
            depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        else:
            depth_label_text = 'Depth (m)'  # Use regular label text for standard section

        depth_label = self.section_canvas.create_text(depth_label_x, depth_label_y, anchor='e',
                                                      text=depth_label_text, angle=90,
                                                      font=("Arial", 11, "bold"))
        self.x_labels.append(depth_label)


        if 'DTMfromGPR' in self.file_name:
            # Add secondary depth label
            secondary_depth_label_x = self.secondary_y_axis_x + 40  # adjust the x-coordinate for the secondary depth label as needed
            secondary_depth_label_y = int((10 + x_axis_y) / 2)
        elif top_corr:
            secondary_depth_label_x = self.secondary_y_axis_x + 40  # adjust the x-coordinate for the secondary depth label as needed
            secondary_depth_label_y = int((10 + x_axis_y) / 2)
        else:
            secondary_depth_label_x = self.secondary_y_axis_x + 35  # adjust the x-coordinate for the secondary depth label as needed
            secondary_depth_label_y = int((10 + x_axis_y) / 2)

        if top_corr:
            secondary_depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        elif 'DTMfromGPR' in self.file_name:
            secondary_depth_label_text = 'Elevation (m)'  # Update label text for topo-corrected sections
        else:
            secondary_depth_label_text = 'Depth (m)'  # Use regular label text for standard section

        secondary_depth_label = self.section_canvas.create_text(secondary_depth_label_x, secondary_depth_label_y,
                                                                anchor='e', text=secondary_depth_label_text, angle=90,
                                                                font=("Arial", 11, "bold"))
        self.secondary_y_labels.append(secondary_depth_label)

    def draw_lines(self, event):
        x, y = event.x, event.y

        # Adjust the x and y coordinates to the section data coordinates
        x_offset = 50
        y_offset = 10
        x_data = (x - x_offset) / self.zoom
        y_data = (y - y_offset) / self.zoom

        # Adjust for the bottom and right edges of the image
        resized_width = int(self.image.width * self.zoom)
        resized_height = int(self.image.height * self.zoom)
        canvas_width = self.section_canvas.winfo_width()
        canvas_height = self.section_canvas.winfo_height()

        if x >= canvas_width - x_offset:
            x_data = self.image.width - (resized_width - x_data)  # Adjust x_data based on the actual image width
        if y >= canvas_height - y_offset:
            y_data = self.image.height - (resized_height - y_data)  # Adjust y_data based on the actual image height

        if x_offset <= x < resized_width + x_offset and y_offset <= y < resized_height + y_offset:
            # Remove any previously drawn lines and height profile
            self.section_canvas.delete('x_line')
            self.section_canvas.delete('y_line')
            self.section_canvas.delete('height_profile_line')

            # Draw vertical line
            if self.draw_x_line_var.get():
                self.section_canvas.create_line(x, 0, x, self.section_canvas.winfo_height(), tags='x_line')

            # Draw horizontal line or plot height profile for topographically corrected section
            if self.draw_y_line_var.get():
                if self.topo_corrected:
                    self.plot_height_profile(y, x)
                else:
                    self.section_canvas.create_line(0, y, self.section_canvas.winfo_width(), y, tags='y_line')


            if self.communication_var.get():
                self.update_depthslice_canvas(x_data, y_data)

        else:
            # Cursor is outside the image bounds, remove any previously drawn lines
            self.section_canvas.delete('line')

    def plot_height_profile(self, y_data, x_data, from_ds_viewer=False):
        # Clear any previous height profile lines
        self.section_canvas.delete('height_profile_line')

        min_height = min(self.downsampled_height_profile)

        # Calculate the total length of the downsampled height profile in meters
        total_length_meters = len(self.downsampled_height_profile) * self.sampling_interval

        # Calculate the scaling factor for both height and width based on the total length in meters
        self.scale_factor = (self.secondary_y_axis_x - self.y_axis_x) / total_length_meters

        height_points = []

        if from_ds_viewer:
            closest_index = np.argmax(self.downsampled_height_profile) + 1
        else:
            # Calculate the closest index in the height profile for the given x-coordinate
            closest_index = int(round((x_data - self.y_axis_x) / (self.sampling_interval * self.scale_factor)))

        # Calculate the y-coordinate offset for this height point based on the closest index

        y_offset = (y_data + (self.downsampled_height_profile[closest_index-1] - min_height) * self.scale_factor)

        # Iterate over each height value and its index in the self.height_profile
        for i, height in enumerate(self.downsampled_height_profile):
            # Calculate the x-coordinate for this height point
            x_coord = self.y_axis_x + (i * self.sampling_interval) * self.scale_factor

            # Calculate the y-coordinate for this height point
            y_coord = y_offset - (height - min_height) * self.scale_factor

            # Append the calculated (x, y) point to the height_points list
            height_points.append((x_coord, y_coord))

        max_height_index = np.argmax(self.downsampled_height_profile)
        y_data_max_height = height_points[max_height_index][1]

        self.y_max_height = y_data_max_height / self.zoom

        # Create a line using all the height points
        self.section_canvas.create_line(height_points, fill='black', tags='height_profile_line')

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

    def update_x_line(self, x, y):
        if self.draw_x_line_var.get():
            x_offset = 50
            canvas_height = self.section_canvas.winfo_height()

            x_pos = self.get_section_coor_from_xy(x, y)

            x = (x_pos * self.zoom) + x_offset

            self.section_canvas.delete('x_line')

            self.section_canvas.create_line(x, 0, x, canvas_height, tags='x_line')

    def get_depth_from_y_data(self, y_data):
        num_rows = len(self.section)
        depth_range = self.depth_m
        depth_value = int((y_data / num_rows) * depth_range * 100)  # Multiply by 100 to convert to centimeters
        depth_value = round(depth_value / (self.pixelsize_z * 100)) * (self.pixelsize_z * 100)   # Round to the nearest 5 cm step
        return depth_value

    def get_y_data_from_depth(self, depth):
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
                depth = (self.get_depth_from_y_data(self.y_max_height) - 5) / 100
            else:
                depth = self.get_depth_from_y_data_ft(y)

        elif self.topo_corrected:
            depth = self.get_depth_from_y_data(self.y_max_height) - 5
        else:
            depth = self.get_depth_from_y_data(y)


        self.frame_image.section_coor(x_coor, y_coor)
        self.frame_left.update_image_selection(depth)

        self.frame_image.print_canvas_coordinates(section_x=x, section_y=y)

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
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 0
            else:
                depth = depth-5
                y_data = self.get_y_data_from_depth(depth)
                y_offset = 10


            if self.topo_corrected:
                y = (y_data * self.zoom) + y_offset
                self.plot_height_profile(y, x_data=0, from_ds_viewer=True)
            else:
                canvas_width = self.section_canvas.winfo_width()

                y = (y_data * self.zoom) + y_offset

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

    def save_section(self):
        file_path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG Image', '*.png')])
        if file_path:
            dpi = 300
            plt.rcParams.update({'font.size': 10})
            if self.topo_corrected:
                xpixels, ypixels = self.topo_corr_data.shape[1], self.topo_corr_data.shape[0]
            else:
                xpixels, ypixels = self.section.shape[1], self.section.shape[0]
            figsize = (xpixels * self.zoom * 3) / dpi, (ypixels * self.zoom * 3) / dpi
            fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

            # Adjust the extent of the image
            extent = [0, xpixels * self.zoom, ypixels * self.zoom, 0]

            # Choose the interpolation method
            interpolation_method = 'bicubic'

            if self.topo_corrected:
                ax.imshow(self.topo_corr_data, cmap='Greys', vmin=self.vmin, vmax=self.vmax, extent=extent,
                          aspect='auto', interpolation=interpolation_method)
            else:
                ax.imshow(self.section, cmap='Greys', vmin=self.vmin, vmax=self.vmax, extent=extent,
                          aspect='auto', interpolation=interpolation_method)

            distance_ticks = np.linspace(0, self.dist, num=5)

            ax.set_xlabel('Distance (m)')
            ax.set_xticks(np.linspace(0, xpixels * self.zoom, len(distance_ticks)))
            ax.set_xticklabels([f"{d:.1f}" for d in distance_ticks])
            ax.set_xlim(0, xpixels * self.zoom)

            if 'DTMfromGPR' in self.file_name:
                # Use min and max elevation for y-axis labels
                min_depth = self.frame_left.min_depth
                max_depth = self.frame_left.max_depth
                depth_ticks = np.linspace(max_depth, min_depth, num=5)
                ax.set_yticks(np.linspace(0, ypixels * self.zoom, len(depth_ticks)))
                ax.set_yticklabels([f"{d / 100:.1f}" for d in depth_ticks])
                ax.set_ylabel('Elevation (m)')
                ax.set_ylim(ypixels * self.zoom, 0)

                ax_sec = ax.twinx()
                ax_sec.set_yticks(np.linspace(0, ypixels * self.zoom, len(depth_ticks)))
                ax_sec.set_yticklabels([f"{d / 100:.1f}" for d in depth_ticks])
                ax_sec.set_ylabel('Elevation (m)')
                ax_sec.set_ylim(ypixels * self.zoom, 0)

            elif self.topo_corrected:
                max_height = max(self.height_profile)
                depth_ticks_for_primary_axis = np.linspace(0, self.depth_m,
                                                           num=5)  # Adjust the number of ticks as needed
                ax.set_yticks(np.linspace(0, ypixels * self.zoom, len(depth_ticks_for_primary_axis)))
                ax.set_yticklabels(
                    [f"{max_height - d:.1f}" for d in depth_ticks_for_primary_axis])  # Reverse depth for primary y-axis
                ax.set_ylim(ypixels * self.zoom, 0)
                ax.set_ylabel('Elevation (m)')

                # Set up secondary y-axis (right side)
                ax_sec = ax.twinx()
                min_height = min(self.height_profile)
                adjusted_height_ticks = np.linspace(max_height, min_height - self.depth_m, num=5)
                ax_sec.set_yticks(np.linspace(0, ypixels * self.zoom, len(adjusted_height_ticks)))
                ax_sec.set_ylim(ypixels * self.zoom, 0)
                ax_sec.set_yticklabels([f"{h:.1f}" for h in adjusted_height_ticks])
                ax_sec.set_ylabel('Elevation (m)')
            else:
                # Standard depth labels
                depth_ticks = np.linspace(0, self.depth_m, num=5)
                ax.set_yticks(np.linspace(0, ypixels * self.zoom, len(depth_ticks)))
                ax.set_yticklabels([f"{d:.1f}" for d in depth_ticks])
                ax.set_ylabel('Depth (m)')
                ax.set_ylim(ypixels * self.zoom, 0)

                ax_sec = ax.twinx()
                ax_sec.set_yticks(np.linspace(0, ypixels * self.zoom, len(depth_ticks)))
                ax_sec.set_yticklabels([f"{d:.1f}" for d in depth_ticks])
                ax_sec.set_ylabel('Depth (m)')
                ax_sec.set_ylim(ypixels * self.zoom, 0)

            # Manually adjust the position of the axes
            bottom_margin = 0.20  # Increase the bottom margin to 10%
            left_margin = 0.05
            right_margin = 0.05
            top_margin = 0.05

            fig.subplots_adjust(left=left_margin, right=1 - right_margin, top=1 - top_margin, bottom=bottom_margin)

            plt.savefig(file_path, dpi=dpi, bbox_inches='tight')
            plt.close()

        self.lift()

    def add_topography(self):
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

    def clear_topography(self):
        self.display_section(self.image_path, top_corr=False, clear_topo=True)
        self.display_section(self.image_path, top_corr=False, clear_topo=True)

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





