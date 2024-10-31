import sys
from PyQt5 import QtWidgets, QtCore
import pyvista as pv
import numpy as np
import xarray as xr
from pyvistaqt import QtInteractor
from matplotlib.cm import get_cmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import vtk


class HistogramWidget(QtWidgets.QFrame):
    def __init__(self, data_array, opacity_points, opacity_values, threshold, parent=None):
        super().__init__(parent)

        # Set up the frame title and layout
        self.setWindowTitle("Data Value Distribution with Editable Opacity Transfer Function")
        layout = QtWidgets.QVBoxLayout(self)

        # Store parameters and make opacity values editable
        self.data_array = data_array
        self.opacity_points = opacity_points
        self.opacity_values = opacity_values.copy()  # Copy to allow modification
        self.threshold = threshold
        self.parent = parent  # Reference to MainWindow to update the 3D view
        self.dragged_point = None

        # Create a matplotlib figure with a specified aspect ratio to be square
        self.figure = Figure(figsize=(4.5, 4.5), tight_layout=True)  # Adjust width and height
        self.canvas = FigureCanvas(self.figure)

        # Add canvas to layout and set a fixed size for consistent aspect ratio
        layout.addWidget(self.canvas)
        self.canvas.setFixedSize(450, 400)  # Keep the canvas size square

        # Plot histogram with editable opacity function
        self.plot_histogram_with_opacity()

    def plot_histogram_with_opacity(self):
        # Flatten the data for histogram
        data_values = self.data_array.values.flatten()

        # Create histogram plot with axis margins to prevent label cut-off
        ax = self.figure.add_subplot(111)
        counts, bin_edges, _ = ax.hist(data_values, bins=50, color='skyblue', edgecolor='black', alpha=0.6,
                                       label='Data Distribution')

        # Set aspect and margins to avoid clipping
        ax.margins(x=0.05, y=0.1)  # Extra margins to prevent label cut-off
        ax.set_aspect('auto')  # Allows automatic adjustment to square aspect

        # Plot opacity transfer function on secondary y-axis
        ax_opacity = ax.twinx()
        ax_opacity.set_ylim(0, 1)
        ax_opacity.set_ylabel("Opacity")

        # Plot draggable points for opacity control
        self.line, = ax_opacity.plot(self.opacity_points, self.opacity_values, color='red', linewidth=2,
                                     label='Opacity Transfer Function')
        self.draggable_points = [ax_opacity.plot(x, y, 'ro', markersize=8, picker=True)[0] for x, y in
                                 zip(self.opacity_points, self.opacity_values)]

        # Connect events for draggable points
        self.canvas.mpl_connect("pick_event", self.on_pick)
        self.canvas.mpl_connect("motion_notify_event", self.on_drag)
        self.canvas.mpl_connect("button_release_event", self.on_release)

        # Draw the initial plot
        self.canvas.draw()

    def on_pick(self, event):
        if event.artist in self.draggable_points:
            self.dragged_point = event.artist

    def on_drag(self, event):
        if self.dragged_point and event.xdata is not None and event.ydata is not None:
            index = self.draggable_points.index(self.dragged_point)

            if index > 0:
                event.xdata = max(event.xdata, self.opacity_points[index - 1] + 0.1)
            if index < len(self.opacity_points) - 1:
                event.xdata = min(event.xdata, self.opacity_points[index + 1] - 0.1)

            self.opacity_points[index] = event.xdata
            self.opacity_values[index] = min(1, max(0, event.ydata))
            self.update_opacity_plot()

    def on_release(self, event):
        if self.dragged_point:
            self.parent.update_3d_view_with_new_opacity(self.opacity_points, self.opacity_values)
            self.dragged_point = None

    def update_opacity_plot(self):
        self.line.set_xdata(self.opacity_points)
        self.line.set_ydata(self.opacity_values)
        for i, point in enumerate(self.draggable_points):
            point.set_xdata(self.opacity_points[i])
            point.set_ydata(self.opacity_values[i])
        self.canvas.draw()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_array):
        super().__init__()

        self.grid = None
        self.volume_actor = None
        self.mapper = vtk.vtkGPUVolumeRayCastMapper()
        self.opacity_function = vtk.vtkPiecewiseFunction()

        # Set up the main window
        self.setWindowTitle("Advanced 3D Data Visualization")


        # Main layout setup
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # Left control panel frame with increased width
        self.control_frame = QtWidgets.QFrame()
        self.control_frame.setFixedWidth(450)  # Increased by 50%
        self.control_layout = QtWidgets.QVBoxLayout(self.control_frame)
        main_layout.addWidget(self.control_frame)

        # Right frame for PyVista 3D visualizer
        self.plotter = QtInteractor(self)
        main_layout.addWidget(self.plotter.interactor)

        # Load data and set initial visualization parameters
        self.data_array = data_array
        self.opacity_points = [0, 5, 10, 20, 25, 31]
        self.init_opacity_values = [0, 0.01, 0.1, 0.3, 0.7, 1]
        self.threshold = 35.7
        self.current_cmap = "viridis"

        # Initialize control widgets
        self.init_controls()

        # Initial render after controls setup
        self.visualize_3d_data()

        # Set initial camera position
        self.set_initial_camera_position()

        self.showMaximized()

    def set_initial_camera_position(self):
        data_shape = np.array(self.data_array.shape)
        spacing = (0.05, 0.05, 0.05)
        volume_size = data_shape * spacing
        center = volume_size / 2

        relative_camera_position = np.array([2.02, 13.47, -12.93])
        zoom_out_factor = 2.5
        max_dimension = max(volume_size)
        camera_position = center + (relative_camera_position / np.linalg.norm(
            relative_camera_position)) * max_dimension * zoom_out_factor

        focal_point = tuple(center)
        view_up = (-0.0665, -0.816, -0.574)
        self.plotter.camera.position = tuple(camera_position)
        self.plotter.camera.focal_point = focal_point
        self.plotter.camera.up = view_up

    def init_controls(self):
        # Colormap Dropdown
        self.cmap_dropdown = QtWidgets.QComboBox()
        self.cmap_dropdown.addItems(["viridis", "plasma", "cividis", "Greys", "gray", "bone", "binary", "coolwarm"])
        self.cmap_dropdown.currentTextChanged.connect(self.update_cmap)
        self.control_layout.addWidget(QtWidgets.QLabel("Select Colormap"))
        self.control_layout.addWidget(self.cmap_dropdown)

        # Histogram and Opacity Transfer Function Widget embedded in left panel
        self.histogram_widget = HistogramWidget(self.data_array, self.opacity_points, self.init_opacity_values,
                                                self.threshold, self)
        self.control_layout.addWidget(self.histogram_widget)

    def update_cmap(self, cmap_name):
        self.current_cmap = cmap_name
        self.visualize_3d_data()

    def create_color_transfer_function(self):
        color_transfer_function = vtk.vtkColorTransferFunction()
        cmap = get_cmap(self.current_cmap)

        for i in range(256):
            color = cmap(i / 255.0)[:3]
            color_transfer_function.AddRGBPoint(i / 255.0 * self.threshold, *color)

        return color_transfer_function

    def visualize_3d_data(self):
        self.plotter.clear()
        data_values = self.data_array.values.astype(float)
        opacity_transfer_function = np.interp(
            np.linspace(0, self.threshold, num=32), self.opacity_points, self.init_opacity_values
        )

        spacing = (0.05, 0.05, 0.05)
        dimensions = np.array(data_values.shape) * np.array(spacing)

        if self.grid is None:
            self.grid = pv.ImageData(dimensions=data_values.shape)
            self.grid.spacing = spacing
            self.grid.origin = (0, 0, 0)
            self.grid.point_data["values"] = data_values.flatten(order="F")

        self.opacity_function.RemoveAllPoints()
        for i, opacity in enumerate(opacity_transfer_function):
            mapped_position = i / (len(opacity_transfer_function) - 1) * self.threshold
            self.opacity_function.AddPoint(mapped_position, opacity)

        volume_property = vtk.vtkVolumeProperty()
        volume_property.SetScalarOpacity(self.opacity_function)
        volume_property.SetColor(self.create_color_transfer_function())
        volume_property.ShadeOff()

        self.mapper.SetInputData(self.grid)
        self.volume_actor = vtk.vtkVolume()
        self.volume_actor.SetMapper(self.mapper)
        self.volume_actor.SetProperty(volume_property)

        self.plotter.renderer.AddVolume(self.volume_actor)

        self.plotter.show_bounds(
            grid="back",
            location="outer",
            ticks="both",
            bounds=(0, dimensions[0], 0, dimensions[1], 0, dimensions[2])
        )

        self.plotter.render()

    def update_3d_view_with_new_opacity(self, new_opacity_points, new_opacity_values):
        self.opacity_points = new_opacity_points
        self.init_opacity_values = new_opacity_values
        self.visualize_3d_data()


# Load dataset and extract data variable
data = xr.open_dataset('d:/001_GPR_testdata/test.nc')
data_array = data["__xarray_dataarray_variable__"].transpose('x', 'y', 'z')

# Set up application
app = QtWidgets.QApplication(sys.argv)
window = MainWindow(data_array)
window.show()

# Run application
sys.exit(app.exec_())
