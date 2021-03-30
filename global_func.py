import PySimpleGUI as sg
import pandas as pd
pd.options.mode.chained_assignment = None #Este parámetro de pandas esta desactivado para evitar error en kg_x_order y kg_x_product
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet

from functions import read_files, kg_per_order, kg_per_product, find_price_list, pdf_builder
from validator import order_checker

def_paths = ["lista_combos.csv", "lista_precios.csv", "ordenes.csv", ""]

def order_handler(switcher, p_bool_o_lst=0, p_bool_tot=0, paths=def_paths):
    # Define and load files
    out_p = paths[3]
    combo_df, price_df, order_df = read_files(paths, "order", p_bool_o_lst)
    # Check order file
    order_np = order_df.to_numpy()
    if not order_checker(order_np):
        sg.popup_error("                Error al validar el archivo de órdenes", "Corregir y generar de nuevo la información de total de kilos", title = "¡ERROR!", text_color = "white", font = ("archivoblack", 13), keep_on_top = 1)
        return

    # Switcher
    if switcher == 1:
        kg_per_order_df = kg_per_order(order_df, price_df)
        if p_bool_tot:
            kg_total = kg_per_order_df["peso_de_orden"].sum()
            print("Total de kilos del listado kg_x_orden.csv: {:.2f} Kg.".format(kg_total))
        #print(kg_per_order_lst)
        if out_p != "":
            path = out_p + "/kg_per_order.csv"
        else:
            path = "kg_per_order.csv"
        kg_per_order_df.to_csv(path, sep= ";", encoding="utf-8", decimal= ",", index= False)
        print("Archivo kg_x_orden.csv generado")
        print()
        return
    elif switcher == 2:
        totals_df = kg_per_product(order_df, price_df, combo_df)
        if p_bool_tot:
            kg_total = totals_df["peso_total"].sum()
            print("Total de kilos del listado kg_x_corte.csv: {:.2f} Kg.".format(kg_total))
        #print(kg_per_order_lst)   
        if out_p != "":
            path = out_p + "/kg_x_corte.csv"
        else:
            path = "kg_x_corte.csv"
        totals_df.to_csv(path, sep= ";", encoding="utf-8", decimal= ",", index= False)
        print("Archivo kg_x_corte.csv generado")
        print()
        return
    else:
        return

def pdf_handler(price_number, price_date, paths=def_paths):
    #FUNCIÓN PARA IMPRIMIR PDF CON LA LISTA DE PRECIOS
    # Define and load files
    out_p = paths[3]

    if price_number != 0:
        print(f"Lista de precios: {price_number}")
        price_df = read_files(paths, "price")
        price_df = price_df.drop(price_df[price_df["codigo_lista"]!=price_number].index)
        if len(price_df) == 0:
            print(f"La lista de precios {price_number} no existe")
        else:
            out_n = pdf_builder(price_df, out_p, price_number)
    else:
        price_number = find_price_list(price_date)
        if price_number == None:
            print(f"No hay una lista de precios vigente para la fecha {price_date}")
        else:
            print(f"Lista de precios vigente para la fecha {price_date} encontrada: {price_number}")
            price_df = read_files(paths, "price")
            price_df.drop(price_df[price_df["codigo_lista"]!=price_number].index, inplace=True)
            if len(price_df) == 0:
                print(f"La lista de precios {price_number} no existe en el archivo {paths[1]}")
            else:
                out_n = pdf_builder(price_df, out_p, price_number)
 
    print()
    print(f"Archivo {out_n} generado en la carpeta: {out_p}")
    print()
    return out_n