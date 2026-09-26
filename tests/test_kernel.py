"""E000: the first lawful Heart, end to end through the kernel."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from harness import EYE, MIND, FixedRetention, infon_from, plain_seed, policy_seed, tamper

from entelechy.foundation.canonical import CanonicalError, Json
from entelechy.foundation.kernel import Accepted, Kernel, KernelError
from entelechy.foundation.replay import IntegrityError
from entelechy.foundation.store import StoreError
from entelechy.foundation.types import (
    Consolidate,
    EventType,
    Forget,
    InfonBody,
    OrganRef,
    OtherOperation,
    Polarity,
    Proposal,
    ReviseInfon,
)
from entelechy.foundation.validator import CERTAINTY, UNIMPLEMENTED, Rejection


def ok(result: Accepted | Rejection) -> Accepted:
    assert isinstance(result, Accepted), str(result)
    return result


def refused(result: Accepted | Rejection) -> Rejection:
    assert isinstance(result, Rejection), f"expected a rejection, got {result}"
    return result


def first_lifecycle(kernel: Kernel, content: Json = "red") -> tuple[str, str]:
    observation = kernel.receive(EYE, content)
    result = ok(
        kernel.propose(Proposal(MIND, (Consolidate(observation), infon_from(observation))))
    )
    (infon_id,) = [object_id for object_id in result.created if object_id != observation]
    return observation, infon_id


def body_of(kernel: Kernel, infon_id: str) -> InfonBody:
    body = kernel.heart.infon(infon_id)
    assert isinstance(body, InfonBody)
    return body


def test_e000_a_lawful_heart_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    kernel = Kernel.create(path, plain_seed())
    omega_id = kernel.omega_id
    _, infon_id = first_lifecycle(kernel, {"color": "red"})
    assert [event.type for event in kernel.heart.events()] == [
        EventType.MEMORY_CONSOLIDATED,
        EventType.INFON_FORMED,
    ]
    before = kernel.heart.digest()
    kernel.close()

    with Kernel.open(path) as reopened:
        assert reopened.omega_id == omega_id
        assert reopened.heart.digest() == before
        assert reopened.replay_current() == before
        assert body_of(reopened, infon_id).relation == "R1"


def test_e000_the_two_step_lifecycle_under_a_retention_policy(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, policy_seed(), [FixedRetention()]) as kernel:
        observation = kernel.receive(EYE, "red")
        ok(kernel.propose(Proposal(MIND, (Consolidate(observation),))))
        ok(kernel.propose(Proposal(MIND, (infon_from(observation),))))
    Kernel.open(path, [FixedRetention()]).close()


type Build = Callable[[Kernel, str, str, str], Proposal]


def cite_transient(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (infon_from(fresh),))


def negative_infon(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    negative = replace(infon_from(fresh), polarity=Polarity.NEGATIVE)
    return Proposal(MIND, (Consolidate(fresh), negative))


def certain(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Consolidate(fresh), infon_from(fresh, confidence=Decimal(1))))


def impossible(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Consolidate(fresh), infon_from(fresh, confidence=Decimal(0))))


def unknown_relation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Consolidate(fresh), infon_from(fresh, relation="Color")))


def stranger(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(OrganRef("llm", "4"), (Consolidate(fresh), infon_from(fresh)))


def forget_without_policy(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Forget(observation, 1, "compressing"),))


def forget_the_self(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Forget(f"self:{kernel.omega_id}", 1, "who am I"),))


def edit_observation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    revise = ReviseInfon(observation, 1, body_of(kernel, infon_id), (fresh,))
    return Proposal(MIND, (Consolidate(fresh), revise))


def change_relation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    body = replace(body_of(kernel, infon_id), relation="R2")
    return Proposal(MIND, (Consolidate(fresh), ReviseInfon(infon_id, 1, body, (fresh,))))


def unbuilt(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (OtherOperation("PROPOSE_MODEL"),))


@pytest.mark.parametrize(
    ("build", "rule"),
    [
        (cite_transient, "PRV-4"),
        (negative_infon, UNIMPLEMENTED),
        (certain, CERTAINTY),
        (impossible, CERTAINTY),
        (unknown_relation, "INF-1"),
        (stranger, "ORG-2"),
        (forget_without_policy, "MEM-2"),
        (forget_the_self, "MEM-4"),
        (edit_observation, "OBS-1"),
        (change_relation, "INF-4"),
        (unbuilt, UNIMPLEMENTED),
    ],
    ids=lambda value: getattr(value, "__name__", str(value)),
)
def test_illegal_proposals_are_rejected_and_change_nothing(
    tmp_path: Path, build: Build, rule: str
) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        observation, infon_id = first_lifecycle(kernel)
        fresh = kernel.receive(EYE, "blue")
        before = kernel.heart.digest()
        result = refused(kernel.propose(build(kernel, observation, infon_id, fresh)))
        assert rule in result.rules
        assert kernel.heart.digest() == before


def test_the_heart_view_cannot_write_law5(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            kernel.heart._structure.allocate_seq()


def test_wake_up_refuses_a_tampered_lineage_law7(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        first_lifecycle(kernel)
    tamper(path, ("transitions_no_update",), "UPDATE transitions SET record = ?", (b"{}",))
    with pytest.raises(IntegrityError):
        Kernel.open(path)


def test_wake_up_refuses_altered_content_rpl2(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        first_lifecycle(kernel)
    tamper(path, ("content_no_update",), "UPDATE content SET body = ?", (b"{}",))
    with pytest.raises(IntegrityError, match="was altered"):
        Kernel.open(path)


def test_wake_up_refuses_a_heart_whose_guards_were_dropped(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    Kernel.create(path, plain_seed()).close()
    raw = sqlite3.connect(path, autocommit=True)
    raw.execute("DROP TRIGGER object_versions_no_delete")
    raw.close()
    with pytest.raises(StoreError, match="guards are missing"):
        Kernel.open(path)


def test_an_unregistered_channel_cannot_deliver_org2(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(KernelError, match="ORG-2"):
            kernel.receive(OrganRef("ear", "1"), "noise")


def test_non_canonical_content_is_refused_before_it_uses_a_seq(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        weight: object = {"weight": 0.5}
        with pytest.raises(CanonicalError, match="floats"):
            kernel.receive(EYE, weight)  # type: ignore[arg-type]
        first_lifecycle(kernel)
        assert kernel.heart.events()[-1].seq == 2


def test_an_unknown_observation_id_is_rejected_not_raised(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        typo = "obs:not-a-real-id"
        result = refused(kernel.propose(Proposal(MIND, (Consolidate(typo), infon_from(typo)))))
        assert result.rules == {"PER-3"}


def test_transient_observations_do_not_survive_restart_per4(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        observation = kernel.receive(EYE, "red")
    with Kernel.open(path) as reopened:
        proposal = Proposal(MIND, (Consolidate(observation), infon_from(observation)))
        assert refused(reopened.propose(proposal)).rules == {"PER-3"}


def test_seq_is_never_reused_across_rejection_and_restart_seq2(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        first_lifecycle(kernel)
        first = kernel.heart.events()[-1].seq
        refused(kernel.propose(Proposal(MIND, ())))
    with Kernel.open(path) as reopened:
        first_lifecycle(reopened)
        latest = reopened.heart.events()[-1].seq
    # The rejected proposal consumed first + 1; nothing after restart reuses it.
    assert latest > first + 1


def test_open_refuses_when_the_seed_policy_is_not_supplied(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    Kernel.create(path, policy_seed(), [FixedRetention()]).close()
    with pytest.raises(KernelError, match="fixed@1"):
        Kernel.open(path)


def test_create_refuses_a_seed_whose_policy_is_missing_and_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with pytest.raises(KernelError, match="fixed@1"):
        Kernel.create(path, policy_seed())
    assert not path.exists()


def test_create_refuses_an_existing_heart_and_leaves_it_intact(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    Kernel.create(path, plain_seed()).close()
    with pytest.raises(StoreError, match="already exists"):
        Kernel.create(path, plain_seed())
    Kernel.open(path).close()


def test_open_refuses_a_file_that_is_not_a_heart(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("dear diary " * 20)
    with pytest.raises(StoreError, match="not an Entelechy Heart"):
        Kernel.open(path)
