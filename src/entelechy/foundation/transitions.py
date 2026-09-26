"""Transition records and the one deterministic apply path (RPL-1, RPL-3).

A record names content only by digest. Body bytes never enter lineage, so
FORGET can remove them for real.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from entelechy.foundation.canonical import Canonical, Json
from entelechy.foundation.types import (
    Check,
    EventRow,
    IssueRow,
    ObjectHeader,
    ObjectRef,
    OperationEntry,
    OrganRef,
    Provenance,
    Rows,
    expect_int,
    expect_list,
    expect_object,
    expect_text,
    field_of,
)

RECORD_SCHEMA = 1


class RecordError(ValueError):
    """A transition record is malformed or inconsistent."""


@dataclass(frozen=True)
class DecodedRecord:
    seq: int
    omega_id: str
    rows: Rows


def build_record(
    *,
    seq: int,
    omega_id: str,
    proposer: OrganRef,
    reason: str,
    operations: Sequence[OperationEntry],
    prior: Sequence[ObjectRef],
    provenance: Sequence[Provenance],
    versions: Sequence[ObjectHeader],
    events: Sequence[EventRow],
    justification: Sequence[Check],
    issues: Sequence[IssueRow] = (),
) -> dict[str, Canonical]:
    """The canonical transition record (PER-6)."""
    return {
        "type": "Transition",
        "schema": RECORD_SCHEMA,
        "seq": seq,
        "omega_id": omega_id,
        "proposer": proposer.to_canonical(),
        "reason": reason,
        "operations": [entry.to_canonical() for entry in operations],
        "prior": [ref.to_canonical() for ref in prior],
        "provenance": [item.to_canonical() for item in provenance],
        "versions": [header.to_canonical() for header in versions],
        "events": [event.to_canonical() for event in events],
        "justification": [check.to_canonical() for check in justification],
        "issues": [item.to_canonical() for item in issues],
    }


def decode_record(record: Json) -> DecodedRecord:
    """Turn a parsed record into Heart rows. Deterministic; never calls an organ."""
    data = expect_object(record, "record")
    if data.get("type") != "Transition" or data.get("schema") != RECORD_SCHEMA:
        raise RecordError("not a v1 transition record")
    seq = expect_int(field_of(data, "seq"), "record.seq")
    omega_id = expect_text(field_of(data, "omega_id"), "record.omega_id")
    provenance = tuple(
        Provenance.from_canonical(item)
        for item in expect_list(field_of(data, "provenance"), "record.provenance")
    )
    versions = tuple(
        ObjectHeader.from_canonical(item)
        for item in expect_list(field_of(data, "versions"), "record.versions")
    )
    events = tuple(
        EventRow.from_canonical(item)
        for item in expect_list(field_of(data, "events"), "record.events")
    )
    issues = tuple(
        IssueRow.from_canonical(item)
        for item in expect_list(field_of(data, "issues"), "record.issues")
    )
    stamped = [item.seq for item in provenance]
    stamped += [header.seq for header in versions]
    stamped += [event.seq for event in events]
    if any(item != seq for item in stamped):
        raise RecordError(f"record {seq} contains rows stamped with another seq")
    return DecodedRecord(seq, omega_id, Rows(provenance, versions, events, issues))
