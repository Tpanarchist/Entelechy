# Foundation Validator v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build E000: a small kernel that creates a seed, lets an organ lawfully form one Infon from one Observation, rejects illegal proposals with structured rejections, and reproduces the identical Heart from origin and lineage after a restart.

**Architecture:** Organs only ever hold a `Kernel`. The kernel passes each `Proposal` to a `Validator`, which knows the rules of FOUNDATIONS.md and returns either an `AcceptedTransition` or a `Rejection`. Only the validator can construct an `AcceptedTransition`, and only an `AcceptedTransition` can reach the SQLite `Store`. The store commits each transition in one SQL transaction, and triggers inside the database refuse raw edits to append-only tables. Replay rebuilds the Heart's structure from origin and lineage and checks the live content store against its digests.

**Tech Stack:** Python 3.14 (CPython 3.14.6 through uv), standard library only at runtime (`sqlite3`, `hashlib`, `json`, `decimal`, `dataclasses`, `enum`, `uuid`), pytest and mypy (strict) for development.

**Spec:** [docs/superpowers/specs/2026-09-26-foundation-validator-v1-design.md](../specs/2026-09-26-foundation-validator-v1-design.md), which implements a subset of [FOUNDATIONS.md](../../../FOUNDATIONS.md) draft 0.4. Read both before starting.

## Global Constraints

- Python 3.14 or later. Run everything through `uv run`; the `python` on PATH on this machine is 3.8.
- Runtime dependencies: standard library only. Development dependencies: `pytest>=8.3` and `mypy>=1.18`, with mypy in `strict` mode.
- No ORM, no async, no network access, no plugin architecture, no neural dependencies.
- The canonical layer accepts only the plain JSON subset: `null`, booleans, integers, strings, arrays, and objects with string keys. Floats, dates and times, and `Decimal` are all refused. Typed schemas write their `Decimal` fields with `decimal_text` and decode them by field. This keeps encoding one-to-one: distinct values never share bytes.
- **E000 is single-writer.** Validator v1 supports exactly one writable `Kernel` per Heart, and serial calls to `receive` and `propose`. Multi-writer concurrency is undefined and deferred.
- **Threat model.** Organs are epistemically untrusted, not hostile native code. The capability token and private attributes are architectural discipline, not a sandbox. Code in the same process, or with access to the database file, can get around them, and E000 does not try to prevent that.
- Digests are written `sha256:<hex>`, naming their algorithm.
- Transition records name content by digest only. Body bytes never enter lineage (RPL-3).
- Only the validator constructs an `AcceptedTransition`. Organs get the `Kernel` and a read-only `HeartView`, never a writable `Store` (Law 5).
- Every rejection cites a FOUNDATIONS rule ID, or a v1 restriction ID (`V1-UNIMPLEMENTED`, `V1-CERTAINTY`), never a weaker FOUNDATIONS rule.
- Test names end with the rule ID they pin, where there is one (for example `..._prv4`).
- Run every command from the repository root, `E:\Entelechy`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

These are the inputs the spec implies but does not spell out that are most likely to bite someone using the kernel. Each has a test in the task that owns the code.

1. **Non-canonical Observation content** (a float, a lone surrogate, a date) arriving at `Kernel.receive` must raise `CanonicalError` before any `seq` is used, and nothing becomes transient. Tests: Task 1 (`test_floats_are_forbidden`, `test_lone_surrogates_are_rejected`, `test_dates_are_forbidden_seq3`) and Task 11 (`test_non_canonical_content_is_refused_before_it_uses_a_seq`).
2. **A proposal naming an Observation id that was never received, or was lost in a restart,** must come back as a `Rejection` citing PER-3, never as an exception. Tests: Task 11 (`test_an_unknown_observation_id_is_rejected_not_raised`, `test_transient_observations_do_not_survive_restart_per4`).
3. **Pointing the kernel at something that is not an intact Heart** (a missing file, a non-SQLite file, a Heart with a dropped guard trigger), or creating over an existing Heart, must raise `StoreError` and leave any existing file untouched. Tests: Task 3 (`test_open_refuses_*`, `test_create_refuses_an_existing_path`) and Task 11 (`test_create_refuses_an_existing_heart_and_leaves_it_intact`, `test_open_refuses_a_file_that_is_not_a_heart`, `test_wake_up_refuses_a_heart_whose_guards_were_dropped`).
4. **A seed naming a retention policy the caller did not supply** must make `Kernel.create` write nothing and `Kernel.open` refuse. Tests: Task 11 (`test_create_refuses_a_seed_whose_policy_is_missing_and_writes_nothing`, `test_open_refuses_when_the_seed_policy_is_not_supplied`).
5. **Two objects with identical body bytes, one of them forgotten,** must leave the survivor's content intact. Test: Task 9 (`test_shared_content_survives_forgetting_one_owner`).

## Implementation Decisions Within the Approved Design

These choices are consistent with the spec but are not spelled out in it. Keep them unless implementation exposes a contradiction.

- **`derived_from` is a column.** It is stored as a canonical JSON array on `object_versions` instead of a separate `object_derivations` table, because it belongs to one object and never changes.
- **Seq is allocated before validation.** A rejected proposal therefore consumes its `seq`. SEQ-2 allows gaps and forbids reuse.
- **`kernel.heart` reads through a read-only SQLite connection.** An organ that reaches inside it still cannot write, which makes Law 5 physical rather than conventional.
- **One extra storage guard:** object versions must be consecutive.
- **The REVISE_INFON requirement has no rule ID** in FOUNDATIONS §10, so v1 cites it as `§10 REVISE_INFON`.
- **A revised Infon version** gets `derivation` provenance whose inputs are the version it revises plus the new evidence. Evidence counts as new per `(id, version)`, so a newer version of something already cited is new evidence. An Infon is never evidence for its own revision.
- **Justifications record what actually happened.** For example, a revision's INF-4 check lists only the fields that changed.
- **Validation stops at the first failing operation** and reports all of that operation's violations.

## File Structure

| File | Responsibility |
| --- | --- |
| `pyproject.toml`, `.python-version`, `.gitignore`, `.gitattributes` | Project, interpreter pin and repository hygiene |
| `src/entelechy/foundation/canonical.py` | Canonical bytes, versioned digests, strict parsing |
| `src/entelechy/foundation/types.py` | Enums, object headers, provenance, Infon and Observation bodies, proposals, decoding helpers |
| `src/entelechy/foundation/store.py` | SQLite schema and guard triggers, atomic commit, reads |
| `src/entelechy/foundation/seed.py` | Seed specification, origin manifest, seed Heart |
| `src/entelechy/foundation/transitions.py` | Building transition records and decoding them into Heart rows |
| `src/entelechy/foundation/validator.py` | The rules: `Proposal` to `AcceptedTransition` or `Rejection` |
| `src/entelechy/foundation/replay.py` | Replay, integrity checks, read-only `HeartView` |
| `src/entelechy/foundation/kernel.py` | The organ-facing facade |
| `tests/harness.py`, `tests/conftest.py` | A Heart built from seed, store and validator, for layer-level tests |
| `tests/test_*.py` | One test file per module, plus `test_kernel.py` for E000 end to end |

---

### Task 1: Project Scaffold and Canonical Serialization

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.gitattributes`
- Create: `src/entelechy/__init__.py`, `src/entelechy/foundation/__init__.py`
- Create: `src/entelechy/foundation/canonical.py`
- Test: `tests/test_canonical.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `type Canonical`: `None | bool | int | str | Sequence[Canonical] | Mapping[str, Canonical]`, anything that can be encoded. There is no `Decimal`: typed schemas convert it with `decimal_text` first.
  - `type Json`: `None | bool | int | str | list[Json] | dict[str, Json]`, what `parse` returns.
  - `class CanonicalError(ValueError)`
  - `canonical_bytes(value: Canonical) -> bytes`
  - `digest(data: bytes) -> str`, returning `"sha256:<hex>"`
  - `digest_of(value: Canonical) -> str`
  - `verify(data: bytes, expected: str) -> bool`
  - `parse(data: bytes) -> Json`
  - `decimal_text(value: Decimal) -> str`

- [ ] **Step 1: Create the project files**

`pyproject.toml`:

```toml
[project]
name = "entelechy"
version = "0.0.1"
description = "Entelechy foundation kernel (experiment E000)"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = ["pytest>=8.3", "mypy>=1.18"]

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.mypy]
strict = true
python_version = "3.14"
mypy_path = "src"
files = ["src", "tests"]
```

`.python-version`:

```text
3.14
```

`.gitignore`:

```text
.venv/
__pycache__/
.mypy_cache/
.pytest_cache/
*.db
*.db-wal
*.db-shm
```

`.gitattributes`:

```text
* text=auto eol=lf
```

`src/entelechy/__init__.py`:

```python
"""Entelechy: a persistent informational organism."""
```

`src/entelechy/foundation/__init__.py`:

```python
"""The Foundation Validator: a kernel that lets Entelechy exist lawfully.

See FOUNDATIONS.md and docs/superpowers/specs/2026-09-26-foundation-validator-v1-design.md.
"""
```

- [ ] **Step 2: Install the environment**

Run: `uv sync`
Expected: uv creates `.venv` with CPython 3.14 and installs pytest and mypy, and writes `uv.lock`.

- [ ] **Step 3: Write the failing test**

`tests/test_canonical.py`:

```python
import datetime
from decimal import Decimal

import pytest

from entelechy.foundation.canonical import (
    CanonicalError,
    canonical_bytes,
    decimal_text,
    digest,
    digest_of,
    parse,
    verify,
)


def test_keys_are_sorted_and_whitespace_free() -> None:
    assert canonical_bytes({"b": 1, "a": [True, None, "x"]}) == b'{"a":[true,null,"x"],"b":1}'


def test_unicode_is_written_as_utf8_not_escapes() -> None:
    assert canonical_bytes("Ω") == '"Ω"'.encode()


def test_tuples_encode_as_arrays() -> None:
    assert canonical_bytes(("a", 1)) == b'["a",1]'


def test_floats_are_forbidden() -> None:
    value: object = {"confidence": 0.8}
    with pytest.raises(CanonicalError, match="floats"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_dates_are_forbidden_seq3() -> None:
    value: object = [datetime.date(2026, 9, 26)]
    with pytest.raises(CanonicalError, match="SEQ-3"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_non_string_keys_are_rejected() -> None:
    value: object = {1: "x"}
    with pytest.raises(CanonicalError, match="keys"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_lone_surrogates_are_rejected() -> None:
    with pytest.raises(CanonicalError, match="Unicode"):
        canonical_bytes("\ud800")


def test_decimal_text_is_normalized() -> None:
    assert decimal_text(Decimal("0.80")) == "0.8"
    assert decimal_text(Decimal("100")) == "100"
    assert decimal_text(Decimal("-0")) == "0"


def test_non_finite_decimals_have_no_text() -> None:
    with pytest.raises(CanonicalError, match="non-finite"):
        decimal_text(Decimal("NaN"))


def test_decimals_need_a_typed_schema() -> None:
    # Otherwise Decimal("0.8") and the string "0.8" would share one encoding.
    value: object = [Decimal("0.8")]
    with pytest.raises(CanonicalError, match="typed schema"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_digest_names_its_algorithm() -> None:
    value = digest(b"abc")
    assert value.startswith("sha256:")
    assert len(value) == len("sha256:") + 64
    assert verify(b"abc", value)
    assert not verify(b"abd", value)


def test_unknown_digest_algorithm_is_refused() -> None:
    with pytest.raises(CanonicalError, match="unsupported"):
        verify(b"abc", "md5:900150983cd24fb0d6963f7d28e17f72")


def test_digest_of_hashes_the_canonical_bytes() -> None:
    assert digest_of({"a": 1}) == digest(b'{"a":1}')


def test_parse_round_trips_canonical_bytes() -> None:
    assert parse(canonical_bytes({"a": [1, "two", None]})) == {"a": [1, "two", None]}


def test_parse_refuses_non_canonical_bytes() -> None:
    with pytest.raises(CanonicalError, match="canonical form"):
        parse(b'{"b":1, "a":2}')


def test_parse_refuses_floats() -> None:
    with pytest.raises(CanonicalError, match="floats"):
        parse(b"[0.5]")


def test_parse_refuses_invalid_utf8() -> None:
    with pytest.raises(CanonicalError, match="not canonical JSON"):
        parse(b"\xff")
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest tests/test_canonical.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.canonical'`.

- [ ] **Step 5: Write the implementation**

`src/entelechy/foundation/canonical.py`:

