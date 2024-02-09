import os
import json
import tkinter as tk
from tkinter import messagebox
from tkinter.filedialog import asksaveasfilename


'''
contains functions to get the datastructure of a GPR dataset processed with ApRadar (Geopshere Austria), 
valid input files are a .fld or .ap_prj file. The retrieved datastructure contains links to the 
.ap_prj, .fld, DTM .tif (if present), .npy (if already preprocessed with ApInsight and the depthslice folder.
The retrieved datastructure is stored in a .json file format and can later be opened and edited with ApInsight'''


def find_matching_apprj_files(fld_file):
    """
    Finds the corresponding .ap_prj file based on the closest creation time to the .fld file.

    Input:
    fld_file -- full path to a .fld project file

    Output:
    matching_file -- Path to the closest matching .ap_prj file
    """
    # Extract the directory and base file name without extension
    dir_path = os.path.dirname(fld_file)
    base_file_name = os.path.splitext(os.path.basename(fld_file))[0]

    # Get the timestamp of the .fld file
    fld_timestamp = os.path.getctime(fld_file)

    closest_file = None
    closest_time_diff = float('inf')

    # Look for .ap_prj files that start with the same base name
    for file in os.listdir(dir_path):
        if file.startswith(base_file_name) and file.endswith('.ap_prj'):
            file_path = os.path.join(dir_path, file)
            file_timestamp = os.path.getctime(file_path)

            # Calculate the time difference between the .fld file and this .ap_prj file
            time_diff = fld_timestamp - file_timestamp

            # Check if this file is closer and before the .fld file
            if 0 <= time_diff < closest_time_diff:
                closest_file = file_path
                closest_time_diff = time_diff

    if closest_file == None:
        return None
    else:
        if os.path.exists(closest_file):
            return closest_file
        else:
            return None

def find_matching_mira_files(apprj_file):
    """
    takes a .ap_prj file as input and locates the corresponding raw data / .mira file
    Input:
    apprj_file -- full path to a .ap_prj file

    Output:
    matching mira files - list containing the full path to the matching .mira file
    """

    with open(apprj_file, 'r') as f:
        lines = f.readlines()
        gpr_file = ''
        for line in lines:
            if line.startswith('FirstGPRFile'):
                gpr_file = line.split()[1]
                break
        if gpr_file == '':
            return []
        gpr_filename = os.path.splitext(os.path.basename(gpr_file))[0]
        gpr_parts = gpr_filename.split('_')
        gpr_basename = '_'.join(gpr_parts[:-2])
        mira_folder = os.path.dirname(apprj_file).replace('processing', gpr_basename)
        matching_mira_files = [f for f in os.listdir(mira_folder) if f.startswith(gpr_basename) and f.endswith('.mira')]
        matching_mira_files = [os.path.join(mira_folder, f) for f in matching_mira_files]
        return matching_mira_files[0]

def list_rd3_files(mira_file):
    """
    takes a mira file as input and returns a list of tuples containing all .rd3 files in the mira folder
    Input
    mira file -- full path to the .mira file

    Output:
    rd3_info -- list of tuples, each tuple contains (line, channel, filename)
    mira_file --  full path to the .mira file

    """
    # extract folder path and mira filename
    folder_path = os.path.dirname(mira_file)
    mira_filename = os.path.splitext(os.path.basename(mira_file))[0]

    # list all rd3 files in folder
    rd3_files = [f for f in os.listdir(folder_path) if f.endswith('.rd3')]

    # create list of lists containing line, channel, and filename for each rd3 file
    rd3_info = []
    for rd3_file in rd3_files:
        rd3_basename = os.path.splitext(rd3_file)[0]
        rd3_parts = rd3_basename.split('_')
        line = int(rd3_parts[-2])
        channel = int(rd3_parts[-1][1:])
        rd3_info.append([line, channel, rd3_file])
    return rd3_info, mira_file

def find_corresponding_shp(mira_file):
    """
    finds a corresponing _AntennaPoints.shp file to a given .mira file
    :param mira_file: full path to a .mira file
    :return: fld_path - full path to the _AntennaPoints.shp file
    """
    base_dir = os.path.dirname(os.path.dirname(mira_file))
    mira_name = os.path.splitext(os.path.basename(mira_file))[0]
    matching_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith("_Antenna_Points.shp") and mira_name in file:
                matching_files.append(os.path.join(root, file))
    return matching_files

