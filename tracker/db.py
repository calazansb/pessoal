"""Armazenamento do histórico em SQLite.

Cada execução gera um *snapshot* (foto do momento) com a lista completa de
seguidores e de quem você segue. Ao salvar um snapshot novo, a diferença em
relação ao snapshot anterior é calculada e gravada como *eventos*
(novo seguidor, deixou de me seguir, comecei a seguir, parei de seguir),
formando o histórico permanente.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    pk         TEXT PRIMARY KEY,   -- id do Instagram (ou "u:<username>" p/ importações)
    username   TEXT NOT NULL,
    full_name  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at        TEXT NOT NULL,  -- ISO 8601 UTC
    source          TEXT NOT NULL,  -- 'api' ou 'export'
    followers_count INTEGER NOT NULL,
    following_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_followers (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    user_pk     TEXT NOT NULL REFERENCES users(pk),
    PRIMARY KEY (snapshot_id, user_pk)
);

CREATE TABLE IF NOT EXISTS snapshot_following (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    user_pk     TEXT NOT NULL REFERENCES users(pk),
    PRIMARY KEY (snapshot_id, user_pk)
);

-- Histórico de mudanças entre snapshots consecutivos
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    taken_at    TEXT NOT NULL,
    type        TEXT NOT NULL,  -- new_follower | lost_follower | started_following | stopped_following
    user_pk     TEXT NOT NULL REFERENCES users(pk)
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
"""

EVENT_TYPES = (
    "new_follower",
    "lost_follower",
    "started_following",
    "stopped_following",
)


@dataclass
class User:
    pk: str
    username: str
    full_name: str = ""


@dataclass
class SnapshotDiff:
    """Resultado da comparação entre o snapshot novo e o anterior."""

    snapshot_id: int
    is_first: bool
    new_followers: list[User]
    lost_followers: list[User]
    started_following: list[User]
    stopped_following: list[User]


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------
    # Gravação
    # ------------------------------------------------------------------
    def save_snapshot(
        self,
        followers: dict[str, User],
        following: dict[str, User],
        source: str,
        taken_at: datetime | None = None,
    ) -> SnapshotDiff:
        """Salva um snapshot novo e retorna a diferença em relação ao anterior."""
        taken_at = taken_at or datetime.now(timezone.utc)
        ts = taken_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        prev = self.latest_snapshot_id()

        cur = self.conn.cursor()
        for user in {**followers, **following}.values():
            cur.execute(
                "INSERT INTO users (pk, username, full_name) VALUES (?, ?, ?) "
                "ON CONFLICT(pk) DO UPDATE SET username = excluded.username, "
                "full_name = excluded.full_name",
                (user.pk, user.username, user.full_name),
            )

        cur.execute(
            "INSERT INTO snapshots (taken_at, source, followers_count, following_count) "
            "VALUES (?, ?, ?, ?)",
            (ts, source, len(followers), len(following)),
        )
        snap_id = cur.lastrowid

        cur.executemany(
            "INSERT INTO snapshot_followers (snapshot_id, user_pk) VALUES (?, ?)",
            [(snap_id, pk) for pk in followers],
        )
        cur.executemany(
            "INSERT INTO snapshot_following (snapshot_id, user_pk) VALUES (?, ?)",
            [(snap_id, pk) for pk in following],
        )

        # Calcula os eventos comparando com o snapshot anterior
        if prev is None:
            diff = SnapshotDiff(snap_id, True, [], [], [], [])
        else:
            prev_followers, prev_following = self.snapshot_sets(prev)
            new_f = sorted(set(followers) - prev_followers)
            lost_f = sorted(prev_followers - set(followers))
            started = sorted(set(following) - prev_following)
            stopped = sorted(prev_following - set(following))

            events = (
                [("new_follower", pk) for pk in new_f]
                + [("lost_follower", pk) for pk in lost_f]
                + [("started_following", pk) for pk in started]
                + [("stopped_following", pk) for pk in stopped]
            )
            cur.executemany(
                "INSERT INTO events (snapshot_id, taken_at, type, user_pk) "
                "VALUES (?, ?, ?, ?)",
                [(snap_id, ts, etype, pk) for etype, pk in events],
            )
            diff = SnapshotDiff(
                snap_id,
                False,
                self._users(new_f),
                self._users(lost_f),
                self._users(started),
                self._users(stopped),
            )

        self.conn.commit()
        return diff

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------
    def latest_snapshot_id(self) -> int | None:
        row = self.conn.execute("SELECT MAX(id) AS id FROM snapshots").fetchone()
        return row["id"]

    def snapshot_info(self, snapshot_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()

    def snapshot_sets(self, snapshot_id: int) -> tuple[set[str], set[str]]:
        followers = {
            r["user_pk"]
            for r in self.conn.execute(
                "SELECT user_pk FROM snapshot_followers WHERE snapshot_id = ?",
                (snapshot_id,),
            )
        }
        following = {
            r["user_pk"]
            for r in self.conn.execute(
                "SELECT user_pk FROM snapshot_following WHERE snapshot_id = ?",
                (snapshot_id,),
            )
        }
        return followers, following

    def not_following_back(self, snapshot_id: int) -> list[User]:
        """Quem eu sigo e não me segue de volta."""
        followers, following = self.snapshot_sets(snapshot_id)
        return self._users(sorted(following - followers))

    def fans(self, snapshot_id: int) -> list[User]:
        """Quem me segue e eu não sigo de volta."""
        followers, following = self.snapshot_sets(snapshot_id)
        return self._users(sorted(followers - following))

    def mutuals_count(self, snapshot_id: int) -> int:
        followers, following = self.snapshot_sets(snapshot_id)
        return len(followers & following)

    def list_snapshots(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT s.*, "
            "  (SELECT COUNT(*) FROM events e WHERE e.snapshot_id = s.id) AS event_count "
            "FROM snapshots s ORDER BY s.id"
        ).fetchall()

    def list_events(self, limit: int | None = None, etype: str | None = None):
        sql = (
            "SELECT e.taken_at, e.type, u.username, u.full_name "
            "FROM events e JOIN users u ON u.pk = e.user_pk "
        )
        params: list = []
        if etype:
            sql += "WHERE e.type = ? "
            params.append(etype)
        sql += "ORDER BY e.id DESC "
        if limit:
            sql += "LIMIT ?"
            params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def _users(self, pks: list[str]) -> list[User]:
        users = []
        for pk in pks:
            row = self.conn.execute(
                "SELECT pk, username, full_name FROM users WHERE pk = ?", (pk,)
            ).fetchone()
            if row:
                users.append(User(row["pk"], row["username"], row["full_name"]))
        return users
