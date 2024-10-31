import tkinter as tk
from tkinter import Frame, Button, font, filedialog, messagebox
import time
import os
import re
import shapefile
from multiprocessing import Process, set_start_method


from GUI.error_handling import show_error_dialog
from GUI._3DViewer import _3DViewer
from GPR_func._2D_vertical import check_section_array

#from GUI.SectionViewer_old import SectionView
from GUI.SectionViewer.SectionView import SectionView
from data.ProjectData import ArbSectionData

from GUI._3DViewer.VolumeViewer import launch_volume_viewer

# Ensure the spawn method is used for starting processes (required for Windows compatibility)
set_start_method("spawn", force=True)

class RightFrame(Frame):
    def __init__(self, master, frame_image, frame_left, menu_builder, project_data, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.config(bg="grey", highlightbackground="black", highlightthickness=3)
        self.master = master
        self.frame_image = frame_image
        self.frame_left = frame_left
        self.top_frame = None
        self.menu_builder = menu_builder

        self.default_bg = None

        self.project_data = project_data
        self.project_file = None
        self.sections = {}
        self.section_count = 1
        self.total_section_count = 1

        self.rectangle_data ={}

        self.section_view_window = None
        self.section_view_active = False

        self.pack_propagate(0)

        self.create_widgets()

    def create_widgets(self):
        # Frame to hold the buttons
        buttons_frame_top = tk.Frame(self)
        buttons_frame_top.pack(side="top", fill="x", padx=5, pady=5)

        # Arbitrary Section Button
        self.arbitrary_section_button = Button(buttons_frame_top, text='Show Section', state='disabled',
                                               command=self.create_arbitrary_section)
        self.arbitrary_section_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')

        # Clear Section Button
        self.clear_section_button = Button(buttons_frame_top, text='Clear Section', state='disabled',
                                           command=self.clear_section)
        self.clear_section_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Configure the column weights for buttons frame top
        buttons_frame_top.grid_columnconfigure(0, weight=1)
        buttons_frame_top.grid_columnconfigure(1, weight=1)

        # Checkboxes Frame
        checkboxes_frame = tk.Frame(self)
        checkboxes_frame.pack(side="top", fill="x", padx=5, pady=5)

        # Checkboxes
        self.draw_x_line_var = tk.BooleanVar(value=True)
        self.draw_y_line_var = tk.BooleanVar(value=True)
        self.communication_var = tk.BooleanVar(value=True)

        self.communication_checkbox = tk.Checkbutton(checkboxes_frame, text="Update Section View", state='disabled',
                                                     variable=self.communication_var)
        self.communication_checkbox.grid(row=1, column=0, padx=5, pady=5, sticky='w')

        # Canvas Section (Unchanged)
        self.add_section_canvas()

        self.add_rectangle_frame()

    def get_default_bg_color(self, master):
        """ Get the default system background color. """
        temp_label = tk.Label(master)
        default_bg = temp_label.cget('bg')
        temp_label.destroy()
        return default_bg

    def add_section_canvas(self):
        # Frame to hold the canvas and scrollbar
        self.sections_frame = tk.Frame(self, highlightbackground="black", highlightthickness=1)
        self.sections_frame.pack(side='top', padx=5, pady=5, fill='x')

        self.default_bg = self.get_default_bg_color(self.sections_frame)

        canvas_frame = tk.Frame(self.sections_frame)
        canvas_frame.pack(side='top', fill='x')

        # Canvas with border
        self.canvas = tk.Canvas(canvas_frame, height=300, width=300, highlightbackground="black", highlightthickness=1)
        self.scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.bind("<MouseWheel>", self.on_mousewheel)

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", pady=5, padx=5, expand=True, fill='x')
        self.scrollbar.pack(side="right", fill="y")

        # Frame to hold the buttons
        buttons_frame = tk.Frame(self.sections_frame)
        buttons_frame.pack(side="bottom", fill="x", pady=5)

        # Row 1 Buttons
        self.show_all_button = tk.Button(buttons_frame, text="Show all", command=self.show_all_sections, state='disabled')
        self.show_all_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')

        self.hide_all_button = tk.Button(buttons_frame, text="Hide all", command=self.hide_all_sections, state='disabled')
        self.hide_all_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Row 2 Buttons
        self.export_button = tk.Button(buttons_frame, text="Export (visible) sections", command=self.export_sections, state='disabled')
        self.export_button.grid(row=1, column=0, padx=5, pady=5, sticky='ew')

        self.import_button = tk.Button(buttons_frame, text="Import section", command=self.import_shapefile, state='disabled')
        self.import_button.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # Configure the column weights to ensure buttons are centered
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)

    def add_rectangle_frame(self):
        # Button Frame for Rectangle Buttons
        rectangle_buttons_frame = tk.Frame(self)
        rectangle_buttons_frame.pack(side='top', fill='x', padx=5, pady=5)

        # Show 3D Data Button
        self.show_3d_data_button = tk.Button(rectangle_buttons_frame, text="Show 3D Data", command=self.show_3d_data,
                                             state='disabled', fg="black")
        self.show_3d_data_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')

        # Clear Rectangle Button
        self.clear_rectangle_button = tk.Button(rectangle_buttons_frame, text="Clear Rectangle",
                                                command=self.clear_rectangle,
                                                state='disabled', fg="black")
        self.clear_rectangle_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        rectangle_buttons_frame.grid_columnconfigure(0, weight=1)
        rectangle_buttons_frame.grid_columnconfigure(1, weight=1)

        # Canvas Frame for Rectangle Canvas
        canvas_frame = tk.Frame(self)
        canvas_frame.pack(side='top', fill='x', pady=5, padx=5)

        # Canvas to display rectangle data
        self.rectangle_canvas = tk.Canvas(canvas_frame, height=300, width=300, highlightbackground="black",
                                          highlightthickness=1)
        self.rectangle_canvas.pack(side='top', padx=5, pady=5, expand=True, fill='both')

    def add_rectangle(self, start_coords, perp_start_coords, perp_stop_coords, stop_coords):
        self.rectangle_data.clear()

        # Remove existing label frame if it exists
        if hasattr(self, "label_frame"):
            self.label_frame.destroy()

        # Create a frame to hold the label
        self.label_frame = tk.Frame(self.rectangle_canvas, bg="white")
        self.label_frame.pack()

        # Add a label to the frame
        label = tk.Label(self.label_frame, text="Rectangle 1", bg="white")
        label.pack()

        # Prevent resizing of the canvas frame
        self.rectangle_canvas.pack_propagate(0)

        # Store rectangle corner point information in the dictionary
        self.rectangle_data = {
            "start_coords": start_coords,
            "perp_start_coords": perp_start_coords,
            "perp_stop_coords": perp_stop_coords,
            "stop_coords": stop_coords
        }

        # Enable buttons
        self.show_3d_data_button.config(state='normal')
        self.clear_rectangle_button.config(state='normal')

    def show_3d_data(self):
        data = self.frame_left.get_selected_data()
        subset = data.fld_file.create_3d_subset(self.rectangle_data)

        #spacing = (data.fld_file.pixelsize_z*10, data.fld_file.pixelsize*10, data.fld_file.pixelsize*10)
        #_3DViewer.visualize_3d_data(subset, spacing=spacing)

        spacing = (data.fld_file.pixelsize_z, data.fld_file.pixelsize_z, data.fld_file.pixelsize_z)

        # Start the VolumeViewer in a new process, passing the xarray and pixel_size
        viewer_process = Process(target=launch_volume_viewer, args=(subset, spacing))
        viewer_process.start()


    def clear_rectangle(self):
        # Disable buttons
        self.show_3d_data_button.config(state='disabled')
        self.clear_rectangle_button.config(state='disabled')

        # Remove rectangle from the canvas
        self.frame_image.canvas.delete("rectangle", 'start_p')

        # Remove label frame if it exists
        if hasattr(self, "label_frame"):
            self.label_frame.destroy()

        # Clear rectangle data dictionary
        self.rectangle_data.clear()

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def update_button_states(self, section_drawn):
        if section_drawn:
            self.arbitrary_section_button['state'] = 'normal'
            self.clear_section_button['state'] = 'normal'
        else:
            self.arbitrary_section_button['state'] = 'disabled'
            self.clear_section_button['state'] = 'disabled'

    def toggle_communication_button(self):
        if self.section_view_active:
            self.communication_checkbox['state'] = 'normal'
        else:
            self.communication_checkbox['state'] = 'disabled'

    def disable_section_button(self):
        self.arbitrary_section_button['state'] = 'disabled'

    def enable_section_button(self):
        self.arbitrary_section_button['state'] = 'normal'

    def disable_focus_buttons(self):
        for section_info in self.sections.values():
            focus_button = section_info.get('focus_button')
            if focus_button:
                focus_button.config(state='disabled')

    def enable_focus_buttons(self):
        for section_info in self.sections.values():
            focus_button = section_info.get('focus_button')
            if focus_button:
                focus_button.config(state='normal')

    def disable_keep_checkbuttons(self):
        for section_info in self.sections.values():
            # Disable 'keep' checkbuttons
            section_frame = section_info.get('frame')
            if section_frame:
                for widget in section_frame.winfo_children():
                    if isinstance(widget, tk.Checkbutton):
                        if widget.cget('text') == 'Keep':
                            widget.config(state='disabled')

    def enable_keep_checkbuttons(self):
        for section_info in self.sections.values():
            # Enable 'keep' checkbuttons
            section_frame = section_info.get('frame')
            if section_frame:
                for widget in section_frame.winfo_children():
                    if isinstance(widget, tk.Checkbutton):
                        if widget.cget('text') == 'Keep':
                            widget.config(state='normal')

    def update_menu_builder(self, menu_builder):
        self.menu_builder = menu_builder

    def update_top_frame(self, top_frame):
        self.top_frame = top_frame

    def update_frame_left(self):
        if self.section_view_window is not None:
            self.frame_left.section_view_active = True
        else:
            self.section_view_window = False

    def update_image_frame(self):
        if self.section_view_window is not None:
            self.frame_image.section_view_active = True
        else:
            self.section_view_window = False

    def update_project(self, project_file):
        self.project_file = project_file
        if self.project_file is not None:
            self.import_button['state'] = 'normal'

    def create_arbitrary_section(self):
        # Check if a SectionView window is already open
        if self.section_view_window is not None:
            self.section_view_window.destroy()  # Close the existing window

        # Get the selected data
        data = self.frame_left.get_selected_data()

        # Extract coordinates from the active section
        if self.frame_image.active_section:
            start_coords = self.frame_image.active_section['start']
            stop_coords = self.frame_image.active_section['end']

            # Convert global coordinates to the format needed for creating arbitrary sections
            start_x, start_y = self.frame_image.canvas_coor_to_global(*start_coords)
            stop_x, stop_y = self.frame_image.canvas_coor_to_global(*stop_coords)

            section_coor = [(start_x, start_y), (stop_x, stop_y)]

            dist, section, depth_m, sampling_interval, data_type, top_removed, bottom_removed, depth_table = data.fld_file.create_arbitrary_section(start_x, start_y, stop_x,
                                                                                               stop_y)

            valid_section = check_section_array(section)

            if section.shape[0] == 0 or valid_section == False:
                show_error_dialog("Section outside the data-area, please try another section!")
            else:
                project_file_path = self.menu_builder.get_project_file()
                dtm_files = data.DTM_files

                # Create the SectionView window with the new coordinates
                arb_section = ArbSectionData(section, depth_m, dist, sampling_interval, dtm_files, section_coor, data.fld_file.pixelsize_z, data_type, top_removed, bottom_removed, depth_table)

                self.section_view_window = SectionView(arb_section, project_file_path, self.frame_image, self.frame_left, self.top_frame, self)

                self.frame_left.define_section_view(self.section_view_window)
                self.frame_image.define_section_view(self.section_view_window)
                time.sleep(0.1)
                self.update_frame_left()
                self.update_image_frame()
                self.top_frame.set_section_view(self.section_view_window)
                self.top_frame.disable_draw_mode()
                self.frame_image.bindings()
                self.top_frame.section_view_active = True
                self.section_view_active = True
                self.disable_section_button()
                self.disable_focus_buttons()
                self.disable_keep_checkbuttons()
                self.toggle_communication_button()
                self.frame_left.disable_project_checkboxes()
        else:
            print("No active section defined.")

    def clear_section(self):
        if self.section_view_window is not None:
            self.section_view_window.cleanup()
        self.frame_image.clear_section()
        self.disable_section_button()
        self.enable_focus_buttons()
        self.enable_keep_checkbuttons()
        self.frame_image.active_section_drawn = False

        for info in self.sections.values():
            info['frame'].config(bg=self.default_bg)  # Default background color

    def add_section(self, start_coords, end_coords, section_name, from_shp=False, from_json=False, select=True):
        bold_font = font.Font(weight="bold", size=10)

        # Create or update the section frame
        frame = self.sections.get(section_name, {}).get('frame', tk.Frame(self.scrollable_frame))
        frame.pack(fill='x', pady=2)

        label = tk.Label(frame, text=section_name, width=10, font=bold_font)
        label.pack(side='left', padx=5)

        # Initialize the select checkbox to be checked by default
        select_var = tk.BooleanVar(value=True)
        visible_label = tk.Label(frame, text="Visible")
        visible_label.pack(side='left', padx=(5, 0))
        select_checkbox = tk.Checkbutton(frame, variable=select_var,
                                         command=lambda: self.on_select_toggle(section_name))
        select_checkbox.pack(side='left', padx=(0, 5))
        if from_json:
            if select:
                select_checkbox.select()
            else:
                select_checkbox.deselect()
        else:
            select_checkbox.select()

        keep_var = self.sections.get(section_name, {}).get('keep', tk.BooleanVar())
        keep_checkbox = tk.Checkbutton(frame, text='Keep', variable=keep_var,
                                       command=lambda: self.on_keep_toggle(section_name))
        keep_checkbox.pack(side='left', padx=5)
        if from_shp or from_json:
            keep_checkbox.select()

        focus_button = tk.Button(frame, text='Focus', command=lambda: self.focus_section(section_name))
        focus_button.pack(side='left', padx=5)

        self.sections[section_name] = {
            'frame': frame,
            'label': label,
            'select': select_var,
            'keep': keep_var,
            'focus_button': focus_button,
            'start': start_coords,
            'end': end_coords
        }

        self.update_sections_button_states()
        self.frame_image.update_section_visibility()
        self.canvas.bbox("all")

    def update_sections(self, from_data_switch=False):
        bold_font = font.Font(weight="bold", size=10)

        # Clear all existing section frames
        for section_info in self.sections.values():
            section_info['frame'].destroy()

        # Rebuild sections based on their order in the dictionary
        for name, info in self.sections.items():
            # Create a new frame for each section
            frame = tk.Frame(self.scrollable_frame)
            frame.pack(fill='x', pady=2)

            label = tk.Label(frame, text=name, width=10, font=bold_font)
            label.pack(side='left', padx=5)

            # Visible label
            visible_label = tk.Label(frame, text="Visible")
            visible_label.pack(side='left', padx=(5, 0))

            # Select checkbox with state from the dictionary
            select_checkbox = tk.Checkbutton(frame, variable=info['select'],
                                             command=lambda name=name: self.on_select_toggle(name))
            select_checkbox.pack(side='left', padx=(0, 5))
            if info['select'].get():
                select_checkbox.select()
            else:
                select_checkbox.deselect()

            keep_checkbox = tk.Checkbutton(frame, text='Keep', variable=info['keep'],
                                           command=lambda name=name: self.on_keep_toggle(name))
            keep_checkbox.pack(side='left', padx=5)

            focus_button = tk.Button(frame, text='Focus',
                                     command=lambda n=name: self.focus_section(n))
            focus_button.pack(side='left', padx=5)

            # Update the stored info with the new frame and label
            info.update({'frame': frame, 'label': label, 'focus_button': focus_button})

            self.update_sections_button_states()

        self.frame_image.update_section_visibility()

        if self.sections:
            if from_data_switch and self.frame_image.active_section_drawn == False:
                pass
            else:
                last_section_name = list(self.sections.keys())[-1]
                self.frame_image.set_active_section(last_section_name)

                # Reset the background of all section frames
                for info in self.sections.values():
                    info['frame'].config(bg=self.default_bg)  # Default background color

                # Highlight the focused section's frame
                self.sections[last_section_name]['frame'].config(bg='blue')

        self.frame_image.section_drawn = True
        self.canvas.bbox("all")

    def on_keep_toggle(self, section_name):
        # If the section is unkept, remove it
        if section_name in self.sections and not self.sections[section_name]['keep'].get():
            self.delete_section(section_name)
            self.update_sections()
        else:
            # Update sections to reflect any changes
            self.update_sections()
            self.scroll_to_bottom()

    def on_select_toggle(self, section_name):
        # Update the select state in the dictionary
        if section_name in self.sections:
            current_state = self.sections[section_name]['select'].get()
            self.sections[section_name]['select'].set(current_state)

            # Update the visibility in ImageFrame
            self.frame_image.update_section_line(section_name,
                                                 self.sections[section_name]['start'],
                                                 self.sections[section_name]['end'],
                                                 current_state)
            # Check if the section being unselected is the active section
            if not current_state and self.frame_image.active_section:
                # Convert active section's canvas coordinates to global coordinates
                active_start_canvas, active_end_canvas = self.frame_image.active_section['start'], \
                self.frame_image.active_section['end']
                active_start_global = self.frame_image.canvas_coor_to_global(*active_start_canvas)
                active_end_global = self.frame_image.canvas_coor_to_global(*active_end_canvas)

                # Coordinates from the sections dictionary are already in global format
                section_start, section_end = self.sections[section_name]['start'], self.sections[section_name]['end']

                if (active_start_global, active_end_global) == (section_start, section_end):
                    # Logic to find and set the next or previous section as active
                    section_names = list(self.sections.keys())
                    current_index = section_names.index(section_name)

                    # Inside RightFrame's on_select_toggle or similar method
                    if len(self.sections) > 1:
                        new_active_section_name = None

                        # Function to find the next active section
                        def find_next_active_section(start_index, direction):
                            if direction == 1:  # Forward
                                range_start, range_end, step = start_index + 1, len(section_names), 1
                            else:  # Backward
                                range_start, range_end, step = start_index - 1, -1, -1

                            for i in range(range_start, range_end, step):
                                section_name = section_names[i]
                                if self.sections[section_name]['select'].get():
                                    return section_name

                            return None  # Return None if no active section is found

                        # Check for the next or previous section
                        if current_index < len(self.sections):
                            # Try to find the next active section
                            new_active_section_name = find_next_active_section(current_index, 1)
                        if new_active_section_name is None and current_index > 0:
                            # If no next active section, try to find the previous active section
                            new_active_section_name = find_next_active_section(current_index, -1)

                        if new_active_section_name:
                            # Set the found section as the new active section
                            new_active_section_info = self.sections[new_active_section_name]
                            self.frame_image.set_active_section(new_active_section_name)
                            self.focus_section(new_active_section_name)

                        else:
                            # Clear the active section if no suitable section is found
                            self.frame_image.clear_section()
                    else:
                        # Clear the active section if no other sections are available
                        self.frame_image.clear_section()

        count_selected = self.count_selected_sections()
        if count_selected == 0:
            self.section_drawn = False
            self.update_button_states(self.section_drawn)
        else:
            self.section_drawn = True
            self.update_button_states((self.section_drawn))

        self.frame_image.section_drawn = True
        self.canvas.bbox("all")

    def count_selected_sections(self):
        count = 0
        for section_info in self.sections.values():
            if section_info['select'].get():
                count += 1
        return count

    def focus_section(self, section_name):
        # Call ImageFrame's method to focus on the section
        if section_name in self.sections:
            self.sections[section_name]['select'].set(True)
            self.frame_image.set_active_section(section_name)

            # Reset the background of all section frames
            for info in self.sections.values():
                info['frame'].config(bg=self.default_bg)  # Default background color

            # Highlight the focused section's frame
            if section_name in self.sections:
                self.sections[section_name]['frame'].config(bg='blue')

                self.scroll_to_frame(self.sections[section_name]['frame'])

        self.enable_section_button()
        self.section_drawn = True
        self.update_button_states(self.section_drawn)
        self.frame_image.section_drawn = True
        self.canvas.bbox("all")

    def show_all_sections(self):
        # Set all sections to visible and update ImageFrame
        for name in self.sections:
            self.sections[name]['select'].set(True)
            self.frame_image.update_section_line(name,
                                                 self.sections[name]['start'],
                                                 self.sections[name]['end'],
                                                 True)

        self.update_sections()

        self.section_drawn = True
        self.update_button_states(self.section_drawn)
        self.frame_image.section_drawn = True
        self.canvas.bbox("all")
        self.enable_section_button()

    def hide_all_sections(self):
        # Set all sections to not visible and update ImageFrame
        for name in self.sections:
            self.sections[name]['select'].set(False)
            self.frame_image.update_section_line(name,
                                                 self.sections[name]['start'],
                                                 self.sections[name]['end'],
                                                 False)

        self.clear_section()
        self.frame_image.section_drawn = False
        self.canvas.bbox("all")

    def scroll_to_bottom(self):
        # Update the scrollable frame's view to the bottom
        self.scrollable_frame.update_idletasks()  # Ensure the frame's layout is updated
        self.canvas.yview_moveto(1.0)  # Move the scrollbar to the bottom

    def scroll_to_frame(self, frame):
        self.scrollable_frame.update_idletasks()
        frame_y = frame.winfo_y()  # Get the y-coordinate of the frame

        # Convert frame position to a relative position in the canvas
        canvas_height = self.canvas.winfo_height()
        scrollable_region_height = self.canvas.bbox("all")[3]  # y-coordinate of the bottom of the scrollable region
        relative_position = frame_y / scrollable_region_height

        # Calculate the position to scroll to, ensuring it doesn't scroll beyond the top of the canvas
        target_position = max(relative_position - canvas_height / 2 / scrollable_region_height, 0)

        # Adjust the canvas scroll to bring the frame into view
        self.canvas.yview_moveto(target_position)

    def add_new_section(self, start_coords, end_coords):
        if self.sections:
            # Get the last section's name and extract its numerical part
            last_section_number = self.find_highest_section_number()
            last_section_name = 'Section ' + str(last_section_number)
            last_section_kept = self.sections[last_section_name]['keep'].get()

            if last_section_kept:
                # If the last section was kept, create a new section with the next number
                new_section_name = f"Section {last_section_number + 1}"
            else:
                # If the last section was not kept, overwrite it
                new_section_name = last_section_name
                self.frame_image.update_section_line(new_section_name,
                                                     self.sections[new_section_name]['start'],
                                                     self.sections[new_section_name]['end'],
                                                     False)
        else:
            # If there are no sections, start with the first section
            new_section_name = "Section 1"

        # Add or overwrite the section
        self.add_section(start_coords, end_coords, section_name=new_section_name)

        # Update sections to reflect the changes
        self.update_sections()
        self.scroll_to_bottom()  # Scroll to bottom only when adding a new section   ------

    def delete_section(self, section_name):
        # Remove the section frame and delete it from the dictionary
        if section_name in self.sections:
            self.frame_image.update_section_line(section_name,
                                                 self.sections[section_name]['start'],
                                                 self.sections[section_name]['end'],
                                                 False)
            self.sections[section_name]['frame'].destroy()
            del self.sections[section_name]

        if len(self.sections) == 0:
            self.frame_image.clear_section()
            self.update_sections_button_states()
        self.canvas.bbox("all")

    def update_sections_button_states(self):
        # Check if there are any sections in the dictionary
        has_sections = len(self.sections) > 0

        # Enable or disable the buttons based on the presence of sections
        state = 'normal' if has_sections else 'disabled'
        self.show_all_button['state'] = state
        self.hide_all_button['state'] = state
        self.export_button['state'] = state

    def export_sections(self):
        initial_dir = os.path.dirname(self.project_file) if self.project_file else None
        base_name = os.path.basename(self.project_file)
        name = os.path.splitext(base_name)[0]
        initial_file = name + '_section_lines'

        # Ask the user for the file name and path to save the shapefile
        filepath = filedialog.asksaveasfilename(
            initialdir=initial_dir, initialfile=initial_file,
            title="Save Shapefile",
            filetypes=[("Shapefiles", "*.shp")],
            defaultextension=".shp",
        )
        if not filepath:
            # User cancelled the file saving
            return

        # Create a dictionary of selected sections
        selected_sections = {name: info for name, info in self.sections.items() if info['select'].get()}

        # Export all selected sections to a single shapefile
        if selected_sections:
            self.export_all_sections_to_shapefile(selected_sections, filepath)

    def export_all_sections_to_shapefile(self, sections, filepath):
        with shapefile.Writer(filepath, shapeType=shapefile.POLYLINE) as shp:
            # Define the fields for each attribute
            shp.field('NAME', 'C')

            for section_name, section_info in sections.items():
                # Define the line with start and stop coordinates
                line = [[section_info['start'], section_info['end']]]

                # Add the line and record to the shapefile
                shp.line(line)
                shp.record(section_name)

        print(f"Exported all selected sections to {filepath}")

    def import_shapefile(self):
        if self.section_view_active:
            # Show warning dialog
            response = messagebox.askyesno(
                "Warning",
                "Another section view is open. Continuing with the import will close this window. Would you like to continue?",
                icon='warning'
            )
            if not response:
                # User chose 'No', so cancel the import
                return
            else:
                self.clear_section()

        filepath = filedialog.askopenfilename(filetypes=[("Shapefiles", "*.shp")])
        if not filepath:
            # User cancelled the file selection
            return

        with shapefile.Reader(filepath) as shp:
            # Check for exported shapefile structure
            fields = [field[0] for field in shp.fields[1:]]  # Skip the deletion flag field
            is_exported_shapefile = 'NAME' in fields

            # Check records for specific naming pattern
            if is_exported_shapefile:
                for record in shp.iterRecords():
                    if not re.match(r'Section \d{1,2}', record[0]):
                        is_exported_shapefile = False
                        break

            if is_exported_shapefile:
                valid_lines_found = False
                for shapeRecord in shp.iterShapeRecords():
                    # Check if the shape is a line with exactly two points
                    if len(shapeRecord.shape.points) == 2:
                        start_coords, end_coords = shapeRecord.shape.points
                        # Extract the section name from the 'NAME' field in the record

                        section_name = shapeRecord.record[0]  # Assuming 'NAME' is the first field
                        if not re.match(r"Section \d{1,2}$", section_name):
                            section_name = self.generate_new_section_name()

                        start_coords, end_coords = shapeRecord.shape.points

                        if self.does_section_exist(start_coords, end_coords):
                            valid_lines_found = True
                            continue

                        self.add_section(start_coords, end_coords, section_name, from_shp=True)
                        valid_lines_found = True

                if not valid_lines_found:
                    show_error_dialog("Selected shapefile does not contain any valid lines consisting of only two points.")
                    return

            else:
                valid_lines_found = False
                for shapeRecord in shp.iterShapeRecords():
                    # Check if the shape is a line with exactly two points
                    if len(shapeRecord.shape.points) == 2:
                        start_coords, end_coords = shapeRecord.shape.points
                        section_name = self.generate_new_section_name()
                        self.add_section(start_coords, end_coords, section_name, from_shp=True)
                        valid_lines_found = True

                if not valid_lines_found:
                    show_error_dialog("Selected shapefile does not contain any valid lines consisting of only two points.")
                    return

            self.show_all_sections()
            print(f"Imported shapefile '{filepath}'")

    def generate_new_section_name(self):
        base_name = "Section"
        index = 1

        # Find a unique section name
        while f"{base_name} {index}" in self.sections:
            index += 1

        return f"{base_name} {index}"

    def does_section_exist(self, new_start_coords, new_end_coords):
        for section_info in self.sections.values():
            existing_start, existing_end = section_info['start'], section_info['end']
            if (existing_start == new_start_coords and existing_end == new_end_coords) or \
                    (existing_start == new_end_coords and existing_end == new_start_coords):
                # Coordinates match, section already exists
                return True
        return False

    def does_section_name_exist(self, new_section_name):
        return any(new_section_name == section_info['label'].cget('text') for section_info in self.sections.values())

    def find_highest_section_number(self):
        max_section_number = 0
        for section_name in self.sections.keys():
            # Extract the numerical part from the section name
            section_number = int(section_name.split(' ')[-1])
            max_section_number = max(max_section_number, section_number)
        return max_section_number

    def clear_all_sections(self):
        # Destroy all section frames and associated widgets
        for section_name in list(self.sections.keys()):
            self.delete_section(section_name)

        # Clear the dictionary
        self.sections.clear()

        # Update the GUI and internal state as needed
        self.frame_image.clear_section()  # Assuming this method clears the relevant parts of the image frame
        self.update_sections_button_states()  # Update the state of any buttons related to sections
