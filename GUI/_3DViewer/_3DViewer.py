import numpy as np
import pyvista as pv

def visualize_3d_data(data, spacing=(1, 1, 1), origin=(0, 0, 0), threshold=30):
    data = data.values

    # Create a PyVista ImageData object for the volumetric data
    grid = pv.ImageData(dimensions=data.shape)

    # Set the spacing and origin
    grid.spacing = spacing
    grid.origin = origin

    # Add the volumetric data to the grid
    grid.point_data["values"] = data.flatten(order="F")

    # Define a camera position for better visualization
    cpos = [(150, 150, 150), (50, 50, 50), (0, 0, 1)]

    # Create an opacity transfer function for values between 0 and 25.8
    opacity = [0, 0.01, 0.01, 0.3, 0.9, 1]
    #opacity_points = [0, 10, 20, 25, threshold, threshold + 1]
    opacity_points = [0, 5, 10, 20, 25, 31]

    # Interpolate opacity function based on values
    opacity_transfer_function = np.interp(np.linspace(0, threshold + 1, num=32), opacity_points, opacity)

    # Create the Plotter and add the volume
    pl = pv.Plotter()
    pl.add_volume(grid, scalars="values", cmap="viridis", opacity=opacity_transfer_function)

    # Add axes and grid
    pl.show_axes()
    pl.show_grid()

    pl.camera_position = cpos
    pl.show()