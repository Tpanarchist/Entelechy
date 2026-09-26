"""Normative structures of FOUNDATIONS.md that Validator v1 needs.

Every persistent structure converts to and from canonical form, so what is
hashed and stored is exactly what replay decodes again.
"""

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from entelechy.foundation.canonical import Canonical, CanonicalError, Json, decimal_text


class ObjectType(enum.StrEnum):
    OBSERVATION = "Observation"
    INFON = "Infon"
    SELF_MAP_ENTRY = "SelfMapEntry"


class Mode(enum.StrEnum):
    """Production mode (FOUNDATIONS §5). Assigned by the kernel or validator; no organ supplies it (PRV-8)."""

    ORIGIN = "origin"
    OBSERVATION = "observation"
    SELF_OBSERVATION = "self-observation"
    TESTIMONY = "testimony"
    ATTRIBUTED = "attributed"
    DERIVATION = "derivation"
    REVISION = "revision"
    SIMULATION = "simulation"
    EXPERIMENT = "experiment"


class Role(enum.StrEnum):
    """A provenance input's role (ROL-1). Governs whether it passes roots and to what it is eligible."""

    SUPPORT = "support"
    COUNTEREVIDENCE = "counterevidence"
    DERIVATION_INPUT = "derivation_input"
    REVISION_TARGET = "revision_target"
    ATTRIBUTION = "attribution"


