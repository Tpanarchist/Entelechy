import pytest
from harness import Harness, tamper

from entelechy.foundation.canonical import Json, canonical_bytes, digest, parse
from entelechy.foundation.replay import (
    HeartView,
    IntegrityError,
    heart_digest,
    rebuild,
    replay_current,
    replay_historical,
)
from entelechy.foundation.types import Forget, InfonBody, Stub


def test_replay_current_equals_the_live_heart_law7(heart: Harness) -> None:
    heart.lifecycle()
    assert replay_current(heart.store) == heart_digest(heart.store)


def test_replay_rebuilds_the_same_rows_rpl1(heart: Harness) -> None:
    heart.lifecycle()
    fresh = rebuild(heart.store)
    assert fresh.versions() == heart.store.versions()
    assert fresh.all_provenance() == heart.store.all_provenance()
    assert fresh.events() == heart.store.events()
    fresh.close()


def test_a_record_that_no_longer_matches_its_digest_is_detected(heart: Harness) -> None:
    heart.lifecycle()
    tamper(heart.path, ("transitions_no_update",), "UPDATE transitions SET record = ?", (b"{}",))
    with pytest.raises(IntegrityError, match="does not match its digest"):
        replay_current(heart.store)


def test_a_consistently_rewritten_record_is_detected(heart: Harness) -> None:
    heart.lifecycle()
    ((seq, record, _),) = heart.store.transitions()
    data = parse(record)
    assert isinstance(data, dict)
    data["events"] = []
    forged = canonical_bytes(data)
    tamper(
        heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError, match="differs from replay"):
        replay_current(heart.store)


def test_altered_content_is_detected_rpl2(heart: Harness) -> None:
    heart.lifecycle()
    tamper(heart.path, ("content_no_update",), "UPDATE content SET body = ?", (b"{}",))
    with pytest.raises(IntegrityError, match="was altered"):
        replay_current(heart.store)


def test_missing_content_is_detected_rpl2(heart: Harness) -> None:
    heart.lifecycle()
    tamper(heart.path, ("content_delete_only_forgotten",), "DELETE FROM content")
    with pytest.raises(IntegrityError, match="is missing"):
        replay_current(heart.store)


def test_replay_current_is_exact_after_forgetting_rpl3(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    policy_heart.commit(Forget(observation, 1, "compressing"))
    assert replay_current(policy_heart.store) == heart_digest(policy_heart.store)


def test_historical_replay_stubs_content_forgotten_later_rpl4(policy_heart: Harness) -> None:
    observation, infon_id = policy_heart.lifecycle()
    formed_at = policy_heart.store.transitions()[-1][0]
    policy_heart.commit(Forget(observation, 1, "compressing"))
    view = replay_historical(policy_heart.store, formed_at)
    assert view.versions(observation) == policy_heart.store.versions(observation)[:1]
    assert view.body(observation) is Stub.CONTENT_FORGOTTEN
    infon = view.infon(infon_id)
    assert isinstance(infon, InfonBody) and infon.relation == "R1"


def test_historical_replay_at_zero_is_the_seed(heart: Harness) -> None:
    heart.lifecycle()
    view = replay_historical(heart.store, 0)
    assert [header.id for header in view.objects()] == [heart.manifest.self_id]
    assert view.events() == []


def test_the_live_view_shows_forgotten_content_as_a_stub(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    policy_heart.commit(Forget(observation, 1, "compressing"))
    view = HeartView(policy_heart.store)
    header = view.latest(observation)
    assert header is not None and header.forgotten
    assert view.body(observation) is Stub.CONTENT_FORGOTTEN


def _forge_evd7_field(record: bytes, field_name: str, value: Json) -> bytes:
    data = parse(record)
    assert isinstance(data, dict)
    justification = data["justification"]
    assert isinstance(justification, list)
    for entry in justification:
        assert isinstance(entry, dict)
        if entry.get("rule") == "EVD-7":
            measured = entry["measured"]
            assert isinstance(measured, dict)
            measured[field_name] = value
    return canonical_bytes(data)


def test_a_fabricated_novel_root_does_not_survive_replay_evd7_case31(heart: Harness) -> None:
    """A validator that claimed a root that does not actually follow from
    provenance would be caught here: replay independently recomputes every
    root, ledger and novelty fact from structure alone (EVD-7)."""
    heart.lifecycle()
    ((seq, record, _),) = heart.store.transitions()
    forged = _forge_evd7_field(
        record, "novel", [{"kind": "testimony", "key": "a-source-nothing-actually-cited"}]
    )
    tamper(
        heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError, match="novel roots"):
        replay_current(heart.store)


def test_a_fabricated_classification_does_not_survive_replay_iss4_case31(heart: Harness) -> None:
    heart.lifecycle()
    ((seq, record, _),) = heart.store.transitions()
    forged = _forge_evd7_field(record, "classification", "re_formation")
    tamper(
        heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError, match="ISS-4 classification"):
        replay_current(heart.store)
