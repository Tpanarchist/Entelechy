import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from entelechy.foundation.canonical import digest
from entelechy.foundation.store import Store, StoreError
from entelechy.foundation.types import (
    EventRow,
    EventType,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Operation,
    OrganRef,
    Provenance,
    ProvenanceKind,
    Rows,
)

BODY = b'{"entry":"test"}'
BODY_DIGEST = digest(BODY)


def origin_rows() -> Rows:
    provenance = Provenance("prov:0", ProvenanceKind.ORIGIN, (), None, None, "entelechy-seed/0", 0)
    header = ObjectHeader(
        "self:test", ObjectType.SELF_MAP_ENTRY, 1, "prov:0", (), 0, 0, None, False, BODY_DIGEST
    )
    return Rows((provenance,), (header,))


def later_rows(seq: int) -> Rows:
    provenance = Provenance(
        "prov:1",
        ProvenanceKind.TESTIMONY,
        (ObjectRef("self:test", 1),),
        Operation.FORM_INFON,
        OrganRef("mind", "1"),
        None,
        seq,
    )
    header = ObjectHeader(
        "infon:1", ObjectType.INFON, 1, "prov:1", (), seq, seq, None, False, BODY_DIGEST
    )
    return Rows((provenance,), (header,), (EventRow(seq, 0, EventType.INFON_FORMED, "infon:1"),))


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "heart.db"


@pytest.fixture
def store(path: Path) -> Iterator[Store]:
    store = Store.create(path)
    store.write_origin("test", b"manifest", digest(b"manifest"), origin_rows(), {BODY_DIGEST: BODY})
    yield store
    store.close()


@pytest.fixture
def raw(store: Store, path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, autocommit=True)
    yield connection
    connection.close()


def test_create_refuses_an_existing_path(store: Store, path: Path) -> None:
    with pytest.raises(StoreError, match="already exists"):
        Store.create(path)


def test_open_refuses_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(StoreError, match="does not exist"):
        Store.open(tmp_path / "missing.db")


def test_open_refuses_a_file_that_is_not_a_heart(tmp_path: Path) -> None:
    path = tmp_path / "notes.db"
    path.write_bytes(b"this is not a database, just some bytes " * 4)
    with pytest.raises(StoreError, match="not an Entelechy Heart"):
        Store.open(path)


def test_open_leaves_a_foreign_sqlite_database_untouched(tmp_path: Path) -> None:
    path = tmp_path / "other.db"
    other = sqlite3.connect(path)
    other.execute("CREATE TABLE notes (text TEXT)")
    other.commit()
    other.close()
    before = path.read_bytes()
    with pytest.raises(StoreError, match="not an Entelechy Heart"):
        Store.open(path)
    assert path.read_bytes() == before
    assert not (tmp_path / "other.db-wal").exists()


def test_open_leaves_an_empty_file_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    path.write_bytes(b"")
    with pytest.raises(StoreError, match="not an Entelechy Heart"):
        Store.open(path)
    assert path.read_bytes() == b""


def test_open_refuses_a_heart_without_origin(path: Path) -> None:
    Store.create(path).close()
    with pytest.raises(StoreError, match="origin is missing"):
        Store.open(path)


def test_open_refuses_a_heart_whose_guards_were_dropped(
    store: Store, raw: sqlite3.Connection, path: Path
) -> None:
    raw.execute("DROP TRIGGER events_no_delete")
    with pytest.raises(StoreError, match="guards are missing"):
        Store.open(path)


def test_reads_return_what_was_written(store: Store) -> None:
    store.apply_replayed(later_rows(1))
    header = store.latest("infon:1")
    assert header is not None and header.body_digest == BODY_DIGEST
    provenance = store.provenance("prov:1")
    assert provenance is not None and provenance.inputs == (ObjectRef("self:test", 1),)
    assert store.content(BODY_DIGEST) == BODY
    assert store.events() == [EventRow(1, 0, EventType.INFON_FORMED, "infon:1")]
    assert [h.id for h in store.versions()] == ["infon:1", "self:test"]


def test_seq_is_allocated_once_even_across_reopen_seq2(store: Store, path: Path) -> None:
    assert store.allocate_seq() == 1
    assert store.allocate_seq() == 2
    store.close()
    reopened = Store.open(path)
    assert reopened.allocate_seq() == 3
    reopened.close()


def test_content_must_match_its_digest(path: Path) -> None:
    store = Store.create(path)
    with pytest.raises(StoreError, match="does not match its digest"):
        store.write_origin("test", b"m", digest(b"m"), origin_rows(), {BODY_DIGEST: b"other"})
    store.close()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE origin SET omega_id = 'someone-else'",
        "DELETE FROM origin",
        "UPDATE provenance SET kind = 'observation'",
        "DELETE FROM provenance_inputs",
        "UPDATE object_versions SET forgotten = 1",
        "DELETE FROM object_versions",
        "DELETE FROM events",
        "UPDATE transitions SET record = x'00'",
    ],
)
def test_append_only_tables_refuse_raw_changes(
    store: Store, raw: sqlite3.Connection, statement: str
) -> None:
    store.apply_replayed(later_rows(1))
    raw.execute("INSERT INTO transitions VALUES (1, x'00', 'sha256:0')")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute(statement)


def test_seq_must_increase_seq2(store: Store, raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO transitions VALUES (5, x'00', 'sha256:0')")
    with pytest.raises(sqlite3.IntegrityError, match="seq must increase"):
        raw.execute("INSERT INTO transitions VALUES (4, x'00', 'sha256:0')")


def test_next_seq_only_rises_seq2(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="only upward"):
        raw.execute("UPDATE meta SET value = '0' WHERE key = 'next_seq'")
    with pytest.raises(sqlite3.IntegrityError, match="only next_seq"):
        raw.execute("UPDATE meta SET value = '9' WHERE key = 'schema_version'")


def test_object_versions_must_be_consecutive(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="consecutive"):
        raw.execute(
            "INSERT INTO object_versions VALUES "
            "('self:test', 3, 'SelfMapEntry', 'prov:0', '[]', 0, 0, NULL, 0, 'x')"
        )


def test_live_content_cannot_be_deleted_rpl3(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="only forgotten content"):
        raw.execute("DELETE FROM content")


def test_content_cannot_be_rewritten(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        raw.execute("UPDATE content SET body = x'00'")


def test_readonly_store_cannot_write(store: Store, path: Path) -> None:
    reader = Store.open_readonly(path)
    assert reader.latest("self:test") is not None
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        reader.allocate_seq()
    reader.close()
