"""E000: the first lawful Heart, end to end through the kernel and its ports."""

import itertools
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from harness import EYE, MIND, FixedRetention, infon_from, plain_seed, policy_seed, tamper

from entelechy.foundation.canonical import CanonicalError, Json, parse
from entelechy.foundation.kernel import Accepted, BodyChannel, Kernel, KernelError, OrganPort
from entelechy.foundation.replay import IntegrityError
from entelechy.foundation.seed import SeedError, SeedSpec
from entelechy.foundation.store import Store, StoreError
from entelechy.foundation.types import (
    Consolidate,
    EventType,
    Forget,
    InfonBody,
    OrganRef,
    OtherOperation,
    Polarity,
    ProposedOperation,
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
    observation = kernel.body_channel(EYE).receive(content)
    result = ok(kernel.organ(MIND).propose(Consolidate(observation), infon_from(observation)))
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
        mind = kernel.organ(MIND)
        observation = kernel.body_channel(EYE).receive("red")
        ok(mind.propose(Consolidate(observation)))
        ok(mind.propose(infon_from(observation)))
    Kernel.open(path, [FixedRetention()]).close()


# ORG-6: authority-bearing identity comes from capability, not payload.


def test_a_body_channel_delivers_only_as_its_own_channel_org6(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        eye = kernel.body_channel(EYE)
        assert eye.channel == EYE
        observation = eye.receive("red")
        ok(kernel.organ(MIND).propose(Consolidate(observation), infon_from(observation)))
        body = kernel.heart.body(observation)
        assert isinstance(body, dict) and body["channel"] == EYE.to_canonical()


CHANNELS = (EYE, OrganRef("ear", "1"), OrganRef("nose", "1"))
ORGANS = (MIND, OrganRef("scribe", "1"), OrganRef("critic", "1"))
# (channel index, organ index) for each use: aperiodic, with back-to-back reuse.
PLAN = [(1, 2), (1, 0), (0, 1), (2, 2), (2, 2), (0, 0), (1, 1), (2, 0)]


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))), ids=str)
def test_each_port_acts_only_as_its_own_identity_org6(
    tmp_path: Path, order: tuple[int, ...]
) -> None:
    # Ports are made in every order (organs in reverse), all before use, and
    # used in an order unrelated to either. A kernel that picks identity by
    # registration slot, creation order, recency or call count fails here.
    path = tmp_path / "heart.db"
    uses: list[tuple[str, OrganRef, Accepted, OrganRef]] = []
    with Kernel.create(path, SeedSpec(("R1",), CHANNELS, ORGANS)) as kernel:
        channel_ports = {CHANNELS[i]: kernel.body_channel(CHANNELS[i]) for i in order}
        organ_ports = {ORGANS[i]: kernel.organ(ORGANS[i]) for i in reversed(order)}
        for ref, channel_port in channel_ports.items():
            assert channel_port.channel == ref
        for ref, organ_port in organ_ports.items():
            assert organ_port.organ == ref
        for c, o in PLAN:
            channel, organ = CHANNELS[order[c]], ORGANS[order[o]]
            observation = channel_ports[channel].receive("x")
            result = ok(
                organ_ports[organ].propose(Consolidate(observation), infon_from(observation))
            )
            uses.append((observation, channel, result, organ))
    reader = Store.open_readonly(path)
    records = {seq: parse(record) for seq, record, _ in reader.transitions()}
    for observation, channel, accepted, organ in uses:
        observed = reader.latest(observation)
        assert observed is not None
        observed_provenance = reader.provenance(observed.provenance_id)
        assert observed_provenance is not None and observed_provenance.organ == channel
        (infon_id,) = [object_id for object_id in accepted.created if object_id != observation]
        infon = reader.latest(infon_id)
        assert infon is not None
        infon_provenance = reader.provenance(infon.provenance_id)
        assert infon_provenance is not None and infon_provenance.organ == organ
        record = records[accepted.seq]
        assert isinstance(record, dict) and record["proposer"] == organ.to_canonical()
    reader.close()