```python
"""Canonical bytes and versioned digests.

Every persistent structure has exactly one byte representation before it is
hashed (design §5.1). The canonical layer accepts only the plain JSON subset,
so distinct values always encode to distinct bytes. Typed schemas convert
their Decimal fields with decimal_text and decode them by field.

Floats have no canonical form because their formatting drifts. Dates and
times have none because ordering machinery is not a concept of time
(FOUNDATIONS SEQ-3).
"""

import datetime
import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal

type Canonical = None | bool | int | str | Sequence[Canonical] | Mapping[str, Canonical]
type Json = None | bool | int | str | list[Json] | dict[str, Json]

DIGEST_ALGORITHM = "sha256"


class CanonicalError(ValueError):
    """A value has no canonical representation, or bytes are not canonical."""


def decimal_text(value: Decimal) -> str:
    """Normalized fixed-point text for typed schemas: Decimal("0.80") -> "0.8"."""
    if not value.is_finite():
        raise CanonicalError(f"non-finite decimal {value}")
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


def _prepare(value: object) -> Json:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        raise CanonicalError("a Decimal needs a typed schema; encode it with decimal_text")
    if isinstance(value, float):
        raise CanonicalError("floats are forbidden in canonical content; use Decimal")
    if isinstance(value, (datetime.date, datetime.time, datetime.timedelta)):
        raise CanonicalError("dates and times are not canonical content (SEQ-3)")
    if isinstance(value, (list, tuple)):
        return [_prepare(item) for item in value]
    if isinstance(value, Mapping):
        prepared: dict[str, Json] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError(f"object keys must be strings, not {type(key).__name__}")
            prepared[key] = _prepare(item)
        return prepared
    raise CanonicalError(f"{type(value).__name__} has no canonical form")


def canonical_bytes(value: Canonical) -> bytes:
    """The one byte representation of `value`: sorted keys, no whitespace, UTF-8."""
    text = json.dumps(
        _prepare(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalError(f"text is not valid Unicode: {error.reason}") from error


def digest(data: bytes) -> str:
    """A digest that names its algorithm, so the algorithm can be replaced later."""
    return f"{DIGEST_ALGORITHM}:{hashlib.sha256(data).hexdigest()}"


def digest_of(value: Canonical) -> str:
    return digest(canonical_bytes(value))


def verify(data: bytes, expected: str) -> bool:
    algorithm, separator, _ = expected.partition(":")
    if separator != ":" or algorithm != DIGEST_ALGORITHM:
        raise CanonicalError(f"unsupported digest {expected!r}")
    return digest(data) == expected


def _reject_float(text: str) -> object:
    raise CanonicalError(f"floats are forbidden in canonical content: {text}")


def _reject_constant(text: str) -> object:
    raise CanonicalError(f"non-finite number {text} in canonical content")


def parse(data: bytes) -> Json:
    """Decode canonical bytes, refusing anything that is not already canonical."""
    try:
        text = data.decode("utf-8")
        value: Json = json.loads(
            text, parse_float=_reject_float, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CanonicalError(f"not canonical JSON: {error}") from error
    if canonical_bytes(value) != data:
        raise CanonicalError("bytes are not in canonical form")
    return value
```

- [ ] **Step 6: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `17 passed`, and `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore .gitattributes src tests
git commit -m "feat(foundation): canonical serialization and versioned digests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Normative Types

**Files:**
- Create: `src/entelechy/foundation/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Consumes: `Canonical`, `CanonicalError`, `Json`, `decimal_text` from Task 1.
- Produces, all in `entelechy.foundation.types`:
  - **Enums:** `ObjectType` (`OBSERVATION`, `INFON`, `SELF_MAP_ENTRY`), `ProvenanceKind` (seven kinds), `Polarity`, `InfonStatus`, `Operation` (all 20 operations in FOUNDATIONS §10), `EventType` (`MEMORY_CONSOLIDATED`, `INFON_FORMED`, `INFON_REVISED`, `MEMORY_FORGOTTEN`), `Stub.CONTENT_FORGOTTEN`, and `V1_OPERATIONS: frozenset[Operation]`.
  - **Frozen dataclasses with `to_canonical()` and `from_canonical(value: Json)`:** `OrganRef(id, version)`, `ObjectRef(id, version)`, `ObjectHeader(id, type, version, provenance_id, derived_from, created_seq, seq, retired_by, forgotten, body_digest)` with `.ref() -> ObjectRef`, `Provenance(id, kind, inputs, operation, organ, seed_spec, seq)`, `InfonBody(relation, participants, polarity, context, confidence, status)`, `EventRow(seq, index, type, object_id)`.
  - `Observation(id, channel, received_seq, content, identifiers)`, with `.body()` and `Observation.from_body(object_id, value)`.
  - **Referents:** `ObjectReferent(object_id)`, `RegionReferent(observation_id, region)` and `OpaqueReferent(observation_id, identifier)`; `type Referent`; `referent_to_canonical` and `referent_from_canonical`.
  - **Records and rows:** `Check(operation, rule, measured)`, `OperationEntry(operation, object_id, reason="")` and `Rows(provenance, versions, events=())`.
  - **Proposals:** `Consolidate(observation_id)`, `FormInfon(relation, participants, confidence, provenance_kind, inputs, context={}, polarity=POSITIVE, derived_from=())`, `ReviseInfon(infon_id, expected_version, body, evidence)`, `Forget(object_id, expected_version, reason, successor=None)`, `OtherOperation(name)`, `type ProposedOperation`, and `Proposal(organ, operations, reason="")`.
  - **Decoding helpers:** `field_of`, `expect_object`, `expect_list`, `expect_text`, `expect_int`, `expect_bool`, `expect_optional_int`, `expect_optional_text`, `expect_texts`, `expect_decimal`, `expect_optional_decimal` and `expect_enum`. All of them raise `CanonicalError` on malformed data.

- [ ] **Step 1: Write the failing test**

`tests/test_types.py`:

```python
from decimal import Decimal

import pytest

from entelechy.foundation.canonical import Canonical, CanonicalError, Json, canonical_bytes, parse
from entelechy.foundation.types import (
    V1_OPERATIONS,
    EventRow,
    EventType,
    InfonBody,
    InfonStatus,
    ObjectHeader,
    ObjectRef,
    ObjectReferent,
    ObjectType,
    Observation,
    OpaqueReferent,
    Operation,
    OrganRef,
    Polarity,
    Provenance,
    ProvenanceKind,
    RegionReferent,
)


def roundtrip(value: Canonical) -> Json:
    return parse(canonical_bytes(value))


HEADER = ObjectHeader(
    id="infon:1",
    type=ObjectType.INFON,
    version=2,
    provenance_id="prov:1",
    derived_from=("infon:0",),
    created_seq=3,
    seq=5,
    retired_by=None,
    forgotten=False,
    body_digest="sha256:" + "0" * 64,
)


def test_header_round_trips() -> None:
    assert ObjectHeader.from_canonical(roundtrip(HEADER.to_canonical())) == HEADER


def test_provenance_round_trips() -> None:
    provenance = Provenance(
        id="prov:1",
        kind=ProvenanceKind.DERIVATION,
        inputs=(ObjectRef("obs:1", 1), ObjectRef("infon:2", 3)),
        operation=Operation.FORM_INFON,
        organ=OrganRef("mind", "1"),
        seed_spec=None,
        seq=4,
    )
    assert Provenance.from_canonical(roundtrip(provenance.to_canonical())) == provenance


def test_origin_provenance_names_the_seed_spec_not_an_organ() -> None:
    provenance = Provenance("prov:0", ProvenanceKind.ORIGIN, (), None, None, "entelechy-seed/0", 0)
    assert Provenance.from_canonical(roundtrip(provenance.to_canonical())) == provenance


def test_infon_body_round_trips_every_referent_kind() -> None:
    body = InfonBody(
        relation="R1",
        participants=(
            ObjectReferent("self:omega"),
            RegionReferent("obs:1", {"x": [1, 2]}),
            OpaqueReferent("obs:1", "track-7"),
        ),
        polarity=Polarity.POSITIVE,
        context={"channel": "eye"},
        confidence=Decimal("0.75"),
        status=InfonStatus.ACTIVE,
    )
    assert InfonBody.from_canonical(roundtrip(body.to_canonical())) == body


def test_observation_body_round_trips() -> None:
    observation = Observation("obs:1", OrganRef("eye", "1"), 7, {"color": "red"}, ("track-7",))
    assert Observation.from_body("obs:1", roundtrip(observation.body())) == observation


def test_event_round_trips() -> None:
    event = EventRow(9, 0, EventType.INFON_FORMED, "infon:1")
    assert EventRow.from_canonical(roundtrip(event.to_canonical())) == event


def test_missing_fields_are_canonical_errors() -> None:
    with pytest.raises(CanonicalError, match="missing field"):
        ObjectHeader.from_canonical({"id": "x"})


def test_unknown_enum_values_are_canonical_errors() -> None:
    data = roundtrip(Provenance("p", ProvenanceKind.TESTIMONY, (), None, None, None, 1).to_canonical())
    assert isinstance(data, dict)
    data["kind"] = "dream"
    with pytest.raises(CanonicalError, match="unknown value"):
        Provenance.from_canonical(data)


def test_non_normalized_confidence_is_refused() -> None:
    data = roundtrip(
        InfonBody("R1", (), Polarity.POSITIVE, {}, Decimal("0.8"), InfonStatus.ACTIVE).to_canonical()
    )
    assert isinstance(data, dict)
    data["confidence"] = "0.80"
    with pytest.raises(CanonicalError, match="not normalized"):
        InfonBody.from_canonical(data)


def test_operations_match_foundations_section_10() -> None:
    assert len(Operation) == 20
    assert V1_OPERATIONS == {
        Operation.CONSOLIDATE,
        Operation.FORM_INFON,
        Operation.REVISE_INFON,
        Operation.FORGET,
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_types.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.types'`.

- [ ] **Step 3: Write the implementation**

`src/entelechy/foundation/types.py`:

```python
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


class ProvenanceKind(enum.StrEnum):
    ORIGIN = "origin"
    OBSERVATION = "observation"
    TESTIMONY = "testimony"
    DERIVATION = "derivation"
    SIMULATION = "simulation"
    EXPERIMENT = "experiment"
    SELF_OBSERVATION = "self-observation"


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
class Provenance:
    """How a commitment came to be (FOUNDATIONS §5). Never modified once written."""

    id: str
    kind: ProvenanceKind
    inputs: tuple[ObjectRef, ...]
    operation: Operation | None
    organ: OrganRef | None
    seed_spec: str | None
    seq: int

    def to_canonical(self) -> dict[str, Canonical]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "inputs": [ref.to_canonical() for ref in self.inputs],
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
            kind=expect_enum(ProvenanceKind, field_of(data, "kind"), "provenance.kind"),
            inputs=tuple(
                ObjectRef.from_canonical(item)
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
class Rows:
    """The Heart rows one transition, or the seed, produces."""

    provenance: tuple[Provenance, ...]
    versions: tuple[ObjectHeader, ...]
    events: tuple[EventRow, ...] = ()


# Proposals. Organs build these; only the validator turns them into transitions.


@dataclass(frozen=True)
class Consolidate:
    observation_id: str


@dataclass(frozen=True)
class FormInfon:
    relation: str
    participants: tuple[Referent, ...]
    confidence: Decimal
    provenance_kind: ProvenanceKind
    inputs: tuple[str, ...]
    context: dict[str, Json] = field(default_factory=dict)
    polarity: Polarity = Polarity.POSITIVE
    derived_from: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviseInfon:
    infon_id: str
    expected_version: int
    body: InfonBody
    evidence: tuple[str, ...]


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
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `27 passed`, and `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/entelechy/foundation/types.py tests/test_types.py
git commit -m "feat(foundation): normative types with canonical round trips" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: SQLite Store, Schema and Guards

**Files:**
- Create: `src/entelechy/foundation/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `canonical_bytes` and `verify` from Task 1, and the types from Task 2.
- Produces, in `entelechy.foundation.store`:
  - `class StoreError(Exception)`, `SCHEMA_VERSION = "1"` and `EXPECTED_TRIGGERS: frozenset[str]`.
  - **Opening:** `Store.create(path: Path) -> Store`, which refuses an existing path; `Store.memory() -> Store`; `Store.open(path: Path) -> Store`, which checks schema version, guards and origin; `Store.open_readonly(path: Path) -> Store`; and `store.close()`.
  - **Writes:** `store.allocate_seq() -> int`; `store.write_origin(omega_id, manifest: bytes, manifest_digest, rows: Rows, contents: Mapping[str, bytes])`; and `store.apply_replayed(rows: Rows)`, which only replay uses.
  - **Reads:** `next_seq() -> int`; `origin() -> tuple[str, bytes, str]`; `latest(object_id) -> ObjectHeader | None`; `versions(object_id: str | None = None) -> list[ObjectHeader]`; `provenance(provenance_id) -> Provenance | None`; `all_provenance() -> list[Provenance]`; `content(body_digest) -> bytes | None`; `transitions() -> list[tuple[int, bytes, str]]`; and `events() -> list[EventRow]`.
  - **Private, patched by Task 7's atomicity test:** `store._insert_rows`, `_insert_provenance`, `_insert_versions`, `_insert_inputs`, `_insert_events` and `_insert_contents`.

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:

```python
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from entelechy.foundation.canonical import digest
from entelechy.foundation.store import Store, StoreError
from entelechy.foundation.types import (
    EventRow,
    EventType,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Operation,
    OrganRef,
    Provenance,
    ProvenanceKind,
    Rows,
)

