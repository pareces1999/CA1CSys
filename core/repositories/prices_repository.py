from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.db.connection import get_db_connection


PRICES_TABLE = "prices"
PRICE_COLUMNS = [
    "id",
    "product_name",
    "description",
    "price_per_kg",
    "price_per_unit",
    "weight_per_unit",
    "unit",
    "category",
    "notes",
    "active",
    "created_at",
]
WRITEABLE_COLUMNS = [
    "product_name",
    "description",
    "price_per_kg",
    "price_per_unit",
    "weight_per_unit",
    "unit",
    "category",
    "notes",
    "active",
]
SEARCHABLE_COLUMNS = [
    "product_name",
    "description",
    "unit",
    "category",
    "notes",
]
CREATE_PRICES_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {PRICES_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    description TEXT,
    price_per_kg REAL DEFAULT 0,
    price_per_unit REAL DEFAULT 0,
    weight_per_unit REAL DEFAULT 0,
    unit TEXT DEFAULT 'kg',
    category TEXT,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

WEIGHT_PER_UNIT_COLUMN_SQL = (
    f"ALTER TABLE {PRICES_TABLE} ADD COLUMN weight_per_unit REAL DEFAULT 0"
)


@dataclass
class RepositoryResult:
    """Simple response object for repository write operations."""

    success: bool
    message: str
    data: dict[str, Any] | None = None


class PricesRepository:
    """Persistence layer for product prices and future price-list management."""

    def __init__(self, *, show_errors: bool = False) -> None:
        self.show_errors = show_errors
        self.ensure_tables_exist()

    def initialize_prices_table(self) -> dict[str, Any]:
        """Create the prices table if it does not already exist."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                connection.execute(CREATE_PRICES_TABLE_SQL)
                existing_columns = {
                    str(row["name"])
                    for row in connection.execute(f"PRAGMA table_info({PRICES_TABLE})").fetchall()
                }
                if "weight_per_unit" not in existing_columns:
                    connection.execute(WEIGHT_PER_UNIT_COLUMN_SQL)
                connection.commit()
                return RepositoryResult(True, "Prices table is ready.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to initialize prices table: {exc}").__dict__

    def ensure_tables_exist(self) -> None:
        """Ensure the prices table exists for the current environment."""
        self.initialize_prices_table()

    def _normalize_payload(self, price_data: dict[str, Any]) -> dict[str, Any]:
        """Keep only known writable columns and normalize the active flag."""
        payload = {
            key: price_data.get(key)
            for key in WRITEABLE_COLUMNS
            if key in price_data
        }
        payload["active"] = 1 if payload.get("active", True) else 0
        return payload

    def _empty_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    def get_all_prices(self) -> pd.DataFrame:
        """Return all price entries ordered for display in Streamlit."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return self._empty_frame()

                self.initialize_prices_table()
                query = f"""
                    SELECT {", ".join(PRICE_COLUMNS)}
                    FROM {PRICES_TABLE}
                    ORDER BY active DESC, product_name ASC, id DESC
                """
                return pd.read_sql_query(query, connection)
        except sqlite3.Error:
            return self._empty_frame()

    def add_price(self, price_data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new product price entry."""
        payload = self._normalize_payload(price_data)
        if not payload.get("product_name"):
            return RepositoryResult(False, "Product name is required.").__dict__

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_prices_table()
                columns = list(payload.keys())
                placeholders = ", ".join("?" for _ in columns)
                cursor = connection.execute(
                    f"""
                    INSERT INTO {PRICES_TABLE} ({", ".join(columns)})
                    VALUES ({placeholders})
                    """,
                    tuple(payload[column] for column in columns),
                )
                connection.commit()
                return RepositoryResult(
                    True,
                    "Product price created successfully.",
                    {"id": int(cursor.lastrowid)},
                ).__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to add price: {exc}").__dict__

    def update_price(self, price_id: int, price_data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing product price entry."""
        payload = self._normalize_payload(price_data)
        if not payload:
            return RepositoryResult(False, "No price data was provided for update.").__dict__

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_prices_table()
                set_clause = ", ".join(f"{column} = ?" for column in payload)
                values = [payload[column] for column in payload]
                values.append(price_id)
                cursor = connection.execute(
                    f"""
                    UPDATE {PRICES_TABLE}
                    SET {set_clause}
                    WHERE id = ?
                    """,
                    values,
                )
                connection.commit()
                if cursor.rowcount == 0:
                    return RepositoryResult(False, f"Price entry {price_id} was not found.").__dict__
                return RepositoryResult(True, f"Price entry {price_id} updated successfully.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to update price: {exc}").__dict__

    def delete_price(self, price_id: int) -> dict[str, Any]:
        """Delete a product price entry."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_prices_table()
                cursor = connection.execute(
                    f"DELETE FROM {PRICES_TABLE} WHERE id = ?",
                    (price_id,),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    return RepositoryResult(False, f"Price entry {price_id} was not found.").__dict__
                return RepositoryResult(True, f"Price entry {price_id} deleted successfully.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to delete price: {exc}").__dict__

    def search_prices(self, search_term: str) -> pd.DataFrame:
        """Search prices across the main descriptive fields."""
        normalized = search_term.strip()
        if not normalized:
            return self.get_all_prices()

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return self._empty_frame()

                self.initialize_prices_table()
                like_term = f"%{normalized}%"
                where_clause = " OR ".join(f"{column} LIKE ?" for column in SEARCHABLE_COLUMNS)
                params = tuple(like_term for _ in SEARCHABLE_COLUMNS)
                query = f"""
                    SELECT {", ".join(PRICE_COLUMNS)}
                    FROM {PRICES_TABLE}
                    WHERE {where_clause}
                    ORDER BY active DESC, product_name ASC, id DESC
                """
                return pd.read_sql_query(query, connection, params=params)
        except sqlite3.Error:
            return self._empty_frame()

    def get_price_by_id(self, price_id: int) -> dict[str, Any] | None:
        """Return one product price entry as a dict."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return None

                self.initialize_prices_table()
                row = connection.execute(
                    f"""
                    SELECT {", ".join(PRICE_COLUMNS)}
                    FROM {PRICES_TABLE}
                    WHERE id = ?
                    """,
                    (price_id,),
                ).fetchone()
                return dict(row) if row is not None else None
        except sqlite3.Error:
            return None

    def get_active_price_count(self) -> int:
        """Return the number of active product price entries."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return 0

                self.initialize_prices_table()
                row = connection.execute(
                    f"SELECT COUNT(*) AS total FROM {PRICES_TABLE} WHERE active = 1"
                ).fetchone()
                return int(row["total"]) if row else 0
        except sqlite3.Error:
            return 0
