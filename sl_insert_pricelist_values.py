import sqlite3
from sqlite3 import Error
import pandas as pd

DB_FILE_PATH = "C:\Pablo\PythonCourse\CA1CSys-Des\DBca1c.db"
CSV_FILE_PATH = "C:\Pablo\PythonCourse\CA1CSys-Des\data\historico_lista_precios.csv"


def connect_to_db(db_file):
    """
    Connect to an SQlite database, if db file does not exist it will be created
    :param db_file: absolute or relative path of db file
    :return: sqlite3 connection
    """
    sqlite3_conn = None

    try:
        sqlite3_conn = sqlite3.connect(db_file)
        return sqlite3_conn

    except Error as err:
        print(err)

        if sqlite3_conn is not None:
            sqlite3_conn.close()


def insert_values_to_table(table_name, csv_file):
    """
    Open a csv file with pandas, store its content in a pandas data frame, change the data frame headers to the table
    column names and insert the data to the table
    :param table_name: table name in the database to insert the data into
    :param csv_file: path of the csv file to process
    :return: None
    """

    conn = connect_to_db(DB_FILE_PATH)

    if conn is not None:
        c = conn.cursor()

        names_price = ["codigo_lista", "sku", "codigo_producto", "nombre_producto", "precio_frigorifico", "precio_carneaunclick", "peso_en_kg", "combo"]
        dict_price_lst = {"codigo_lista": int, "sku": int, "codigo_producto": str, "nombre_producto": str, "precio_frigorifico": float, "precio_carneaunclick": float, "peso_en_kg": float, "combo": bool}

        df = pd.read_csv(csv_file, delimiter=";", decimal= ",", encoding="utf-8", skiprows=1, header=None, names=names_price, dtype=dict_price_lst)

        df.columns = get_column_names_from_db_table(c, table_name)

        df.to_sql(name=table_name, con=conn, if_exists="append", index=False)

        conn.close()
        print("SQL insert process finished")
    else:
        print("Connection to database failed")


def get_column_names_from_db_table(sql_cursor, table_name):
    """
    Scrape the column names from a database table to a list
    :param sql_cursor: sqlite cursor
    :param table_name: table name to get the column names from
    :return: a list with table column names
    """

    table_column_names = "PRAGMA table_info(" + table_name + ");"
    sql_cursor.execute(table_column_names)
    table_column_names = sql_cursor.fetchall()

    column_names = list()

    for name in table_column_names:
        column_names.append(name[1])

    return column_names


if __name__ == "__main__":
    insert_values_to_table("pricelist_values", CSV_FILE_PATH)
