import tkinter as tk

class DTMFileSelector(tk.Toplevel):
    def __init__(self, parent, dtm_files, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.dtm_files = dtm_files
        self.selected_dtm_files = []
        self.confirm_button = None
        self.result = None

        self.title("Select DTM File")
        self.create_widgets()

    def create_widgets(self):
        label = tk.Label(self, text="Multiple DTM files available. Please select the desired DTM file:")
        label.pack()

        # Create checkboxes for each DTM file option
        for dtm_file_key in self.dtm_files.keys():
            dtm_file_path = self.dtm_files[dtm_file_key]

            var = tk.BooleanVar()

            # Create a checkbox for the DTM file option
            checkbox = tk.Checkbutton(self, text=dtm_file_key, variable=var)
            checkbox.dtm_file_path = dtm_file_path  # Store the DTM file path as an attribute of the checkbox
            checkbox.pack()

            # Add a command to handle checkbox selection
            checkbox.config(command=lambda cb=checkbox: self.toggle_dtm_file_selection(cb))

        self.confirm_button = tk.Button(self, text="Confirm", command=self.confirm_selection, state='disabled')
        self.confirm_button.pack()

    def toggle_dtm_file_selection(self, checkbox):
        for cb in self.selected_dtm_files:
            cb.deselect()
        self.selected_dtm_files.clear()
        self.selected_dtm_files.append(checkbox)
        checkbox.select()
        self.confirm_button.config(state='normal')

    def confirm_selection(self):
        self.result = [cb.dtm_file_path for cb in self.selected_dtm_files]
        self.destroy()

    def get_selected_dtm_files(self):
        self.wait_window()
        return self.result