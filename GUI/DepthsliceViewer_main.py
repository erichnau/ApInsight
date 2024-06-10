"""GUI libraries"""
import tkinter as tk
from tkinter import Frame, Button, Menu, filedialog, messagebox, PanedWindow, PhotoImage, Toplevel, Text, END
import platform
import webbrowser

from screeninfo import get_monitors
import json

"""imports from own scripts:"""
from GUI.EditProjectFile import start_projectGUI
from GUI.ImageFrame import ImageFrame
from GUI.MeasurementTool import MeasurementWindow
from GUI.LeftFrame import LeftFrame
from GUI.RightFrame import RightFrame

from data.ProjectData import ProjectData
from config_manager import ConfigurationManager
from GUI.error_handling import show_error_dialog

monitors = get_monitors()
screen_res_primary = [monitors[0].height, monitors[0].width]


class GuiLayout(object):
    def __init__(self, master):
        self.master = master
        self.frame_left = None
        self.frame_image = None
        self.frame_right = None
        self.top_frame = None
        self.menu_builder = None
        self.listbox = None
        self.canvas = None
        self.methods = None

        self.last_window_width = None
        self.layout_update_id = None

        self.project_data = ProjectData(self.frame_right)

        self.setup_layout()

    def setup_layout(self):
        height = monitors[0].height
        width = monitors[0].width
        width_frame_left = width // 8
        width_frame_image = int((width // 1.5))
        width_frame_right = width - width_frame_left - width_frame_image
        height_frame = height - 20

        # Create a horizontal PanedWindow
        self.pwindow = PanedWindow(self.master, orient='horizontal')

        # Create frames
        self.frame_image = ImageFrame(self.pwindow, self.frame_right,
                                      width=width - width_frame_left - width_frame_right,
                                      height=height_frame)

        self.top_frame = TopFrame(self.master, self.frame_image, width=width, height=height_frame // 20)
        self.top_frame.pack(side='top', fill='x', padx=5, pady=5)

        self.frame_left = LeftFrame(self.pwindow, self.frame_image, width=width_frame_left, height=height_frame)
        self.frame_right = RightFrame(self.pwindow, self.frame_image, self.frame_left, self.menu_builder,
                                      self.project_data,
                                      width=width_frame_right, height=height_frame)

        self.pwindow.pack(fill='both', expand=True)

        # Add frames to the PanedWindow
        self.pwindow.add(self.frame_left, minsize=100)
        self.pwindow.add(self.frame_image, minsize=300)
        self.pwindow.add(self.frame_right, minsize=100)

        # Initialize and build the menu
        self.menu_builder = MenuBuilder(self.master, self.project_data, self.frame_left, self.frame_image,
                                        self.top_frame, self.frame_right)
        self.menu_builder.build_menu()

        # Update frame references
        self.frame_image.update_frame_right(self.frame_right)
        self.frame_left.update_frame_right(self.frame_right)
        self.frame_left.update_top_frame(self.top_frame)
        self.frame_right.update_menu_builder(self.menu_builder)
        self.frame_right.update_top_frame(self.top_frame)

        # Set initial position of the sashes
        initial_sash_pos_left = width_frame_left + 200
        initial_sash_pos_right = width_frame_left + width_frame_image - 200
        self.pwindow.update()  # Ensure window is updated before placing sashes
        self.pwindow.sash_place(0, initial_sash_pos_left, 0)
        self.pwindow.sash_place(1, initial_sash_pos_right, 0)

        self.master.bind('<Configure>', lambda e: self.adjust_layout())

        self.master.mainloop()

    def adjust_layout(self):
        # Cancel previous scheduled update if it exists
        if self.layout_update_id:
            self.master.after_cancel(self.layout_update_id)
            self.layout_update_id = None

        # Schedule the layout update after a short delay
        self.layout_update_id = self.master.after(100, self._update_layout)

    def _update_layout(self):
        # Get the current width of the window
        current_width = self.master.winfo_width()

        # Check if the width has changed significantly to avoid constant adjustments
        if self.last_window_width is None or abs(current_width - self.last_window_width) > 10:
            # Calculate the new widths for the frames
            new_width_frame_left = current_width // 8
            new_width_frame_image = int(current_width // 1.5)
            new_width_frame_right = current_width - new_width_frame_left - new_width_frame_image

            # Adjust the sashes of the PanedWindow
            self.pwindow.sash_place(0, new_width_frame_left, 0)
            self.pwindow.sash_place(1, new_width_frame_left + new_width_frame_image, 0)

            # Update the last window width
            self.last_window_width = current_width

        # Reset the layout update ID
        self.layout_update_id = None

    def get_master(self):
        return self.master


class MenuBuilder:
    def __init__(self, master, project_data, frame_left, frame_image, top_frame, frame_right):
        self.master = master
        self.project_data = project_data
        self.frame_left = frame_left
        self.frame_image = frame_image
        self.top_frame = top_frame
        self.frame_right = frame_right
        self.previous_json_file = None
        self.json_file = None

    def build_menu(self):
        menubar = Menu(self.master)
        self.master.config(menu=menubar)

        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label="Create / Edit Project",
                             command=lambda: start_projectGUI(self.master, self.frame_left))
        filemenu.add_separator()
        filemenu.add_command(label="Open project", command=self.open_project)
        filemenu.add_command(label="Save project", command=self.save_project)
        filemenu.add_command(label="Save project as", command=self.save_project_as)
        filemenu.add_separator()
        filemenu.add_command(label="Options", command=self.open_options_window)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.master.quit)

        viewmenu = Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Velocity Analysis", state='disabled')
        # viewmenu.add_command(label="Toggle Fullscreen")

        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label='Help', command=self.show_help)
        helpmenu.add_command(label='Info', command=self.show_info)

        menubar.add_cascade(label="File", menu=filemenu)
        menubar.add_cascade(label="View", menu=viewmenu)
        menubar.add_cascade(label='Help', menu=helpmenu)

    def show_info(self):
        info_text = "ApInsight, previously known as Schlitzi+, is the result of a three-year journey that started around Christmas 2020. It began as a personal project to learn Python and quickly showed promising results. By 2022, the project was part of the Vestfold Monitoring Project (VEMOP), funded by the Oslofjord Fund. In 2023, it grew even further with help from Angermann IT Services and received funding from NIKU's strategic funds, supported by the Norwegian Research Council, and additional support from Geosphere Austria. \n\nIf you're interested in more information, want to collaborate, or contribute to ApInsight, please reach out to Erich Nau at: \nerich.nau@niku.no"

        self.show_dialog("Info", info_text)

    def show_help(self):
        self.show_dialog("Help",
                         "Two videos explaining the installation and functionality of ApInsight can be found on YouTube:\n\n1. Setup and Installation: \nhttps://youtu.be/f0AKAc0pgbo\n\n2. Introduction and User Guide: \nhttps://youtu.be/lIJPaZ917v4 \n\nThese videos should answer most of your questions. If you have further issues, please post the issue directly in the GitHub repository: \nhttps://github.com/erichnau/ApInsight.git \n\nor send an e-mail to: \nerich.nau@niku.no")

    def show_dialog(self, title, text):
        window = Toplevel(self.master)
        window.title(title)

        txt = Text(window, wrap="word", width=60, height=18, background="light gray")
        txt.pack(padx=10, pady=10)
        txt.insert(END, text)
        txt.config(state="disabled")

        # Define a function to create clickable links
        def add_hyperlink(tag_name, link, start_index, end_index):
            def open_link(e, link=link):
                webbrowser.open_new(link)

            txt.tag_config(tag_name, foreground="blue", underline=1)
            txt.tag_bind(tag_name, "<Enter>", lambda e: txt.config(cursor="hand2"))
            txt.tag_bind(tag_name, "<Leave>", lambda e: txt.config(cursor=""))
            txt.tag_bind(tag_name, "<Button-1>", open_link)
            txt.tag_add(tag_name, start_index, end_index)

        # Adding hyperlinks
        add_hyperlink("hyper1", "https://youtu.be/f0AKAc0pgbo", "4.0", "4.end")
        add_hyperlink("hyper2", "https://youtu.be/lIJPaZ917v4", "7.0", "7.end")
        add_hyperlink("hyper3", "https://github.com/erichnau/ApInsight.git", "10.0", "10.end")
        add_hyperlink("hyper4", "mailto:erich.nau@niku.no", "13.0", "13.end")

        # Close button
        close_button = Button(window, text="Close", command=window.destroy)
        close_button.pack(pady=10)

        window.geometry("500x350")  # Adjust the size as needed

    def open_project(self):
        self.json_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if self.json_file:
            # Clear previous project data and related elements
            if self.project_data:
                self.project_data.clear_project()
                self.frame_right.clear_section()
                self.frame_right.clear_all_sections()

                # Destroy all children in frame_left
                for child in self.frame_left.winfo_children():
                    child.destroy()

            for child in self.frame_image.winfo_children():
                child.destroy()
            self.frame_image.create_canvas()
            self.frame_image.create_coordinates_label()
            self.frame_image.bindings()
            self.frame_image.scale = 1.0
            self.frame_left.first_image_inserted = False

            self.project_data.update_frame_right(self.frame_right)
            self.project_data.load_project_from_json(self.json_file)

            self.frame_left.depth_slider = None
            self.frame_left.create_checkboxes(self.project_data.projects)
            self.top_frame.zoom_button.config(state='normal')
            self.top_frame.draw_section_button.config(state='normal')
            self.top_frame.measure_tool.config(state='normal')
            self.top_frame.draw_rectangle_button.config(state='normal')
            self.top_frame.disable_draw_mode()
            self.frame_right.update_project(self.json_file)

            self.project_data.load_sections()
            self.previous_json_file = self.json_file
        else:
            self.json_file = self.previous_json_file

    def save_project_as(self):
        if self.json_file:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON Files", "*.json")],
                title="Save Project As"
            )

            if file_path:
                # Load the current project data
                project_data = self.project_data.load_project_from_json(self.json_file)

                # Serialize the sections data
                sections_data = {}
                if len(self.frame_right.sections) > 0:
                    sections_data = self.serialize_sections(self.frame_right.sections)

                # Organize the data with 'projects' and 'sections' keys
                data = {
                    "projects": project_data,
                    "sections": sections_data
                }

                # Save the organized data to the JSON file
                with open(file_path, 'w') as file:
                    json.dump(data, file, indent=4)

                # Update the current project file path
                self.json_file = file_path

        else:
            show_error_dialog('No project file is currently open')

    def save_project(self):
        # Check if the current project file path is set
        if self.json_file:
            # Load the current project data
            project_data = self.project_data.load_project_from_json(self.json_file)

            # Serialize the sections data
            sections_data = {}
            if len(self.frame_right.sections) > 0:
                sections_data = self.serialize_sections(self.frame_right.sections)

            # Organize the data with 'projects' and 'sections' keys
            data = {
                "projects": project_data,
                "sections": sections_data
            }

            # Save the organized data to the JSON file
            with open(self.json_file, 'w') as file:
                json.dump(data, file, indent=4)
        else:
            show_error_dialog('No project file is currently open')

    def serialize_sections(self, sections):
        serialized_data = {}
        for name, info in sections.items():
            serialized_data[name] = {
                'select': info['select'].get(),  # Assuming this is a BooleanVar
                'keep': info['keep'].get(),  # Assuming this is a BooleanVar
                'start': info['start'],  # Assuming this is a list or tuple
                'end': info['end']  # Assuming this is a list or tuple
            }
        return serialized_data

    def get_project_file(self):
        return self.json_file

    def open_options_window(self):
        def show_information():
            info_window = tk.Toplevel(options_window)
            info_window.title("Information")
            info_text = "A function to read and convert ApRadar fld files was also implemented in C++. " \
                        "\nIt is used as a compiled .exe file in this program and thus not open-source any more." \
                        "\nThe 'Use compiled exe' option allows you to enable using this compiled .exe file or to stick with a fully " \
                        "\nopen-source Python-program (which is significantly slower converting .fld files)"
            info_label = tk.Label(info_window, text=info_text)
            info_label.pack()
            info_button = tk.Button(info_window, text="Close", command=info_window.destroy)
            info_button.pack()

        self.config_manager = ConfigurationManager('config.ini')
        self.use_compiled_exe = self.config_manager.get_boolean_option('Application', 'use_compiled_exe')
        self.vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        self.vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        options_window = tk.Toplevel(self.master)
        options_window.title("Options")
        if platform.system() == 'Windows':
            options_window.iconbitmap('icon2.ico')
        else:
            icon_image = PhotoImage(file='icon2.png')
            options_window.iconphoto(True, icon_image)
        options_window.geometry('300x250')  # Adjusted size to accommodate new frame

        # Use compiled exe
        label_exe = tk.Label(options_window, text="Use compiled exe:")
        label_exe.pack()
        use_compiled_exe_var = tk.BooleanVar(value=self.use_compiled_exe)
        checkbutton_exe = tk.Checkbutton(options_window, variable=use_compiled_exe_var)
        checkbutton_exe.pack()

        info_button = tk.Button(options_window, text="Information", command=show_information)
        info_button.pack()

        # Frame for default greyscale values
        greyscale_frame = tk.Frame(options_window, borderwidth=2, relief="groove")
        greyscale_frame.pack(pady=10)

        label_greyscale = tk.Label(greyscale_frame, text="Default Greyscale Values for Section View")
        label_greyscale.pack()

        # vmin option
        label_vmin = tk.Label(greyscale_frame, text="Default vmin:")
        label_vmin.pack()
        vmin_var = tk.StringVar(value=str(self.vmin))
        entry_vmin = tk.Entry(greyscale_frame, width=5, textvariable=vmin_var)
        entry_vmin.pack()

        # vmax option
        label_vmax = tk.Label(greyscale_frame, text="Default vmax:")
        label_vmax.pack()
        vmax_var = tk.StringVar(value=str(self.vmax))
        entry_vmax = tk.Entry(greyscale_frame, width=5, textvariable=vmax_var)
        entry_vmax.pack()

        def confirm():
            # Update the use_compiled_exe variable
            new_use_compiled_exe = use_compiled_exe_var.get()
            new_vmin = vmin_var.get()
            new_vmax = vmax_var.get()

            # Update the configuration file
            self.config_manager.set_option('Application', 'use_compiled_exe', str(new_use_compiled_exe))
            self.config_manager.set_option('Greyscale', 'vmin', new_vmin)
            self.config_manager.set_option('Greyscale', 'vmax', new_vmax)
            self.config_manager.save_config()

            options_window.destroy()
            messagebox.showinfo("Options", "Configuration updated.")

        confirm_button = tk.Button(options_window, text="Confirm", command=confirm)
        confirm_button.pack()

        def exit_options():
            options_window.destroy()

        exit_button = tk.Button(options_window, text="Exit", command=exit_options)
        exit_button.pack()


