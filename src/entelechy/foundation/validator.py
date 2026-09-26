"""The validator knows the laws but does not think.

It checks each proposal against FOUNDATIONS.md and returns either an
AcceptedTransition or a structured Rejection. It never generates content,
and only it can construct an AcceptedTransition (Law 5).
"""

import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Protocol

from entelechy.foundation.canonical import (
    Canonical,
    CanonicalError,
    canonical_bytes,
    decimal_text,
    digest,
    parse,
)
from entelechy.foundation.evidence import (
    Classification,
    Root,
    classify,
    issue_digest,
    ledger,
    novel_roots,
    roots_of_many,
    testimony_root,
)
from entelechy.foundation.seed import Manifest
from entelechy.foundation.types import (
    V1_OPERATIONS,
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
    ObjectRef,
    ObjectReferent,
    ObjectType,
    Observation,
    OpaqueReferent,
    Operation,
    OperationEntry,
    OtherOperation,
    Polarity,
    Proposal,
    ProposedOperation,
    Provenance,
    ProvenanceInput,
    Referent,
    RegionReferent,
    ReviseInfon,
    Role,
    RoleInput,
)

UNIMPLEMENTED = "V1-UNIMPLEMENTED"
CERTAINTY = "V1-CERTAINTY"

_CAPABILITY = object()


