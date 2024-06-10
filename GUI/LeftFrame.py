from tkinter import Frame, Checkbutton, BooleanVar, Label, Listbox, Scale, font
import os
import re

class LeftFrame(Frame):
    def __init__(self, master, frame_image, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.frame_image = frame_image
        self.frame_right = None
        self.top_frame = None

        self.config(bg="grey", highlightbackground="black", highlightthickness=3)
        self.viewer_mode_checkbox = None
        self.analysis_mode_checkbox = None
        self.nc_checkboxes_frame = None
        self.checkboxes = {}
        self.image_listbox = None
        self.previous_pixelsize = None
        self.first_image_inserted = False  # Flag to track if the first image is inserted
        self.depth_label = None
        self.depth_slider = None
        self.pack_propagate(0)  # Prevent the frame from resizing based on contents

        self.section_view_active = False

        self.bold_font = font.Font(weight="bold", size=10)

    def set_top_frame_tools(self, tf):
        self.tf = tf

    def create_checkboxes(self, projects):
        self.depth_label = None
        self.clear_checkboxes()

        # Checkbox Options Frame
        checkbox_options_frame = Frame(self)
        checkbox_options_frame.pack(side='top', padx=5, pady=5, fill='x')

        # Viewer Mode Checkbox
        self.viewer_var = BooleanVar(value=True)
        self.viewer_mode_checkbox = Checkbutton(checkbox_options_frame, text="Viewer Mode",
                                                command=self.switch_to_viewer_mode,
                                                variable=self.viewer_var, onvalue=True, offvalue=False, state='disabled')
        self.viewer_mode_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky='w')

        # Analysis Mode Checkbox
        self.analysis_var = BooleanVar(value=False)
        self.analysis_mode_checkbox = Checkbutton(checkbox_options_frame, text="Analysis Mode",
                                                  command=self.switch_to_analysis_mode,
                                                  variable=self.analysis_var, onvalue=True, offvalue=False, state='disabled')
        self.analysis_mode_checkbox.grid(row=0, column=1, padx=5, pady=5, sticky='w')

        # NetCDF Checkboxes Frame
        self.nc_checkboxes_frame = Frame(self, highlightbackground="black", highlightthickness=1)
        self.nc_checkboxes_frame.pack(side='top', padx=5, pady=5, fill='x')

        # Data Label
        label = Label(self.nc_checkboxes_frame, text="Data", font=self.bold_font)
        label.pack(side='top')

        # Create Checkboxes for Projects
        for project in projects:
            project_name = os.path.basename(project.fld_file.file_name) if project.fld_file else "Unnamed Project"
            selected = BooleanVar(value=False)
            checkbox = Checkbutton(self.nc_checkboxes_frame, text=project_name, variable=selected,
                                   command=lambda p=project: self.handle_data_checkbox(p))
            checkbox.pack(anchor='w')
            self.checkboxes[project_name] = (checkbox, selected, project)

        self.select_default_checkbox()
        self.update_checkboxes_state()

        # Image Listbox
        self.image_listbox = Listbox(self, bg="white", selectbackground="lightblue")
        self.image_listbox.pack(side='top', padx=5, pady=5, fill='x')
        self.image_listbox.bind("<<ListboxSelect>>", self.wrapper_image_selection)
        self.update_image_listbox(self.get_selected_data())

        # Depth Slider Frame
        self.slider_frame = Frame(self)
        self.slider_frame.pack(side='top', fill='x', padx=5, pady=2)
        self.create_depth_slider()
        self.set_first_checkbox()

    def clear_checkboxes(self):
        if self.viewer_mode_checkbox:
            self.viewer_mode_checkbox.destroy()
            self.viewer_mode_checkbox = None

        if self.analysis_mode_checkbox:
            self.analysis_mode_checkbox.destroy()
            self.analysis_mode_checkbox = None

        for checkbox, var, _ in self.checkboxes.values():
            checkbox.pack_forget()
        self.checkboxes = {}

        if self.nc_checkboxes_frame:
            self.nc_checkboxes_frame.destroy()
            self.nc_checkboxes_frame = None

    def switch_to_viewer_mode(self):
        if self.analysis_var.get():
            selected_checkboxes = [checkbox for checkbox, var, data in self.checkboxes.values() if var.get()]
            if selected_checkboxes:
                for checkbox in selected_checkboxes[1:]:
                    checkbox.deselect()
            else:
                # Select the first checkbox if none are selected
                first_checkbox = next(iter(self.checkboxes.values()))
                first_checkbox[0].select()

        self.analysis_var.set(False)
        self.update_checkboxes_state()
        self.update_image_listbox(self.get_selected_data())

    def switch_to_analysis_mode(self):
        self.viewer_var.set(False)
        self.update_checkboxes_state()

    def set_first_checkbox(self):
        # Check if there are any checkboxes available
        if self.checkboxes:
            # Get the first item from the checkboxes dictionary
            first_checkbox_key = next(iter(self.checkboxes))
            first_checkbox_data = self.checkboxes[first_checkbox_key][2]  # Assuming the data is in the third position

            # Invoke the handle_data_checkbox function for the first checkbox
            self.handle_data_checkbox(first_checkbox_data)

    def handle_data_checkbox(self, clicked_data):
        if self.viewer_var.get():
            # Get the state of the clicked checkbox
            clicked_checkbox_info = self.checkboxes[clicked_data.fld_file.file_name]
            clicked_checkbox, clicked_var, _ = clicked_checkbox_info

            # If the clicked checkbox is not selected, select it
            if not clicked_var.get():
                clicked_var.set(True)
                clicked_data.fld_file.selected.set(True)

            # Deselect all other checkboxes
            for data_key, (checkbox, var, data) in self.checkboxes.items():
                if data != clicked_data:
                    var.set(False)

            self.update_image_listbox(self.get_selected_data())
            self.update_scale_range(0, len(self.image_dict) - 1)
            self.update_depth_interval()
            self.update_min_max_depth()
            self.frame_right.update_sections(from_data_switch=True)

            if self.previous_pixelsize != clicked_data.fld_file.pixelsize:
                self.top_frame.zoom_to_full_extent()

        elif self.analysis_var.get():
            # No action required for multiple selections in Analysis mode
            pass

        self.previous_pixelsize = clicked_data.fld_file.pixelsize

    def update_checkboxes_state(self):
        if self.viewer_var.get() or self.analysis_var.get():
            state = 'normal'
        else:
            state = 'disabled'

        for checkbox, var, data in self.checkboxes.values():
            checkbox.config(state=state)

    def disable_project_checkboxes(self):
        for checkbox_info in self.checkboxes.values():
            checkbox_widget = checkbox_info[0]  # Assuming the checkbox widget is the first item in the tuple
            if checkbox_widget:
                checkbox_widget.config(state='disabled')

    def enable_project_checkboxes(self):
        for checkbox_info in self.checkboxes.values():
            checkbox_widget = checkbox_info[0]  # Assuming the checkbox widget is the first item in the tuple
            if checkbox_widget:
                checkbox_widget.config(state='normal')

    def update_frame_right(self, frame_right):
        self.frame_right = frame_right

    def update_top_frame(self, top_frame):
        self.top_frame = top_frame

    def select_default_checkbox(self):
        if self.checkboxes:
            default_checkbox = next(iter(self.checkboxes.values()))
            default_checkbox[1].set(True)

    def get_checkbox_states(self):
        checkbox_states = {}
        for file_name, (checkbox, var, data) in self.checkboxes.items():
            checkbox_state = var.get()
            checkbox_states[file_name] = checkbox_state

        return checkbox_states

    def get_selected_data(self):
        for file_name, (checkbox, var, data) in self.checkboxes.items():
            if var.get():
                selected_data = data
                self.pixelsize_z = selected_data.fld_file.pixelsize_z
                self.data_type = selected_data.fld_file.data_type
        self.active_file_name = selected_data.fld_file.file_name

        return selected_data

    def update_image_listbox(self, data):
        self.clear_image_listbox()

        image_folder = data.depthslice_folder
        self.image_dict = {}

        if os.path.exists(image_folder) and os.path.isdir(image_folder):
            image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.tiff', '.tif'))]

            file_sizes = [os.path.getsize(os.path.join(image_folder, f)) for f in image_files]
            if not file_sizes:
                self.image_listbox.insert("end", "No images found")
                self.first_image_inserted = False
                return

            avg_file_size = sum(file_sizes) / len(file_sizes)
            min_file_size = min(file_sizes)

            # Check if the smallest file size is significantly smaller than the average
            if file_sizes.count(min_file_size) >= 3 and min_file_size < avg_file_size * 0.25:
                # Remove all files with the smallest file size
                image_files = [f for f in image_files if os.path.getsize(os.path.join(image_folder, f)) > min_file_size]

            for file_name in image_files:
                depth_start, depth_end = self.extract_depth_from_filename(file_name, image_files)
                if depth_start is not None and depth_end is not None:
                    self.image_dict[file_name] = (depth_start, depth_end)

            if self.image_dict:
                if 'DTMfromGPR' in self.active_file_name:
                    sorted_images = sorted(self.image_dict.keys(), key=lambda x: self.image_dict[x][0], reverse=True)
                else:
                    sorted_images = sorted(self.image_dict.keys(), key=lambda x: self.image_dict[x][0])

                for file_name in sorted_images:
                    self.image_listbox.insert("end", file_name)

                self.image_listbox.selection_set(0)
                self.handle_image_selection(None)
            else:
                self.image_listbox.insert("end", "No valid images found")
                self.first_image_inserted = False
        else:
            self.image_listbox.insert("end", "No images found")
            self.first_image_inserted = False

    def extract_depth_from_filename(self, file_name, image_files):
        depth_start = None
        depth_end = None

        selected_data = self.get_selected_data()
        fname = selected_data.fld_file.file_name

        # Check if the file name ends with a valid image extension
        valid_extensions = [".jpg", ".jpeg", ".png", ".tif", ".tiff"]
        if file_name.lower().endswith(tuple(valid_extensions)):
            # Extract the depth values from the file name based on file type
            if self.data_type == 2:
                # New file type with depth and traveltime information
                depth_values = re.findall(r"(\d+\.\d+)ns_(\d+\.\d+)m\.tif", file_name)
                if depth_values:
                    depth_start, depth_end = depth_values[0]  # First tuple from the list
                    depth_start = float(depth_start.replace('ns', ''))
                    depth_end = float(depth_end.replace('m', ''))
            elif 'DTMfromGPR' in fname:
                # Extracting elevation values for files with 'DTMfromGPR' in their name
                depth_values = re.findall(r"_([m]?[\d]+)-([m]?[\d]+)\.", file_name)
                if depth_values:
                    depth_start, depth_end = depth_values[0]  # Unpack the first (and likely only) match
                    depth_start = int(depth_start.replace('m', '-'))  # Convert to integer, handle negative values
                    depth_end = int(depth_end.replace('m', '-'))  # Convert to integer, handle negative values
            else:
                # Original file type with only depth information
                base_name = os.path.splitext(file_name)[0]
                depth_values = re.findall(r"[\d]+", base_name)
                if depth_values:
                    if len(depth_values) >= 2:
                        depth_start = int(depth_values[-2])
                        depth_end = int(depth_values[-1])
                    else:
                        depth_start = int(depth_values[-1])

        return depth_start, depth_end

    def clear_image_listbox(self):
        if self.image_listbox:
            self.image_listbox.delete(0, "end")

    def wrapper_image_selection(self, event=None, selected_file=None):
        if event:
            selected_file = self.handle_image_selection(event)

        if self.section_view_active and self.frame_right.communication_var.get() and self.section_view_window.section_canvas.is_cursor_on_image() == False:
            if self.frame_right.draw_y_line_var.get():
                if self.data_type == 2:
                    depth_start, depth_end = self.image_dict.get(selected_file, (None, None))
                    self.section_view_window.update_y_line(depth_end*100)
                    self.frame_image.set_depth(depth=depth_end)
                elif 'DTMfromGPR' in selected_file:
                    depth_start, depth_end = self.image_dict.get(selected_file, (None, None))
                    self.section_view_window.update_y_line(depth_end/100)
                    self.frame_image.set_depth(depth=depth_end)
                else:
                    depth_start, depth_end = self.image_dict.get(selected_file, (None, None))
                    self.section_view_window.update_y_line(depth_end)
                    self.frame_image.set_depth(depth=depth_end)

    def create_depth_slider(self):
        # Parent frame to hold the three columns
        columns_frame = Frame(self.slider_frame)
        columns_frame.pack(side='top', fill='x')

        # Create three columns with equal weight
        for i in range(3):
            columns_frame.grid_columnconfigure(i, weight=1)

        # Left frame for depth label and Min/Max labels
        left_frame = Frame(columns_frame)
        left_frame.grid(row=0, column=0, sticky='ew')

        # Right frame for dummy widget
        right_frame = Frame(columns_frame)
        right_frame.grid(row=0, column=2, sticky='ew')

        # Create and pack the label with a bold font
        l = Label(right_frame, text='Depthslider', font=self.bold_font)
        l.pack(side='top', padx=5, pady=2)

        # Create Min label aligned with the top of the Scale
        self.min_label = Label(right_frame, text="Min:", anchor='s')
        self.min_label.pack(side='top', fill='x')

        # Create the depth slider in the middle frame
        self.depth_slider = Scale(right_frame, length=300, from_=0, to=len(self.image_dict) - 1,
                                  orient='vertical', showvalue=0,
                                  command=self.on_slider_change)
        self.depth_slider.pack(pady=2)

        # Create the depth label in the left frame
        self.depth_label = Label(left_frame, text="Depth: \n N/A", width=10)
        self.depth_label.pack(padx=5, pady=2)

        # Create Max label aligned with the bottom of the Scale
        self.max_label = Label(right_frame, text="Max:", anchor='n')
        self.max_label.pack(side='bottom', fill='x')

        self.update_image_listbox(self.get_selected_data())
        self.update_depth_interval()
        self.update_min_max_depth()

    def update_depth_interval(self):
        self.depth_interval = self.extract_depth_interval()

    def update_scale_range(self, new_from, new_to):
        # Update the scale range
        self.depth_slider.config(from_=new_from, to=new_to)

        # Reset the scale value if it's outside the new range
        current_value = self.depth_slider.get()
        if current_value < new_from or current_value > new_to:
            self.depth_slider.set(new_from)

    def update_min_max_depth(self):
        # Initialize min and max depth variables
        min_depth = float('inf')
        max_depth = -float('inf')

        for _, (depth_start, depth_end) in self.image_dict.items():
            # Update the min and max depths based on the entire dictionary
            min_depth = min(min_depth, depth_start)
            max_depth = max(max_depth, depth_end)

        # Check if valid min and max depths have been found
        if min_depth != float('inf') and max_depth != -float('inf'):
            selected_data = self.get_selected_data()
            fname = selected_data.fld_file.file_name
            if 'DTMfromGPR' in fname:
                self.min_label.config(text=f"Max elevation: \n {max_depth / 100} m")  # Highest elevation first
                self.max_label.config(text=f"Min elevation: \n {min_depth / 100} m")
            elif self.data_type == 2:
                self.min_label.config(text=f"Min depth: \n 0.0 cm")  # Highest elevation first
                self.max_label.config(text=f"Max depth: \n {max_depth * 100} cm")
            else:
                self.min_label.config(text=f"Min depth: \n {int(min_depth)} cm")
                self.max_label.config(text=f"Max depth: \n {int(max_depth)} cm")

            self.max_depth = max_depth
            self.min_depth = min_depth

        else:
            # Default text if no depth values are found
            self.min_label.config(text="Min: N/A")
            self.max_label.config(text="Max: N/A")

    def on_slider_change(self, val):
        # Update listbox selection based on slider value
        index = int(val)
        self.image_listbox.selection_clear(0, 'end')
        self.image_listbox.selection_set(index)
        self.image_listbox.see(index)
        self.handle_image_selection(None)
        # Calculate the depth range based on the slider position and depth interval
        if self.depth_interval:
            selected_index = self.image_listbox.curselection()
            selected_file = self.image_listbox.get(selected_index)
            depth_start, depth_end = self.image_dict.get(selected_file, (None, None))

            if self.data_type == 2:
                self.depth_label.config(text=f"Depth: \n {round((depth_end * 100), 2)} cm \n\n Time: \n {depth_start} ns")
            elif 'DTMfromGPR' in self.active_file_name:
                lower_depth = int(val) * self.depth_interval
                upper_depth = lower_depth + self.depth_interval
                self.depth_label.config(text=f"Elevation: \n {depth_start/100}-{depth_end/100} m \n\n Depth: \n {lower_depth}-{upper_depth} cm ")
                if self.section_view_active:
                    self.section_view_window.set_depth_value(upper_depth, depth_start/100)
            else:
                self.depth_label.config(text=f"Depth: \n {depth_start}-{depth_end} cm")

            if self.section_view_active and self.frame_right.communication_var.get():
                if self.frame_right.draw_y_line_var.get():
                    selected_index = self.image_listbox.curselection()
                    selected_file = self.image_listbox.get(selected_index)

                    self.wrapper_image_selection(selected_file)

        else:
            self.depth_label.config(text="Depth: \n N/A")

    def extract_depth_interval(self):
        if self.data_type == 1:
            for filename in self.image_dict.keys():
                depth_info = re.search(r"(\d+)-(\d+)", filename)
                if depth_info:
                    depth_start, depth_end = map(int, depth_info.groups())
                    return abs(depth_end - depth_start)
        else:
            return 1
        return None  # Return None if no interval can be determined

    def handle_image_selection(self, event):
        if self.image_listbox.curselection():
            selected_index = self.image_listbox.curselection()[0]
            selected_file = self.image_listbox.get(selected_index)

            # Update the slider position to match the listbox selection
            if self.depth_slider:
                self.depth_slider.set(selected_index)
            else:
                pass

            # Continue with the rest of the method to update image display and depth label
            selected_data = self.get_selected_data()
            selected_file_path = os.path.join(selected_data.depthslice_folder, selected_file)
            self.frame_image.data_variables(selected_data)
            self.frame_image.update_image_canvas(selected_file_path)

            if not self.first_image_inserted:
                self.first_image_inserted = True
                self.frame_image.center_image()

        return selected_file

    def update_image_selection(self, depth):
        selected_image = None

        if self.data_type == 2:
            # Find the image with the closest end value to the depth
            closest_diff = float('inf')
            selected_image = None
            for file_name, (_, end) in self.image_dict.items():
                diff = abs(depth - end)
                if diff < closest_diff:
                    closest_diff = diff
                    selected_image = file_name
        else:
            # Search for the matching depth in the image dictionary
            for file_name, (start, end) in self.image_dict.items():
                if 'DTMfromGPR' in self.active_file_name:
                    if end <= depth <= start:
                        selected_image = file_name
                        break
                else:
                    if start <= depth <= end:
                        selected_image = file_name
                        break

        # Update the selection in the image listbox
        if selected_image:
            index = self.image_listbox.get(0, "end").index(selected_image)
            self.image_listbox.selection_clear(0, "end")
            self.image_listbox.selection_set(index)
            self.image_listbox.see(index)

            # Handle the image selection
            self.handle_image_selection(None)

    def define_section_view(self, section_view):
        self.section_view_window = section_view
