from dataclasses import replace
from decimal import Decimal

import pytest
from harness import EYE, MIND, Harness, accepted, infon_from, rejected

from entelechy.foundation.types import (
    Consolidate,
    EventType,
    FormInfon,
    ObjectReferent,
    OpaqueReferent,
    OrganRef,
    OtherOperation,
    Polarity,
    Proposal,
    ProvenanceKind,
)
from entelechy.foundation.validator import (
    CERTAINTY,
    UNIMPLEMENTED,
    AcceptedTransition,
)


def test_first_lifecycle_is_one_transition_mem1(heart: Harness) -> None:
    observation = heart.receive()
    result = accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    assert [event.type for event in result.events] == [
        EventType.MEMORY_CONSOLIDATED,
        EventType.INFON_FORMED,
    ]
    assert result.justification[0].rule == "MEM-1"
    assert result.justification[0].measured["clause"] == "evidence"
    assert {header.id for header in result.versions} >= {observation}


def test_the_justification_is_written_by_the_validator_per7(heart: Harness) -> None:
    observation = heart.receive()
    result = accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    assert {check.rule for check in result.justification} >= {"MEM-1", "INF-1", "PRV-4", CERTAINTY}


def test_only_the_validator_can_accept_a_transition_law5() -> None:
    with pytest.raises(PermissionError, match="Law 5"):
        AcceptedTransition(
            seq=1,
            proposal=Proposal(MIND, ()),
            operations=(),
            prior=(),
            provenance=(),
            versions=(),
            events=(),
            justification=(),
            bodies={},
            capability=object(),
        )


def test_an_unregistered_organ_is_rejected_org2(heart: Harness) -> None:
    observation = heart.receive()
    stranger = OrganRef("stranger", "1")
    result = rejected(heart.propose(Consolidate(observation), organ=stranger))
    assert result.rules == {"ORG-2"}


def test_a_channel_cannot_propose_org2(heart: Harness) -> None:
    observation = heart.receive()
    assert rejected(heart.propose(Consolidate(observation), organ=EYE)).rules == {"ORG-2"}


def test_an_empty_proposal_is_rejected_per6(heart: Harness) -> None:
    assert rejected(heart.propose()).rules == {"PER-6"}


def test_an_infon_citing_a_transient_observation_is_rejected_prv4(heart: Harness) -> None:
    observation = heart.receive()
    result = rejected(heart.propose(infon_from(observation)))
    assert "PRV-4" in result.rules
    assert any("is transient" in violation.explanation for violation in result.violations)


def test_standalone_consolidate_needs_a_bound_retention_clause_mem1(heart: Harness) -> None:
    observation = heart.receive()
    result = rejected(heart.propose(Consolidate(observation)))
    assert result.rules == {"MEM-1"}
    assert result.violations[0].measured == {
        "theta_retain": "unbound",
        "retention_policy": "unbound",
    }


def test_standalone_consolidate_succeeds_under_a_policy_mem1(policy_heart: Harness) -> None:
    observation = policy_heart.receive()
    result = accepted(policy_heart.propose(Consolidate(observation)))
    assert result.justification[0].measured["clause"] == "retention"


def test_consolidating_twice_is_rejected_per3(heart: Harness) -> None:
    observation = heart.receive()
    result = rejected(
        heart.propose(Consolidate(observation), Consolidate(observation), infon_from(observation))
    )
    assert result.operation == 1
    assert result.rules == {"PER-3"}


def test_an_unknown_observation_is_rejected_per3(heart: Harness) -> None:
    assert rejected(heart.propose(Consolidate("obs:nowhere"))).rules == {"PER-3"}


def test_negative_infons_are_unimplemented(heart: Harness) -> None:
    observation = heart.receive()
    negative = replace(infon_from(observation), polarity=Polarity.NEGATIVE)
    result = rejected(heart.propose(Consolidate(observation), negative))
    assert result.rules == {UNIMPLEMENTED}


