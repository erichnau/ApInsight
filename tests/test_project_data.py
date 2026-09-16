from data.ProjectData import FldData, ArbSectionData


def make_test_fld():
    """
    Create an FldData object without loading an actual FLD file.

    The synthetic dataset represents:
      pixel size: 0.05 m
      dimensions: 100 x 100 pixels
      lower-left x: 1000.0
      lower y-coordinate: 2000.0
    """
    fld = FldData.__new__(FldData)

    fld.x_coor = 1000.0
    fld.y_coor = 2000.0
    fld.xpixels = 100
    fld.ypixels = 100
    fld.pixelsize = 0.05

    return fld


def test_coordinate_to_index_upper_left():
    fld = make_test_fld()

    # Upper-left corner of the dataset
    x = 1000.0
    y = 2005.0

    x_index, y_index = fld.calc_index_from_coor(x, y)

    assert x_index == 0
    assert y_index == 0


def test_coordinate_to_index_known_position():
    fld = make_test_fld()

    # 1 m east and 2 m south from the upper-left corner
    x = 1001.0
    y = 2003.0

    x_index, y_index = fld.calc_index_from_coor(x, y)

    assert x_index == 20
    assert y_index == 40


import numpy as np
import xarray as xr


def make_test_gpr_cube():
    """
    Create a synthetic 3D GPR volume for testing section extraction.

    Horizontal resolution: 0.05 m
    Vertical resolution:   0.02 m

    Values vary predictably with x, y and z so that interpolation
    through the volume can be checked.
    """
    fld = FldData.__new__(FldData)

    fld.x_coor = 1000.0
    fld.y_coor = 2000.0
    fld.pixelsize = 0.05
    fld.pixelsize_z = 0.02
    fld.xpixels = 21
    fld.ypixels = 21
    fld.zpixels = 10
    fld.data_type = 2
    fld.file_name = "synthetic.fld"

    x = np.linspace(1000.0, 1001.0, 21)
    y = np.linspace(2001.0, 2000.0, 21)
    z = np.linspace(0.0, -0.18, 10)

    # Create a predictable 3D volume.
    zz, yy, xx = np.meshgrid(z, y, x, indexing="ij")

    data = (
        (xx - 1000.0) * 10
        + (yy - 2000.0) * 20
        + (-zz) * 100
        + 1
    )

    fld.fld_dset = xr.DataArray(
        data,
        coords={"z": z, "y": y, "x": x},
        dims=("z", "y", "x")
    )

    fld.depth_table = [
        (i * 0.02, 0.0) for i in range(10)
    ]

    return fld


def test_arbitrary_section_distance_and_sampling():
    fld = make_test_gpr_cube()

    result = fld.create_arbitrary_section(
        1000.0, 2000.5,
        1001.0, 2000.5
    )

    dist, section, depth_m, pixelsize_z, data_type, *_ = result

    assert np.isclose(dist, 1.0)

    # For data_type 2, ApInsight uses a fixed 1 cm sampling
    # interval for arbitrary sections.
    # 1.0 m / 0.01 m = 100 samples.
    assert section.shape[1] == 100

    assert np.isclose(pixelsize_z, 0.01)
    assert data_type == 2


def test_arbitrary_section_values():
    fld = make_test_gpr_cube()

    result = fld.create_arbitrary_section(
        1000.0, 2000.5,
        1001.0, 2000.5
    )

    section = result[1]

    # Along this section y remains constant at 2000.5.
    # At the uppermost depth:
    #
    # start: 0*10 + 0.5*20 + 0*100 + 1 = 11
    # end:   1*10 + 0.5*20 + 0*100 + 1 = 21

    assert np.isclose(section[0, 0], 11.0)
    assert np.isclose(section[0, -1], 21.0)

    # The amplitude should increase linearly along the section.
    assert np.allclose(
        section[0],
        np.linspace(11.0, 21.0, 100)
    )


def test_arbitrary_section_diagonal():
    fld = make_test_gpr_cube()

    result = fld.create_arbitrary_section(
        1000.0, 2000.0,
        1001.0, 2001.0
    )

    dist, section, *_ = result

    # Diagonal across a 1 x 1 m square
    expected_distance = np.sqrt(2)

    assert np.isclose(dist, expected_distance)

    # ApInsight uses 1 cm sampling for data_type 2.
    expected_samples = round(expected_distance / 0.01)

    assert section.shape[1] == expected_samples

    # At the uppermost depth:
    #
    # start:
    # x contribution = 0
    # y contribution = 0
    # z contribution = 0
    # + 1
    # = 1
    #
    # end:
    # x contribution = 1 * 10 = 10
    # y contribution = 1 * 20 = 20
    # z contribution = 0
    # + 1
    # = 31

    assert np.isclose(section[0, 0], 1.0)
    assert np.isclose(section[0, -1], 31.0)

    # Because the synthetic volume varies linearly in x and y,
    # the complete extracted section should also vary linearly.
    assert np.allclose(
        section[0],
        np.linspace(1.0, 31.0, expected_samples)
    )

def test_arbitrary_section_depth_values():
    fld = make_test_gpr_cube()

    result = fld.create_arbitrary_section(
        1000.0, 2000.5,
        1001.0, 2000.5
    )

    section = result[1]

    # Synthetic cube uses:
    # amplitude = x*10 + y*20 + depth*100 + 1
    #
    # Each depth sample is 0.02 m in the synthetic source cube,
    # so the second depth layer adds 2 to every amplitude.

    assert np.isclose(section[0, 0], 11.0)
    assert np.isclose(section[1, 0], 13.0)

    assert np.isclose(section[0, -1], 21.0)
    assert np.isclose(section[1, -1], 23.0)

    # Difference between first and second depth layers
    # should therefore be 2 everywhere.
    assert np.allclose(
        section[1] - section[0],
        2.0
    )



class FakeDTM:
    """Simple predictable terrain profile for testing."""

    def create_height_profile(self, section_coor, samples):
        return np.array([100.0, 100.1, 100.2, 100.1, 100.0])


def make_test_section():
    section_data = np.array([
        [1, 2, 3, 4, 5],
        [6, 7, 8, 9, 10],
        [11, 12, 13, 14, 15],
    ], dtype=float)

    return ArbSectionData(
        section_data=section_data,
        depth_m=0.03,
        dist=1.0,
        sampling_intervael=0.01,
        dtm_files={},
        section_coor=((0, 0), (1, 0)),
        pixelsize_z=0.01,
        data_type=2,
        top_removed=None,
        bottom_removed=None,
        depth_table=None
    )


def test_topographic_correction_shape():
    section = make_test_section()
    dtm = FakeDTM()

    downsampled, height_profile = section.topographic_correction(dtm)

    # Terrain varies by 0.2 m.
    # With 1 cm vertical sampling this requires 20 extra rows.
    assert section.topo_corr_data.shape == (23, 5)

    assert np.allclose(
        height_profile,
        [100.0, 100.1, 100.2, 100.1, 100.0]
    )


def test_topographic_correction_shifts_columns():
    section = make_test_section()
    dtm = FakeDTM()

    section.topographic_correction(dtm)

    corrected = section.topo_corr_data

    # Highest point (middle column, 100.2 m) receives no shift.
    assert np.allclose(
        corrected[:3, 2],
        [3, 8, 13]
    )

    # First column lies 0.2 m below the highest point.
    # At 1 cm/sample it should be shifted down by 20 rows.
    assert np.all(np.isnan(corrected[:20, 0]))

    assert np.allclose(
        corrected[20:23, 0],
        [1, 6, 11]
    )

