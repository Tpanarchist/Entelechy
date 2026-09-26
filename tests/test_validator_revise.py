from dataclasses import replace
from decimal import Decimal

import pytest
from harness import Harness, infon_body, infon_from, rejected, form_testimony

from entelechy.foundation.types import (
    Consolidate,
    EventType,
    InfonStatus,
    Mode,
    ObjectRef,
    RegionReferent,
    ReviseInfon,
    Role,
    RoleInput,
)
from entelechy.foundation.validator import CERTAINTY


@pytest.fixture
def formed(heart: Harness) -> tuple[str, str]:
    """A committed Observation and the Infon that cites it."""
    return heart.lifecycle()


def _support(object_id: str) -> tuple[RoleInput, ...]:
    return (RoleInput(object_id, Role.SUPPORT),)


def _counterevidence(object_id: str) -> tuple[RoleInput, ...]:
    return (RoleInput(object_id, Role.COUNTEREVIDENCE),)


def test_revising_confidence_upward_needs_a_novel_support_root_rol4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    result = heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence))
    )
    header = heart.store.latest(infon_id)
    assert header is not None and header.version == 2 and header.id == infon_id
    assert infon_body(heart.store, infon_id).confidence == Decimal("0.9")
    assert result.prior == (ObjectRef(infon_id, 1),)
    assert [e.type for e in result.events][-1] is EventType.INFON_REVISED


def test_revising_confidence_upward_with_counterevidence_only_is_refused_rol4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _counterevidence(evidence)))
    )
    assert result.rules == {"ROL-4"}


def test_revising_confidence_downward_needs_a_novel_counterevidence_root_rol4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.5"))
    result = heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, _counterevidence(evidence))
    )
    assert infon_body(heart.store, infon_id).confidence == Decimal("0.5")


def test_revising_confidence_downward_with_support_only_is_refused_rol4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.5"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert result.rules == {"ROL-4"}


def test_moving_both_ways_at_once_is_refused_rol4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(
        infon_body(heart.store, infon_id),
        confidence=Decimal("0.9"),
        status=InfonStatus.CONTRADICTED,
    )
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert result.rules == {"ROL-4"}


def test_changing_the_relation_requires_a_successor_inf4_obj4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), relation="R2")
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert result.rules == {"INF-4", "OBJ-4"}
    assert result.violations[0].measured["changed"] == ["relation"]


def test_a_revision_must_change_something_inf4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert result.rules == {"INF-4"}


def test_a_trust_change_needs_evidence_evd4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    assert rejected(heart.propose(ReviseInfon(infon_id, 1, body, ()))).rules == {"EVD-4"}


def test_a_trust_change_needs_new_evidence_not_already_cited(
    heart: Harness, formed: tuple[str, str]
) -> None:
    observation, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    # `observation` already grounds this Infon (it is its derivation_input);
    # its root is already in the issue's ledger, so citing it again is not new.
    result = rejected(heart.propose(ReviseInfon(infon_id, 1, body, _support(observation))))
    assert result.rules == {"EVD-4"}


def test_a_stale_version_is_rejected_per6(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 7, body, _support(evidence)))
    )
    assert result.rules == {"PER-6"}
    assert result.violations[0].measured == {"expected": 7, "current": 1}


def test_observations_are_never_edited_obs1(heart: Harness, formed: tuple[str, str]) -> None:
    observation, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(observation, 1, body, _support(evidence)))
    )
    assert result.rules == {"OBS-1"}


def test_the_self_reference_is_not_an_infon_trn1(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    self_id = heart.manifest.self_id
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(self_id, 1, body, _support(evidence)))
    )
    assert result.rules == {"TRN-1"}


