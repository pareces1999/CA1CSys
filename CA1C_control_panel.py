import sys
import time
import PySimpleGUI as sg
from functions import execute_subprocess
from base64images import carneaunclic_logo, mac_red_button_design, mac_green_button_design, mac_orange_button_design

db_file_path = sys.argv

sg.LOOK_AND_FEEL_TABLE["carneaunclick"] =   {"BACKGROUND": "#a61029",
                                             "TEXT": "#f6e4b5",
                                             "INPUT": "#b54e35",
                                             "TEXT_INPUT": "#f6e4b5",
                                             "SCROLL": "#b54e35",
                                             "BUTTON": ("#f6e4b5", "#a61029"),
                                             "PROGRESS": ("#01826B", "#D0D0D0"),
                                             "BORDER": 1,
                                             "SLIDER_DEPTH": 0,
                                             "PROGRESS_DEPTH": 0,
                                             "COLOR_LIST": ["#a61029", "#1fad9f", "#b54e35", "#f6e4b5"],
                                             "DESCRIPTION": ["Turquoise", "Red", "Yellow"]}


sg.theme("carneaunclick")
sg.SetOptions(font = "archivoblack 12")

frame_layout = [
                [sg.Button("", image_data=mac_green_button_design, key="-order_handler-"), sg.Text("Order Handler")],
                [sg.Button("", image_data=mac_orange_button_design, key="-price_manager-"), sg.Text("Price Manager")],
                [sg.Button("", image_data=mac_red_button_design, key="-clients_data-"), sg.Text("Clients DataBase")] 
                ]

layout = [
          [sg.Frame("Control Panel", frame_layout), sg.Image(data = carneaunclic_logo, pad=(30, 0), tooltip = "Esperamos tu pedido")],
          [sg.Text("")],
          [sg.Text("Copyleft / GNU General Public License / 2020-2021", size=(50, 1), font = ("archivoblack", 8), justification = "center")],
          [sg.Text("www.carneaunclick.com", size=(50, 1), font = ("archivoblack", 8), justification = "center")], 
         ]

window = sg.Window("CA1CSys v1.3", layout,
                    grab_anywhere=True,
                    alpha_channel=0, finalize=True)

for i in range(100):
    window.set_alpha(i/100)
    time.sleep(.01)

while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
        break
    if event == "-order_handler-":
        execute_subprocess("python", "gui_order_handler.py")
    elif event == "-price_manager-":
        execute_subprocess("python", "gui_price_manager.py")
    elif event == "-clients_data-":
        execute_subprocess("python", "gui_clients_data.py")
window.close()
