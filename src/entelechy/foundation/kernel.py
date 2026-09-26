"""The kernel and the ports organs act through.

Organ -> Port -> Kernel -> Validator -> Store. The host holds the Kernel and
wires one port to each organ: a BodyChannel to each Body component and an
OrganPort to each Mind organ. Identity comes from which port delivered
something, never from data the organ supplies (ORG-6). The kernel never hands
out its Store, so Law 5 is architectural rather than conventional.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from entelechy.foundation.canonical import CanonicalError, Json, canonical_bytes, digest, parse
from entelechy.foundation.replay import HeartView, replay_current, replay_historical
from entelechy.foundation.seed import Manifest, PolicyRef, SeedSpec, manifest_for, seed_heart
from entelechy.foundation.store import Store
from entelechy.foundation.types import (
    EventRow,
    Observation,
    Operation,
    OrganRef,
    Proposal,
    ProposedOperation,
)
from entelechy.foundation.validator import (
    AcceptedTransition,
    Rejection,
    RetentionPolicy,
    Validator,
)

_PORT_KEY = object()


class KernelError(Exception):
    """The kernel cannot be created or opened, or an input is refused outright."""


@dataclass(frozen=True)
class Accepted:
    seq: int
    events: tuple[EventRow, ...]
    created: tuple[str, ...]


def _resolve_policy(
    ref: PolicyRef | None, policies: Sequence[RetentionPolicy]
) -> RetentionPolicy | None:
    if ref is None:
        return None
    for policy in policies:
        if policy.name == ref.name and policy.version == ref.version:
            return policy
    raise KernelError(f"the seed requires retention policy {ref.name}@{ref.version}")


def _name(ref: OrganRef) -> str:
    return f"{ref.id}@{ref.version}"


class BodyChannel:
    """The capability to deliver Observations as exactly one Body channel (ORG-6).

    Only Kernel.body_channel makes one. Its channel is fixed when it is made,
    and nothing passed to `receive` can change it.
    """

    def __init__(self, kernel: Kernel, channel: OrganRef, *, key: object) -> None:
        if key is not _PORT_KEY:
            raise PermissionError("ORG-6: only the kernel makes ports")
        self._kernel = kernel
        self._channel = channel

    @property
    def channel(self) -> OrganRef:
        return self._channel

    def receive(self, content: Json, identifiers: Sequence[str] = ()) -> str:
        """Deliver an Observation. It stays transient until CONSOLIDATE."""
        return self._kernel._receive(self._channel, content, identifiers)


class OrganPort:
    """The capability to propose as exactly one Mind organ (ORG-6).

    Only Kernel.organ makes one. Every proposal made through it names its
    organ; the organ never names itself.
    """

    def __init__(self, kernel: Kernel, organ: OrganRef, *, key: object) -> None:
        if key is not _PORT_KEY:
            raise PermissionError("ORG-6: only the kernel makes ports")
        self._kernel = kernel
        self._organ = organ

    @property
    def organ(self) -> OrganRef:
        return self._organ

    @property
    def heart(self) -> HeartView:
        return self._kernel.heart

    def propose(self, *operations: ProposedOperation, reason: str = "") -> Accepted | Rejection:
        return self._kernel._propose(Proposal(self._organ, operations, reason))


class Kernel:
    """Create with Kernel.create or Kernel.open, never directly.

    The Kernel belongs to the host that wires organs together. Organs hold
    only the ports the host gives them.
    """

    def __init__(
        self, store: Store, path: Path, manifest: Manifest, policy: RetentionPolicy | None
    ) -> None:
        self._store = store
        self._manifest = manifest
        self._validator = Validator(manifest, policy)
        self._transient: dict[str, Observation] = {}
        self._reader = Store.open_readonly(path)
        self.heart = HeartView(self._reader)

    @classmethod
    def create(
        cls, path: Path, seed: SeedSpec, policies: Sequence[RetentionPolicy] = ()
    ) -> Kernel:
        manifest = manifest_for(seed, str(uuid.uuid4()))
        policy = _resolve_policy(manifest.retention_policy, policies)
        store = Store.create(path)
        rows, contents = seed_heart(manifest)
        manifest_bytes = manifest.to_bytes()
        store.write_origin(manifest.omega_id, manifest_bytes, digest(manifest_bytes), rows, contents)
        return cls(store, path, manifest, policy)

    @classmethod
    def open(cls, path: Path, policies: Sequence[RetentionPolicy] = ()) -> Kernel:
        """Wake up: replay all of lineage and refuse to open on any mismatch."""
        store = Store.open(path)
        try:
            replay_current(store)
            manifest = Manifest.from_bytes(store.origin()[1])
            policy = _resolve_policy(manifest.retention_policy, policies)
        except BaseException:
            store.close()
            raise
        return cls(store, path, manifest, policy)

    @property
    def omega_id(self) -> str:
        return self._manifest.omega_id

    def close(self) -> None:
        self._reader.close()
        self._store.close()

    def __enter__(self) -> Kernel:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # Wiring: the host hands each port to the one organ it belongs to.

    def body_channel(self, channel: OrganRef) -> BodyChannel:
        if channel in self._manifest.organs:
            raise KernelError(f"ORG-6: {_name(channel)} is a Mind organ, not a Body channel")
        if channel not in self._manifest.channels:
            raise KernelError(f"ORG-2: channel {_name(channel)} is not registered")
        return BodyChannel(self, channel, key=_PORT_KEY)

    def organ(self, organ: OrganRef) -> OrganPort:
        if organ in self._manifest.channels:
            raise KernelError(f"ORG-6: {_name(organ)} is a Body channel; it cannot propose")
        if organ not in self._manifest.organs:
            raise KernelError(f"ORG-2: organ {_name(organ)} is not registered")
        return OrganPort(self, organ, key=_PORT_KEY)

    # Called only by ports, which supply the identity.

    def _receive(self, channel: OrganRef, content: Json, identifiers: Sequence[str]) -> str:
        if isinstance(identifiers, str):
            raise CanonicalError("identifiers must be a list of strings, not one string")
        names = tuple(identifiers)
        if not all(isinstance(name, str) for name in names):
            raise CanonicalError("identifiers must all be strings")
        # Keep a canonical snapshot, not the caller's object: a channel that
        # reuses its buffer must not rewrite what was received (OBS-1). This
        # also refuses non-canonical content before a seq is used.
        snapshot = parse(canonical_bytes(content))
        seq = self._store.allocate_seq()
        observation = Observation(f"obs:{uuid.uuid4()}", channel, seq, snapshot, names)
        self._transient[observation.id] = observation
        return observation.id

    def _propose(self, proposal: Proposal) -> Accepted | Rejection:
        seq = self._store.allocate_seq()
        result = self._validator.validate(proposal, seq, self._store, self._transient)
        if isinstance(result, Rejection):
            return result
        self._commit(result)
        return Accepted(
            seq=result.seq,
            events=result.events,
            created=tuple(header.id for header in result.versions if header.version == 1),
        )

    def _commit(self, accepted: AcceptedTransition) -> None:
        self._store.commit(accepted, self._manifest.omega_id)
        for entry in accepted.operations:
            if entry.operation is Operation.CONSOLIDATE:
                self._transient.pop(entry.object_id, None)

    def replay_current(self) -> str:
        return replay_current(self._store)

    def replay_historical(self, seq: int) -> HeartView:
        # The view reads content through the read-only connection, like kernel.heart.
        return replay_historical(self._store, seq, content=self._reader)
