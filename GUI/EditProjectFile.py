from tkinter import *
from tkinter import ttk, filedialog, messagebox, font, PhotoImage
import json
import os
import numpy as np
import threading
from PIL import Image
import platform

from data.data_structure import load_json, save_project_info_to_json, add_data
from GPR_func import read_fld
from config_manager import ConfigurationManager
from GPR_func.read_fld import create_depthslice_images

global edit_project_window

class ProjectGUI(Frame, object):
    def __init__(self, master, frame_left):
        super(ProjectGUI, self).__init__(master)
        self.pack()

        self.config_manager = ConfigurationManager('config.ini')
        self.use_compiled_exe = self.config_manager.get_boolean_option('Application', 'use_compiled_exe')
        self.vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        self.vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        self.section_data = {}
        self.project_open = False

        self.master = master
        self.bold_font = font.Font(weight="bold", size=10)
        self.create_window(master)

        self.frame_left = frame_left
        if self.frame_left:
            self.disable_frame_left()


    def exit(self):
        self.cleanup()
        self.master.destroy()
        if self.frame_left and hasattr(self.frame_left, 'image_listbox') and self.frame_left.image_listbox is not None:
            self.frame_left.image_listbox.config(state=NORMAL)
            self.frame_left.image_listbox.bind("<<ListboxSelect>>", self.frame_left.wrapper_image_selection)

    def disable_frame_left(self):
        if self.frame_left and hasattr(self.frame_left, 'image_listbox') and self.frame_left.image_listbox is not None:
            self.frame_left.image_listbox.config(state=DISABLED)
            self.frame_left.image_listbox.unbind("<<ListboxSelect>>")
    def cleanup(self):
        # Unbind all mousewheel events from the canvas
        self.editor_canvas.unbind_all("<MouseWheel>")

    def create_window(self, root):
        # Create a top frame for the buttons
        self.top_frame = Frame(root, bg='white')
        self.top_frame.pack(side=TOP, fill=X)

        # Create a frame for the file command buttons
        file_command_frame = Frame(self.top_frame, bg='white')
        file_command_frame.pack(side=TOP, fill=X, padx=10, pady=5)

        # Add file command buttons to the file_command_frame
        create_project_button = Button(file_command_frame, text='Create new project', command=self.create_new_project)
        create_project_button.pack(side=LEFT, padx=5)

        open_project_button = Button(file_command_frame, text='Open project', command=self.open_file)
        open_project_button.pack(side=LEFT, padx=5)

        self.save_project_button = Button(file_command_frame, text='Save project', state=DISABLED, command=self.save_file)
        self.save_project_button.pack(side=LEFT, padx=5)

        self.button_add = Button(file_command_frame, text='Add dataset to project', state=DISABLED, command=self.add_dataset_to_project)
        self.button_add.pack(side=LEFT, padx=5)

        exit_button = Button(file_command_frame, text='Exit', command=self.exit)
        exit_button.pack(side=LEFT, padx=5)

        # Create a separator
        separator = ttk.Separator(self.top_frame, orient='horizontal')
        separator.pack(side=TOP, fill=X, pady=5)

        # Create a frame for data-related buttons
        data_command_frame = Frame(self.top_frame, bg='white')
        data_command_frame.pack(side=TOP, fill=X, padx=10, pady=5)

        l1 = Label(data_command_frame, text='1.', font=self.bold_font)
        l1.pack(side='left')

        # Add data-related buttons to the data_command_frame
        button_validate = Button(data_command_frame, text="Validate filepaths", command=self.validate_file_paths)
        button_validate.pack(side=LEFT, padx=5)

        l2 = Label(data_command_frame, text='2.', font=self.bold_font)
        l2.pack(side='left')

        button_check_fld = Button(data_command_frame, text='Check fld files', command=self.check_fld_files)
        button_check_fld.pack(side=LEFT, padx=5)

        l3 = Label(data_command_frame, text='3.', font=self.bold_font)
        l3.pack(side='left')

        self.button_check_ds = Button(data_command_frame, text="Check Depthslice Images", command=self.check_depthslice_images, state='disabled')
        self.button_check_ds.pack(side=LEFT, padx=5)

        # Create a canvas to hold all the input frames
        self.editor_canvas = Canvas(root, bg='white')
        self.editor_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        # Create a scrollbar and associate it with the canvas
        self.scrollbar = ttk.Scrollbar(root, orient=VERTICAL, command=self.editor_canvas.yview)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        self.editor_canvas.configure(yscrollcommand=self.scrollbar.set)

        # Create a frame inside the canvas to hold all the input frames
        self.main_frame = Frame(self.editor_canvas, bg='white')
        self.editor_canvas.create_window((0, 0), window=self.main_frame, anchor=NW)

        # Resize the canvas to fit the contents
        self.main_frame.update_idletasks()
        self.editor_canvas.config(scrollregion=self.editor_canvas.bbox("all"))

        # Bind the mousewheel event to the canvas
        self.editor_canvas.bind_all("<MouseWheel>", self.on_mousewheel)


    def create_input_frame(self, root, key, value, row):
        # Create a new label frame for the input with the given key
        input_frame = LabelFrame(root, text=key, bg="lightgray", font=('Consolas', 12))
        input_frame.grid(row=row, column=0, padx=10, pady=10, sticky=W)

        # Define a function to open a file dialog and set the selected file path in the given entry widget
        def open_file_dialog(entry):
            file_path = filedialog.askopenfilename(parent=self.master, initialdir=self.initial_directory, title='Select File',
                                                   filetypes=(('DTM TIFF Files', '*.tif'), ('All Files', '*.*')))
            if file_path:
                entry.delete(0, END)
                entry.insert(END, file_path)

        def open_folder(entry):
            entry.config(state='normal')
            folder_path = filedialog.askdirectory(parent=self.master, initialdir=self.initial_directory, title='Select depthslice folder')
            if folder_path:
                entry.delete(0, END)
                entry.insert(END, folder_path)
            entry.config(state='readonly')

        def process_fld(entry):
            fld_file = entry.get()
            self.fld_to_process = [fld_file]
            self.preprocess_fld_files(single=True)

            self.npy = fld_file.rsplit('.', 1)[0] + '.npy'

            self.project_key = os.path.splitext(os.path.basename(fld_file))[0]

            self.save_file(update_npy=True)

        def resize_window_to_content(input_frame):
            total_width = 0

            # Iterate through all widgets in the frame and calculate the total width
            for widget in input_frame.winfo_children():
                widget.update_idletasks()  # Update widget layout
                width = widget.winfo_width()
                total_width += width  # Consider the widest widget

            # Get current window height
            current_height = edit_project_window.winfo_height()

            # Set new width (with some additional padding if necessary)
            new_width = total_width + 42  # 20 is arbitrary padding

            # Resize the window
            edit_project_window.geometry(f"{new_width}x{current_height}")

        def add_row(input_frame, base_row, add_row_button):
            fld_key = None
            # Remove the current 'Add Row' button
            add_row_button.grid_forget()

            # Calculate the new row index within the input_frame
            new_row = base_row + len([child for child in input_frame.winfo_children() if isinstance(child, Frame)])

            # Create a new frame for the additional row
            new_frame = Frame(input_frame, bg="lightgray")
            new_frame.grid(row=new_row, column=0, columnspan=4, sticky="w")

            # Add a new entry widget
            entry = Entry(new_frame, width=100, borderwidth=2, fg="black", font=('Consolas', 12))
            entry.grid(row=0, column=1, sticky=W)

            # Add an 'Open File' button to open a file dialog for the entry widget
            file_button = Button(new_frame, text="Select file", command=lambda e=entry: open_file_dialog(e))
            file_button.grid(row=0, column=3, padx=5)

            # Add a new "Add Row" button below the newly added row
            add_row_button = Button(input_frame, text="Add Row",
                                    command=lambda: add_row(input_frame, new_row, add_row_button))
            add_row_button.grid(row=new_row + 1, column=3, pady=10)

            # Update the main frame and the canvas
            input_frame.update_idletasks()
            self.editor_canvas.config(scrollregion=self.editor_canvas.bbox("all"))

        if key == 'ap_prj_file':
            entry = Entry(input_frame, width=100, borderwidth=2, fg="black", font=('Consolas', 12))
            entry.grid(row=0, column=1, sticky=W)
            entry.insert(END, str(value))
            entry.config(state='readonly')

        if key == 'fld_file':
            entry = Entry(input_frame, width=100, borderwidth=2, fg="black", font=('Consolas', 12))
            entry.grid(row=0, column=1, sticky=W)
            entry.insert(END, str(value))
            entry.config(state='readonly')

            self.fld_key = value

            preprocess_fld_button = Button(input_frame, text="Preprocess fld", command=lambda e=entry: process_fld(e))
            preprocess_fld_button.grid(row=0, column=3, padx=5)

        if key == 'npy_file':
            entry = Entry(input_frame, width=100, borderwidth=2, fg="black", font=('Consolas', 12))
            entry.grid(row=0, column=1, sticky=W)
            entry.insert(END, str(value))
            entry.config(state='readonly')

        elif key == 'depthslice_folder':
            ds_entry = Entry(input_frame, width=100, borderwidth=2, fg="black", font=('Consolas', 12))
            ds_entry.grid(row=0, column=1, sticky=W)
            ds_entry.insert(END, str(value))
            ds_entry.config(state='readonly')

            locate_button = Button(input_frame, text="Select folder", command=lambda e=ds_entry: open_folder(e))
            locate_button.grid(row=0, column=3, padx=5)

        elif key == 'DTM_file':
            # Check if the value is a list and iterate over it, otherwise, put it in a list
            dtm_values = value if isinstance(value, list) else [value]

            # Initial row for DTM data within the input_frame
            dtm_row = 0

            for dtm_value in dtm_values:
                # Add an entry for each DTM file
                dtm_entry = Entry(input_frame, width=100, borderwidth=2, fg="black", font=('Consolas', 12))
                dtm_entry.grid(row=dtm_row, column=1, sticky=W)

                # Add an 'Open File' button for each DTM file
                file_button = Button(input_frame, text="Select file", command=lambda e=dtm_entry: open_file_dialog(e))
                file_button.grid(row=dtm_row, column=3, padx=5)

                dtm_row += 1  # Increment the row for the next DTM entry

            # Add an "Add Row" button after all existing DTM entries
            add_row_button = Button(input_frame, text="Add Row",
                                    command=lambda: add_row(input_frame, dtm_row, add_row_button))
            add_row_button.grid(row=dtm_row, column=3, pady=10)

            if 'DTMfromGPR' in self.fld_key:
                dtm_entry.insert(END, 'None')
                dtm_entry.config(state='disabled')
                file_button.config(state='disabled')
                add_row_button.config(state='disabled')
            else:
                dtm_entry.insert(END, str(dtm_value))

        row += 1

        resize_window_to_content(input_frame)

        return row

    def open_file(self, file_path=None):
        if file_path is None:
            file_path = filedialog.askopenfilename(parent=self.master, title='Select File',
                                                   filetypes=(('JSON files', '*.json'), ('All files', '*.*')))

        if file_path:
            if self.editor_canvas:
                self.editor_canvas.destroy()
                self.top_frame.destroy()
                self.scrollbar.destroy()

            self.create_window(self.master)

            # Create the main frame and add it to the canvas
            self.main_frame = Frame(self.editor_canvas, bg='white')
            self.editor_canvas.create_window((0, 0), window=self.main_frame, anchor=NW)

            # Load the selected JSON file
            all_data = load_json(file_path)
            all_projects_data = all_data.get("projects", {})
            self.section_data = all_data.get('sections', {})

            # Variable to keep track of the current row in the main frame
            main_row = 0

            # Iterate over each project in the JSON file
            for project_key, project_data in all_projects_data.items():
                # Create a new frame for each project
                project_frame = LabelFrame(self.main_frame, text=project_key, bg="lightgray", font=('Consolas', 12))
                project_frame.grid(row=main_row, column=0, padx=10, pady=10, sticky=W)

                # Variable to keep track of the current row in the project frame
                project_row = 0

                # Iterate over each key-value pair in the project data
                for data_key, data_value in project_data.items():
                    project_row = self.create_input_frame(project_frame, data_key, data_value, project_row)

                if len(all_projects_data) > 1:
                    remove_button = Button(project_frame, text="Remove dataset",
                                           command=lambda key=project_key: self.remove_project(key))
                    remove_button.grid(row=project_row, column=0, padx=5, pady=5)

                # Update the main row index
                main_row += 1

            # Update the main frame and the canvas
            self.main_frame.update_idletasks()
            self.editor_canvas.config(scrollregion=self.editor_canvas.bbox("all"))

            self.json_file_path = file_path
            self.initial_directory = os.path.dirname(self.json_file_path)

            self.master.lift()

            self.main_frame.update_idletasks()
            self.editor_canvas.config(scrollregion=self.editor_canvas.bbox("all"))

            self.project_open = True
            self.activate_buttons()

    def activate_buttons(self):
        self.button_add.config(state=NORMAL)
        self.save_project_button.config(state=NORMAL)

    def add_dataset_to_project(self):
        # Open a file dialog to let the user select an .fld or .ap_prj file
        file_path = filedialog.askopenfilename(parent=self.master, initialdir=self.initial_directory, title='Select File',
                                               filetypes=(('fld files', '*.fld'), ('ap_prj files', '*.ap_prj'),
                                                          ('All files', '*.*')))
        if not file_path:
            return  # User cancelled the file selection

        # Generate project data from the selected file
        new_project_data = add_data(file_path)

        # Load existing JSON data
        json_file_path = self.json_file_path
        existing_data = load_json(self.json_file_path) if os.path.exists(json_file_path) else {}
        project_data = existing_data['projects']

        # Append the new project data to the existing data
        project_data.update(new_project_data)

        new_data = {"projects": project_data, 'sections': self.section_data}

        # Save the updated data back to the JSON file
        with open(json_file_path, 'w') as f:
            json.dump(new_data, f, indent=4)

        # Refresh the GUI
        self.open_file(self.json_file_path)

    def remove_project(self, project_key):
        # Load the existing projects
        all_data = load_json(self.json_file_path)
        all_projects_data = all_data['projects']
        sections = all_data['sections']

        del all_projects_data[project_key]

        data_to_save = {"projects": all_projects_data, 'sections': self.section_data}

        # Save the modified data back to the JSON file
        with open(self.json_file_path, 'w') as f:
            json.dump(data_to_save, f, indent=4)

        # Re-open the file to refresh the GUI
        self.open_file(self.json_file_path)

        self.main_frame.update_idletasks()
        self.editor_canvas.config(scrollregion=self.editor_canvas.bbox("all"))


    def save_file(self, update_npy=False):
        if self.project_open:
            # Initialize an empty dictionary to hold all project data
            all_projects_data = {}

            # Iterate over the main frame's children (each child is a project LabelFrame)
            for project_frame in self.main_frame.winfo_children():
                if isinstance(project_frame, LabelFrame):
                    project_key = project_frame.cget('text')
                    project_data = {}

                    # Iterate over the main frame's children
                    for frame in project_frame.winfo_children():
                        if isinstance(frame, LabelFrame):
                            key = frame.cget('text')
                            value = []
                            # Iterate over the children of the LabelFrame
                            for child in frame.winfo_children():
                                if isinstance(child, Entry):
                                    if child.get():
                                        value.append(child.get())
                                elif isinstance(child, Frame):
                                    # Iterate over the children of the nested frame
                                    for entry in child.winfo_children():
                                        if isinstance(entry, Entry):
                                            if entry.get():
                                                value.append(entry.get())

                            if len(value) > 1:
                                project_data[key] = value
                            else:
                                project_data[key] = value[0]

                    if update_npy:
                        if project_key == self.project_key:
                            project_data['npy_file'] = self.npy

                    all_projects_data[project_key] = project_data

            data_to_save = {"projects": all_projects_data, 'sections': self.section_data}

            initial_file = os.path.basename(self.json_file_path)

            if not update_npy:
                # Create and focus the save file dialog
                file_dialog = filedialog.asksaveasfile(parent=self.master, initialdir=self.initial_directory, title='Save File',
                                                   filetypes=(('JSON files', '*.json'), ('All files', '*.*')), initialfile=initial_file)


                if file_dialog:
                    self.json_file_path = file_dialog.name
                    with open(self.json_file_path, 'w') as f:
                        json.dump(data_to_save, f, indent=4)
            else:
                with open(self.json_file_path, 'w') as f:
                    json.dump(data_to_save, f, indent=4)

            if self.main_frame:
                self.main_frame.destroy()
            self.open_file(self.json_file_path)

        else:
            pass

    def create_new_project(self, file_path=None):
        filetypes = [("FLD files", "*.fld"), ("AP_PRJ files", "*.ap_prj")]
        file_path = filedialog.askopenfilename(parent=self.master, title="Select a project file", filetypes=filetypes)

        if file_path:
            # Save project information to JSON file
            self.json_file_path = save_project_info_to_json(file_path, self.master)

            if not self.json_file_path:
                return

            # Open the JSON file
            self.open_file(self.json_file_path)

    def validate_file_paths(self):
        for project_frame in self.main_frame.winfo_children():
            if isinstance(project_frame, LabelFrame):
                for frame in project_frame.winfo_children():
                    if isinstance(frame, LabelFrame):
                        for child in frame.winfo_children():
                            if isinstance(child, Entry):
                                path = child.get()
                                if path:
                                    validation_label = Label(frame, width=2,
                                                             bg='grey')  # Create a small label for validation
                                    validation_label.grid(row=0, column=2)
                                    if os.path.isfile(path) or (
                                            frame.cget('text') == 'depthslice_folder' and os.path.isdir(path)):
                                        validation_label.config(bg='light green')
                                    else:
                                        validation_label.config(bg='#ffcccc')

    def check_fld_files(self):
        results = []
        self.fld_to_process = []
        all_processed = True

        # Iterate through each project dataset
        for project_frame in self.main_frame.winfo_children():
            if isinstance(project_frame, LabelFrame):
                project_key = project_frame.cget('text')
                fld_file_path = self.get_fld_file_path(project_frame)
                if fld_file_path:
                    _, _, _, _, _, _, _, _, _, xpixels, ypixels = read_fld.read_fld_size(fld_file_path)
                    npy_file = fld_file_path.replace('.fld', '.npy')
                    if os.path.exists(npy_file):
                        data = np.load(npy_file)

                        if data.shape[-2:] == (ypixels, xpixels):
                            results.append(f'Fld file {os.path.basename(fld_file_path)} already processed')
                        else:
                            results.append(
                                f'Fld file {os.path.basename(fld_file_path)} not processed due to shape mismatch')
                            self.fld_to_process.append(fld_file_path)
                            all_processed = False
                    else:
                        results.append(f'Fld file {os.path.basename(fld_file_path)} not processed')
                        self.fld_to_process.append(fld_file_path)
                        all_processed = False

        # Create and display the results in a new window
        self.display_fld_results(results)

        # Update the state of the check FLD button
        if all_processed:
            self.preprocess_button.config(state='disabled')
            self.button_check_ds.config(state='normal')
        else:
            self.preprocess_button.config(state='normal')

    def get_fld_file_path(self, project_frame):
        # Iterate through each input frame to find the fld file path
        for frame in project_frame.winfo_children():
            if isinstance(frame, LabelFrame) and frame.cget('text') == 'fld_file':
                for child in frame.winfo_children():
                    if isinstance(child, Entry):
                        return child.get()
        return None

    def display_fld_results(self, results):
        self.results_window = Toplevel(self.master)
        self.results_window.title("FLD File Check Results")
        if platform.system() =='Windows':
            self.results_window.iconbitmap('icon2.ico')
        else:
            icon_image = PhotoImage(file='icon2.png')
            self.results_window.iconphoto(True, icon_image)
        self.results_window.geometry("400x300+300+300")

        f = Frame(self.results_window, pady=5, padx=5)
        f.pack(side='top', padx=5, pady=5)

        # Display each result in the window
        for result in results:
            label = Label(f, text=result)
            label.pack(side='top', padx=5, pady=5)

        # Add OK button
        ok_button = Button(f, text="OK", command=self.results_window.destroy)
        ok_button.pack(side='top', pady=5, padx=5)

        # Add 'Preprocess fld' button
        self.preprocess_button = Button(f, text="Preprocess fld", command=lambda :self.preprocess_fld_files(single=False))
        self.preprocess_button.pack(side='top', padx=5, pady=5)

    def preprocess_fld_files(self, single=False):
        # Create and display the progress bar window
        progress_window = Toplevel(self.master)
        progress_window.title("Processing FLD Files")
        progress_window.geometry("300x100+350+350")

        progress_bar = ttk.Progressbar(progress_window, orient='horizontal', length=200, mode='indeterminate')
        progress_bar.pack(pady=20)
        progress_bar.start()

        # Define the processing function
        def process_files():
            for entry in self.fld_to_process:

                # Use the compiled executable function if not containing "DTM" and the compiled exe is to be used
                if self.use_compiled_exe:
                    _, _, _, self.zpixels, _, _, _, self.pixelsize_z, _, _, _ = read_fld.define_fld_parameters_cpp(entry, overwrite=True)
                    if self.zpixels == None:
                        progress_window.destroy()
                        return
                else:
                    _, _, _, self.zpixels, _, _, _, self.pixelsize_z, _, _, _ = read_fld.define_fld_parameters(entry, overwrite=True)
            # Close the progress bar window after processing
            progress_window.destroy()

            if not single:
                self.results_window.destroy()
                self.update_json_with_npy(self.json_file_path)
                self.check_fld_files()

        # Run the processing in a separate thread
        processing_thread = threading.Thread(target=process_files)
        processing_thread.start()

    def update_json_with_npy(self, json_file_path):
        data = load_json(json_file_path)
        project_data = data['projects']
        section_data = data['sections']

        for project_key, project_info in project_data.items():
            fld_file_path = project_info.get('fld_file', None)
            if fld_file_path:
                npy_file_path = fld_file_path.replace('.fld', '.npy')
                if os.path.exists(npy_file_path):
                    project_info['npy_file'] = npy_file_path

        data_to_save = {"projects": project_data, 'sections': section_data}
        with open(json_file_path, 'w') as json_file:
            json.dump(data_to_save, json_file, indent=4)

        self.open_file(json_file_path)

    def check_depthslice_images(self):
        check_results = {}

        # Iterate over each project frame in the main frame
        for project_frame in self.main_frame.winfo_children():
            if isinstance(project_frame, LabelFrame):
                fld_file_path = None
                depthslice_folder_path = None

                for frame in project_frame.winfo_children():
                    if isinstance(frame, LabelFrame):
                        key = frame.cget('text')
                        if key == 'fld_file':
                            entry_widget = frame.winfo_children()[0]
                            fld_file_path = entry_widget.get()
                        elif key == 'depthslice_folder':
                            entry_widget = frame.winfo_children()[0]
                            depthslice_folder_path = entry_widget.get()

                if fld_file_path:
                    zpixels, pixelsize_z, x_coor, y_coor, pixelsize_x, depth_table, time_table, data_type, z_vals, xpixels, ypixels = read_fld.read_fld_size(fld_file_path)

                    if not os.path.exists(depthslice_folder_path):
                        depthslice_folder_path = 'None'

                    if depthslice_folder_path != 'None':
                        missing_images = self.check_ds_folder(fld_file_path, zpixels, round(pixelsize_z * 100),
                                                          depthslice_folder_path, data_type)
                        filesize = self.check_ds_images_size(depthslice_folder_path, fld_file_path, xpixels, ypixels)
                        if not filesize: missing_images.append('filesize')
                    else:
                        missing_images = ['dummy']

                    # Store whether there are missing images or not, along with other data
                    check_results[fld_file_path] = {
                        "missing_images": bool(missing_images),  # True if there are missing images, otherwise False
                        "zpixels": zpixels,
                        "pixelsize_z": pixelsize_z,
                        "pixelsize_x": pixelsize_x,
                        "x_coor": x_coor,
                        "y_coor": y_coor,
                        "depth_table": depth_table,
                        "time_table": time_table,
                        "data_type": data_type,
                        "z_vals": z_vals
                    }
        # Call the function to display the results
        self.display_depthslice_check_results(check_results)

    def check_ds_folder(self, fld_file_path, zpixels, pixelsize_z, depthslice_folder_path, data_type):
        missing_images = []
        fld_base_name = os.path.splitext(os.path.basename(fld_file_path))[0]

        # Determine the base name for the depthslice image files
        special_base = 'rad_' + fld_base_name.split('_')[0] if any(
            suffix in fld_base_name for suffix in ['lf', 'rat', 'mig']) else fld_base_name

        # Check for special conditions
        if data_type == 2 or 'DTMfromGPR' in fld_base_name:
            # For pixelsize_z = 0.01 or 'DTM' in filename, check only the count of images in the folder
            exclude_prefix = f"all_{fld_base_name}"
            image_files = [name for name in os.listdir(depthslice_folder_path)
                           if name.endswith('.tif') and not name.startswith(exclude_prefix)]
            image_count = len(image_files)
            if image_count != zpixels:
                missing_images.append(f"Expected {zpixels} images, found {image_count}")
        else:
            # Check for image filenames based on the special base and standard base
            for i in range(zpixels):
                depth_start = i * pixelsize_z
                depth_end = (i + 1) * pixelsize_z
                special_image_name = f"{special_base}_{depth_start:03d}-{depth_end:03d}.tif"
                standard_image_name = f"{fld_base_name}_{depth_start:03d}-{depth_end:03d}.tif"
                special_image_path = os.path.join(depthslice_folder_path, special_image_name)
                standard_image_path = os.path.join(depthslice_folder_path, standard_image_name)

                if not os.path.exists(special_image_path) and not os.path.exists(standard_image_path):
                    missing_images.append(
                        special_image_name if os.path.exists(special_image_path) else standard_image_name)
        return missing_images

    def check_ds_images_size(self, depthslice_folder_path, fld_file_path, xpixels, ypixels):
        fld_base_name = os.path.splitext(os.path.basename(fld_file_path))[0]
        exclude_prefix = f"all_{fld_base_name}"

        # Iterate through each file in the folder
        for file in os.listdir(depthslice_folder_path):
            if file.endswith('.tif') and not file.startswith(exclude_prefix):
                image_path = os.path.join(depthslice_folder_path, file)

                # Open the image and check its size
                with Image.open(image_path) as img:
                    width, height = img.size
                    if width != xpixels or height != ypixels:
                        return False  # Image size doesn't match expected dimensions

        return True  # All images match the expected dimensions

    def display_depthslice_check_results(self, check_results):
        self.selected_datasets = {}
        self.results_window = Toplevel(self.master)
        if platform.system() =='Windows':
            self.results_window.iconbitmap('icon2.ico')
        else:
            icon_image = PhotoImage(file='icon2.png')
            self.results_window.iconphoto(True, icon_image)
        self.results_window.title("Depthslice Images Check")
        self.results_window.geometry("500x400+300+300")

        # Store extra data for creating depthslice images
        self.depthslice_data = {}

        f = Frame(self.results_window, pady=5, padx=5)
        f.pack(side='top', padx=5, pady=5)

        # Display each result with a checkbutton
        for fld_file_path, data in check_results.items():
            fld_filename = os.path.basename(fld_file_path)
            missing_images = data['missing_images']

            text = f"{fld_filename}: {'missing depthslice images detected' if missing_images else 'all depthslice images found'}"
            var = BooleanVar(value=missing_images)
            checkbutton = Checkbutton(self.results_window, text=text, variable=var, command=self.update_create_button_state)
            checkbutton.pack(side='top', pady=5, padx=5)
            self.selected_datasets[fld_file_path] = var

            self.depthslice_data[fld_filename] = {
                "zpixels": data["zpixels"],
                "pixelsize_z": data["pixelsize_z"],
                "pixelsize_x": data["pixelsize_x"],
                "x_coor": data["x_coor"],
                "y_coor": data["y_coor"],
                "depth_table": data["depth_table"],
                "time_table": data["time_table"],
                "data_type": data["data_type"],
                "z_vals": data["z_vals"],
                "fld_file_path": fld_file_path
            }

        # Create a separator
        separator = ttk.Separator(self.results_window, orient='horizontal')
        separator.pack(side=TOP, fill=X, pady=5)

        greyscale_frame = Frame(self.results_window, highlightbackground='black', highlightthickness=1, padx=5, pady=5)
        greyscale_frame.pack(side=TOP, pady=5, padx=5)

        greyscale_label = Label(greyscale_frame, text='Greyscale range')
        greyscale_label.pack()

        # vmin entry and arrow buttons
        self.vmin_var = IntVar(value=self.vmin)  # Assuming self.vmin is defined
        vmin_entry = Entry(greyscale_frame, width=4, textvariable=self.vmin_var)
        vmin_entry.pack(side="left")
        vmin_up_button = Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmin(1))
        vmin_up_button.pack(side="left")
        vmin_down_button = Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmin(-1))
        vmin_down_button.pack(side="left")

        # vmax entry and arrow buttons
        self.vmax_var = IntVar(value=self.vmax)  # Assuming self.vmax is defined
        vmax_entry = Entry(greyscale_frame, width=4, textvariable=self.vmax_var)
        vmax_entry.pack(side="left")
        vmax_up_button = Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmax(1))
        vmax_up_button.pack(side="left")
        vmax_down_button = Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmax(-1))
        vmax_down_button.pack(side="left")

        default_button = Button(greyscale_frame, text="Default", command=self.reset_to_default_greyscale)
        default_button.pack(side='left', pady=5, padx=5)

        # Create depthslice images button
        self.create_button = Button(self.results_window, text="Create depthslice images for selected datasets",
                               command=self.create_selected_depthslice_images)
        self.create_button.pack(side=TOP, padx=5, pady=5)

        # OK button
        ok_button = Button(self.results_window, text="Exit", command=self.results_window.destroy)
        ok_button.pack(side=TOP, padx=5, pady=5)

        self.update_create_button_state()

    def update_create_button_state(self):
        # Enable the create_button if any checkbox is selected
        if any(var.get() for var in self.selected_datasets.values()):
            self.create_button.config(state=NORMAL)
        else:
            self.create_button.config(state=DISABLED)

    def create_selected_depthslice_images(self):
        vmin = self.vmin_var.get()
        vmax = self.vmax_var.get()

        # Create and display the progress bar window
        progress_window = Toplevel(self.master)
        progress_window.title("Processing Depthslice Images")
        progress_window.geometry("300x100+350+350")

        progress_bar = ttk.Progressbar(progress_window, orient='horizontal', length=200, mode='indeterminate')
        progress_bar.pack(pady=20)
        progress_bar.start()

        def process_files():
            depthslice_folder_updates = {}
            for fld_file_path, var in self.selected_datasets.items():
                fld_filename = os.path.basename(fld_file_path)
                if var.get():  # Check if the dataset is selected
                    data = self.depthslice_data[fld_filename]
                    if data:
                        npy_file_path = data["fld_file_path"].replace('.fld', '.npy')
                        zpixels = data["zpixels"]
                        pixelsize_z = data["pixelsize_z"]
                        pixelsize_x = data["pixelsize_x"]  # Ensure this is stored or calculated appropriately
                        x_coor = data["x_coor"]
                        y_coor = data["y_coor"]
                        depth_table = data["depth_table"]
                        time_table = data["time_table"]
                        data_type = data["data_type"]
                        z_vals = data["z_vals"]

                        # Call the function to create depthslice images
                        depthslice_folder_path = create_depthslice_images(vmin, vmax, npy_file_path, zpixels, pixelsize_z, pixelsize_x, x_coor,
                                                 y_coor, depth_table, time_table, data_type, z_vals)
                        depthslice_folder_updates[fld_filename.rsplit('.')[0]] = depthslice_folder_path


            progress_window.destroy()
            self.results_window.destroy()
            self.update_json_with_depthslice_folder(self.json_file_path, depthslice_folder_updates)
            self.check_depthslice_images()

        # Run the processing in a separate thread
        processing_thread = threading.Thread(target=process_files)
        processing_thread.start()

    def update_json_with_depthslice_folder(self, json_file_path, depthslice_folder_updates):
        data = load_json(json_file_path)
        project_data = data['projects']
        section_data = data['sections']

        for project_key, folder_path in depthslice_folder_updates.items():
            if project_key in project_data:
                project_data[project_key]['depthslice_folder'] = folder_path

        data_to_save = {"projects": project_data, 'sections': section_data}

        with open(json_file_path, 'w') as json_file:
            json.dump(data_to_save, json_file, indent=4)

        self.open_file(json_file_path)

    def on_mousewheel(self, event):
        # Get the current view region
        view_start, view_end = self.editor_canvas.yview()

        # Scroll up
        if event.delta > 0 and view_start > 0:
            self.editor_canvas.yview_scroll(-1, "units")

        # Scroll down
        elif event.delta < 0 and view_end < 1:
            self.editor_canvas.yview_scroll(1, "units")

    def adjust_vmin(self, adjustment):
        new_vmin = self.vmin + adjustment
        if new_vmin < self.vmax:
            self.vmin = int(new_vmin)
            self.vmin_var.set(self.vmin)
        else:
            self.show_error_message("Invalid Adjustment", "vmin cannot be equal or greater than vmax.")

    def adjust_vmax(self, adjustment):
        new_vmax = self.vmax + adjustment
        if new_vmax > self.vmin:
            self.vmax = int(new_vmax)
            self.vmax_var.set(self.vmax)
        else:
            self.show_error_message("Invalid Adjustment", "vmax cannot be equal or less than vmin.")

    def update_vmin_vmax(self, event=None):
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())

            if vmin < vmax:
                self.vmin = vmin
                self.vmax = vmax
            else:
                self.show_error_message("Invalid Input", "Ensure that vmin is less than vmax.")
        except ValueError:
            self.show_error_message("Invalid Input", "Please enter numeric values for vmin and vmax.")

    def show_error_message(self, title, message):
        global edit_project_window
        messagebox.showerror(title, message)
        edit_project_window.focus_set()
        edit_project_window.lift()
        self.results_window.focus_set()  # Set the focus back to the SectionView window
        self.results_window.lift()  # Bring the SectionView window to the front

    def reset_to_default_greyscale(self):
        # Retrieve vmin and vmax values from the configuration file
        default_vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        default_vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        # Update the entry widgets with default values
        self.vmin_var.set(default_vmin)
        self.vmax_var.set(default_vmax)

        self.update_vmin_vmax()

def start_projectGUI(root, frame_left):
    # Create main window and canvas
    global edit_project_window
    edit_project_window = Toplevel(root)
    if platform.system() == 'Windows':
        edit_project_window.iconbitmap('icon2.ico')
    else:
        icon_image = PhotoImage(file='icon2.png')
        edit_project_window.iconphoto(True, icon_image)
    edit_project_window.title('Edit project file')
    edit_project_window.geometry("1080x720")
    edit_project_window.configure(bg='LightBlue')

    app = ProjectGUI(edit_project_window, frame_left)

    # Bind the closing event to the cleanup method
    edit_project_window.protocol("WM_DELETE_WINDOW", app.exit)

    app.mainloop()




