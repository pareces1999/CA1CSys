import PySimpleGUI as sg
from datetime import date
from base64images import carneaunclic_logo, oval_button_design
from global_func import pdf_handler
from functions import execute_subprocess
import sys
import os

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
sg.SetOptions(font="archivoblack 12")

today_da = int(date.today().strftime("%d"))
today_mo = int(date.today().strftime("%m"))
today_ye = int(date.today().strftime("%Y"))

frame_layout =  [
                [sg.Text("Lista de Precios", size=(13, 1)), sg.Input(key="-browse_lista-"), sg.FileBrowse(key="-browse_lista-")],
                [sg.Text("Carpeta Salida", size=(13, 1)), sg.Input(key="-browse_path-"), sg.FolderBrowse(key="-browse_path-")]
                ]

layout =    [  
            [sg.Frame("Archivos de datos", frame_layout), sg.Image(data=carneaunclic_logo, pad=(30, 0), tooltip="Esperamos tu pedido")],
            [
             sg.Text("Ingresar Lista de Precios =>", size=(22, 1)), sg.Input(key="-input_lista-", size=(4,1,), do_not_clear = False),
             sg.Text("o Seleccionar Fecha =>", size=(17, 1)), sg.CalendarButton("Calendario",target="-calendar-", location=(500, 250), format="%d-%m-%Y", default_date_m_d_y=(today_mo,today_da,today_ye)), sg.Input(key="-calendar-", size=(11,1), do_not_clear = True)
            ],
            [sg.Output(size=(82, 20))],
             [
             sg.Button(button_text="GENERAR", key="-generate-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0),
             sg.Button(button_text="SALIR", key="-exit-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0)
             ]
            ]
window = sg.Window("Price Manager v1.0 | 202103 (ɔ)carneaunclick.com", layout, resizable=True)

#Loop leyendo los eventos generados por el usuario en la ventana
while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, "-exit-"):
        break
    if event == "-generate-":
        price_p = values["-browse_lista-"]
        out_p = values["-browse_path-"]
        price_number_tmp = values["-input_lista-"]
        price_date = values["-calendar-"]
        if price_p != "":
            path_arr = ["", price_p, "", out_p]
        else:
            sg.popup_error("Falta el archivo con las listas de precio", "Seleccionar el archivo de datos necesario", title="¡ERROR!", text_color="white", font=("archivoblack", 13), keep_on_top=1)
            continue
        if price_number_tmp == "" and price_date== "":
            sg.popup_error("Falta ingresar el número de lista de precios o la fecha de consulta. Ingresar uno de los dos", title="¡ERROR!", text_color="white", font=("archivoblack", 13), keep_on_top=1)
            continue
        if price_number_tmp != "" and price_date!= "":
            sg.popup_error("Es necesario el número de lista o la fecha de consulta pero no ambos. Ingresar uno de los dos", title = "¡ERROR!", text_color = "white", font = ("archivoblack", 13), keep_on_top = 1)
            continue
        if price_number_tmp == "":
            price_number = 0
        else:
            price_number = int(price_number_tmp)
        #Llamada a función para generar el archivo PDF con la lista de precios
        out_n = pdf_handler(price_number, price_date, path_arr)
        open_pdf = sg.PopupYesNo("¿Quiere abrir la lista de precios generada?", title = "", text_color="white", font=("archivoblack", 13), keep_on_top=1)
    if open_pdf == "Yes":
        execute_subprocess("C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe", os.path.join(out_p, out_n))

window.close()