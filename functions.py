import pandas as pd
import numpy as np
import subprocess
import os

from datetime import datetime, date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet

#LISTA CON TODAS LAS LISTAS DE PRECIOS Y SU VIGENCIA
#Cuando se crea una nueva lista es necesario agregarla al final con su fecha de inicio de vigencia
# dejando en blanco la fecha de final de vigencia. Y se debe completar la fecha de final de vigencia
# de la lista previa con el día anterior al inicio de vigencia de la nueva lista.
pled =  [ #Listas de precio con Número, fecha desde y fecha hasta
        [1,"01-10-2017","30-11-2017"],
        [2,"01-12-2017","07-03-2018"],
        [3,"08-03-2018","11-05-2018"],
        [4,"12-05-2018","27-05-2018"],
        [5,"28-05-2018","05-06-2018"],
        [6,"06-06-2018","31-07-2018"],
        [7,"01-08-2018","07-09-2018"],
        [8,"08-09-2018","02-10-2018"],
        [9,"03-10-2018","31-10-2018"],
        [10,"01-11-2018","03-02-2019"],
        [11,"04-02-2019","17-02-2019"],
        [12,"18-02-2019","24-03-2019"],
        [13,"25-03-2019","24-04-2019"],
        [14,"25-04-2019","09-06-2019"],
        [15,"10-06-2019","15-07-2019"],
        [16,"16-07-2019","31-07-2019"],
        [17,"01-08-2019","20-08-2019"],
        [18,"21-08-2019","10-11-2019"],
        [19,"11-11-2019","30-11-2019"],
        [20,"01-12-2019","05-01-2020"],
        [21,"06-01-2020","29-02-2020"],
        [22,"01-03-2020","25-03-2020"],
        [23,"26-03-2020","12-03-2020"],
        [24,"13-03-2020","31-05-2020"],
        [25,"01-06-2020","30-06-2020"],
        [26,"01-07-2020","16-08-2020"],
        [27,"17-08-2020","18-09-2020"],
        [28,"19-09-2020","19-10-2020"],
        [29,"20-10-2020","16-11-2020"],
        [30,"17-11-2020","31-12-2020"],
        [31,"01-01-2021","19-02-2021"],
        [32,"20-02-2021",""] #La última lista de precios (es decir la vigente) no tiene end_date
        ]


def execute_subprocess(command, *args):      
    try:      
        sp = subprocess.Popen([command, *args], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)      
        out, err = sp.communicate()      
        if out:      
            print(out.decode("utf-8"))      
        if err:      
            print(err.decode("utf-8"))      
    except:      
        pass      

def read_files(paths, mode, p_bool=0):
    #FUNCIÓN PARA LEER LOS CSV DE 1) HISTORICO LISTA DE PRECIOS (price_lst), 2) HISTORICO COMPOSICIÓN DE
    #COMBOS (combo_lst) Y 3) DETALLE DE ÓRDENES A PROCESAR (order_lst)
    #Usa dos modos: mode = order => cuando se llama desde la función order_handler y devuelve los tres df
    #               mode = price => cuando se llama desde el módulo pdf_builder y devuelve solo el df price_lst
    #Utiliza lists y dictionaries para unificar nombres de columnas y datatypes

    names_combo = ["codigo_lista", "codigo_combo", "sku", "nombre_producto", "cantidad_en_kg", "frigorifico_sin_iva", "frigorifico_con_iva", "ca1c_sin_iva", "ca1c_con_iva"]
    names_price = ["codigo_lista", "sku", "codigo_producto", "nombre_producto", "precio_frigorifico", "precio_carneaunclick", "peso_en_kg", "combo"]
    names_order = ["orden", "codigo_lista", "cantidad_producto", "sku"]

    dict_combo_lst = {"codigo_lista": int,"codigo_combo": int,"sku": int,"nombre_producto": object,"cantidad_en_kg": float,"frigorifico_sin_iva": float,"frigorifico_con_iva": float,"ca1c_sin_iva": float,"ca1c_con_iva": float}
    dict_price_lst = {"codigo_lista": int, "sku": int, "codigo_producto": str, "nombre_producto": str, "precio_frigorifico": float, "precio_carneaunclick": float, "peso_en_kg": float, "combo": bool}
    dict_order_lst = {"orden": int, "codigo_lista": int, "cantidad_producto": int, "sku": int}

    if mode == "order":
        #Lee los csv utilizando ";" como separador, "," como decimal" y utf-8 enconding
        combo_lst = pd.read_csv(paths[0], delimiter=";", decimal= ",", encoding="utf-8", skiprows=1, header=None, names=names_combo, dtype=dict_combo_lst)
        price_lst = pd.read_csv(paths[1], delimiter=";", decimal= ",", encoding="utf-8", skiprows=1, header=None, names=names_price, dtype=dict_price_lst)
        order_lst = pd.read_csv(paths[2], delimiter=";", decimal= ",", encoding="utf-8", skiprows=1, header=None, names=names_order, dtype=dict_order_lst)
        
        #Se imprime listado de órdenes porque el parámetro es True
        if p_bool:
            proce_orders = order_lst.orden.unique()
            print(f"Se procesaron en total {proce_orders.size} órdenes y el detalle es el siguiente:")
            print(proce_orders)
            print()
        return combo_lst, price_lst, order_lst
    else:
        #Lee solo el csv de las listas de precios utilizando ";" como separador, "," como decimal"
        #y utf-8 enconding importando solamente la lista elegida para imprimir
        price_lst = pd.read_csv(paths[1], delimiter=";", decimal= ",", encoding="utf-8", skiprows=1, header=None, names=names_price, dtype=dict_price_lst)
        return price_lst


