import pandas as pd
pd.options.mode.chained_assignment = None

#UPLOAD SECTION
#Utiliza dictionaries para unificar colum labels y datatypes
# **** FALTA PROBAR CARGAR LOS CSV SIN HEADER PARA QUE NO HAYA CAMBIOS EN LOS COLUMN LABELS ****

dict_combo_lst = {"codigo_lista": int,"codigo_combo": int,"sku": int,"nombre_combo": object,"cantidad_en_kg": float,"frigorifico_sin_iva": float,"frigorifico_con_iva": float,"ca1c_sin_iva": float,"ca1c_sin_iva": float}
dict_price_lst = {"codigo_lista": int, "sku": int, "codigo_producto": str, "nombre_producto": str, "precio_frigorifico": float, "precio_carneaunclick": float, "peso_en_kg": float, "combo": bool}
dict_order_lst = {"orden": int, "codigo_lista": int, "sku": int, "cantidad_producto": int}

#Utiliza list para que los nombres de archivos de input/output se pueda pasar como parametros
paths = ["lista_combos.csv", "lista_precios.csv", "ordenes.csv", "totals.csv"]

#Lee los csv utilizando ";" como separador, ", decimal" y utf-8 enconding
combo_lst = pd.read_csv(paths[0], delimiter=";", decimal= ",", encoding="utf-8", dtype= dict_combo_lst)
price_lst = pd.read_csv(paths[1], delimiter=";", decimal= ",", encoding="utf-8", dtype= dict_price_lst)
order_lst = pd.read_csv(paths[2], delimiter=";", decimal= ",", encoding="utf-8", dtype= dict_order_lst)

#PROCESS SECTION
temp_merged = pd.merge(order_lst, price_lst, on= ["codigo_lista", "sku"], how= "left")

#Selecciona del df las columnas que son necesarias para crear el archivo de salida
order_lst_merged = temp_merged[["orden", "cantidad_producto", "peso_en_kg", "combo"]]

#Agrega al df columna con peso total del item y lo calcula porque ese dato no existe
order_lst_merged["peso_de_orden"] = order_lst_merged["cantidad_producto"] * order_lst_merged["peso_en_kg"]

#Hace el group by para calcular el peso total por orden
output_kg_per_order = order_lst_merged.groupby(["orden"])["peso_de_orden"].sum().reset_index()

#DOWNLOAD SECTION
output_kg_per_order.to_csv("kg_x_orden.csv", sep= ";", encoding="utf-8", decimal= ",", index= False)