def test_retired_infons_are_final_obj3(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = heart.commit(ReviseInfon(infon_id, 1, retired, ()))
    header = heart.store.latest(infon_id)
    assert header is not None and header.retired_by == result.seq
    revived = replace(retired, status=InfonStatus.ACTIVE)
    outcome = rejected(heart.propose(ReviseInfon(infon_id, 2, revived, ())))
    assert outcome.rules == {"OBJ-3"}


def test_a_revision_derives_from_the_version_it_revises(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    revision = result.provenance[-1]
    assert revision.mode is Mode.REVISION
    assert revision.inputs[0].role is Role.REVISION_TARGET
    assert revision.inputs[0].ref == ObjectRef(infon_id, 1)
    assert any(item.ref == ObjectRef(evidence, 1) and item.role is Role.SUPPORT for item in revision.inputs)


def test_citing_only_the_target_itself_carries_no_novel_root_evd4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    """§4.3 replaces E000's special-cased self-citation check entirely: there
    is no rule against citing the target (or any Infon on the same issue) as
    evidence. It is refused only because its root is already in the issue's
    ledger, so it can never be novel (EVD-4) — the general novelty math, not
    a special case."""
    _, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    result = rejected(heart.propose(ReviseInfon(infon_id, 1, body, _support(infon_id))))
    assert result.rules == {"EVD-4"}


def test_citing_the_target_alongside_genuinely_new_evidence_is_accepted(
    heart: Harness, formed: tuple[str, str]
) -> None:
    """The mixed case §4.3 exists to allow: citing the target contributes
    nothing, but the proposal also carries a genuinely novel root, and
    NovelRoots is a set union — one novel member is enough."""
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    result = heart.commit(
        Consolidate(evidence),
        ReviseInfon(infon_id, 1, body, (RoleInput(infon_id, Role.SUPPORT), *_support(evidence))),
    )
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["novel"] == [{"kind": "observation", "key": evidence}]


def test_administratively_revising_the_witness_creates_no_new_root(
    heart: Harness, formed: tuple[str, str]
) -> None:
    """Novelty tracks roots, not object identity or version (ROT-5, EVD-6). An
    administrative change admits no roots (EVD-5), so retiring the witness
    leaves its roots exactly as they were: citing it again still grounds
    nothing new."""
    _, infon_id = formed
    witness = form_testimony(heart.manifest.self_id, relation="R2")
    (witness_id,) = [h.id for h in heart.commit(witness).versions]
    lowered = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    heart.commit(ReviseInfon(infon_id, 1, lowered, _counterevidence(witness_id)))

    retired = replace(infon_body(heart.store, witness_id), status=InfonStatus.RETIRED)
    heart.commit(ReviseInfon(witness_id, 1, retired, ()))

    again = replace(lowered, confidence=Decimal("0.5"))
    stale = rejected(heart.propose(ReviseInfon(infon_id, 2, again, _counterevidence(witness_id))))
    assert stale.rules == {"EVD-4"}


def test_new_grounding_reaches_through_a_revised_witness(
    heart: Harness, formed: tuple[str, str]
) -> None:
    """A root admitted into the witness's own issue by its later revision
    becomes part of the witness's roots (Law 9), so citing the witness again
    can ground a fresh revision even though the witness object id is the same."""
    _, infon_id = formed
    witness = form_testimony(heart.manifest.self_id, relation="R2")
    (witness_id,) = [h.id for h in heart.commit(witness).versions]
    lowered = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    heart.commit(ReviseInfon(infon_id, 1, lowered, _counterevidence(witness_id)))

    new_observation = heart.receive()
    firmer = replace(infon_body(heart.store, witness_id), confidence=Decimal("0.7"))
    heart.commit(
        Consolidate(new_observation), ReviseInfon(witness_id, 1, firmer, _support(new_observation))
    )

    again = replace(lowered, confidence=Decimal("0.5"))
    result = heart.commit(ReviseInfon(infon_id, 2, again, _counterevidence(witness_id)))
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["novel"]


def test_the_justification_names_only_what_changed_per7(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), status=InfonStatus.CONTRADICTED)
    result = heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, _counterevidence(evidence))
    )
    revision_checks = [check for check in result.justification if check.operation == 1]
    inf4 = next(c for c in revision_checks if c.rule == "INF-4")
    assert inf4.measured == {"changed": ["status"]}


