import sqlite3
from sqlite3 import Error
import pandas as pd

db_file_path = "C:\Pablo\PythonCourse\CA1CSys-Des\DBca1c.db"
csv_file_path = "C:\Pablo\PythonCourse\CA1CSys-Des\data\clients_pers_data.csv"


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

    conn = connect_to_db(db_file_path)

    if conn is not None:
        c = conn.cursor()

        names_clients = ["first_name", "last_name", "client_dni", "e_mail", "phone", "address_street", "address_number", "address_floor", "address_city", "address_neigb", "address_province", "address_zip", "address_country"]
        dict_clients = {"first_name": str, "last_name": str, "client_dni": str, "e_mail": str, "phone": str, "address_street": str, "address_number": int, "address_floor": str, "address_city": str, "address_neigb": str, "address_province": str, "address_zip": int, "address_country": str}

        df = pd.read_csv(csv_file, delimiter=";", decimal= ",", encoding="utf-8", skiprows=1, header=None, names=names_clients, dtype=dict_clients)

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
    insert_values_to_table("clients_pers_data", csv_file_path)
