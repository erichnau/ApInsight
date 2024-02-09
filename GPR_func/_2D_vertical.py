import numpy as np

def check_section_array(section_data):
    if np.any(np.logical_and(np.isfinite(section_data), section_data != 0)):
        return True
    else:
        return False

def filter_nan_and_zero_rows(section_data):
    # Create a mask to identify rows that are not entirely composed of nan and 0
    mask = ~(np.all(np.isnan(section_data) | (section_data == 0), axis=1))
    # Apply the mask to filter out these rows
    filtered_data = section_data[mask]

    return filtered_data
