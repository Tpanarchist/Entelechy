"""Unit tests for evidence.py (FOUNDATIONS §8.14): roots, issues and ledgers.

A small in-memory reader builds provenance graphs directly, so deep chains
and cycles can be tested without going through the Store or validator.
"""

from dataclasses import dataclass, field

import pytest

from entelechy.foundation.evidence import (
    Classification,
    EvidenceError,
    Root,
    classify,
    issue_digest,
    ledger,
    new_evidence,
    novel_roots,
    observation_root,
    roots_of,
    roots_of_many,
)
from entelechy.foundation.evidence import testimony_root as make_testimony_root
from entelechy.foundation.types import (
    Mode,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    OrganRef,
    Provenance,
    ProvenanceInput,
    Role,
)


def _header(
    object_id: str,
    object_type: ObjectType,
    version: int,
    provenance_id: str,
    seq: int,
    *,
    retired_by: int | None = None,
    forgotten: bool = False,
) -> ObjectHeader:
    return ObjectHeader(
        id=object_id,
        type=object_type,
        version=version,
        provenance_id=provenance_id,
        derived_from=(),
        created_seq=seq,
        seq=seq,
        retired_by=retired_by,
        forgotten=forgotten,
        body_digest="sha256:" + "0" * 64,
    )


@dataclass
class FakeReader:
    """A minimal RootReader (and HeartReader-shaped) test double."""

    headers: dict[ObjectRef, ObjectHeader] = field(default_factory=dict)
    provenance: dict[str, Provenance] = field(default_factory=dict)
    issues: dict[str, list[str]] = field(default_factory=dict)

    def header_at(self, ref: ObjectRef) -> ObjectHeader | None:
        return self.headers.get(ref)

    def provenance_of(self, provenance_id: str) -> Provenance | None:
        return self.provenance.get(provenance_id)

    def infon_ids_for_issue(self, issue: str) -> list[str]:
        return list(self.issues.get(issue, []))

    def versions_of(self, object_id: str) -> list[ObjectHeader]:
        return sorted(
            (header for ref, header in self.headers.items() if ref.id == object_id),
            key=lambda header: header.version,
        )

    def add_observation(self, object_id: str, *, seq: int = 1) -> ObjectRef:
        ref = ObjectRef(object_id, 1)
        self.headers[ref] = _header(object_id, ObjectType.OBSERVATION, 1, "prov:none", seq)
        return ref

    def add_origin(self, object_id: str, *, seq: int = 0) -> ObjectRef:
        ref = ObjectRef(object_id, 1)
        provenance_id = f"prov:origin:{object_id}"
        self.provenance[provenance_id] = Provenance(
            id=provenance_id,
            mode=Mode.ORIGIN,
            inputs=(),
            operation=None,
            organ=None,
            seed_spec="entelechy-seed/0",
            seq=seq,
        )
        self.headers[ref] = _header(object_id, ObjectType.SELF_MAP_ENTRY, 1, provenance_id, seq)
        return ref

    def add_infon(
        self,
        object_id: str,
        issue: str,
        *,
        version: int = 1,
        mode: Mode = Mode.TESTIMONY,
        organ: str = "mind",
        inputs: tuple[ProvenanceInput, ...] = (),
        seq: int = 1,
        retired: bool = False,
        forgotten: bool = False,
        provenance_id: str | None = None,
    ) -> ObjectRef:
        ref = ObjectRef(object_id, version)
        provenance_id = provenance_id or f"prov:{object_id}:{version}"
        self.provenance[provenance_id] = Provenance(
            id=provenance_id,
            mode=mode,
            inputs=inputs,
            operation=None,
            organ=None if mode is Mode.ORIGIN else OrganRef(organ, "1"),
            seed_spec=None,
            seq=seq,
        )
        self.headers[ref] = _header(
            object_id,
            ObjectType.INFON,
            version,
            provenance_id,
            seq,
            retired_by=seq if retired else None,
            forgotten=forgotten,
        )
        self.issues.setdefault(issue, [])
        if object_id not in self.issues[issue]:
            self.issues[issue].append(object_id)
        return ref


# Roots (ROT).