BODY = b'{"entry":"test"}'
BODY_DIGEST = digest(BODY)


def origin_rows() -> Rows:
    provenance = Provenance("prov:0", ProvenanceKind.ORIGIN, (), None, None, "entelechy-seed/0", 0)
    header = ObjectHeader(
        "self:test", ObjectType.SELF_MAP_ENTRY, 1, "prov:0", (), 0, 0, None, False, BODY_DIGEST
    )
    return Rows((provenance,), (header,))


def later_rows(seq: int) -> Rows:
    provenance = Provenance(
        "prov:1",
        ProvenanceKind.TESTIMONY,
        (ObjectRef("self:test", 1),),
        Operation.FORM_INFON,
        OrganRef("mind", "1"),
        None,
        seq,
    )
    header = ObjectHeader(
        "infon:1", ObjectType.INFON, 1, "prov:1", (), seq, seq, None, False, BODY_DIGEST
    )
    return Rows((provenance,), (header,), (EventRow(seq, 0, EventType.INFON_FORMED, "infon:1"),))


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "heart.db"


@pytest.fixture
def store(path: Path) -> Iterator[Store]:
    store = Store.create(path)
    store.write_origin("test", b"manifest", digest(b"manifest"), origin_rows(), {BODY_DIGEST: BODY})
    yield store
    store.close()


@pytest.fixture
def raw(store: Store, path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, autocommit=True)
    yield connection
    connection.close()


def test_create_refuses_an_existing_path(store: Store, path: Path) -> None:
    with pytest.raises(StoreError, match="already exists"):
        Store.create(path)


def test_open_refuses_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(StoreError, match="does not exist"):
        Store.open(tmp_path / "missing.db")


def test_open_refuses_a_file_that_is_not_a_heart(tmp_path: Path) -> None:
    path = tmp_path / "notes.db"
    path.write_bytes(b"this is not a database, just some bytes " * 4)
    with pytest.raises(StoreError, match="not an Entelechy Heart"):
        Store.open(path)


def test_open_refuses_a_heart_without_origin(path: Path) -> None:
    Store.create(path).close()
    with pytest.raises(StoreError, match="origin is missing"):
        Store.open(path)


def test_open_refuses_a_heart_whose_guards_were_dropped(
    store: Store, raw: sqlite3.Connection, path: Path
) -> None:
    raw.execute("DROP TRIGGER events_no_delete")
    with pytest.raises(StoreError, match="guards are missing"):
        Store.open(path)


def test_reads_return_what_was_written(store: Store) -> None:
    store.apply_replayed(later_rows(1))
    header = store.latest("infon:1")
    assert header is not None and header.body_digest == BODY_DIGEST
    provenance = store.provenance("prov:1")
    assert provenance is not None and provenance.inputs == (ObjectRef("self:test", 1),)
    assert store.content(BODY_DIGEST) == BODY
    assert store.events() == [EventRow(1, 0, EventType.INFON_FORMED, "infon:1")]
    assert [h.id for h in store.versions()] == ["infon:1", "self:test"]


def test_seq_is_allocated_once_even_across_reopen_seq2(store: Store, path: Path) -> None:
    assert store.allocate_seq() == 1
    assert store.allocate_seq() == 2
    store.close()
    reopened = Store.open(path)
    assert reopened.allocate_seq() == 3
    reopened.close()


def test_content_must_match_its_digest(path: Path) -> None:
    store = Store.create(path)
    with pytest.raises(StoreError, match="does not match its digest"):
        store.write_origin("test", b"m", digest(b"m"), origin_rows(), {BODY_DIGEST: b"other"})
    store.close()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE origin SET omega_id = 'someone-else'",
        "DELETE FROM origin",
        "UPDATE provenance SET kind = 'observation'",
        "DELETE FROM provenance_inputs",
        "UPDATE object_versions SET forgotten = 1",
        "DELETE FROM object_versions",
        "DELETE FROM events",
        "UPDATE transitions SET record = x'00'",
    ],
)
def test_append_only_tables_refuse_raw_changes(
    store: Store, raw: sqlite3.Connection, statement: str
) -> None:
    store.apply_replayed(later_rows(1))
    raw.execute("INSERT INTO transitions VALUES (1, x'00', 'sha256:0')")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute(statement)