class Polarity(enum.StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class InfonStatus(enum.StrEnum):
    ACTIVE = "active"
    CONTRADICTED = "contradicted"
    RETIRED = "retired"


class Operation(enum.StrEnum):
    """Every legal operation in FOUNDATIONS §10."""

    CONSOLIDATE = "CONSOLIDATE"
    FORM_INFON = "FORM_INFON"
    REVISE_INFON = "REVISE_INFON"
    DISCOVER_PATTERN = "DISCOVER_PATTERN"
    CRYSTALLIZE_FORM = "CRYSTALLIZE_FORM"
    REVISE_FORM = "REVISE_FORM"
    PROPOSE_MODEL = "PROPOSE_MODEL"
    REVISE_MODEL = "REVISE_MODEL"
    CHANGE_MODEL_STATUS = "CHANGE_MODEL_STATUS"
    RECORD_PREDICTION = "RECORD_PREDICTION"
    RECORD_OUTCOME = "RECORD_OUTCOME"
    COMPILE_SKILL = "COMPILE_SKILL"
    RECORD_SKILL_OUTCOME = "RECORD_SKILL_OUTCOME"
    CHANGE_SKILL_DEPTH = "CHANGE_SKILL_DEPTH"
    REVISE_SKILL = "REVISE_SKILL"
    UPDATE_SELF_MAP = "UPDATE_SELF_MAP"
    CHANGE_GOAL = "CHANGE_GOAL"
    FORGET = "FORGET"
    CHANGE_ORGAN = "CHANGE_ORGAN"
    RECORD_RESOURCE_THRESHOLD = "RECORD_RESOURCE_THRESHOLD"


V1_OPERATIONS = frozenset(
    {Operation.CONSOLIDATE, Operation.FORM_INFON, Operation.REVISE_INFON, Operation.FORGET}
)


class EventType(enum.StrEnum):
    MEMORY_CONSOLIDATED = "MEMORY_CONSOLIDATED"
    INFON_FORMED = "INFON_FORMED"
    INFON_REVISED = "INFON_REVISED"
    MEMORY_FORGOTTEN = "MEMORY_FORGOTTEN"


class Stub(enum.Enum):
    """Stands in for content that FORGET removed (RPL-4)."""

    CONTENT_FORGOTTEN = "CONTENT_FORGOTTEN"


# Decoding helpers. They turn malformed canonical data into CanonicalError.


def field_of(data: dict[str, Json], key: str) -> Json:
    if key not in data:
        raise CanonicalError(f"missing field {key!r}")
    return data[key]


def expect_object(value: Json, what: str) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise CanonicalError(f"{what}: expected an object")
    return value


def expect_list(value: Json, what: str) -> list[Json]:
    if not isinstance(value, list):
        raise CanonicalError(f"{what}: expected a list")
    return value


def expect_text(value: Json, what: str) -> str:
    if not isinstance(value, str):
        raise CanonicalError(f"{what}: expected a string")
    return value


def expect_int(value: Json, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonicalError(f"{what}: expected an integer")
    return value


def expect_bool(value: Json, what: str) -> bool:
    if not isinstance(value, bool):
        raise CanonicalError(f"{what}: expected a boolean")
    return value


def expect_optional_int(value: Json, what: str) -> int | None:
    return None if value is None else expect_int(value, what)


def expect_optional_text(value: Json, what: str) -> str | None:
    return None if value is None else expect_text(value, what)


def expect_texts(value: Json, what: str) -> tuple[str, ...]:
    return tuple(expect_text(item, what) for item in expect_list(value, what))


def expect_decimal(value: Json, what: str) -> Decimal:
    text = expect_text(value, what)
    try:
        result = Decimal(text)
    except InvalidOperation as error:
        raise CanonicalError(f"{what}: {text!r} is not a decimal") from error
    if decimal_text(result) != text:
        raise CanonicalError(f"{what}: {text!r} is not normalized")
    return result


def expect_optional_decimal(value: Json, what: str) -> Decimal | None:
    return None if value is None else expect_decimal(value, what)


def expect_enum[E: enum.Enum](kind: type[E], value: Json, what: str) -> E:
    text = expect_text(value, what)
    try:
        return kind(text)
    except ValueError as error:
        raise CanonicalError(f"{what}: unknown value {text!r}") from error


@dataclass(frozen=True)
class OrganRef:
    """An organ or Body channel, named with its version (PRV-7)."""

    id: str
    version: str

    def to_canonical(self) -> dict[str, Canonical]:
        return {"id": self.id, "version": self.version}

    @classmethod
    def from_canonical(cls, value: Json) -> OrganRef:
        data = expect_object(value, "organ")
        return cls(
            expect_text(field_of(data, "id"), "organ.id"),
            expect_text(field_of(data, "version"), "organ.version"),
        )


@dataclass(frozen=True)
class ObjectRef:
    """One version of one persistent object."""

    id: str
    version: int

    def to_canonical(self) -> dict[str, Canonical]:
        return {"id": self.id, "version": self.version}

    @classmethod
    def from_canonical(cls, value: Json) -> ObjectRef:
        data = expect_object(value, "object reference")
        return cls(
            expect_text(field_of(data, "id"), "ref.id"),
            expect_int(field_of(data, "version"), "ref.version"),
        )


@dataclass(frozen=True)
class ObjectReferent:
    """Points at a persistent object by id."""

    object_id: str


@dataclass(frozen=True)
class RegionReferent:
    """Points at a region of a persisted Observation. The region is opaque."""

    observation_id: str
    region: Json


@dataclass(frozen=True)
class OpaqueReferent:
    """Points at an opaque identifier that a persisted Observation introduced."""

    observation_id: str
    identifier: str


type Referent = ObjectReferent | RegionReferent | OpaqueReferent


def referent_to_canonical(referent: Referent) -> dict[str, Canonical]:
    match referent:
        case ObjectReferent(object_id=object_id):
            return {"kind": "object", "object": object_id}
        case RegionReferent(observation_id=observation_id, region=region):
            return {"kind": "region", "observation": observation_id, "region": region}
        case OpaqueReferent(observation_id=observation_id, identifier=identifier):
            return {"kind": "opaque", "observation": observation_id, "identifier": identifier}


def referent_from_canonical(value: Json) -> Referent:
    data = expect_object(value, "referent")
    kind = field_of(data, "kind")
    if kind == "object":
        return ObjectReferent(expect_text(field_of(data, "object"), "referent.object"))
    if kind == "region":
        return RegionReferent(
            expect_text(field_of(data, "observation"), "referent.observation"),
            field_of(data, "region"),
        )
    if kind == "opaque":
        return OpaqueReferent(
            expect_text(field_of(data, "observation"), "referent.observation"),
            expect_text(field_of(data, "identifier"), "referent.identifier"),
        )
    raise CanonicalError(f"unknown referent kind {kind!r}")


@dataclass(frozen=True)
class ObjectHeader:
    """The PersistentObject header (FOUNDATIONS §7). Headers are never forgotten."""

    id: str
    type: ObjectType
    version: int
    provenance_id: str
    derived_from: tuple[str, ...]
    created_seq: int
    seq: int
    retired_by: int | None
    forgotten: bool
    body_digest: str

    def ref(self) -> ObjectRef:
        return ObjectRef(self.id, self.version)

    def to_canonical(self) -> dict[str, Canonical]:
        return {
            "id": self.id,
            "type": self.type.value,
            "version": self.version,
            "provenance": self.provenance_id,
            "derived_from": list(self.derived_from),
            "created_seq": self.created_seq,
            "seq": self.seq,
            "retired_by": self.retired_by,
            "forgotten": self.forgotten,
            "body_digest": self.body_digest,
        }

    @classmethod
    def from_canonical(cls, value: Json) -> ObjectHeader:
        data = expect_object(value, "header")
        return cls(
            id=expect_text(field_of(data, "id"), "header.id"),
            type=expect_enum(ObjectType, field_of(data, "type"), "header.type"),
            version=expect_int(field_of(data, "version"), "header.version"),
            provenance_id=expect_text(field_of(data, "provenance"), "header.provenance"),
            derived_from=expect_texts(field_of(data, "derived_from"), "header.derived_from"),
            created_seq=expect_int(field_of(data, "created_seq"), "header.created_seq"),
            seq=expect_int(field_of(data, "seq"), "header.seq"),
            retired_by=expect_optional_int(field_of(data, "retired_by"), "header.retired_by"),
            forgotten=expect_bool(field_of(data, "forgotten"), "header.forgotten"),
            body_digest=expect_text(field_of(data, "body_digest"), "header.body_digest"),
        )


@dataclass(frozen=True)
class ProvenanceInput:
    """One provenance input: which version, under what role (ROL-1)."""

    ref: ObjectRef
    role: Role

    def to_canonical(self) -> dict[str, Canonical]:
        return {"ref": self.ref.to_canonical(), "role": self.role.value}

    @classmethod
    def from_canonical(cls, value: Json) -> ProvenanceInput:
        data = expect_object(value, "provenance input")
        return cls(
            ref=ObjectRef.from_canonical(field_of(data, "ref")),
            role=expect_enum(Role, field_of(data, "role"), "input.role"),
        )


@dataclass(frozen=True)
class RoleInput:
    """An organ's proposed reference to an object, under a role it claims (ROL-3, ROL-5)."""

    object_id: str
    role: Role


@dataclass(frozen=True)
class Provenance:
    """How a commitment came to be (FOUNDATIONS §5). Never modified once written."""

    id: str
    mode: Mode
    inputs: tuple[ProvenanceInput, ...]
    operation: Operation | None
    organ: OrganRef | None
    seed_spec: str | None
    seq: int

    def to_canonical(self) -> dict[str, Canonical]:
        return {
            "id": self.id,
            "mode": self.mode.value,
            "inputs": [item.to_canonical() for item in self.inputs],
            "operation": None if self.operation is None else self.operation.value,
            "organ": None if self.organ is None else self.organ.to_canonical(),
            "seed_spec": self.seed_spec,
            "seq": self.seq,
        }

    @classmethod
    def from_canonical(cls, value: Json) -> Provenance:
        data = expect_object(value, "provenance")
        operation = field_of(data, "operation")
        organ = field_of(data, "organ")
        return cls(
            id=expect_text(field_of(data, "id"), "provenance.id"),
            mode=expect_enum(Mode, field_of(data, "mode"), "provenance.mode"),
            inputs=tuple(
                ProvenanceInput.from_canonical(item)
                for item in expect_list(field_of(data, "inputs"), "provenance.inputs")
            ),
            operation=None
            if operation is None
            else expect_enum(Operation, operation, "provenance.operation"),
            organ=None if organ is None else OrganRef.from_canonical(organ),
            seed_spec=expect_optional_text(field_of(data, "seed_spec"), "provenance.seed_spec"),
            seq=expect_int(field_of(data, "seq"), "provenance.seq"),
        )


@dataclass(frozen=True)
class InfonBody:
    """The body of an Infon (FOUNDATIONS §8.4)."""

    relation: str
    participants: tuple[Referent, ...]
    polarity: Polarity
    context: dict[str, Json]
    confidence: Decimal
    status: InfonStatus

    def to_canonical(self) -> dict[str, Canonical]:
        return {
            "type": "Infon",
            "schema": 1,
            "relation": self.relation,
            "participants": [referent_to_canonical(item) for item in self.participants],
            "polarity": self.polarity.value,
            "context": self.context,
            "confidence": decimal_text(self.confidence),
            "status": self.status.value,
        }

    @classmethod
    def from_canonical(cls, value: Json) -> InfonBody:
        data = expect_object(value, "infon")
        if data.get("type") != "Infon":
            raise CanonicalError("not an Infon body")
        return cls(
            relation=expect_text(field_of(data, "relation"), "infon.relation"),
            participants=tuple(
                referent_from_canonical(item)
                for item in expect_list(field_of(data, "participants"), "infon.participants")
            ),
            polarity=expect_enum(Polarity, field_of(data, "polarity"), "infon.polarity"),
            context=expect_object(field_of(data, "context"), "infon.context"),
            confidence=expect_decimal(field_of(data, "confidence"), "infon.confidence"),
            status=expect_enum(InfonStatus, field_of(data, "status"), "infon.status"),
        )


@dataclass(frozen=True)
class Observation:
    """What a Body channel received (FOUNDATIONS §8.2). Transient until CONSOLIDATE."""

    id: str
    channel: OrganRef
    received_seq: int
    content: Json
    identifiers: tuple[str, ...] = ()

    def body(self) -> dict[str, Canonical]:
        return {
            "type": "Observation",
            "schema": 1,
            "channel": self.channel.to_canonical(),
            "received_seq": self.received_seq,
            "content": self.content,
            "identifiers": list(self.identifiers),
        }

    @classmethod
    def from_body(cls, object_id: str, value: Json) -> Observation:
        data = expect_object(value, "observation")
        if data.get("type") != "Observation":
            raise CanonicalError("not an Observation body")
        return cls(
            id=object_id,
            channel=OrganRef.from_canonical(field_of(data, "channel")),
            received_seq=expect_int(field_of(data, "received_seq"), "observation.received_seq"),
            content=field_of(data, "content"),
            identifiers=expect_texts(field_of(data, "identifiers"), "observation.identifiers"),
        )


@dataclass(frozen=True)
class Check:
    """One line of a validator-written justification (PER-7)."""

    operation: int
    rule: str
    measured: Mapping[str, Canonical] = field(default_factory=dict)

    def to_canonical(self) -> dict[str, Canonical]:
        return {"operation": self.operation, "rule": self.rule, "measured": self.measured}


@dataclass(frozen=True)
class EventRow:
    """A World Language event (FOUNDATIONS §8.13)."""

    seq: int
    index: int
    type: EventType
    object_id: str

    def to_canonical(self) -> dict[str, Canonical]:
        return {
            "seq": self.seq,
            "index": self.index,
            "type": self.type.value,
            "object": self.object_id,
        }

    @classmethod
    def from_canonical(cls, value: Json) -> EventRow:
        data = expect_object(value, "event")
        return cls(
            seq=expect_int(field_of(data, "seq"), "event.seq"),
            index=expect_int(field_of(data, "index"), "event.index"),
            type=expect_enum(EventType, field_of(data, "type"), "event.type"),
            object_id=expect_text(field_of(data, "object"), "event.object"),
        )


@dataclass(frozen=True)
class OperationEntry:
    """Which operation a transition applied to which object. Never holds body bytes."""

    operation: Operation
    object_id: str
    reason: str = ""

    def to_canonical(self) -> dict[str, Canonical]:
        return {"operation": self.operation.value, "object": self.object_id, "reason": self.reason}


@dataclass(frozen=True)
class IssueRow:
    """Binds an Infon's identity, once, to its IssueDigest (INF-7, ISS-2). Never repeated or changed."""

    object_id: str
    issue_digest: str

    def to_canonical(self) -> dict[str, Canonical]:
        return {"object": self.object_id, "issue": self.issue_digest}

    @classmethod
    def from_canonical(cls, value: Json) -> IssueRow:
        data = expect_object(value, "issue row")
        return cls(
            object_id=expect_text(field_of(data, "object"), "issue.object"),
            issue_digest=expect_text(field_of(data, "issue"), "issue.issue"),
        )


@dataclass(frozen=True)
class Rows:
    """The Heart rows one transition, or the seed, produces."""

    provenance: tuple[Provenance, ...]
    versions: tuple[ObjectHeader, ...]
    events: tuple[EventRow, ...] = ()
    issues: tuple[IssueRow, ...] = ()


# Proposals. Organs build these; only the validator turns them into transitions.


@dataclass(frozen=True)
class Consolidate:
    observation_id: str


@dataclass(frozen=True)
class FormInfon:
    """Mode is never supplied here (PRV-8): the validator derives it from the roles of `inputs`.

    No inputs is `testimony` (ORG-3); inputs that are all `attribution` is
    `attributed` (ORG-4); otherwise `derivation`. ROL-3 restricts an organ to
    the roles `derivation_input` and `attribution` for formation.
    """

    relation: str
    participants: tuple[Referent, ...]
    confidence: Decimal
    inputs: tuple[RoleInput, ...] = ()
    context: dict[str, Json] = field(default_factory=dict)
    polarity: Polarity = Polarity.POSITIVE
    derived_from: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviseInfon:
    """`evidence` roles are restricted to `support`, `counterevidence` and `attribution` (ROL-3).

    The validator adds a `revision_target` input naming the version revised;
    an organ cannot supply that role itself.
    """

    infon_id: str
    expected_version: int
    body: InfonBody
    evidence: tuple[RoleInput, ...] = ()


@dataclass(frozen=True)
class Forget:
    object_id: str
    expected_version: int
    reason: str
    successor: str | None = None


@dataclass(frozen=True)
class OtherOperation:
    """Any operation v1 has no typed form for, named as in FOUNDATIONS §10."""

    name: str


type ProposedOperation = Consolidate | FormInfon | ReviseInfon | Forget | OtherOperation


@dataclass(frozen=True)
class Proposal:
    organ: OrganRef
    operations: tuple[ProposedOperation, ...]
    reason: str = ""
