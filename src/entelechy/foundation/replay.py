"""Replay and read-only views of the Heart (Law 7).

ReplayCurrent(Origin, Lineage, ContentStore_live) = Heart_current.
Origin and lineage rebuild structure; the live content store supplies bytes.
"""

from collections.abc import Collection

from entelechy.foundation.canonical import CanonicalError, Json, digest_of, parse, verify
from entelechy.foundation.seed import Manifest, seed_heart
from entelechy.foundation.store import Store
from entelechy.foundation.transitions import RecordError, decode_record
from entelechy.foundation.types import (
    EventRow,
    InfonBody,
    ObjectHeader,
    ObjectType,
    Stub,
)


class IntegrityError(Exception):
    """Origin, lineage, the materialized Heart and content do not agree."""


def heart_digest(store: Store) -> str:
    """Digest of structure: every version header, provenance record and event."""
    return digest_of(
        {
            "versions": [header.to_canonical() for header in store.versions()],
            "provenance": [item.to_canonical() for item in store.all_provenance()],
            "events": [event.to_canonical() for event in store.events()],
        }
    )


def rebuild(store: Store, up_to: int | None = None) -> Store:
    """Rebuild the Heart's structure in memory from origin and lineage alone."""
    omega_id, manifest_bytes, manifest_digest = store.origin()
    if not verify(manifest_bytes, manifest_digest):
        raise IntegrityError("the origin manifest does not match its digest")
    try:
        manifest = Manifest.from_bytes(manifest_bytes)
    except CanonicalError as error:
        raise IntegrityError(f"the origin manifest is malformed: {error}") from error
    if manifest.omega_id != omega_id:
        raise IntegrityError("the origin manifest names a different Ω")
    fresh = Store.memory()
    rows, _ = seed_heart(manifest)
    fresh.write_origin(omega_id, manifest_bytes, manifest_digest, rows, {})
    for seq, record, record_digest in store.transitions():
        if up_to is not None and seq > up_to:
            break
        if not verify(record, record_digest):
            fresh.close()
            raise IntegrityError(f"transition {seq} does not match its digest")
        try:
            decoded = decode_record(parse(record))
        except (CanonicalError, RecordError) as error:
            fresh.close()
            raise IntegrityError(f"transition {seq} is malformed: {error}") from error
        if decoded.seq != seq or decoded.omega_id != omega_id:
            fresh.close()
            raise IntegrityError(f"transition {seq} belongs to another seq or Ω")
        fresh.apply_replayed(decoded.rows)
    return fresh


def replay_current(store: Store) -> str:
    """Check the whole Heart against origin and lineage; return its digest (RPL-2)."""
    fresh = rebuild(store)
    try:
        rebuilt = heart_digest(fresh)
        if rebuilt != heart_digest(store):
            raise IntegrityError("the materialized Heart differs from replay of origin and lineage")
        versions = fresh.versions()
        forgotten = {header.id for header in versions if header.forgotten}
        for header in versions:
            if header.id in forgotten:
                continue
            data = store.content(header.body_digest)
            if data is None:
                raise IntegrityError(f"content of {header.id} v{header.version} is missing")
            if not verify(data, header.body_digest):
                raise IntegrityError(f"content of {header.id} v{header.version} was altered")
        return rebuilt
    finally:
        fresh.close()


class HeartView:
    """A read-only view of a Heart. Organs get this, never a Store."""

    def __init__(
        self,
        structure: Store,
        content: Store | None = None,
        forgotten_later: Collection[str] = (),
    ) -> None:
        self._structure = structure
        self._content = content if content is not None else structure
        self._forgotten_later = frozenset(forgotten_later)

    def latest(self, object_id: str) -> ObjectHeader | None:
        return self._structure.latest(object_id)

    def versions(self, object_id: str) -> list[ObjectHeader]:
        return self._structure.versions(object_id)

    def objects(self, object_type: ObjectType | None = None) -> list[ObjectHeader]:
        latest: dict[str, ObjectHeader] = {}
        for header in self._structure.versions():
            latest[header.id] = header
        return [h for h in latest.values() if object_type is None or h.type is object_type]

    def body(self, object_id: str) -> Json | Stub | None:
        header = self.latest(object_id)
        if header is None:
            return None
        if header.forgotten or object_id in self._forgotten_later:
            return Stub.CONTENT_FORGOTTEN
        data = self._content.content(header.body_digest)
        if data is None or not verify(data, header.body_digest):
            raise IntegrityError(f"content of {object_id} is missing or altered")
        return parse(data)

    def infon(self, object_id: str) -> InfonBody | Stub | None:
        body = self.body(object_id)
        if body is None or isinstance(body, Stub):
            return body
        return InfonBody.from_canonical(body)

    def events(self) -> list[EventRow]:
        return self._structure.events()

    def digest(self) -> str:
        return heart_digest(self._structure)


def replay_historical(store: Store, seq: int) -> HeartView:
    """The Heart as it stood at `seq` (RPL-4). Later-forgotten content is a stub."""
    if seq < 0:
        raise ValueError("seq must not be negative")
    fresh = rebuild(store, up_to=seq)
    forgotten_now = {header.id for header in store.versions() if header.forgotten}
    return HeartView(fresh, content=store, forgotten_later=forgotten_now)
