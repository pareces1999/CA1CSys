import PySimpleGUI as sg
from base64images import carneaunclic_logo, oval_button_design
from global_func import order_handler
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
sg.SetOptions(font = "archivoblack 12")

frame_layout =  [
                [sg.Text("Datos Combos", size=(12, 1)), sg.Input(), sg.FileBrowse()],
                [sg.Text("Datos Precios", size=(12, 1)), sg.Input(), sg.FileBrowse()],
                [sg.Text("Datos Órdenes", size=(12, 1)), sg.Input(), sg.FileBrowse()],
                [sg.Text("Carpeta Salida", size=(12, 1)), sg.Input(), sg.FolderBrowse()]
                ]

layout =    [
            [sg.Frame("Archivos de datos", frame_layout), sg.Image(data = carneaunclic_logo, pad=(30, 0), tooltip = "Esperamos tu pedido")],
            [sg.Text("Seleccionar  =>", size=(12, 1)), sg.Combo(values=["Kg/Orden", "Kg/Corte"], size=(10, 6))],
            [sg.Checkbox("Listar Órdenes"), sg.Checkbox("Sumar Total de Kg.")],
            [sg.Output(size=(82, 20))],
            [
             sg.Button(button_text="GENERAR", key="-generate-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0),
             sg.Button(button_text="SALIR", key="-exit-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0)]
            ]

window = sg.Window("Order Handler v2.0 (ɔ)carneaunclick.com ", layout, resizable=True)

#Loop leyendo los eventos generados por el usuario en la ventana
while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, "-exit-"):
        break
    if event == "-generate-":
        combo_p = values[0] #Parámetro con el path y nombre del archivo de composición de combos
        price_p = values[1] #Parámetro con el path y nombre del archivo de lista de precios
        order_p = values[2] #Parámetro con el path y nombre del archivo de órdenes
        out_p = values[3]  #Parámetro con el path para generar los archivos de output
        switch_str = values[5]  #Parámetro con la switch-string => "Kg/Orden" o "Kg/Corte"
        p_bool_o_lst= int(values[6]) #Parámetro para listar órdenes cuando es True
        p_bool_tot= int(values[7]) #Parámetro para calcular total de kg cuando es True
        #Validar que se hayan seleccionado los datos para que las funciones corran
        if combo_p != "" and price_p != "" and order_p != "":
            path_arr = [combo_p, price_p, order_p, out_p]
        else:
            sg.popup_error("Falta elegir todos o alguno de los archivos", "Seleccionar los archivos de datos necesarios", title = "¡ERROR!", text_color = "white", font = ("archivoblack", 13), keep_on_top = 1)
            continue
        if switch_str == "Kg/Orden":
            switcher = 1
        elif switch_str == "Kg/Corte":
            switcher = 2
        else:
            sg.popup_error("Falta elegir cómo totalizar los kilos", "Seleccionar 'Kg/Orden' o 'Kg/Corte'", title = "¡ERROR!", text_color = "white", font = ("archivoblack", 13), keep_on_top = 1)
            continue
        #Llamada a función para generar el archivo kg_x_order.csv o kg_x_product.csv 
        order_handler(switcher, p_bool_o_lst, p_bool_tot, path_arr)
    open_csv = sg.PopupYesNo("¿Quiere abrir el archivo generado?", title = "", text_color="white", font=("archivoblack", 13), keep_on_top=1) 
    if open_csv == "Yes":
        if switcher == 1:
            execute_subprocess("Excel.lnk", os.path.join(out_p, "kg_per_order.csv"))
        else:
            execute_subprocess("Excel.lnk", os.path.join(out_p, "kg_x_corte.csv"))

window.close()