def find_matching_fld(ap_prj_file):
    """
    finds the corresponding .fld file to a given .ap_prj file
    :param ap_prj_file: full path to a .ap_prj file
    :return: fld_path, full path to the matching .fld file
    """
    ap_prj_filename = os.path.splitext(os.path.basename(ap_prj_file))[0]
    fld_filename = ap_prj_filename.rsplit('_', 1)[0].rsplit('_', 1)[0] + '.fld'
    fld_path = os.path.join(os.path.dirname(ap_prj_file), fld_filename)
    if os.path.isfile(fld_path):
        return fld_path
    else:
        return None

def find_matching_npy(fld_file):
    """
    finds the corresponding .npy file to a given .fld file
    :param fld_file: full path to a .fld file
    :return: npy_file, full path to the matching .npy file
    """
    # Replace the .fld extension with .npy
    npy_file_path = fld_file.rsplit('.', 1)[0] + '.npy'

    # Check if the .npy file exists
    if os.path.isfile(npy_file_path):
        return npy_file_path
    else:
        return None


def find_corresponding_par_files(mira_file):
    """
    finds corresponding .par (created upon VelocityAnalysis in apradar) files to a given .mira file
    :param mira_file: full path to the .mira file
    :return: par_files, list of tuples containing (line, channel, file)
    """
    par_files = []
    mira_dir = os.path.dirname(mira_file)
    reflex_dir = os.path.join(mira_dir, '../..', 'VelocityAnalysis', 'reflex', 'ROHDATA')
    if os.path.exists(reflex_dir):
        for root, dirs, files in os.walk(reflex_dir):
            for file in files:
                if file.endswith('.par') and file.startswith(os.path.basename(mira_file).split('.')[0]):
                    parts = file.split('.')[0].split('_')
                    line = int(parts[-2].replace('channel', ''))
                    channel = int(parts[-1].split('.')[0][7:])
                    par_files.append((line, channel, file))
    return par_files, mira_file

def find_velocity_model_file(mira_file):
    """
    finds the link to a possibly existing _Valocity_model.txt file of a given .mira file
    :param mira_file: full path to a .mira file
    :return: velocity_model_path, full path to a found _Valocity_model.txt
    """
    # Get directory where the mira file is located
    mira_dir = os.path.dirname(mira_file)

    # Get base name of the mira file (without extension)
    mira_basename = os.path.splitext(os.path.basename(mira_file))[0]

    # Search for the Velocity_model.txt file in the ROHDATA folder
    velocity_model_path = os.path.join(mira_dir, '../..', 'VelocityAnalysis', 'reflex', 'ROHDATA', f'{mira_basename}_Velocity_model.txt')
    if os.path.exists(velocity_model_path):
        return velocity_model_path
    else:
        return None

def find_nc_file(ap_prj_filename):
    """
    finds the link to a possibly existing .nc file to a given .ap_prj file
    :param ap_prj_filename: full path to a .ap_prj file
    :return: nc_path, full path to a .nc file (if one is found)
    """
    ap_prj_file = os.path.splitext(os.path.basename(ap_prj_filename))[0]
    nc_filename = ap_prj_file.rsplit('_', 1)[0].rsplit('_', 1)[0] + '.nc'
    nc_path = os.path.join(os.path.dirname(ap_prj_filename), nc_filename)
    if os.path.exists(nc_path):
        return nc_path
    else:
        return None

def find_DTM_tif_file(fld_filename):
    """
    Finds the link to a possibly existing DTM.tif file corresponding to a given .fld file.
    :param fld_filename: full path to a .fld file
    :return: DTM_path, full path to a DTM.tif file (if one is found)
    """
    
    # Extract the base name without the extension
    base_name = os.path.splitext(os.path.basename(fld_filename))[0]

    # Construct the DTM file name
    DTM_filename = base_name + '_DTM_Float.tif'
    DTM_path = os.path.join(os.path.dirname(fld_filename), DTM_filename)

    if os.path.exists(DTM_path):
        return DTM_path
    else:
        return None

def find_Energy_file(ap_prj_filename):
    """
    finds the link to a possibly existing Energy.txt file to a given .ap_prj file
    :param ap_prj_filename: full path to a .ap_prj file
    :return: DTM_path, full path to a Energy.txt file (if one is found)
    """
    ap_prj_file = os.path.splitext(os.path.basename(ap_prj_filename))[0]
    energy_filename = ap_prj_file.rsplit('_', 1)[0].rsplit('_', 1)[0] + '_Energy.txt'
    energy_path = os.path.join(os.path.dirname(ap_prj_filename),energy_filename)
    if os.path.exists(energy_path):
        return energy_path
    else:
        return None

