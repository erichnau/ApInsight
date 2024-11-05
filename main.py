from tkinter import Tk, PhotoImage
from screeninfo import get_monitors
import platform

from config_manager import ConfigurationManager
from GUI.DepthsliceViewer_main import GuiLayout

monitors = get_monitors()
screen_res_primary = [monitors[0].height, monitors[0].width]

config_manager = ConfigurationManager('config.ini')


def start_apinsight():
    global root
    root = Tk()
    root.title("ApInsight")
    root.geometry("%dx%d+0+0" % (screen_res_primary[1], screen_res_primary[0]))

    if platform.system() == 'Windows':
        # Maximize the window on Windows
        root.iconbitmap('icons/icon2.ico')
        root.state('zoomed')
    else:
        icon_image = PhotoImage(file='icons/icon2.png')
        root.iconphoto(True, icon_image)
        root.attributes('-zoomed', True)
        config_manager.set_option('Application', 'use_compiled_exe', 'False')
        config_manager.save_config()

    apinsight = GuiLayout(root)


if __name__ == '__main__':
    start_apinsight()
