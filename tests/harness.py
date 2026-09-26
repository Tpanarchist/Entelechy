"""A Heart built from seed, store and validator, without the kernel.

Validator and store tests use this to exercise each layer directly.
"""

import sqlite3
from decimal import Decimal
from pathlib import Path

from entelechy.foundation.canonical import Json, digest, parse
from entelechy.foundation.seed import PolicyRef, SeedSpec, manifest_for, seed_heart
from entelechy.foundation.store import Store
from entelechy.foundation.types import (
    Consolidate,
    FormInfon,
    InfonBody,
    ObjectType,
    Observation,
    OrganRef,
    Proposal,
    ProposedOperation,
    ProvenanceKind,
    RegionReferent,
)
from entelechy.foundation.validator import (
    AcceptedTransition,
    Rejection,
    RetentionPolicy,
    Validator,
)

EYE = OrganRef("eye", "1")
MIND = OrganRef("mind", "1")
OMEGA = "omega-test"
FIXED = PolicyRef("fixed", "1")


class FixedRetention:
    """A test retention policy that gives every object the same score."""

    name = "fixed"
    version = "1"

    def __init__(self, value: Decimal = Decimal("0.5")) -> None:
        self.value = value

    def score(self, object_type: ObjectType, body: bytes) -> Decimal:
        return self.value


def plain_seed() -> SeedSpec:
    """A seed with no retention policy, like a production seed today."""
    return SeedSpec(relations=("R1", "R2"), channels=(EYE,), organs=(MIND,))


def policy_seed() -> SeedSpec:
    """A seed that binds both retention thresholds and the fixed test policy."""
    return SeedSpec(
        relations=("R1", "R2"),
        channels=(EYE,),
        organs=(MIND,),
        theta_retain=Decimal("0.5"),
        theta_forget=Decimal("0.5"),
        retention_policy=FIXED,
    )


def infon_from(
    observation_id: str, relation: str = "R1", confidence: Decimal = Decimal("0.8")
) -> FormInfon:
    """An Infon about a region of an Observation, citing that Observation."""
    return FormInfon(
        relation=relation,
        participants=(RegionReferent(observation_id, {"x": 1}),),
        confidence=confidence,
        provenance_kind=ProvenanceKind.OBSERVATION,
        inputs=(observation_id,),
    )


class Harness:
    def __init__(self, path: Path, seed: SeedSpec, policy: RetentionPolicy | None = None) -> None:
        self.path = path
        self.manifest = manifest_for(seed, OMEGA)
        self.store = Store.create(path)
        rows, contents = seed_heart(self.manifest)
        manifest_bytes = self.manifest.to_bytes()
        self.store.write_origin(OMEGA, manifest_bytes, digest(manifest_bytes), rows, contents)
        self.validator = Validator(self.manifest, policy)
        self.transient: dict[str, Observation] = {}

    def receive(self, content: Json = "red", identifiers: tuple[str, ...] = ()) -> str:
        seq = self.store.allocate_seq()
        observation = Observation(f"obs:{seq}", EYE, seq, content, identifiers)
        self.transient[observation.id] = observation
        return observation.id

    def propose(
        self, *operations: ProposedOperation, organ: OrganRef = MIND
    ) -> AcceptedTransition | Rejection:
        seq = self.store.allocate_seq()
        return self.validator.validate(Proposal(organ, operations), seq, self.store, self.transient)

    def commit(self, *operations: ProposedOperation) -> AcceptedTransition:
        result = accepted(self.propose(*operations))
        self.store.commit(result, OMEGA)
        for entry in result.operations:
            self.transient.pop(entry.object_id, None)
        return result

    def lifecycle(self, content: Json = "red") -> tuple[str, str]:
        """Commit the first lifecycle; return the Observation and Infon ids."""
        observation = self.receive(content)
        result = self.commit(Consolidate(observation), infon_from(observation))
        (infon_id,) = [header.id for header in result.versions if header.id != observation]
        return observation, infon_id

    def raw(self) -> sqlite3.Connection:
        """A second, ordinary connection: what anyone with the file could do."""
        return sqlite3.connect(self.path, autocommit=True)

    def close(self) -> None:
        self.store.close()


def tamper(path: Path, guards: tuple[str, ...], statement: str, params: tuple[object, ...] = ()) -> None:
    """Edit the database file behind the kernel's back, then put the guards back."""
    raw = sqlite3.connect(path, autocommit=True)
    try:
        saved = [
            raw.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?", (name,)
            ).fetchone()[0]
            for name in guards
        ]
        for name in guards:
            raw.execute(f"DROP TRIGGER {name}")
        raw.execute(statement, params)
        for sql in saved:
            raw.execute(sql)
    finally:
        raw.close()


def rejected(result: AcceptedTransition | Rejection) -> Rejection:
    assert isinstance(result, Rejection), f"expected a rejection, got {result}"
    return result


def accepted(result: AcceptedTransition | Rejection) -> AcceptedTransition:
    assert isinstance(result, AcceptedTransition), str(result)
    return result


def infon_body(store: Store, infon_id: str) -> InfonBody:
    header = store.latest(infon_id)
    assert header is not None
    data = store.content(header.body_digest)
    assert data is not None
    return InfonBody.from_canonical(parse(data))
