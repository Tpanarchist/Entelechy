from dataclasses import replace
from decimal import Decimal

import pytest
from harness import Harness, infon_body, rejected

from entelechy.foundation.types import (
    Consolidate,
    EventType,
    FormInfon,
    InfonStatus,
    ObjectRef,
    ObjectReferent,
    ProvenanceKind,
    ReviseInfon,
)
from entelechy.foundation.validator import CERTAINTY, REVISE_REQUIRES


@pytest.fixture
def formed(heart: Harness) -> tuple[str, str]:
    """A committed Observation and the Infon that cites it."""
    return heart.lifecycle()


def test_revising_confidence_keeps_identity_obj4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    header = heart.store.latest(infon_id)
    assert header is not None and header.version == 2 and header.id == infon_id
    assert infon_body(heart.store, infon_id).confidence == Decimal("0.6")
    assert result.prior == (ObjectRef(infon_id, 1),)
    assert [e.type for e in result.events][-1] is EventType.INFON_REVISED


def test_changing_the_relation_requires_a_successor_inf4_obj4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), relation="R2")
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    )
    assert result.rules == {"INF-4", "OBJ-4"}
    assert result.violations[0].measured["changed"] == ["relation"]


def test_a_revision_must_change_something_inf4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    )
    assert result.rules == {"INF-4"}


def test_a_revision_needs_evidence(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    assert rejected(heart.propose(ReviseInfon(infon_id, 1, body, ()))).rules == {REVISE_REQUIRES}


def test_a_revision_needs_new_evidence(heart: Harness, formed: tuple[str, str]) -> None:
    observation, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = rejected(heart.propose(ReviseInfon(infon_id, 1, body, (observation,))))
    assert result.rules == {REVISE_REQUIRES}


def test_a_stale_version_is_rejected_per6(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 7, body, (evidence,)))
    )
    assert result.rules == {"PER-6"}
    assert result.violations[0].measured == {"expected": 7, "current": 1}


def test_observations_are_never_edited_obs1(heart: Harness, formed: tuple[str, str]) -> None:
    observation, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(observation, 1, body, (evidence,)))
    )
    assert result.rules == {"OBS-1"}


def test_the_self_reference_is_not_an_infon_trn1(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    self_id = heart.manifest.self_id
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(self_id, 1, body, (evidence,)))
    )
    assert result.rules == {"TRN-1"}


def test_retired_infons_are_final_obj3(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    first, second = heart.receive(), heart.receive()
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = heart.commit(Consolidate(first), ReviseInfon(infon_id, 1, retired, (first,)))
    header = heart.store.latest(infon_id)
    assert header is not None and header.retired_by == result.seq
    revived = replace(retired, status=InfonStatus.ACTIVE)
    outcome = rejected(
        heart.propose(Consolidate(second), ReviseInfon(infon_id, 2, revived, (second,)))
    )
    assert outcome.rules == {"OBJ-3"}


def test_a_revision_derives_from_the_version_it_revises(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    revision = result.provenance[-1]
    assert revision.kind is ProvenanceKind.DERIVATION
    assert revision.inputs == (ObjectRef(infon_id, 1), ObjectRef(evidence, 1))


def test_an_infon_is_not_evidence_for_its_own_revision(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = rejected(heart.propose(ReviseInfon(infon_id, 1, body, (infon_id,))))
    assert result.rules == {REVISE_REQUIRES}


def test_a_newer_version_of_cited_evidence_is_new_evidence(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    witness = FormInfon(
        relation="R2",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.TESTIMONY,
        inputs=(),
    )
    (witness_id,) = [h.id for h in heart.commit(witness).versions]
    lowered = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    heart.commit(ReviseInfon(infon_id, 1, lowered, (witness_id,)))
    again = replace(lowered, confidence=Decimal("0.5"))
    # The witness at version 1 is already cited.
    stale = rejected(heart.propose(ReviseInfon(infon_id, 2, again, (witness_id,))))
    assert stale.rules == {REVISE_REQUIRES}
    # Once the witness is revised, its version 2 is new evidence.
    evidence = heart.receive()
    firmer = replace(infon_body(heart.store, witness_id), confidence=Decimal("0.7"))
    heart.commit(Consolidate(evidence), ReviseInfon(witness_id, 1, firmer, (evidence,)))
    result = heart.commit(ReviseInfon(infon_id, 2, again, (witness_id,)))
    assert result.justification[1].measured["new_evidence"] == [{"id": witness_id, "version": 2}]


def test_the_justification_names_only_what_changed_per7(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), status=InfonStatus.CONTRADICTED)
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    revision_checks = [check for check in result.justification if check.operation == 1]
    assert revision_checks[0].rule == "INF-4"
    assert revision_checks[0].measured == {"changed": ["status"]}


def test_revised_confidence_obeys_v1_certainty(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    )
    assert result.rules == {CERTAINTY}