def test_seq_must_increase_seq2(store: Store, raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO transitions VALUES (5, x'00', 'sha256:0')")
    with pytest.raises(sqlite3.IntegrityError, match="seq must increase"):
        raw.execute("INSERT INTO transitions VALUES (4, x'00', 'sha256:0')")


def test_next_seq_only_rises_seq2(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="only upward"):
        raw.execute("UPDATE meta SET value = '0' WHERE key = 'next_seq'")
    with pytest.raises(sqlite3.IntegrityError, match="only next_seq"):
        raw.execute("UPDATE meta SET value = '9' WHERE key = 'schema_version'")


def test_object_versions_must_be_consecutive(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="consecutive"):
        raw.execute(
            "INSERT INTO object_versions VALUES "
            "('self:test', 3, 'SelfMapEntry', 'prov:0', '[]', 0, 0, NULL, 0, 'x')"
        )


def test_live_content_cannot_be_deleted_rpl3(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="only forgotten content"):
        raw.execute("DELETE FROM content")


def test_content_cannot_be_rewritten(store: Store, raw: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        raw.execute("UPDATE content SET body = x'00'")


def test_readonly_store_cannot_write(store: Store, path: Path) -> None:
    reader = Store.open_readonly(path)
    assert reader.latest("self:test") is not None
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        reader.allocate_seq()
    reader.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_store.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.store'`.

- [ ] **Step 3: Write the implementation**

`src/entelechy/foundation/store.py`. The commit path is added in Task 7.

```python
"""SQLite persistence.

The store enforces storage invariants: append-only tables, increasing seq,
foreign keys and digest integrity. It never decides epistemic legality; the
validator does. Organs never receive a Store.
"""

import json
import sqlite3
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from entelechy.foundation.canonical import canonical_bytes, verify
from entelechy.foundation.types import (
    EventRow,
    EventType,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Operation,
    OrganRef,
    Provenance,
    ProvenanceKind,
    Rows,
)

SCHEMA_VERSION = "1"

_TABLES = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE origin (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    omega_id TEXT NOT NULL,
    manifest BLOB NOT NULL,
    manifest_digest TEXT NOT NULL
) STRICT;

CREATE TABLE transitions (
    seq INTEGER PRIMARY KEY CHECK (seq > 0),
    record BLOB NOT NULL,
    record_digest TEXT NOT NULL
) STRICT;

CREATE TABLE provenance (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    operation TEXT,
    organ_id TEXT,
    organ_version TEXT,
    seed_spec TEXT,
    seq INTEGER NOT NULL
) STRICT;

CREATE TABLE object_versions (
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    type TEXT NOT NULL,
    provenance_id TEXT NOT NULL REFERENCES provenance (id),
    derived_from TEXT NOT NULL,
    created_seq INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    retired_by INTEGER,
    forgotten INTEGER NOT NULL CHECK (forgotten IN (0, 1)),
    body_digest TEXT NOT NULL,
    PRIMARY KEY (object_id, version)
) STRICT;

CREATE TABLE provenance_inputs (
    provenance_id TEXT NOT NULL REFERENCES provenance (id),
    position INTEGER NOT NULL,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    PRIMARY KEY (provenance_id, position),
    FOREIGN KEY (object_id, version) REFERENCES object_versions (object_id, version)
) STRICT;

CREATE TABLE content (
    digest TEXT PRIMARY KEY,
    body BLOB NOT NULL
) STRICT;

CREATE TABLE events (
    seq INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    PRIMARY KEY (seq, idx)
) STRICT;
"""

_APPEND_ONLY = (
    "origin",
    "transitions",
    "provenance",
    "object_versions",
    "provenance_inputs",
    "events",
)

_GUARDS = """
CREATE TRIGGER transitions_seq_increases BEFORE INSERT ON transitions
WHEN NEW.seq <= COALESCE((SELECT MAX(seq) FROM transitions), 0)
BEGIN SELECT RAISE(ABORT, 'seq must increase (SEQ-2)'); END;

CREATE TRIGGER object_versions_in_order BEFORE INSERT ON object_versions
WHEN NEW.version <> COALESCE(
    (SELECT MAX(version) FROM object_versions WHERE object_id = NEW.object_id), 0) + 1
BEGIN SELECT RAISE(ABORT, 'object versions must be consecutive'); END;

CREATE TRIGGER meta_no_delete BEFORE DELETE ON meta
BEGIN SELECT RAISE(ABORT, 'meta: rows cannot be deleted'); END;

CREATE TRIGGER meta_only_next_seq_rises BEFORE UPDATE ON meta
WHEN OLD.key <> 'next_seq' OR NEW.key <> OLD.key
    OR CAST(NEW.value AS INTEGER) <= CAST(OLD.value AS INTEGER)
BEGIN SELECT RAISE(ABORT, 'meta: only next_seq may change, and only upward (SEQ-2)'); END;

CREATE TRIGGER content_no_update BEFORE UPDATE ON content
BEGIN SELECT RAISE(ABORT, 'content: bodies are immutable'); END;

CREATE TRIGGER content_delete_only_forgotten BEFORE DELETE ON content
WHEN EXISTS (
    SELECT 1 FROM object_versions AS v
    WHERE v.body_digest = OLD.digest
      AND NOT EXISTS (
          SELECT 1 FROM object_versions AS f
          WHERE f.object_id = v.object_id AND f.forgotten = 1
      )
)
BEGIN SELECT RAISE(ABORT, 'content: only forgotten content may be deleted (RPL-3)'); END;
"""


def _append_only_triggers() -> str:
    return "\n".join(
        f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, 'append-only: {table}'); END;"
        for table in _APPEND_ONLY
        for action in ("UPDATE", "DELETE")
    )


EXPECTED_TRIGGERS = frozenset(
    [f"{table}_no_{action}" for table in _APPEND_ONLY for action in ("update", "delete")]
    + [
        "transitions_seq_increases",
        "object_versions_in_order",
        "meta_no_delete",
        "meta_only_next_seq_rises",
        "content_no_update",
        "content_delete_only_forgotten",
    ]
)

_SCHEMA = (
    "BEGIN;\n"
    + _TABLES
    + _append_only_triggers()
    + _GUARDS
    + "INSERT INTO meta (key, value) VALUES "
    + f"('schema_version', '{SCHEMA_VERSION}'), ('digest_algorithm', 'sha256'), "
    + "('next_seq', '1');\n"
    + "COMMIT;\n"
)

_VERSION_COLUMNS = (
    "object_id, version, type, provenance_id, derived_from, created_seq, seq, "
    "retired_by, forgotten, body_digest"
)

class StoreError(Exception):
    """The database is missing, already exists, or is not an intact Entelechy Heart."""


def _header(row: Any) -> ObjectHeader:
    return ObjectHeader(
        id=row[0],
        version=row[1],
        type=ObjectType(row[2]),
        provenance_id=row[3],
        derived_from=tuple(str(item) for item in json.loads(row[4])),
        created_seq=row[5],
        seq=row[6],
        retired_by=row[7],
        forgotten=bool(row[8]),
        body_digest=row[9],
    )


class Store:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    @staticmethod
    def _connect(target: str) -> sqlite3.Connection:
        connection = sqlite3.connect(target, autocommit=True)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
        except sqlite3.DatabaseError:
            connection.close()
            raise
        return connection

    @classmethod
    def create(cls, path: Path) -> Store:
        if path.exists():
            raise StoreError(f"{path} already exists; refusing to overwrite it")
        try:
            connection = cls._connect(str(path))
        except sqlite3.Error as error:
            raise StoreError(f"cannot create {path}: {error}") from error
        connection.executescript(_SCHEMA)
        return cls(connection)

    @classmethod
    def memory(cls) -> Store:
        connection = cls._connect(":memory:")
        connection.executescript(_SCHEMA)
        return cls(connection)

    @classmethod
    def open(cls, path: Path) -> Store:
        if not path.is_file():
            raise StoreError(f"{path} does not exist")
        try:
            connection = cls._connect(str(path))
        except sqlite3.Error as error:
            raise StoreError(f"{path} is not an Entelechy Heart: {error}") from error
        return cls._checked(connection)

    @classmethod
    def open_readonly(cls, path: Path) -> Store:
        """A connection SQLite itself refuses to write through. Organs read via this."""
        if not path.is_file():
            raise StoreError(f"{path} does not exist")
        try:
            connection = sqlite3.connect(
                f"{path.resolve().as_uri()}?mode=ro", uri=True, autocommit=True
            )
        except sqlite3.Error as error:
            raise StoreError(f"{path} is not an Entelechy Heart: {error}") from error
        return cls._checked(connection)

    @classmethod
    def _checked(cls, connection: sqlite3.Connection) -> Store:
        store = cls(connection)
        try:
            store._check_schema()
        except BaseException:
            connection.close()
            raise
        return store

    def _check_schema(self) -> None:
        try:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            triggers = {
                name
                for (name,) in self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                )
            }
            origins = self._conn.execute("SELECT COUNT(*) FROM origin").fetchone()[0]
        except sqlite3.DatabaseError as error:
            raise StoreError(f"not an Entelechy Heart: {error}") from error
        if row is None or row[0] != SCHEMA_VERSION:
            raise StoreError("unsupported schema version")
        missing = EXPECTED_TRIGGERS - triggers
        if missing:
            raise StoreError(f"storage guards are missing: {sorted(missing)}")
        if origins != 1:
            raise StoreError("origin is missing")

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    # Writes

    def allocate_seq(self) -> int:
        """Reserve the next seq. It is never reused, even if nothing commits with it."""
        with self._transaction():
            seq = self.next_seq()
            self._conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'next_seq'", (str(seq + 1),)
            )
        return seq

    def write_origin(
        self,
        omega_id: str,
        manifest: bytes,
        manifest_digest: str,
        rows: Rows,
        contents: Mapping[str, bytes],
    ) -> None:
        with self._transaction():
            self._conn.execute(
                "INSERT INTO origin (singleton, omega_id, manifest, manifest_digest) "
                "VALUES (1, ?, ?, ?)",
                (omega_id, manifest, manifest_digest),
            )
            self._insert_rows(rows)
            self._insert_contents(contents)

    def apply_replayed(self, rows: Rows) -> None:
        """Insert rows decoded from lineage. Only replay calls this, on a fresh store."""
        with self._transaction():
            self._insert_rows(rows)

    def _insert_rows(self, rows: Rows) -> None:
        self._insert_provenance(rows.provenance)
        self._insert_versions(rows.versions)
        self._insert_inputs(rows.provenance)
        self._insert_events(rows.events)

    def _insert_provenance(self, provenance: Iterable[Provenance]) -> None:
        self._conn.executemany(
            "INSERT INTO provenance "
            "(id, kind, operation, organ_id, organ_version, seed_spec, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item.id,
                    item.kind.value,
                    None if item.operation is None else item.operation.value,
                    None if item.organ is None else item.organ.id,
                    None if item.organ is None else item.organ.version,
                    item.seed_spec,
                    item.seq,
                )
                for item in provenance
            ],
        )

    def _insert_versions(self, versions: Iterable[ObjectHeader]) -> None:
        self._conn.executemany(
            f"INSERT INTO object_versions ({_VERSION_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    header.id,
                    header.version,
                    header.type.value,
                    header.provenance_id,
                    canonical_bytes(list(header.derived_from)).decode("utf-8"),
                    header.created_seq,
                    header.seq,
                    header.retired_by,
                    int(header.forgotten),
                    header.body_digest,
                )
                for header in versions
            ],
        )

    def _insert_inputs(self, provenance: Iterable[Provenance]) -> None:
        self._conn.executemany(
            "INSERT INTO provenance_inputs (provenance_id, position, object_id, version) "
            "VALUES (?, ?, ?, ?)",
            [
                (item.id, position, ref.id, ref.version)
                for item in provenance
                for position, ref in enumerate(item.inputs)
            ],
        )

    def _insert_events(self, events: Iterable[EventRow]) -> None:
        self._conn.executemany(
            "INSERT INTO events (seq, idx, type, object_id) VALUES (?, ?, ?, ?)",
            [(event.seq, event.index, event.type.value, event.object_id) for event in events],
        )

    def _insert_contents(self, contents: Mapping[str, bytes]) -> None:
        for body_digest, body in contents.items():
            if not verify(body, body_digest):
                raise StoreError(f"content does not match its digest {body_digest}")
            self._conn.execute(
                "INSERT OR IGNORE INTO content (digest, body) VALUES (?, ?)",
                (body_digest, body),
            )

    # Reads

    def next_seq(self) -> int:
        row = self._conn.execute("SELECT value FROM meta WHERE key = 'next_seq'").fetchone()
        return int(row[0])

    def origin(self) -> tuple[str, bytes, str]:
        row = self._conn.execute(
            "SELECT omega_id, manifest, manifest_digest FROM origin"
        ).fetchone()
        if row is None:
            raise StoreError("origin is missing")
        return str(row[0]), bytes(row[1]), str(row[2])

    def latest(self, object_id: str) -> ObjectHeader | None:
        row = self._conn.execute(
            f"SELECT {_VERSION_COLUMNS} FROM object_versions WHERE object_id = ? "
            "ORDER BY version DESC LIMIT 1",
            (object_id,),
        ).fetchone()
        return None if row is None else _header(row)

    def versions(self, object_id: str | None = None) -> list[ObjectHeader]:
        if object_id is None:
            rows = self._conn.execute(
                f"SELECT {_VERSION_COLUMNS} FROM object_versions ORDER BY object_id, version"
            )
        else:
            rows = self._conn.execute(
                f"SELECT {_VERSION_COLUMNS} FROM object_versions WHERE object_id = ? "
                "ORDER BY version",
                (object_id,),
            )
        return [_header(row) for row in rows]

    def provenance(self, provenance_id: str) -> Provenance | None:
        row = self._conn.execute(
            "SELECT id, kind, operation, organ_id, organ_version, seed_spec, seq "
            "FROM provenance WHERE id = ?",
            (provenance_id,),
        ).fetchone()
        if row is None:
            return None
        inputs = tuple(
            ObjectRef(object_id, version)
            for object_id, version in self._conn.execute(
                "SELECT object_id, version FROM provenance_inputs "
                "WHERE provenance_id = ? ORDER BY position",
                (provenance_id,),
            )
        )
        return Provenance(
            id=row[0],
            kind=ProvenanceKind(row[1]),
            inputs=inputs,
            operation=None if row[2] is None else Operation(row[2]),
            organ=None if row[3] is None else OrganRef(row[3], row[4]),
            seed_spec=row[5],
            seq=row[6],
        )

    def all_provenance(self) -> list[Provenance]:
        ids = [row[0] for row in self._conn.execute("SELECT id FROM provenance ORDER BY id")]
        return [item for item in map(self.provenance, ids) if item is not None]

    def content(self, body_digest: str) -> bytes | None:
        row = self._conn.execute(
            "SELECT body FROM content WHERE digest = ?", (body_digest,)
        ).fetchone()
        return None if row is None else bytes(row[0])

    def transitions(self) -> list[tuple[int, bytes, str]]:
        return [
            (int(seq), bytes(record), str(record_digest))
            for seq, record, record_digest in self._conn.execute(
                "SELECT seq, record, record_digest FROM transitions ORDER BY seq"
            )
        ]

    def events(self) -> list[EventRow]:
        return [
            EventRow(seq, index, EventType(event_type), object_id)
            for seq, index, event_type, object_id in self._conn.execute(
                "SELECT seq, idx, type, object_id FROM events ORDER BY seq, idx"
            )
        ]
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `49 passed`, and `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/entelechy/foundation/store.py tests/test_store.py
git commit -m "feat(foundation): SQLite store with append-only guards" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Seed and Origin Manifest

**Files:**
- Create: `src/entelechy/foundation/seed.py`
- Test: `tests/test_seed.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces, in `entelechy.foundation.seed`:
  - `SEED_SPEC_VERSION = "entelechy-seed/0"` and `class SeedError(ValueError)`.
  - `PolicyRef(name, version)`.
  - `SeedSpec(relations, channels, organs, theta_retain=None, theta_forget=None, retention_policy=None)`.
  - `Manifest(omega_id, spec_version, relations, channels, organs, theta_retain, theta_forget, retention_policy)`, with the `.self_id` property returning `"self:<omega_id>"`, plus `.to_canonical()`, `.to_bytes()` and `Manifest.from_bytes(data)`.
  - `check_seed(spec)`, `manifest_for(spec, omega_id) -> Manifest` and `seed_heart(manifest) -> tuple[Rows, dict[str, bytes]]`.

- [ ] **Step 1: Write the failing test**

`tests/test_seed.py`:

```python
from decimal import Decimal

import pytest

from entelechy.foundation.canonical import parse
from entelechy.foundation.seed import (
    SEED_SPEC_VERSION,
    Manifest,
    PolicyRef,
    SeedError,
    SeedSpec,
    manifest_for,
    seed_heart,
)
from entelechy.foundation.types import ObjectType, OrganRef, ProvenanceKind

EYE = OrganRef("eye", "1")
MIND = OrganRef("mind", "1")
SPEC = SeedSpec(
    relations=("R1", "R2"),
    channels=(EYE,),
    organs=(MIND,),
    theta_retain=Decimal("0.5"),
    theta_forget=None,
    retention_policy=PolicyRef("fixed", "1"),
)


def test_manifest_round_trips() -> None:
    manifest = manifest_for(SPEC, "omega-1")
    assert Manifest.from_bytes(manifest.to_bytes()) == manifest


def test_manifest_lists_the_seed_objects_dev1() -> None:
    data = parse(manifest_for(SPEC, "omega-1").to_bytes())
    assert isinstance(data, dict)
    assert data["seed_objects"] == ["self:omega-1"]


def test_seed_heart_is_only_the_self_reference_slf1() -> None:
    rows, contents = seed_heart(manifest_for(SPEC, "omega-1"))
    (header,) = rows.versions
    assert header.id == "self:omega-1"
    assert header.type is ObjectType.SELF_MAP_ENTRY
    assert header.seq == 0
    assert list(contents) == [header.body_digest]


def test_seed_heart_has_origin_provenance_naming_the_seed_spec_prv7() -> None:
    rows, _ = seed_heart(manifest_for(SPEC, "omega-1"))
    (provenance,) = rows.provenance
    assert provenance.kind is ProvenanceKind.ORIGIN
    assert provenance.organ is None
    assert provenance.seed_spec == SEED_SPEC_VERSION


def test_seed_heart_is_rebuilt_exactly_from_the_manifest_dev2() -> None:
    manifest = manifest_for(SPEC, "omega-1")
    assert seed_heart(Manifest.from_bytes(manifest.to_bytes())) == seed_heart(manifest)


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (SeedSpec(("R1",), (), (MIND,)), "Body channel"),
        (SeedSpec(("R1",), (EYE,), ()), "Mind organ"),
        (SeedSpec(("R1",), (EYE,), (EYE,)), "unique"),
        (SeedSpec(("R1", "R1"), (EYE,), (MIND,)), "relations"),
        (SeedSpec(("",), (EYE,), (MIND,)), "relations"),
        (SeedSpec(("R1",), (EYE,), (MIND,), theta_retain=Decimal("1.5")), "theta_retain"),
        (SeedSpec(("R1",), (EYE,), (MIND,), theta_forget=Decimal("NaN")), "theta_forget"),
    ],
)
def test_invalid_seeds_are_refused(spec: SeedSpec, message: str) -> None:
    with pytest.raises(SeedError, match=message):
        manifest_for(spec, "omega-1")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_seed.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.seed'`.

- [ ] **Step 3: Write the implementation**

`src/entelechy/foundation/seed.py`:

```python
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
        if value is not None and not (value.is_finite() and 0 <= value <= 1):
            raise SeedError(f"{name} must be a decimal within [0, 1]")


def manifest_for(spec: SeedSpec, omega_id: str) -> Manifest:
    check_seed(spec)
    return Manifest(
        omega_id=omega_id,
        spec_version=SEED_SPEC_VERSION,
        relations=spec.relations,
        channels=spec.channels,
        organs=spec.organs,
        theta_retain=spec.theta_retain,
        theta_forget=spec.theta_forget,
        retention_policy=spec.retention_policy,
    )


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
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `61 passed`, and `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/entelechy/foundation/seed.py tests/test_seed.py
git commit -m "feat(foundation): seed specification and origin manifest" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Transition Records

**Files:**
- Create: `src/entelechy/foundation/transitions.py`
- Test: `tests/test_transitions.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces, in `entelechy.foundation.transitions`:
  - `class RecordError(ValueError)` and `RECORD_SCHEMA = 1`.
  - `DecodedRecord(seq, omega_id, rows)`.
  - `build_record(*, seq, omega_id, proposer, reason, operations, prior, provenance, versions, events, justification) -> dict[str, Canonical]`.
  - `decode_record(record: Json) -> DecodedRecord`. This is the one deterministic apply path that both commit and replay use.

- [ ] **Step 1: Write the failing test**

`tests/test_transitions.py`:

```python
import pytest

from entelechy.foundation.canonical import canonical_bytes, digest, parse
from entelechy.foundation.transitions import RecordError, build_record, decode_record
from entelechy.foundation.types import (
    Check,
    EventRow,
    EventType,
    ObjectHeader,
    ObjectRef,
    ObjectType,
    Operation,
    OperationEntry,
    OrganRef,
    Provenance,
    ProvenanceKind,
)

SECRET_BODY = b'{"content":"ultraviolet-secret"}'


