import tkinter as tk
from tkinter import filedialog, INSERT
import os
import numpy as np
from PIL import Image, ImageTk
import platform

import GPR_func.GPR_data_formats as gpr


class TopFrameToolsVelocity(tk.Frame):
    def __init__(self, parent, callback_display_data, callback_pan, callback_zoom, callback_home):
        super().__init__(parent)
        self.callback_display_data = callback_display_data
        self.callback_pan = callback_pan
        self.callback_home = callback_home
        self.callback_zoom = callback_zoom
        self.create_widgets()

        self.velo_model = []


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

        self.home = tk.Button(self, text='Zoom to full extent', command=self.callback_home)
        self.home.grid(row=2, column=0)

        self.zoom_image = Image.open("zoom.ico")
        self.zoom_photo = ImageTk.PhotoImage(self.zoom_image)

        self.zoom_button = tk.Button(self, image=self.zoom_photo, command=self.toggle_zoom)
        self.zoom_button.grid(row=2, column=1)

        # Load the image using PIL
        self.pan_image = Image.open("pan.ico")
        self.pan_photo = ImageTk.PhotoImage(self.pan_image)

        # Create the custom pan button with the image
        self.pan_button = tk.Button(self, image=self.pan_photo, command=self.toggle_pan)
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
                                               onvalue=1, offvalue=0, command=self.velo_bindings)
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

        elif self.velo_analysis.get() == 0:
            self.velo_analysis.set(0)
            self.section_canvas.canvas.mpl_disconnect('button_press_event')
            self.section_canvas.canvas.mpl_disconnect('button_release_event')

            if platform.system() == 'Windows':
                self.section_canvas.unbind_all("<MouseWheel>")
            else:
                self.unbind_all("<Button-4>")
                self.unbind_all("<Button-5>")


    def increase_velo(self):
        value = round(float(self.velo_value.get()) + 0.0025, 4)
        self.velo_value.delete(0, 'end')
        self.velo_value.insert(INSERT, value)
        self.section_canvas.plot_hyperbola()


    def decrease_velo(self):
        value = round(float(self.velo_value.get()) - 0.0025, 4)
        self.velo_value.delete(0, 'end')
        self.velo_value.insert(INSERT, value)
        self.section_canvas.plot_hyperbola()


    def on_mouse_wheel(self, event):
        if event.num == 5 or event.delta == -120:
            self.decrease_velo()
        if event.num == 4 or event.delta == 120:
            self.increase_velo()


    def add_velocity_to_model(self):
        velo_value = []
        try:
            remove_hyp = self.section_canvas.hypberbola.pop()
            remove_hyp.remove()
        except:
            print('ft')

        self.section_canvas.velo_point = self.section_canvas.ax.plot(self.section_canvas.x, self.section_canvas.y, marker="o", markersize=5, markeredgecolor="red",
                                     markerfacecolor="red")
        label = self.velo_value.get() + ' m/ns'
        self.section_canvas.ax.annotate(label, (self.section_canvas.x, self.section_canvas.y), textcoords="offset points", xytext=(0, 10), ha='center')

        velo_value.append(self.line_nr)
        velo_value.append(round(self.section_canvas.x, 3))
        velo_value.append(round(self.section_canvas.y, 3))
        velo_value.append(self.velo_value.get())

        self.velo_model.append(velo_value)

        self.section_canvas.canvas.draw()


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


