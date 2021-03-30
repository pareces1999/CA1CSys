import sqlite3 as sl
from sqlite3 import Error
import pandas as pd
import os
import sys

from datetime import date

db_file_path = "C:\Pablo\PythonCourse\CA1CSys-Des\DBca1c.db"

def ret_clients_data(client_id):
    #RECUPERA TODAS LAS COLUMNAS DE LA TABLA clients_pers_data ACCEDIENDO CON EL PARÁMETRO client_id
    #Recibe como parámetro obligatorio el client_id y retorna 13 valores de las columnas de la tabla en variables separadas
    con = sl.connect(db_file_path)
    cur = con.cursor()
    sql_query = """ select *
                    from clients_pers_data
                    where client_id = {}
            """.format(client_id)
    for row in cur.execute(sql_query):
        client_id, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country = row
    cur.close()
    con.close()
    return client_id, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country


def upd_clients_data(client_id, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country):
    #UPDATEA TODAS LAS COLUMNAS DE LA TABLA clients_pers_data ACCEDIENDO CON EL PARÁMETRO client_id
    #Recibe como parámetros obligatorios los 13 valores que corresponden a las columnas de la tabla.
    #Retorna un mensaje confirmando el update o con el mensaje de error.
    try:
        con = sl.connect(db_file_path)
        cur = con.cursor()
        upd_query = """ update clients_pers_data
                        set client_id = ?,
                            first_name = ?,
                            last_name = ?,
                            e_mail = ?,
                            phone = ?,
                            address_street = ?,
                            address_number = ?,
                            address_floor = ?,
                            addres_neigb = ?,
                            address_city = ?,
                            address_province = ?,
                            address_zip = ?,
                            address_country = ?
                        where client_id = ?
                    """
        data = (client_id, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country, client_id)
        cur.execute(upd_query, data)
        con.commit()
        upd_message = f"Client {client_id} successfully updated"
        cur.close()
    except Error as error:
        upd_message = f"Failed to update sqlite table {error}"
    finally:
        if con:
            con.close()
    return upd_message

client_param = 166

client_id, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country = ret_clients_data(client_param)

print("Cod Cliente: ", client_id)
print(f"Nombre y Apellido: {first_name} {last_name}")
print()

last_name = "Flores"
print(upd_clients_data(client_param, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country))
print()

client_id, first_name, last_name, e_mail, phone, address_street, address_number, address_floor, addres_neigb, address_city, address_province, address_zip, address_country = ret_clients_data(client_param)

print("Cod Cliente: ", client_id)
print(f"Nombre y Apellido: {first_name} {last_name}")
print()