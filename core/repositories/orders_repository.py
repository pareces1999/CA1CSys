from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.db.connection import get_db_connection


ORDERS_TABLE = "orders"
ORDER_ITEMS_TABLE = "order_items"
CREATE_ORDERS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {ORDERS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_kg REAL DEFAULT 0,
    estimated_value REAL DEFAULT 0,
    status TEXT DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients_pers_data(id)
)
"""
CREATE_ORDER_ITEMS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {ORDER_ITEMS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_description TEXT NOT NULL,
    quantity REAL DEFAULT 0,
    weight_per_unit REAL DEFAULT 0,
    kg_contribution REAL DEFAULT 0,
    unit_value REAL DEFAULT 0,
    line_total REAL DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES {ORDERS_TABLE}(id) ON DELETE CASCADE
)
"""


@dataclass
class RepositoryResult:
    """Simple response object for repository write operations."""

    success: bool
    message: str
    data: dict[str, Any] | None = None


class OrdersRepository:
    """Persistence layer for orders and related line items."""

    def __init__(self, *, show_errors: bool = False) -> None:
        self.show_errors = show_errors
        self.ensure_tables_exist()

    def initialize_orders_tables(self) -> dict[str, Any]:
        """Create orders tables if they do not already exist."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(CREATE_ORDERS_TABLE_SQL)
                connection.execute(CREATE_ORDER_ITEMS_TABLE_SQL)
                connection.commit()
                return RepositoryResult(True, "Orders tables are ready.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to initialize orders tables: {exc}").__dict__

    def ensure_tables_exist(self) -> None:
        """Ensure orders persistence tables exist for the current environment."""
        self.initialize_orders_tables()

    def save_order(self, order_data: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        """Insert an order header and its line items in one transaction."""
        if not order_data.get("client_id"):
            return RepositoryResult(False, "A client must be selected before saving an order.").__dict__
        if not items:
            return RepositoryResult(False, "At least one valid line item is required.").__dict__

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                connection.execute("PRAGMA foreign_keys = ON")
                self.initialize_orders_tables()

                with connection:
                    cursor = connection.execute(
                        f"""
                        INSERT INTO {ORDERS_TABLE} (
                            client_id,
                            order_date,
                            total_kg,
                            estimated_value,
                            status,
                            notes
                        )
                        VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
                        """,
                        (
                            order_data["client_id"],
                            float(order_data.get("total_kg", 0) or 0),
                            float(order_data.get("estimated_value", 0) or 0),
                            str(order_data.get("status", "draft")),
                            order_data.get("notes"),
                        ),
                    )
                    order_id = int(cursor.lastrowid)

                    item_rows = [
                        (
                            order_id,
                            str(item.get("product_description", "")).strip(),
                            float(item.get("quantity", 0) or 0),
                            float(item.get("weight_per_unit", 0) or 0),
                            float(item.get("kg_contribution", 0) or 0),
                            float(item.get("unit_value", 0) or 0),
                            float(item.get("line_total", 0) or 0),
                        )
                        for item in items
                    ]

                    connection.executemany(
                        f"""
                        INSERT INTO {ORDER_ITEMS_TABLE} (
                            order_id,
                            product_description,
                            quantity,
                            weight_per_unit,
                            kg_contribution,
                            unit_value,
                            line_total
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        item_rows,
                    )

                return RepositoryResult(
                    True,
                    f"Order {order_id} saved successfully.",
                    {"order_id": order_id},
                ).__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to save order: {exc}").__dict__

    def get_recent_orders(self, limit: int = 10) -> pd.DataFrame:
        """Return recent orders joined with basic client information."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return pd.DataFrame()

                self.initialize_orders_tables()
                query = f"""
                    SELECT
                        o.id,
                        o.order_date,
                        o.total_kg,
                        o.estimated_value,
                        o.status,
                        o.notes,
                        c.first_name,
                        c.last_name,
                        c.dni_cuil,
                        COUNT(oi.id) AS line_count
                    FROM {ORDERS_TABLE} o
                    LEFT JOIN clients_pers_data c ON c.id = o.client_id
                    LEFT JOIN {ORDER_ITEMS_TABLE} oi ON oi.order_id = o.id
                    GROUP BY
                        o.id,
                        o.order_date,
                        o.total_kg,
                        o.estimated_value,
                        o.status,
                        o.notes,
                        c.first_name,
                        c.last_name,
                        c.dni_cuil
                    ORDER BY o.id DESC
                    LIMIT ?
                """
                recent_df = pd.read_sql_query(query, connection, params=(limit,))
                if recent_df.empty:
                    return recent_df

                recent_df["client_name"] = (
                    recent_df["first_name"].fillna("").astype(str).str.strip()
                    + " "
                    + recent_df["last_name"].fillna("").astype(str).str.strip()
                ).str.strip()
                recent_df["client_name"] = recent_df["client_name"].where(
                    recent_df["client_name"] != "",
                    "Unknown client",
                )
                recent_df["client_label"] = recent_df["client_name"] + " - " + recent_df["dni_cuil"].fillna("No DNI").astype(str)
                return recent_df
        except sqlite3.Error:
            return pd.DataFrame()

    def get_order_by_id(self, order_id: int) -> dict[str, Any] | None:
        """Return one order header plus its line items."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return None

                self.initialize_orders_tables()
                order_row = connection.execute(
                    f"""
                    SELECT
                        o.*,
                        c.first_name,
                        c.last_name,
                        c.dni_cuil
                    FROM {ORDERS_TABLE} o
                    LEFT JOIN clients_pers_data c ON c.id = o.client_id
                    WHERE o.id = ?
                    """,
                    (order_id,),
                ).fetchone()
                if order_row is None:
                    return None

                item_rows = connection.execute(
                    f"""
                    SELECT
                        id,
                        order_id,
                        product_description,
                        quantity,
                        weight_per_unit,
                        kg_contribution,
                        unit_value,
                        line_total
                    FROM {ORDER_ITEMS_TABLE}
                    WHERE order_id = ?
                    ORDER BY id
                    """,
                    (order_id,),
                ).fetchall()
                order_dict = dict(order_row)
                order_dict["items"] = [dict(row) for row in item_rows]
                return order_dict
        except sqlite3.Error:
            return None

    def get_open_order_count(self) -> int:
        """Return the number of non-closed orders for dashboard use."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return 0

                self.initialize_orders_tables()
                row = connection.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM {ORDERS_TABLE}
                    WHERE status NOT IN ('completed', 'cancelled')
                    """
                ).fetchone()
                return int(row["total"]) if row else 0
        except sqlite3.Error:
            return 0

    def get_all_orders(self, *, status: str | None = None, limit: int | None = None) -> pd.DataFrame:
        """Return orders (most recent first) with client info and line count. Supports optional status filter and limit."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return pd.DataFrame()

                self.initialize_orders_tables()
                where = ""
                params: list[Any] = []
                if status:
                    where = "WHERE o.status = ?"
                    params.append(status)

                limit_clause = f"LIMIT {int(limit)}" if limit else ""

                query = f"""
                    SELECT
                        o.id,
                        o.order_date,
                        o.total_kg,
                        o.estimated_value,
                        o.status,
                        o.notes,
                        o.client_id,
                        c.first_name,
                        c.last_name,
                        c.dni_cuil,
                        COUNT(oi.id) AS line_count
                    FROM {ORDERS_TABLE} o
                    LEFT JOIN clients_pers_data c ON c.id = o.client_id
                    LEFT JOIN {ORDER_ITEMS_TABLE} oi ON oi.order_id = o.id
                    {where}
                    GROUP BY
                        o.id, o.order_date, o.total_kg, o.estimated_value,
                        o.status, o.notes, o.client_id,
                        c.first_name, c.last_name, c.dni_cuil
                    ORDER BY o.id DESC
                    {limit_clause}
                """
                df = pd.read_sql_query(query, connection, params=params or None)
                if df.empty:
                    return df

                client_name = (
                    df["first_name"].fillna("").astype(str).str.strip()
                    + " "
                    + df["last_name"].fillna("").astype(str).str.strip()
                ).str.strip()
                df["client_name"] = client_name.where(client_name != "", "Unknown client")
                df["client_label"] = df["client_name"] + " - " + df["dni_cuil"].fillna("No DNI").astype(str)
                return df
        except sqlite3.Error:
            return pd.DataFrame()

    def update_order(self, order_id: int, order_data: dict[str, Any]) -> dict[str, Any]:
        """Update allowed header fields of an order (primarily status and notes for workflow)."""
        allowed = {"status", "notes"}
        payload = {k: v for k, v in order_data.items() if k in allowed}
        if not payload:
            return RepositoryResult(False, "No updatable fields (status/notes) were provided.").__dict__

        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                self.initialize_orders_tables()
                set_clause = ", ".join(f"{col} = ?" for col in payload)
                values = list(payload.values())
                values.append(order_id)

                cursor = connection.execute(
                    f"UPDATE {ORDERS_TABLE} SET {set_clause} WHERE id = ?",
                    values,
                )
                connection.commit()

                if cursor.rowcount == 0:
                    return RepositoryResult(False, f"Order {order_id} was not found.").__dict__
                return RepositoryResult(True, f"Order {order_id} updated successfully.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to update order: {exc}").__dict__

    def delete_order(self, order_id: int) -> dict[str, Any]:
        """Delete an order and all its line items (foreign key cascade handles items)."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return RepositoryResult(False, "Database connection is not available.").__dict__

                connection.execute("PRAGMA foreign_keys = ON")
                self.initialize_orders_tables()
                cursor = connection.execute(f"DELETE FROM {ORDERS_TABLE} WHERE id = ?", (order_id,))
                connection.commit()

                if cursor.rowcount == 0:
                    return RepositoryResult(False, f"Order {order_id} was not found.").__dict__
                return RepositoryResult(True, f"Order {order_id} deleted successfully.").__dict__
        except sqlite3.Error as exc:
            return RepositoryResult(False, f"Failed to delete order: {exc}").__dict__

    def get_order_status_counts(self) -> dict[str, int]:
        """Return dict of status -> count for dashboard/metrics in Order Management."""
        try:
            with get_db_connection(show_errors=self.show_errors) as connection:
                if connection is None:
                    return {}
                self.initialize_orders_tables()
                rows = connection.execute(
                    f"SELECT status, COUNT(*) as cnt FROM {ORDERS_TABLE} GROUP BY status"
                ).fetchall()
                return {str(row["status"]): int(row["cnt"]) for row in rows}
        except sqlite3.Error:
            return {}