def kg_per_order(order_df, price_df):
    #FUNCIÓN PARA CALCULAR EL TOTAL DE KILOS POR ORDEN
    #Joinea el detalle de productos de las órdenes con la información de la lista de precios para tener los kilos por producto
    temp_merged = pd.merge(order_df, price_df, on= ["codigo_lista", "sku"], how= "left")

    #Selecciona del df las columnas que son necesarias para crear el archivo de salida
    order_df_merged = temp_merged[["orden", "cantidad_producto", "peso_en_kg", "combo"]]

    #Agrega al df columna con peso total del item y lo calcula porque ese dato no existe
    order_df_merged["peso_de_orden"] = order_df_merged["cantidad_producto"] * order_df_merged["peso_en_kg"]

    #Hace el group by para calcular el peso total por orden
    output_kg_per_order = order_df_merged.groupby(["orden"])["peso_de_orden"].sum().reset_index()
    return output_kg_per_order


def kg_per_product(order_df, price_df, combo_df):
    #FUNCIÓN PARA CALCULAR EL TOTAL DE KILOS POR PRODUCTO
    #Como hay que joinear tres df se hace en dos pasos, primero order_df y price_df
    temp_merged1 = pd.merge(order_df, price_df, on= ["codigo_lista", "sku"], how= "left")

    #Separa en dos df combo/no-combo para poder convertir combo a los productos que componen cada combo
    temp_merged_combo = temp_merged1.loc[temp_merged1["combo"]]
    temp_merged_nocombo = temp_merged1.loc[temp_merged1["combo"] != True]

    #Agrega al df no-combo columna con peso total del item y lo calcula porque ese dato no existe
    temp_merged_nocombo["peso_total"] = temp_merged_nocombo["cantidad_producto"] * temp_merged_nocombo["peso_en_kg"]

    #Joinea la lista combo con la lista con composición de combos para obtener los productos que componen cada uno
    #agrega columna con peso total del item y updatea peso_en_kg con el valor de cada corte de la price_df
    #porque en la lista combo este campo tiene el peso total del combo (y no el peso del corte) y columna con unidades
    temp_merged2 = pd.merge(temp_merged_combo, combo_df, left_on= ["codigo_lista", "sku"], right_on= ["codigo_lista", "codigo_combo"], how= "left")
    temp_merged2["peso_total"] = temp_merged2["cantidad_producto"] * temp_merged2["cantidad_en_kg"]
    for row_ix, row_values in temp_merged2.iterrows():
        temp_merged2.iloc[row_ix, 8] = price_df.loc[((price_df["codigo_lista"] == row_values[1]) & (price_df["sku"] == row_values[11])), "peso_en_kg"].values[0]

    #Crea el df para unir combo/no-combo y hace los append para volver a tener un df unificado
    cols_dict = {"sku_y": "sku", "nombre_producto_y": "nombre_producto"}
    temp_append1 = temp_merged_nocombo[["codigo_lista", "sku", "nombre_producto", "peso_en_kg", "peso_total"]]
    temp_append2 = temp_merged2[["codigo_lista", "sku_y", "nombre_producto_y", "peso_en_kg", "peso_total"]]
    temp_append3 = temp_append2.rename(columns= cols_dict)
    cut_lst_merged = temp_append1.append(temp_append3)

    #Selecciona del df las columnas que son necesarias para crear el archivo de salida, hace el group by y 
    #agrega al df final columna con cantidad de unidades y la calcula porque ese dato no existe
    output_totals = cut_lst_merged.groupby(["sku", "nombre_producto", "peso_en_kg"])["peso_total"].sum().reset_index()
    output_totals["cantidad_unidades"] = 0
    for row_ix, row_values in output_totals.iterrows():
        output_totals.iloc[row_ix, 4] = (lambda peso_tot, peso_unit: round(peso_tot / peso_unit, 2) if peso_unit != 1 else 0) (output_totals.iloc[row_ix, 3], output_totals.iloc[row_ix, 2])
    return output_totals


