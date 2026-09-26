"""The seed: machinery, not knowledge (FOUNDATIONS §9).

The origin manifest alone is enough to rebuild the seed Heart (DEV-2), and
everything in the seed carries `origin` provenance (DEV-1).
"""

from dataclasses import dataclass
from decimal import Decimal

from entelechy.foundation.canonical import (
    Canonical,
    CanonicalError,
    Json,
    canonical_bytes,
    decimal_text,
    digest,
    parse,
)
from entelechy.foundation.types import (
    ObjectHeader,
    ObjectType,
    OrganRef,
    Provenance,
    ProvenanceKind,
    Rows,
    expect_list,
    expect_object,
    expect_optional_decimal,
    expect_text,
    expect_texts,
    field_of,
)

SEED_SPEC_VERSION = "entelechy-seed/0"
MANIFEST_SCHEMA = 1


class SeedError(ValueError):
    """A seed specification cannot constitute an Entelechy."""


def _optional_decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else decimal_text(value)


@dataclass(frozen=True)
class PolicyRef:
    """A retention policy named in the seed (OPEN-5, OPEN-15)."""

    name: str
    version: str

    def to_canonical(self) -> dict[str, Canonical]:
        return {"name": self.name, "version": self.version}

    @classmethod
    def from_canonical(cls, value: Json) -> PolicyRef:
        data = expect_object(value, "policy")
        return cls(
            expect_text(field_of(data, "name"), "policy.name"),
            expect_text(field_of(data, "version"), "policy.version"),
        )


@dataclass(frozen=True)
class SeedSpec:
    relations: tuple[str, ...]
    channels: tuple[OrganRef, ...]
    organs: tuple[OrganRef, ...]
    theta_retain: Decimal | None = None
    theta_forget: Decimal | None = None
    retention_policy: PolicyRef | None = None


@dataclass(frozen=True)
class Manifest:
    """The origin manifest: the complete seed, at seq 0."""

    omega_id: str
    spec_version: str
    relations: tuple[str, ...]
    channels: tuple[OrganRef, ...]
    organs: tuple[OrganRef, ...]
    theta_retain: Decimal | None
    theta_forget: Decimal | None
    retention_policy: PolicyRef | None

    @property
    def self_id(self) -> str:
        return f"self:{self.omega_id}"

    def to_canonical(self) -> dict[str, Canonical]:
        return {
            "type": "Origin",
            "schema": MANIFEST_SCHEMA,
            "omega_id": self.omega_id,
            "spec_version": self.spec_version,
            "relations": list(self.relations),
            "channels": [channel.to_canonical() for channel in self.channels],
            "organs": [organ.to_canonical() for organ in self.organs],
            "parameters": {
                "theta_retain": _optional_decimal_text(self.theta_retain),
                "theta_forget": _optional_decimal_text(self.theta_forget),
            },
            "retention_policy": None
            if self.retention_policy is None
            else self.retention_policy.to_canonical(),
            "seed_objects": [self.self_id],
        }

    def to_bytes(self) -> bytes:
        return canonical_bytes(self.to_canonical())

    @classmethod
    def from_bytes(cls, data: bytes) -> Manifest:
        manifest = expect_object(parse(data), "manifest")
        if manifest.get("type") != "Origin" or manifest.get("schema") != MANIFEST_SCHEMA:
            raise CanonicalError("not a v1 origin manifest")
        parameters = expect_object(field_of(manifest, "parameters"), "manifest.parameters")
        policy = field_of(manifest, "retention_policy")
        return cls(
            omega_id=expect_text(field_of(manifest, "omega_id"), "manifest.omega_id"),
            spec_version=expect_text(field_of(manifest, "spec_version"), "manifest.spec_version"),
            relations=expect_texts(field_of(manifest, "relations"), "manifest.relations"),
            channels=tuple(
                OrganRef.from_canonical(item)
                for item in expect_list(field_of(manifest, "channels"), "manifest.channels")
            ),
            organs=tuple(
                OrganRef.from_canonical(item)
                for item in expect_list(field_of(manifest, "organs"), "manifest.organs")
            ),
            theta_retain=expect_optional_decimal(
                field_of(parameters, "theta_retain"), "theta_retain"
            ),
            theta_forget=expect_optional_decimal(
                field_of(parameters, "theta_forget"), "theta_forget"
            ),
            retention_policy=None if policy is None else PolicyRef.from_canonical(policy),
        )


def check_seed(spec: SeedSpec) -> None:
    if not spec.channels:
        raise SeedError("the seed needs at least one Body channel (FOUNDATIONS §9)")
    if not spec.organs:
        raise SeedError("the seed needs at least one Mind organ (FOUNDATIONS §9)")
    ids = [ref.id for ref in (*spec.channels, *spec.organs)]
    if len(set(ids)) != len(ids):
        raise SeedError("channel and organ ids must be unique")
    if len(set(spec.relations)) != len(spec.relations) or not all(spec.relations):
        raise SeedError("relations must be unique, non-empty names")
    for name, value in (("theta_retain", spec.theta_retain), ("theta_forget", spec.theta_forget)):
        if value is None:
            continue
        if not (value.is_finite() and 0 <= value <= 1):
            raise SeedError(f"{name} must be a decimal within [0, 1]")
        try:
            decimal_text(value)
        except CanonicalError as error:
            raise SeedError(f"{name} has no canonical form: {error}") from error


def manifest_for(spec: SeedSpec, omega_id: str) -> Manifest:
    check_seed(spec)
    manifest = Manifest(
        omega_id=omega_id,
        spec_version=SEED_SPEC_VERSION,
        relations=spec.relations,
        channels=spec.channels,
        organs=spec.organs,
        theta_retain=spec.theta_retain,
        theta_forget=spec.theta_forget,
        retention_policy=spec.retention_policy,
    )
    # The manifest must rebuild exactly from its own bytes (DEV-2), so every
    # field is checked here, before anything is written anywhere.
    try:
        rebuilt = Manifest.from_bytes(manifest.to_bytes())
    except CanonicalError as error:
        raise SeedError(f"the seed has no canonical form: {error}") from error
    if rebuilt != manifest:
        raise SeedError("the seed has no canonical form: it does not survive encoding")
    return manifest


def seed_heart(manifest: Manifest) -> tuple[Rows, dict[str, bytes]]:
    """The seed Heart: a Self Map holding only the self-reference (SLF-1)."""
    body = canonical_bytes(
        {
            "type": "SelfMapEntry",
            "schema": 1,
            "entry": "self-reference",
            "omega_id": manifest.omega_id,
        }
    )
    body_digest = digest(body)
    provenance = Provenance(
        id=f"prov:origin:{manifest.omega_id}",
        kind=ProvenanceKind.ORIGIN,
        inputs=(),
        operation=None,
        organ=None,
        seed_spec=manifest.spec_version,
        seq=0,
    )
    header = ObjectHeader(
        id=manifest.self_id,
        type=ObjectType.SELF_MAP_ENTRY,
        version=1,
        provenance_id=provenance.id,
        derived_from=(),
        created_seq=0,
        seq=0,
        retired_by=None,
        forgotten=False,
        body_digest=body_digest,
    )
    return Rows((provenance,), (header,)), {body_digest: body}
