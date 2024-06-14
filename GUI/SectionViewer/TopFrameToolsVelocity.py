import tkinter as tk
from tkinter import filedialog
import os
import numpy as np

import GPR_func.GPR_data_formats as gpr


class TopFrameToolsVelocity(tk.Frame):
    def __init__(self, parent, callback_display_data, callback_pan, callback_zoom, callback_home):
        super().__init__(parent)
        self.callback_display_data = callback_display_data
        self.callback_pan = callback_pan
        self.callback_home = callback_home
        self.callback_zoom = callback_zoom
        self.create_widgets()

    def create_widgets(self):
        self.button_open = tk.Button(self, text='Open file', command=self.open_file)
        self.button_open.grid(row=0, column=0)

        self.button_exit = tk.Button(self, text='Exit', command=self.exit_viewer)
        self.button_exit.grid(row=0, column=1)

        self.contrast_frame = tk.Frame(self, bg="white", width=150, height=25, highlightbackground="black",
                                       highlightthickness=1)
        self.contrast_frame.grid(row=1, column=0)

        self.button_increase_contrast = tk.Button(self.contrast_frame, text='+', command=self.increase_contrast)
        self.button_increase_contrast.grid(row=1, column=2)

        self.button_decrease_contrast = tk.Button(self.contrast_frame, text='-', command=self.decrease_contrast)
        self.button_decrease_contrast.grid(row=1, column=0)

        self.label_contrast = tk.Label(self.contrast_frame, text='Contrast')
        self.label_contrast.grid(row=1, column=1)

        self.zoom = tk.Button(self, text='Zoom In', command=self.callback_zoom)
        self.zoom.grid(row=2, column=0)

        self.home = tk.Button(self, text='Home', command=self.callback_home)
        self.home.grid(row=2, column=1)

        self.pan_button = tk.Button(self, text='Pan', command=self.callback_pan)
        self.pan_button.grid(row=2, column=2)

        self.velocity_label = tk.Label(self, text='Velocity:')
        self.velocity_label.grid(row=3, column=0)

        self.velo_value = tk.Entry(self, width=15)
        self.velo_value.grid(row=3, column=1)
        self.velo_value.insert(tk.INSERT, '0.1')

        self.velo_label = tk.Label(self, text='m/ns')
        self.velo_label.grid(row=3, column=2)

        self.velo_analysis = tk.IntVar()
        self.velo_checkbutton = tk.Checkbutton(self, variable=self.velo_analysis, text='Velocity Analysis',
                                               onvalue=1, offvalue=0, command=self.bindings)
        self.velo_checkbutton.grid(row=3, column=3)

        self.inc_vel = tk.Button(self, text='+', command=self.increase_velo)
        self.inc_vel.grid(row=3, column=4)

        self.dec_vel = tk.Button(self, text='-', command=self.decrease_velo)
        self.dec_vel.grid(row=3, column=5)

        self.add_velo_value = tk.Button(self, text='Add to model', command=self.add_velocity_to_model)
        self.add_velo_value.grid(row=4, column=0)

        self.plot_velo_model = tk.Button(self, text='Plot velocity model', command=self.plot_velocity_model)
        self.plot_velo_model.grid(row=4, column=1)

        self.save_velo_model = tk.Button(self, text='Save velocity model', command=self.save_velocity_model)
        self.save_velo_model.grid(row=4, column=2)

        self.load_velo_model = tk.Button(self, text='Load velocity model', command=self.load_velocity_model)
        self.load_velo_model.grid(row=4, column=3)

        self.previous_file = tk.Button(self, text='Previous', command=self.previous_profile)
        self.previous_file.grid(row=4, column=4)

        self.next_file = tk.Button(self, text='Next', command=self.next_profile)
        self.next_file.grid(row=4, column=5)

        self.project_label = tk.Label(self, text='Project: ', font=('Arial 11 bold'))
        self.project_label.grid(row=0, column=6)

        self.project_label2 = tk.Label(self, text='no file', font=('Arial 11 bold'))
        self.project_label2.grid(row=0, column=7)

        self.line_label = tk.Label(self, text=',   Line nr.: ', font=('Arial 11 bold'))
        self.line_label.grid(row=0, column=8)

        self.line_label2 = tk.Label(self, text='no file', font=('Arial 11 bold'))
        self.line_label2.grid(row=0, column=9)

        self.velo_model = []
    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[('DAT', '*.dat'), ("RD3", '*.rd3'), ('RD7', '*.rd7'), ('NPY', '*.npy')])
        if file_path:
            file_root, _ = os.path.splitext(file_path)
            info = gpr.read_par(file_root)
            data = gpr.read_dat(file_root)
            vmax = np.max(data)
            vmin = np.min(data)
            self.callback_display_data(data, info, vmax, vmin)



    def exit_viewer(self):
        self.master.destroy()

    def increase_contrast(self):
        pass

    def decrease_contrast(self):
        pass

    def bindings(self):
        pass

    def increase_velo(self):
        pass

    def decrease_velo(self):
        pass

    def add_velocity_to_model(self):
        pass

    def plot_velocity_model(self):
        pass

    def save_velocity_model(self):
        pass

    def load_velocity_model(self):
        pass

    def previous_profile(self):
        pass

    def next_profile(self):
        pass


