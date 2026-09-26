from dataclasses import replace
from decimal import Decimal

import pytest
from harness import MIND, Harness, form_testimony, infon_body, tamper

from entelechy.foundation.canonical import Json, canonical_bytes, digest, parse
from entelechy.foundation.evidence import observation_root
from entelechy.foundation.replay import (
    HeartView,
    IntegrityError,
    heart_digest,
    rebuild,
    replay_current,
    replay_historical,
)
from entelechy.foundation.transitions import build_record
from entelechy.foundation.types import (
    Check,
    Consolidate,
    EventRow,
    EventType,
    Forget,
    FormInfon,
    InfonBody,
    InfonStatus,
    IssueRow,
    Mode,
    ObjectHeader,
    ObjectReferent,
    ObjectRef,
    ObjectType,
    Operation,
    OperationEntry,
    Provenance,
    ProvenanceInput,
    ReviseInfon,
    Role,
    RoleInput,
    Stub,
)


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


# The E001 read API (spec §2.6): roots, grounded, issue, head, ledger, and a
# version-aware body/infon (the PER-8 read path).


def test_heart_view_roots_and_grounded(heart: Harness) -> None:
    observation, infon_id = heart.lifecycle()
    view = HeartView(heart.store)
    assert view.roots(observation) == {observation_root(observation)}
    assert view.roots(infon_id) == {observation_root(observation)}
    assert view.grounded(infon_id)


def test_heart_view_roots_is_version_aware_rot5(heart: Harness) -> None:
    _, infon_id = heart.lifecycle()
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, (RoleInput(evidence, Role.SUPPORT),))
    )
    view = HeartView(heart.store)
    assert len(view.roots(infon_id, version=1)) == 1
    assert len(view.roots(infon_id, version=2)) == 2
    assert view.roots(infon_id, version=1) < view.roots(infon_id, version=2)


def test_heart_view_grounded_is_false_for_an_attributed_infon_rot8(heart: Harness) -> None:
    utterance = heart.receive(content="hello")
    attributed = FormInfon(
        relation="R1",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        inputs=(RoleInput(utterance, Role.ATTRIBUTION),),
    )
    result = heart.commit(Consolidate(utterance), attributed)
    (attributed_id,) = [h.id for h in result.versions if h.id != utterance]
    view = HeartView(heart.store)
    assert view.roots(attributed_id) == frozenset()
    assert not view.grounded(attributed_id)


def test_heart_view_issue_and_head(heart: Harness) -> None:
    _, infon_id = heart.lifecycle()
    view = HeartView(heart.store)
    issue = view.issue(infon_id)
    assert issue is not None
    assert view.head(issue) == infon_id
    assert view.ledger(issue) == view.roots(infon_id)
    assert view.issue("infon:ghost") is None


def test_heart_view_head_is_none_once_the_only_member_is_retired(heart: Harness) -> None:
    _, infon_id = heart.lifecycle()
    view_before = HeartView(heart.store)
    issue = view_before.issue(infon_id)
    assert issue is not None
    header = heart.store.latest(infon_id)
    assert header is not None
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    heart.commit(ReviseInfon(infon_id, header.version, retired, ()))
    view_after = HeartView(heart.store)
    assert view_after.head(issue) is None
    # The ledger still holds every root this issue ever admitted.
    assert view_after.ledger(issue) == view_before.roots(infon_id)


def test_heart_view_body_reads_a_historical_version_per8(heart: Harness) -> None:
    _, infon_id = heart.lifecycle()
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, (RoleInput(evidence, Role.SUPPORT),))
    )
    view = HeartView(heart.store)
    original = view.infon(infon_id, version=1)
    current = view.infon(infon_id, version=2)
    assert isinstance(original, InfonBody) and original.confidence == Decimal("0.8")
    assert isinstance(current, InfonBody) and current.confidence == Decimal("0.9")


def test_heart_view_body_is_none_for_an_unknown_object_or_version(heart: Harness) -> None:
    _, infon_id = heart.lifecycle()
    view = HeartView(heart.store)
    assert view.body("infon:ghost") is None
    assert view.body(infon_id, version=99) is None


