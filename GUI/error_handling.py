import tkinter as tk
from tkinter import PhotoImage, messagebox
import platform

def show_error_dialog(message):
    # Create a top-level window with 'parent' as its master
    error_dialog = tk.Toplevel()
    error_dialog.title("Error")
    if platform.system() == 'Windows':
        error_dialog.iconbitmap('icon2.ico')
    else:
        icon_image = PhotoImage(file='icon2.png')
        error_dialog.iconphoto(True, icon_image)

    # Add a label with the error message
    label = tk.Label(error_dialog, text=message)
    label.pack(padx=10, pady=10)

    # Add an OK button
    ok_button = tk.Button(error_dialog, text="OK", command=error_dialog.destroy)
    ok_button.pack(pady=(0, 10))

def confirm_python_processing(root, expected_size):
    root = root

    expected_size = str(round((expected_size / 1024**2), 2))

    message = f"The expected npy-file size is {expected_size}MB, the program can only use Python code to process the file, which is significantly slower (the processing might take several minutes). Do you want to continue?"

    response = messagebox.askyesno("Processing Confirmation", message)

    # The response will be True if the user clicks 'Yes' and False if the user clicks 'No'.
    return response