def find_matching_par_file(par_files, mira_file, search_line):
    """
    finds the full path to a matching par file upon given line nr and channel nr
    :param par_files: list of tuples containg (line, channel, file)
    :param mira_file: full path to a .mira file
    :param search_line: integer of the line number
    :return: par_path, full path to the matching .par file
    """
    search_channel = 8
    # Get directory where the mira file is located
    mira_dir = os.path.dirname(mira_file)

    # Get base name of the mira file (without extension)
    mira_basename = os.path.splitext(os.path.basename(mira_file))[0]

    # Get base name of the par file we're looking for
    par_basename = f"{mira_basename}_{search_line:03d}_channel{search_channel:02d}"

    # Search for the matching par file in the list of par files
    for par_info in par_files:
        if par_info[2].startswith(par_basename):
            # Calculate the absolute path of the par file
            par_path = os.path.join(os.path.join(mira_dir, os.pardir), 'VelocityAnalysis', 'reflex', 'ROHDATA', par_info[2])
            return par_path

    # If we reach here, we couldn't find a matching par file
    return None

def find_matching_rd3_file(rd3_info, mira_file, search_line, search_channel):
    """
    finds the full path to a matching rd3 file upon given line nr and channel nr
    :param rd3_info: list of tuples containg (line, channel, file)
    :param mira_file: full path to a .mira file
    :param search_line: integer of the line number
    :param search_channel: integer of the channel number
    :return: rd3_path, full path to the matching .rd3 file
    """

    # Get directory where the mira file is located
    mira_dir = os.path.dirname(mira_file)

    # Get base name of the mira file (without extension)
    mira_basename = os.path.splitext(os.path.basename(mira_file))[0]

    # Get base name of the rd3 file we're looking for
    rd3_basename = f"{mira_basename}_{search_line:03d}_A{search_channel:03d}"

    # Search for the matching rd3 file in the list of rd3 files
    for rd3_info in rd3_info:
        if rd3_info[2].startswith(rd3_basename):
            # Calculate the absolute path of the rd3 file
            rd3_path = os.path.join(mira_dir, rd3_info[2])
            return rd3_path

    # If we reach here, we couldn't find a matching rd3 file
    return None

def find_image_folder(data_file):
    """
    Finds the full path to the image folder for any given .nc or .fld file.
    :param data_file: full path to file of type .nc or .fld containing a 3D array of GPR data.
    :return: full path to the folder containing the corresponding depthslice images.
    """
    special_suffixes = ['lf', 'rat', 'mig']
    depth_slices = ['01cm', '05cm', '10cm']
    data_file_base = os.path.splitext(os.path.basename(data_file))[0]

    # Check for special folder first
    for suffix in special_suffixes:
        if f'_{suffix}_' in data_file_base:
            parts = data_file_base.split(f'_{suffix}_')
            special_base = 'rad_' + parts[0]
            special_folders = [os.path.join(os.path.dirname(data_file), suffix, ds) for ds in depth_slices]
            for folder in special_folders:
                if os.path.exists(folder) and os.path.isdir(folder):
                    image_files = [f for f in os.listdir(folder) if f.startswith(special_base) and f.lower().endswith(('.jpg', '.jpeg', '.tiff', '.tif'))]
                    if len(image_files) >= 5:
                        return folder  # Found a valid image folder in special folder

    # If not found in special folders, check standard folders
    possible_output_folders = [os.path.splitext(data_file)[0] + '/' + ds + '/' for ds in depth_slices] + \
                              [os.path.dirname(data_file) + '/' + ds + '/' for ds in depth_slices]

    for folder in possible_output_folders:
        if os.path.exists(folder) and os.path.isdir(folder):
            image_files = [f for f in os.listdir(folder) if f.startswith(data_file_base) and f.lower().endswith(('.jpg', '.jpeg', '.tiff', '.tif'))]
            if len(image_files) >= 5:
                return folder  # Found a valid image folder in standard folder

    return None


