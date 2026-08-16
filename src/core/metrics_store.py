"""MetricsStore: SQLite con eventos, metricas, alertas y snapshots (M3)."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from src.core.config import appdata_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    distro TEXT,
    message TEXT,
    data TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    distro TEXT NOT NULL,
    state TEXT,
    ram_mb INTEGER,
    ram_percent REAL,
    ip TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    tipo TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    distro TEXT,
    message TEXT,
    estado TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    distro TEXT NOT NULL,
    path TEXT NOT NULL,
    size_bytes INTEGER,
    result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    created REAL NOT NULL,
    expires REAL,
    note TEXT
);
"""


class MetricsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else appdata_dir() / "metrics.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _exec(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # -- events (journal U6) -------------------------------------------------

    def log_event(self, type_: str, distro: str | None = None, message: str = "", data: dict | None = None) -> None:
        import json

        self._exec(
            "INSERT INTO events (ts, type, distro, message, data) VALUES (?,?,?,?,?)",
            (time.time(), type_, distro, message, json.dumps(data or {}, ensure_ascii=False)),
        )

    def list_events(self, limit: int = 100) -> list[dict]:
        return [
            {
                "ts": r["ts"],
                "type": r["type"],
                "distro": r["distro"],
                "message": r["message"],
                "data": r["data"],
            }
            for r in self._query("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        ]

    # -- metrics ----------------------------------------------------------------

    def insert_metric(self, distro: str, state: str, ram_mb: int | None, ram_percent: float | None, ip: str | None) -> None:
        self._exec(
            "INSERT INTO metrics (ts, distro, state, ram_mb, ram_percent, ip) VALUES (?,?,?,?,?,?)",
            (time.time(), distro, state, ram_mb, ram_percent, ip),
        )

    def list_metrics(self, distro: str | None = None, limit: int = 500) -> list[dict]:
        sql = "SELECT * FROM metrics"
        params: tuple = ()
        if distro:
            sql += " WHERE distro = ?"
            params = (distro,)
        sql += " ORDER BY id DESC LIMIT ?"
        return [
            {
                "ts": r["ts"],
                "distro": r["distro"],
                "state": r["state"],
                "ram_mb": r["ram_mb"],
                "ram_percent": r["ram_percent"],
                "ip": r["ip"],
            }
            for r in self._query(sql, (*params, limit))
        ]

    # -- alerts ------------------------------------------------------------------

    def add_alert(self, tipo: str, message: str, severity: str = "warning", distro: str | None = None) -> None:
        self._exec(
            "INSERT INTO alerts (ts, tipo, severity, distro, message) VALUES (?,?,?,?,?)",
            (time.time(), tipo, severity, distro, message),
        )

    def list_alerts(self, limit: int = 100) -> list[dict]:
        return [
            {
                "ts": r["ts"],
                "tipo": r["tipo"],
                "severity": r["severity"],
                "distro": r["distro"],
                "message": r["message"],
                "estado": r["estado"],
            }
            for r in self._query("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
        ]

    def resolve_alerts(self, tipo: str, distro: str | None = None) -> None:
        if distro:
            self._exec("UPDATE alerts SET estado='resolved' WHERE tipo=? AND distro=?", (tipo, distro))
        else:
            self._exec("UPDATE alerts SET estado='resolved' WHERE tipo=?", (tipo,))

    # -- snapshots -----------------------------------------------------------------

    def record_snapshot(self, distro: str, path: str, size_bytes: int | None, result: str = "ok") -> None:
        self._exec(
            "INSERT INTO snapshots (ts, distro, path, size_bytes, result) VALUES (?,?,?,?,?)",
            (time.time(), distro, path, size_bytes, result),
        )

    def list_snapshots(self, limit: int = 100) -> list[dict]:
        return [
            {
                "ts": r["ts"],
                "distro": r["distro"],
                "path": r["path"],
                "size_bytes": r["size_bytes"],
                "result": r["result"],
            }
            for r in self._query("SELECT * FROM snapshots ORDER BY id DESC LIMIT ?", (limit,))
        ]

    # -- retencion -------------------------------------------------------------------

    def prune(self, metrics_days: int = 30, events_days: int = 90) -> None:
        cutoff = time.time() - metrics_days * 86400
        self._exec("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        cutoff_ev = time.time() - events_days * 86400
        self._exec("DELETE FROM events WHERE ts < ?", (cutoff_ev,))

    # -- tokens (para la API) ----------------------------------------------------------

    def add_token(self, token_hash: str, scope: str, expires: float | None, note: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO tokens (token_hash, scope, created, expires, note) VALUES (?,?,?,?,?)",
            (token_hash, scope, time.time(), expires, note),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_tokens(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r["id"],
                "scope": r["scope"],
                "created": r["created"],
                "expires": r["expires"],
                "note": r["note"],
            }
            for r in self._query("SELECT * FROM tokens ORDER BY id")
        ]

    def token_exists(self, token_hash: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM tokens WHERE token_hash = ?", (token_hash,))
        if not rows:
            return None
        r = rows[0]
        return {
            "id": r["id"],
            "scope": r["scope"],
            "created": r["created"],
            "expires": r["expires"],
            "note": r["note"],
        }

    def revoke_token(self, token_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM tokens WHERE id = ?", (token_id,))
        self._conn.commit()
        return cur.rowcount > 0
