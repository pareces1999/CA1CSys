from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "DBca1c.db"


@dataclass
class DBInfo:
    """Simple status payload returned to Streamlit pages."""

    backend: str
    status: str
    message: str
    database_path: str | None = None
    sqlite_version: str | None = None
    table_count: int = 0
    tables: list[str] | None = None


def _safe_secret(key: str, default: Any = None) -> Any:
    """Read a Streamlit secret without failing when the key is absent."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _report_error(message: str, *, show_to_user: bool = True) -> None:
    """Display a Streamlit-friendly error when running in app context."""
    if not show_to_user:
        return

    try:
        st.error(message)
    except Exception:
        # Keep this helper safe for non-Streamlit execution contexts.
        pass


def get_sqlite_db_path() -> Path:
    """
    Resolve the local SQLite database path.

    Priority:
    1. `db_path` in Streamlit secrets
    2. `database.path` in Streamlit secrets
    3. project-root `DBca1c.db`
    """
    configured_path = _safe_secret("db_path")

    if configured_path:
        return Path(str(configured_path)).expanduser()

    database_section = _safe_secret("database", {})
    if isinstance(database_section, Mapping):
        section_path = database_section.get("path")
        if section_path:
            return Path(str(section_path)).expanduser()

    return DEFAULT_SQLITE_PATH


def get_db_config() -> dict[str, Any]:
    """Return normalized database configuration for the active environment."""
    turso_url = _safe_secret("turso_url") or _safe_secret("libsql_url")
    turso_token = _safe_secret("turso_auth_token") or _safe_secret("libsql_auth_token")
    sqlite_path = get_sqlite_db_path()

    if turso_url and turso_token:
        return {
            "backend": "turso",
            "url": str(turso_url),
            "auth_token": str(turso_token),
            "sqlite_path": sqlite_path,
        }

    return {
        "backend": "sqlite",
        "sqlite_path": sqlite_path,
    }


class DBConnection(AbstractContextManager["sqlite3.Connection | None"]):
    """Context manager for database connections with future Turso readiness."""

    def __init__(self, *, show_errors: bool = True) -> None:
        self.show_errors = show_errors
        self.config = get_db_config()
        self.backend = str(self.config["backend"])
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection | None:
        try:
            if self.backend == "sqlite":
                sqlite_path = Path(self.config["sqlite_path"])
                self._connection = sqlite3.connect(sqlite_path)
                self._connection.row_factory = sqlite3.Row
                return self._connection

            # Turso/libSQL support will be plugged in once the client package
            # and deployment credentials are finalized.
            return None
        except sqlite3.Error as exc:
            _report_error(f"Database connection failed: {exc}", show_to_user=self.show_errors)
            return None
        except Exception as exc:
            _report_error(f"Unexpected database error: {exc}", show_to_user=self.show_errors)
            return None

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        return False


def get_db_connection(*, show_errors: bool = True) -> DBConnection:
    """Return a reusable database context manager."""
    return DBConnection(show_errors=show_errors)


def get_connection(*, show_errors: bool = True) -> DBConnection:
    """Backward-friendly alias for the database context manager."""
    return get_db_connection(show_errors=show_errors)


def get_db_info(*, show_errors: bool = False) -> DBInfo:
    """Return a lightweight database status summary for the UI."""
    config = get_db_config()
    backend = str(config["backend"])

    if backend == "turso":
        return DBInfo(
            backend="turso",
            status="ready",
            message="Ready for Turso",
        )

    sqlite_path = Path(config["sqlite_path"])
    if not sqlite_path.exists():
        return DBInfo(
            backend="sqlite",
            status="missing",
            message="Local SQLite database file not found yet.",
            database_path=str(sqlite_path),
        )

    try:
        with get_db_connection(show_errors=show_errors) as connection:
            if connection is None:
                return DBInfo(
                    backend="sqlite",
                    status="error",
                    message="Database connection could not be created.",
                    database_path=str(sqlite_path),
                )

            version_row = connection.execute("SELECT sqlite_version()").fetchone()
            tables = [
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                ).fetchall()
            ]

            return DBInfo(
                backend="sqlite",
                status="connected",
                message="Connected to local SQLite",
                database_path=str(sqlite_path),
                sqlite_version=version_row[0] if version_row else None,
                table_count=len(tables),
                tables=tables,
            )
    except sqlite3.Error as exc:
        _report_error(f"Database query failed: {exc}", show_to_user=show_errors)
        return DBInfo(
            backend="sqlite",
            status="error",
            message=f"Database query failed: {exc}",
            database_path=str(sqlite_path),
        )
    except Exception as exc:
        _report_error(f"Unexpected database error: {exc}", show_to_user=show_errors)
        return DBInfo(
            backend="sqlite",
            status="error",
            message=f"Unexpected database error: {exc}",
            database_path=str(sqlite_path),
        )
