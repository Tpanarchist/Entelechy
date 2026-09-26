"""Replay and read-only views of the Heart (Law 7).

ReplayCurrent(Origin, Lineage, ContentStore_live) = Heart_current.
Origin and lineage rebuild structure; the live content store supplies bytes.
"""

from collections.abc import Collection

from entelechy.foundation.canonical import CanonicalError, Json, digest_of, parse, verify
from entelechy.foundation.evidence import (
    Root,
    classify,
    ledger as _ledger_of,
    novel_roots,
    roots_of,
    roots_of_many,
    testimony_root,
)
from entelechy.foundation.seed import Manifest, seed_heart
from entelechy.foundation.store import Store
from entelechy.foundation.transitions import RecordError, decode_record
from entelechy.foundation.types import (
    EventRow,
    InfonBody,
    Mode,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Role,
    Rows,
    Stub,
    expect_int,
    expect_list,
    expect_object,
    field_of,
)


class IntegrityError(Exception):
    """Origin, lineage, the materialized Heart and content do not agree."""


def heart_digest(store: Store) -> str:
    """Digest of structure: every version header, provenance record, event and
    issue row. `infon_issues` is part of Heart structure (INF-7, ISS-2): it is
    what `classify()` and `Ledger(K)` read, so a live table that has drifted
    from lineage must be as visible here as a drifted `object_versions` row.
    """
    return digest_of(
        {
            "versions": [header.to_canonical() for header in store.versions()],
            "provenance": [item.to_canonical() for item in store.all_provenance()],
            "events": [event.to_canonical() for event in store.events()],
            "issues": [row.to_canonical() for row in store.issues()],
        }
    )


def rebuild(store: Store, up_to: int | None = None) -> Store:
    """Rebuild the Heart's structure in memory from origin and lineage alone."""
    omega_id, manifest_bytes, manifest_digest = store.origin()
    if not verify(manifest_bytes, manifest_digest):
        raise IntegrityError("the origin manifest does not match its digest")
    try:
        manifest = Manifest.from_bytes(manifest_bytes)
    except CanonicalError as error:
        raise IntegrityError(f"the origin manifest is malformed: {error}") from error
    if manifest.omega_id != omega_id:
        raise IntegrityError("the origin manifest names a different Ω")
    fresh = Store.memory()
    rows, _ = seed_heart(manifest)
    fresh.write_origin(omega_id, manifest_bytes, manifest_digest, rows, {})
    for seq, record, record_digest in store.transitions():
        if up_to is not None and seq > up_to:
            break
        if not verify(record, record_digest):
            fresh.close()
            raise IntegrityError(f"transition {seq} does not match its digest")
        try:
            data = parse(record)
            decoded = decode_record(data)
        except (CanonicalError, RecordError) as error:
            fresh.close()
            raise IntegrityError(f"transition {seq} is malformed: {error}") from error
        if decoded.seq != seq or decoded.omega_id != omega_id:
            fresh.close()
            raise IntegrityError(f"transition {seq} belongs to another seq or Ω")
        try:
            _audit_and_apply(data, decoded.rows, fresh)
        except BaseException:
            fresh.close()
            raise
    try:
        _audit_iss3(fresh)
    except BaseException:
        fresh.close()
        raise
    return fresh


def _roots_from_canonical(value: Json) -> frozenset[Root]:
    assert isinstance(value, list)
    result: set[Root] = set()
    for item in value:
        assert isinstance(item, dict)
        kind, key = item["kind"], item["key"]
        assert isinstance(kind, str) and isinstance(key, str)
        result.add(Root(kind, key))
    return frozenset(result)


def _text(data: dict[str, Json], key: str) -> str:
    value = field_of(data, key)
    if not isinstance(value, str):
        raise IntegrityError(f"malformed record: {key!r} is not a string")
    return value