class TopFrame(Frame):
    def __init__(self, master, frame_image, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master = master
        self.frame_image = frame_image

        self.measure_mode = False
        self.mw = None
        self.rectangle_mode = False

        self.section_view = None
        self.section_view_active = False

        self.create_widgets()
        self.pack_propagate(0)

    def create_widgets(self):
        self.zoom_button = Button(self, text="Zoom to Full Extent", command=self.zoom_to_full_extent, state='disabled')
        self.zoom_button.pack(side="left", padx=5, pady=5)

        self.draw_section_button = tk.Button(self, text="Draw Section", command=self.enable_draw_mode, state='disabled')
        self.draw_section_button.pack(side='left', padx=5, pady=5)

        self.draw_rectangle_button = tk.Button(self, text='Draw Rectangle', command=self.toggle_rectangle_mode, state='disabled')
        self.draw_rectangle_button.pack(side='left', padx=5, pady=5)

        self.measure_tool = tk.Button(self, text="Measure Tool", command=self.measure, state='disabled')
        self.measure_tool.pack(side='left', padx=5, pady=5)

    def zoom_to_full_extent(self):
        # Calculate the zoom level for the best fit
        width = self.frame_image.winfo_width()
        height = self.frame_image.winfo_height()
        canvas_width = self.frame_image.canvas.winfo_width()
        canvas_height = self.frame_image.canvas.winfo_height()

        zoom_x = canvas_width / width
        zoom_y = canvas_height / height

        # Take the smaller zoom level to ensure the whole image is visible
        zoom_level = min(zoom_x, zoom_y)

        # Update the image canvas with the new zoom level
        self.frame_image.set_zoom(zoom_level)

    def enable_draw_mode(self):
        self.measure_tool.config(relief='raised')
        self.draw_rectangle_button.config(relief='raised')
        if self.mw is not None:
            self.mw.on_window_close()
            self.measure_mode = False

        if self.frame_image.draw_section_mode:
            self.frame_image.bindings()
            self.draw_section_button.config(relief="raised")
            self.frame_image.draw_section_mode = False
        else:
            if self.section_view_active:
                # Display a warning popup
                result = messagebox.askquestion("Warning",
                                                "Another Section View is active. Do you want to continue? This will close the current SectionView window",
                                                icon='warning')
                if result == 'no':
                    return  # Cancel the operation
                else:
                    self.section_view.cleanup()

            self.frame_image.set_draw_section_mode()
            self.draw_section_button.config(relief="sunken")
            self.frame_image.draw_section_mode = True


    def disable_draw_mode(self):
        self.draw_section_button.config(relief="raised")
        self.frame_image.draw_section_mode = False


    def toggle_rectangle_mode(self):
        if self.frame_image.draw_rectangle_mode:
            self.disable_rectangle_mode()
        else:
            self.enable_rectangle_mode()


    def enable_rectangle_mode(self):
        self.measure_tool.config(relief='raised')
        self.draw_section_button.config(relief='raised')
        self.disable_draw_mode()
        if self.mw is not None:
            self.mw.on_window_close()
            self.measure_mode = False

        if self.frame_image.draw_section_mode:
            self.frame_image.bindings()
            self.draw_section_button.config(relief="raised")
            self.frame_image.draw_section_mode = False

        # Add logic to enable rectangle mode
        self.frame_image.draw_rectangle_mode = True
        # Implement whatever logic is necessary to enable rectangle drawing mode

        self.frame_image.set_draw_rectangle_mode()
        self.draw_rectangle_button.config(relief="sunken")


    def disable_rectangle_mode(self):
        # Add logic to disable rectangle mode
        self.frame_image.draw_rectangle_mode = False
        # Implement whatever logic is necessary to disable rectangle drawing mode
        self.draw_section_button.config(relief='raised')
        self.draw_rectangle_button.config(relief="raised")


    def measure(self):
        if self.measure_mode is True:
            self.mw.on_window_close()
            self.measure_tool.config(relief='raised')
            self.measure_mode = False
        else:
            self.disable_draw_mode()
            self.disable_rectangle_mode()
            self.mw = MeasurementWindow(self.frame_image, self)
            self.measure_tool.config(relief='sunken')
            self.measure_mode = True

    def set_section_view(self, section_view_window):
        self.section_view = section_view_window
