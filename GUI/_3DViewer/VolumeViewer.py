import sys
from PyQt5 import QtWidgets
import pyvista as pv
import numpy as np
from pyvistaqt import QtInteractor
from matplotlib.cm import get_cmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import vtk

class HistogramWidget(QtWidgets.QFrame):
    def __init__(self, data_array, opacity_points, opacity_values, threshold, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.data_array = data_array
        self.opacity_points = opacity_points
        self.opacity_values = opacity_values.copy()
        self.threshold = threshold
        self.parent = parent
        self.dragged_point = None
        self.figure = Figure(figsize=(4.5, 4.5), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.canvas.setFixedSize(450, 400)
        self.plot_histogram_with_opacity()

    def plot_histogram_with_opacity(self):
        data_values = self.data_array.values.flatten()
        ax = self.figure.add_subplot(111)
        counts, bin_edges, _ = ax.hist(data_values, bins=50, color='skyblue', edgecolor='black', alpha=0.6)
        ax.margins(x=0.05, y=0.1)
        ax_opacity = ax.twinx()
        ax_opacity.set_ylim(0, 1)
        ax_opacity.set_ylabel("Opacity")
        self.line, = ax_opacity.plot(self.opacity_points, self.opacity_values, color='red', linewidth=2)
        self.draggable_points = [ax_opacity.plot(x, y, 'ro', markersize=8, picker=True)[0] for x, y in zip(self.opacity_points, self.opacity_values)]
        self.canvas.mpl_connect("pick_event", self.on_pick)
        self.canvas.mpl_connect("motion_notify_event", self.on_drag)
        self.canvas.mpl_connect("button_release_event", self.on_release)
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

class VolumeViewer(QtWidgets.QMainWindow):
    def __init__(self, data_array, pixel_size=(0.05, 0.05, 0.05)):
        super().__init__()
        self.grid = None
        self.volume_actor = None
        self.mapper = vtk.vtkGPUVolumeRayCastMapper()
        self.opacity_function = vtk.vtkPiecewiseFunction()
        self.setWindowTitle("3D Data Volume Viewer")
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        self.control_frame = QtWidgets.QFrame()
        self.control_frame.setFixedWidth(450)
        self.control_layout = QtWidgets.QVBoxLayout(self.control_frame)
        main_layout.addWidget(self.control_frame)
        self.plotter = QtInteractor(self)
        main_layout.addWidget(self.plotter.interactor)
        self.data_array = data_array
        self.opacity_points = [0, 5, 10, 20, 25, 31]
        self.init_opacity_values = [0, 0.01, 0.1, 0.3, 0.7, 1]
        self.threshold = 35.7
        self.pixel_size = pixel_size  # Set the pixel size dynamically
        self.current_cmap = "viridis"
        self.init_controls()
        self.visualize_3d_data()
        self.set_initial_camera_position()
        self.showMaximized()

    def set_initial_camera_position(self):
        data_shape = np.array(self.data_array.shape)
        volume_size = data_shape * self.pixel_size
        center = volume_size / 2
        relative_camera_position = np.array([2.02, 13.47, -12.93])
        zoom_out_factor = 2.5
        max_dimension = max(volume_size)
        camera_position = center + (relative_camera_position / np.linalg.norm(relative_camera_position)) * max_dimension * zoom_out_factor
        focal_point = tuple(center)
        view_up = (-0.0665, -0.816, -0.574)
        self.plotter.camera.position = tuple(camera_position)
        self.plotter.camera.focal_point = focal_point
        self.plotter.camera.up = view_up

    def init_controls(self):
        self.cmap_dropdown = QtWidgets.QComboBox()
        self.cmap_dropdown.addItems(["viridis", "plasma", "cividis", "Greys", "gray", "bone", "binary", "coolwarm"])
        self.cmap_dropdown.currentTextChanged.connect(self.update_cmap)
        self.control_layout.addWidget(QtWidgets.QLabel("Select Colormap"))
        self.control_layout.addWidget(self.cmap_dropdown)
        self.histogram_widget = HistogramWidget(self.data_array, self.opacity_points, self.init_opacity_values, self.threshold, self)
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
        if self.grid is None:
            self.grid = pv.ImageData(dimensions=data_values.shape)
            self.grid.spacing = self.pixel_size
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
            bounds=(0, self.grid.dimensions[0] * self.pixel_size[0],
                    0, self.grid.dimensions[1] * self.pixel_size[1],
                    0, self.grid.dimensions[2] * self.pixel_size[2])
        )
        self.plotter.render()

    def update_3d_view_with_new_opacity(self, new_opacity_points, new_opacity_values):
        self.opacity_points = new_opacity_points
        self.init_opacity_values = new_opacity_values
        self.visualize_3d_data()


def launch_volume_viewer(data_array, pixel_size):
    # Initialize the Qt application
    app = QtWidgets.QApplication(sys.argv)

    # Initialize and show the VolumeViewer with the passed data
    viewer = VolumeViewer(data_array, pixel_size=pixel_size)
    viewer.show()

    sys.exit(app.exec_())