def test_an_organ_port_proposes_only_as_its_own_organ_org6(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        mind = kernel.organ(MIND)
        assert mind.organ == MIND
        assert mind.heart.digest() == kernel.heart.digest()
        assert not hasattr(mind, "receive")


def test_the_kernel_takes_no_identity_as_data_org6(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        assert not hasattr(kernel, "receive")
        assert not hasattr(kernel, "propose")


def test_a_mind_organ_cannot_act_as_a_body_channel_org6(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(KernelError, match="ORG-6"):
            kernel.body_channel(MIND)


def test_a_body_channel_cannot_act_as_a_mind_organ_org6(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(KernelError, match="ORG-6"):
            kernel.organ(EYE)


def test_ports_are_made_only_by_the_kernel_org6(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(PermissionError, match="ORG-6"):
            BodyChannel(kernel, EYE, key=object())
        with pytest.raises(PermissionError, match="ORG-6"):
            OrganPort(kernel, MIND, key=object())


def test_an_unregistered_channel_gets_no_port_org2(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(KernelError, match="ORG-2"):
            kernel.body_channel(OrganRef("ear", "1"))


def test_an_unregistered_organ_gets_no_port_org2(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(KernelError, match="ORG-2"):
            kernel.organ(OrganRef("llm", "4"))


type Ops = tuple[ProposedOperation, ...]
type Build = Callable[[Kernel, str, str, str], Ops]


def cite_transient(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (infon_from(fresh),)


def negative_infon(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Consolidate(fresh), replace(infon_from(fresh), polarity=Polarity.NEGATIVE))


def certain(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Consolidate(fresh), infon_from(fresh, confidence=Decimal(1)))


def impossible(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Consolidate(fresh), infon_from(fresh, confidence=Decimal(0)))


def unknown_relation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Consolidate(fresh), infon_from(fresh, relation="Color"))


def forget_without_policy(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Forget(observation, 1, "compressing"),)


def forget_the_self(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Forget(f"self:{kernel.omega_id}", 1, "who am I"),)


def edit_observation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (Consolidate(fresh), ReviseInfon(observation, 1, body_of(kernel, infon_id), (fresh,)))


def change_relation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    body = replace(body_of(kernel, infon_id), relation="R2")
    return (Consolidate(fresh), ReviseInfon(infon_id, 1, body, (fresh,)))


def unbuilt(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Ops:
    return (OtherOperation("PROPOSE_MODEL"),)


@pytest.mark.parametrize(
    ("build", "rule"),
    [
        (cite_transient, "PRV-4"),
        (negative_infon, UNIMPLEMENTED),
        (certain, CERTAINTY),
        (impossible, CERTAINTY),
        (unknown_relation, "INF-1"),
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
        fresh = kernel.body_channel(EYE).receive("blue")
        before = kernel.heart.digest()
        operations = build(kernel, observation, infon_id, fresh)
        result = refused(kernel.organ(MIND).propose(*operations))
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


def test_non_canonical_content_is_refused_before_it_uses_a_seq(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        weight: object = {"weight": 0.5}
        with pytest.raises(CanonicalError, match="floats"):
            kernel.body_channel(EYE).receive(weight)  # type: ignore[arg-type]
        first_lifecycle(kernel)
        assert kernel.heart.events()[-1].seq == 2


def test_the_kernel_keeps_what_was_received_not_the_callers_buffer_obs1(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        buffer: dict[str, Json] = {"reading": 1}
        observation = kernel.body_channel(EYE).receive(buffer)
        buffer["reading"] = 2
        ok(kernel.organ(MIND).propose(Consolidate(observation), infon_from(observation)))
        body = kernel.heart.body(observation)
        assert isinstance(body, dict) and body["content"] == {"reading": 1}


def test_identifiers_must_be_a_list_not_one_string(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(CanonicalError, match="identifiers"):
            kernel.body_channel(EYE).receive("red", "abc")


@pytest.mark.parametrize("identifiers", [None, {"track-7": 1}], ids=["none", "dict"])
def test_identifiers_must_be_a_list_or_tuple(tmp_path: Path, identifiers: object) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(CanonicalError, match="identifiers"):
            kernel.body_channel(EYE).receive("red", identifiers)  # type: ignore[arg-type]


def test_unencodable_identifiers_are_refused_before_they_use_a_seq(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(CanonicalError):
            kernel.body_channel(EYE).receive("red", ["photo-\udcff.jpg"])
        first_lifecycle(kernel)
        assert kernel.heart.events()[-1].seq == 2


def test_identifiers_must_be_strings(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        numbers: object = [7]
        with pytest.raises(CanonicalError, match="identifiers"):
            kernel.body_channel(EYE).receive("red", numbers)  # type: ignore[arg-type]


def test_an_integer_too_large_to_encode_is_refused_before_it_uses_a_seq(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(CanonicalError):
            kernel.body_channel(EYE).receive(10**5000)
        first_lifecycle(kernel)
        assert kernel.heart.events()[-1].seq == 2


def test_historical_views_cannot_write_the_heart_law5(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        first_lifecycle(kernel)
        view = kernel.replay_historical(1)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            view._content.allocate_seq()


def test_an_unknown_observation_id_is_rejected_not_raised(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        typo = "obs:not-a-real-id"
        result = refused(kernel.organ(MIND).propose(Consolidate(typo), infon_from(typo)))
        assert result.rules == {"PER-3"}


def test_transient_observations_do_not_survive_restart_per4(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        observation = kernel.body_channel(EYE).receive("red")
    with Kernel.open(path) as reopened:
        result = reopened.organ(MIND).propose(Consolidate(observation), infon_from(observation))
        assert refused(result).rules == {"PER-3"}


def test_seq_is_never_reused_across_rejection_and_restart_seq2(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        first_lifecycle(kernel)
        first = kernel.heart.events()[-1].seq
        refused(kernel.organ(MIND).propose())
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


def test_create_with_an_unencodable_seed_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with pytest.raises(SeedError):
        Kernel.create(path, SeedSpec(("R\udcff",), (EYE,), (MIND,)))
    assert not path.exists()


def test_a_failed_origin_write_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "heart.db"

    def fail(self: Store, *args: object) -> None:
        raise RuntimeError("power cut")

    monkeypatch.setattr(Store, "write_origin", fail)
    with pytest.raises(RuntimeError, match="power cut"):
        Kernel.create(path, plain_seed())
    assert list(tmp_path.iterdir()) == []


def test_a_real_failure_while_building_the_schema_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_connect = Store._connect

    def tiny_disk(target: str) -> sqlite3.Connection:
        connection = real_connect(target)
        connection.execute("PRAGMA max_page_count = 2")
        return connection

    monkeypatch.setattr(Store, "_connect", staticmethod(tiny_disk))
    with pytest.raises(sqlite3.OperationalError, match="full"):
        Kernel.create(tmp_path / "heart.db", plain_seed())
    assert list(tmp_path.iterdir()) == []


def test_a_target_that_appears_during_creation_is_never_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "heart.db"
    real_write_origin = Store.write_origin

    def someone_else_arrives(self: Store, *args: Any) -> None:
        real_write_origin(self, *args)
        path.write_bytes(b"someone else's file")

    monkeypatch.setattr(Store, "write_origin", someone_else_arrives)
    with pytest.raises(StoreError, match="already exists"):
        Kernel.create(path, plain_seed())
    assert path.read_bytes() == b"someone else's file"
    assert [entry.name for entry in tmp_path.iterdir()] == ["heart.db"]


def test_successful_creation_leaves_only_an_openable_heart(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        created = kernel.heart.digest()
    assert [entry.name for entry in tmp_path.iterdir()] == ["heart.db"]
    with Kernel.open(path) as reopened:
        assert reopened.replay_current() == created


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
