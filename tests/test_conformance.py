"""Conformance cases 1-33.

Source: docs/superpowers/specs/2026-09-26-e001-evidence-integrity-spec.md §7.
Each test follows the spec's table row directly: the initial state, the
proposal, the verdict, and — wherever the table gives one — the exact
novel-root set and the issue's ledger afterward. Checking the root sets
themselves, not just accept/reject, is what makes a mutant (a wrong root
computed, a rule left unchecked, an off-by-one in novelty) fail the test
rather than slip through on a lucky verdict.
"""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from harness import EYE, FIXED, MIND, FixedRetention, Harness, accepted, infon_body, rejected, tamper

from entelechy.foundation.canonical import Json, canonical_bytes, digest, parse
from entelechy.foundation.evidence import observation_root
from entelechy.foundation.evidence import testimony_root as make_testimony_root
from entelechy.foundation.kernel import Accepted as KernelAccepted
from entelechy.foundation.kernel import Kernel
from entelechy.foundation.replay import HeartView, IntegrityError, replay_current
from entelechy.foundation.seed import SeedSpec
from entelechy.foundation.store import Store
from entelechy.foundation.types import (
    Consolidate,
    Forget,
    FormInfon,
    InfonBody,
    InfonStatus,
    Mode,
    ObjectReferent,
    OrganRef,
    Polarity,
    ReviseInfon,
    Role,
    RoleInput,
)
from entelechy.foundation.validator import CERTAINTY

# --- helpers -------------------------------------------------------------


def _support(object_id: str) -> RoleInput:
    return RoleInput(object_id, Role.SUPPORT)


def _counterevidence(object_id: str) -> RoleInput:
    return RoleInput(object_id, Role.COUNTEREVIDENCE)


def _derivation(object_id: str) -> RoleInput:
    return RoleInput(object_id, Role.DERIVATION_INPUT)


def _attribution(object_id: str) -> RoleInput:
    return RoleInput(object_id, Role.ATTRIBUTION)


def _claim(
    self_id: str,
    *inputs: RoleInput,
    tag: str,
    relation: str = "R1",
    confidence: Decimal = Decimal("0.6"),
    context: dict[str, Json] | None = None,
) -> FormInfon:
    """A first-formation FormInfon on a fresh issue, distinguished by `tag`.

    ClaimKey is (relation, participants, context) (ISS-1); holding relation
    and participants constant and varying `tag` in context is enough to mint
    as many distinct issues as a case needs.
    """
    body: dict[str, Json] = {"case": tag}
    if context:
        body.update(context)
    return FormInfon(
        relation=relation,
        participants=(ObjectReferent(self_id),),
        confidence=confidence,
        inputs=inputs,
        context=body,
    )


def _revise(
    policy_heart: Harness,
    infon_id: str,
    *,
    confidence: Decimal | None = None,
    status: InfonStatus | None = None,
    evidence: tuple[RoleInput, ...] = (),
) -> ReviseInfon:
    header = policy_heart.store.latest(infon_id)
    assert header is not None
    body = infon_body(policy_heart.store, infon_id)
    if confidence is not None:
        body = replace(body, confidence=confidence)
    if status is not None:
        body = replace(body, status=status)
    return ReviseInfon(infon_id, header.version, body, evidence)


def _form(policy_heart: Harness, *operations: object) -> str:
    """Commit a proposal ending in a formation; return the formed object's id."""
    result = policy_heart.commit(*operations)  # type: ignore[arg-type]
    return result.operations[-1].object_id


def _novel(result: object) -> set[tuple[str, str]]:
    justification = result.justification  # type: ignore[attr-defined]
    check = next(c for c in justification if c.rule == "EVD-7")
    return {(item["kind"], item["key"]) for item in check.measured["novel"]}


def _candidate(result: object) -> set[tuple[str, str]]:
    justification = result.justification  # type: ignore[attr-defined]
    check = next(c for c in justification if c.rule == "EVD-7")
    return {(item["kind"], item["key"]) for item in check.measured["candidate"]}


def _classification(result: object) -> str:
    justification = result.justification  # type: ignore[attr-defined]
    check = next(c for c in justification if c.rule == "EVD-7")
    value = check.measured["classification"]
    assert isinstance(value, str)
    return value


# --- cases 1-12: novelty is counted by root, in an issue's ledger --------


