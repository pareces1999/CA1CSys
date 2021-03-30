import pandas as pd
pd.options.mode.chained_assignment = None

#UPLOAD SECTION
#Utiliza dictionaries para unificar colum labels y datatypes
# **** FALTA PROBAR CARGAR LOS CSV SIN HEADER PARA QUE NO HAYA CAMBIOS EN LOS COLUMN LABELS ****

dict_combo_lst = {"codigo_lista": int,"codigo_combo": int,"sku": int,"nombre_producto": object,"cantidad_en_kg": float,"frigorifico_sin_iva": float,"frigorifico_con_iva": float,"ca1c_sin_iva": float,"ca1c_con_iva": float}
dict_price_lst = {"codigo_lista": int, "sku": int, "codigo_producto": str, "nombre_producto": str, "precio_frigorifico": float, "precio_carneaunclick": float, "peso_en_kg": float, "combo": bool}
dict_order_lst = {"codigo_lista": int, "orden": int, "cantidad_producto": int, "sku": int}

#Utiliza list para que los nombres de archivos de input/output se pueda pasar como parametros
paths = ["lista_combos.csv", "lista_precios.csv", "ordenes.csv", "totals.csv"]

#Lee los csv utilizando ";" como separador, ", decimal" y utf-8 enconding
combo_lst = pd.read_csv(paths[0], delimiter=";", decimal= ",", encoding="utf-8", dtype= dict_combo_lst)
price_lst = pd.read_csv(paths[1], delimiter=";", decimal= ",", encoding="utf-8", dtype= dict_price_lst)
order_lst = pd.read_csv(paths[2], delimiter=";", decimal= ",", encoding="utf-8", dtype= dict_order_lst)

#PROCESS SECTION
#Como hay que joinear tres df se hace en dos pasos, primero order_lst y price_lst
temp_merged1 = pd.merge(order_lst, price_lst, on= ["codigo_lista", "sku"], how= "left")

#Separa en dos df combo/no-combo para poder convertir combo a los productos que componen cada combo
temp_merged_combo = temp_merged1.loc[temp_merged1["combo"]]
temp_merged_nocombo = temp_merged1.loc[temp_merged1["combo"] != True]

#Agrega al df no-combo columna con peso total del item y lo calcula porque ese dato no existe
temp_merged_nocombo["peso_total"] = temp_merged_nocombo["cantidad_producto"] * temp_merged_nocombo["peso_en_kg"]

#Joinea la lista combo con la lista con composición de combos para obtener los productos que componen cada uno
#agrega columna con peso total del item y updatea peso_en_kg con el valor de cada corte de la price_lst
#porque en la lista combo este campo tiene el peso total del combo (y no el peso del corte) y columna con unidades
temp_merged2 = pd.merge(temp_merged_combo, combo_lst, left_on= ["codigo_lista", "sku"], right_on= ["codigo_lista", "codigo_combo"], how= "left")
temp_merged2["peso_total"] = temp_merged2["cantidad_producto"] * temp_merged2["cantidad_en_kg"]
for row_ix, row_values in temp_merged2.iterrows():
  temp_merged2.iloc[row_ix, 8] = price_lst.loc[((price_lst["codigo_lista"] == row_values[1]) & (price_lst["sku"] == row_values[11])), "peso_en_kg"].values[0]

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

#DOWNLOAD SECTION
output_totals.to_csv(paths[3], sep= ";", encoding="utf-8", decimal= ",", index= False)