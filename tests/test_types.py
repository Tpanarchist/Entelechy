from decimal import Decimal

import pytest

from entelechy.foundation.canonical import Canonical, CanonicalError, Json, canonical_bytes, parse
from entelechy.foundation.types import (
    V1_OPERATIONS,
    EventRow,
    EventType,
    InfonBody,
    InfonStatus,
    Mode,
    ObjectHeader,
    ObjectRef,
    ObjectReferent,
    ObjectType,
    Observation,
    OpaqueReferent,
    Operation,
    OrganRef,
    Polarity,
    Provenance,
    ProvenanceInput,
    RegionReferent,
    Role,
)


def roundtrip(value: Canonical) -> Json:
    return parse(canonical_bytes(value))


HEADER = ObjectHeader(
    id="infon:1",
    type=ObjectType.INFON,
    version=2,
    provenance_id="prov:1",
    derived_from=("infon:0",),
    created_seq=3,
    seq=5,
    retired_by=None,
    forgotten=False,
    body_digest="sha256:" + "0" * 64,
)


def test_header_round_trips() -> None:
    assert ObjectHeader.from_canonical(roundtrip(HEADER.to_canonical())) == HEADER


def test_provenance_round_trips() -> None:
    provenance = Provenance(
        id="prov:1",
        mode=Mode.DERIVATION,
        inputs=(
            ProvenanceInput(ObjectRef("obs:1", 1), Role.DERIVATION_INPUT),
            ProvenanceInput(ObjectRef("infon:2", 3), Role.ATTRIBUTION),
        ),
        operation=Operation.FORM_INFON,
        organ=OrganRef("mind", "1"),
        seed_spec=None,
        seq=4,
    )
    assert Provenance.from_canonical(roundtrip(provenance.to_canonical())) == provenance


def test_origin_provenance_names_the_seed_spec_not_an_organ() -> None:
    provenance = Provenance("prov:0", Mode.ORIGIN, (), None, None, "entelechy-seed/0", 0)
    assert Provenance.from_canonical(roundtrip(provenance.to_canonical())) == provenance


def test_infon_body_round_trips_every_referent_kind() -> None:
    body = InfonBody(
        relation="R1",
        participants=(
            ObjectReferent("self:omega"),
            RegionReferent("obs:1", {"x": [1, 2]}),
            OpaqueReferent("obs:1", "track-7"),
        ),
        polarity=Polarity.POSITIVE,
        context={"channel": "eye"},
        confidence=Decimal("0.75"),
        status=InfonStatus.ACTIVE,
    )
    assert InfonBody.from_canonical(roundtrip(body.to_canonical())) == body


def test_observation_body_round_trips() -> None:
    observation = Observation("obs:1", OrganRef("eye", "1"), 7, {"color": "red"}, ("track-7",))
    assert Observation.from_body("obs:1", roundtrip(observation.body())) == observation


def test_event_round_trips() -> None:
    event = EventRow(9, 0, EventType.INFON_FORMED, "infon:1")
    assert EventRow.from_canonical(roundtrip(event.to_canonical())) == event


def test_missing_fields_are_canonical_errors() -> None:
    with pytest.raises(CanonicalError, match="missing field"):
        ObjectHeader.from_canonical({"id": "x"})


def test_unknown_enum_values_are_canonical_errors() -> None:
    data = roundtrip(Provenance("p", Mode.TESTIMONY, (), None, None, None, 1).to_canonical())
    assert isinstance(data, dict)
    data["mode"] = "dream"
    with pytest.raises(CanonicalError, match="unknown value"):
        Provenance.from_canonical(data)


def test_non_normalized_confidence_is_refused() -> None:
    data = roundtrip(
        InfonBody("R1", (), Polarity.POSITIVE, {}, Decimal("0.8"), InfonStatus.ACTIVE).to_canonical()
    )
    assert isinstance(data, dict)
    data["confidence"] = "0.80"
    with pytest.raises(CanonicalError, match="not normalized"):
        InfonBody.from_canonical(data)


def test_operations_match_foundations_section_10() -> None:
    assert len(Operation) == 20
    assert V1_OPERATIONS == {
        Operation.CONSOLIDATE,
        Operation.FORM_INFON,
        Operation.REVISE_INFON,
        Operation.FORGET,
    }