def record(seq: int = 4, header_seq: int = 4) -> bytes:
    provenance = Provenance(
        "prov:1", ProvenanceKind.OBSERVATION, (), Operation.CONSOLIDATE, OrganRef("eye", "1"), None, seq
    )
    header = ObjectHeader(
        "obs:1", ObjectType.OBSERVATION, 1, "prov:1", (), seq, header_seq, None, False,
        digest(SECRET_BODY),
    )
    return canonical_bytes(
        build_record(
            seq=seq,
            omega_id="omega-1",
            proposer=OrganRef("mind", "1"),
            reason="saw something",
            operations=[OperationEntry(Operation.CONSOLIDATE, "obs:1")],
            prior=[ObjectRef("obs:0", 1)],
            provenance=[provenance],
            versions=[header],
            events=[EventRow(seq, 0, EventType.MEMORY_CONSOLIDATED, "obs:1")],
            justification=[Check(0, "MEM-1", {"clause": "evidence"})],
        )
    )


def test_record_decodes_into_rows() -> None:
    decoded = decode_record(parse(record()))
    assert decoded.seq == 4
    assert decoded.omega_id == "omega-1"
    assert [header.id for header in decoded.rows.versions] == ["obs:1"]
    assert [item.id for item in decoded.rows.provenance] == ["prov:1"]
    assert decoded.rows.events == (EventRow(4, 0, EventType.MEMORY_CONSOLIDATED, "obs:1"),)


def test_record_names_content_by_digest_only_rpl3() -> None:
    data = record()
    assert b"ultraviolet-secret" not in data
    assert digest(SECRET_BODY).encode() in data


def test_rows_stamped_with_another_seq_are_rejected() -> None:
    with pytest.raises(RecordError, match="another seq"):
        decode_record(parse(record(seq=4, header_seq=3)))


def test_non_transition_records_are_rejected() -> None:
    with pytest.raises(RecordError, match="not a v1 transition record"):
        decode_record({"type": "Origin"})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_transitions.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.transitions'`.

- [ ] **Step 3: Write the implementation**

`src/entelechy/foundation/transitions.py`:

```python
"""Transition records and the one deterministic apply path (RPL-1, RPL-3).

A record names content only by digest. Body bytes never enter lineage, so
FORGET can remove them for real.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from entelechy.foundation.canonical import Canonical, Json
from entelechy.foundation.types import (
    Check,
    EventRow,
    ObjectHeader,
    ObjectRef,
    OperationEntry,
    OrganRef,
    Provenance,
    Rows,
    expect_int,
    expect_list,
    expect_object,
    expect_text,
    field_of,
)

RECORD_SCHEMA = 1


class RecordError(ValueError):
    """A transition record is malformed or inconsistent."""


@dataclass(frozen=True)
class DecodedRecord:
    seq: int
    omega_id: str
    rows: Rows


def build_record(
    *,
    seq: int,
    omega_id: str,
    proposer: OrganRef,
    reason: str,
    operations: Sequence[OperationEntry],
    prior: Sequence[ObjectRef],
    provenance: Sequence[Provenance],
    versions: Sequence[ObjectHeader],
    events: Sequence[EventRow],
    justification: Sequence[Check],
) -> dict[str, Canonical]:
    """The canonical transition record (PER-6)."""
    return {
        "type": "Transition",
        "schema": RECORD_SCHEMA,
        "seq": seq,
        "omega_id": omega_id,
        "proposer": proposer.to_canonical(),
        "reason": reason,
        "operations": [entry.to_canonical() for entry in operations],
        "prior": [ref.to_canonical() for ref in prior],
        "provenance": [item.to_canonical() for item in provenance],
        "versions": [header.to_canonical() for header in versions],
        "events": [event.to_canonical() for event in events],
        "justification": [check.to_canonical() for check in justification],
    }


def decode_record(record: Json) -> DecodedRecord:
    """Turn a parsed record into Heart rows. Deterministic; never calls an organ."""
    data = expect_object(record, "record")
    if data.get("type") != "Transition" or data.get("schema") != RECORD_SCHEMA:
        raise RecordError("not a v1 transition record")
    seq = expect_int(field_of(data, "seq"), "record.seq")
    omega_id = expect_text(field_of(data, "omega_id"), "record.omega_id")
    provenance = tuple(
        Provenance.from_canonical(item)
        for item in expect_list(field_of(data, "provenance"), "record.provenance")
    )
    versions = tuple(
        ObjectHeader.from_canonical(item)
        for item in expect_list(field_of(data, "versions"), "record.versions")
    )
    events = tuple(
        EventRow.from_canonical(item)
        for item in expect_list(field_of(data, "events"), "record.events")
    )
    stamped = [item.seq for item in provenance]
    stamped += [header.seq for header in versions]
    stamped += [event.seq for event in events]
    if any(item != seq for item in stamped):
        raise RecordError(f"record {seq} contains rows stamped with another seq")
    return DecodedRecord(seq, omega_id, Rows(provenance, versions, events))
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `65 passed`, and `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/entelechy/foundation/transitions.py tests/test_transitions.py
git commit -m "feat(foundation): transition records that name content by digest" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Validator for CONSOLIDATE and FORM_INFON

**Files:**
- Create: `src/entelechy/foundation/validator.py`
- Create: `tests/harness.py`, `tests/conftest.py`
- Test: `tests/test_validator_infons.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 3 and 4. The harness uses `Store` and `seed_heart`.
- Produces, in `entelechy.foundation.validator`:
  - `UNIMPLEMENTED = "V1-UNIMPLEMENTED"` and `CERTAINTY = "V1-CERTAINTY"`.
  - **Protocols:** `RetentionPolicy`, with a `name` property, a `version` property and `score(object_type, body) -> Decimal`; and `HeartReader`, with `latest`, `content` and `provenance`. `Store` satisfies `HeartReader`.
  - `Violation(rule, explanation, measured={})`.
  - `Rejection(proposal, operation, violations)`, with `.rules -> frozenset[str]` and a `__str__` that reads `REJECTED` followed by one `RULE  explanation` line per violation.
  - `AcceptedTransition(seq, proposal, operations, prior, provenance, versions, events, justification, bodies, *, capability)`. Constructing one outside the validator raises `PermissionError`.
  - `Validator(manifest, policy, new_id=...)` with `.validate(proposal, seq, heart, transient) -> AcceptedTransition | Rejection`.
  - In this task, `ReviseInfon` and `Forget` are rejected as not yet built. Tasks 8 and 9 replace those two match arms.
- Also produces, in `tests/harness.py`: `EYE`, `MIND`, `OMEGA`, `FIXED`, `FixedRetention`, `plain_seed()`, `policy_seed()`, `infon_from(observation_id, relation="R1", confidence=Decimal("0.8"))`, `Harness(path, seed, policy=None)` with `.receive()`, `.propose()`, `.raw()` and `.close()`, plus `rejected()`, `accepted()` and `infon_body()`. `tests/conftest.py` provides the `heart` and `policy_heart` fixtures.

- [ ] **Step 1: Write the test harness**

`tests/harness.py`:

```python
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

    def raw(self) -> sqlite3.Connection:
        """A second, ordinary connection: what anyone with the file could do."""
        return sqlite3.connect(self.path, autocommit=True)

    def close(self) -> None:
        self.store.close()


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
```

`tests/conftest.py`:

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from harness import FixedRetention, Harness, plain_seed, policy_seed


@pytest.fixture
def heart(tmp_path: Path) -> Iterator[Harness]:
    harness = Harness(tmp_path / "heart.db", plain_seed())
    yield harness
    harness.close()


@pytest.fixture
def policy_heart(tmp_path: Path) -> Iterator[Harness]:
    harness = Harness(tmp_path / "heart.db", policy_seed(), FixedRetention())
    yield harness
    harness.close()
```

- [ ] **Step 2: Write the failing test**

`tests/test_validator_infons.py`:

```python
from dataclasses import replace
from decimal import Decimal

import pytest
from harness import EYE, MIND, Harness, accepted, infon_from, rejected

from entelechy.foundation.types import (
    Consolidate,
    EventType,
    FormInfon,
    ObjectReferent,
    OpaqueReferent,
    OrganRef,
    OtherOperation,
    Polarity,
    Proposal,
    ProvenanceKind,
)
from entelechy.foundation.validator import (
    CERTAINTY,
    UNIMPLEMENTED,
    AcceptedTransition,
)


def test_first_lifecycle_is_one_transition_mem1(heart: Harness) -> None:
    observation = heart.receive()
    result = accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    assert [event.type for event in result.events] == [
        EventType.MEMORY_CONSOLIDATED,
        EventType.INFON_FORMED,
    ]
    assert result.justification[0].rule == "MEM-1"
    assert result.justification[0].measured["clause"] == "evidence"
    assert {header.id for header in result.versions} >= {observation}


def test_the_justification_is_written_by_the_validator_per7(heart: Harness) -> None:
    observation = heart.receive()
    result = accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    assert {check.rule for check in result.justification} >= {"MEM-1", "INF-1", "PRV-4", CERTAINTY}


def test_only_the_validator_can_accept_a_transition_law5() -> None:
    with pytest.raises(PermissionError, match="Law 5"):
        AcceptedTransition(
            seq=1,
            proposal=Proposal(MIND, ()),
            operations=(),
            prior=(),
            provenance=(),
            versions=(),
            events=(),
            justification=(),
            bodies={},
            capability=object(),
        )


def test_an_unregistered_organ_is_rejected_org2(heart: Harness) -> None:
    observation = heart.receive()
    stranger = OrganRef("stranger", "1")
    result = rejected(heart.propose(Consolidate(observation), organ=stranger))
    assert result.rules == {"ORG-2"}


def test_a_channel_cannot_propose_org2(heart: Harness) -> None:
    observation = heart.receive()
    assert rejected(heart.propose(Consolidate(observation), organ=EYE)).rules == {"ORG-2"}


def test_an_empty_proposal_is_rejected_per6(heart: Harness) -> None:
    assert rejected(heart.propose()).rules == {"PER-6"}


def test_an_infon_citing_a_transient_observation_is_rejected_prv4(heart: Harness) -> None:
    observation = heart.receive()
    result = rejected(heart.propose(infon_from(observation)))
    assert "PRV-4" in result.rules
    assert any("is transient" in violation.explanation for violation in result.violations)


def test_standalone_consolidate_needs_a_bound_retention_clause_mem1(heart: Harness) -> None:
    observation = heart.receive()
    result = rejected(heart.propose(Consolidate(observation)))
    assert result.rules == {"MEM-1"}
    assert result.violations[0].measured == {
        "theta_retain": "unbound",
        "retention_policy": "unbound",
    }


def test_standalone_consolidate_succeeds_under_a_policy_mem1(policy_heart: Harness) -> None:
    observation = policy_heart.receive()
    result = accepted(policy_heart.propose(Consolidate(observation)))
    assert result.justification[0].measured["clause"] == "retention"


def test_consolidating_twice_is_rejected_per3(heart: Harness) -> None:
    observation = heart.receive()
    result = rejected(
        heart.propose(Consolidate(observation), Consolidate(observation), infon_from(observation))
    )
    assert result.operation == 1
    assert result.rules == {"PER-3"}


def test_an_unknown_observation_is_rejected_per3(heart: Harness) -> None:
    assert rejected(heart.propose(Consolidate("obs:nowhere"))).rules == {"PER-3"}


def test_negative_infons_are_unimplemented(heart: Harness) -> None:
    observation = heart.receive()
    negative = replace(infon_from(observation), polarity=Polarity.NEGATIVE)
    result = rejected(heart.propose(Consolidate(observation), negative))
    assert result.rules == {UNIMPLEMENTED}


@pytest.mark.parametrize("confidence", ["0", "1", "1.00", "-0.1", "1.5", "NaN"])
def test_certainty_is_out_of_reach_in_v1(heart: Harness, confidence: str) -> None:
    observation = heart.receive()
    infon = infon_from(observation, confidence=Decimal(confidence))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {CERTAINTY}


def test_a_relation_outside_the_vocabulary_is_rejected_inf1(heart: Harness) -> None:
    observation = heart.receive()
    infon = infon_from(observation, relation="Color")
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"INF-1"}


def test_learned_structure_cannot_claim_origin_prv5(heart: Harness) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), provenance_kind=ProvenanceKind.ORIGIN)
    assert "PRV-5" in rejected(heart.propose(Consolidate(observation), infon)).rules


@pytest.mark.parametrize("kind", [ProvenanceKind.EXPERIMENT, ProvenanceKind.SIMULATION])
def test_experiment_and_simulation_provenance_are_unimplemented(
    heart: Harness, kind: ProvenanceKind
) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), provenance_kind=kind)
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {UNIMPLEMENTED}


def test_observation_provenance_must_cite_an_observation_prv1(heart: Harness) -> None:
    infon = FormInfon(
        relation="R1",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.OBSERVATION,
        inputs=(heart.manifest.self_id,),
    )
    assert rejected(heart.propose(infon)).rules == {"PRV-1"}


def test_derivation_must_reference_inputs_prv3(heart: Harness) -> None:
    infon = FormInfon(
        relation="R1",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.DERIVATION,
        inputs=(),
    )
    assert rejected(heart.propose(infon)).rules == {"PRV-3"}


def test_testimony_from_an_organ_needs_no_inputs_org3(heart: Harness) -> None:
    infon = FormInfon(
        relation="R2",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.TESTIMONY,
        inputs=(),
    )
    result = accepted(heart.propose(infon))
    assert result.provenance[0].organ == MIND


def test_opaque_identifiers_must_come_from_the_observation_ref1(heart: Harness) -> None:
    observation = heart.receive(identifiers=("track-7",))
    unknown = replace(
        infon_from(observation), participants=(OpaqueReferent(observation, "track-9"),)
    )
    assert rejected(heart.propose(Consolidate(observation), unknown)).rules == {"REF-1"}
    known = replace(
        infon_from(observation), participants=(OpaqueReferent(observation, "track-7"),)
    )
    accepted(heart.propose(Consolidate(observation), known))


def test_a_participant_that_does_not_exist_is_rejected_ref1(heart: Harness) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), participants=(ObjectReferent("infon:ghost"),))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"REF-1"}


def test_a_missing_predecessor_is_rejected_obj4(heart: Harness) -> None:
    observation = heart.receive()
    infon = replace(infon_from(observation), derived_from=("infon:ghost",))
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"OBJ-4"}


def test_context_must_be_canonical_inf1(heart: Harness) -> None:
    observation = heart.receive()
    context: dict[str, object] = {"weight": 0.5}
    infon = replace(infon_from(observation), context=context)  # type: ignore[arg-type]
    assert rejected(heart.propose(Consolidate(observation), infon)).rules == {"INF-1"}


@pytest.mark.parametrize(
    ("name", "rule"),
    [
        ("PROPOSE_MODEL", UNIMPLEMENTED),
        ("RECORD_RESOURCE_THRESHOLD", UNIMPLEMENTED),
        ("FORM_INFON", "TRN-1"),
        ("DREAM", "TRN-1"),
    ],
)
def test_operations_outside_v1_are_rejected_by_name(heart: Harness, name: str, rule: str) -> None:
    assert rejected(heart.propose(OtherOperation(name))).rules == {rule}


def test_rejections_read_as_rules_and_reasons(heart: Harness) -> None:
    observation = heart.receive()
    text = str(rejected(heart.propose(infon_from(observation))))
    assert text.startswith("REJECTED")
    assert f"PRV-4  provenance input {observation} is transient" in text


def test_validation_does_not_touch_the_store(heart: Harness) -> None:
    observation = heart.receive()
    before = heart.store.versions()
    accepted(heart.propose(Consolidate(observation), infon_from(observation)))
    assert heart.store.versions() == before
    assert heart.store.transitions() == []
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_validator_infons.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.validator'`.