def test_case1_support_partly_grounded_in_a_shared_root_is_partly_novel(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1, o2 = policy_heart.receive(), policy_heart.receive()
    policy_heart.commit(Consolidate(o1), Consolidate(o2))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case1-I"))
    j_id = _form(policy_heart, _claim(self_id, _derivation(o1), _derivation(o2), tag="case1-J"))
    result = policy_heart.commit(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(j_id),)))
    assert _novel(result) == {("observation", o2)}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o2)}


def test_case2_deriving_from_the_same_root_grounds_nothing_new(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    a_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case2-A"))
    b_id = _form(policy_heart, _claim(self_id, _derivation(a_id), tag="case2-B"))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, a_id, confidence=Decimal("0.7"), evidence=(_support(b_id),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(a_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1)}


def test_case3_two_testimonies_by_the_same_organ_share_one_root(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    a_id = _form(policy_heart, _claim(self_id, tag="case3-A"))
    j_id = _form(policy_heart, _claim(self_id, tag="case3-J"))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, a_id, confidence=Decimal("0.7"), evidence=(_support(j_id),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(a_id)
    assert issue is not None
    assert view.ledger(issue) == {make_testimony_root("mind")}


def test_case4_a_root_already_weighed_cannot_ground_a_second_downward_move(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1, o2 = policy_heart.receive(), policy_heart.receive()
    policy_heart.commit(Consolidate(o1), Consolidate(o2))
    a_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case4-A"))
    policy_heart.commit(_revise(policy_heart, a_id, confidence=Decimal("0.4"), evidence=(_counterevidence(o2),)))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, a_id, confidence=Decimal("0.3"), evidence=(_counterevidence(o2),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(a_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o2)}


def test_case5_a_root_already_weighed_cannot_ground_the_opposite_move_either(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1, o2 = policy_heart.receive(), policy_heart.receive()
    policy_heart.commit(Consolidate(o1), Consolidate(o2))
    a_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case5-A"))
    policy_heart.commit(_revise(policy_heart, a_id, confidence=Decimal("0.4"), evidence=(_counterevidence(o2),)))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, a_id, confidence=Decimal("0.9"), evidence=(_support(o2),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(a_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o2)}


def test_case6_reverting_to_an_already_weighed_root_grounds_nothing(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case6-I"))
    e = policy_heart.receive()
    policy_heart.commit(Consolidate(e))
    policy_heart.commit(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(e),)))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, i_id, confidence=Decimal("0.8"), evidence=(_support(o1),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(e)}


def test_case7_a_paraphrase_by_the_same_organ_is_still_the_same_root(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    c_id = _form(policy_heart, _claim(self_id, tag="case7-C"))
    paraphrase_id = _form(policy_heart, _claim(self_id, tag="case7-C-paraphrase"))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, c_id, confidence=Decimal("0.7"), evidence=(_support(paraphrase_id),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(c_id)
    assert issue is not None
    assert view.ledger(issue) == {make_testimony_root("mind")}


def test_case8_a_second_hearing_recorded_honestly_as_attribution_grounds_nothing(
    policy_heart: Harness,
) -> None:
    self_id = policy_heart.manifest.self_id
    u1 = policy_heart.receive(content="hearing 1")
    policy_heart.commit(Consolidate(u1))
    x_id = _form(policy_heart, _claim(self_id, _attribution(u1), tag="case8-X"))
    u2 = policy_heart.receive(content="hearing 2")
    policy_heart.commit(Consolidate(u2))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, x_id, confidence=Decimal("0.7"), evidence=(_attribution(u2),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(x_id)
    assert issue is not None
    assert view.ledger(issue) == frozenset()


def test_case9_citing_attributed_infons_as_support_still_grounds_nothing(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    c_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case9-C"))
    speakers = [policy_heart.receive(content=f"speaker-{i}") for i in range(3)]
    policy_heart.commit(*(Consolidate(u) for u in speakers))
    attributed_ids = [
        _form(policy_heart, _claim(self_id, _attribution(u), tag=f"case9-speaker-{i}"))
        for i, u in enumerate(speakers)
    ]
    result = rejected(
        policy_heart.propose(
            _revise(
                policy_heart, c_id, confidence=Decimal("0.7"), evidence=tuple(_support(a) for a in attributed_ids)
            )
        )
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(c_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1)}


def test_case10_novelty_flows_back_and_forth_until_both_ledgers_converge(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o_a, o_b = policy_heart.receive(), policy_heart.receive()
    policy_heart.commit(Consolidate(o_a), Consolidate(o_b))
    a_id = _form(policy_heart, _claim(self_id, _derivation(o_a), tag="case10-A"))
    b_id = _form(policy_heart, _claim(self_id, _derivation(o_b), tag="case10-B"))

    step1 = policy_heart.commit(_revise(policy_heart, a_id, confidence=Decimal("0.7"), evidence=(_support(b_id),)))
    assert _novel(step1) == {("observation", o_b)}

    step2 = policy_heart.commit(_revise(policy_heart, b_id, confidence=Decimal("0.7"), evidence=(_support(a_id),)))
    assert _novel(step2) == {("observation", o_a)}

    result = rejected(
        policy_heart.propose(_revise(policy_heart, a_id, confidence=Decimal("0.8"), evidence=(_support(b_id),)))
    )
    assert result.rules == {"EVD-4"}

    view = HeartView(policy_heart.store)
    issue_k = view.issue(a_id)
    assert issue_k is not None
    assert view.ledger(issue_k) == {observation_root(o_a), observation_root(o_b)}


def test_case11_justification_reports_both_candidate_and_novel(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case11-I"))
    o2 = policy_heart.receive()
    policy_heart.commit(Consolidate(o2))
    result = policy_heart.commit(
        _revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(o1), _support(o2)))
    )
    assert _candidate(result) == {("observation", o1), ("observation", o2)}
    assert _novel(result) == {("observation", o2)}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o2)}


def test_case12_a_forgotten_roots_identity_survives_and_still_grounds_nothing_new(
    policy_heart: Harness,
) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case12-I"))
    policy_heart.commit(Forget(o1, 1, "compressing"))
    result = rejected(
        policy_heart.propose(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(o1),)))
    )
    assert result.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1)}


# --- case 13: interoceptive classification --------------------------------


def test_case13_interoceptive_classification_sets_the_mode_int2_int3(tmp_path: Path) -> None:
    interoceptive_channel = OrganRef("heartbeat", "1")
    spec = SeedSpec(
        relations=("R1",),
        channels=(EYE, interoceptive_channel),
        organs=(MIND,),
        interoceptive=(interoceptive_channel,),
        theta_retain=Decimal("0.5"),
        retention_policy=FIXED,
    )
    path = tmp_path / "e001-case13.db"
    with Kernel.create(path, spec, [FixedRetention()]) as kernel:
        internal = kernel.body_channel(interoceptive_channel).receive("steady")
        external = kernel.body_channel(EYE).receive("red")
        outcome = kernel.organ(MIND).propose(Consolidate(internal), Consolidate(external))
        assert isinstance(outcome, KernelAccepted), str(outcome)
        internal_header = kernel.heart.latest(internal)
        external_header = kernel.heart.latest(external)
        assert internal_header is not None and external_header is not None
        internal_provenance_id = internal_header.provenance_id
        external_provenance_id = external_header.provenance_id

    reader = Store.open_readonly(path)
    try:
        internal_provenance = reader.provenance(internal_provenance_id)
        external_provenance = reader.provenance(external_provenance_id)
        assert internal_provenance is not None and internal_provenance.mode is Mode.SELF_OBSERVATION
        assert external_provenance is not None and external_provenance.mode is Mode.OBSERVATION
    finally:
        reader.close()

    # No proposal field can set a mode at all (PRV-8, INT-3).
    assert set(Consolidate.__dataclass_fields__) == {"observation_id"}


# --- cases 14-18: issue classification (ISS-4) ----------------------------


def test_case14_forming_a_claim_with_a_current_head_is_a_clone(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    _form(policy_heart, _claim(self_id, _derivation(o1), tag="case14"))
    clone = _claim(self_id, _derivation(o1), tag="case14")
    assert rejected(policy_heart.propose(clone)).rules == {"ISS-4"}


def test_case15_the_refused_clones_candidate_still_grounds_a_later_revision(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case15"))
    o3 = policy_heart.receive()
    policy_heart.commit(Consolidate(o3))
    clone_attempt = _claim(self_id, _derivation(o3), tag="case15")
    assert rejected(policy_heart.propose(clone_attempt)).rules == {"ISS-4"}
    result = policy_heart.commit(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(o3),)))
    assert _novel(result) == {("observation", o3)}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o3)}