def test_evidence_cited_by_any_earlier_version_is_not_new(
    heart: Harness, formed: tuple[str, str]
) -> None:
    observation, infon_id = formed
    evidence = heart.receive()
    lowered = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.4"))
    heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, lowered, _counterevidence(evidence)))
    # Version 1 already grounded the issue with `observation`'s root; citing
    # it again is not new.
    raised = replace(lowered, confidence=Decimal("0.9"))
    result = rejected(heart.propose(ReviseInfon(infon_id, 2, raised, _support(observation))))
    assert result.rules == {"EVD-4"}


def test_true_is_different_content_from_one_inf4(heart: Harness) -> None:
    observation = heart.receive()
    form = replace(infon_from(observation), context={"scope": 1})
    result = heart.commit(Consolidate(observation), form)
    (infon_id,) = [h.id for h in result.versions if h.id != observation]
    evidence = heart.receive()
    body = replace(
        infon_body(heart.store, infon_id), context={"scope": True}, confidence=Decimal("0.9")
    )
    outcome = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert outcome.rules == {"INF-4", "OBJ-4"}
    assert outcome.violations[0].measured == {"changed": ["context"]}


def test_a_region_of_true_is_not_a_region_of_one_inf4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    observation, infon_id = formed
    evidence = heart.receive()
    body = replace(
        infon_body(heart.store, infon_id),
        participants=(RegionReferent(observation, {"x": True}),),
        confidence=Decimal("0.9"),
    )
    outcome = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert outcome.violations[0].measured == {"changed": ["participants"]}


def test_a_non_canonical_revised_body_is_rejected_not_raised_inf1(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    context: dict[str, object] = {"x": 1.0}
    body = replace(
        infon_body(heart.store, infon_id),
        context=context,  # type: ignore[arg-type]
        confidence=Decimal("0.9"),
    )
    outcome = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert outcome.rules == {"INF-1"}


def test_a_signalling_nan_confidence_is_rejected_not_raised(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("sNaN"))
    outcome = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert outcome.rules == {CERTAINTY}


def test_revised_confidence_obeys_v1_certainty(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, _support(evidence)))
    )
    assert result.rules == {CERTAINTY}


# Administrative retirement (EVD-5).


def test_administrative_retirement_needs_no_evidence_evd5(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = heart.commit(ReviseInfon(infon_id, 1, retired, ()))
    check = next(c for c in result.justification if c.rule == "EVD-7")
    assert check.measured["classification"] == "administrative"
    assert check.measured["novel"] == []


def test_administrative_retirement_must_not_admit_support_evd5(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, retired, _support(evidence)))
    )
    assert result.rules == {"EVD-5"}


def test_administrative_retirement_must_not_admit_counterevidence_evd5(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = rejected(
        heart.propose(
            Consolidate(evidence), ReviseInfon(infon_id, 1, retired, _counterevidence(evidence))
        )
    )
    assert result.rules == {"EVD-5"}


def test_administrative_retirement_may_carry_attribution(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    utterance = heart.receive(content="retiring this")
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = heart.commit(
        Consolidate(utterance),
        ReviseInfon(infon_id, 1, retired, (RoleInput(utterance, Role.ATTRIBUTION),)),
    )
    header = heart.store.latest(infon_id)
    assert header is not None and header.retired_by == result.seq


def test_revising_an_organ_cannot_use_derivation_input_or_revision_target_rol3(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    for role in (Role.DERIVATION_INPUT, Role.REVISION_TARGET):
        result = rejected(
            heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (RoleInput(evidence, role),)))
        )
        assert result.rules == {"ROL-3"}
