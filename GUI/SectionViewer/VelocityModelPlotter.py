import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from GPR_func.GPR_proc import bin_by

class VelocityModelPlot:
    def __init__(self, master, velo_model):
        self.master = master
        self.velo_model = velo_model

        self.create_window()

    def create_window(self):
        self.plot_window = tk.Toplevel(self.master)
        self.plot_window.title("Velocity Model")

        # Create a figure and axis
        self.fig, self.ax = plt.subplots()

        # Prepare the data
        velo_for_plot_x = []
        velo_for_plot_y = []
        for element in self.velo_model:
            velo_for_plot_x.append(float(element[2]))
            velo_for_plot_y.append(float(element[3]))

        x = np.array(velo_for_plot_x)
        y = np.array(velo_for_plot_y)

        # Bin the values and determine the envelopes
        df = bin_by(x, y, nbins=6, bins=None)

        cols = ['#EE7550', '#F19463', '#F6B176']

        # Plot the data
        self.ax.fill_between(df.x, df['5th'], df['95th'], alpha=0.7, color=cols[2])
        self.ax.fill_between(df.x, df['10th'], df['90th'], alpha=0.7, color=cols[1])
        self.ax.fill_between(df.x, df['25th'], df['75th'], alpha=0.7, color=cols[0])
        self.ax.plot(df.x, df['median'], color='black', alpha=0.7, linewidth=1.5)
        self.ax.scatter(velo_for_plot_x, velo_for_plot_y, facecolors='blue', edgecolors='0', s=5, lw=1)

        # Add labels to the axes
        self.ax.set_xlabel("Time (ns)")
        self.ax.set_ylabel("Velocity (m/ns)")

        # Create a canvas to embed the plot
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_window)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Add a custom save button
        self.save_button = tk.Button(self.plot_window, text="Save Figure", command=self.save_figure)
        self.save_button.pack()

    def save_figure(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if file_path:
            self.fig.savefig(file_path)
        self.plot_window.lift()

