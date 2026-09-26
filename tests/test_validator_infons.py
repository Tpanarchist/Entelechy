from dataclasses import replace
from decimal import Decimal

import pytest
from harness import EYE, MIND, Harness, accepted, infon_from, rejected, form_testimony

from entelechy.foundation.canonical import parse
from entelechy.foundation.types import (
    Consolidate,
    EventType,
    Forget,
    FormInfon,
    InfonBody,
    InfonStatus,
    Mode,
    ObjectReferent,
    ObjectType,
    OpaqueReferent,
    OrganRef,
    OtherOperation,
    Polarity,
    Proposal,
    ReviseInfon,
    Role,
    RoleInput,
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


def test_near_certainty_is_stored_exactly_not_rounded_to_one(heart: Harness) -> None:
    observation = heart.receive()
    nines = Decimal("0." + "9" * 29)
    result = accepted(
        heart.propose(Consolidate(observation), infon_from(observation, confidence=nines))
    )
    (infon,) = [header for header in result.versions if header.type is ObjectType.INFON]
    stored = InfonBody.from_canonical(parse(result.bodies[infon.body_digest]))
    assert stored.confidence == nines


def test_a_confidence_without_canonical_form_is_rejected_not_raised_inf1(heart: Harness) -> None:
    observation = heart.receive()
    infon = infon_from(observation, confidence=Decimal("1E-1000030"))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"INF-1"}


def test_a_relation_outside_the_vocabulary_is_rejected_inf1(heart: Harness) -> None:
    observation = heart.receive()
    infon = infon_from(observation, relation="Color")
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"INF-1"}


def test_an_organ_cannot_use_support_or_counterevidence_at_formation_rol3(heart: Harness) -> None:
    observation = heart.receive()
    for role in (Role.SUPPORT, Role.COUNTEREVIDENCE, Role.REVISION_TARGET):
        infon = replace(infon_from(observation), inputs=(RoleInput(observation, role),))
        assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"ROL-3"}


def test_an_attribution_input_must_be_a_persisted_observation_rol3(heart: Harness) -> None:
    testify = form_testimony(heart.manifest.self_id)
    (witness_id,) = [h.id for h in heart.commit(testify).versions]
    observation = heart.receive()
    infon = replace(
        infon_from(observation),
        inputs=(
            RoleInput(observation, Role.DERIVATION_INPUT),
            RoleInput(witness_id, Role.ATTRIBUTION),
        ),
    )
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"ROL-3"}


def test_no_inputs_is_testimony_mode_org3(heart: Harness) -> None:
    infon = form_testimony(heart.manifest.self_id)
    result = accepted(heart.propose(infon))
    assert result.provenance[0].organ == MIND
    assert result.provenance[0].mode is Mode.TESTIMONY


def test_a_derivation_input_makes_derivation_mode(heart: Harness) -> None:
    observation = heart.receive()
    result = accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    (infon_header,) = [h for h in result.versions if h.type is ObjectType.INFON]
    assert result.provenance[-1].mode is Mode.DERIVATION


def test_only_attribution_inputs_makes_attributed_mode_org4(heart: Harness) -> None:
    utterance = heart.receive(content="hello")
    infon = FormInfon(
        relation="R2",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        inputs=(RoleInput(utterance, Role.ATTRIBUTION),),
    )
    result = accepted(heart.propose(Consolidate(utterance), infon))
    assert result.provenance[-1].mode is Mode.ATTRIBUTED


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
        ("FORM_INFON", "TRN-2"),
        ("CONSOLIDATE", "TRN-2"),
        ("DREAM", "TRN-1"),
    ],
)
def test_operations_outside_v1_are_rejected_by_name(heart: Harness, name: str, rule: str) -> None:
    assert rejected(heart.propose(OtherOperation(name))).rules == {rule}


def test_a_revision_of_an_unknown_infon_is_rejected_trn3(heart: Harness) -> None:
    placeholder = InfonBody("R1", (), Polarity.POSITIVE, {}, Decimal("0.6"), InfonStatus.ACTIVE)
    result = rejected(heart.propose(ReviseInfon("infon:ghost", 1, placeholder, ())))
    assert result.rules == {"TRN-3"}


def test_forgetting_an_unknown_object_is_rejected_trn3(heart: Harness) -> None:
    result = rejected(heart.propose(Forget("infon:ghost", 1, "gone already")))
    assert result.rules == {"TRN-3"}


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