def test_case16_reforming_with_the_same_root_is_refused(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case16"))
    policy_heart.commit(_revise(policy_heart, i_id, status=InfonStatus.RETIRED))
    reform = _claim(self_id, _derivation(o1), tag="case16")
    result = rejected(policy_heart.propose(reform))
    assert result.rules == {"ISS-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1)}


def test_case17_reformation_with_new_evidence_then_the_old_root_grounds_nothing(
    policy_heart: Harness,
) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case17"))
    policy_heart.commit(_revise(policy_heart, i_id, status=InfonStatus.RETIRED))
    o3 = policy_heart.receive()
    policy_heart.commit(Consolidate(o3))
    reform = _claim(self_id, _derivation(o3), tag="case17")
    result = policy_heart.commit(reform)
    j_id = result.operations[0].object_id
    assert _novel(result) == {("observation", o3)}
    stale = rejected(
        policy_heart.propose(_revise(policy_heart, j_id, confidence=Decimal("0.7"), evidence=(_support(o1),)))
    )
    assert stale.rules == {"EVD-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(j_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o3)}


def test_case18_reforming_a_forgotten_issue_with_the_same_root_is_refused(
    policy_heart: Harness,
) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case18"))
    policy_heart.commit(Forget(i_id, 1, "compressing"))
    reform = _claim(self_id, _derivation(o1), tag="case18")
    result = rejected(policy_heart.propose(reform))
    assert result.rules == {"ISS-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1)}


# --- cases 19-20: trust changes versus administrative changes -------------


def test_case19_reviving_from_contradicted_needs_evidence(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    i_id = _form(policy_heart, _claim(self_id, tag="case19"))
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    policy_heart.commit(_revise(policy_heart, i_id, status=InfonStatus.CONTRADICTED, evidence=(_counterevidence(o1),)))
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    before = view.ledger(issue)
    result = rejected(policy_heart.propose(_revise(policy_heart, i_id, status=InfonStatus.ACTIVE)))
    assert result.rules == {"EVD-4"}
    assert HeartView(policy_heart.store).ledger(issue) == before


def test_case20_administrative_retirement_needs_no_evidence(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    i_id = _form(policy_heart, _claim(self_id, tag="case20"))
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    before = view.ledger(issue)
    result = policy_heart.commit(_revise(policy_heart, i_id, status=InfonStatus.RETIRED))
    assert _classification(result) == "administrative"
    assert _novel(result) == set()
    assert HeartView(policy_heart.store).ledger(issue) == before


# --- case 21: syntactic issue identity ------------------------------------


def test_case21_different_context_is_a_different_issue(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case21"))
    view = HeartView(policy_heart.store)
    issue_k = view.issue(i_id)
    assert issue_k is not None
    before = view.ledger(issue_k)

    different_context = _claim(self_id, _derivation(o1), tag="case21", context={"note": "x"})
    result = policy_heart.commit(different_context)
    j_id = result.operations[0].object_id
    assert _classification(result) == "first_formation"
    assert _novel(result) == {("observation", o1)}

    view_after = HeartView(policy_heart.store)
    assert view_after.ledger(issue_k) == before
    issue_k_prime = view_after.issue(j_id)
    assert issue_k_prime is not None and issue_k_prime != issue_k
    assert view_after.ledger(issue_k_prime) == {observation_root(o1)}


# --- case 22: a rejected proposal consumes nothing (EVD-3) ----------------


def test_case22_certainty_failure_does_not_consume_the_evidence(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case22"))
    o7 = policy_heart.receive()
    policy_heart.commit(Consolidate(o7))
    certain = rejected(
        policy_heart.propose(_revise(policy_heart, i_id, confidence=Decimal("1"), evidence=(_support(o7),)))
    )
    assert certain.rules == {CERTAINTY}
    result = policy_heart.commit(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(o7),)))
    assert _novel(result) == {("observation", o7)}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o7)}


# --- case 23: forgetting a re-formed head keeps its admitted roots -------


def test_case23_forgetting_a_re_formed_head_does_not_erase_its_admitted_roots(
    policy_heart: Harness,
) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case23"))
    policy_heart.commit(_revise(policy_heart, i_id, status=InfonStatus.RETIRED))

    o2 = policy_heart.receive()
    policy_heart.commit(Consolidate(o2))
    reform = _claim(self_id, _derivation(o1), _derivation(o2), tag="case23")
    result = policy_heart.commit(reform)
    j_id = result.operations[0].object_id
    assert _novel(result) == {("observation", o2)}

    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o2)}

    policy_heart.commit(Forget(j_id, 1, "compressing"))
    assert HeartView(policy_heart.store).ledger(issue) == {observation_root(o1), observation_root(o2)}

    reform_again = _claim(self_id, _derivation(o2), tag="case23")
    stale = rejected(policy_heart.propose(reform_again))
    assert stale.rules == {"ISS-4"}
    assert HeartView(policy_heart.store).ledger(issue) == {observation_root(o1), observation_root(o2)}


# --- cases 24-25: attribution, grounding and the relevance boundary -------


def test_case24_attributed_only_formation_is_rootless_but_allowed(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    u = policy_heart.receive(content="a claim someone made")
    policy_heart.commit(Consolidate(u))
    result = policy_heart.commit(_claim(self_id, _attribution(u), tag="case24"))
    x_id = result.operations[0].object_id
    assert result.provenance[-1].mode is Mode.ATTRIBUTED
    assert _novel(result) == set()
    view = HeartView(policy_heart.store)
    assert not view.grounded(x_id)
    issue = view.issue(x_id)
    assert issue is not None
    assert view.ledger(issue) == frozenset()


def test_case25_relabeling_a_second_hearing_as_support_grounds_it_evd4_rol5(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    u1 = policy_heart.receive(content="first hearing")
    policy_heart.commit(Consolidate(u1))
    result = policy_heart.commit(_claim(self_id, _attribution(u1), tag="case25", confidence=Decimal("0.5")))
    x_id = result.operations[0].object_id
    view = HeartView(policy_heart.store)
    issue = view.issue(x_id)
    assert issue is not None
    assert view.ledger(issue) == frozenset()
    assert not view.grounded(x_id)

    u2 = policy_heart.receive(content="second hearing")
    policy_heart.commit(Consolidate(u2))
    result = policy_heart.commit(_revise(policy_heart, x_id, confidence=Decimal("0.6"), evidence=(_support(u2),)))
    assert _novel(result) == {("observation", u2)}
    assert HeartView(policy_heart.store).ledger(issue) == {observation_root(u2)}


# --- case 26: direction must match the role that carries novelty (ROL-4) --


def test_case26_counterevidence_alone_cannot_ground_an_upward_move(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case26"))
    o2 = policy_heart.receive()
    policy_heart.commit(Consolidate(o2))
    up = rejected(policy_heart.propose(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_counterevidence(o2),))))
    assert up.rules == {"ROL-4"}
    down = policy_heart.commit(_revise(policy_heart, i_id, confidence=Decimal("0.5"), evidence=(_counterevidence(o2),)))
    assert _novel(down) == {("observation", o2)}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1), observation_root(o2)}


# --- case 27: a later operation's failure discards the whole proposal ----


def test_case27_a_rejected_later_operation_admits_nothing_from_the_proposal(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i0_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case27-existing"))
    before = policy_heart.store.versions()

    o2 = policy_heart.receive()
    new_claim = _claim(self_id, _derivation(o2), tag="case27-new")
    stale_revision = _revise(policy_heart, i0_id, confidence=Decimal("0.7"), evidence=(_support(o1),))
    result = rejected(policy_heart.propose(Consolidate(o2), new_claim, stale_revision))
    assert result.operation == 2
    assert result.rules == {"EVD-4"}
    assert policy_heart.store.versions() == before


# --- case 28: rootless re-formation adds nothing --------------------------


def test_case28_rootless_reformation_adds_nothing(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    u1 = policy_heart.receive(content="hearing")
    policy_heart.commit(Consolidate(u1))
    x_id = _form(policy_heart, _claim(self_id, _attribution(u1), tag="case28"))
    policy_heart.commit(_revise(policy_heart, x_id, status=InfonStatus.RETIRED))
    u2 = policy_heart.receive(content="hearing 2")
    policy_heart.commit(Consolidate(u2))
    reform = _claim(self_id, _attribution(u2), tag="case28")
    result = rejected(policy_heart.propose(reform))
    assert result.rules == {"ISS-4"}
    view = HeartView(policy_heart.store)
    issue = view.issue(x_id)
    assert issue is not None
    assert view.ledger(issue) == frozenset()


# --- case 29: a different organ's testimony is an independent source -----


def test_case29_a_different_organs_testimony_is_an_independent_source(tmp_path: Path) -> None:
    scribe = OrganRef("scribe", "1")
    spec = SeedSpec(relations=("R1", "R2"), channels=(EYE,), organs=(MIND, scribe))
    harness = Harness(tmp_path / "e001-case29.db", spec)
    try:
        self_id = harness.manifest.self_id
        a_result = harness.commit(_claim(self_id, tag="case29-A"))
        a_id = a_result.operations[0].object_id

        n_claim = _claim(self_id, tag="case29-N", relation="R2")
        n_result = accepted(harness.propose(n_claim, organ=scribe))
        harness.store.commit(n_result, harness.manifest.omega_id)
        n_id = n_result.operations[0].object_id

        result = harness.commit(_revise(harness, a_id, confidence=Decimal("0.7"), evidence=(_support(n_id),)))
        assert _novel(result) == {("testimony", "scribe")}
        view = HeartView(harness.store)
        issue = view.issue(a_id)
        assert issue is not None
        assert view.ledger(issue) == {make_testimony_root("mind"), make_testimony_root("scribe")}
    finally:
        harness.close()


# --- case 30: formation cannot use support or revision_target (ROL-3) ----


def test_case30_formation_cannot_use_support_or_revision_target(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    for role in (Role.SUPPORT, Role.REVISION_TARGET):
        observation = policy_heart.receive()
        claim = _claim(self_id, RoleInput(observation, role), tag=f"case30-{role.value}")
        result = rejected(policy_heart.propose(Consolidate(observation), claim))
        assert result.rules == {"ROL-3"}


# --- case 31: replay refuses a tampered justification (EVD-7) ------------


def test_case31_tampering_a_revisions_justification_refuses_wake_up(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    i_id = _form(policy_heart, _claim(self_id, tag="case31"))
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    policy_heart.commit(_revise(policy_heart, i_id, confidence=Decimal("0.7"), evidence=(_support(o1),)))

    seq, record, _ = policy_heart.store.transitions()[-1]
    data = parse(record)
    assert isinstance(data, dict)
    justification = data["justification"]
    assert isinstance(justification, list)
    for entry in justification:
        if isinstance(entry, dict) and entry.get("rule") == "EVD-7":
            measured = entry["measured"]
            assert isinstance(measured, dict)
            measured["novel"] = []
    forged = canonical_bytes(data)
    tamper(
        policy_heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError):
        replay_current(policy_heart.store)


# --- case 32: a Mind cannot name another organ as its source (Law 8) ------


def test_case32_a_mind_cannot_name_another_organ_as_its_source(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    claim = _claim(self_id, tag="case32", context={"claimed_source": "scribe"})
    result = policy_heart.commit(claim)
    assert result.provenance[-1].mode is Mode.TESTIMONY
    assert result.provenance[-1].organ == MIND
    assert _candidate(result) == {("testimony", "mind")}


# --- case 33: administrative retirement must not admit evidence (EVD-5) --


def test_case33_administrative_retirement_must_not_admit_evidence(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    o1 = policy_heart.receive()
    policy_heart.commit(Consolidate(o1))
    i_id = _form(policy_heart, _claim(self_id, _derivation(o1), tag="case33"))
    o7 = policy_heart.receive()
    policy_heart.commit(Consolidate(o7))

    attempt = rejected(
        policy_heart.propose(_revise(policy_heart, i_id, status=InfonStatus.RETIRED, evidence=(_support(o7),)))
    )
    assert attempt.rules == {"EVD-5"}
    view = HeartView(policy_heart.store)
    issue = view.issue(i_id)
    assert issue is not None
    assert view.ledger(issue) == {observation_root(o1)}

    policy_heart.commit(_revise(policy_heart, i_id, status=InfonStatus.RETIRED))
    assert HeartView(policy_heart.store).ledger(issue) == {observation_root(o1)}

    reform = _claim(self_id, _derivation(o7), tag="case33")
    result = policy_heart.commit(reform)
    assert _novel(result) == {("observation", o7)}
    assert HeartView(policy_heart.store).ledger(issue) == {observation_root(o1), observation_root(o7)}
