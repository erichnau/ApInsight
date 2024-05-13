from tkinter import Label


class CoordinatesLabel:
    def __init__(self, master, font=("Arial", 11), initial_width=30):
        self.font = font
        self.label = Label(master, text="", bd=1, relief='sunken', anchor='center', width=initial_width, font=font)
        self.label.pack(side='bottom')
        self.base_width = initial_width

    def update_coordinates(self, x, y, depth=None, elevation=None):
        # Construct the base coordinate text
        text = f" E={x:.2f}, N={y:.2f}"

        # Append depth information if provided
        if depth is not None:
            text += f", Depth={depth:.0f}cm"

        # Append elevation information if provided
        if elevation is not None:
            text += f", Elev={elevation:.2f}m"

        # Adjust the width of the label based on the content
        additional_width = 0
        if depth is not None:
            additional_width += 10  # Assuming 'Depth' adds approximately 15 units to width
        if elevation is not None:
            additional_width += 10  # Assuming 'Elevation' adds approximately 15 units to width

        new_width = self.base_width + additional_width

        # Check if the widget still exists before updating
        if self.label.winfo_exists():
            self.label.configure(text=text, width=new_width)
        else:
            print("Attempted to update a non-existent label.")