@pytest.mark.parametrize("confidence", ["0", "1", "1.00", "-0.1", "1.5", "NaN"])
def test_certainty_is_out_of_reach_in_v1(heart: Harness, confidence: str) -> None:
    observation = heart.receive()
    infon = infon_from(observation, confidence=Decimal(confidence))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {CERTAINTY}


def test_a_relation_outside_the_vocabulary_is_rejected_inf1(heart: Harness) -> None:
    observation = heart.receive()
    infon = infon_from(observation, relation="Color")
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"INF-1"}


def test_learned_structure_cannot_claim_origin_prv5(heart: Harness) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), provenance_kind=ProvenanceKind.ORIGIN)
    assert "PRV-5" in rejected(heart.propose(Consolidate(observation), infon)).rules


@pytest.mark.parametrize("kind", [ProvenanceKind.EXPERIMENT, ProvenanceKind.SIMULATION])
def test_experiment_and_simulation_provenance_are_unimplemented(
    heart: Harness, kind: ProvenanceKind
) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), provenance_kind=kind)
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {UNIMPLEMENTED}


def test_observation_provenance_must_cite_an_observation_prv1(heart: Harness) -> None:
    infon = FormInfon(
        relation="R1",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.OBSERVATION,
        inputs=(heart.manifest.self_id,),
    )
    assert rejected(heart.propose(infon)).rules == {"PRV-1"}


def test_derivation_must_reference_inputs_prv3(heart: Harness) -> None:
    infon = FormInfon(
        relation="R1",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.DERIVATION,
        inputs=(),
    )
    assert rejected(heart.propose(infon)).rules == {"PRV-3"}


def test_testimony_from_an_organ_needs_no_inputs_org3(heart: Harness) -> None:
    infon = FormInfon(
        relation="R2",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.TESTIMONY,
        inputs=(),
    )
    result = accepted(heart.propose(infon))
    assert result.provenance[0].organ == MIND


def test_opaque_identifiers_must_come_from_the_observation_ref1(heart: Harness) -> None:
    observation = heart.receive(identifiers=("track-7",))
    unknown = replace(
        infon_from(observation), participants=(OpaqueReferent(observation, "track-9"),)
    )
    assert rejected(heart.propose(Consolidate(observation), unknown)).rules == {"REF-1"}
    known = replace(
        infon_from(observation), participants=(OpaqueReferent(observation, "track-7"),)
    )
    accepted(heart.propose(Consolidate(observation), known))


def test_a_participant_that_does_not_exist_is_rejected_ref1(heart: Harness) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), participants=(ObjectReferent("infon:ghost"),))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"REF-1"}


def test_a_missing_predecessor_is_rejected_obj4(heart: Harness) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), derived_from=("infon:ghost",))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"OBJ-4"}


def test_context_must_be_canonical_inf1(heart: Harness) -> None:
    observation = heart.receive()
    context: dict[str, object] = {"weight": 0.5}
    infon = replace(infon_from(observation), context=context)  # type: ignore[arg-type]
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"INF-1"}


@pytest.mark.parametrize(
    ("name", "rule"),
    [
        ("PROPOSE_MODEL", UNIMPLEMENTED),
        ("RECORD_RESOURCE_THRESHOLD", UNIMPLEMENTED),
        ("FORM_INFON", "TRN-1"),
        ("DREAM", "TRN-1"),
    ],
)
def test_operations_outside_v1_are_rejected_by_name(heart: Harness, name: str, rule: str) -> None:
    assert rejected(heart.propose(OtherOperation(name))).rules == {rule}


def test_rejections_read_as_rules_and_reasons(heart: Harness) -> None:
    observation = heart.receive()
    text = str(rejected(heart.propose(infon_from(observation))))
    assert text.startswith("REJECTED")
    assert f"PRV-4  provenance input {observation} is transient" in text


def test_validation_does_not_touch_the_store(heart: Harness) -> None:
    observation = heart.receive()
    before = heart.store.versions()
    accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    assert heart.store.versions() == before
    assert heart.store.transitions() == []
