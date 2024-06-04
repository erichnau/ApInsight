import tkinter as tk
from tkinter import Frame, messagebox

from config_manager import ConfigurationManager


class TopFrameTools(Frame):
    def __init__(self, parent, section, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.config_manager = ConfigurationManager('config.ini')
        self.vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        self.vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        self.section_window = None
        self.section_canvas = None

        self.section = section
        self.topo_corrected = False

        self.create_widgets()
        self.create_zoom_controls()


    def create_widgets(self):
        # Add buttons or other widgets as needed
        save_button = tk.Button(self, text="Export image", command=self.save_section)
        save_button.pack(side="left", padx=5, pady=5)

        topo_correction = tk.Button(self, text='Add topography', command=self.add_topography)
        topo_correction.pack(side='left', padx=5, pady=5)

        clear_topo = tk.Button(self, text='Clear topography', command=self.clear_topography)
        clear_topo.pack(side='left', padx=5, pady=5)

        # Create check buttons for drawing lines and communication
        self.draw_y_line_var = tk.BooleanVar(value=True)
        self.draw_x_line_var = tk.BooleanVar(value=True)
        self.communication_var = tk.BooleanVar(value=True)

        draw_x_line_checkbox = tk.Checkbutton(self, text="Draw X Line", variable=self.draw_y_line_var)
        draw_x_line_checkbox.pack(side="left", padx=5, pady=5)

        draw_y_line_checkbox = tk.Checkbutton(self, text="Draw Y Line", variable=self.draw_x_line_var)
        draw_y_line_checkbox.pack(side="left", padx=5, pady=5)

        communication_checkbox = tk.Checkbutton(self, text="Enable Communication", variable=self.communication_var)
        communication_checkbox.pack(side="left", padx=5, pady=5)

        greyscale_frame = tk.Frame(self, highlightcolor='black', borderwidth=1, relief='solid', pady=5, padx=5)
        greyscale_frame.pack(side='left', padx=10, pady=5)

        greyscale_label = tk.Label(greyscale_frame, text='Greyscale range')
        greyscale_label.pack()

        # vmin entry and arrow buttons
        self.vmin_var = tk.IntVar(value=self.vmin)  # Removed self.vmin definition assumption
        vmin_entry = tk.Entry(greyscale_frame, width=4, textvariable=self.vmin_var)
        vmin_entry.pack(side="left")
        vmin_up_button = tk.Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmin(1))
        vmin_up_button.pack(side="left")
        vmin_down_button = tk.Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmin(-1))
        vmin_down_button.pack(side="left")

        # vmax entry and arrow buttons
        self.vmax_var = tk.IntVar(value=self.vmax)  # Removed self.vmax definition assumption
        vmax_entry = tk.Entry(greyscale_frame, width=4, textvariable=self.vmax_var)
        vmax_entry.pack(side="left")
        vmax_up_button = tk.Button(greyscale_frame, text="▲", command=lambda: self.adjust_vmax(1))
        vmax_up_button.pack(side="left")
        vmax_down_button = tk.Button(greyscale_frame, text="▼", command=lambda: self.adjust_vmax(-1))
        vmax_down_button.pack(side="left")

        default_button = tk.Button(greyscale_frame, text="Default", command=self.reset_to_default_greyscale)
        default_button.pack(side='left', padx=5, pady=5)

        # Bind entry updates
        vmin_entry.bind('<Return>', self.update_vmin_vmax)
        vmax_entry.bind('<Return>', self.update_vmin_vmax)

    def create_zoom_controls(self):
        zoom_in_button = tk.Button(self, text="+", command=lambda: self.section_canvas.zoom_section('in'))
        zoom_in_button.pack(side="left", padx=5, pady=5)
        zoom_out_button = tk.Button(self, text="-", command=lambda: self.section_canvas.zoom_section('out'))
        zoom_out_button.pack(side="left", padx=5, pady=5)

    def set_zoom_controls(self):
        # Bind right-click drag for panning
        self.section_canvas.bind("<Button-3>", self.section_canvas.start_pan)
        self.section_canvas.bind("<B3-Motion>", self.section_canvas.pan_image)


    def save_section(self):
        self.section_window.save_section()

    def add_topography(self):
        self.section_canvas.add_topography()

    def clear_topography(self):
        self.section_canvas.clear_topography()

    def adjust_vmin(self, adjustment):
        new_vmin = self.vmin + adjustment
        if new_vmin < self.vmax:
            self.vmin = new_vmin
            self.vmin_var.set(int(self.vmin))
            self.section_canvas.regenerate_and_refresh_image()
        else:
            self.show_error_message("Invalid Adjustment", "vmin cannot be equal or greater than vmax.")

    def adjust_vmax(self, adjustment):
        new_vmax = self.vmax + adjustment
        if new_vmax > self.vmin:
            self.vmax = new_vmax
            self.vmax_var.set(int(self.vmax))
            self.section_canvas.regenerate_and_refresh_image()
        else:
            self.show_error_message("Invalid Adjustment", "vmax cannot be equal or less than vmin.")

    def update_vmin_vmax(self, event=None):
        try:
            vmin = int(self.vmin_var.get())
            vmax = int(self.vmax_var.get())

            if vmin < vmax:
                self.vmin = vmin
                self.vmax = vmax
                self.section_canvas.regenerate_and_refresh_image()
            else:
                self.show_error_message("Invalid Input", "Ensure that vmin is less than vmax.")
        except ValueError:
            self.show_error_message("Invalid Input", "Please enter numeric values for vmin and vmax.")

    def reset_to_default_greyscale(self):
        # Retrieve vmin and vmax values from the configuration file
        default_vmin = int(self.config_manager.get_option('Greyscale', 'vmin'))
        default_vmax = int(self.config_manager.get_option('Greyscale', 'vmax'))

        # Update the entry widgets with default values
        self.vmin_var.set(default_vmin)
        self.vmax_var.set(default_vmax)

        self.update_vmin_vmax()

    def show_error_message(self, title, message):
        messagebox.showerror(title, message)
        self.focus_set()  # Set the focus back to the SectionView window
        self.lift()  # Bring the SectionView window to the front





