import tkinter as tk
import tkinter.ttk as ttk
from tkinter import Label

class MeasurementWindow(tk.Toplevel):

    def __init__(self, frame_image, top_frame):
        super().__init__()
        self.title("Measurement Tool")
        self.geometry('270x175')
        self.attributes('-topmost', True)
        self.protocol('WM_DELETE_WINDOW', self.on_window_close)

        self.top_frame = top_frame
        self.frame_image = frame_image
        self.frame_image = frame_image
        self.canvas = self.frame_image.canvas
        self.mode = tk.StringVar()

        self.create_widgets()

        self.points = []

    def create_widgets(self):
        # Create check buttons for distance and area measurement
        distance_checkbtn = tk.Checkbutton(self, text="Distance", variable=self.mode, onvalue="distance",
                                           command=self.measure_bindings)
        distance_checkbtn.grid(row=0, column=0, padx=10, pady=10)

        area_checkbtn = tk.Checkbutton(self, text="Area", variable=self.mode, onvalue="area",
                                       command=self.measure_bindings)
        area_checkbtn.grid(row=0, column=1, padx=10, pady=10)

        separator = ttk.Separator(self, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky='ew')

        clear_button = tk.Button(self, text="Clear", command=self.clear_measurements)
        clear_button.grid(row=1, column=3, padx=10, pady=10)

        vertical_separator = ttk.Separator(self, orient='vertical')
        vertical_separator.grid(row=0, column=2, rowspan=4, padx=10, pady=10, sticky='ns')

        self.distance_label = Label(self, text="Distance: ")
        self.distance_label.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        self.area_label = Label(self, text="Area: ")
        self.area_label.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

        self.mode.set('distance')
        self.measure_bindings()

    def measure_bindings(self):
        if self.mode.get() == 'distance':
            self.canvas.delete('poly_motion', 'poly_lines', 'poly_final', 'poly_point')
            self.area_label.config(text="Area: ")
            self.points = []

            self.canvas.unbind("<ButtonPress-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.unbind("<ButtonRelease-1>")
            self.canvas.unbind('<MouseWheel>')

            self.canvas.bind("<ButtonPress-1>", self.start_p)
            self.canvas.bind("<B1-Motion>", self.draw_dist)
            self.canvas.bind("<ButtonRelease-1>", self.stop_p)

        elif self.mode.get() == 'area':
            self.canvas.delete('start_p_dist', 'stop_p_dist', 'dist')
            self.distance_label.config(text="Distance: ")

            self.canvas.unbind("<ButtonPress-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.unbind("<ButtonRelease-1>")
            self.canvas.unbind('<MouseWheel>')

            self.canvas.bind("<Button-1>", self.add_point)
            self.canvas.bind("<Motion>", self.wrapper_function)
            self.canvas.bind("<Double-Button-1>", self.finalize_poly)

    def clear_measurements(self):
        # Delete all drawn objects from the canvas
        self.canvas.delete('start_p_dist', 'stop_p_dist', 'dist')
        self.canvas.delete('poly_motion', 'poly_lines', 'poly_final', 'poly_point')

        # Clear the points list
        self.points = []

        # Reset the labels
        self.distance_label.config(text="Distance: ")
        self.area_label.config(text="Area: ")

    def start_p(self, event):
        self.canvas.delete('start_p_dist')
        self.x0, self.y0 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.create_oval(self.x0, self.y0, self.x0, self.y0, tags='start_p_dist', outline='blue', width=5)

    def draw_dist(self, event):
        self.canvas.delete('dist')
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Draw a line from the starting position to the current mouse position
        self.canvas.create_line(self.x0, self.y0, canvas_x, canvas_y, tags="dist", fill='red')

    def stop_p(self, event):
        self.canvas.delete('stop_p_dist')
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.create_oval(x1, y1, x1, y1, tags='stop_p_dist', outline='blue', width=5)

        dist = self.measure_distance(self.x0, self.y0, x1, y1)

        self.distance_label.config(text=f"Distance: {dist} m")

    def add_point(self, event):
        if len(self.canvas.find_withtag('poly_final')) > 0:
            self.canvas.delete('poly_final', 'poly_lines', 'poly_point')
            self.points = []
            self.canvas.bind("<Motion>", self.wrapper_function)

        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.points.append((x, y))
        self.canvas.create_oval(x, y, x, y, tag='poly_point', fill='red', width=5)

        if len(self.points) > 1:
            for i in range(len(self.points) - 1):
                x0, y0 = self.points[i]
                x1, y1 = self.points[i + 1]
                self.canvas.create_line(x0, y0, x1, y1, tags="poly_lines", fill='red')

    def draw_poly(self, event):
        self.canvas.delete('poly_motion')
        if len(self.points) > 1:
            first_x, first_y = self.points[0]
            last_x, last_y = self.points[-1]
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.canvas.create_line(last_x, last_y, canvas_x, canvas_y, tags="poly_motion", fill='red')
            self.canvas.create_line(first_x, first_y, canvas_x, canvas_y, tags="poly_motion", fill='red')

    def finalize_poly(self, event):
        self.canvas.delete('poly_motion', 'poly_lines')
        if len(self.points) < 3:
            return

        self.points.append(self.points[0])  # Close the polygon
        self.poly_id = self.canvas.create_polygon(self.points, tags='poly_final', outline='blue', fill='', width=2)

        self.calculate_polygon_area(self.points[:-1])  # Exclude the closing point

        self.canvas.unbind('<Motion>')
        self.canvas.bind('<Motion>', self.frame_image.print_canvas_coordinates)

    def measure_distance(self, x0, y0, x1, y1):
        # Calculate the distance between two points
        global_x0, global_y0 = self.frame_image.canvas_coor_to_global(x0, y0)
        global_x1, global_y1 = self.frame_image.canvas_coor_to_global(x1, y1)

        distance = round((((global_x1 - global_x0)**2 + (global_y1 - global_y0)**2) ** 0.5), 2)

        return distance

    def calculate_polygon_area(self, points):
        global_points = []
        for element in points:
            x_glob, y_glob = self.frame_image.canvas_coor_to_global(element[0], element[1])
            global_points.append([x_glob, y_glob])

        area = 0
        for i in range(len(global_points)):
            x1, y1 = global_points[i]
            x2, y2 = global_points[(i + 1) % len(global_points)]
            area += (x1 * y2) - (x2 * y1)

        area /= 2
        area = round(abs(area), 2)
        self.area_label.config(text=f"Area: {area} m²")

    def on_window_close(self):
        self.canvas.delete('start_p_dist', 'stop_p_dist', 'dist')
        self.canvas.delete('poly_motion', 'poly_lines', 'poly_final', 'poly_point')
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<Motion>")
        self.canvas.unbind("<Double-Button-1>")
        self.top_frame.measure_tool.config(relief='raised')
        self.top_frame.measure_mode = False
        self.top_frame.mw = None
        self.frame_image.bindings()
        self.destroy()

    def wrapper_function(self, event):
        self.draw_poly(event)
        self.frame_image.print_canvas_coordinates(event)