- [ ] **Step 4: Write the implementation**

`src/entelechy/foundation/validator.py`:

```python
"""The validator knows the laws but does not think.

It checks each proposal against FOUNDATIONS.md and returns either an
AcceptedTransition or a structured Rejection. It never generates content,
and only it can construct an AcceptedTransition (Law 5).
"""

import uuid
from collections.abc import Callable, Mapping, Sequence
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
    ProvenanceKind,
    Referent,
    RegionReferent,
    ReviseInfon,
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

    def content(self, body_digest: str) -> bytes | None: ...

    def provenance(self, provenance_id: str) -> Provenance | None: ...


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
        self._latest: dict[str, ObjectHeader] = {}
        self._provenance: dict[str, Provenance] = {}

    def latest(self, object_id: str) -> ObjectHeader | None:
        staged = self._latest.get(object_id)
        return staged if staged is not None else self.heart.latest(object_id)

    def content(self, body_digest: str) -> bytes | None:
        staged = self.bodies.get(body_digest)
        return staged if staged is not None else self.heart.content(body_digest)

    def provenance_of(self, provenance_id: str) -> Provenance | None:
        staged = self._provenance.get(provenance_id)
        return staged if staged is not None else self.heart.provenance(provenance_id)

    def stage(self, header: ObjectHeader, provenance: Provenance | None, body: bytes | None) -> None:
        self._latest[header.id] = header
        self.versions.append(header)
        if provenance is not None:
            self._provenance[provenance.id] = provenance
            self.provenance.append(provenance)
        if body is not None:
            self.bodies[header.body_digest] = body

    def emit(self, event_type: EventType, object_id: str) -> None:
        self.events.append(EventRow(self.seq, len(self.events), event_type, object_id))


def _cited_inputs(operation: ProposedOperation) -> tuple[str, ...]:
    match operation:
        case FormInfon(inputs=inputs):
            return inputs
        case ReviseInfon(evidence=evidence):
            return evidence
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
                return [Violation(UNIMPLEMENTED, "REVISE_INFON is not built yet")]
            case Forget():
                return [Violation(UNIMPLEMENTED, "FORGET is not built yet")]
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
            kind=ProvenanceKind.OBSERVATION,
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
        if not score.is_finite():
            return Violation(rule, "the retention policy returned a non-finite score")
        measured: dict[str, Canonical] = {
            "clause": "retention",
            "score": decimal_text(score),
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
        if op.provenance_kind is ProvenanceKind.ORIGIN:
            violations.append(Violation("PRV-5", "origin provenance is only assigned at creation"))
        if op.provenance_kind in (ProvenanceKind.EXPERIMENT, ProvenanceKind.SIMULATION):
            violations.append(
                Violation(UNIMPLEMENTED, f"{op.provenance_kind.value} provenance needs Models")
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
        inputs, input_violations = _resolve_inputs(op.inputs, work)
        violations += input_violations
        if op.provenance_kind is ProvenanceKind.OBSERVATION and not any(
            (header := work.latest(ref.id)) is not None and header.type is ObjectType.OBSERVATION
            for ref in inputs
        ):
            violations.append(
                Violation("PRV-1", "observation provenance must cite a persisted Observation")
            )
        if op.provenance_kind is ProvenanceKind.DERIVATION and not op.inputs:
            violations.append(Violation("PRV-3", "derivation provenance must reference its inputs"))
        for predecessor in op.derived_from:
            if work.latest(predecessor) is None:
                violations.append(Violation("OBJ-4", f"predecessor {predecessor} does not exist"))
        if violations:
            return violations

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
            kind=op.provenance_kind,
            inputs=inputs,
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
        work.operations.append(OperationEntry(Operation.FORM_INFON, header.id))
        work.checks += [
            Check(index, "INF-1", {"relation_in_vocabulary": True}),
            Check(index, "REF-1", {"participants": len(op.participants)}),
            Check(index, "PRV-4", {"inputs": len(inputs)}),
            Check(index, CERTAINTY, {"open_interval": True}),
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

    # Everything else

    def _other(self, op: OtherOperation) -> list[Violation]:
        if op.name in {operation.value for operation in V1_OPERATIONS}:
            return [Violation("TRN-1", f"{op.name} must be proposed with its typed operation")]
        if op.name in {operation.value for operation in Operation}:
            return [Violation(UNIMPLEMENTED, f"{op.name} is legal in FOUNDATIONS but not built in v1")]
        return [Violation("TRN-1", f"{op.name} is not a legal operation")]


def _certainty(confidence: Decimal) -> list[Violation]:
    if confidence.is_finite() and Decimal(0) < confidence < Decimal(1):
        return []
    return [
        Violation(
            CERTAINTY,
            "v1 cannot establish certainty; confidence must be strictly between 0 and 1",
            {"confidence": str(confidence)},
        )
    ]


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


def _resolve_inputs(
    object_ids: Sequence[str], work: _Work
) -> tuple[tuple[ObjectRef, ...], list[Violation]]:
    refs: list[ObjectRef] = []
    violations: list[Violation] = []
    for object_id in object_ids:
        header = work.latest(object_id)
        if header is None:
            violations.append(_missing("PRV-4", "provenance input", object_id, work))
        else:
            refs.append(header.ref())
    return tuple(refs), violations
```

- [ ] **Step 5: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `100 passed`, and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/entelechy/foundation/validator.py tests/harness.py tests/conftest.py tests/test_validator_infons.py
git commit -m "feat(foundation): validator for CONSOLIDATE and FORM_INFON" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Atomic Commit

**Files:**
- Modify: `src/entelechy/foundation/store.py`
- Modify: `tests/harness.py`
- Test: `tests/test_commit.py`

**Interfaces:**
- Consumes: `build_record` and `decode_record` from Task 5, and `AcceptedTransition` from Task 6.
- Produces:
  - `store.commit(accepted: AcceptedTransition, omega_id: str) -> None`. It raises `TypeError` for anything that is not an `AcceptedTransition`, and it deletes the content of forgotten objects only when no live object shares it.
  - In the harness: `Harness.commit(*operations) -> AcceptedTransition` and `Harness.lifecycle(content="red") -> tuple[str, str]`, which returns the Observation id and the Infon id.

- [ ] **Step 1: Extend the harness**

In `tests/harness.py`, add `Consolidate` to the `entelechy.foundation.types` import, so that the import reads:

```python
from entelechy.foundation.types import (
    Consolidate,
    FormInfon,
```

Then insert these two methods into `Harness`, directly before `def raw(self)`:

```python
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
```

- [ ] **Step 2: Write the failing test**

`tests/test_commit.py`:

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_commit.py`
Expected: failures with `AttributeError: 'Store' object has no attribute 'commit'`.

- [ ] **Step 4: Add the commit path to the store**

In `src/entelechy/foundation/store.py`, replace the line

```python
from entelechy.foundation.canonical import canonical_bytes, verify
```

with

```python
from entelechy.foundation.canonical import canonical_bytes, digest, parse, verify
from entelechy.foundation.transitions import build_record, decode_record
```

and add this line directly after the closing `)` of the `entelechy.foundation.types` import:

```python
from entelechy.foundation.validator import AcceptedTransition
```

Insert this constant directly before `class StoreError`:

```python
_DELETE_UNSHARED_CONTENT = """
DELETE FROM content WHERE digest = :digest AND NOT EXISTS (
    SELECT 1 FROM object_versions AS v
    WHERE v.body_digest = :digest
      AND NOT EXISTS (
          SELECT 1 FROM object_versions AS f
          WHERE f.object_id = v.object_id AND f.forgotten = 1
      )
)
"""
```

Insert this method directly after `apply_replayed`, before `def _insert_rows`:

```python
    def commit(self, accepted: AcceptedTransition, omega_id: str) -> None:
        """Persist one accepted transition atomically (PER-5)."""
        if not isinstance(accepted, AcceptedTransition):
            raise TypeError("only an AcceptedTransition from the validator can be committed")
        record = canonical_bytes(
            build_record(
                seq=accepted.seq,
                omega_id=omega_id,
                proposer=accepted.proposal.organ,
                reason=accepted.proposal.reason,
                operations=accepted.operations,
                prior=accepted.prior,
                provenance=accepted.provenance,
                versions=accepted.versions,
                events=accepted.events,
                justification=accepted.justification,
            )
        )
        with self._transaction():
            self._conn.execute(
                "INSERT INTO transitions (seq, record, record_digest) VALUES (?, ?, ?)",
                (accepted.seq, record, digest(record)),
            )
            # Apply from the recorded bytes, exactly as replay will (RPL-1).
            self._insert_rows(decode_record(parse(record)).rows)
            self._insert_contents(accepted.bodies)
            self._delete_forgotten_content(
                header.id for header in accepted.versions if header.forgotten
            )
```

Insert this method directly after `_insert_contents`, before the `# Reads` comment:

```python
    def _delete_forgotten_content(self, object_ids: Iterable[str]) -> None:
        for object_id in object_ids:
            digests = [
                row[0]
                for row in self._conn.execute(
                    "SELECT DISTINCT body_digest FROM object_versions WHERE object_id = ?",
                    (object_id,),
                )
            ]
            for body_digest in digests:
                self._conn.execute(_DELETE_UNSHARED_CONTENT, {"digest": body_digest})
```

- [ ] **Step 5: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `105 passed`, and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/entelechy/foundation/store.py tests/harness.py tests/test_commit.py
git commit -m "feat(foundation): atomic commit of accepted transitions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: REVISE_INFON

**Files:**
- Modify: `src/entelechy/foundation/validator.py`
- Test: `tests/test_validator_revise.py`

**Interfaces:**
- Consumes: the harness from Tasks 6 and 7.
- Produces: `REVISE_REQUIRES = "§10 REVISE_INFON"` and `Validator._revise_infon`. Revising keeps the Infon's id and increments its version. Changing relation, participants, polarity or context is rejected under INF-4 and OBJ-4. The new version's `derivation` provenance cites the prior version and the evidence. New evidence is judged per `(id, version)`.

- [ ] **Step 1: Write the failing test**

`tests/test_validator_revise.py`:

```python
from dataclasses import replace
from decimal import Decimal

import pytest
from harness import Harness, infon_body, rejected

from entelechy.foundation.types import (
    Consolidate,
    EventType,
    FormInfon,
    InfonStatus,
    ObjectRef,
    ObjectReferent,
    ProvenanceKind,
    ReviseInfon,
)
from entelechy.foundation.validator import CERTAINTY, REVISE_REQUIRES


@pytest.fixture
def formed(heart: Harness) -> tuple[str, str]:
    """A committed Observation and the Infon that cites it."""
    return heart.lifecycle()


def test_revising_confidence_keeps_identity_obj4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    header = heart.store.latest(infon_id)
    assert header is not None and header.version == 2 and header.id == infon_id
    assert infon_body(heart.store, infon_id).confidence == Decimal("0.6")
    assert result.prior == (ObjectRef(infon_id, 1),)
    assert [e.type for e in result.events][-1] is EventType.INFON_REVISED


def test_changing_the_relation_requires_a_successor_inf4_obj4(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), relation="R2")
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    )
    assert result.rules == {"INF-4", "OBJ-4"}
    assert result.violations[0].measured["changed"] == ["relation"]


def test_a_revision_must_change_something_inf4(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    )
    assert result.rules == {"INF-4"}


def test_a_revision_needs_evidence(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    assert rejected(heart.propose(ReviseInfon(infon_id, 1, body, ()))).rules == {REVISE_REQUIRES}


def test_a_revision_needs_new_evidence(heart: Harness, formed: tuple[str, str]) -> None:
    observation, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = rejected(heart.propose(ReviseInfon(infon_id, 1, body, (observation,))))
    assert result.rules == {REVISE_REQUIRES}


def test_a_stale_version_is_rejected_per6(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 7, body, (evidence,)))
    )
    assert result.rules == {"PER-6"}
    assert result.violations[0].measured == {"expected": 7, "current": 1}


def test_observations_are_never_edited_obs1(heart: Harness, formed: tuple[str, str]) -> None:
    observation, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(observation, 1, body, (evidence,)))
    )
    assert result.rules == {"OBS-1"}


def test_the_self_reference_is_not_an_infon_trn1(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = infon_body(heart.store, infon_id)
    self_id = heart.manifest.self_id
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(self_id, 1, body, (evidence,)))
    )
    assert result.rules == {"TRN-1"}


def test_retired_infons_are_final_obj3(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    first, second = heart.receive(), heart.receive()
    retired = replace(infon_body(heart.store, infon_id), status=InfonStatus.RETIRED)
    result = heart.commit(Consolidate(first), ReviseInfon(infon_id, 1, retired, (first,)))
    header = heart.store.latest(infon_id)
    assert header is not None and header.retired_by == result.seq
    revived = replace(retired, status=InfonStatus.ACTIVE)
    outcome = rejected(
        heart.propose(Consolidate(second), ReviseInfon(infon_id, 2, revived, (second,)))
    )
    assert outcome.rules == {"OBJ-3"}


def test_a_revision_derives_from_the_version_it_revises(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    revision = result.provenance[-1]
    assert revision.kind is ProvenanceKind.DERIVATION
    assert revision.inputs == (ObjectRef(infon_id, 1), ObjectRef(evidence, 1))


def test_an_infon_is_not_evidence_for_its_own_revision(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    result = rejected(heart.propose(ReviseInfon(infon_id, 1, body, (infon_id,))))
    assert result.rules == {REVISE_REQUIRES}


def test_a_newer_version_of_cited_evidence_is_new_evidence(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    witness = FormInfon(
        relation="R2",
        participants=(ObjectReferent(heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.TESTIMONY,
        inputs=(),
    )
    (witness_id,) = [h.id for h in heart.commit(witness).versions]
    lowered = replace(infon_body(heart.store, infon_id), confidence=Decimal("0.6"))
    heart.commit(ReviseInfon(infon_id, 1, lowered, (witness_id,)))
    again = replace(lowered, confidence=Decimal("0.5"))
    # The witness at version 1 is already cited.
    stale = rejected(heart.propose(ReviseInfon(infon_id, 2, again, (witness_id,))))
    assert stale.rules == {REVISE_REQUIRES}
    # Once the witness is revised, its version 2 is new evidence.
    evidence = heart.receive()
    firmer = replace(infon_body(heart.store, witness_id), confidence=Decimal("0.7"))
    heart.commit(Consolidate(evidence), ReviseInfon(witness_id, 1, firmer, (evidence,)))
    result = heart.commit(ReviseInfon(infon_id, 2, again, (witness_id,)))
    assert result.justification[1].measured["new_evidence"] == [{"id": witness_id, "version": 2}]


def test_the_justification_names_only_what_changed_per7(
    heart: Harness, formed: tuple[str, str]
) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), status=InfonStatus.CONTRADICTED)
    result = heart.commit(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    revision_checks = [check for check in result.justification if check.operation == 1]
    assert revision_checks[0].rule == "INF-4"
    assert revision_checks[0].measured == {"changed": ["status"]}


def test_revised_confidence_obeys_v1_certainty(heart: Harness, formed: tuple[str, str]) -> None:
    _, infon_id = formed
    evidence = heart.receive()
    body = replace(infon_body(heart.store, infon_id), confidence=Decimal("0"))
    result = rejected(
        heart.propose(Consolidate(evidence), ReviseInfon(infon_id, 1, body, (evidence,)))
    )
    assert result.rules == {CERTAINTY}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_validator_revise.py`
Expected: collection error, `ImportError: cannot import name 'REVISE_REQUIRES'`.

- [ ] **Step 3: Write the implementation**

In `src/entelechy/foundation/validator.py`, add this line directly after `CERTAINTY = "V1-CERTAINTY"`:

```python
REVISE_REQUIRES = "§10 REVISE_INFON"
```

In `Validator._apply`, replace the placeholder arm

```python
            case ReviseInfon():
                return [Violation(UNIMPLEMENTED, "REVISE_INFON is not built yet")]
```

with

```python
            case ReviseInfon():
                return self._revise_infon(index, operation, proposal, work)
```

Insert this section into `Validator`, directly before the `    # Everything else` comment:

```python
    # REVISE_INFON

    def _revise_infon(
        self, index: int, op: ReviseInfon, proposal: Proposal, work: _Work
    ) -> list[Violation]:
        header = work.latest(op.infon_id)
        if header is None:
            return [_missing("PER-6", "Infon", op.infon_id, work)]
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

        violations: list[Violation] = []
        content_changes = [
            name
            for name in ("relation", "participants", "polarity", "context")
            if getattr(op.body, name) != getattr(current, name)
        ]
        trust_changes = [
            name for name in ("confidence", "status") if getattr(op.body, name) != getattr(current, name)
        ]
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
        violations += _certainty(op.body.confidence)

        # New evidence is judged per version: a newer version of something
        # already cited is itself new evidence.
        evidence, evidence_violations = _resolve_inputs(op.evidence, work)
        violations += evidence_violations
        prior_provenance = work.provenance_of(header.provenance_id)
        prior_inputs = set() if prior_provenance is None else set(prior_provenance.inputs)
        new_evidence = [ref for ref in evidence if ref not in prior_inputs]
        if not op.evidence:
            violations.append(Violation(REVISE_REQUIRES, "REVISE_INFON requires evidence"))
        elif any(ref.id == header.id for ref in evidence):
            violations.append(
                Violation(REVISE_REQUIRES, "an Infon cannot be evidence for its own revision")
            )
        elif not evidence_violations and not new_evidence:
            violations.append(
                Violation(REVISE_REQUIRES, "the evidence must include an input not already cited")
            )
        if violations:
            return violations

        # The revised commitment derives from the version it revises and the
        # new evidence, so both are provenance inputs.
        body = canonical_bytes(op.body.to_canonical())
        provenance = Provenance(
            id=self._new_id("prov"),
            kind=ProvenanceKind.DERIVATION,
            inputs=(header.ref(), *evidence),
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
                index, REVISE_REQUIRES, {"new_evidence": [ref.to_canonical() for ref in new_evidence]}
            ),
            Check(index, CERTAINTY, {"open_interval": True}),
        ]
        work.emit(EventType.INFON_REVISED, header.id)
        return []
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `119 passed`, and `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/entelechy/foundation/validator.py tests/test_validator_revise.py
git commit -m "feat(foundation): REVISE_INFON keeps identity; content changes need successors" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: FORGET

**Files:**
- Modify: `src/entelechy/foundation/validator.py`
- Test: `tests/test_forget.py`

**Interfaces:**
- Consumes: the `_retention` method from Task 6 and `store.commit`'s content deletion from Task 7.
- Produces: `Validator._forget`. Forgetting adds a new version with `forgotten=True`, keeping the same provenance and body digest, and it never applies to origin structure (MEM-4).

- [ ] **Step 1: Write the failing test**

`tests/test_forget.py`:

```python
from decimal import Decimal
from pathlib import Path

from harness import FixedRetention, Harness, policy_seed, rejected

from entelechy.foundation.types import (
    EventType,
    Forget,
    FormInfon,
    ObjectReferent,
    ProvenanceKind,
)
from entelechy.foundation.validator import UNIMPLEMENTED


def test_forget_needs_a_bound_policy_mem2(heart: Harness) -> None:
    observation, _ = heart.lifecycle()
    result = rejected(heart.propose(Forget(observation, 1, "compressing")))
    assert result.rules == {"MEM-2"}
    assert result.violations[0].measured["theta_forget"] == "unbound"


def test_forget_retires_content_and_keeps_a_stub_mem3(policy_heart: Harness) -> None:
    observation, infon_id = policy_heart.lifecycle()
    before = policy_heart.store.latest(observation)
    assert before is not None
    result = policy_heart.commit(Forget(observation, 1, "compressing"))
    stub = policy_heart.store.latest(observation)
    assert stub is not None
    assert (stub.version, stub.forgotten, stub.retired_by) == (2, True, result.seq)
    assert (stub.provenance_id, stub.body_digest) == (before.provenance_id, before.body_digest)
    assert policy_heart.store.content(before.body_digest) is None
    assert [e.type for e in result.events] == [EventType.MEMORY_FORGOTTEN]
    assert result.operations[0].reason == "compressing"
    # The Infon that cited the Observation stays valid on the stub (MEM-5).
    infon = policy_heart.store.latest(infon_id)
    assert infon is not None and policy_heart.store.content(infon.body_digest) is not None


def test_a_score_above_the_threshold_is_not_forgotten_mem2(tmp_path: Path) -> None:
    heart = Harness(tmp_path / "heart.db", policy_seed(), FixedRetention(Decimal("0.9")))
    observation, _ = heart.lifecycle()
    assert rejected(heart.propose(Forget(observation, 1, "compressing"))).rules == {"MEM-2"}
    heart.close()


def test_seed_structure_cannot_be_forgotten_mem4(policy_heart: Harness) -> None:
    self_id = policy_heart.manifest.self_id
    assert rejected(policy_heart.propose(Forget(self_id, 1, "who am I"))).rules == {"MEM-4"}


def test_forgetting_twice_is_rejected_mem3(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    policy_heart.commit(Forget(observation, 1, "compressing"))
    result = rejected(policy_heart.propose(Forget(observation, 2, "again")))
    assert result.rules == {"MEM-3"}


def test_forget_needs_a_reason_mem3(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    assert rejected(policy_heart.propose(Forget(observation, 1, "  "))).rules == {"MEM-3"}


def test_forget_of_a_stale_version_is_rejected_per6(policy_heart: Harness) -> None:
    observation, _ = policy_heart.lifecycle()
    assert rejected(policy_heart.propose(Forget(observation, 2, "x"))).rules == {"PER-6"}


def test_compression_into_a_successor_is_unimplemented(policy_heart: Harness) -> None:
    observation, infon_id = policy_heart.lifecycle()
    result = rejected(policy_heart.propose(Forget(observation, 1, "compressing", infon_id)))
    assert result.rules == {UNIMPLEMENTED}


def test_transient_observations_are_not_forgotten_through_forget(policy_heart: Harness) -> None:
    observation = policy_heart.receive()
    assert rejected(policy_heart.propose(Forget(observation, 1, "x"))).rules == {"MEM-3"}


def test_shared_content_survives_forgetting_one_owner(policy_heart: Harness) -> None:
    testimony = FormInfon(
        relation="R2",
        participants=(ObjectReferent(policy_heart.manifest.self_id),),
        confidence=Decimal("0.6"),
        provenance_kind=ProvenanceKind.TESTIMONY,
        inputs=(),
    )
    result = policy_heart.commit(testimony, testimony)
    first, second = result.versions
    assert first.body_digest == second.body_digest
    policy_heart.commit(Forget(first.id, 1, "duplicate"))
    assert policy_heart.store.content(second.body_digest) is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_forget.py`
Expected: failures whose messages include `V1-UNIMPLEMENTED  FORGET is not built yet`, and rule mismatches such as `{'V1-UNIMPLEMENTED'} == {'MEM-4'}`.

- [ ] **Step 3: Write the implementation**

In `Validator._apply`, replace the placeholder arm

```python
            case Forget():
                return [Violation(UNIMPLEMENTED, "FORGET is not built yet")]
```

