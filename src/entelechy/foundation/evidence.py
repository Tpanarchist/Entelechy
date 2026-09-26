"""Grounding roots, roles and issue ledgers (FOUNDATIONS §8.14).

Roots establish support ancestry. They are derived from provenance and
lineage on demand (ROT-7); nothing here is authoritative state, which is
exactly what lets EVD-7 demand that every accounting fact be independently
recomputable at replay.
"""

import enum
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from entelechy.foundation.canonical import Canonical, Json, digest_of
from entelechy.foundation.types import (
    Mode,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Provenance,
    Referent,
    Role,
    referent_to_canonical,
)


class EvidenceError(ValueError):
    """The provenance graph cannot be read: a reference is missing, or it cycles (PRV-3)."""


@dataclass(frozen=True)
class Root:
    """One of the three kinds of grounding root (ROT-1)."""

    kind: str
    key: str

    def to_canonical(self) -> dict[str, Canonical]:
        return {"kind": self.kind, "key": self.key}


class RootKind(enum.StrEnum):
    OBSERVATION = "observation"
    TESTIMONY = "testimony"
    EXPERIMENT = "experiment"


def observation_root(observation_id: str) -> Root:
    return Root(RootKind.OBSERVATION.value, observation_id)


def testimony_root(organ_id: str) -> Root:
    return Root(RootKind.TESTIMONY.value, organ_id)


class RootReader(Protocol):
    """What roots_of and the issue ledger need. Implemented by `_Work` and by the Store."""

    def header_at(self, ref: ObjectRef) -> ObjectHeader | None: ...

    def provenance_of(self, provenance_id: str) -> Provenance | None: ...

    def infon_ids_for_issue(self, issue: str) -> Iterable[str]: ...

    def versions_of(self, object_id: str) -> Sequence[ObjectHeader]: ...


def roots_of(ref: ObjectRef, reader: RootReader) -> frozenset[Root]:
    """Roots(x@v) (ROT-6). Version-relative (ROT-5); recomputed, never stored (ROT-7)."""
    return _roots_of(ref, reader, frozenset())


def _roots_of(ref: ObjectRef, reader: RootReader, seen: frozenset[ObjectRef]) -> frozenset[Root]:
    if ref in seen:
        raise EvidenceError(f"provenance cycles back to {ref.id}@{ref.version} (PRV-3)")
    header = reader.header_at(ref)
    if header is None:
        raise EvidenceError(f"no such object version {ref.id}@{ref.version}")
    if header.type is ObjectType.OBSERVATION:
        return frozenset({observation_root(ref.id)})
    provenance = reader.provenance_of(header.provenance_id)
    if provenance is None:
        raise EvidenceError(f"missing provenance for {ref.id}@{ref.version}")
    if provenance.mode is Mode.ORIGIN:
        return frozenset()
    if provenance.mode is Mode.TESTIMONY:
        assert provenance.organ is not None
        return frozenset({testimony_root(provenance.organ.id)})
    seen = seen | {ref}
    result: set[Root] = set()
    for item in provenance.inputs:
        if item.role is Role.ATTRIBUTION:
            continue
        result |= _roots_of(item.ref, reader, seen)
    return frozenset(result)


def roots_of_many(refs: Iterable[ObjectRef], reader: RootReader) -> frozenset[Root]:
    result: set[Root] = set()
    for ref in refs:
        result |= roots_of(ref, reader)
    return frozenset(result)


def issue_digest(relation: str, participants: Sequence[Referent], context: dict[str, Json]) -> str:
    """IssueDigest(I) = Digest(Canonical(ClaimKey(I))) (ISS-1). Polarity is not part of ClaimKey."""
    return digest_of(
        {
            "relation": relation,
            "participants": [referent_to_canonical(item) for item in participants],
            "context": context,
        }
    )


class Classification(enum.StrEnum):
    FIRST_FORMATION = "first_formation"
    CLONE = "clone"
    RE_FORMATION = "re_formation"


def _current_head(object_id: str, reader: RootReader) -> ObjectHeader | None:
    versions = reader.versions_of(object_id)
    if not versions:
        return None
    latest = versions[-1]
    return None if (latest.retired_by is not None or latest.forgotten) else latest


def classify(issue: str, reader: RootReader) -> Classification:
    """ISS-4: classify a FORM_INFON proposal for issue `issue` by the issue's history."""
    members = list(reader.infon_ids_for_issue(issue))
    if not members:
        return Classification.FIRST_FORMATION
    if any(_current_head(object_id, reader) is not None for object_id in members):
        return Classification.CLONE
    return Classification.RE_FORMATION


def ledger(issue: str, reader: RootReader, *, at_seq: int | None = None) -> frozenset[Root]:
    """Ledger(K)@seq (ISS-7): roots admitted into issue K's history at or before `at_seq`.

    Includes every Infon that has ever had this issue: current, retired and
    forgotten (a forgotten Infon's roots are still recomputed from its
    surviving header and provenance, never from its forgotten body).
    """
    result: set[Root] = set()
    for object_id in reader.infon_ids_for_issue(issue):
        for header in reader.versions_of(object_id):
            if at_seq is not None and header.seq > at_seq:
                continue
            result |= roots_of(header.ref(), reader)
    return frozenset(result)


def novel_roots(candidate: frozenset[Root], inherited: frozenset[Root]) -> frozenset[Root]:
    """NovelRoots(E, K) = Roots(E) \\ Ledger(K) (EVD-2)."""
    return candidate - inherited


def new_evidence(candidate: frozenset[Root], inherited: frozenset[Root]) -> bool:
    return bool(novel_roots(candidate, inherited))