def test_heart_view_body_stubs_a_purged_historical_version(policy_heart: Harness) -> None:
    """A historical (non-latest) version's own header never gets `forgotten`
    set, yet its bytes are purged along with the rest of the object's
    content once it is forgotten (unless another live object still shares
    the digest). The version-aware read must show that as a stub, not raise.
    """
    observation, infon_id = policy_heart.lifecycle()
    evidence = policy_heart.receive()
    body = replace(infon_body(policy_heart.store, infon_id), confidence=Decimal("0.9"))
    policy_heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, (RoleInput(evidence, Role.SUPPORT),))
    )
    policy_heart.commit(Forget(infon_id, 2, "compressing"))
    view = HeartView(policy_heart.store)
    assert view.body(infon_id, version=1) is Stub.CONTENT_FORGOTTEN
    assert view.body(infon_id, version=2) is Stub.CONTENT_FORGOTTEN
    assert view.body(infon_id) is Stub.CONTENT_FORGOTTEN


def test_heart_view_body_raises_on_unforgotten_missing_content(heart: Harness) -> None:
    """A historical version's content going missing is a stub only when the
    object was actually forgotten (its latest version's `forgotten` flag,
    MEM-3). A live, never-forgotten object whose v1 bytes vanish some other
    way is corruption, and must still raise IntegrityError — the version
    requested does not by itself make missing content look forgotten.
    """
    _, infon_id = heart.lifecycle()
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.9"))
    heart.commit(
        Consolidate(evidence), ReviseInfon(infon_id, 1, body, (RoleInput(evidence, Role.SUPPORT),))
    )
    v1 = heart.store.header_at(ObjectRef(infon_id, 1))
    assert v1 is not None
    tamper(heart.path, ("content_delete_only_forgotten",), "DELETE FROM content WHERE digest = ?", (v1.body_digest,))
    view = HeartView(heart.store)
    with pytest.raises(IntegrityError, match="missing or altered"):
        view.body(infon_id, version=1)


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


def test_a_deleted_evd7_check_does_not_survive_replay(heart: Harness) -> None:
    """A tamper that removes the EVD-7 check entirely (rather than editing a
    field inside it) must be caught too: zero checks must not silently mean
    zero audit."""
    heart.lifecycle()
    ((seq, record, _),) = heart.store.transitions()
    data = parse(record)
    assert isinstance(data, dict)
    justification = data["justification"]
    assert isinstance(justification, list)
    data["justification"] = [
        item
        for item in justification
        if not (isinstance(item, dict) and item.get("rule") == "EVD-7")
    ]
    forged = canonical_bytes(data)
    tamper(
        heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError, match="exactly one"):
        replay_current(heart.store)


def test_a_form_infon_with_no_issue_row_is_refused_not_raised_as_stopiteration(
    heart: Harness,
) -> None:
    """A FORM_INFON with its IssueRow stripped out must fail with a clear
    IntegrityError, not a bare StopIteration from an exhausted iterator."""
    heart.lifecycle()
    ((seq, record, _),) = heart.store.transitions()
    data = parse(record)
    assert isinstance(data, dict)
    data["issues"] = []
    forged = canonical_bytes(data)
    tamper(
        heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError, match="no IssueRow row left to apply"):
        rebuild(heart.store)


def test_an_extra_issue_row_not_consumed_by_any_operation_is_refused(heart: Harness) -> None:
    """Every row a transition carries must be consumed by exactly one
    operation (RPL-1). An extra `issues` row a forged, consistently
    re-digested record smuggles in has no operation to be `next()`-ed
    against, so no per-operation cardinality check catches it on its own;
    replay must still refuse rather than silently drop it.
    """
    heart.lifecycle()
    ((seq, record, _),) = heart.store.transitions()
    data = parse(record)
    assert isinstance(data, dict)
    issues = data["issues"]
    assert isinstance(issues, list)
    issues.append({"object": "infon:phantom", "issue": "sha256:" + "9" * 64})
    forged = canonical_bytes(data)
    tamper(
        heart.path,
        ("transitions_no_update",),
        "UPDATE transitions SET record = ?, record_digest = ? WHERE seq = ?",
        (forged, digest(forged), seq),
    )
    with pytest.raises(IntegrityError, match="more issues rows"):
        rebuild(heart.store)


