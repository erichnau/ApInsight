from tkinter import *
import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
import matplotlib as mpl
from matplotlib import pyplot as plt
import numpy as np
from os import path

import GPR_func.GPR_data_formats
from GPR_func.GPR_proc import bin_by

from matplotlib.backend_bases import MouseButton
from math import sqrt
from screeninfo import get_monitors


monitors = get_monitors()
screen_res_primary = [monitors[0].height, monitors[0].width]

class MalaRd7(Frame, object):
    def __init__(self, master):
        super(MalaRd7, self). \
            __init__(master)
        self.pack()
        self.create_widgets()

    def create_widgets(self):

        self.tool_frame = Frame(self.master, borderwidth=5, relief='sunken')
        self.tool_frame.pack(ipady=20, fill='x')

        self.button_open = Button(self.tool_frame, text='Open file', command=self.openRD7)
        self.button_open.grid(row=0)

        self.button_exit = Button(self.tool_frame, text='Exit', command=self.exit_viewer)
        self.button_exit.grid(row=0, column=1)

        self.contrast_frame = Frame(self.tool_frame, bg="white", width=150, height=25, highlightbackground="black",
                                    highlightthickness=1)
        self.contrast_frame.grid(row=1, column=0)

        self.button_increase_contrast = Button(self.contrast_frame, text='+', command=self.increase_contrast)
        self.button_increase_contrast.grid(row=1, column=2)

        self.button_decrease_contrast = Button(self.contrast_frame, text='-', command=self.decrease_contrast)
        self.button_decrease_contrast.grid(row=1, column=0)

        self.contrast_slider = Scale(self.tool_frame, from_=1, to=100, length=200, orient=HORIZONTAL,
                                     command=self.slide_contrast)
        self.contrast_slider.set(1)
        self.contrast_slider.grid(row=1, column=1)

        self.label_contrast = Label(self.contrast_frame, text='Contrast')
        self.label_contrast.grid(row=1, column=1)

        self.velocity_label = Label(self.tool_frame, text='Velocity:')
        self.velocity_label.grid(row=1, column=2)

        self.velo_value = Entry(self.tool_frame, width=15)
        self.velo_value.grid(row=1, column=3)
        self.velo_value.insert(INSERT, '0.1')

        self.velo_label = Label(self.tool_frame, text='m/ns')
        self.velo_label.grid(row=1, column=4)

        self.velo_analysis = tk.IntVar()
        self.velo_checkbutton = Checkbutton(self.tool_frame, variable=self.velo_analysis, text='Velocity Analysis',
                                            onvalue=1, offvalue=0, command=self.bindings)
        self.velo_checkbutton.grid(row=1, column=5)

        self.inc_vel = Button(self.tool_frame, text='+', command=self.increase_velo)
        self.inc_vel.grid(row=1, column=6)

        self.dec_vel = Button(self.tool_frame, text='-', command=self.decrease_velo)
        self.dec_vel.grid(row=2, column=6)

        self.add_velo_value = Button(self.tool_frame, text='Add to model', command=self.add_velocity_to_model)
        self.add_velo_value.grid(row=2, column=5)

        self.plot_velo_model = Button(self.tool_frame, text='Plot velocity model', command=self.plot_velocity_model)
        self.plot_velo_model.grid(row=3, column=5)

        self.save_velo_model = Button(self.tool_frame, text='Save velocity model', command=self.save_velocity_model)
        self.save_velo_model.grid(row=3, column=6)

        self.load_velo_model = Button(self.tool_frame, text='Load velocity model', command=self.load_velocity_model)
        self.load_velo_model.grid(row=3, column=7)

        self.previous_file = Button(self.tool_frame, text='Previous', command=self.previous_profile)
        self.previous_file.grid(row=1, column=7)

        self.next_file = Button(self.tool_frame, text='Next', command=self.next_profile)
        self.next_file.grid(row=1, column=8)

        self.project_label = Label(self.tool_frame, text='Project: ', font=('Arial 11 bold'))
        self.project_label.grid(row=0, column=9)

        self.project_label2 = Label(self.tool_frame, text='no file', font=('Arial 11 bold'))
        self.project_label2.grid(row=0, column=10)

        self.line_label = Label(self.tool_frame, text=',   Line nr.: ', font=('Arial 11 bold'))
        self.line_label.grid(row=0, column=11)

        self.line_label2 = Label(self.tool_frame, text='no file', font=('Arial 11 bold'))
        self.line_label2.grid(row=0, column=12)

        self.velo_model = []

        self.img_frame = Frame(self.master)
        self.img_frame.pack()

        self.fig = plt.figure(figsize=(25, 5), dpi=100)
        self.a = self.fig.add_subplot()
        self.fig_canvas = FigureCanvasTkAgg(self.fig, master=self.img_frame)
        self.fig_canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)

        self.toolbar = NavigationToolbar2Tk(self.fig_canvas, self.img_frame)
        self.toolbar.update()

        self.toolbar.pack(side=tk.TOP)

        #self.fig_canvas.mpl_connect("key_press_event", lambda event: print(f"you pressed {event.key}"))
        #self.fig_canvas.mpl_connect("key_press_event", key_press_handler)

        try:
            if file_name_velo:
                self.file = file_name_velo
                self.openRD7()
        except:
            print('nooooooo')


    def openRD7(self):
        try:
            if file_name_velo:
                self.file = file_name_velo + '.dat'
        except:
            self.file = filedialog.askopenfilename(initialdir="/", title="Select GPR file",
                                                   filetypes=[('DAT', '*.dat'), ("RD3", "*.rd3"), ('RD7', '*.rd7'),
                                                              ('NPY', '*.npy')], parent=root_3)

        if self.file:
            if str(self.file)[-4:] == '.rd3' or str(self.file)[-4:] == '.rd7':
                self.filename = str(self.file)[:-4]
                self.max_data = self.readMALA(file_name=self.filename)[2]
                self.min_data = self.readMALA(file_name=self.filename)[3]
                self.show_profile(filename=self.filename, vmax=self.max_data, vmin=self.min_data)
            elif str(self.file)[-4:] == '.npy':
                self.filename = str(self.file)[:-4]
                self.data = np.asmatrix(np.load(self.file))
                self.max_data = np.max(self.data)
                self.min_data = np.min(self.data)
                self.show_profile(filename=self.filename, vmax=self.max_data, vmin=self.min_data)
            elif str(self.file)[-4:] == '.dat':
                self.filename = str(self.file)[:-4]
                self.data = self.readReflex(self.filename)[0]
                self.max_data = np.max(self.data)
                self.min_data = np.min(self.data)
                self.show_profile(filename=self.filename, vmax=self.max_data, vmin=self.min_data)

            else:
                print('tesss')

        self.folder = self.file[:self.file.rfind('/')]  # [:-31] to get main folder(after #)

        proj_name_temp = self.file[self.file.rfind('/') + 1:]
        ind1 = proj_name_temp.rfind('_')
        temp_1 = proj_name_temp[:proj_name_temp.rfind('_')]
        ind2 = temp_1.rfind('_')

        self.line_nr = proj_name_temp[:ind1][ind2 + 1:]
        self.project_name = proj_name_temp[:ind1][:ind2]
        self.appendix = proj_name_temp[ind1:].rsplit('.')[0]
        self.extension = proj_name_temp[ind1:].rsplit('.')[1]

        self.project_label2.config(text=self.project_name)
        self.line_label2.config(text=self.line_nr)

        'new sliders for sinle adjustment of min and max values, maybe needed for arbitrary sections from full trace analysis'
        # self.set_new_slider()
        'new sliders for sinle adjustment of min and max values, maybe needed for arbitrary sections from full trace analysis'

    def next_profile(self):
        c = 1

        def open_next(c):
            new_number = format((int(self.line_nr) + c), "03d")
            next_profile = self.folder + '/' + self.project_name + '_' + new_number + self.appendix + '.' + self.extension

            if path.exists(next_profile):
                global file_name_velo
                file_name_velo = self.folder + '/' + self.project_name + '_' + new_number + self.appendix
                self.file = file_name_velo
                self.openRD7()

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
                file_name_velo = self.folder + '/' + self.project_name + '_' + new_number + self.appendix
                self.file = file_name_velo
                self.openRD7()
            else:
                if c <= 10:
                    c += 1
                    open_previous(c)

        open_previous(c)

        self.plot_saved_model()

    def show_profile(self, filename, vmax, vmin):

        if str(self.file)[-4:] == '.rd3' or str(self.file)[-4:] == '.rd7':
            dx = self.profilePos[3] - self.profilePos[2]
            dt = self.twtt[3] - self.twtt[2]

            self.data = self.readMALA(file_name=self.filename)[0]
            self.a.clear()
            self.a.imshow(self.data, cmap='gray', vmax=vmax, vmin=vmin, extent=[min(self.profilePos) - dx / 2.0,
                                                                                max(self.profilePos) + dx / 2.0,
                                                                                max(self.twtt) + dt / 2.0,
                                                                                min(self.twtt) - dt / 2.0],
                          aspect="auto", )

            self.a.set_ylim(self.yrng)
            self.a.set_xlim(self.xrng)
            self.a.set_ylabel("two-way travel time [ns]", fontsize=mpl.rcParams['font.size'])
            self.a.invert_yaxis()

            self.a.get_xaxis().set_visible(True)
            self.a.get_yaxis().set_visible(True)
            self.a.set_xlabel("profile position [m]", fontsize=mpl.rcParams['font.size'])
            self.a.xaxis.tick_top()
            self.a.xaxis.set_label_position('top')

            self.vmin = vmin
            self.vmax = vmax

        elif str(self.file)[-4:] == '.dat':
            dx = self.profilePos[3] - self.profilePos[2]
            dt = self.twtt[3] - self.twtt[2]

            self.data = self.readReflex(file_name=self.filename)[0]
            self.a.clear()
            self.a.imshow(self.data, cmap='gray', vmax=vmax, vmin=vmin, extent=[min(self.profilePos) - dx / 2.0,
                                                                                max(self.profilePos) + dx / 2.0,
                                                                                max(self.twtt) + dt / 2.0,
                                                                                min(self.twtt) - dt / 2.0],
                          aspect="auto", )

            self.a.set_ylim(self.yrng)
            self.a.set_xlim(self.xrng)
            self.a.set_ylabel("two-way travel time [ns]", fontsize=mpl.rcParams['font.size'])
            self.a.invert_yaxis()

            self.a.get_xaxis().set_visible(True)
            self.a.get_yaxis().set_visible(True)
            self.a.set_xlabel("profile position [m]", fontsize=mpl.rcParams['font.size'])
            self.a.xaxis.tick_top()
            self.a.xaxis.set_label_position('top')

            self.vmin = vmin
            self.vmax = vmax

        elif str(self.file)[-4:] == '.npy':
            self.fig.clear()
            self.data = np.asmatrix(np.load(self.file))
            self.fig.add_subplot().imshow(self.data, cmap='gray', vmax=vmax, vmin=vmin)
            self.fig_canvas.draw()
            self.vmin = vmin
            self.vmax = vmax
        else:
            print('f)')

        'new sliders for sinle adjustment of min and max values, maybe needed for arbitrary sections from full trace analysis'
        # def set_new_slider(self):
        # self.contrast_slider_max = Scale(self.tool_frame, from_=0, to=self.vmax, length=200, orient=HORIZONTAL, command=self.slide_contrast_single)
        # self.contrast_slider_max.set(self.max_data)
        # self.contrast_slider_max.grid(row=2, column=1)

        # self.contrast_slider_min = Scale(self.tool_frame, from_=self.vmin, to=0, length=200, orient=HORIZONTAL, command=self.slide_contrast_single)
        # self.contrast_slider_min.set(self.min_data)
        # self.contrast_slider_min.grid(row=2, column=2)
        'new sliders for sinle adjustment of min and max values, maybe needed for arbitrary sections from full trace analysis'

        self.fig_canvas.draw()

    def increase_contrast(self):
        if str(self.file)[-4:] == '.rd3' or str(self.file)[-4:] == '.rd7':
            vmax_inc = self.vmax / 1.25
            vmin_inc = self.vmin / 1.25
            self.show_profile(self.filename, vmax_inc, vmin_inc)

        elif str(self.file)[-4:] == '.dat':
            vmax_inc = self.vmax / 1.25
            vmin_inc = self.vmin / 1.25
            self.show_profile(self.filename, vmax_inc, vmin_inc)

        elif str(self.file)[-4:] == '.npy':
            vmax_inc = self.vmax / 2.5
            vmin_inc = self.vmin / 2.5
            self.show_profile(self.filename, vmax_inc, vmin_inc)

    def decrease_contrast(self):
        if str(self.file)[-4:] == '.rd3' or str(self.file)[-4:] == '.rd7':
            vmax_dec = self.vmax * 1.25
            vmin_dec = self.vmin * 1.25
            self.show_profile(self.filename, vmax_dec, vmin_dec)

        if str(self.file)[-4:] == '.dat':
            vmax_dec = self.vmax * 1.25
            vmin_dec = self.vmin * 1.25
            self.show_profile(self.filename, vmax_dec, vmin_dec)

        elif str(self.file)[-4:] == '.npy':
            vmax_dec = self.vmax * 2.5
            vmin_dec = self.vmin * 2.5
            self.show_profile(self.filename, vmax_dec, vmin_dec)

    def slide_contrast(self, value):
        if int(value) < 30:
            vmax_slide = int(self.max_data) / (1.1 * int(value))
            vmin_slide = int(self.min_data) / (1.1 * int(value))
        elif int(value) < 60:
            vmax_slide = int(self.max_data) / (1.5 * int(value))
            vmin_slide = int(self.min_data) / (1.5 * int(value))
        else:
            vmax_slide = int(self.max_data) / (2 * int(value))
            vmin_slide = int(self.min_data) / (2 * int(value))

        self.show_profile(self.filename, vmax_slide, vmin_slide)

    def slide_contrast_single(self, value):
        vmax = self.contrast_slider_max.get()
        vmin = self.contrast_slider_min.get()
        self.show_profile(self.filename, vmax, vmin)

    def bindings(self):
        if self.velo_analysis.get() == 1:
            self.velo_analysis.set(1)
            self.fig_canvas.mpl_connect('button_press_event', self.plotClick)
        elif self.velo_analysis.get() == 0:
            self.velo_analysis.set(0)
            self.fig_canvas.mpl_disconnect('button_press_event')
        # self.fig_canvas.bind('ButtonPress-1', self.show_hypberbola)

    def plotClick(self, event):
        print(self.velo_analysis.get())
        if self.velo_analysis.get() == 1:
            if event.button == MouseButton.LEFT:
                self.x = event.xdata
                self.y = event.ydata

                print('Clicked at x=%f, y=%f' % (event.xdata, event.ydata))

                self.plot_hyperbola()
            else:
                print('nic')

    def plot_hyperbola(self):
        try:
            remove_hyp = self.hypberbola.pop(0)
            remove_hyp.remove()
            remove_hyp2 = self.hypberbola2.pop(0)
            remove_hyp2.remove()
        except:
            print('nix')

        x = self.profilePos - self.x
        v = float(self.velo_value.get())
        d = sqrt((v * float(self.y) / 2.0) ** 2 + (self.antenna_separation / 2) ** 2)
        d2 = v * float(self.y) / 2.0

        k = np.sqrt(d ** 2 + np.power(x, 2)) - (d - d2)
        t2 = 2 * k / v

        k2 = np.sqrt(d2 ** 2 + np.power(x, 2))
        t3 = 2 * k2 / v

        self.hypberbola = self.a.plot(self.profilePos, t2, '--r', linewidth=1)
        self.hypberbola2 = self.a.plot(self.profilePos, t3, '--g', linewidth=1)
        self.fig_canvas.draw()

    def increase_velo(self):
        value = round(float(self.velo_value.get()) + 0.0025, 4)
        self.velo_value.delete(0, 'end')
        self.velo_value.insert(INSERT, value)
        self.plot_hyperbola()

    def decrease_velo(self):
        value = round(float(self.velo_value.get()) - 0.0025, 4)
        self.velo_value.delete(0, 'end')
        self.velo_value.insert(INSERT, value)
        self.plot_hyperbola()

    def add_velocity_to_model(self):
        velo_value = []
        try:
            remove_hyp = self.hypberbola.pop()
            remove_hyp.remove()
        except:
            print('ft')

        self.hyp_point = self.a.plot(self.x, self.y, marker="o", markersize=5, markeredgecolor="red",
                                     markerfacecolor="red")
        label = self.velo_value.get() + ' m/ns'
        plt.annotate(label, (self.x, self.y), textcoords="offset points", xytext=(0, 10), ha='center')

        velo_value.append(self.line_nr)
        velo_value.append(round(self.x, 3))
        velo_value.append(round(self.y, 3))
        velo_value.append(self.velo_value.get())

        self.velo_model.append(velo_value)

        self.fig_canvas.draw()

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

        ###
        # Plot 1
        ###
        # determine the colors
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
        try:
            remove_hyp = self.hypberbola.pop(0)
            remove_hyp.remove()
        except:
            print('no hyp esix')
        try:
            remove_pnt = self.hyp_point.pop()
            remove_pnt.remove()
        except:
            print('no point exitste')

        for entry in self.velo_model:
            if entry[0] == self.line_nr:
                self.hyp_point = self.a.plot(float(entry[1]), float(entry[2]), marker="o", markersize=5,
                                             markeredgecolor="red",
                                             markerfacecolor="red")
                label = entry[3] + ' m/ns'
                plt.annotate(label, (float(entry[1]), float(entry[2])), textcoords="offset points", xytext=(0, 10),
                             ha='center')

        self.fig_canvas.draw()

    def exit_viewer(self):
        self.master.destroy()


    def readMALA(self, file_name):
        info = self.readGPRhdr(file_name + '.rad')
        try:
            filename = file_name + '.rd3'
            data = np.fromfile(filename, dtype=np.int16)
        except:
            filename = file_name + '.rd7'
            data = np.fromfile(filename, dtype=np.int32)

        nrows = int(len(data) / int(info['SAMPLES']))

        data = (np.asmatrix(data.reshape(nrows, int(info['SAMPLES'])))).transpose()
        vmax = np.max(data)
        vmin = np.min(data)

        self.profilePos = float(info["DISTANCE INTERVAL"]) * np.arange(0, data.shape[1])
        self.twtt = np.linspace(0, float(info["TIMEWINDOW"]), int(info["SAMPLES"]))

        self.yrng = [np.min(self.twtt), np.max(self.twtt)]
        self.xrng = [np.min(self.profilePos), np.max(self.profilePos)]

        return data, info, vmax, vmin

    def readGPRhdr(self, filename):
        info = {}
        with open(filename) as f:
            for line in f:
                strsp = line.split(':')
                info[strsp[0]] = strsp[1].rstrip()
        return info

    def readReflex(self, file_name):
        info = GPR_func.GPR_data_formats.read_par(file_name)
        data = GPR_func.GPR_data_formats.read_dat(file_name)

        timewindow = float(info[1]) * float(info[3])

        vmax = np.max(data)
        vmin = np.min(data)

        self.profilePos = (float(info[0]) / 2) * np.arange(0, (data.shape[1] * 2))
        print(self.profilePos)
        self.twtt = np.linspace(0, timewindow, info[3])

        self.yrng = [np.min(self.twtt), np.max(self.twtt)]
        self.xrng = [np.min(self.profilePos), np.max(self.profilePos)]
        self.antenna_separation = info[4]

        return data, info, vmax, vmin


def start_ProfileViewer():
    global root_3

    root_3 = tk.Tk()
    root_3.title('Profile Schlitzi+')
    root_3.geometry("%dx%d+0+0" % (screen_res_primary[1], screen_res_primary[0]))

    app = MalaRd7(root_3)
    app.mainloop()


start_ProfileViewer()
