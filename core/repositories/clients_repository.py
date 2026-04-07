from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.db.connection import get_db_connection


CLIENTS_TABLE = "clients_pers_data"
CLIENT_COLUMNS = [
    "id",
    "first_name",
    "last_name",
    "dni_cuil",
    "phone",
    "email",
    "street",
    "street_number",
    "floor_apt",
    "neighborhood",
    "city",
    "province",
    "country",
    "zip_code",
    "created_at",
    "updated_at",
]
WRITEABLE_COLUMNS = [
    "first_name",
    "last_name",
    "dni_cuil",
    "phone",
    "email",
    "street",
    "street_number",
    "floor_apt",
    "neighborhood",
    "city",
    "province",
    "country",
    "zip_code",
]
SEARCHABLE_COLUMNS = [
    "first_name",
    "last_name",
    "dni_cuil",
    "phone",
    "email",
    "city",
    "province",
    "country",
]
CREATE_CLIENTS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {CLIENTS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    dni_cuil TEXT UNIQUE,
    phone TEXT,
    email TEXT,
    street TEXT,
    street_number TEXT,
    floor_apt TEXT,
    neighborhood TEXT,
    city TEXT,
    province TEXT,
    country TEXT DEFAULT 'Argentina',
    zip_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


@dataclass
class RepositoryResult:
    """Simple response for repository write operations."""

    success: bool
    message: str
    data: dict[str, Any] | None = None


class ClientsRepository:
    """Encapsulate all client database access in one reusable class."""

    def __init__(self, *, show_errors: bool = False) -> None:
        self.show_errors = show_errors
        self.ensure_tables_exist()

    def initialize_clients_table(self) -> dict[str, Any]:
        """Create the clients table if it does not already exist."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                connection.execute(CREATE_CLIENTS_TABLE_SQL)
                connection.commit()
                return RepositoryResult(True, "Clients table is ready.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to initialize clients table: {exc}").__dict__

    def ensure_tables_exist(self) -> None:
        """Ensure required repository tables exist for the current environment."""
        self.initialize_clients_table()

    def _table_exists(self, connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (CLIENTS_TABLE,),
        ).fetchone()
        return row is not None

    def _empty_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=CLIENT_COLUMNS)

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def _normalize_payload(self, client_data: dict[str, Any]) -> dict[str, Any]:
        """Keep only known client fields and support legacy aliases."""
        aliases = {
            "client_id": "id",
            "client_dni": "dni_cuil",
            "e_mail": "email",
            "address_street": "street",
            "address_number": "street_number",
            "address_floor": "floor_apt",
            "address_neigb": "neighborhood",
            "address_city": "city",
            "address_province": "province",
            "address_zip": "zip_code",
            "address_country": "country",
        }

        normalized: dict[str, Any] = {}
        for key, value in client_data.items():
            normalized_key = aliases.get(key, key)
            if normalized_key in WRITEABLE_COLUMNS:
                normalized[normalized_key] = value

        if "country" not in normalized or normalized["country"] in (None, ""):
            normalized["country"] = "Argentina"

        return normalized

    def get_all_clients(self) -> pd.DataFrame:
        """Return all clients as a DataFrame suitable for `st.dataframe`."""
        with get_db_connection(show_errors=self.show_errors) as connection:
            if connection is None or not self._table_exists(connection):
                return self._empty_frame()

            query = f"""
                SELECT {", ".join(CLIENT_COLUMNS)}
                FROM {CLIENTS_TABLE}
                ORDER BY last_name, first_name, id
            """
            return pd.read_sql_query(query, connection)

    def get_client_by_id(self, client_id: int) -> dict[str, Any] | None:
        """Return a single client row as a dict."""
        with get_db_connection(show_errors=self.show_errors) as connection:
            if connection is None or not self._table_exists(connection):
                return None

            row = connection.execute(
                f"""
                SELECT {", ".join(CLIENT_COLUMNS)}
                FROM {CLIENTS_TABLE}
                WHERE id = ?
                """,
                (client_id,),
            ).fetchone()
            return self._row_to_dict(row)

    def add_client(self, client_data: dict[str, Any]) -> dict[str, Any]:
        """Insert a client record and return a friendly result payload."""
        payload = self._normalize_payload(client_data)
        if not payload:
            return RepositoryResult(False, "No client data was provided.").__dict__

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_clients_table()
                columns = list(payload.keys())
                placeholders = ", ".join("?" for _ in columns)
                cursor = connection.execute(
                    f"""
                    INSERT INTO {CLIENTS_TABLE} ({", ".join(columns)})
                    VALUES ({placeholders})
                    """,
                    tuple(payload[column] for column in columns),
                )
                connection.commit()

                return RepositoryResult(
                    True,
                    "Client created successfully.",
                    {"id": cursor.lastrowid},
                ).__dict__
        except sqlite3.IntegrityError:
            return RepositoryResult(False, "A client with that DNI/CUIL already exists.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to add client: {exc}").__dict__

    def update_client(self, client_id: int, client_data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing client row."""
        payload = self._normalize_payload(client_data)
        if not payload:
            return RepositoryResult(False, "No client data was provided for update.").__dict__

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_clients_table()
                set_clause = ", ".join(f"{column} = ?" for column in payload)
                values = [payload[column] for column in payload]
                values.append(client_id)

                cursor = connection.execute(
                    f"""
                    UPDATE {CLIENTS_TABLE}
                    SET {set_clause},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    values,
                )
                connection.commit()

                if cursor.rowcount == 0:
                    return RepositoryResult(False, f"Client {client_id} was not found.").__dict__

                return RepositoryResult(True, f"Client {client_id} updated successfully.").__dict__
        except sqlite3.IntegrityError:
            return RepositoryResult(False, "Another client already uses that DNI/CUIL.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to update client: {exc}").__dict__

    def delete_client(self, client_id: int) -> dict[str, Any]:
        """Delete a client row by ID."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_clients_table()
                cursor = connection.execute(
                    f"DELETE FROM {CLIENTS_TABLE} WHERE id = ?",
                    (client_id,),
                )
                connection.commit()

                if cursor.rowcount == 0:
                    return RepositoryResult(False, f"Client {client_id} was not found.").__dict__

                return RepositoryResult(True, f"Client {client_id} deleted successfully.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to delete client: {exc}").__dict__

    def search_clients(self, search_term: str) -> pd.DataFrame:
        """Search clients across the main identifying and contact fields."""
        normalized_term = search_term.strip()
        if not normalized_term:
            return self.get_all_clients()

        with get_db_connection(show_errors=self.show_errors) as connection:
            if connection is None or not self._table_exists(connection):
                return self._empty_frame()

            like_term = f"%{normalized_term}%"
            where_clause = " OR ".join(f"{column} LIKE ?" for column in SEARCHABLE_COLUMNS)
            params = tuple(like_term for _ in SEARCHABLE_COLUMNS)
            query = f"""
                SELECT {", ".join(CLIENT_COLUMNS)}
                FROM {CLIENTS_TABLE}
                WHERE {where_clause}
                ORDER BY last_name, first_name, id
            """
            return pd.read_sql_query(query, connection, params=params)

    def get_client_count(self) -> int:
        """Return the number of client rows for dashboard metrics."""
        with get_db_connection(show_errors=self.show_errors) as connection:
            if connection is None or not self._table_exists(connection):
                return 0

            row = connection.execute(f"SELECT COUNT(*) AS total FROM {CLIENTS_TABLE}").fetchone()
            return int(row["total"]) if row else 0