def test_a_tampered_live_infon_issues_row_is_detected(heart: Harness) -> None:
    """Critical: `infon_issues` is part of Heart structure (INF-7, ISS-2), not
    a side table. A live row rewritten offline (guard dropped, then
    restored) must make the live-vs-replay digest disagree — otherwise
    `classify()` could see no member for the true issue and let the same
    claim be formed again as a first formation, reopening the clone/reset
    attack ISS-4 exists to close.
    """
    infon = form_testimony(heart.manifest.self_id, relation="R2")
    (infon_id,) = [h.id for h in heart.commit(infon).versions]
    before = heart_digest(heart.store)
    tamper(
        heart.path,
        ("infon_issues_no_update",),
        "UPDATE infon_issues SET issue_digest = ? WHERE object_id = ?",
        ("sha256:" + "f" * 64, infon_id),
    )
    assert heart_digest(heart.store) != before
    with pytest.raises(IntegrityError, match="differs from replay"):
        replay_current(heart.store)


def test_a_forged_form_infon_with_a_mismatched_issue_row_is_refused(heart: Harness) -> None:
    """A single transition's own IssueRow must name the object it forms and
    the issue its own EVD-7 justification claims — not some other pairing a
    forged record could otherwise get away with, even while every digest
    still matches itself.
    """
    infon = form_testimony(heart.manifest.self_id, relation="R2")
    heart.commit(infon)
    seq = heart.store.allocate_seq()
    forged_id = "infon:forged"
    provenance = Provenance(
        id=f"prov:{forged_id}",
        mode=Mode.TESTIMONY,
        inputs=(),
        operation=Operation.FORM_INFON,
        organ=MIND,
        seed_spec=None,
        seq=seq,
    )
    header = ObjectHeader(
        id=forged_id,
        type=ObjectType.INFON,
        version=1,
        provenance_id=provenance.id,
        derived_from=(),
        created_seq=seq,
        seq=seq,
        retired_by=None,
        forgotten=False,
        body_digest="sha256:" + "2" * 64,
    )
    check = Check(
        0,
        "EVD-7",
        {
            "issue": "sha256:" + "3" * 64,
            "classification": "first_formation",
            "inherited": [],
            "candidate": [{"kind": "testimony", "key": "mind"}],
            "novel": [{"kind": "testimony", "key": "mind"}],
        },
    )
    record = canonical_bytes(
        build_record(
            seq=seq,
            omega_id=heart.manifest.omega_id,
            proposer=MIND,
            reason="",
            operations=[OperationEntry(Operation.FORM_INFON, forged_id)],
            prior=[],
            provenance=[provenance],
            versions=[header],
            events=[EventRow(seq, 0, EventType.INFON_FORMED, forged_id)],
            justification=[check],
            # The IssueRow claims a DIFFERENT issue than the check just above.
            issues=[IssueRow(forged_id, "sha256:" + "4" * 64)],
        )
    )
    raw = heart.raw()
    raw.execute(
        "INSERT INTO transitions (seq, record, record_digest) VALUES (?, ?, ?)",
        (seq, record, digest(record)),
    )
    raw.close()
    with pytest.raises(IntegrityError, match="INF-7"):
        rebuild(heart.store)


