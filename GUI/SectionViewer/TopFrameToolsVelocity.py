import tkinter as tk
from tkinter import filedialog
import os
from os import path
import numpy as np
from PIL import Image, ImageTk
import platform

import GPR_func.GPR_data_formats as gpr
from GPR_func.GPR_proc import bin_by
from GUI.SectionViewer.VelocityModelPlotter import VelocityModelPlot


class TopFrameToolsVelocity(tk.Frame):
    def __init__(self, master, callback_display_data, callback_pan, callback_zoom, callback_home, callback_save_image):
        super().__init__(master)

        self.master = master
        self.callback_display_data = callback_display_data
        self.callback_pan = callback_pan
        self.callback_home = callback_home
        self.callback_zoom = callback_zoom
        self.callback_save_image = callback_save_image

        self.tooltip_bindings = {} # Initialize tooltip_bindings here
        self.annotations = []
        self.velo_points = []
        self.project_name = None

        self.create_widgets()

        self.velo_model = []

    def create_widgets(self):
        frame_height = 50  # Set a fixed height for all frames

        # Configure grid rows and columns to have fixed heights
        self.grid_rowconfigure(0, minsize=frame_height)
        self.grid_rowconfigure(1, minsize=frame_height)

        # First row - first frame for file operations
        file_operations_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        file_operations_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.button_open = tk.Button(file_operations_frame, text='Open file', command=self.open_file)
        self.button_open.pack(side="left", padx=5, pady=5)

        self.button_exit = tk.Button(file_operations_frame, text='Exit', command=self.exit_viewer)
        self.button_exit.pack(side="left", padx=5, pady=5)

        self.previous_file = tk.Button(file_operations_frame, text='Previous', command=self.previous_profile, state='disabled')
        self.previous_file.pack(side="left", padx=5, pady=5)

        self.next_file = tk.Button(file_operations_frame, text='Next', command=self.next_profile, state='disabled')
        self.next_file.pack(side="left", padx=5, pady=5)

        self.export_image = tk.Button(file_operations_frame, text='Save image', command=self.callback_save_image, state='disabled')
        self.export_image.pack(side='left', padx=5, pady=5)

        # First row - second frame for project and line labels
        project_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        project_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        self.project_label = tk.Label(project_frame, text='Project: ', font=('Arial', 11, 'bold'))
        self.project_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.project_label2 = tk.Label(project_frame, text='no file opened', font=('Arial', 11))
        self.project_label2.pack(side=tk.LEFT, padx=5, pady=5)

        self.line_label = tk.Label(project_frame, text='    Line nr.: ', font=('Arial', 11, 'bold'))
        self.line_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.line_label2 = tk.Label(project_frame, text='no file opened', font=('Arial', 11))
        self.line_label2.pack(side=tk.LEFT, padx=5, pady=5)

        # Second row - first frame for zoom, pan, and contrast buttons
        zoom_pan_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        zoom_pan_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        self.home = tk.Button(zoom_pan_frame, text='Zoom to full extent', command=self.callback_home, state='disabled')
        self.home.pack(side=tk.LEFT, padx=5, pady=5)

        self.zoom_image = Image.open("zoom.ico").resize((20, 20), Image.LANCZOS)
        self.zoom_photo = ImageTk.PhotoImage(self.zoom_image)

        self.zoom_button = tk.Button(zoom_pan_frame, image=self.zoom_photo, command=self.toggle_zoom, state='disabled')
        self.zoom_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.pan_image = Image.open("pan.ico").resize((20, 20), Image.LANCZOS)
        self.pan_photo = ImageTk.PhotoImage(self.pan_image)

        self.pan_button = tk.Button(zoom_pan_frame, image=self.pan_photo, command=self.toggle_pan, state='disabled')
        self.pan_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Add contrast controls to the zoom_pan_frame
        self.label_contrast = tk.Label(zoom_pan_frame, text='Contrast')
        self.label_contrast.pack(side=tk.LEFT, padx=5, pady=5)

        self.button_increase_contrast = tk.Button(zoom_pan_frame, text='+', command=self.increase_contrast, state='disabled')
        self.button_increase_contrast.pack(side=tk.LEFT, padx=2, pady=2)

        self.button_decrease_contrast = tk.Button(zoom_pan_frame, text='-', command=self.decrease_contrast, state='disabled')
        self.button_decrease_contrast.pack(side=tk.LEFT, padx=2, pady=2)

        # Second row - second frame for velocity analysis and model buttons
        velo_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        velo_frame.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")

        self.velo_analysis = tk.IntVar()
        self.velo_checkbutton = tk.Checkbutton(velo_frame, variable=self.velo_analysis, text='Velocity Analysis',
                                               onvalue=1, offvalue=0, state='disabled', command=self.velo_bindings,
                                               font=('Arial', 11))
        self.velo_checkbutton.pack(side=tk.LEFT, padx=5, pady=5)

        self.velocity_label = tk.Label(velo_frame, text='Velocity:', font=('Arial', 11))
        self.velocity_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.velo_value = tk.Entry(velo_frame, width=10, validate='key',
                                   validatecommand=(self.register(self.validate_velo), '%P'))
        self.velo_value.pack(side=tk.LEFT, padx=5, pady=5)
        self.velo_value.insert(tk.INSERT, '0.1')

        self.velo_label = tk.Label(velo_frame, text='m/ns', font=('Arial', 11))
        self.velo_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.inc_vel = tk.Button(velo_frame, text='+', command=self.increase_velo, state='disabled')
        self.inc_vel.pack(side=tk.LEFT, padx=2, pady=2)

        self.dec_vel = tk.Button(velo_frame, text='-', command=self.decrease_velo, state='disabled')
        self.dec_vel.pack(side=tk.LEFT, padx=2, pady=2)

        self.add_velo_value = tk.Button(velo_frame, text='Add to model', command=self.add_velocity_to_model, state='disabled')
        self.add_velo_value.pack(side=tk.LEFT, padx=5, pady=5)

        self.load_velo_model = tk.Button(velo_frame, text='Load velocity model', command=self.load_velocity_model, state='disabled')
        self.load_velo_model.pack(side=tk.LEFT, padx=5, pady=5)

        self.save_velo_model = tk.Button(velo_frame, text='Save velocity model', command=self.save_velocity_model, state='disabled')
        self.save_velo_model.pack(side=tk.LEFT, padx=5, pady=5)

        self.plot_velo_model = tk.Button(velo_frame, text='Plot velocity model', command=self.plot_velocity_model, state='disabled')
        self.plot_velo_model.pack(side=tk.LEFT, padx=5, pady=5)

        self.velo_model = []

        self.add_tooltips()

    def add_tooltips(self):
        self.bind_tooltip(self.zoom_button, 'Enable zoom mode')
        self.bind_tooltip(self.pan_button, 'Enable pan mode. Use left mousebutton for panning and right mouse button for zooming along the two axis')
        self.bind_tooltip(self.inc_vel, 'Increase the velocity value, or use the mouse wheel to adjust the velocity once the hyperbola has been drawn')
        self.bind_tooltip(self.dec_vel, 'Increase the velocity value, or use the mouse wheel to adjust the velocity once the hyperbola has been drawn')
        self.bind_tooltip(self.add_velo_value, 'Add the velocity value to the model, or use the spacebar')

    def bind_tooltip(self, widget, text):
        tooltip = ToolTip(widget, text)
        self.tooltip_bindings[widget] = tooltip

    def open_file(self, file_path=None):
        if file_path is None:
            file_path = filedialog.askopenfilename(filetypes=[('DAT', '*.dat')])

        if not file_path:
            self.master.lift()
            return

        file_root, _ = os.path.splitext(file_path)
        info = gpr.read_par(file_root)
        data = gpr.read_dat(file_root)
        vmax = np.max(data)
        vmin = np.min(data)

        self.callback_display_data(data, info, vmax, vmin)
        self.activate_buttons()

        self.folder = file_path[:file_path.rfind('/')]

        proj_name_temp = file_path[file_path.rfind('/') + 1:]
        ind1 = proj_name_temp.rfind('_')
        temp_1 = proj_name_temp[:proj_name_temp.rfind('_')]
        ind2 = temp_1.rfind('_')

        new_line_nr = proj_name_temp[:ind1][ind2 + 1:]
        self.line_nr_digits = len(new_line_nr)  # Store the length of the line number
        new_project_name = proj_name_temp[:ind1][:ind2]
        new_appendix = proj_name_temp[ind1:].rsplit('.')[0]
        new_extension = proj_name_temp[ind1:].rsplit('.')[1]

        # Check if the project name has changed
        if new_project_name != self.project_name:
            self.velo_model = []  # Reset the velocity model
            self.plot_velo_model.config(state='disabled')
            self.save_velo_model.config(state='disabled')

        self.line_nr = int(new_line_nr)  # Convert the line number to an integer
        self.project_name = new_project_name
        self.appendix = new_appendix
        self.extension = new_extension

        self.project_label2.config(text=self.project_name)
        self.line_label2.config(text=str(self.line_nr).zfill(self.line_nr_digits))

        self.master.lift()

    def activate_buttons(self):
        self.previous_file.config(state='normal')
        self.next_file.config(state='normal')
        self.export_image.config(state='normal')
        self.home.config(state='normal')
        self.zoom_button.config(state='normal')
        self.pan_button.config(state='normal')
        self.button_decrease_contrast.config(state='normal')
        self.button_increase_contrast.config(state='normal')
        self.velo_checkbutton.config(state='normal')
        self.dec_vel.config(state='normal')
        self.inc_vel.config(state='normal')
        self.add_velo_value.config(state='normal')
        self.load_velo_model.config(state='normal')
        self.save_velo_model.config(state='normal')


    def activate_plot(self):
        self.plot_velo_model.config(state='normal')

    def activate_save(self):
        self.save_velo_model.config(state='normal')


    def toggle_pan(self):
        if self.pan_button.config('relief')[-1] == 'sunken':
            self.pan_button.config(relief="raised")
            self.section_canvas.config(cursor="hand2")
        else:
            self.pan_button.config(relief="sunken")
            self.zoom_button.config(relief="raised")


        self.callback_pan()
        self.section_canvas.config(cursor="hand2")


    def toggle_zoom(self):
        if self.zoom_button.config('relief')[-1] == 'sunken':
            self.zoom_button.config(relief="raised")
        else:
            self.zoom_button.config(relief="sunken")
            self.pan_button.config(relief="raised")

        self.callback_zoom()

    def save_image(self):
        pass


    def exit_viewer(self):
        self.master.destroy()


    def increase_contrast(self):
        vmax = float(self.section_canvas.image.get_clim()[1]) / 1.15
        vmin = float(self.section_canvas.image.get_clim()[0]) / 1.15
        self.section_canvas.update_contrast(vmin, vmax)


    def decrease_contrast(self):
        vmax = float(self.section_canvas.image.get_clim()[1]) * 1.15
        vmin = float(self.section_canvas.image.get_clim()[0]) * 1.15
        self.section_canvas.update_contrast(vmin, vmax)


    def velo_bindings(self):
        if self.velo_analysis.get() == 1:
            self.velo_analysis.set(1)
            self.section_canvas.canvas.mpl_connect('button_press_event', self.section_canvas.on_click)

            if platform.system() == 'Windows':
                self.section_canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)
            else:
                self.bind_all("<Button-4>", self.on_mouse_wheel)
                self.bind_all("<Button-5>", self.on_mouse_wheel)

            self.bind_all("<space>", self.add_velocity_to_model)
            self.bind_all("<Delete>", self.section_canvas.delete_selected_point)

        elif self.velo_analysis.get() == 0:
            self.velo_analysis.set(0)
            self.section_canvas.canvas.mpl_disconnect('button_press_event')
            self.section_canvas.canvas.mpl_disconnect('button_release_event')

            if platform.system() == 'Windows':
                self.section_canvas.unbind_all("<MouseWheel>")
            else:
                self.unbind_all("<Button-4>")
                self.unbind_all("<Button-5>")

            self.unbind_all("<space>")
            self.unbind_all("<Delete>")

    def increase_velo(self):
        speed_of_light_m_ns = 0.299792458  # Speed of light in m/ns
        current_value = float(self.velo_value.get())
        new_value = round(current_value + 0.0025, 4)

        if new_value > speed_of_light_m_ns:
            new_value = speed_of_light_m_ns
            print(f"Signal velocity value cannot exceed the speed of light ({speed_of_light_m_ns} m/ns). Setting to maximum.")

        self.velo_value.delete(0, 'end')
        self.velo_value.insert(tk.INSERT, new_value)

        if hasattr(self.section_canvas, 'hyperbola') and self.section_canvas.hyperbola:
            self.section_canvas.plot_hyperbola()


    def decrease_velo(self):
        current_value = float(self.velo_value.get())
        new_value = round(current_value - 0.0025, 4)

        if new_value < 0.0025:
            new_value = 0.0025
            print('Signal velocity must be above 0. Setting to 0.25 m/ns')

        self.velo_value.delete(0, 'end')
        self.velo_value.insert(tk.INSERT, new_value)
        # Check if self.section_canvas has hyperbola drawn
        if hasattr(self.section_canvas, 'hyperbola') and self.section_canvas.hyperbola:
            self.section_canvas.plot_hyperbola()


    def validate_velo(self, proposed_value):
        if proposed_value == "":  # Allow the entry to be empty
            return True
        try:
            value = float(proposed_value)
            if value > 0.299792458:  # Speed of light in m/ns
                print(f"Velocity value cannot exceed the speed of light (0.299792458 m/ns).")
                return False
            return True
        except ValueError:
            return False


    def on_mouse_wheel(self, event):
        if event.num == 5 or event.delta == -120:
            self.decrease_velo()
        if event.num == 4 or event.delta == 120:
            self.increase_velo()

    def point_exists_in_model(self, x, y):
        for index, value in enumerate(self.velo_model):
            if (value[1] == x) and (value[2] == y):
                return True, index
        return False, -1

    def add_velocity_to_model(self, event=None):
        velo_value = []

        if hasattr(self.section_canvas, 'hyperbola') and self.section_canvas.hyperbola:
            remove_hyp = self.section_canvas.hyperbola.pop(0)
            remove_hyp.remove()

        # Get the current point
        current_x = round(self.section_canvas.x, 3)
        current_y = round(self.section_canvas.y, 3)
        current_velo = self.velo_value.get()

        if self.section_canvas.selected_point:
            if self.update_existing_point(current_x, current_y, current_velo):
                return

        # Add the point to the model
        velo_point, = self.section_canvas.ax.plot(self.section_canvas.x, self.section_canvas.y,
                                                  marker="o", markersize=5, markeredgecolor="red",
                                                  markerfacecolor="red")
        label = current_velo + ' m/ns'
        annotation = self.section_canvas.ax.annotate(label, (self.section_canvas.x, self.section_canvas.y),
                                                     textcoords="offset points", xytext=(0, 10), ha='center')

        self.annotations.append(annotation)
        self.velo_points.append((velo_point, current_velo, annotation))  # Store the point, velocity, and annotation

        velo_value.append(self.line_nr)
        velo_value.append(current_x)
        velo_value.append(current_y)
        velo_value.append(current_velo)

        self.velo_model.append(velo_value)

        self.section_canvas.canvas.draw()
        if len(self.velo_model) >= 1:
            self.activate_save()
        if len(self.velo_model) >= 2:
            self.activate_plot()

    def update_existing_point(self, current_x, current_y, current_velo):
        for point, velo, annotation in self.velo_points:
            # Find the selected point in the list
            if point == self.section_canvas.selected_point:
                # Check if the velocity value has changed
                if velo != current_velo:
                    # Remove the point and annotation
                    point.remove()
                    annotation.remove()

                    # Remove the point from the list
                    self.velo_points.remove((point, velo, annotation))

                    # Add the updated point and annotation
                    velo_point, = self.section_canvas.ax.plot(current_x, current_y,
                                                              marker="o", markersize=5, markeredgecolor="red",
                                                              markerfacecolor="red")
                    label = current_velo + ' m/ns'
                    annotation = self.section_canvas.ax.annotate(label, (current_x, current_y),
                                                                 textcoords="offset points", xytext=(0, 10),
                                                                 ha='center')

                    self.annotations.append(annotation)
                    self.velo_points.append((velo_point, current_velo, annotation))

                    for value in self.velo_model:
                        if float(value[1]) == current_x and float(value[2]) == current_y:
                            self.velo_model.remove(value)  # Remove the old value
                            break

                    velo_value = [self.line_nr, current_x, current_y, current_velo]
                    self.velo_model.append(velo_value)

                    self.section_canvas.canvas.draw()
                    print('Velocity value updated for the selected point.')
                    return True
                else:
                    print('Selected point already has the same velocity value.')
                    return True
        return False

    def plot_velocity_model(self):
        VelocityModelPlot(self.master, self.velo_model)

    def save_velocity_model(self):
        default_filename = self.project_name + '_Velocity_model.txt'

        fileformat = [('GPR velocity model', '*.txt')]
        file = filedialog.asksaveasfilename(filetype=fileformat, defaultextension='.txt', initialdir=self.folder,
                                            initialfile=default_filename, parent=self.master)

        if not file:
            return

        f = open(file, 'w')

        for entry in self.velo_model:
            f.write('%s,%s,%s,%s\n' % (entry[0], entry[1], entry[2], entry[3]))

        f.close()

        # Check if there are enough data points to perform binning
        if len(self.velo_model) >= 6:
            velo_for_plot_x = []
            velo_for_plot_y = []

            for element in self.velo_model:
                velo_for_plot_x.append(float(element[2]))
                velo_for_plot_y.append(float(element[3]))

            x = np.array(velo_for_plot_x)
            y = np.array(velo_for_plot_y)

            try:
                # bin the values and determine the envelopes
                df = bin_by(x, y, nbins=6, bins=None)
                df_x_as_string = df.x.to_string(header=False, index=False).strip().split('\n')
                df_median_as_string = df['median'].to_string(header=False, index=False).strip().split('\n')

                f = open(file, 'a')
                f.write('\n')
                f.write('Median' + '\n')

                for i in range(len(df_x_as_string) - 1):
                    f.write(df_x_as_string[i] + ',' + df_median_as_string[i] + '\n')

                f.close()
            except IndexError:
                # Handle the case where binning fails due to insufficient data points
                print("Not enough data points for binning. Saving individual velocity values only.")
        else:
            print("Not enough data points for binning. Saving individual velocity values only.")

    def load_velocity_model(self):
        fileformat = [('GPR velocity model', '*.txt')]

        model_name = filedialog.askopenfilename(initialdir=self.folder, title='Open velocity model',
                                                filetypes=fileformat, parent=self.master)

        # Check if a file was selected
        if not model_name:
            return

        with open(model_name, 'r') as file:
            line_num = 0
            next_part = 999
            for line in file.readlines():
                line_num += 1
                if line.find('Median') >= 0:
                    next_part = line_num

        self.velo_model = []
        with open(model_name, 'r') as file:
            for line in file.readlines()[:next_part - 2]:
                velo_model_temp = []
                single_line = line.rsplit(',')
                velo_model_temp.append(single_line[0])
                velo_model_temp.append(single_line[1])
                velo_model_temp.append(single_line[2])
                velo_model_temp.append(single_line[3].strip('\n'))
                self.velo_model.append(velo_model_temp)

        self.plot_saved_model()
        self.activate_plot()
        self.activate_save()

    def plot_saved_model(self):
        # Remove any existing hyperbola
        if hasattr(self.section_canvas, 'hyperbola') and self.section_canvas.hyperbola:
            remove_hyp = self.section_canvas.hyperbola.pop(0)
            remove_hyp.remove()

        # Remove all previous points and annotations from the canvas and lists
        if hasattr(self, 'velo_points') and self.velo_points:
            for point, _, annotation in self.velo_points:
                point.remove()
                annotation.remove()
            self.velo_points.clear()

        self.annotations.clear()

        # Plot the loaded model
        for entry in self.velo_model:
            print(int(entry[0]), self.line_nr)
            if int(entry[0]) == self.line_nr:
                velo_point, = self.section_canvas.ax.plot(float(entry[1]), float(entry[2]), marker="o", markersize=5,
                                                          markeredgecolor="red", markerfacecolor="red")
                label = entry[3] + ' m/ns'
                annotation = self.section_canvas.ax.annotate(label, (float(entry[1]), float(entry[2])),
                                                             textcoords="offset points", xytext=(0, 10), ha='center')

                self.annotations.append(annotation)
                self.velo_points.append((velo_point, entry[3], annotation))
                print(self.velo_points)

        # Redraw the canvas to update the changes
        self.section_canvas.canvas.draw()


    def next_profile(self):
        c = 1

        def open_next(c):
            new_number = format((self.line_nr + c), f"0{self.line_nr_digits}d")  # Format using line_nr_digits
            next_profile = f"{self.folder}/{self.project_name}_{new_number}{self.appendix}.{self.extension}"

            if path.exists(next_profile):
                self.file = next_profile
                self.open_file(self.file)
            else:
                if c <= 10:
                    c += 1
                    open_next(c)

        open_next(c)

        self.plot_saved_model()

    def previous_profile(self):
        c = 1

        def open_previous(c):
            new_number = format((self.line_nr - c), f"0{self.line_nr_digits}d")  # Format using line_nr_digits
            next_profile = f"{self.folder}/{self.project_name}_{new_number}{self.appendix}.{self.extension}"

            if path.exists(next_profile):
                self.file = next_profile
                self.open_file(self.file)
            else:
                if c <= 10:
                    c += 1
                    open_previous(c)

        open_previous(c)

        self.plot_saved_model()


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()
