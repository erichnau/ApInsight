from tkinter import Frame, Canvas
from PIL import ImageTk, Image
import math

from GUI.CoordinatesLabel import CoordinatesLabel

class ImageFrame(Frame):
    def __init__(self, master, frame_right, width, height, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master = master
        self.frame_right = frame_right
        self.config(highlightbackground="black", highlightthickness=3)
        self.width = width
        self.height = height
        self.image_path = None
        self.scale = 1.0
        self.delta = 1.1
        self.imscale = 1.0
        self.image = None
        self.imageid = None
        self.x_pos = 0
        self.y_pos = 0

        self.xpixel = 0
        self.ypixels = 0
        self.pixelsize = 0
        self.y_coor = 0.0
        self.x_coor = 0.0

        self.active_section = None
        self.draw_section_mode = False
        self.draw_rectangle_mode = False
        self.section_drawn = False
        self.section_view_active = False
        self.marker_drawn = False

        self.marker = None

        self.create_canvas()

        self.coordinates_label = CoordinatesLabel(self.canvas)


    def data_variables(self, data):
        self.xpixels, self.ypixels, self.pixelsize, self.y_coor, self.x_coor = data.fld_file.xpixels, data.fld_file.ypixels, data.fld_file.pixelsize, data.fld_file.y_coor, data.fld_file.x_coor

    def update_frame_right(self, frame_right):
        self.frame_right = frame_right

    def create_canvas(self):
        self.canvas = Canvas(self, bg='white', highlightthickness=0, width=self.width,
                             height=self.height)
        self.canvas.pack(fill='both', expand=True)

        self.canvas.bind('<Motion>', self.print_canvas_coordinates)

    def create_coordinates_label(self):
        self.coordinates_label = CoordinatesLabel(self.canvas)


    def bindings(self):
        # Unbind the previous bindings
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')

        # Bind the new bindings for zooming and panning
        self.canvas.bind('<ButtonPress-1>', self.move_from)
        self.canvas.bind('<B1-Motion>', self.move_to)
        self.canvas.bind("<Configure>", self.move_from)
        self.canvas.bind('<MouseWheel>', self.zoom)
        self.canvas.bind("<Motion>", self.print_canvas_coordinates)

    def set_draw_section_mode(self):
        # Unbind the previous bindings
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind("<Configure>")
        self.canvas.unbind('<MouseWheel>')

        # Bind the new bindings for drawing sections
        self.canvas.bind('<ButtonPress-1>', self.start_section)
        self.canvas.bind('<B1-Motion>', self.draw_section)
        self.canvas.bind('<ButtonRelease-1>', self.finish_section)
        self.canvas.bind("<Motion>", self.print_canvas_coordinates)

    def set_draw_rectangle_mode(self):
        # Unbind the previous bindings
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        self.canvas.unbind("<Motion>")

        # Bind the new bindings for drawing rectangles
        self.canvas.bind('<ButtonPress-1>', self.start_rectangle)
        self.canvas.bind('<B1-Motion>', self.draw_baseline)
        self.canvas.bind("<Motion>", self.print_canvas_coordinates)


    def finalize_rectangle_mode(self):
        self.canvas.unbind('<ButtonPress-1>')
        self.canvas.unbind('<ButtonRelease-1>')

        self.canvas.bind('<Motion>', self.draw_rectangle)
        self.canvas.bind('<ButtonPress-1>', self.finish_rectangle)

    def set_marker_mode(self):
        self.canvas.tag_bind(self.marker, '<Button-3>', self.select_section_marker)
        self.canvas.tag_bind(self.marker, '<B3-Motion>', self.move_section_marker)
        self.canvas.tag_bind(self.marker, '<ButtonRelease-3>', self.update_marker)

    def clear_marker_mode(self):
        # Check if the marker exists before trying to unbind
        if self.canvas.find_withtag(self.marker):
            self.canvas.tag_unbind(self.marker, '<Button-3>')
            self.canvas.tag_unbind(self.marker, '<B3-Motion>')
            self.canvas.tag_unbind(self.marker, '<ButtonRelease-3>')

    def move_to(self, event):
        """ Drag (move) canvas to the new position """
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def move_from(self, event):
        """ Remember previous coordinates for scrolling with the mouse """
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def zoom(self, event):
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:
            self.scale *= self.delta

        if event.num == 4 or event.delta == 120:
            self.scale /= self.delta

        # Get the mouse cursor position in canvas coordinates
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        self.canvas.scale('all', x, y, self.scale, self.scale)

        self.update_image_canvas(self.image_path)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

        if self.section_drawn:
            self.update_canvas_objects()

    def set_zoom(self, zoom):
        self.scale = zoom
        self.update_image_canvas(self.image_path)
        self.center_image()

    def center_image(self):
        # Get the size of the canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Calculate the zoom level to fit the image in the canvas
        zoom_x = canvas_width / self.image.width
        zoom_y = canvas_height / self.image.height
        zoom = min(zoom_x, zoom_y)
        self.scale = zoom

        # Update the image on the canvas with the new scale
        self.update_image_canvas(self.image_path)

        # Recalculate the scaled image dimensions
        scaled_image_width = int(self.image.width * self.scale)
        scaled_image_height = int(self.image.height * self.scale)

        # Update the scroll region
        self.canvas.configure(scrollregion=(0, 0, scaled_image_width, scaled_image_height))

        # Calculate the scroll positions to center the image
        scroll_x = max(0, (scaled_image_width - canvas_width) / 2) / scaled_image_width
        scroll_y = max(0, (scaled_image_height - canvas_height) / 2) / scaled_image_height

        # Set the scroll positions to center the image
        self.canvas.xview_moveto(scroll_x)
        self.canvas.yview_moveto(scroll_y)

        if self.section_drawn:
            self.update_canvas_objects()

    def update_image_canvas(self, image_path):
        if self.imageid:
            self.canvas.delete(self.imageid)
            self.imageid = None
            self.canvas.photo = None  # delete previous image from the canvas

        self.image_path = image_path
        self.image = Image.open(image_path)
        width, height = self.image.size
        new_size = int(self.scale * width), int(self.scale * height)
        photo = ImageTk.PhotoImage(self.image.resize(new_size))

        # Create the image item at the stored position
        self.imageid = self.canvas.create_image(0, 0, anchor='nw', image=photo)
        self.canvas.lower(self.imageid)
        self.canvas.photo = photo  # Save reference to avoid garbage collection
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

        self.canvas.update_idletasks()

    def canvas_coor_to_global(self, x, y):
        self.centerx = float(self.x_coor)
        self.centery = float(self.y_coor) + (int(self.ypixels)) * self.pixelsize

        glob_x = self.centerx + ((x * self.pixelsize) / self.scale)
        glob_y = self.centery - ((y * self.pixelsize) / self.scale)

        return glob_x, glob_y

    def global_to_canvas_coor(self, glob_x, glob_y):
        self.centerx = float(self.x_coor)
        self.centery = float(self.y_coor) + (int(self.ypixels)) * self.pixelsize

        local_x = (glob_x - self.centerx) * self.scale / self.pixelsize
        local_y = (self.centery - glob_y) * self.scale / self.pixelsize

        return local_x, local_y

    def print_canvas_coordinates(self, event=None, section_x=None, section_y=None):
        if event:
            can_x = self.canvas.canvasx(event.x)
            can_y = self.canvas.canvasy(event.y)
        else:
            can_x = section_x
            can_y = section_y

        img_x, img_y = self.canvas_coor_to_global(can_x, can_y)
        self.coordinates_label.update_coordinates(img_x, img_y)  # Update using the new method

    def start_section(self, event):
        if self.draw_section_mode:
            # Create a point at the clicked position
            self.canvas.delete("section")
            self.canvas.delete("start_p")
            self.canvas.delete("stop_p")

            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            self.canvas.create_oval(canvas_x, canvas_y, canvas_x, canvas_y, tags='start_p', outline='red', width=5)

            self.global_start_p_x, self.global_start_p_y = self.canvas_coor_to_global(canvas_x, canvas_y)

            # Store the starting position of the line
            self.start_x = canvas_x
            self.start_y = canvas_y

    def draw_section(self, event):
        if self.draw_section_mode:
            # Delete the previous line (if any)
            self.canvas.delete("section")

            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            # Draw a line from the starting position to the current mouse position
            self.canvas.create_line(self.start_x, self.start_y, canvas_x, canvas_y, tags="section", fill='red')

    def finish_section(self, event):
        if self.draw_section_mode:
            # Draw the final line
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            self.stop_x, self.stop_y = canvas_x, canvas_y

            self.active_section = {'start': (self.start_x, self.start_y),
                                   'end': (self.stop_x, self.stop_y)}

            self.canvas.create_oval(canvas_x, canvas_y, canvas_x, canvas_y, tags='stop_p', outline = 'orange red', width = 5)
            self.global_stop_x, self.global_stop_y = self.canvas_coor_to_global(canvas_x, canvas_y)
            self.canvas.create_line(self.start_x, self.start_y, canvas_x, canvas_y, tags="section", fill='orange red', width=2)

            self.section_drawn = True
            self.active_section_drawn = True
            self.frame_right.update_button_states(self.section_drawn)
            self.update_canvas_objects()

            self.send_section_to_right_frame((round(self.global_start_p_x, 2), round(self.global_start_p_y, 2)), (round(self.global_stop_x,2), round(self.global_stop_y, 2)))


    def update_canvas_objects(self):
        for section_name, section_info in self.frame_right.sections.items():
            if section_info['select'].get():  # Check if the section is marked as visible
                section_tag = f"section_line_{section_name.replace(' ', '_')}"
                self.canvas.delete(section_tag)  # Delete the existing line for this section

                start_canvas_coords = self.global_to_canvas_coor(*section_info['start'])
                stop_canvas_coords = self.global_to_canvas_coor(*section_info['end'])

                # Create line for each section
                self.canvas.create_line(start_canvas_coords[0], start_canvas_coords[1],
                                        stop_canvas_coords[0], stop_canvas_coords[1],
                                        tags=section_tag, fill='black', width=2)

                # Check if there is an active section to draw
            if self.active_section_drawn:
                # Extract start and stop canvas coordinates from the active section
                start_canvas_coords = self.global_to_canvas_coor(*self.active_section_glob['start'])
                stop_canvas_coords = self.global_to_canvas_coor(*self.active_section_glob['end'])

                # Clear any existing drawings related to the section
                self.canvas.delete('stop_p', 'start_p', 'section', 'label_A', 'label_B')

                # Create ovals and line for the active section
                self.canvas.create_oval(start_canvas_coords[0], start_canvas_coords[1],
                                        start_canvas_coords[0], start_canvas_coords[1],
                                        tags='start_p', outline='orange red', width=3)
                self.canvas.create_oval(stop_canvas_coords[0], stop_canvas_coords[1],
                                        stop_canvas_coords[0], stop_canvas_coords[1],
                                        tags='stop_p', outline='orange red', width=3)
                self.canvas.create_line(start_canvas_coords[0], start_canvas_coords[1],
                                        stop_canvas_coords[0], stop_canvas_coords[1],
                                        tags="section", fill='orange red', width=3)

                self.active_section = {'start': start_canvas_coords, 'end': stop_canvas_coords}

                # Determine angle of the line
                dx = stop_canvas_coords[0] - start_canvas_coords[0]
                dy = stop_canvas_coords[1] - start_canvas_coords[1]
                angle = math.atan2(dy, dx)  # Angle in radians

                # Determine label offset based on angle
                label_offset_x = 20 * math.cos(angle + math.pi / 2)
                label_offset_y = 20 * math.sin(angle + math.pi / 2)

                # Add labels "A" and "B" near the start and stop points
                self.canvas.create_text(start_canvas_coords[0] + label_offset_x, start_canvas_coords[1] + label_offset_y, text="A", tags="label_A",
                                        fill="black", font=("Arial", 14, "bold"))
                self.canvas.create_text(stop_canvas_coords[0] + label_offset_x, stop_canvas_coords[1] + label_offset_y,
                                        text="B", tags="label_B",
                                        fill="black", font=("Arial", 14, "bold"))

        # Redraw marker if it exists
        if self.marker_drawn:
            self.canvas.delete('section_p')
            marker_point_x, marker_point_y = self.global_to_canvas_coor(self.marker_x, self.marker_y)
            marker_line_start_x, marker_line_start_y = self.global_to_canvas_coor(self.marker_line_start_x,
                                                                                  self.marker_line_start_y)
            marker_line_stop_x, marker_line_stop_y = self.global_to_canvas_coor(self.marker_line_stop_x,
                                                                                self.marker_line_stop_y)

            self.canvas.create_oval(marker_point_x - 2.5, marker_point_y - 2.5, marker_point_x + 2.5,
                                    marker_point_y + 2.5,
                                    tags='section_p', outline='green2', width=3)
            self.canvas.create_line(marker_line_start_x, marker_line_start_y, marker_line_stop_x, marker_line_stop_y,
                                    tags='section_p', fill='green2', width=3)

    def section_coor(self, x, y):
        self.marker_x = x
        self.marker_y = y
        x_loc, y_loc = self.global_to_canvas_coor(x, y)

        self.canvas.delete('section_p')
        self.marker_point = self.canvas.create_oval(
            x_loc - 2.5, y_loc - 2.5, x_loc + 2.5, y_loc + 2.5,
            tags='section_p', outline='green2', width=3)

        if self.active_section:
            start_x, start_y = self.active_section['start']
            stop_x, stop_y = self.active_section['end']

            # Calculate slope of the section line
            if stop_x == start_x:
                section_slope = float('inf')  # Vertical line
            else:
                section_slope = (stop_y - start_y) / (stop_x - start_x)

            # Calculate the perpendicular slope
            if section_slope == 0:
                perpendicular_slope = float('inf')  # Vertical line if section line is horizontal
            elif section_slope == float('inf'):
                perpendicular_slope = 0  # Horizontal line if section line is vertical
            else:
                perpendicular_slope = -1 / section_slope

            # Length of the marker line
            line_length = 20

            # Calculate the coordinates for the line endpoints
            if perpendicular_slope == float('inf'):
                # For vertical lines
                line_x1 = x_loc
                line_y1 = y_loc - line_length / 2
                line_x2 = x_loc
                line_y2 = y_loc + line_length / 2
            elif perpendicular_slope == 0:
                # For horizontal lines
                line_x1 = x_loc - line_length / 2
                line_y1 = y_loc
                line_x2 = x_loc + line_length / 2
                line_y2 = y_loc
            else:
                dx = line_length / 2 / ((1 + perpendicular_slope ** 2) ** 0.5)
                dy = perpendicular_slope * dx

                line_x1 = x_loc - dx
                line_y1 = y_loc - dy
                line_x2 = x_loc + dx
                line_y2 = y_loc + dy

            self.marker_line_start_x, self.marker_line_start_y = self.canvas_coor_to_global(line_x1, line_y1)
            self.marker_line_stop_x, self.marker_line_stop_y = self.canvas_coor_to_global(line_x2, line_y2)

            self.marker = self.canvas.create_line(line_x1, line_y1, line_x2, line_y2, tags='section_p', fill='green2',
                                                  width=3)

        self.set_marker_mode()
        self.marker_drawn = True

    def select_section_marker(self, event):
        self.canvas.itemconfig(self.marker, fill='deep sky blue')
        self.canvas.itemconfig(self.marker_point, outline='deep sky blue')

    def update_marker(self, event):
        self.canvas.itemconfig(self.marker, fill='green2')
        self.canvas.itemconfig(self.marker_point, outline='green2')

    def clear_marker(self):
        # First, unbind any events related to the marker.
        self.clear_marker_mode()

        # Check if the marker still exists before deleting
        if self.canvas.find_withtag('section_p'):
            self.canvas.delete('section_p')

        # Update the marker drawn status.
        self.marker_drawn = False

    def move_section_marker(self, event):
        if self.marker:
            # Calculate the current position of the marker line
            current_x1, current_y1, current_x2, current_y2 = self.canvas.coords(self.marker)

            # Get the midpoint of the current marker line
            current_mid_x = (current_x1 + current_x2) / 2
            current_mid_y = (current_y1 + current_y2) / 2

            # Get cursor position
            cursor_x, cursor_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

            # Use active_section to get the closest point
            start_x, start_y = self.active_section['start']
            stop_x, stop_y = self.active_section['end']
            closest_point = self.closest_point_on_line(start_x, start_y, stop_x, stop_y, cursor_x, cursor_y)

            new_mid_x, new_mid_y = closest_point

            # Calculate the movement vector
            movement_vector_x = new_mid_x - current_mid_x
            movement_vector_y = new_mid_y - current_mid_y

            # Move the endpoints of the line by the movement vector
            new_x1 = current_x1 + movement_vector_x
            new_y1 = current_y1 + movement_vector_y
            new_x2 = current_x2 + movement_vector_x
            new_y2 = current_y2 + movement_vector_y

            # Move the marker line
            self.canvas.coords(self.marker, new_x1, new_y1, new_x2, new_y2)

            self.marker_line_start_x, self.marker_line_start_y = self.canvas_coor_to_global(new_x1, new_y1)
            self.marker_line_stop_x, self.marker_line_stop_y = self.canvas_coor_to_global(new_x2, new_y2)
            self.marker_x, self.marker_y = self.canvas_coor_to_global(new_mid_x, new_mid_y)

            # Move the marker line
            #self.canvas.coords(self.marker, new_x1, new_y1, new_x2, new_y2)
            self.canvas.coords(self.marker_point, new_mid_x-2.5, new_mid_y-2.5, new_mid_x+2.5, new_mid_y+2.5)
            if self.section_view_active and self.frame_right.communication_var.get():
                if self.frame_right.draw_x_line_var.get():
                    self.section_view_window.update_x_line(self.marker_x, self.marker_y)

                self.update_section_coordinates_label()

    def update_section_coordinates_label(self):
        self.section_view_window.update_coordinates_label_from_ds(self.marker_x, self.marker_y, self.depth)

    def set_depth(self, depth):
        self.depth = depth
        self.update_section_coordinates_label()

    def define_section_view(self, section_view):
        self.section_view_window = section_view

    def closest_point_on_line(self, x1, y1, x2, y2, x, y):
        # Calculate the closest point on the line segment defined by (x1, y1) and (x2, y2) to the point (x, y)
        dx = x2 - x1
        dy = y2 - y1
        t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))  # Clamp the value of t between 0 and 1 to restrict it to the line segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        return closest_x, closest_y

    def clear_section(self):
        self.canvas.delete('section', 'section_p', 'start_p', 'stop_p', 'label_A', 'label_B')
        self.active_section_drawn = False
        self.frame_right.update_button_states(self.active_section_drawn)
        self.frame_right.disable_section_button()
        self.marker_drawn = False

    def send_section_to_right_frame(self, start_coords, end_coords):
        self.frame_right.add_new_section(start_coords, end_coords)

    def draw_section_line(self, section_name, start_coords, end_coords, visible=True):
        if visible:
            # Using underscore to concatenate the strings
            line_tag = f"section_line_{section_name.replace(' ', '_')}"
            start_x, start_y = self.global_to_canvas_coor(*start_coords)
            end_x, end_y = self.global_to_canvas_coor(*end_coords)
            self.canvas.create_line(start_x, start_y, end_x, end_y, tags=line_tag, fill='black', width=2)

    def update_section_lines(self):
        for section_name, section_info in self.frame_right.sections.items():
            self.update_section_line(section_name, section_info['start'], section_info['end'], section_info['select'].get())

    def update_section_line(self, section_name, start_coords, end_coords, visible):
        line_tag = f"section_line_{section_name.replace(' ', '_')}"
        self.canvas.delete(line_tag)
        if visible:
            self.draw_section_line(section_name, start_coords, end_coords, visible)
        else:
            self.hide_section(section_name)

    def update_section_visibility(self):
        for section_name, section_info in self.frame_right.sections.items():
            if section_info['keep'].get():
                if section_info['select'].get():
                    # Show the section if the 'select' checkbox is checked
                    self.show_section(section_name, section_info['start'], section_info['end'])
                else:
                    # Hide the section if the 'select' checkbox is not checked
                    self.hide_section(section_name)

    def show_section(self, section_name, start_coords, end_coords):
        self.draw_section_line(section_name, start_coords, end_coords, visible=True)

    def hide_section(self, section_name):
        line_tag = f"section_line_{section_name}"

        self.canvas.delete(line_tag)

    def set_active_section(self, section_name):
        if section_name in self.frame_right.sections:
            section_info = self.frame_right.sections[section_name]

            # Convert global coordinates to canvas coordinates
            start_canvas_coords = self.global_to_canvas_coor(*section_info['start'])
            stop_canvas_coords = self.global_to_canvas_coor(*section_info['end'])

            # Set active section with canvas coordinates
            self.active_section = {'start': start_canvas_coords, 'end': stop_canvas_coords}
            self.active_section_glob = {'start': section_info['start'], 'end': section_info['end']}

            self.active_section_drawn = True

            # Optionally, draw the active section and update canvas objects
            self.draw_active_section()  # This function should use the canvas coordinates in 'self.active_section'
            self.update_canvas_objects()  # Ensure this function uses the canvas coordinates


    def draw_active_section(self):
        if self.active_section:
            self.canvas.delete("section", "start_p", "stop_p", "label_A",
                               "label_B")  # Clear any existing section drawings

            # Coordinates for start and stop points
            start_x, start_y = self.active_section['start']
            stop_x, stop_y = self.active_section['end']

            # Draw start and stop points for the active section
            self.canvas.create_oval(start_x, start_y, start_x, start_y, tags='start_p', outline='orange red', width=5)
            self.canvas.create_oval(stop_x, stop_y, stop_x, stop_y, tags='stop_p', outline='orange red', width=5)

            # Draw the line for the active section
            self.canvas.create_line(start_x, start_y, stop_x, stop_y, tags="section", fill='orange red', width=2)

            # Determine angle of the line
            dx = stop_x - start_x
            dy = stop_y - start_y
            angle = math.atan2(dy, dx)  # Angle in radians

            # Determine label offset based on angle
            label_offset_x = 20 * math.cos(angle + math.pi / 2)
            label_offset_y = 20 * math.sin(angle + math.pi / 2)

            # Add labels "A" and "B" near the start and stop points
            self.canvas.create_text(start_x + label_offset_x, start_y + label_offset_y, text="A", tags="label_A",
                                    fill="black", font=("Arial", 14, "bold"))
            self.canvas.create_text(stop_x + label_offset_x, stop_y + label_offset_y, text="B", tags="label_B",
                                    fill="black", font=("Arial", 14, "bold"))



