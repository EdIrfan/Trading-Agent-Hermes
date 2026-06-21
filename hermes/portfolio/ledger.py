"""Append-only SQLite ledger of every fill.

The ledger is the immutable audit trail (decision D7). Portfolio balances are
derivable from it; ``portfolio.json`` is a convenience snapshot, the ledger is
the truth. One row per fill, never updated or deleted.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hermes.core.models import Fill, Side

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    symbol      TEXT    NOT NULL,
    side        TEXT    NOT NULL,
    quantity    REAL    NOT NULL,
    price       REAL    NOT NULL,
    fee         REAL    NOT NULL,
    order_id    TEXT,
    broker      TEXT    NOT NULL
);
"""


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, fill: Fill) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO fills (ts, symbol, side, quantity, price, fee, order_id, broker)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (fill.ts, fill.symbol, fill.side.value, fill.quantity,
                 fill.price, fill.fee, fill.order_id, fill.broker),
            )

    def all_fills(self) -> list[Fill]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM fills ORDER BY id ASC").fetchall()
        return [self._row_to_fill(r) for r in rows]

    def recent_fills(self, limit: int = 20) -> list[Fill]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM fills ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_fill(r) for r in reversed(rows)]

    @staticmethod
    def _row_to_fill(r: sqlite3.Row) -> Fill:
        return Fill(
            symbol=r["symbol"], side=Side(r["side"]), quantity=r["quantity"],
            price=r["price"], fee=r["fee"], ts=r["ts"],
            order_id=r["order_id"], broker=r["broker"],
        )