def save_project_info_to_json(input_file, gui):
    """
    Takes a .fld or .ap_prj file as input, generates a list of .rd3 files in the same directory,
    and saves a JSON file containing the list of .rd3 files along with the path to the
    .mira file.
    """

    if os.path.isfile(input_file):
        file_name = os.path.basename(input_file)

        if file_name.endswith('.ap_prj'):
            ap_prj_file = input_file
            fld_file = find_matching_fld(input_file)
            npy_file = find_matching_npy(fld_file)
            depthslice_folder =find_image_folder(fld_file[0])
            DTM_file = find_DTM_tif_file(fld_file)

        elif file_name.endswith('fld'):
            ap_prj_file = find_matching_apprj_files(input_file)
            fld_file = input_file
            npy_file = find_matching_npy(fld_file)
            depthslice_folder = find_image_folder(fld_file)
            DTM_file = find_DTM_tif_file(fld_file)

        project_key = os.path.splitext(os.path.basename(fld_file))[0]

        # Initialize an empty dictionary with all the keys
        project_data = {
            'ap_prj_file' : None,
            'fld_file' : None,
            'npy_file' : None,
            'depthslice_folder' : None,
            'DTM_file' : None,
        }

        if ap_prj_file:
            project_data['ap_prj_file'] = ap_prj_file

        if fld_file:
            project_data['fld_file'] = fld_file

        if npy_file:
            project_data['npy_file'] = npy_file

        if depthslice_folder:
            project_data['depthslice_folder'] = depthslice_folder


        if DTM_file:
            project_data['DTM_file'] = DTM_file

        folder_path = os.path.dirname(fld_file)
        parent_folder_path = os.path.dirname(folder_path)

        json_file = os.path.join(parent_folder_path, os.path.splitext(os.path.basename(fld_file))[0] + '.json')

        project_data = cleanup_json(project_data)

        data = {}
        data[project_key] = project_data

        if os.path.isfile(json_file):
            root = tk.Tk()
            root.withdraw()
            response = messagebox.askyesnocancel("Warning",
                                                 f"File '{json_file}' already exists. Do you want to overwrite (yes) or rename (no)?",
                                                 parent=gui)

            if response is None:
                return
            elif response is False:
                # Remove existing file and rename it using asksaveasfilename
                os.remove(json_file)
                new_file = asksaveasfilename(initialdir=parent_folder_path, defaultextension=".json")
                if not new_file:
                    return
                json_file = new_file
            elif response is True:
                # Remove existing file
                os.remove(json_file)

        project_data = data
        data = {'projects': data, 'sections': {}}

        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)

        return json_file
def add_data(input_file):
    """
    Takes a .fld or .ap_prj file as input and returns a dictionary with the project data
    """
    if os.path.isfile(input_file):
        file_name = os.path.basename(input_file)

        if file_name.endswith('.ap_prj'):
            ap_prj_file = input_file
            fld_file = find_matching_fld(input_file)
            npy_file = find_matching_npy(fld_file)
            depthslice_folder =find_image_folder(fld_file[0])
            DTM_file = find_DTM_tif_file(fld_file)

        elif file_name.endswith('fld'):
            ap_prj_file = find_matching_apprj_files(input_file)
            fld_file = input_file
            npy_file = find_matching_npy(fld_file)
            depthslice_folder = find_image_folder(fld_file)
            DTM_file = find_DTM_tif_file(fld_file)

        project_key = os.path.splitext(os.path.basename(fld_file))[0]

        # Initialize an empty dictionary with all the keys
        project_data = {
            'ap_prj_file' : None,
            'fld_file' : None,
            'npy_file' : None,
            'depthslice_folder' : None,
            'DTM_file' : None,
        }

        if ap_prj_file:
            project_data['ap_prj_file'] = ap_prj_file

        if fld_file:
            project_data['fld_file'] = fld_file

        if npy_file:
            project_data['npy_file'] = npy_file

        if depthslice_folder:
            project_data['depthslice_folder'] = depthslice_folder

        if DTM_file:
            project_data['DTM_file'] = DTM_file

        project_data = cleanup_json(project_data)

        data = {}
        data[project_key] = project_data

        return data

def cleanup_json(json_data):
    for key, value in json_data.items():
        # If the value is a list, process each item in the list
        if isinstance(value, list):
            new_list = []
            for item in value:
                # Process string paths in the list
                if isinstance(item, str):
                    item = item.replace('\\', '/')
                new_list.append(item)

            # Remove duplicates and None values
            new_list = [v for i, v in enumerate(new_list) if v is not None and v not in new_list[:i]]
            if len(new_list) == 0:
                new_list = None
            json_data[key] = new_list

        # Process string paths that are not in a list
        elif isinstance(value, str):
            json_data[key] = value.replace('\\', '/')

        # If the value is None, leave it as None
        elif value is None:
            json_data[key] = None

    return json_data

def read_project_info_from_json(json_file):
    """
    Reads a .vemop file and returns a dictionary of the stored data.
    """

    if not os.path.isfile(json_file):
        raise ValueError(f"{json_file} is not a valid file path.")

    with open(json_file, 'r') as f:
        data = json.load(f)

    return data

def load_json(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)

    return data

