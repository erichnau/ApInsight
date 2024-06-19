import tkinter as tk
from tkinter import filedialog, INSERT
import os
import numpy as np
from PIL import Image, ImageTk
import platform
from matplotlib import pyplot as plt
from os import path

import GPR_func.GPR_data_formats as gpr
from GPR_func.GPR_proc import bin_by


class TopFrameToolsVelocity(tk.Frame):
    def __init__(self, master, callback_display_data, callback_pan, callback_zoom, callback_home):
        super().__init__(master)

        self.master = master
        self.callback_display_data = callback_display_data
        self.callback_pan = callback_pan
        self.callback_home = callback_home
        self.callback_zoom = callback_zoom
        self.create_widgets()

        self.velo_model = []

    def create_widgets(self):
        # First row - first frame for file operations
        file_operations_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        file_operations_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.button_open = tk.Button(file_operations_frame, text='Open file', command=self.open_file)
        self.button_open.pack(side="left", padx=5, pady=5)

        self.previous_file = tk.Button(file_operations_frame, text='Previous', command=self.previous_profile)
        self.previous_file.pack(side="left", padx=5, pady=5)

        self.next_file = tk.Button(file_operations_frame, text='Next', command=self.next_profile)
        self.next_file.pack(side="left", padx=5, pady=5)

        self.button_exit = tk.Button(file_operations_frame, text='Exit', command=self.exit_viewer)
        self.button_exit.pack(side="left", padx=5, pady=5)

        # First row - second frame for project and line labels
        project_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        project_frame.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        self.project_label = tk.Label(project_frame, text='Project: ', font=('Arial', 11, 'bold'))
        self.project_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.project_label2 = tk.Label(project_frame, text='no file', font=('Arial', 11, 'bold'))
        self.project_label2.pack(side=tk.LEFT, padx=5, pady=5)

        self.line_label = tk.Label(project_frame, text=', Line nr.: ', font=('Arial', 11, 'bold'))
        self.line_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.line_label2 = tk.Label(project_frame, text='no file', font=('Arial', 11, 'bold'))
        self.line_label2.pack(side=tk.LEFT, padx=5, pady=5)

        # Second row - first frame for zoom and pan buttons
        zoom_pan_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        zoom_pan_frame.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.home = tk.Button(zoom_pan_frame, text='Zoom to full extent', command=self.callback_home)
        self.home.pack(side=tk.LEFT, padx=5, pady=5)

        self.zoom_image = Image.open("zoom.ico").resize((20, 20), Image.LANCZOS)
        self.zoom_photo = ImageTk.PhotoImage(self.zoom_image)

        self.zoom_button = tk.Button(zoom_pan_frame, image=self.zoom_photo, command=self.toggle_zoom)
        self.zoom_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.pan_image = Image.open("pan.ico").resize((20, 20), Image.LANCZOS)
        self.pan_photo = ImageTk.PhotoImage(self.pan_image)

        self.pan_button = tk.Button(zoom_pan_frame, image=self.pan_photo, command=self.toggle_pan)
        self.pan_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Second row - second frame for velocity analysis and model buttons
        velo_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        velo_frame.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        self.velo_analysis = tk.IntVar()
        self.velo_checkbutton = tk.Checkbutton(velo_frame, variable=self.velo_analysis, text='Velocity Analysis',
                                               onvalue=1, offvalue=0, command=self.velo_bindings,
                                               font=('Arial', 11, 'bold'))
        self.velo_checkbutton.pack(side=tk.LEFT, padx=5, pady=5)

        self.velocity_label = tk.Label(velo_frame, text='Velocity:', font=('Arial', 11))
        self.velocity_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.velo_value = tk.Entry(velo_frame, width=10, validate='key',
                                   validatecommand=(self.register(self.validate_velo), '%P'))
        self.velo_value.pack(side=tk.LEFT, padx=5, pady=5)
        self.velo_value.insert(tk.INSERT, '0.1')

        self.velo_label = tk.Label(velo_frame, text='m/ns', font=('Arial', 11))
        self.velo_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.inc_vel = tk.Button(velo_frame, text='+', command=self.increase_velo)
        self.inc_vel.pack(side=tk.LEFT, padx=2, pady=2)

        self.dec_vel = tk.Button(velo_frame, text='-', command=self.decrease_velo)
        self.dec_vel.pack(side=tk.LEFT, padx=2, pady=2)

        self.add_velo_value = tk.Button(velo_frame, text='Add to model', command=self.add_velocity_to_model)
        self.add_velo_value.pack(side=tk.LEFT, padx=5, pady=5)

        self.load_velo_model = tk.Button(velo_frame, text='Load velocity model', command=self.load_velocity_model)
        self.load_velo_model.pack(side=tk.LEFT, padx=5, pady=5)

        self.save_velo_model = tk.Button(velo_frame, text='Save velocity model', command=self.save_velocity_model)
        self.save_velo_model.pack(side=tk.LEFT, padx=5, pady=5)

        self.plot_velo_model = tk.Button(velo_frame, text='Plot velocity model', command=self.plot_velocity_model)
        self.plot_velo_model.pack(side=tk.LEFT, padx=5, pady=5)

        self.velo_model = []

    def open_file(self, file_path=None):
        if file_path == None:
            file_path = filedialog.askopenfilename(filetypes=[('DAT', '*.dat')])   #, ("RD3", '*.rd3'), ('RD7', '*.rd7'), ('NPY', '*.npy')])

        if file_path:
            file_root, _ = os.path.splitext(file_path)
            info = gpr.read_par(file_root)
            data = gpr.read_dat(file_root)
            vmax = np.max(data)
            vmin = np.min(data)
            self.callback_display_data(data, info, vmax, vmin)

        self.folder = file_path[:file_path.rfind('/')]  # [:-31] to get main folder(after #)

        proj_name_temp = file_path[file_path.rfind('/') + 1:]
        ind1 = proj_name_temp.rfind('_')
        temp_1 = proj_name_temp[:proj_name_temp.rfind('_')]
        ind2 = temp_1.rfind('_')

        self.line_nr = proj_name_temp[:ind1][ind2 + 1:]
        self.project_name = proj_name_temp[:ind1][:ind2]
        self.appendix = proj_name_temp[ind1:].rsplit('.')[0]
        self.extension = proj_name_temp[ind1:].rsplit('.')[1]

        self.project_label2.config(text=self.project_name)
        self.line_label2.config(text=self.line_nr)


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
            self.section_canvas.canvas.mpl_connect('button_press_event', self.section_canvas.velo_click)
            self.section_canvas.canvas.mpl_connect('button_release_event', self.section_canvas.velo_release)

            if platform.system() == 'Windows':
                self.section_canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)
            else:
                self.bind_all("<Button-4>", self.on_mouse_wheel)
                self.bind_all("<Button-5>", self.on_mouse_wheel)

            self.bind_all("<space>", self.add_velocity_to_model)

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

    def increase_velo(self):
        speed_of_light_m_ns = 0.299792458  # Speed of light in m/ns
        current_value = float(self.velo_value.get())
        new_value = round(current_value + 0.0025, 4)

        if new_value > speed_of_light_m_ns:
            new_value = speed_of_light_m_ns
            print(f"Velocity value cannot exceed the speed of light ({speed_of_light_m_ns} m/ns). Setting to maximum.")

        self.velo_value.delete(0, 'end')
        self.velo_value.insert(tk.INSERT, new_value)
        self.section_canvas.plot_hyperbola()


    def decrease_velo(self):
        value = round(float(self.velo_value.get()) - 0.0025, 4)
        self.velo_value.delete(0, 'end')
        self.velo_value.insert(tk.INSERT, value)
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


    def point_exists_in_model(self, x, y, velo):
        for value in self.velo_model:
            if (value[1] == x) and (value[2] == y) and (value[3] == velo):
                return True
        return False


    def add_velocity_to_model(self, event=None):
        velo_value = []

        if hasattr(self.section_canvas, 'hyperbola') and self.section_canvas.hyperbola:
            remove_hyp = self.section_canvas.hyperbola.pop(0)
            remove_hyp.remove()

        # Get the current point
        current_x = round(self.section_canvas.x, 3)
        current_y = round(self.section_canvas.y, 3)
        current_velo = self.velo_value.get()

        # Check if the point already exists in the model
        if self.point_exists_in_model(current_x, current_y, current_velo):
            print('Point already exists in the model.')
            return

        # Add the point to the model
        self.section_canvas.velo_point = self.section_canvas.ax.plot(self.section_canvas.x, self.section_canvas.y,
                                                                     marker="o", markersize=5, markeredgecolor="red",
                                                                     markerfacecolor="red")
        label = current_velo + ' m/ns'
        self.section_canvas.ax.annotate(label, (self.section_canvas.x, self.section_canvas.y),
                                        textcoords="offset points", xytext=(0, 10), ha='center')

        velo_value.append(self.line_nr)
        velo_value.append(current_x)
        velo_value.append(current_y)
        velo_value.append(current_velo)

        self.velo_model.append(velo_value)

        self.section_canvas.canvas.draw()


    def plot_velocity_model(self):
        velo_for_plot_x = []
        velo_for_plot_y = []

        for element in self.velo_model:
            velo_for_plot_x.append(float(element[2]))
            velo_for_plot_y.append(float(element[3]))

        x = np.array(velo_for_plot_x)
        y = np.array(velo_for_plot_y)

        # bin the values and determine the envelopes
        df = bin_by(x, y, nbins=6, bins=None)

        cols = ['#EE7550', '#F19463', '#F6B176']

        plt.ion()
        fig = plt.figure(111)
        a = fig.add_subplot()
        # plot the 3rd stdv
        a.fill_between(df.x, df['5th'], df['95th'], alpha=0.7, color=cols[2])
        a.fill_between(df.x, df['10th'], df['90th'], alpha=0.7, color=cols[1])
        a.fill_between(df.x, df['25th'], df['75th'], alpha=0.7, color=cols[0])
        # plt the line
        plt.plot(df.x, df['median'], color='black', alpha=0.7, linewidth=1.5)

        # plot the points
        a.scatter(velo_for_plot_x, velo_for_plot_y, facecolors='blue', edgecolors='0', s=5, lw=1)

        # plt.savefig('fig1.png', facecolor='white', edgecolor='none')


    def save_velocity_model(self):
        default_filename = self.project_name + '_Velocity_model.txt'

        fileformat = [('GPR velocity model', '*.txt')]
        file = filedialog.asksaveasfilename(filetype=fileformat, defaultextension=fileformat, initialdir=self.folder,
                                            initialfile=default_filename, parent=self.master)

        f = open(file, 'w')

        for entry in self.velo_model:
            f.write('%s,%s,%s,%s\n' % (entry[0], entry[1], entry[2], entry[3]))

        f.close()

        f = open(file, 'a')

        f.write('\n')
        f.write('Median' + '\n')

        velo_for_plot_x = []
        velo_for_plot_y = []

        for element in self.velo_model:
            velo_for_plot_x.append(float(element[2]))
            velo_for_plot_y.append(float(element[3]))

        x = np.array(velo_for_plot_x)
        y = np.array(velo_for_plot_y)

        # bin the values and determine the envelopes
        df = bin_by(x, y, nbins=6, bins=None)
        df_x_as_string = df.x.to_string(header=False, index=False).strip().split('\n')
        df_median_as_string = df['median'].to_string(header=False, index=False).strip().split('\n')
        for i in range(len(df_x_as_string) - 1):
            f.write(df_x_as_string[i] + ',' + df_median_as_string[i] + '\n')

        f.close()

    def load_velocity_model(self):
        fileformat = [('GPR velocity model', '*.txt')]

        model_name = filedialog.askopenfilename(initialdir=self.folder, title='Open velocity model',
                                                filetypes=fileformat, parent=self.master)
        file = open(model_name, 'r')

        line_num = 0
        next_part = 999
        for line in file.readlines():
            line_num += 1
            if line.find('Median') >= 0:
                next_part = line_num

        self.velo_model = []
        file = open(model_name, 'r')
        for line in file.readlines()[:next_part - 2]:
            velo_model_temp = []
            single_line = line.rsplit(',')
            velo_model_temp.append(single_line[0])
            velo_model_temp.append(single_line[1])
            velo_model_temp.append(single_line[2])
            velo_model_temp.append(single_line[3].strip('\n'))
            self.velo_model.append(velo_model_temp)

        self.plot_saved_model()

    def plot_saved_model(self):
        if hasattr(self.section_canvas, 'hyperbola') and self.section_canvas.hyperbola:
            remove_hyp = self.section_canvas.hyperbola.pop(0)
            remove_hyp.remove()

        if hasattr(self.section_canvas, 'velo_point') and self.section_canvas.velo_point:
            remove_pnt = self.section_canvas.velo_point.pop()
            remove_pnt.remove()

        for entry in self.velo_model:
            if entry[0] == self.line_nr:
                self.section_canvas.point = self.section_canvas.ax.plot(float(entry[1]), float(entry[2]), marker="o", markersize=5,
                                             markeredgecolor="red",
                                             markerfacecolor="red")
                label = entry[3] + ' m/ns'
                self.section_canvas.ax.annotate(label, (float(entry[1]), float(entry[2])), textcoords="offset points", xytext=(0, 10),
                             ha='center')

        self.section_canvas.canvas.draw()

    def next_profile(self):
        c = 1

        def open_next(c):
            new_number = format((int(self.line_nr) + c), "03d")
            next_profile = self.folder + '/' + self.project_name + '_' + new_number + self.appendix + '.' + self.extension

            if path.exists(next_profile):
                global file_name_velo
                file_name_velo = self.folder + '/' + self.project_name + '_' + new_number + self.appendix + '.' + self.extension
                self.file = file_name_velo
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
            new_number = format((int(self.line_nr) - c), "03d")
            next_profile = self.folder + '/' + self.project_name + '_' + new_number + self.appendix + '.' + self.extension

            if path.exists(next_profile):
                global file_name_velo
                file_name_velo = self.folder + '/' + self.project_name + '_' + new_number + self.appendix + '.' + self.extension
                self.file = file_name_velo
                self.open_file(self.file)
            else:
                if c <= 10:
                    c += 1
                    open_previous(c)

        open_previous(c)

        self.plot_saved_model()