def _audit_and_apply(record: Json, rows: Rows, reader: Store) -> None:
    """Apply one transition's rows operation by operation, checking EVD-7 for
    FORM_INFON and REVISE_INFON against `reader`'s state just before each
    operation — exactly the staged state the validator checked it against
    (EVD-3). One transition can consolidate an Observation and cite it in
    the same breath, so this cannot wait until the whole transition lands.
    """
    data = expect_object(record, "record")
    operations = expect_list(field_of(data, "operations"), "record.operations")
    justification_by_op: dict[int, list[dict[str, Json]]] = {}
    for entry in expect_list(field_of(data, "justification"), "record.justification"):
        check = expect_object(entry, "justification entry")
        if check.get("rule") != "EVD-7":
            continue
        op_index = expect_int(field_of(check, "operation"), "justification.operation")
        justification_by_op.setdefault(op_index, []).append(check)

    versions = iter(rows.versions)
    provenance = iter(rows.provenance)
    issues = iter(rows.issues)
    for op_index, operation_entry_raw in enumerate(operations):
        operation_entry = expect_object(operation_entry_raw, "operations[i]")
        operation_name = _text(operation_entry, "operation")
        object_id = _text(operation_entry, "object")
        version = next(versions)
        this_provenance = None if operation_name == "FORGET" else next(provenance)
        this_issue = next(issues) if operation_name == "FORM_INFON" else None

        # EVD-7: a FORM_INFON or REVISE_INFON MUST carry exactly one check;
        # every other operation MUST carry none. A deleted or duplicated
        # check is refused here, before it can be silently skipped or
        # silently accepted (§5 of the E001 spec).
        checks = justification_by_op.pop(op_index, [])
        evd7_applies = operation_name in ("FORM_INFON", "REVISE_INFON")
        if evd7_applies and len(checks) != 1:
            raise IntegrityError(
                f"operation {op_index} ({operation_name}) must carry exactly one "
                f"EVD-7 check; found {len(checks)}"
            )
        if not evd7_applies and checks:
            raise IntegrityError(
                f"operation {op_index} ({operation_name}) must not carry an EVD-7 check"
            )

        for check in checks:
            measured = expect_object(field_of(check, "measured"), "justification.measured")
            issue = _text(measured, "issue")
            assert this_provenance is not None
            inherited = _ledger_of(issue, reader)
            if operation_name == "FORM_INFON":
                # INF-7/ISS-2: the IssueRow this transition admits for the
                # formed object must name that same object and issue — not
                # some other one the live infon_issues table might carry.
                if this_issue is None or this_issue.object_id != object_id:
                    raise IntegrityError(
                        f"FORM_INFON of {object_id} carries no matching IssueRow (INF-7)"
                    )
                if this_issue.issue_digest != issue:
                    raise IntegrityError(
                        f"the IssueRow for {object_id} names a different issue than its "
                        "own EVD-7 justification (INF-7/ISS-2)"
                    )
                classification = classify(issue, reader)
                if classification.value != measured.get("classification"):
                    raise IntegrityError(
                        f"issue {issue} does not replay to the recorded ISS-4 classification"
                    )
                if this_provenance.mode is Mode.TESTIMONY:
                    assert this_provenance.organ is not None
                    candidate = frozenset({testimony_root(this_provenance.organ.id)})
                else:
                    candidate = roots_of_many(
                        (i.ref for i in this_provenance.inputs if i.role is Role.DERIVATION_INPUT),
                        reader,
                    )
            else:
                candidate = roots_of_many(
                    (
                        i.ref
                        for i in this_provenance.inputs
                        if i.role in (Role.SUPPORT, Role.COUNTEREVIDENCE)
                    ),
                    reader,
                )
            if inherited != _roots_from_canonical(field_of(measured, "inherited")):
                raise IntegrityError(f"Ledger({issue}) does not replay to what was recorded (EVD-7)")
            if candidate != _roots_from_canonical(field_of(measured, "candidate")):
                raise IntegrityError(f"candidate roots for {issue} do not replay (EVD-7)")
            if novel_roots(candidate, inherited) != _roots_from_canonical(field_of(measured, "novel")):
                raise IntegrityError(f"novel roots for {issue} do not replay (EVD-7)")

        reader.apply_replayed(
            Rows(
                provenance=() if this_provenance is None else (this_provenance,),
                versions=(version,),
                events=(),
                issues=() if this_issue is None else (this_issue,),
            )
        )
        _audit_iss3(reader)
    if justification_by_op:
        raise IntegrityError(
            f"EVD-7 checks reference operations that do not exist: {sorted(justification_by_op)}"
        )
    reader.apply_replayed(Rows(provenance=(), versions=(), events=rows.events, issues=()))


def _audit_iss3(reader: Store) -> None:
    """ISS-3: every issue has at most one current head, at every point in lineage.

    Called after every operation `_audit_and_apply` applies (and once more
    after the whole rebuild), not only once at the end: a history that ever
    held two current heads for one issue is invalid even if a later
    transition retires one of them and the final state looks clean.
    """
    issues: dict[str, list[str]] = {}
    for header in reader.versions():
        if header.type is not ObjectType.INFON or header.version != 1:
            continue
        issue = reader.issue_of(header.id)
        assert issue is not None
        issues.setdefault(issue, []).append(header.id)
    for issue, members in issues.items():
        heads = [
            object_id
            for object_id in members
            for latest in (reader.latest(object_id),)
            if latest is not None and latest.retired_by is None and not latest.forgotten
        ]
        if len(heads) > 1:
            raise IntegrityError(f"issue {issue} has more than one current head (ISS-3): {heads}")


