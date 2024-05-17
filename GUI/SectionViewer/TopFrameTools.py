import tkinter as tk
from tkinter import Frame
from PIL import Image, ImageTk

from config_manager import ConfigurationManager
from GUI.CoordinatesLabel import CoordinatesLabel

class TopFrameTools(Frame):
    def __init__(self, parent, section, section_coor, dist, file_name, data_type, depth_m, pixelsize_z, frame_image, frame_left, *args, **kwargs):  # Corrected __int__ to __init__
        super().__init__(parent, *args, **kwargs)

        self.config_manager = ConfigurationManager('config.ini')
        self.vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        self.vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        self.section_view = None
        self.section_canvas = None
        self.canvas_image = None
        self.section_image = None
        self.x_axis_y = None
        self.y_axis_x = None
        self.secondary_y_axis_x = None
        self.zoom = None
        self.topo_corrected = None
        self.image = None
        self.init_image_position = (0, 0)
        self.section_coor = section_coor
        self.section = section
        self.dist = dist
        self.file_name = file_name
        self.data_type = data_type
        self.depth_m = depth_m
        self.pixelsize_z = pixelsize_z
        self.frame_image = frame_image
        self.frame_left = frame_left
        self.coordinates_label = None

        self.create_widgets()
        self.create_zoom_controls()

        self.frame_left.set_top_frame_tools(self)

    def create_widgets(self):
        # Add buttons or other widgets as needed
        save_button = tk.Button(self, text="Export image", command=self.save_section)
        save_button.pack(side="left", padx=5, pady=5)

        topo_correction = tk.Button(self, text='Add topography', command=self.add_topography)
        topo_correction.pack(side='left', padx=5, pady=5)

        clear_topo = tk.Button(self, text='Clear topography', command=self.clear_topography)
        clear_topo.pack(side='left', padx=5, pady=5)

        # Create check buttons for drawing lines and communication
        self.draw_y_line_var = tk.BooleanVar(value=True)
        self.draw_x_line_var = tk.BooleanVar(value=True)
        self.communication_var = tk.BooleanVar(value=True)

        draw_x_line_checkbox = tk.Checkbutton(self, text="Draw X Line", variable=self.draw_y_line_var)
        draw_x_line_checkbox.pack(side="left", padx=5, pady=5)

        draw_y_line_checkbox = tk.Checkbutton(self, text="Draw Y Line", variable=self.draw_x_line_var)
        draw_y_line_checkbox.pack(side="left", padx=5, pady=5)

        communication_checkbox = tk.Checkbutton(self, text="Enable Communication", variable=self.communication_var)
        communication_checkbox.pack(side="left", padx=5, pady=5)

        greyscale_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        greyscale_frame.pack(side='left', padx=10, pady=5)

        greyscale_label = tk.Label(greyscale_frame, text='Greyscale range')
        greyscale_label.pack()

        # vmin entry and arrow buttons
        self.vmin_var = tk.IntVar(value=self.vmin)  # Removed self.vmin definition assumption
        vmin_entry = tk.Entry(greyscale_frame, width=4, textvariable=self.vmin_var)
        vmin_entry.pack(side="left")
        vmin_up_button = tk.Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmin(1))
        vmin_up_button.pack(side="left")
        vmin_down_button = tk.Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmin(-1))
        vmin_down_button.pack(side="left")

        # vmax entry and arrow buttons
        self.vmax_var = tk.IntVar(value=self.vmax)  # Removed self.vmax definition assumption
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

    def create_zoom_controls(self):
        zoom_in_button = tk.Button(self, text="+", command=self.zoom_in)
        zoom_in_button.pack(side="left", padx=5, pady=5)
        zoom_out_button = tk.Button(self, text="-", command=self.zoom_out)
        zoom_out_button.pack(side="left", padx=5, pady=5)

    def set_zoom_controls(self):
        # Bind right-click drag for panning
        self.section_canvas.bind("<Button-3>", self.start_pan)
        self.section_canvas.bind("<B3-Motion>", self.pan_image)

    def set_coordinates_label(self):
        self.coordinates_label = CoordinatesLabel(self.section_canvas)

    # Placeholder methods for functionality
    def save_section(self):
        pass

    def add_topography(self):
        pass

    def clear_topography(self):
        pass

    def adjust_vmin(self, adjustment):
        pass

    def adjust_vmax(self, adjustment):
        pass

    def update_vmin_vmax(self, event):
        pass

    def reset_to_default_greyscale(self):
        pass

    def start_pan(self, event):
        self.init_image_position = (event.x, event.y)  # Capture initial position

    def pan_image(self, event):
        dx = (event.x - self.init_image_position[0])
        dy = (event.y - self.init_image_position[1])

        self.section_view.pan_offset_x += dx
        self.section_view.pan_offset_y += dy

        actual_image_width = self.section_image.width()
        actual_image_height = self.section_image.height()

        current_pos = self.section_canvas.coords(self.canvas_image)
        new_x = current_pos[0] + dx
        new_y = current_pos[1] + dy

        if new_x > self.section_view.image_left_bound:
            dx = self.section_view.image_left_bound - current_pos[0]
        if new_x + actual_image_width < self.section_view.secondary_y_axis_x:
            dx = self.section_view.secondary_y_axis_x - 1 - (current_pos[0] + actual_image_width)

        if new_y > self.section_view.image_top_bound:
            dy = self.section_view.image_top_bound - current_pos[1]
        elif new_y + actual_image_height < self.section_view.x_axis_y:
            dy = self.section_view.x_axis_y - 2 - (current_pos[1] + actual_image_height)

        self.section_canvas.move(self.canvas_image, dx, dy)
        self.section_view.init_image_position = (event.x, event.y)
        self.init_image_position = (event.x, event.y)
        self.update_axes_based_on_pan(dx, dy)

    def update_axes_based_on_pan(self, dx, dy):
        # Adjust the x-axis labels based on the image movement, skip the last label
        for label in self.section_view.x_labels[:-1]:  # The '[:-1]' slice selects all but the last item
            self.section_canvas.move(label, dx, 0)

        # Adjust the y-axis labels based on the image movement, skip the last label
        for label in self.section_view.y_labels[:-1]:  # Similarly, '[:-1]' skips the last item
            self.section_canvas.move(label, 0, dy)

        # Do the same for secondary y-axis labels if present, skip the last label
        for label in self.section_view.secondary_y_labels[:-1]:
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
        new_x = min(max(new_x, self.section_view.secondary_y_axis_x - new_width), self.section_view.image_left_bound)
        new_y = min(max(new_y, self.section_view.x_axis_y - new_height), self.section_view.image_top_bound)

        # Update the image position and zoom
        self.section_canvas.itemconfig(self.canvas_image, image=self.section_image)
        self.section_canvas.coords(self.canvas_image, new_x, new_y)

        self.section_view.adjust_window_size(zoom=True)
        self.section_view.update_axes_after_zoom()

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
        new_width = max(int(self.section_image.width() / 1.1), self.section_view.actual_image_width)
        new_height = max(int(self.section_image.height() / 1.1), self.section_view.actual_image_height)

        if new_width == self.section_view.actual_image_width:
            self.zoom = self.section_view.init_zoom

        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        self.section_image = ImageTk.PhotoImage(resized_image)

        # Calculate the new position to maintain the zoom center
        current_pos = self.section_canvas.coords(self.canvas_image)
        shift_x = (self.section_image.width() - new_width) / 2
        shift_y = (self.section_image.height() - new_height) / 2
        new_x = viewport_center_x - (viewport_center_x - current_pos[0]) * (1 / 1.1)
        new_y = viewport_center_y - (viewport_center_y - current_pos[1]) * (1 / 1.1)

        # Apply boundary constraints
        new_x = min(max(new_x, self.secondary_y_axis_x - new_width), self.section_view.image_left_bound)
        new_y = min(max(new_y, self.x_axis_y - new_height), self.section_view.image_top_bound)

        # Update the image position and zoom
        self.section_canvas.itemconfig(self.canvas_image, image=self.section_image)
        self.section_canvas.coords(self.canvas_image, new_x, new_y)

        self.section_view.adjust_window_size(zoom=True)
        self.section_view.update_axes_after_zoom()

        fake_event = FakeEvent(viewport_center_x, viewport_center_y)
        self.pan_image(fake_event)

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

    def get_depth_from_y_data(self, y_data):
        num_rows = len(self.section)
        depth_range = self.depth_m
        depth_value = int((y_data / num_rows) * depth_range * 100)  # Multiply by 100 to convert to centimeters
        depth_value = round(depth_value / (self.pixelsize_z * 100)) * (self.pixelsize_z * 100)   # Round to the nearest 5 cm step
        return depth_value


class FakeEvent:
    def __init__(self, x, y):
        self.x = x
        self.y = y