def test_an_observations_root_is_itself_rot6() -> None:
    reader = FakeReader()
    ref = reader.add_observation("obs:1")
    assert roots_of(ref, reader) == {observation_root("obs:1")}


def test_testimony_roots_are_keyed_by_the_organ_rot3() -> None:
    reader = FakeReader()
    ref = reader.add_infon("infon:1", "issue:a", mode=Mode.TESTIMONY, organ="mind")
    assert roots_of(ref, reader) == {make_testimony_root("mind")}


def test_seed_structure_has_no_roots_rot6() -> None:
    reader = FakeReader()
    ref = reader.add_origin("self:omega")
    assert roots_of(ref, reader) == frozenset()


def test_derivation_roots_are_the_union_of_non_attribution_inputs_rot6() -> None:
    reader = FakeReader()
    observed = reader.add_observation("obs:1")
    attributed = reader.add_observation("obs:2")
    derived = reader.add_infon(
        "infon:1",
        "issue:a",
        mode=Mode.DERIVATION,
        inputs=(
            ProvenanceInput(observed, Role.DERIVATION_INPUT),
            ProvenanceInput(attributed, Role.ATTRIBUTION),
        ),
    )
    # The attribution input passes no roots (ROL-2): only obs:1 grounds this.
    assert roots_of(derived, reader) == {observation_root("obs:1")}


def test_roots_are_version_relative_rot5() -> None:
    reader = FakeReader()
    witness_v1 = reader.add_infon("infon:1", "issue:a", version=1, mode=Mode.TESTIMONY, organ="mind")
    evidence = reader.add_observation("obs:1")
    witness_v2 = reader.add_infon(
        "infon:1",
        "issue:a",
        version=2,
        mode=Mode.REVISION,
        inputs=(
            ProvenanceInput(witness_v1, Role.REVISION_TARGET),
            ProvenanceInput(evidence, Role.SUPPORT),
        ),
    )
    assert roots_of(witness_v1, reader) == {make_testimony_root("mind")}
    assert roots_of(witness_v2, reader) == {make_testimony_root("mind"), observation_root("obs:1")}


def test_deep_chains_flow_through_to_the_observation() -> None:
    reader = FakeReader()
    root_observation = reader.add_observation("obs:1")
    a = reader.add_infon(
        "infon:a", "issue:a", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(root_observation, Role.DERIVATION_INPUT),),
    )
    b = reader.add_infon(
        "infon:b", "issue:b", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(a, Role.DERIVATION_INPUT),),
    )
    c = reader.add_infon(
        "infon:c", "issue:c", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(b, Role.DERIVATION_INPUT),),
    )
    assert roots_of(c, reader) == {observation_root("obs:1")}


def test_cyclic_provenance_is_refused_prv3() -> None:
    reader = FakeReader()
    a_ref = ObjectRef("infon:a", 1)
    b_ref = ObjectRef("infon:b", 1)
    reader.provenance["prov:a"] = Provenance(
        id="prov:a", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(b_ref, Role.DERIVATION_INPUT),),
        operation=None, organ=OrganRef("mind", "1"), seed_spec=None, seq=1,
    )
    reader.headers[a_ref] = _header("infon:a", ObjectType.INFON, 1, "prov:a", 1)
    reader.provenance["prov:b"] = Provenance(
        id="prov:b", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(a_ref, Role.DERIVATION_INPUT),),
        operation=None, organ=OrganRef("mind", "1"), seed_spec=None, seq=1,
    )
    reader.headers[b_ref] = _header("infon:b", ObjectType.INFON, 1, "prov:b", 1)
    with pytest.raises(EvidenceError, match="cycles"):
        roots_of(a_ref, reader)


def test_a_missing_referenced_version_is_refused() -> None:
    reader = FakeReader()
    with pytest.raises(EvidenceError, match="no such object version"):
        roots_of(ObjectRef("infon:ghost", 1), reader)


def test_a_missing_provenance_record_is_refused() -> None:
    reader = FakeReader()
    ref = ObjectRef("infon:a", 1)
    reader.headers[ref] = _header("infon:a", ObjectType.INFON, 1, "prov:missing", 1)
    with pytest.raises(EvidenceError, match="missing provenance"):
        roots_of(ref, reader)