class RetentionPolicy(Protocol):
    """The retention function f (OPEN-5). Declared in the seed; there is no default."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def score(self, object_type: ObjectType, body: bytes) -> Decimal: ...


class HeartReader(Protocol):
    def latest(self, object_id: str) -> ObjectHeader | None: ...

    def versions(self, object_id: str | None = None) -> list[ObjectHeader]: ...

    def content(self, body_digest: str) -> bytes | None: ...

    def provenance(self, provenance_id: str) -> Provenance | None: ...

    def header_at(self, ref: ObjectRef) -> ObjectHeader | None: ...

    def infon_ids_for_issue(self, issue: str) -> Iterable[str]: ...

    def versions_of(self, object_id: str) -> Sequence[ObjectHeader]: ...

    def issue_of(self, object_id: str) -> str | None: ...


@dataclass(frozen=True)
class Violation:
    rule: str
    explanation: str
    measured: Mapping[str, Canonical] = field(default_factory=dict)


@dataclass(frozen=True)
class Rejection:
    """Why a proposal was refused. Transient in v1; organs can learn from it."""

    proposal: Proposal
    operation: int | None
    violations: tuple[Violation, ...]

    @property
    def rules(self) -> frozenset[str]:
        return frozenset(violation.rule for violation in self.violations)

    def __str__(self) -> str:
        lines = ["REJECTED"]
        lines += [f"    {v.rule}  {v.explanation}" for v in self.violations]
        return "\n".join(lines)


@dataclass(frozen=True)
class AcceptedTransition:
    seq: int
    proposal: Proposal
    operations: tuple[OperationEntry, ...]
    prior: tuple[ObjectRef, ...]
    provenance: tuple[Provenance, ...]
    versions: tuple[ObjectHeader, ...]
    events: tuple[EventRow, ...]
    justification: tuple[Check, ...]
    bodies: Mapping[str, bytes]
    issues: tuple[IssueRow, ...] = ()
    capability: object = field(repr=False, compare=False, kw_only=True)

    def __post_init__(self) -> None:
        if self.capability is not _CAPABILITY:
            raise PermissionError("only the validator can accept a transition (Law 5)")


def _new_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


class _Work:
    """The Heart as it will be once the operations validated so far commit."""

    def __init__(self, seq: int, heart: HeartReader, transient: Mapping[str, Observation]):
        self.seq = seq
        self.heart = heart
        self.transient = transient
        self.operations: list[OperationEntry] = []
        self.prior: list[ObjectRef] = []
        self.provenance: list[Provenance] = []
        self.versions: list[ObjectHeader] = []
        self.events: list[EventRow] = []
        self.checks: list[Check] = []
        self.bodies: dict[str, bytes] = {}
        self.issues: list[IssueRow] = []
        self._latest: dict[str, ObjectHeader] = {}
        self._provenance: dict[str, Provenance] = {}
        self._issue_of: dict[str, str] = {}
        self._issue_members: dict[str, list[str]] = {}

    def latest(self, object_id: str) -> ObjectHeader | None:
        staged = self._latest.get(object_id)
        return staged if staged is not None else self.heart.latest(object_id)

    def versions_of(self, object_id: str) -> list[ObjectHeader]:
        staged = [header for header in self.versions if header.id == object_id]
        return self.heart.versions(object_id) + staged

    def header_at(self, ref: ObjectRef) -> ObjectHeader | None:
        for header in self.versions:
            if header.id == ref.id and header.version == ref.version:
                return header
        return self.heart.header_at(ref)

    def content(self, body_digest: str) -> bytes | None:
        staged = self.bodies.get(body_digest)
        return staged if staged is not None else self.heart.content(body_digest)

    def provenance_of(self, provenance_id: str) -> Provenance | None:
        staged = self._provenance.get(provenance_id)
        return staged if staged is not None else self.heart.provenance(provenance_id)

    def issue_of(self, object_id: str) -> str | None:
        staged = self._issue_of.get(object_id)
        return staged if staged is not None else self.heart.issue_of(object_id)

    def infon_ids_for_issue(self, issue: str) -> list[str]:
        persisted = list(self.heart.infon_ids_for_issue(issue))
        staged = self._issue_members.get(issue, [])
        return persisted + [object_id for object_id in staged if object_id not in persisted]

    def stage(self, header: ObjectHeader, provenance: Provenance | None, body: bytes | None) -> None:
        self._latest[header.id] = header
        self.versions.append(header)
        if provenance is not None:
            self._provenance[provenance.id] = provenance
            self.provenance.append(provenance)
        if body is not None:
            self.bodies[header.body_digest] = body

    def stage_issue(self, object_id: str, issue: str) -> None:
        self.issues.append(IssueRow(object_id, issue))
        self._issue_of[object_id] = issue
        self._issue_members.setdefault(issue, []).append(object_id)

    def emit(self, event_type: EventType, object_id: str) -> None:
        self.events.append(EventRow(self.seq, len(self.events), event_type, object_id))


def _cited_inputs(operation: ProposedOperation) -> tuple[str, ...]:
    match operation:
        case FormInfon(inputs=inputs):
            return tuple(item.object_id for item in inputs)
        case ReviseInfon(evidence=evidence):
            return tuple(item.object_id for item in evidence)
        case _:
            return ()


class Validator:
    def __init__(
        self,
        manifest: Manifest,
        policy: RetentionPolicy | None,
        new_id: Callable[[str], str] = _new_id,
    ) -> None:
        self._manifest = manifest
        self._policy = policy
        self._new_id = new_id

    def validate(
        self,
        proposal: Proposal,
        seq: int,
        heart: HeartReader,
        transient: Mapping[str, Observation],
    ) -> AcceptedTransition | Rejection:
        violations = self._check_proposal(proposal)
        if violations:
            return Rejection(proposal, None, tuple(violations))
        work = _Work(seq, heart, transient)
        for index, operation in enumerate(proposal.operations):
            violations = self._apply(index, operation, proposal, work)
            if violations:
                return Rejection(proposal, index, tuple(violations))
        return AcceptedTransition(
            seq=seq,
            proposal=proposal,
            operations=tuple(work.operations),
            prior=tuple(work.prior),
            provenance=tuple(work.provenance),
            versions=tuple(work.versions),
            events=tuple(work.events),
            justification=tuple(work.checks),
            bodies=dict(work.bodies),
            issues=tuple(work.issues),
            capability=_CAPABILITY,
        )

    def _check_proposal(self, proposal: Proposal) -> list[Violation]:
        violations: list[Violation] = []
        if proposal.organ not in self._manifest.organs:
            violations.append(
                Violation(
                    "ORG-2",
                    f"organ {proposal.organ.id}@{proposal.organ.version} is not registered",
                    {"organ": proposal.organ.to_canonical()},
                )
            )
        if not proposal.operations:
            violations.append(Violation("PER-6", "a transition must produce new state"))
        return violations

    def _apply(
        self, index: int, operation: ProposedOperation, proposal: Proposal, work: _Work
    ) -> list[Violation]:
        match operation:
            case Consolidate():
                return self._consolidate(index, operation, proposal, work)
            case FormInfon():
                return self._form_infon(index, operation, proposal, work)
            case ReviseInfon():
                return self._revise_infon(index, operation, proposal, work)
            case Forget():
                return self._forget(index, operation, work)
            case OtherOperation():
                return self._other(operation)

    # CONSOLIDATE

    def _consolidate(
        self, index: int, op: Consolidate, proposal: Proposal, work: _Work
    ) -> list[Violation]:
        if work.latest(op.observation_id) is not None:
            return [Violation("PER-3", f"{op.observation_id} is already persistent")]
        observation = work.transient.get(op.observation_id)
        if observation is None:
            return [Violation("PER-3", f"there is no transient Observation {op.observation_id}")]
        body = canonical_bytes(observation.body())
        citing = [
            later
            for later in range(index + 1, len(proposal.operations))
            if op.observation_id in _cited_inputs(proposal.operations[later])
        ]
        if citing:
            check = Check(index, "MEM-1", {"clause": "evidence", "cited_by_operation": citing[0]})
        else:
            outcome = self._retention(
                index, ObjectType.OBSERVATION, body, "MEM-1", "theta_retain", at_least=True
            )
            if isinstance(outcome, Violation):
                return [outcome]
            check = outcome
        provenance = Provenance(
            id=self._new_id("prov"),
            mode=Mode.SELF_OBSERVATION
            if self._manifest.is_interoceptive(observation.channel)
            else Mode.OBSERVATION,
            inputs=(),
            operation=Operation.CONSOLIDATE,
            organ=observation.channel,
            seed_spec=None,
            seq=work.seq,
        )
        header = ObjectHeader(
            id=observation.id,
            type=ObjectType.OBSERVATION,
            version=1,
            provenance_id=provenance.id,
            derived_from=(),
            created_seq=work.seq,
            seq=work.seq,
            retired_by=None,
            forgotten=False,
            body_digest=digest(body),
        )
        work.stage(header, provenance, body)
        work.operations.append(OperationEntry(Operation.CONSOLIDATE, observation.id))
        work.checks.append(check)
        work.emit(EventType.MEMORY_CONSOLIDATED, observation.id)
        return []

    def _retention(
        self,
        index: int,
        object_type: ObjectType,
        body: bytes,
        rule: str,
        parameter: str,
        *,
        at_least: bool,
    ) -> Check | Violation:
        threshold = (
            self._manifest.theta_retain
            if parameter == "theta_retain"
            else self._manifest.theta_forget
        )
        unbound: dict[str, Canonical] = {}
        if threshold is None:
            unbound[parameter] = "unbound"
        if self._policy is None:
            unbound["retention_policy"] = "unbound"
        if threshold is None or self._policy is None:
            return Violation(rule, "the retention clause needs a bound parameter and policy", unbound)
        score = self._policy.score(object_type, body)
        try:
            score_text = decimal_text(score)
        except CanonicalError as error:
            return Violation(rule, f"the retention policy returned an unusable score: {error}")
        measured: dict[str, Canonical] = {
            "clause": "retention",
            "score": score_text,
            parameter: decimal_text(threshold),
            "policy": f"{self._policy.name}@{self._policy.version}",
        }
        passed = score >= threshold if at_least else score <= threshold
        if not passed:
            return Violation(rule, "the retention score does not meet the threshold", measured)
        return Check(index, rule, measured)

    # FORM_INFON

    def _form_infon(
        self, index: int, op: FormInfon, proposal: Proposal, work: _Work
    ) -> list[Violation]:
        violations: list[Violation] = []
        if op.polarity is Polarity.NEGATIVE:
            violations.append(
                Violation(UNIMPLEMENTED, "negative Infons need a negative-evidence contract (INF-6)")
            )
        if op.relation not in self._manifest.relations:
            violations.append(
                Violation("INF-1", f"relation {op.relation!r} is not in the seed vocabulary")
            )
        violations += _certainty(op.confidence)
        try:
            canonical_bytes(op.context)
        except CanonicalError as error:
            violations.append(Violation("INF-1", f"context has no canonical form: {error}"))
        for referent in op.participants:
            violations += self._referent(referent, work)
        for item in op.inputs:
            if item.role not in (Role.DERIVATION_INPUT, Role.ATTRIBUTION):
                violations.append(
                    Violation(
                        "ROL-3",
                        f"FORM_INFON cannot use role {item.role.value}",
                        {"object": item.object_id},
                    )
                )
        resolved, input_violations = _resolve_role_inputs(op.inputs, work)
        violations += input_violations
        for predecessor in op.derived_from:
            if work.latest(predecessor) is None:
                violations.append(Violation("OBJ-4", f"predecessor {predecessor} does not exist"))
        if violations:
            return violations

        # PRV-8: mode is derived from the roles present, never supplied by the organ.
        if not resolved:
            mode = Mode.TESTIMONY
        elif all(item.role is Role.ATTRIBUTION for item in resolved):
            mode = Mode.ATTRIBUTED
        else:
            mode = Mode.DERIVATION

        issue = issue_digest(op.relation, op.participants, op.context)
        classification = classify(issue, work)
        if classification is Classification.CLONE:
            return [
                Violation(
                    "ISS-4",
                    "this issue already has a current head; revise it instead of cloning it",
                    {"issue": issue},
                )
            ]

        inherited = ledger(issue, work)
        if mode is Mode.TESTIMONY:
            candidate = frozenset({testimony_root(proposal.organ.id)})
        else:
            candidate = roots_of_many(
                (item.ref for item in resolved if item.role is Role.DERIVATION_INPUT), work
            )
        novel = novel_roots(candidate, inherited)
        if classification is Classification.RE_FORMATION and not novel:
            return [
                Violation(
                    "ISS-4",
                    "re-formation requires new evidence: no root in this formation is novel to the issue",
                    {"issue": issue},
                )
            ]

        infon = InfonBody(
            relation=op.relation,
            participants=op.participants,
            polarity=op.polarity,
            context=op.context,
            confidence=op.confidence,
            status=InfonStatus.ACTIVE,
        )
        body = canonical_bytes(infon.to_canonical())
        provenance = Provenance(
            id=self._new_id("prov"),
            mode=mode,
            inputs=resolved,
            operation=Operation.FORM_INFON,
            organ=proposal.organ,
            seed_spec=None,
            seq=work.seq,
        )
        header = ObjectHeader(
            id=self._new_id("infon"),
            type=ObjectType.INFON,
            version=1,
            provenance_id=provenance.id,
            derived_from=op.derived_from,
            created_seq=work.seq,
            seq=work.seq,
            retired_by=None,
            forgotten=False,
            body_digest=digest(body),
        )
        work.stage(header, provenance, body)
        work.stage_issue(header.id, issue)
        work.operations.append(OperationEntry(Operation.FORM_INFON, header.id))
        work.checks += [
            Check(index, "INF-1", {"relation_in_vocabulary": True}),
            Check(index, "REF-1", {"participants": len(op.participants)}),
            Check(index, "PRV-4", {"inputs": len(resolved)}),
            Check(index, CERTAINTY, {"open_interval": True}),
            Check(
                index,
                "EVD-7",
                {
                    "issue": issue,
                    "classification": classification.value,
                    "inherited": _roots_canonical(inherited),
                    "candidate": _roots_canonical(candidate),
                    "novel": _roots_canonical(novel),
                },
            ),
        ]
        work.emit(EventType.INFON_FORMED, header.id)
        return []

    def _referent(self, referent: Referent, work: _Work) -> list[Violation]:
        match referent:
            case ObjectReferent(object_id=object_id):
                if work.latest(object_id) is None:
                    return [_missing("REF-1", "participant", object_id, work)]
                return []
            case RegionReferent(observation_id=observation_id, region=region):
                violations = _persisted_observation(observation_id, work)
                try:
                    canonical_bytes(region)
                except CanonicalError as error:
                    violations.append(Violation("REF-1", f"region has no canonical form: {error}"))
                return violations
            case OpaqueReferent(observation_id=observation_id, identifier=identifier):
                violations = _persisted_observation(observation_id, work)
                if violations:
                    return violations
                header = work.latest(observation_id)
                assert header is not None
                data = None if header.forgotten else work.content(header.body_digest)
                if data is None:
                    return [Violation("REF-1", f"the content of {observation_id} is forgotten")]
                observation = Observation.from_body(observation_id, parse(data))
                if identifier not in observation.identifiers:
                    return [
                        Violation(
                            "REF-1",
                            f"{observation_id} did not introduce identifier {identifier!r}",
                        )
                    ]
                return []

    # REVISE_INFON

    def _revise_infon(
        self, index: int, op: ReviseInfon, proposal: Proposal, work: _Work
    ) -> list[Violation]:
        header = work.latest(op.infon_id)
        if header is None:
            return [_missing("TRN-3", "Infon", op.infon_id, work)]
        if header.type is ObjectType.OBSERVATION:
            return [Violation("OBS-1", "Observations are never edited; revise the Infons instead")]
        if header.type is not ObjectType.INFON:
            return [Violation("TRN-1", f"REVISE_INFON applies only to Infons, not {header.type}")]
        if header.forgotten:
            return [Violation("MEM-3", f"the content of {op.infon_id} is forgotten")]
        if header.retired_by is not None:
            return [Violation("OBJ-3", f"{op.infon_id} is retired; retired objects are final")]
        if op.expected_version != header.version:
            return [
                Violation(
                    "PER-6",
                    "the proposal revises a stale version",
                    {"expected": op.expected_version, "current": header.version},
                )
            ]
        data = work.content(header.body_digest)
        if data is None:
            return [Violation("MEM-3", f"the content of {op.infon_id} is missing")]
        current = InfonBody.from_canonical(parse(data))

        # A confidence that fails V1-CERTAINTY cannot be encoded or compared,
        # so nothing else about the proposed body can be judged.
        certainty = _certainty(op.body.confidence)
        if certainty:
            return certainty
        try:
            proposed = _field_bytes(op.body)
        except CanonicalError as error:
            return [Violation("INF-1", f"the revised body has no canonical form: {error}")]
        existing = _field_bytes(current)

        # Compare canonical encodings, never Python equality: 1 == True and
        # 1 == 1.0 in Python, but they are different content.
        violations: list[Violation] = []
        content_changes = [
            name
            for name in ("relation", "participants", "polarity", "context")
            if proposed[name] != existing[name]
        ]
        trust_changes = [name for name in ("confidence", "status") if proposed[name] != existing[name]]
        if content_changes:
            violations.append(
                Violation(
                    "INF-4",
                    "REVISE_INFON changes only confidence and status",
                    {"changed": content_changes},
                )
            )
            violations.append(
                Violation("OBJ-4", "a content change creates a successor: use FORM_INFON")
            )
        elif not trust_changes:
            violations.append(Violation("INF-4", "the revision changes nothing"))
        if violations:
            return violations

        # ROL-3: revision may cite support, counterevidence and attribution;
        # revision_target is added below, by the validator, never by an organ.
        for item in op.evidence:
            if item.role not in (Role.SUPPORT, Role.COUNTEREVIDENCE, Role.ATTRIBUTION):
                violations.append(
                    Violation(
                        "ROL-3",
                        f"REVISE_INFON cannot use role {item.role.value}",
                        {"object": item.object_id},
                    )
                )
        resolved, evidence_violations = _resolve_role_inputs(op.evidence, work)
        violations += evidence_violations
        if violations:
            return violations

        # ROL-4: direction. Upward raises confidence or moves contradicted ->
        # active; downward lowers confidence or moves active -> contradicted.
        # Moving both ways at once is refused.
        directions: set[str] = set()
        if op.body.confidence > current.confidence:
            directions.add("up")
        if op.body.confidence < current.confidence:
            directions.add("down")
        if current.status is InfonStatus.CONTRADICTED and op.body.status is InfonStatus.ACTIVE:
            directions.add("up")
        if current.status is InfonStatus.ACTIVE and op.body.status is InfonStatus.CONTRADICTED:
            directions.add("down")
        if len(directions) > 1:
            return [
                Violation("ROL-4", "a revision that moves both upward and downward at once is refused")
            ]
        direction = next(iter(directions), None)

        issue = work.issue_of(header.id)
        assert issue is not None, "every committed Infon was formed with an issue (INF-7)"
        inherited = ledger(issue, work)
        support = tuple(item.ref for item in resolved if item.role is Role.SUPPORT)
        counterevidence = tuple(item.ref for item in resolved if item.role is Role.COUNTEREVIDENCE)

        # EVD-5: an administrative change (a move to retired with confidence
        # unchanged) needs no evidence and must not admit any.
        is_administrative = op.body.status is InfonStatus.RETIRED and direction is None
        if is_administrative:
            if support or counterevidence:
                return [
                    Violation(
                        "EVD-5", "an administrative change must not admit support or counterevidence"
                    )
                ]
            candidate: frozenset[Root] = frozenset()
            novel: frozenset[Root] = frozenset()
            classification = "administrative"
        else:
            candidate_support = roots_of_many(support, work)
            candidate_counterevidence = roots_of_many(counterevidence, work)
            novel_support = novel_roots(candidate_support, inherited)
            novel_counterevidence = novel_roots(candidate_counterevidence, inherited)
            # EVD-4 asks whether there is new evidence at all; ROL-4 asks,
            # only once EVD-4 is satisfied, whether it is on the side the
            # direction requires. Citing the target, or anything else already
            # in the issue's ledger, fails EVD-4 by itself (§4.3): there is
            # nothing special-cased about self-citation.
            if not (novel_support or novel_counterevidence):
                violations.append(Violation("EVD-4", "a trust change requires new evidence"))
            elif direction == "up" and not novel_support:
                violations.append(
                    Violation("ROL-4", "an upward change requires a novel root from a support input")
                )
            elif direction == "down" and not novel_counterevidence:
                violations.append(
                    Violation(
                        "ROL-4",
                        "a downward change requires a novel root from a counterevidence input",
                    )
                )
            if violations:
                return violations
            candidate = candidate_support | candidate_counterevidence
            novel = novel_support | novel_counterevidence
            classification = "trust_change"

        # The revised commitment inherits the roots of the version it revises
        # (Law 9) and whatever the cited evidence itself is rooted in.
        body = canonical_bytes(op.body.to_canonical())
        provenance = Provenance(
            id=self._new_id("prov"),
            mode=Mode.REVISION,
            inputs=(ProvenanceInput(header.ref(), Role.REVISION_TARGET), *resolved),
            operation=Operation.REVISE_INFON,
            organ=proposal.organ,
            seed_spec=None,
            seq=work.seq,
        )
        revised = replace(
            header,
            version=header.version + 1,
            provenance_id=provenance.id,
            seq=work.seq,
            retired_by=work.seq if op.body.status is InfonStatus.RETIRED else None,
            body_digest=digest(body),
        )
        work.prior.append(header.ref())
        work.stage(revised, provenance, body)
        work.operations.append(OperationEntry(Operation.REVISE_INFON, header.id))
        work.checks += [
            Check(index, "INF-4", {"changed": trust_changes}),
            Check(
                index,
                "EVD-7",
                {
                    "issue": issue,
                    "classification": classification,
                    "direction": direction,
                    "inherited": _roots_canonical(inherited),
                    "candidate": _roots_canonical(candidate),
                    "novel": _roots_canonical(novel),
                },
            ),
            Check(index, CERTAINTY, {"open_interval": True}),
        ]
        work.emit(EventType.INFON_REVISED, header.id)
        return []

    # FORGET

    def _forget(self, index: int, op: Forget, work: _Work) -> list[Violation]:
        header = work.latest(op.object_id)
        if header is None:
            if op.object_id in work.transient:
                return [Violation("MEM-3", "transient state lapses on its own; FORGET is for the Heart")]
            return [Violation("TRN-3", f"there is no persistent object {op.object_id}")]
        provenance = work.provenance_of(header.provenance_id)
        if provenance is not None and provenance.mode is Mode.ORIGIN:
            return [Violation("MEM-4", "seed structure cannot be forgotten")]
        if header.forgotten:
            return [Violation("MEM-3", f"{op.object_id} is already forgotten")]
        if op.expected_version != header.version:
            return [
                Violation(
                    "PER-6",
                    "the proposal forgets a stale version",
                    {"expected": op.expected_version, "current": header.version},
                )
            ]
        if op.successor is not None:
            return [Violation(UNIMPLEMENTED, "compression into a successor needs Patterns or Forms")]
        if not op.reason.strip():
            return [Violation("MEM-3", "FORGET requires a reason")]
        body = work.content(header.body_digest)
        if body is None:
            return [Violation("MEM-3", f"the content of {op.object_id} is missing")]
        outcome = self._retention(index, header.type, body, "MEM-2", "theta_forget", at_least=False)
        if isinstance(outcome, Violation):
            return [outcome]

        forgotten = replace(
            header,
            version=header.version + 1,
            seq=work.seq,
            retired_by=header.retired_by if header.retired_by is not None else work.seq,
            forgotten=True,
        )
        work.prior.append(header.ref())
        work.stage(forgotten, None, None)
        work.operations.append(OperationEntry(Operation.FORGET, header.id, op.reason))
        work.checks.append(outcome)
        work.emit(EventType.MEMORY_FORGOTTEN, header.id)
        return []

    # Everything else

    def _other(self, op: OtherOperation) -> list[Violation]:
        if op.name in {operation.value for operation in V1_OPERATIONS}:
            return [Violation("TRN-2", f"{op.name} must be proposed with its typed operation")]
        if op.name in {operation.value for operation in Operation}:
            return [Violation(UNIMPLEMENTED, f"{op.name} is legal in FOUNDATIONS but not built in v1")]
        return [Violation("TRN-1", f"{op.name} is not a legal operation")]


def _certainty(confidence: Decimal) -> list[Violation]:
    if not (confidence.is_finite() and Decimal(0) < confidence < Decimal(1)):
        return [
            Violation(
                CERTAINTY,
                "v1 cannot establish certainty; confidence must be strictly between 0 and 1",
                {"confidence": str(confidence)},
            )
        ]
    # The checked value must be exactly the stored value, so it must encode.
    try:
        decimal_text(confidence)
    except CanonicalError as error:
        return [Violation("INF-1", f"confidence has no canonical form: {error}")]
    return []


def _field_bytes(body: InfonBody) -> dict[str, bytes]:
    return {name: canonical_bytes(value) for name, value in body.to_canonical().items()}


def _missing(rule: str, role: str, object_id: str, work: _Work) -> Violation:
    if object_id in work.transient:
        return Violation(rule, f"{role} {object_id} is transient", {"object": object_id})
    return Violation(rule, f"{role} {object_id} does not exist", {"object": object_id})


def _persisted_observation(observation_id: str, work: _Work) -> list[Violation]:
    header = work.latest(observation_id)
    if header is None:
        return [_missing("REF-1", "participant", observation_id, work)]
    if header.type is not ObjectType.OBSERVATION:
        return [Violation("REF-1", f"{observation_id} is not an Observation")]
    return []


def _resolve_role_inputs(
    items: Sequence[RoleInput], work: _Work
) -> tuple[tuple[ProvenanceInput, ...], list[Violation]]:
    resolved: list[ProvenanceInput] = []
    violations: list[Violation] = []
    for item in items:
        header = work.latest(item.object_id)
        if header is None:
            violations.append(_missing("PRV-4", "provenance input", item.object_id, work))
            continue
        resolved.append(ProvenanceInput(header.ref(), item.role))
        if item.role is Role.ATTRIBUTION and header.type is not ObjectType.OBSERVATION:
            violations.append(
                Violation(
                    "ROL-3",
                    "an attribution input must be a persisted Observation",
                    {"object": item.object_id},
                )
            )
    return tuple(resolved), violations


def _roots_canonical(roots: frozenset[Root]) -> list[Canonical]:
    return [item.to_canonical() for item in sorted(roots, key=lambda item: (item.kind, item.key))]
