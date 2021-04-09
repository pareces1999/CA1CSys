import PySimpleGUI as sg
import sqlite3 as sl
import pandas as pd
import sys
import os
import re
from datetime import date
from base64images import carneaunclic_logo, oval_button_design
from sl_DBca1c_functions import ret_clients_data, upd_clients_data


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

try:
     base_path = sys._MEIPASS
except Exception:
     base_path = os.path.abspath(".")

db_file_path = base_path+"\DBca1c.db"

today_da = int(date.today().strftime("%d"))
today_mo = int(date.today().strftime("%m"))
today_ye = int(date.today().strftime("%Y"))

regex_mail = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
regex_dni = r"(^\d\d\d\d\d\d\d$)|(^\d\d\d\d\d\d\d\d$)"
regex_cuil = r"^(20|23|27|30|33)([0-9]{9}|-[0-9]{8}-[0-9]{1})$"

client_id = 0
first_name = ""
last_name = ""
client_dni = 0
e_mail = ""
phone = 0
address_street = ""
address_number = 0
address_floor = ""
address_neigb = ""
address_city = ""
address_province = ""
address_zip = ""
address_country = ""
client_param = 0

frame_layout =  [
                    [sg.Text("E-Mail:", size=(10, 1)), sg.Input(size=(48, 1), key="-find_mail-")], 
                    [sg.Text("DNI/CUIL:", size=(10, 1)), sg.Input(size=(35, 1), key="-find_dni-"), sg.Button(button_text="BUSCAR", key="-find-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0)],
                    [sg.Button("-submit-", visible=False, bind_return_key=True)]
                ]

layout = [
            [sg.Frame("Busqueda de Cliente", frame_layout), sg.Image(data=carneaunclic_logo, pad=(45, 0), tooltip="Esperamos tu pedido")],
            [sg.Text("Datos Personales", font="Default 18")],
            [
             sg.Text("Nombre:", size=(8,1)), sg.Input(first_name, size=(30, 1), key='-first-'),
             sg.Text("Apellido:", size=(8,1)), sg.Input(last_name, size=(30, 1), key='-last-')
            ],
            [
             sg.Text("E-mail:", size=(8,1)),sg.Input(e_mail, size=(30, 1), key="-mail-"),
             sg.Text("Teléfono:", size=(8,1)), sg.Input(phone, size=(30,1), key="-phone-")
            ],
            [sg.Text("Dirección", font="Default 18")],
            [
             sg.Text("Calle:", size=(5,1)), sg.Input(address_street, size=(31,1), key="-street-"),
             sg.Text("Número:", size=(6,1)), sg.Input(address_number, size=(6,1), key="-number-"),
             sg.Text("Piso/Dpto:", size=(8,1)), sg.Input(address_floor, size=(17,1), key="-floor-")
            ],
            [
             sg.Text("Barrio:", size=(5,1)), sg.Input(address_neigb, size=(31,1), key="-neigb-"),
             sg.Text("Ciudad:", size=(6,1)), sg.Input(address_city, size=(34,1), key="-city-")
            ],
            [
             sg.Text("Provincia:", size=(8,1)), sg.Input(address_province, size=(28,1), key="-provin-"),
             sg.Text("C.P.:", size=(6,1)), sg.Input(address_city, size=(7,1), key="-zip-"),
             sg.Text("Pais:", size=(4,1)), sg.Input(address_country, size=(20,1), key="-country-")
            ],

            [
            sg.Button(button_text="GRABAR", key="-save-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0),
            sg.Button(button_text="SALIR", key="-exit-", image_data=oval_button_design, image_subsample=2, button_color=("black", sg.theme_background_color()), font=("archivoblack",13), border_width=0)
            ]
         ]


window = sg.Window("Clients DataBase v1.0 | 202103 (ɔ)carneaunclick.com", layout, resizable=True)

#Loop leyendo los eventos generados por el usuario en la ventana
while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, "-exit-"):
        break

    if event in ("-submit-", "-find-"):
        if not ((re.search(regex_dni, values["-find_dni-"]) or re.search(regex_cuil, values["-find_dni-"])) or re.search(regex_mail, values["-find_mail-"])):
            window["-find_mail-"].update("")
            window["-find_dni-"].update("")
            continue

    find_mail = values["-find_mail-"]
    find_dni = values["-find_dni-"]
    if event in ("-submit-", "-find-"):
        if find_mail != "" and find_dni != "":
            sg.popup_error("Es necesario el E-Mail o el DNI/CUIL pero no ambos","Ingresar solamente uno de los dos", title="¡ERROR!", text_color="white", font=("archivoblack", 13), keep_on_top=1)
            continue
        else:
            sg.popup_quick_message("Buscando al cliente...", background_color="red")
            if find_mail !="":
                search_query = "select client_id from clients_pers_data where e_mail = '{}'".format(values["-find_mail-"])
            else:
                search_query = "select client_id from clients_pers_data where client_dni = {}".format(int(values["-find_dni-"]))
            con = sl.connect(db_file_path)
            search_df = pd.read_sql_query(search_query, con)
            con.close
            if search_df.empty:
                sg.popup_error("No se econtró un cliente con el E-Mail o el DNI/CUIL indicado", title="¡ERROR!", text_color="white", font=("archivoblack", 13), keep_on_top=1)
                window["-first-"].update("")
                window["-last-"].update("")
                window["-mail-"].update("")
                window["-phone-"].update("")
                window["-street-"].update("")
                window["-number-"].update("")
                window["-floor-"].update("")
                window["-neigb-"].update("")
                window["-city-"].update("")
                window["-provin-"].update("")
                window["-zip-"].update("")
                window["-country-"].update("")
                continue
            elif len(search_df.index) == 1:
                client_param = int(search_df["client_id"].to_string(index=False))
                client_id, first_name, last_name, client_dni, e_mail, phone, address_street, address_number, address_floor, address_neigb, address_city, address_province, address_zip, address_country = ret_clients_data(client_param)
                client_param = 0
                window["-first-"].update(first_name)
                window["-last-"].update(last_name)
                window["-mail-"].update(e_mail)
                window["-phone-"].update(phone)
                window["-street-"].update(address_street)
                window["-number-"].update(address_number)
                window["-floor-"].update(address_floor)
                window["-neigb-"].update(address_neigb)
                window["-city-"].update(address_city)
                window["-provin-"].update(address_province)
                window["-zip-"].update(address_zip)
                window["-country-"].update(address_country)
            else:
                sg.popup_error(f"Los siguientes {len(search_df.index)} clientes tienen la clave indicada repetida:", search_df.to_string(index=False), title="¡ERROR!", text_color="white", font=("archivoblack", 13), keep_on_top=1)
    elif event == "-save-":
        if client_param == 0:
            continue
        else:
            first_name = values["-first-"]
            last_name = values["-last-"]
            e_mail = values["-mail-"]
            phone = values["-phone-"]
            address_street = values["-street-"]
            address_number = values["-number-"]
            address_floor = values["-floor-"]
            address_neigb = values["-neigb-"]
            address_city = values["-city-"]
            address_province = values["-provin-"]
            address_zip = values["-zip-"]
            address_country = values["-country-"]
            upd_message = upd_clients_data(client_id, first_name, last_name, client_dni, e_mail, phone, address_street, address_number, address_floor, address_neigb, address_city, address_province, address_zip, address_country)
            if upd_message.startswith("Cliente"):
                sg.popup_quick_message(upd_message, background_color="green")
            else:
                sg.popup_quick_message(upd_message, background_color="red")

window.close()