with

```python
            case Forget():
                return self._forget(index, operation, work)
```

Insert this section into `Validator`, directly before the `    # Everything else` comment:

```python
    # FORGET

    def _forget(self, index: int, op: Forget, work: _Work) -> list[Violation]:
        header = work.latest(op.object_id)
        if header is None:
            if op.object_id in work.transient:
                return [Violation("MEM-3", "transient state lapses on its own; FORGET is for the Heart")]
            return [Violation("MEM-3", f"there is no persistent object {op.object_id}")]
        provenance = work.provenance_of(header.provenance_id)
        if provenance is not None and provenance.kind is ProvenanceKind.ORIGIN:
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
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `129 passed`, and `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/entelechy/foundation/validator.py tests/test_forget.py
git commit -m "feat(foundation): FORGET retires content and keeps a lineage stub" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Replay and HeartView

**Files:**
- Create: `src/entelechy/foundation/replay.py`
- Modify: `tests/harness.py`
- Test: `tests/test_replay.py`

**Interfaces:**
- Consumes: `Store`, `seed_heart`, `Manifest` and `decode_record`.
- Produces, in `entelechy.foundation.replay`:
  - `class IntegrityError(Exception)`.
  - `heart_digest(store) -> str`, the digest of every version header, provenance record and event.
  - `rebuild(store, up_to=None) -> Store`, a fresh in-memory store rebuilt from origin and lineage.
  - `replay_current(store) -> str`, which raises `IntegrityError` on any mismatch.
  - `replay_historical(store, seq) -> HeartView`.
  - `HeartView(structure, content=None, forgotten_later=())`, with `latest`, `versions`, `objects`, `body` (returning `Json | Stub | None`), `infon`, `events` and `digest`.
  - In the harness: `tamper(path, guards, statement, params=())`.

- [ ] **Step 1: Add the tampering helper to the harness**

In `tests/harness.py`, insert this function directly before `def rejected(`:

```python
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
```

- [ ] **Step 2: Write the failing test**

`tests/test_replay.py`:

```python
import pytest
from harness import Harness, tamper

from entelechy.foundation.canonical import canonical_bytes, digest, parse
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_replay.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.replay'`.

- [ ] **Step 4: Write the implementation**

`src/entelechy/foundation/replay.py`:

```python
"""Replay and read-only views of the Heart (Law 7).

ReplayCurrent(Origin, Lineage, ContentStore_live) = Heart_current.
Origin and lineage rebuild structure; the live content store supplies bytes.
"""

from collections.abc import Collection

from entelechy.foundation.canonical import CanonicalError, Json, digest_of, parse, verify
from entelechy.foundation.seed import Manifest, seed_heart
from entelechy.foundation.store import Store
from entelechy.foundation.transitions import RecordError, decode_record
from entelechy.foundation.types import (
    EventRow,
    InfonBody,
    ObjectHeader,
    ObjectType,
    Stub,
)


class IntegrityError(Exception):
    """Origin, lineage, the materialized Heart and content do not agree."""


def heart_digest(store: Store) -> str:
    """Digest of structure: every version header, provenance record and event."""
    return digest_of(
        {
            "versions": [header.to_canonical() for header in store.versions()],
            "provenance": [item.to_canonical() for item in store.all_provenance()],
            "events": [event.to_canonical() for event in store.events()],
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
            decoded = decode_record(parse(record))
        except (CanonicalError, RecordError) as error:
            fresh.close()
            raise IntegrityError(f"transition {seq} is malformed: {error}") from error
        if decoded.seq != seq or decoded.omega_id != omega_id:
            fresh.close()
            raise IntegrityError(f"transition {seq} belongs to another seq or Ω")
        fresh.apply_replayed(decoded.rows)
    return fresh


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

    def body(self, object_id: str) -> Json | Stub | None:
        header = self.latest(object_id)
        if header is None:
            return None
        if header.forgotten or object_id in self._forgotten_later:
            return Stub.CONTENT_FORGOTTEN
        data = self._content.content(header.body_digest)
        if data is None or not verify(data, header.body_digest):
            raise IntegrityError(f"content of {object_id} is missing or altered")
        return parse(data)

    def infon(self, object_id: str) -> InfonBody | Stub | None:
        body = self.body(object_id)
        if body is None or isinstance(body, Stub):
            return body
        return InfonBody.from_canonical(body)

    def events(self) -> list[EventRow]:
        return self._structure.events()

    def digest(self) -> str:
        return heart_digest(self._structure)


def replay_historical(store: Store, seq: int) -> HeartView:
    """The Heart as it stood at `seq` (RPL-4). Later-forgotten content is a stub."""
    if seq < 0:
        raise ValueError("seq must not be negative")
    fresh = rebuild(store, up_to=seq)
    forgotten_now = {header.id for header in store.versions() if header.forgotten}
    return HeartView(fresh, content=store, forgotten_later=forgotten_now)
```

- [ ] **Step 5: Run the tests and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `139 passed`, and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/entelechy/foundation/replay.py tests/harness.py tests/test_replay.py
git commit -m "feat(foundation): replay from origin and lineage, with integrity checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Kernel and E000

**Files:**
- Create: `src/entelechy/foundation/kernel.py`
- Modify: `README.md`
- Test: `tests/test_kernel.py`

**Interfaces:**
- Consumes: everything above.
- Produces, in `entelechy.foundation.kernel`:
  - `class KernelError(Exception)` and `Accepted(seq, events, created)`.
  - `Kernel.create(path, seed, policies=()) -> Kernel` and `Kernel.open(path, policies=()) -> Kernel`. `open` is the wake-up: it replays all of lineage and refuses to open on any mismatch.
  - On a kernel: `omega_id`, `receive(channel, content, identifiers=()) -> str`, `propose(proposal) -> Accepted | Rejection`, `heart: HeartView` (read-only), `replay_current() -> str`, `replay_historical(seq) -> HeartView`, `close()`, and use as a context manager.

- [ ] **Step 1: Write the failing test**

`tests/test_kernel.py`:

```python
"""E000: the first lawful Heart, end to end through the kernel."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from harness import EYE, MIND, FixedRetention, infon_from, plain_seed, policy_seed, tamper

from entelechy.foundation.canonical import CanonicalError, Json
from entelechy.foundation.kernel import Accepted, Kernel, KernelError
from entelechy.foundation.replay import IntegrityError
from entelechy.foundation.store import StoreError
from entelechy.foundation.types import (
    Consolidate,
    EventType,
    Forget,
    InfonBody,
    OrganRef,
    OtherOperation,
    Polarity,
    Proposal,
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
    observation = kernel.receive(EYE, content)
    result = ok(
        kernel.propose(Proposal(MIND, (Consolidate(observation), infon_from(observation))))
    )
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
        observation = kernel.receive(EYE, "red")
        ok(kernel.propose(Proposal(MIND, (Consolidate(observation),))))
        ok(kernel.propose(Proposal(MIND, (infon_from(observation),))))
    Kernel.open(path, [FixedRetention()]).close()


type Build = Callable[[Kernel, str, str, str], Proposal]


def cite_transient(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (infon_from(fresh),))


def negative_infon(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    negative = replace(infon_from(fresh), polarity=Polarity.NEGATIVE)
    return Proposal(MIND, (Consolidate(fresh), negative))


def certain(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Consolidate(fresh), infon_from(fresh, confidence=Decimal(1))))


def impossible(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Consolidate(fresh), infon_from(fresh, confidence=Decimal(0))))


def unknown_relation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Consolidate(fresh), infon_from(fresh, relation="Color")))


def stranger(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(OrganRef("llm", "4"), (Consolidate(fresh), infon_from(fresh)))


def forget_without_policy(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Forget(observation, 1, "compressing"),))


def forget_the_self(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (Forget(f"self:{kernel.omega_id}", 1, "who am I"),))


def edit_observation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    revise = ReviseInfon(observation, 1, body_of(kernel, infon_id), (fresh,))
    return Proposal(MIND, (Consolidate(fresh), revise))


def change_relation(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    body = replace(body_of(kernel, infon_id), relation="R2")
    return Proposal(MIND, (Consolidate(fresh), ReviseInfon(infon_id, 1, body, (fresh,))))


def unbuilt(kernel: Kernel, observation: str, infon_id: str, fresh: str) -> Proposal:
    return Proposal(MIND, (OtherOperation("PROPOSE_MODEL"),))


@pytest.mark.parametrize(
    ("build", "rule"),
    [
        (cite_transient, "PRV-4"),
        (negative_infon, UNIMPLEMENTED),
        (certain, CERTAINTY),
        (impossible, CERTAINTY),
        (unknown_relation, "INF-1"),
        (stranger, "ORG-2"),
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
        fresh = kernel.receive(EYE, "blue")
        before = kernel.heart.digest()
        result = refused(kernel.propose(build(kernel, observation, infon_id, fresh)))
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


def test_an_unregistered_channel_cannot_deliver_org2(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        with pytest.raises(KernelError, match="ORG-2"):
            kernel.receive(OrganRef("ear", "1"), "noise")


def test_non_canonical_content_is_refused_before_it_uses_a_seq(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        weight: object = {"weight": 0.5}
        with pytest.raises(CanonicalError, match="floats"):
            kernel.receive(EYE, weight)  # type: ignore[arg-type]
        first_lifecycle(kernel)
        assert kernel.heart.events()[-1].seq == 2


def test_an_unknown_observation_id_is_rejected_not_raised(tmp_path: Path) -> None:
    with Kernel.create(tmp_path / "heart.db", plain_seed()) as kernel:
        typo = "obs:not-a-real-id"
        result = refused(kernel.propose(Proposal(MIND, (Consolidate(typo), infon_from(typo)))))
        assert result.rules == {"PER-3"}


def test_transient_observations_do_not_survive_restart_per4(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        observation = kernel.receive(EYE, "red")
    with Kernel.open(path) as reopened:
        proposal = Proposal(MIND, (Consolidate(observation), infon_from(observation)))
        assert refused(reopened.propose(proposal)).rules == {"PER-3"}


def test_seq_is_never_reused_across_rejection_and_restart_seq2(tmp_path: Path) -> None:
    path = tmp_path / "heart.db"
    with Kernel.create(path, plain_seed()) as kernel:
        first_lifecycle(kernel)
        first = kernel.heart.events()[-1].seq
        refused(kernel.propose(Proposal(MIND, ())))
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_kernel.py`
Expected: collection error, `ModuleNotFoundError: No module named 'entelechy.foundation.kernel'`.

- [ ] **Step 3: Write the implementation**

`src/entelechy/foundation/kernel.py`:

```python
"""The kernel: the only object an organ holds.

Organ -> Kernel -> Validator -> Store. The kernel never hands out its Store,
so Law 5 is architectural rather than conventional.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from entelechy.foundation.canonical import Json, canonical_bytes, digest
from entelechy.foundation.replay import HeartView, replay_current, replay_historical
from entelechy.foundation.seed import Manifest, PolicyRef, SeedSpec, manifest_for, seed_heart
from entelechy.foundation.store import Store
from entelechy.foundation.types import (
    EventRow,
    Observation,
    Operation,
    OrganRef,
    Proposal,
)
from entelechy.foundation.validator import (
    AcceptedTransition,
    Rejection,
    RetentionPolicy,
    Validator,
)


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


class Kernel:
    """Create with Kernel.create or Kernel.open, never directly."""

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

    def receive(
        self, channel: OrganRef, content: Json, identifiers: Sequence[str] = ()
    ) -> str:
        """A Body channel delivers an Observation. It stays transient until CONSOLIDATE."""
        if channel not in self._manifest.channels:
            raise KernelError(f"ORG-2: channel {channel.id}@{channel.version} is not registered")
        observation = Observation(f"obs:{uuid.uuid4()}", channel, 0, content, tuple(identifiers))
        canonical_bytes(observation.body())  # refuse non-canonical content before using a seq
        seq = self._store.allocate_seq()
        observation = Observation(observation.id, channel, seq, content, tuple(identifiers))
        self._transient[observation.id] = observation
        return observation.id

    def propose(self, proposal: Proposal) -> Accepted | Rejection:
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
        return replay_historical(self._store, seq)
```

- [ ] **Step 4: Run the full suite and the type checker**

Run: `uv run pytest` and then `uv run mypy`
Expected: `165 passed`, and `Success: no issues found in 23 source files`.

- [ ] **Step 5: Document how to run E000**

In `README.md`, insert this section directly before `## Further Reading`:

````markdown
## Running E000

E000 is the Foundation Validator in `src/entelechy/foundation`: a kernel that lets Entelechy exist lawfully. It needs [uv](https://docs.astral.sh/uv/), which provides Python 3.14.

```bash
uv sync
uv run pytest
uv run mypy
```

`tests/test_kernel.py` is the E000 experiment end to end.
````

- [ ] **Step 6: Commit**

```bash
git add src/entelechy/foundation/kernel.py tests/test_kernel.py README.md
git commit -m "feat(foundation): kernel and E000, the first lawful Heart" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
