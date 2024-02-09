import tkinter as tk
from tkinter import PhotoImage
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
