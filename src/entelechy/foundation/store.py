"""SQLite persistence.

The store enforces storage invariants: append-only tables, increasing seq,
foreign keys and digest integrity. It never decides epistemic legality; the
validator does. Organs never receive a Store.
"""

import json
import os
import sqlite3
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from entelechy.foundation.canonical import canonical_bytes, digest, parse, verify
from entelechy.foundation.transitions import build_record, decode_record
from entelechy.foundation.types import (
    EventRow,
    EventType,
    IssueRow,
    Mode,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Operation,
    OrganRef,
    Provenance,
    ProvenanceInput,
    Role,
    Rows,
)
from entelechy.foundation.validator import AcceptedTransition

SCHEMA_VERSION = "2"

_TABLES = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE origin (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    omega_id TEXT NOT NULL,
    manifest BLOB NOT NULL,
    manifest_digest TEXT NOT NULL
) STRICT;

CREATE TABLE transitions (
    seq INTEGER PRIMARY KEY CHECK (seq > 0),
    record BLOB NOT NULL,
    record_digest TEXT NOT NULL
) STRICT;

CREATE TABLE provenance (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    operation TEXT,
    organ_id TEXT,
    organ_version TEXT,
    seed_spec TEXT,
    seq INTEGER NOT NULL
) STRICT;

CREATE TABLE object_versions (
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    type TEXT NOT NULL,
    provenance_id TEXT NOT NULL REFERENCES provenance (id),
    derived_from TEXT NOT NULL,
    created_seq INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    retired_by INTEGER,
    forgotten INTEGER NOT NULL CHECK (forgotten IN (0, 1)),
    body_digest TEXT NOT NULL,
    PRIMARY KEY (object_id, version)
) STRICT;

CREATE TABLE provenance_inputs (
    provenance_id TEXT NOT NULL REFERENCES provenance (id),
    position INTEGER NOT NULL,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (provenance_id, position),
    FOREIGN KEY (object_id, version) REFERENCES object_versions (object_id, version)
) STRICT;

CREATE TABLE content (
    digest TEXT PRIMARY KEY,
    body BLOB NOT NULL
) STRICT;

CREATE TABLE events (
    seq INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    PRIMARY KEY (seq, idx)
) STRICT;

CREATE TABLE infon_issues (
    object_id TEXT PRIMARY KEY,
    issue_digest TEXT NOT NULL
) STRICT;

CREATE INDEX infon_issues_by_issue ON infon_issues (issue_digest);
"""

_APPEND_ONLY = (
    "origin",
    "transitions",
    "provenance",
    "object_versions",
    "provenance_inputs",
    "events",
    "infon_issues",
)

_GUARDS = """
CREATE TRIGGER transitions_seq_increases BEFORE INSERT ON transitions
WHEN NEW.seq <= COALESCE((SELECT MAX(seq) FROM transitions), 0)
BEGIN SELECT RAISE(ABORT, 'seq must increase (SEQ-2)'); END;

CREATE TRIGGER object_versions_in_order BEFORE INSERT ON object_versions
WHEN NEW.version <> COALESCE(
    (SELECT MAX(version) FROM object_versions WHERE object_id = NEW.object_id), 0) + 1
BEGIN SELECT RAISE(ABORT, 'object versions must be consecutive'); END;

CREATE TRIGGER meta_no_delete BEFORE DELETE ON meta
BEGIN SELECT RAISE(ABORT, 'meta: rows cannot be deleted'); END;

CREATE TRIGGER meta_only_next_seq_rises BEFORE UPDATE ON meta
WHEN OLD.key <> 'next_seq' OR NEW.key <> OLD.key
    OR CAST(NEW.value AS INTEGER) <= CAST(OLD.value AS INTEGER)
BEGIN SELECT RAISE(ABORT, 'meta: only next_seq may change, and only upward (SEQ-2)'); END;

CREATE TRIGGER content_no_update BEFORE UPDATE ON content
BEGIN SELECT RAISE(ABORT, 'content: bodies are immutable'); END;