def test_roots_of_many_unions_across_refs() -> None:
    reader = FakeReader()
    first = reader.add_observation("obs:1")
    second = reader.add_observation("obs:2")
    assert roots_of_many((first, second), reader) == {
        observation_root("obs:1"),
        observation_root("obs:2"),
    }


# Case 29: novelty is counted by root, not by how many inputs cite it.


def test_two_inputs_sharing_one_root_count_as_one_root() -> None:
    reader = FakeReader()
    observation = reader.add_observation("obs:1")
    # Two different Infons, both grounded only in the same Observation.
    first = reader.add_infon(
        "infon:first", "issue:first", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(observation, Role.DERIVATION_INPUT),),
    )
    second = reader.add_infon(
        "infon:second", "issue:second", mode=Mode.DERIVATION,
        inputs=(ProvenanceInput(observation, Role.DERIVATION_INPUT),),
    )
    candidate = roots_of_many((first, second), reader)
    # One underlying root, not two: the formation calculus counts roots, not
    # citing objects.
    assert candidate == {observation_root("obs:1")}


# Issues and ledgers (ISS, EVD).


def test_issue_digest_excludes_polarity_iss1() -> None:
    from entelechy.foundation.types import ObjectReferent, Polarity

    participants = (ObjectReferent("self:x"),)
    positive = issue_digest("R1", participants, {})
    also_positive = issue_digest("R1", participants, {})
    assert positive == also_positive
    different_relation = issue_digest("R2", participants, {})
    assert different_relation != positive


def test_classify_first_formation_when_issue_has_no_history_iss4() -> None:
    reader = FakeReader()
    assert classify("issue:new", reader) is Classification.FIRST_FORMATION


def test_classify_clone_when_a_current_head_exists_iss4() -> None:
    reader = FakeReader()
    reader.add_infon("infon:1", "issue:a")
    assert classify("issue:a", reader) is Classification.CLONE


def test_classify_reformation_when_history_has_no_current_head_iss4() -> None:
    reader = FakeReader()
    reader.add_infon("infon:1", "issue:a", retired=True)
    assert classify("issue:a", reader) is Classification.RE_FORMATION


def test_classify_reformation_when_the_only_member_is_forgotten_iss4() -> None:
    reader = FakeReader()
    reader.add_infon("infon:1", "issue:a", forgotten=True, retired=True)
    assert classify("issue:a", reader) is Classification.RE_FORMATION


def test_ledger_unions_current_retired_and_forgotten_members_iss7() -> None:
    reader = FakeReader()
    reader.add_infon("infon:1", "issue:a", mode=Mode.TESTIMONY, organ="mind", retired=True)
    reader.add_infon("infon:2", "issue:a", mode=Mode.TESTIMONY, organ="scribe")
    assert ledger("issue:a", reader) == {make_testimony_root("mind"), make_testimony_root("scribe")}


def test_ledger_at_seq_excludes_later_commits_iss7() -> None:
    reader = FakeReader()
    reader.add_infon("infon:1", "issue:a", mode=Mode.TESTIMONY, organ="mind", seq=1)
    reader.add_infon("infon:2", "issue:a", mode=Mode.TESTIMONY, organ="scribe", seq=5)
    assert ledger("issue:a", reader, at_seq=1) == {make_testimony_root("mind")}
    assert ledger("issue:a", reader, at_seq=5) == {make_testimony_root("mind"), make_testimony_root("scribe")}


def test_novel_roots_is_a_set_difference_evd2() -> None:
    inherited = frozenset({make_testimony_root("mind")})
    candidate = frozenset({make_testimony_root("mind"), observation_root("obs:1")})
    assert novel_roots(candidate, inherited) == {observation_root("obs:1")}
    assert new_evidence(candidate, inherited)
    assert not new_evidence(inherited, inherited)


def test_a_root_referenced_twice_is_still_weighed_once_evd6() -> None:
    inherited = frozenset({observation_root("obs:1")})
    candidate = frozenset({observation_root("obs:1")})
    assert novel_roots(candidate, inherited) == frozenset()