def replay_current(store: Store) -> str:
    """Check the whole Heart against origin and lineage; return its digest (RPL-2)."""
    fresh = rebuild(store)
    try:
        rebuilt = heart_digest(fresh)
        if rebuilt != heart_digest(store):
            raise IntegrityError("the materialized Heart differs from replay of origin and lineage")
        versions = fresh.versions()
        forgotten = {header.id for header in versions if header.forgotten}
        for header in versions:
            if header.id in forgotten:
                continue
            data = store.content(header.body_digest)
            if data is None:
                raise IntegrityError(f"content of {header.id} v{header.version} is missing")
            if not verify(data, header.body_digest):
                raise IntegrityError(f"content of {header.id} v{header.version} was altered")
        return rebuilt
    finally:
        fresh.close()


class HeartView:
    """A read-only view of a Heart. Organs get this, never a Store."""

    def __init__(
        self,
        structure: Store,
        content: Store | None = None,
        forgotten_later: Collection[str] = (),
    ) -> None:
        self._structure = structure
        self._content = content if content is not None else structure
        self._forgotten_later = frozenset(forgotten_later)

    def latest(self, object_id: str) -> ObjectHeader | None:
        return self._structure.latest(object_id)

    def versions(self, object_id: str) -> list[ObjectHeader]:
        return self._structure.versions(object_id)

    def objects(self, object_type: ObjectType | None = None) -> list[ObjectHeader]:
        latest: dict[str, ObjectHeader] = {}
        for header in self._structure.versions():
            latest[header.id] = header
        return [h for h in latest.values() if object_type is None or h.type is object_type]

    def body(self, object_id: str, version: int | None = None) -> Json | Stub | None:
        """The PER-8 read path: any prior version, not only the latest."""
        if version is None:
            header = self.latest(object_id)
            missing_is_stub = False
        else:
            header = self._structure.header_at(ObjectRef(object_id, version))
            missing_is_stub = True
        if header is None:
            return None
        if header.forgotten or object_id in self._forgotten_later:
            return Stub.CONTENT_FORGOTTEN
        data = self._content.content(header.body_digest)
        if data is None:
            # A historical (non-latest) version's own header never gets
            # `forgotten` set — only the version FORGET itself produced does
            # (MEM-3) — yet FORGET purges every digest that version ever
            # used (unless another live object still needs it). Missing
            # content here is that, not corruption.
            if missing_is_stub:
                return Stub.CONTENT_FORGOTTEN
            raise IntegrityError(f"content of {object_id} is missing or altered")
        if not verify(data, header.body_digest):
            raise IntegrityError(f"content of {object_id} is missing or altered")
        return parse(data)

    def infon(self, object_id: str, version: int | None = None) -> InfonBody | Stub | None:
        body = self.body(object_id, version)
        if body is None or isinstance(body, Stub):
            return body
        return InfonBody.from_canonical(body)

    def roots(self, object_id: str, version: int | None = None) -> frozenset[Root]:
        """Roots(x@v) (ROT-6/ROT-7), recomputed on demand, never stored."""
        header = self.latest(object_id) if version is None else self._structure.header_at(
            ObjectRef(object_id, version)
        )
        if header is None:
            raise ValueError(f"no such object version {object_id}@{version}")
        return roots_of(header.ref(), self._structure)

    def grounded(self, object_id: str, version: int | None = None) -> bool:
        """grounded(x@v) := Roots(x@v) != empty (ROT-8)."""
        return bool(self.roots(object_id, version))

    def issue(self, object_id: str) -> str | None:
        """The IssueDigest an Infon was formed with (INF-7, ISS-2), or None."""
        return self._structure.issue_of(object_id)

    def head(self, issue: str) -> str | None:
        """The current head of `issue` (ISS-3): its id, or None if it has none."""
        for object_id in self._structure.infon_ids_for_issue(issue):
            latest = self._structure.latest(object_id)
            if latest is not None and latest.retired_by is None and not latest.forgotten:
                return object_id
        return None

    def ledger(self, issue: str) -> frozenset[Root]:
        """Ledger(K) (ISS-7): every root ever admitted into this issue's history."""
        return _ledger_of(issue, self._structure)

    def events(self) -> list[EventRow]:
        return self._structure.events()

    def digest(self) -> str:
        return heart_digest(self._structure)


def replay_historical(store: Store, seq: int, content: Store | None = None) -> HeartView:
    """The Heart as it stood at `seq` (RPL-4). Later-forgotten content is a stub.

    `content` is where the view reads live bytes from; it defaults to `store`.
    """
    if seq < 0:
        raise ValueError("seq must not be negative")
    fresh = rebuild(store, up_to=seq)
    forgotten_now = {header.id for header in store.versions() if header.forgotten}
    return HeartView(
        fresh, content=store if content is None else content, forgotten_later=forgotten_now
    )
