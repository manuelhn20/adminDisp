from __future__ import annotations

from typing import Any, Iterable


class SACompatCursor:
    """Cursor-like wrapper over SQLAlchemy Connection.exec_driver_sql."""

    def __init__(self, owner: "SACompatConnection"):
        self._owner = owner
        self._rows: list[tuple[Any, ...]] = []
        self._index = 0
        self.rowcount = -1
        self.description = None

    def _normalize_params(self, params: Any, extra: tuple[Any, ...]) -> Any:
        if extra:
            base = () if params is None else ((params,) if not isinstance(params, (tuple, list)) else tuple(params))
            return tuple(base) + tuple(extra)

        if params is None:
            return ()

        if isinstance(params, list):
            # Keep executemany-style list[tuple] as-is; single list becomes tuple.
            if params and isinstance(params[0], (tuple, list, dict)):
                return params
            return tuple(params)

        return params

    def execute(self, sql: str, params: Any = None, *extra: Any):
        bind_params = self._normalize_params(params, extra)
        conn = self._owner._ensure_connection()
        result = conn.exec_driver_sql(sql, bind_params)

        self.rowcount = result.rowcount
        self._index = 0
        self._rows = []
        self.description = None

        if result.returns_rows:
            keys = list(result.keys())
            self.description = [(k, None, None, None, None, None, None) for k in keys]
            self._rows = [tuple(r) for r in result.fetchall()]

        if self._owner.autocommit:
            self._owner.commit()

        return self

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self):
        if self._index >= len(self._rows):
            return []
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows

    def close(self):
        return None


class SACompatConnection:
    """Minimal pyodbc-like connection facade backed by SQLAlchemy Engine."""

    def __init__(self, engine):
        self.engine = engine
        self.autocommit = False
        self._conn = None

    def _ensure_connection(self):
        if self._conn is None:
            self._conn = self.engine.connect()
        return self._conn

    def _new_cursor(self):
        return SACompatCursor(self)

    def cursor(self):
        return self._new_cursor()

    def get_cursor(self):
        return self._new_cursor()

    def commit(self):
        conn = self._ensure_connection()
        conn.commit()

    def rollback(self):
        conn = self._ensure_connection()
        conn.rollback()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