def test_iss3_is_checked_at_every_point_not_only_the_final_state(heart: Harness) -> None:
    """Important #3: a history that ever holds two current heads for one
    issue is invalid even if a later transition retires one of them and the
    final state looks clean. Builds a real formation, then forges a second
    FORM_INFON on the same issue (a clone the validator itself would refuse,
    ISS-4), then forges a retirement of it — so the final state has exactly
    one current head, yet the lineage passed through an invalid state.
    """
    infon = form_testimony(heart.manifest.self_id, relation="R2")
    (a_header,) = [h for h in heart.commit(infon).versions if h.type is ObjectType.INFON]
    issue = heart.store.issue_of(a_header.id)
    assert issue is not None

    duplicate_seq = heart.store.allocate_seq()
    b_id = "infon:forged-duplicate"
    form_provenance = Provenance(
        id=f"prov:{b_id}",
        mode=Mode.TESTIMONY,
        inputs=(),
        operation=Operation.FORM_INFON,
        organ=MIND,
        seed_spec=None,
        seq=duplicate_seq,
    )
    b_header = ObjectHeader(
        id=b_id,
        type=ObjectType.INFON,
        version=1,
        provenance_id=form_provenance.id,
        derived_from=(),
        created_seq=duplicate_seq,
        seq=duplicate_seq,
        retired_by=None,
        forgotten=False,
        body_digest=a_header.body_digest,
    )
    # A real validator refuses a clone outright (ISS-4) and never commits it,
    # so there is no real transition to model this on. To reach the ISS-3
    # audit at all, the forged classification must itself be internally
    # consistent with what classify() recomputes here (CLONE, since A is
    # still K's current head) — otherwise the EVD-7 audit refuses it first,
    # for the right but different reason. That EVD-7 does not also refuse a
    # *committed* clone by classification alone is exactly why ISS-3 must
    # independently catch the duplicate head this leaves behind.
    form_check = Check(
        0,
        "EVD-7",
        {
            "issue": issue,
            "classification": "clone",
            "inherited": [{"kind": "testimony", "key": "mind"}],
            "candidate": [{"kind": "testimony", "key": "mind"}],
            "novel": [],
        },
    )
    form_record = canonical_bytes(
        build_record(
            seq=duplicate_seq,
            omega_id=heart.manifest.omega_id,
            proposer=MIND,
            reason="",
            operations=[OperationEntry(Operation.FORM_INFON, b_id)],
            prior=[],
            provenance=[form_provenance],
            versions=[b_header],
            events=[EventRow(duplicate_seq, 0, EventType.INFON_FORMED, b_id)],
            justification=[form_check],
            issues=[IssueRow(b_id, issue)],
        )
    )

    retire_seq = heart.store.allocate_seq()
    retire_provenance = Provenance(
        id=f"prov:{b_id}:retire",
        mode=Mode.REVISION,
        inputs=(ProvenanceInput(ObjectRef(b_id, 1), Role.REVISION_TARGET),),
        operation=Operation.REVISE_INFON,
        organ=MIND,
        seed_spec=None,
        seq=retire_seq,
    )
    retired_header = replace(
        b_header,
        version=2,
        provenance_id=retire_provenance.id,
        seq=retire_seq,
        retired_by=retire_seq,
        body_digest="sha256:" + "5" * 64,
    )
    retire_check = Check(
        0,
        "EVD-7",
        {
            "issue": issue,
            "classification": "administrative",
            "direction": None,
            "inherited": [{"kind": "testimony", "key": "mind"}],
            "candidate": [],
            "novel": [],
        },
    )
    retire_record = canonical_bytes(
        build_record(
            seq=retire_seq,
            omega_id=heart.manifest.omega_id,
            proposer=MIND,
            reason="",
            operations=[OperationEntry(Operation.REVISE_INFON, b_id)],
            prior=[ObjectRef(b_id, 1)],
            provenance=[retire_provenance],
            versions=[retired_header],
            events=[EventRow(retire_seq, 0, EventType.INFON_REVISED, b_id)],
            justification=[retire_check],
            issues=[],
        )
    )

    raw = heart.raw()
    raw.execute(
        "INSERT INTO transitions (seq, record, record_digest) VALUES (?, ?, ?)",
        (duplicate_seq, form_record, digest(form_record)),
    )
    raw.execute(
        "INSERT INTO transitions (seq, record, record_digest) VALUES (?, ?, ?)",
        (retire_seq, retire_record, digest(retire_record)),
    )
    raw.close()

    # The final state (A current, B retired) is clean on its own. The bug
    # this guards against checked exactly that and nothing else.
    with pytest.raises(IntegrityError, match="ISS-3"):
        rebuild(heart.store)
