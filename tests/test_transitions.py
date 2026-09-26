import pytest

from entelechy.foundation.canonical import canonical_bytes, digest, parse
from entelechy.foundation.transitions import RecordError, build_record, decode_record
from entelechy.foundation.types import (
    Check,
    EventRow,
    EventType,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Operation,
    OperationEntry,
    OrganRef,
    Provenance,
    ProvenanceKind,
)

SECRET_BODY = b'{"content":"ultraviolet-secret"}'


def record(seq: int = 4, header_seq: int = 4) -> bytes:
    provenance = Provenance(
        "prov:1", ProvenanceKind.OBSERVATION, (), Operation.CONSOLIDATE, OrganRef("eye", "1"), None, seq
    )
    header = ObjectHeader(
        "obs:1", ObjectType.OBSERVATION, 1, "prov:1", (), seq, header_seq, None, False,
        digest(SECRET_BODY),
    )
    return canonical_bytes(
        build_record(
            seq=seq,
            omega_id="omega-1",
            proposer=OrganRef("mind", "1"),
            reason="saw something",
            operations=[OperationEntry(Operation.CONSOLIDATE, "obs:1")],
            prior=[ObjectRef("obs:0", 1)],
            provenance=[provenance],
            versions=[header],
            events=[EventRow(seq, 0, EventType.MEMORY_CONSOLIDATED, "obs:1")],
            justification=[Check(0, "MEM-1", {"clause": "evidence"})],
        )
    )


def test_record_decodes_into_rows() -> None:
    decoded = decode_record(parse(record()))
    assert decoded.seq == 4
    assert decoded.omega_id == "omega-1"
    assert [header.id for header in decoded.rows.versions] == ["obs:1"]
    assert [item.id for item in decoded.rows.provenance] == ["prov:1"]
    assert decoded.rows.events == (EventRow(4, 0, EventType.MEMORY_CONSOLIDATED, "obs:1"),)


def test_record_names_content_by_digest_only_rpl3() -> None:
    data = record()
    assert b"ultraviolet-secret" not in data
    assert digest(SECRET_BODY).encode() in data


def test_rows_stamped_with_another_seq_are_rejected() -> None:
    with pytest.raises(RecordError, match="another seq"):
        decode_record(parse(record(seq=4, header_seq=3)))


def test_non_transition_records_are_rejected() -> None:
    with pytest.raises(RecordError, match="not a v1 transition record"):
        decode_record({"type": "Origin"})
