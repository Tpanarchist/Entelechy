from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from harness import FixedRetention, Harness, form_testimony, policy_seed, rejected

from entelechy.foundation.canonical import parse
from entelechy.foundation.types import (
    Consolidate,
    EventType,
    FormInfon,
    Forget,
    InfonBody,
    InfonStatus,
    ObjectReferent,
    ObjectType,
    ReviseInfon,
    Role,
    RoleInput,
)
from entelechy.foundation.validator import UNIMPLEMENTED


def test_forget_needs_a_bound_policy_mem2(heart: Harness) -> None:
    observation, _ = heart.lifecycle()
    result = rejected(heart.propose(Forget(observation, 1, "compressing")))
    assert result.rules == {"MEM-2"}
    assert result.violations[0].measured["theta_forget"] == "unbound"


def test_forget_retires_content_and_keeps_a_stub_mem3(policy_heart: Harness) -> None:
    observation, infon_id = policy_heart.lifecycle()
    before = policy_heart.store.latest(observation)
    assert before is not None
    result = policy_heart.commit(Forget(observation, 1, "compressing"))
    stub = policy_heart.store.latest(observation)
    assert stub is not None
    assert (stub.version, stub.forgotten, stub.retired_by) == (2, True, result.seq)
    assert (stub.provenance_id, stub.body_digest) == (before.provenance_id, before.body_digest)
    assert policy_heart.store.content(before.body_digest) is None
    assert [e.type for e in result.events] == [EventType.MEMORY_FORGOTTEN]
    assert result.operations[0].reason == "compressing"
    # The Infon that cited the Observation stays valid on the stub (MEM-5).
    infon = policy_heart.store.latest(infon_id)
    assert infon is not None and policy_heart.store.content(infon.body_digest) is not None


def test_a_score_above_the_threshold_is_not_forgotten_mem2(tmp_path: Path) -> None:
    heart = Harness(tmp_path / "heart.db", policy_seed(), FixedRetention(Decimal("0.9")))
    observation, _ = heart.lifecycle()
    assert rejected(heart.propose(Forget(observation, 1, "compressing"))).rules == {"MEM-2"}
    heart.close()


def test_a_retention_score_with_no_canonical_form_is_rejected_not_raised(tmp_path: Path) -> None:
    heart = Harness(tmp_path / "heart.db", policy_seed(), FixedRetention(Decimal("1E-200")))
    observation = heart.receive()
    assert rejected(heart.propose(Consolidate(observation))).rules == {"MEM-1"}
    lifecycle_observation, _ = heart.lifecycle()
    forget = Forget(lifecycle_observation, 1, "compressing")
    assert rejected(heart.propose(forget)).rules == {"MEM-2"}
    heart.close()


def test_seed_structure_cannot_be_forgotten_mem4(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    assert rejected(policy_heart.propose(Forget(self_id, 1, "who am I"))).rules == {"MEM-4"}


def test_forgetting_twice_is_rejected_mem3(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    policy_heart.commit(Forget(observation, 1, "compressing"))
    result = rejected(policy_heart.propose(Forget(observation, 2, "again")))
    assert result.rules == {"MEM-3"}


def test_forget_needs_a_reason_mem3(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    assert rejected(policy_heart.propose(Forget(observation, 1, "  "))).rules == {"MEM-3"}


def test_forget_of_a_stale_version_is_rejected_per6(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    assert rejected(policy_heart.propose(Forget(observation, 2, "x"))).rules == {"PER-6"}


def test_compression_into_a_successor_is_unimplemented(policy_heart: Harness) -> None:
    observation, infon_id = policy_heart.lifecycle()
    result = rejected(policy_heart.propose(Forget(observation, 1, "compressing", infon_id)))
    assert result.rules == {UNIMPLEMENTED}


def test_transient_observations_are_not_forgotten_through_forget(policy_heart: Harness) -> None:
    observation = policy_heart.receive()
    assert rejected(policy_heart.propose(Forget(observation, 1, "x"))).rules == {"MEM-3"}


def test_shared_content_survives_forgetting_one_owner(policy_heart: Harness) -> None:
    """Two live objects can share a body digest: an Infon's own historical
    version, and a second Infon re-formed on the same issue with the same
    content. Forgetting the first must not take the shared bytes with it
    (MEM-5), even though the digest is reachable through its own lineage too.
    """
    testify = form_testimony(policy_heart.manifest.self_id, relation="R2", confidence=Decimal("0.6"))
    (first_id,) = [h.id for h in policy_heart.commit(testify).versions]
    original = policy_heart.store.latest(first_id)
    assert original is not None
    shared_digest = original.body_digest

    retired = replace(
        InfonBody.from_canonical(parse(policy_heart.store.content(shared_digest))),  # type: ignore[arg-type]
        status=InfonStatus.RETIRED,
    )
    policy_heart.commit(ReviseInfon(first_id, 1, retired, ()))

    evidence = policy_heart.receive()
    reformed = FormInfon(
        relation="R2",
        participants=(ObjectReferent(policy_heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        inputs=(RoleInput(evidence, Role.DERIVATION_INPUT),),
    )
    result = policy_heart.commit(Consolidate(evidence), reformed)
    (second_id,) = [h.id for h in result.versions if h.type is ObjectType.INFON]
    second = policy_heart.store.latest(second_id)
    assert second is not None and second.body_digest == shared_digest

    policy_heart.commit(Forget(first_id, 2, "retired and no longer needed"))
    assert policy_heart.store.content(shared_digest) is not None
