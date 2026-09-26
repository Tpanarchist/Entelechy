import sqlite3

import pytest
from harness import OMEGA, Harness, accepted, infon_from

from entelechy.foundation.store import Store
from entelechy.foundation.types import Consolidate, EventType


def test_commit_persists_the_transition(heart: Harness) -> None:
    observation = heart.receive()
    result = heart.commit(Consolidate(observation), infon_from(observation))
    (infon_id,) = [h.id for h in result.versions if h.id != observation]
    assert [seq for seq, _, _ in heart.store.transitions()] == [result.seq]
    assert heart.store.latest(observation) is not None
    header = heart.store.latest(infon_id)
    assert header is not None and heart.store.content(header.body_digest) is not None
    assert [e.type for e in heart.store.events()] == [
        EventType.MEMORY_CONSOLIDATED,
        EventType.INFON_FORMED,
    ]


def test_the_record_never_contains_body_bytes_rpl3(heart: Harness) -> None:
    observation = heart.receive(content="ultraviolet-secret")
    heart.commit(Consolidate(observation), infon_from(observation))
    ((_, record, _),) = heart.store.transitions()
    assert b"ultraviolet-secret" not in record


def test_a_failed_commit_leaves_nothing_behind_per5(
    heart: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    observation = heart.receive()
    result = accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    before = heart.store.versions()

    def fail(self: Store, events: object) -> None:
        raise RuntimeError("power cut")

    monkeypatch.setattr(Store, "_insert_events", fail)
    with pytest.raises(RuntimeError, match="power cut"):
        heart.store.commit(result, OMEGA)
    assert heart.store.transitions() == []
    assert heart.store.versions() == before
    assert heart.store.events() == []


def test_only_accepted_transitions_can_be_committed_law5(heart: Harness) -> None:
    forged: object = {"seq": 1}
    with pytest.raises(TypeError, match="AcceptedTransition"):
        heart.store.commit(forged, OMEGA)  # type: ignore[arg-type]


def test_raw_delete_of_a_committed_object_aborts(heart: Harness) -> None:
    observation = heart.receive()
    heart.commit(Consolidate(observation), infon_from(observation))
    raw = heart.raw()
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute("DELETE FROM object_versions WHERE object_id = ?", (observation,))
    raw.close()