CREATE TRIGGER content_delete_only_forgotten BEFORE DELETE ON content
WHEN EXISTS (
    SELECT 1 FROM object_versions AS v
    WHERE v.body_digest = OLD.digest
      AND NOT EXISTS (
          SELECT 1 FROM object_versions AS f
          WHERE f.object_id = v.object_id AND f.forgotten = 1
      )
)
BEGIN SELECT RAISE(ABORT, 'content: only forgotten content may be deleted (RPL-3)'); END;
"""


def _append_only_triggers() -> str:
    return "\n".join(
        f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, 'append-only: {table}'); END;"
        for table in _APPEND_ONLY
        for action in ("UPDATE", "DELETE")
    )


EXPECTED_TRIGGERS = frozenset(
    [f"{table}_no_{action}" for table in _APPEND_ONLY for action in ("update", "delete")]
    + [
        "transitions_seq_increases",
        "object_versions_in_order",
        "meta_no_delete",
        "meta_only_next_seq_rises",
        "content_no_update",
        "content_delete_only_forgotten",
    ]
)

_SCHEMA = (
    "BEGIN;\n"
    + _TABLES
    + _append_only_triggers()
    + _GUARDS
    + "INSERT INTO meta (key, value) VALUES "
    + f"('schema_version', '{SCHEMA_VERSION}'), ('digest_algorithm', 'sha256'), "
    + "('next_seq', '1');\n"
    + "COMMIT;\n"
)

_VERSION_COLUMNS = (
    "object_id, version, type, provenance_id, derived_from, created_seq, seq, "
    "retired_by, forgotten, body_digest"
)

_DELETE_UNSHARED_CONTENT = """
DELETE FROM content WHERE digest = :digest AND NOT EXISTS (
    SELECT 1 FROM object_versions AS v
    WHERE v.body_digest = :digest
      AND NOT EXISTS (
          SELECT 1 FROM object_versions AS f
          WHERE f.object_id = v.object_id AND f.forgotten = 1
      )
)
"""


class StoreError(Exception):
    """The database is missing, already exists, or is not an intact Entelechy Heart."""


def _header(row: Any) -> ObjectHeader:
    return ObjectHeader(
        id=row[0],
        version=row[1],
        type=ObjectType(row[2]),
        provenance_id=row[3],
        derived_from=tuple(str(item) for item in json.loads(row[4])),
        created_seq=row[5],
        seq=row[6],
        retired_by=row[7],
        forgotten=bool(row[8]),
        body_digest=row[9],
    )


class Store:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    @staticmethod
    def _connect(target: str) -> sqlite3.Connection:
        connection = sqlite3.connect(target, autocommit=True)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
        except sqlite3.DatabaseError:
            connection.close()
            raise
        return connection

    @classmethod
    def create(cls, path: Path) -> Store:
        if path.exists():
            raise StoreError(f"{path} already exists; refusing to overwrite it")
        try:
            connection = cls._connect(str(path))
        except sqlite3.Error as error:
            raise StoreError(f"cannot create {path}: {error}") from error
        try:
            connection.executescript(_SCHEMA)
        except BaseException:
            connection.close()
            raise
        return cls(connection)

    @classmethod
    def build(cls, path: Path, initialize: Callable[[Store], None]) -> None:
        """Build a complete Heart and publish it at `path` only if `path` does not exist.

        The Heart is built under a temporary name in the same directory and
        closed before it is published, so a failure before publication leaves
        nothing at `path`, and the temporary files are removed. Publication is
        a hard link: link(2) on POSIX and CreateHardLink on Windows both refuse
        an existing target, so an existing file is never replaced. That refusal
        is tested on Windows (NTFS) only, and publication needs a filesystem
        that supports hard links. A process killed mid-build can leave a
        temporary file behind, but never a partial Heart at `path`.
        """
        if path.exists():
            raise StoreError(f"{path} already exists; refusing to overwrite it")
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.creating")
        try:
            store = cls.create(temporary)
            try:
                initialize(store)
            finally:
                store.close()
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise StoreError(f"{path} already exists; refusing to overwrite it") from error
        finally:
            for suffix in ("", "-wal", "-shm"):
                temporary.with_name(temporary.name + suffix).unlink(missing_ok=True)

    @classmethod
    def memory(cls) -> Store:
        connection = cls._connect(":memory:")
        connection.executescript(_SCHEMA)
        return cls(connection)

    @classmethod
    def open(cls, path: Path) -> Store:
        # Check through a read-only connection first, so that a file which is
        # not a Heart is refused without being changed (no WAL switch).
        cls.open_readonly(path).close()
        try:
            connection = cls._connect(str(path))
        except sqlite3.Error as error:
            raise StoreError(f"{path} is not an Entelechy Heart: {error}") from error
        return cls._checked(connection)

    @classmethod
    def open_readonly(cls, path: Path) -> Store:
        """A connection SQLite itself refuses to write through. Organs read via this."""
        if not path.is_file():
            raise StoreError(f"{path} does not exist")
        try:
            connection = sqlite3.connect(
                f"{path.resolve().as_uri()}?mode=ro", uri=True, autocommit=True
            )
        except sqlite3.Error as error:
            raise StoreError(f"{path} is not an Entelechy Heart: {error}") from error
        return cls._checked(connection)

    @classmethod
    def _checked(cls, connection: sqlite3.Connection) -> Store:
        store = cls(connection)
        try:
            store._check_schema()
        except BaseException:
            connection.close()
            raise
        return store

    def _check_schema(self) -> None:
        try:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            triggers = {
                name
                for (name,) in self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                )
            }
            origins = self._conn.execute("SELECT COUNT(*) FROM origin").fetchone()[0]
        except sqlite3.DatabaseError as error:
            raise StoreError(f"not an Entelechy Heart: {error}") from error
        if row is None or row[0] != SCHEMA_VERSION:
            raise StoreError("unsupported schema version")
        missing = EXPECTED_TRIGGERS - triggers
        if missing:
            raise StoreError(f"storage guards are missing: {sorted(missing)}")
        if origins != 1:
            raise StoreError("origin is missing")

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    # Writes

    def allocate_seq(self) -> int:
        """Reserve the next seq. It is never reused, even if nothing commits with it."""
        with self._transaction():
            seq = self.next_seq()
            self._conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'next_seq'", (str(seq + 1),)
            )
        return seq

    def write_origin(
        self,
        omega_id: str,
        manifest: bytes,
        manifest_digest: str,
        rows: Rows,
        contents: Mapping[str, bytes],
    ) -> None:
        with self._transaction():
            self._conn.execute(
                "INSERT INTO origin (singleton, omega_id, manifest, manifest_digest) "
                "VALUES (1, ?, ?, ?)",
                (omega_id, manifest, manifest_digest),
            )
            self._insert_rows(rows)
            self._insert_contents(contents)

    def apply_replayed(self, rows: Rows) -> None:
        """Insert rows decoded from lineage. Only replay calls this, on a fresh store."""
        with self._transaction():
            self._insert_rows(rows)

    def commit(self, accepted: AcceptedTransition, omega_id: str) -> None:
        """Persist one accepted transition atomically (PER-5)."""
        if not isinstance(accepted, AcceptedTransition):
            raise TypeError("only an AcceptedTransition from the validator can be committed")
        record = canonical_bytes(
            build_record(
                seq=accepted.seq,
                omega_id=omega_id,
                proposer=accepted.proposal.organ,
                reason=accepted.proposal.reason,
                operations=accepted.operations,
                prior=accepted.prior,
                provenance=accepted.provenance,
                versions=accepted.versions,
                events=accepted.events,
                justification=accepted.justification,
                issues=accepted.issues,
            )
        )
        with self._transaction():
            self._conn.execute(
                "INSERT INTO transitions (seq, record, record_digest) VALUES (?, ?, ?)",
                (accepted.seq, record, digest(record)),
            )
            # Apply from the recorded bytes, exactly as replay will (RPL-1).
            self._insert_rows(decode_record(parse(record)).rows)
            self._insert_contents(accepted.bodies)
            self._delete_forgotten_content(
                header.id for header in accepted.versions if header.forgotten
            )

    def _insert_rows(self, rows: Rows) -> None:
        self._insert_provenance(rows.provenance)
        self._insert_versions(rows.versions)
        self._insert_inputs(rows.provenance)
        self._insert_events(rows.events)
        self._insert_issues(rows.issues)

    def _insert_provenance(self, provenance: Iterable[Provenance]) -> None:
        self._conn.executemany(
            "INSERT INTO provenance "
            "(id, mode, operation, organ_id, organ_version, seed_spec, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item.id,
                    item.mode.value,
                    None if item.operation is None else item.operation.value,
                    None if item.organ is None else item.organ.id,
                    None if item.organ is None else item.organ.version,
                    item.seed_spec,
                    item.seq,
                )
                for item in provenance
            ],
        )

    def _insert_versions(self, versions: Iterable[ObjectHeader]) -> None:
        self._conn.executemany(
            f"INSERT INTO object_versions ({_VERSION_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    header.id,
                    header.version,
                    header.type.value,
                    header.provenance_id,
                    canonical_bytes(list(header.derived_from)).decode("utf-8"),
                    header.created_seq,
                    header.seq,
                    header.retired_by,
                    int(header.forgotten),
                    header.body_digest,
                )
                for header in versions
            ],
        )

    def _insert_inputs(self, provenance: Iterable[Provenance]) -> None:
        self._conn.executemany(
            "INSERT INTO provenance_inputs (provenance_id, position, object_id, version, role) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (item.id, position, entry.ref.id, entry.ref.version, entry.role.value)
                for item in provenance
                for position, entry in enumerate(item.inputs)
            ],
        )

    def _insert_events(self, events: Iterable[EventRow]) -> None:
        self._conn.executemany(
            "INSERT INTO events (seq, idx, type, object_id) VALUES (?, ?, ?, ?)",
            [(event.seq, event.index, event.type.value, event.object_id) for event in events],
        )

    def _insert_issues(self, issues: Iterable[IssueRow]) -> None:
        self._conn.executemany(
            "INSERT INTO infon_issues (object_id, issue_digest) VALUES (?, ?)",
            [(item.object_id, item.issue_digest) for item in issues],
        )

    def _insert_contents(self, contents: Mapping[str, bytes]) -> None:
        for body_digest, body in contents.items():
            if not verify(body, body_digest):
                raise StoreError(f"content does not match its digest {body_digest}")
            self._conn.execute(
                "INSERT OR IGNORE INTO content (digest, body) VALUES (?, ?)",
                (body_digest, body),
            )

    def _delete_forgotten_content(self, object_ids: Iterable[str]) -> None:
        for object_id in object_ids:
            digests = [
                row[0]
                for row in self._conn.execute(
                    "SELECT DISTINCT body_digest FROM object_versions WHERE object_id = ?",
                    (object_id,),
                )
            ]
            for body_digest in digests:
                self._conn.execute(_DELETE_UNSHARED_CONTENT, {"digest": body_digest})

    # Reads

    def next_seq(self) -> int:
        row = self._conn.execute("SELECT value FROM meta WHERE key = 'next_seq'").fetchone()
        return int(row[0])

    def origin(self) -> tuple[str, bytes, str]:
        row = self._conn.execute(
            "SELECT omega_id, manifest, manifest_digest FROM origin"
        ).fetchone()
        if row is None:
            raise StoreError("origin is missing")
        return str(row[0]), bytes(row[1]), str(row[2])

    def latest(self, object_id: str) -> ObjectHeader | None:
        row = self._conn.execute(
            f"SELECT {_VERSION_COLUMNS} FROM object_versions WHERE object_id = ? "
            "ORDER BY version DESC LIMIT 1",
            (object_id,),
        ).fetchone()
        return None if row is None else _header(row)

    def header_at(self, ref: ObjectRef) -> ObjectHeader | None:
        """The header of one specific version. Roots are version-relative (ROT-5)."""
        row = self._conn.execute(
            f"SELECT {_VERSION_COLUMNS} FROM object_versions WHERE object_id = ? AND version = ?",
            (ref.id, ref.version),
        ).fetchone()
        return None if row is None else _header(row)

    def provenance_of(self, provenance_id: str) -> Provenance | None:
        return self.provenance(provenance_id)

    def issue_of(self, object_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT issue_digest FROM infon_issues WHERE object_id = ?", (object_id,)
        ).fetchone()
        return None if row is None else str(row[0])

    def infon_ids_for_issue(self, issue: str) -> list[str]:
        return [
            row[0]
            for row in self._conn.execute(
                "SELECT object_id FROM infon_issues WHERE issue_digest = ? ORDER BY object_id",
                (issue,),
            )
        ]

    def versions_of(self, object_id: str) -> list[ObjectHeader]:
        return self.versions(object_id)

    def versions(self, object_id: str | None = None) -> list[ObjectHeader]:
        if object_id is None:
            rows = self._conn.execute(
                f"SELECT {_VERSION_COLUMNS} FROM object_versions ORDER BY object_id, version"
            )
        else:
            rows = self._conn.execute(
                f"SELECT {_VERSION_COLUMNS} FROM object_versions WHERE object_id = ? "
                "ORDER BY version",
                (object_id,),
            )
        return [_header(row) for row in rows]

    def provenance(self, provenance_id: str) -> Provenance | None:
        row = self._conn.execute(
            "SELECT id, mode, operation, organ_id, organ_version, seed_spec, seq "
            "FROM provenance WHERE id = ?",
            (provenance_id,),
        ).fetchone()
        if row is None:
            return None
        inputs = tuple(
            ProvenanceInput(ObjectRef(object_id, version), Role(role))
            for object_id, version, role in self._conn.execute(
                "SELECT object_id, version, role FROM provenance_inputs "
                "WHERE provenance_id = ? ORDER BY position",
                (provenance_id,),
            )
        )
        return Provenance(
            id=row[0],
            mode=Mode(row[1]),
            inputs=inputs,
            operation=None if row[2] is None else Operation(row[2]),
            organ=None if row[3] is None else OrganRef(row[3], row[4]),
            seed_spec=row[5],
            seq=row[6],
        )

    def all_provenance(self) -> list[Provenance]:
        ids = [row[0] for row in self._conn.execute("SELECT id FROM provenance ORDER BY id")]
        return [item for item in map(self.provenance, ids) if item is not None]

    def content(self, body_digest: str) -> bytes | None:
        row = self._conn.execute(
            "SELECT body FROM content WHERE digest = ?", (body_digest,)
        ).fetchone()
        return None if row is None else bytes(row[0])

    def transitions(self) -> list[tuple[int, bytes, str]]:
        return [
            (int(seq), bytes(record), str(record_digest))
            for seq, record, record_digest in self._conn.execute(
                "SELECT seq, record, record_digest FROM transitions ORDER BY seq"
            )
        ]

    def events(self) -> list[EventRow]:
        return [
            EventRow(seq, index, EventType(event_type), object_id)
            for seq, index, event_type, object_id in self._conn.execute(
                "SELECT seq, idx, type, object_id FROM events ORDER BY seq, idx"
            )
        ]

    def issues(self) -> list[IssueRow]:
        """Every Infon's IssueDigest, in a stable order (INF-7). Part of Heart structure."""
        return [
            IssueRow(object_id, issue_digest)
            for object_id, issue_digest in self._conn.execute(
                "SELECT object_id, issue_digest FROM infon_issues ORDER BY object_id"
            )
        ]