def unit_to_kg(t_array, p_array, t_index, conv_index, sku_index_t, sku_index_p):
    # Convert to kg
    t_array_c = np.copy(t_array)
    sku_array = np.array([pr[sku_index_p] for pr in p_array])
    for i in range(len(t_array_c)):
        it_sku = t_array_c[i][sku_index_t]
        it_index = np.where(sku_array == it_sku)[0][0]
        t_array_c[i][t_index] = float(t_array_c[i][t_index])*p_array[it_index][conv_index]
    return t_array_c


def kg_to_unit(t_array, p_array, t_index, conv_index, sku_index_t, sku_index_p):
    t_array_c = np.copy(t_array)
    sku_array = np.array([pr[sku_index_p] for pr in p_array])
    for i in range(len(t_array_c)):
        it_sku = t_array_c[i][sku_index_t]
        it_index = np.where(sku_array == it_sku)[0][0]
        t_array_c[i][t_index] = t_array_c[i][t_index]/p_array[it_index][conv_index]
    return t_array_c


def np_arr_to_df(data_arr, labels):
    res_df = pd.DataFrame(data=data_arr,
                          index=range(0, len(data_arr)),
                          columns=labels)
    return res_df


def decomposer(o_arr, c_arr, p_entry_bool=0):
    # Obtain total entries
    entries = 0
    combo_id_array = np.array([comb[1] for comb in c_arr])
    for item in o_arr:
        order_sku = item[2]
        if order_sku >= 100:
            length = len(np.where(combo_id_array == order_sku)[0])
            entries += length
        else:
            entries += 1
    if p_entry_bool:
        print("Total number of entries = " + str(entries))

    # Decompose order list
    decomp_order_lst = np.zeros((entries, 4))
    i = 0
    j = 0
    while i < len(o_arr):
        order_id = o_arr[i][0]
        order_plst_n = o_arr[i][1]
        order_sku = o_arr[i][2]
        order_quant = o_arr[i][3]
        if order_sku >= 100:
            combo_item_index = np.where(combo_id_array == order_sku)[0]
            for index in combo_item_index:
                ins_arr = [order_id, order_plst_n, c_arr[index][2], order_quant*c_arr[index][4]]
                decomp_order_lst[j] = ins_arr
                j += 1
        else:
            decomp_order_lst[j] = o_arr[i]
            j += 1
        i += 1
    return decomp_order_lst


def aggregator(p_arr, dec_arr):
    # Aggregate totals
    final_list = np.c_[p_arr, np.zeros(len(p_arr))]
    sku_array = np.array([pr[1] for pr in final_list])
    for item in dec_arr:
        order_sku = item[2]
        order_quant = item[3]
        sku_index = np.where(sku_array == order_sku)[0][0]
        final_list[sku_index][4] += order_quant*final_list[sku_index][3]
    return final_list