# Issues (ISS) and evidence accounting (EVD), FOUNDATIONS §8.14.


def test_first_formation_from_testimony_is_allowed_unconditionally_iss4(heart: Harness) -> None:
    """First formation is allowed whether or not it is rootless (ISS-4); this
    exercises the grounded case (organ testimony). The rootless case (an
    attributed-only formation) is case 24 in tests/test_conformance.py."""
    infon = form_testimony(heart.manifest.self_id)
    result = accepted(heart.propose(infon))
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["classification"] == "first_formation"


def test_cloning_an_issue_with_a_current_head_is_refused_iss4(heart: Harness) -> None:
    infon = form_testimony(heart.manifest.self_id)
    heart.commit(infon)
    clone = replace(infon, confidence=Decimal("0.7"))
    assert rejected(heart.propose(clone)).rules == {"ISS-4"}


def test_two_different_issues_may_each_form_org3(heart: Harness) -> None:
    first = form_testimony(heart.manifest.self_id, relation="R1")
    second = form_testimony(heart.manifest.self_id, relation="R2")
    result = heart.commit(first, second)
    assert len(result.versions) == 2


def _retire(heart: Harness, infon_id: str) -> None:
    """Administratively retire an Infon (EVD-5): its issue keeps history but no current head."""
    header = heart.store.latest(infon_id)
    assert header is not None
    data = heart.store.content(header.body_digest)
    assert data is not None
    body = replace(InfonBody.from_canonical(parse(data)), status=InfonStatus.RETIRED)
    heart.commit(ReviseInfon(infon_id, header.version, body, ()))


def test_reformation_without_new_evidence_is_refused_iss4(heart: Harness) -> None:
    infon = form_testimony(heart.manifest.self_id)
    (infon_id,) = [h.id for h in heart.commit(infon).versions]
    _retire(heart, infon_id)
    # Retired: the issue has history but no current head. The same organ's
    # form_testimony carries no new root, since TestimonyRoot(MIND) is already
    # in the issue's ledger.
    assert rejected(heart.propose(infon)).rules == {"ISS-4"}


def test_reformation_with_new_evidence_is_allowed_iss4(heart: Harness) -> None:
    infon = form_testimony(heart.manifest.self_id, relation="R2")
    (infon_id,) = [h.id for h in heart.commit(infon).versions]
    _retire(heart, infon_id)

    evidence = heart.receive()
    reformed = FormInfon(
        relation="R2",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        inputs=(RoleInput(evidence, Role.DERIVATION_INPUT),),
    )
    result = heart.commit(Consolidate(evidence), reformed)
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["classification"] == "re_formation"
    assert check.measured["novel"]


def test_a_mind_cannot_fabricate_another_organs_testimony_root_law8_rot2(heart: Harness) -> None:
    """Law 8 / ROT-2: a Mind can cause its own capability-bound testimony to
    be admitted, but has no field through which to claim another organ's
    identity. TestimonyRoot always names the port that proposed, never
    payload the organ supplied."""
    infon = form_testimony(heart.manifest.self_id)
    result = heart.commit(infon)
    assert result.provenance[0].organ == MIND
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["candidate"] == [{"kind": "testimony", "key": "mind"}]
    # FormInfon has no field naming a source organ at all: mode and its root
    # are derived entirely from the roles of `inputs` and the proposing
    # port (PRV-8), never from anything the proposal itself can spell out.
    assert not hasattr(infon, "organ") and not hasattr(infon, "source")


def test_a_real_root_need_not_be_relevant_evidence_at_formation(heart: Harness) -> None:
    """E001 guarantees a root is real (it came through a capability-bound
    port); it does not, and by design cannot, judge whether that evidence is
    actually probative of the claim it is cited for (ROL-5). An Observation
    about anything at all still grounds a `derivation_input` at formation.
    The relevance boundary reached by relabeling a role at revision time is
    case 25 in tests/test_conformance.py."""
    weather = heart.receive(content={"topic": "weather", "reading": "sunny"})
    unrelated_claim = FormInfon(
        relation="R1",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        inputs=(RoleInput(weather, Role.DERIVATION_INPUT),),
    )
    result = accepted(heart.propose(Consolidate(weather), unrelated_claim))
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["novel"] == [{"kind": "observation", "key": weather}]