def rounder(t_lst, index, dec):
    for i in range(len(t_lst)):
        t_lst[i][index] = round(t_lst[i][index], dec)
    return


def find_price_list(price_date):
    #FUNCIÓN PARA DETERMINAR LA LISTA DE PRECIOS VIGENTE EN UNA FECHA.
    format = "%d-%m-%Y"

    #Para poder determinar la lista de precios vigente compara la fecha target con los rangos de vigencia,
    #devuelve el número de lista si existe o None si no hay lista vigente para la fecha target
    for row_ix in range(0,len(pled)):
        start_date = pled[row_ix][1]
        #Asigna today() como end_date cuando es la lista vigente
        end_date = pled[row_ix][2] if pled[row_ix][2] != "" else date.today().strftime("%d-%m-%Y")
        if datetime.strptime(price_date, format) >= datetime.strptime(start_date, format) and datetime.strptime(price_date, format) <= datetime.strptime(end_date, format):
            return pled[row_ix][0]
    return


def find_price_st_en_date(price_number):
    for row_ix in range(len(pled)):
        if price_number == pled[row_ix][0]:
            return pled[row_ix][1], pled[row_ix][2]


def pdf_builder(price_df, out_p, price_number):
    #FUNCIÓN PARA GENERAR PDF CON LISTA DE PRECIOS
    #Se registran las truetype fonts para poder utilizarlas y que queden embebidas en el pdf
    pdfmetrics.registerFont(TTFont("ArchivoBlack-Regular", "C:\Windows\Fonts\ArchivoBlack-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("Archivo-Bold", "C:\Windows\Fonts\Archivo-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Archivo-Medium", "C:\Windows\Fonts\Archivo-Medium.ttf"))
    pdfmetrics.registerFont(TTFont("ArchivoNarrow-Regular", "C:\Windows\Fonts\ArchivoNarrow-Regular.ttf")) 

    #Se inicializa variable con template para definir nombre de archivo de output, tamaño de página y márgenes
    out_n = "Lista_de_Precios_ca1c-"+str(price_number)+"-"+date.today().strftime("%Y%m%d")+".pdf"
    output_file_path = os.path.join(out_p, out_n)
    output_pdf = SimpleDocTemplate(output_file_path,
                            pagesize = A4,
                            leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=0.25*cm, bottomMargin=1*cm)

    #Inicializa variable para incluir imagen del logo con su tamaño y alineación 
    logo_ca1c = Image("Logo_CA1C_COM.png", width = 3.5*cm, height = 3*cm, hAlign = "RIGHT") 

    #Inicializa variable con estilos predefinidos 
    headfoot_style = getSampleStyleSheet() 
    
    #Define los estilos para heading y footer (alineación, font, tamaño de font, etc)
    title_style1 = headfoot_style["Heading1"]
    title_style1.alignment = 0 # 0: left, 1: center, 2: right 4: justify
    title_style1.setFont = "ArchivoBlack-Regular"
    title_style1.fontSize = 20
    title_style2 = headfoot_style["Heading2"] 
    title_style2.alignment = 1 # 0: left, 1: center, 2: right 4: justify
    title_style2.setFont = "ArchivoBlack-Regular"
    title_style2.fontSize = 16
    title_style2.spaceAfter = 16
    footer_style = headfoot_style["Normal"] 
    footer_style.alignment = 4 # 0: left, 1: center, 2: right 4: justify
    footer_style.setFont = "ArchivoNarrow-Regular"
    footer_style.spaceBefore = 18
    footer_style.fontSize = 12
    footer_style.autoLeading = "max"

    #Crea los párrafos de texto para heading y footer
    start_date, end_date = find_price_st_en_date(price_number)
    if end_date == "":
        end_date = date.today().strftime("%d-%m-%Y")  
    title1 = Paragraph("LISTA DE PRECIOS", title_style1) 
    title2 = Paragraph("De carneaunclick.com - vigente desde: "+start_date+" hasta: "+end_date, title_style2)
    footer = Paragraph("Somos carneaunclick.com una carnicería 100% online con distribución gratuita en todos los barrios de CABA. Los precios indicados incluyen el IVA y la entrega de lunes a sábado entre las 9:00 y las 13:00 Hs en Ciudad Autónoma de Buenos Aires. Los pedidos pueden realizarse los siete días de la semana las 24 Hs del día en nuestro sitio www.carneaunclick.com. Aceptamos como medio de pago todas las tarjetas de débito y crédito a través de Mercadopago y también en efectivo contra entrega. CONTACTO: WhatsApp 11 3133 2545 / Mail: ventas@carneaunclick.com", footer_style)
    
    #Define el formato de la tabla (colores, fuentes, alineación de títulos y columnas)
    table_style = TableStyle(
        [ 
            ("BOX", (0, 0), (-1, -1), 1 , colors.black), 
            ("GRID", (0, 0), (-1, -1), 1 , colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.gray), #Fila de títulos de tabla
            ("ALIGN", (0, 0), (-1, 0), "CENTER"), #Fila de títulos de tabla
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), #Fila títulos de tabla
            ("FONT", (0, 0), (-1, 0), "Archivo-Medium", 10), #Fila títulos de tabla
            ("BACKGROUND", (0 , 1) , (-1 , -1), colors.beige), #Filas cuerpo de tabla
            #("ALIGN", (0, 1), (1, -1), "LEFT"), #Columnas con caracteres
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"), #Columnas con números
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.black), #Filas cuerpo de tabla
            ("FONT", (0, 1), (-1, -1), "Archivo-Medium", 8), #Filas cuerpo de tabla
            ("FONT", (4, 1), (-1, -1), "Courier-Bold", 8) #Columnas con números
        ] 
   ) 

    #Formatea el df para generar las columnas en el orden, con los datos y con el formato que se quiere para cada columna 
    new_column_values = []
    for row_ix in range(len(price_df)):
        if price_df.iloc[row_ix,0] in (59, 63, 67):
            new_column_values.append("Achuras")
        elif price_df.iloc[row_ix,0] > 600:
            new_column_values.append("Elaborados")
        elif price_df.iloc[row_ix,0] > 100:
            new_column_values.append("Combo")
        elif price_df.iloc[row_ix,0] <55:
            new_column_values.append("Ternera")
        else:
            new_column_values.append("Cerdo")

    price_df.insert(loc=4, column="tipo", value=new_column_values)
    price_df.insert(loc=5, column="unidad_venta", value=price_df.apply(lambda cell_value: "Pieza de "+str(cell_value.peso_en_kg)+" Kg." if cell_value.peso_en_kg!=1 else "Por Kg.", axis=1))
    price_df.insert(loc=8, column="precio_x_pieza", value=price_df.apply(lambda cell_value: cell_value.precio_carneaunclick * cell_value.peso_en_kg if cell_value.peso_en_kg!=1 else 0, axis=1))

    for row_ix in range(len(price_df)):
        if price_df.iloc[row_ix,10]:
            price_df.iloc[row_ix,8] = 0
            price_df.iloc[row_ix,5] = "Por unidad"

    price_df.drop(["codigo_lista", "codigo_producto", "precio_frigorifico", "combo"], axis="columns", inplace=True)

    #Convierte el df en list para poder inicializar la variable con los datos y el estilo definido para el PDF
    price_list = price_df.values.tolist()
    output_list = [["SKU", "Cortes", "Tipo", "Venta", "Pr x Kg", "Pr x Pieza", "Unid Vta (Kg)"]]
    for row_ix in range(len(price_list)):
        row_values = [
                        "{0:^7}".format(*price_list[row_ix]), #SKU
                        "{1:<30}".format(*price_list[row_ix]), #Cortes
                        "{2:<15}".format(*price_list[row_ix]), #Tipo
                        "{3:<15}".format(*price_list[row_ix]), #Venta
                        "${4:9.2f}".format(*price_list[row_ix]), #Pr x Kg
                        "${5:9.2f}".format(*price_list[row_ix]), #Pr x Pieza
                        "{6:5.2f}".format(*price_list[row_ix]) #Unid Vta (Kg)
                     ]
        output_list.append(row_values)
    price_table = Table(output_list , style = table_style, repeatRows=1)
    
    #Se arma el output con todos los elementos definidos y se graba el archivo pdf en disco
    output_pdf.build([logo_ca1c, title1, title2 , price_table, footer])
    return out_n