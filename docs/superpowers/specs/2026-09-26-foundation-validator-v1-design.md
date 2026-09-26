# Foundation Validator v1: Design

> **Status:** Approved with corrections, 2026-09-26.
> **Implements:** a subset of [FOUNDATIONS.md](../../../FOUNDATIONS.md) draft 0.4.
> **Experiment:** E000.

## 1. Goal

Prove that Entelechy can exist lawfully. It does not yet need to learn anything.

E000 is complete when the kernel can do all of the following:

1. Create a seed.
2. Receive an Observation and hold it as transient state.
3. Commit an Infon that cites that Observation, through a legal transition.
4. Reject every illegal proposal in §9.2, with a structured rejection naming the violated rules.
5. Shut down, restart, and reproduce the identical Heart from origin and lineage.

### Non-goals

Models, Predictions, Forms, Patterns, Skills, salience, Will, Manas, learning of any kind, neural dependencies, network access, async, ORMs and plugin architecture.

- **Concurrency.** E000 supports exactly one writable kernel per Heart, with serial calls to `receive` and `propose`. Multi-writer concurrency is undefined and deferred.
- **Sandboxing.** The threat model is organs that are epistemically untrusted, not hostile native code. The capability token and private attributes are architectural discipline. Code in the same process, or with access to the database file, can get around them.

---

## 2. Principles

$$
\boxed{\text{Store does not decide legality. Validator does.}}
$$

$$
\boxed{\text{Organs never receive a Store write handle.}}
$$

The only path to persistent state is:

```text
Proposal → Validator → AcceptedTransition → Store
```

- **The validator knows the laws but does not think.** It checks proposals; it never generates content.
- **The Mind thinks but does not decide what is legal.** Organs build proposals; they cannot commit them.
- **The Heart remembers only what lawfully crossed the boundary.**
- **The store enforces storage invariants, not epistemic ones.** It guarantees append-only tables, unique increasing `seq`, foreign keys and digest integrity. Whether an Infon is justified is not its concern.
- **One apply path.** The same deterministic `apply` function turns a transition record into Heart rows during a live commit and during replay (RPL-1).

---

## 3. Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.14. It is installed through uv as CPython 3.14.6. The `python` on PATH is 3.8, so every command runs through `uv run`. |
| Runtime dependencies | Standard library only: `dataclasses`, `enum`, `sqlite3`, `hashlib`, `json`, `uuid`, `decimal`. |
| Storage | SQLite 3.53 (bundled with 3.14), with foreign keys on, WAL journal and `synchronous=FULL`. |
| Dev dependencies | `pytest` and `mypy --strict`. |
| Packaging | `pyproject.toml` managed by uv, `src/` layout. |

No Pydantic: validation belongs to our validator, not to hidden framework behaviour.

---

## 4. Package Layout

```text
src/entelechy/foundation/
    types.py        enums and frozen dataclasses for every normative structure
    canonical.py    canonical bytes and versioned digests
    store.py        SQLite schema, triggers and atomic commit
    transitions.py  deterministic apply: transition record → Heart rows
    validator.py    rule checks: Proposal → AcceptedTransition | Rejection
    replay.py       ReplayCurrent, ReplayHistorical and the Heart digest
    seed.py         seed specification and origin creation
    kernel.py       the facade organs use; owns the store privately
tests/
```

`kernel.py` is an addition to the seven modules in the original proposal. It is the one object an organ can hold, and it exposes no store.

---

## 5. Data Model

### 5.1 Canonical serialization

Every persistent structure has exactly one byte representation before it is hashed.

- **Encoding:** JSON, UTF-8, keys sorted by code point, separators `,` and `:`, no insignificant whitespace, `ensure_ascii=False`.
- **Allowed values:** `null`, booleans, integers, strings, arrays, and objects with string keys. Nothing else, so distinct values never share bytes.
- **Floats are forbidden.** Float formatting is where hash drift comes from.
- **Decimals belong to typed schemas.** Non-integer quantities such as confidence are `decimal.Decimal`. The generic encoder refuses them; the typed schema that owns the field writes it as a normalized fixed-point string such as `"0.8"` and decodes it by field. If the generic encoder accepted Decimals, `Decimal("0.8")` and the string `"0.8"` would share one encoding.
- **Dates and times are rejected by the encoder** (SEQ-3).
- Every encoded structure carries `type` and `schema` fields.

A digest is written as `sha256:<hex>`. The algorithm prefix is stored with every digest so that it can be replaced later without confusing identity.

### 5.2 Header and body

Each object version is split into two parts:

- **Header:** `id`, `type`, `version`, provenance reference, `derived_from`, `created_seq`, `retired_by` and a `forgotten` flag. Headers are never forgotten.
- **Body:** the type-specific content, stored in a content-addressed store under its digest. `FORGET` can remove a body; it never touches a header or a digest.

Every version is immutable. A status change produces a new version with a new body digest (OBJ-4).

Transition records contain digests, never body bytes (RPL-3). The bytes travel with the accepted transition into the content store, and only there. This is what makes forgetting real: once `FORGET` deletes a body, no immutable record still holds it.

### 5.3 SQLite schema

| Table | Holds | Mutability |
| --- | --- | --- |
| `meta` | schema version, digest algorithm, `next_seq` | `next_seq` may only increase |
| `origin` | `omega_id`, manifest bytes and manifest digest | immutable |
| `provenance` | `kind`, `organ`, `organ_version` or `seed_spec`, `operation`, `seq` | append-only |
| `provenance_inputs` | provenance id → input `(object_id, version)` | append-only |
| `object_versions` | object headers and `body_digest` | append-only |
| `object_derivations` | object → the objects it `derived_from` | append-only |
| `content` | `digest` → body bytes | deletion only as described below |
| `transitions` | `seq`, record bytes and record digest | append-only |
| `events` | `seq`, index, event type, transition `seq` | append-only |

Triggers enforce these rules physically:

- **Append-only tables:** `BEFORE UPDATE` and `BEFORE DELETE` triggers abort with `append-only: <table>`.
- **Ordering:** `transitions.seq` is a primary key, and an insert trigger requires it to exceed the current maximum (SEQ-2).
- **Content deletion:** a delete from `content` is allowed only when every object version referencing that digest belongs to an object whose latest version is `forgotten`. Content is deduplicated by digest, so this stops one `FORGET` from erasing another object's identical body.

`object_versions` and `events` are a materialized Heart. They can always be derived from `origin` and `transitions`, and replay checks that they are.

### 5.4 Transient state

The kernel holds received but unconsolidated Observations in memory, keyed by Observation id. A restart discards them (PER-4).

Receiving an Observation allocates its `received_seq` in a small SQL transaction that only advances `meta.next_seq`. That allocation is machinery, not an epistemic mutation, so it is not a transition. It guarantees `seq` is never reused across restarts (SEQ-2).

### 5.5 Seed

A `SeedSpec` contains:

- a seed specification version, `entelechy-seed/0`,
- the relation vocabulary (OPEN-2; test seeds use neutral names such as `R1`),
- the registered Body channels and Mind organs, each with a version,
- parameter bindings, each explicitly bound or `unbound`,
- an optional retention policy, named with its version.

`create` generates `omega_id`, writes the manifest to `origin`, and writes the seed Heart. In v1 the seed Heart is a single SelfMapEntry holding the self-reference (SLF-1). Its id is derived deterministically from `omega_id`, and it carries `origin` provenance naming the seed specification (DEV-1, PRV-7). The manifest alone is enough to rebuild the seed Heart (DEV-2).

Origin is not a transition. Lineage starts at `seq` 1.

---

## 6. Proposal, Validation and Commit

### 6.1 Proposal

A proposal contains:

- `organ`: the proposing organ's id and version,
- `operations`: an ordered list, applied atomically as one transition (PER-9),
- `reason`: the proposer's own free-text account, recorded but never trusted.

The v1 operations are:

| Operation | Carries |
| --- | --- |
| `Consolidate` | a transient Observation id |
| `FormInfon` | relation, participants, polarity, context, confidence, provenance kind and inputs, optional `derived_from` |
| `ReviseInfon` | Infon id, expected version, a full proposed body, evidence inputs |
| `Forget` | object id, expected version, reason, optional successor |

`ReviseInfon` carries a full body rather than just the changed fields, so that an attempt to change the relation reaches the validator and is rejected by name (INF-4).

### 6.2 Validation

`Validator.validate(proposal, heart, transient)` evaluates operations in order against a staged view. An Observation consolidated earlier in the same proposal therefore counts as persistent for a later `FormInfon`, which is how MEM-1's evidence clause works.

Validation stops at the first failing operation and reports every violation of that operation. Later operations would only produce cascading errors.

The result is one of:

```text
AcceptedTransition
    proposal
    resolved object versions, provenance and events
    justification       generated by the validator: every rule checked and its measured values

Rejection
    proposal
    violations          list of (rule_id, measured_values, explanation)
```

The justification is written by the validator, not by the organ, so a transition's legality can be checked independently of whoever proposed it (PER-7).

Rejections are transient in v1. They are returned to the proposer and never persisted. Their shape is fixed now so that future Minds can learn the laws of their existence from them:

```text
REJECTED
    PRV-4  provenance input obs:… is transient
```

`AcceptedTransition` can only be constructed by the validator. Its constructor checks a module-private capability token.

### 6.3 Commit

`store.commit(accepted)` runs in one SQL transaction:

1. Allocate `seq`.
2. Build the transition record with `transitions.build_record(accepted, seq)` and compute its digest.
3. Run `transitions.apply(record)` to produce the provenance, object version, derivation and event rows.
4. Write those rows, write the accepted transition's body bytes to `content`, and delete any content that is now forgotten.
5. Commit.

Any exception rolls back the whole transaction (PER-5).

### 6.4 Kernel API

This is the only surface an organ touches.

```text
Kernel.create(path, seed_spec) → Kernel
Kernel.open(path, policies)    → Kernel        runs ReplayCurrent; refuses to open on mismatch
kernel.receive(channel, content, identifiers) → ObservationRef
kernel.propose(proposal)       → Accepted(seq, events) | Rejection
kernel.heart                   → read-only HeartView
kernel.replay_current()        → HeartDigest
kernel.replay_historical(seq)  → HeartView
```

`Kernel.open` replays the whole lineage and compares it with the materialized Heart before accepting any proposal. In v1 lineage is tiny, and this wake-up check is the most direct test of Law 7.

---

## 7. Rules Enforced in v1

| Area | Rules | How v1 checks them |
| --- | --- | --- |
| Commit boundary | PER-2, PER-3, PER-5, PER-6, PER-7, PER-9 | Only `propose` writes. The typed operation is the boundary. There is one SQL transaction per transition, and the justification is generated by the validator. |
| Ordering | SEQ-1, SEQ-2, SEQ-3 | One counter, trigger-enforced increase, no dates or times in canonical content. |
| Replay | RPL-1 to RPL-4 | Shared `apply`, digest-addressed content, content-deletion trigger, `CONTENT_FORGOTTEN` stubs in historical replay. |
| Identity | OMG-1, OMG-2, OMG-5 | Immutable `origin`, append-only lineage, wake-up replay. |
| Provenance | PRV-1 to PRV-7 | Every object version has provenance. Inputs must be persistent. `origin` is only assigned by `create`. No operation changes provenance. |
| Organs | ORG-1, ORG-2 | The proposing organ must be registered in the manifest at the stated version. |
| Objects | OBJ-1 to OBJ-4 | Shared header. `ReviseInfon` diffs the proposed body against the current one. |
| Referents | REF-1 to REF-3 | Each participant is an object id, an Observation region, or an opaque identifier listed in a persisted Observation's `identifiers`. |
| Observations | OBS-1, OBS-3 | No operation edits an Observation. `received_seq` is assigned at receipt. OBS-2 is satisfied by the stricter V1-CERTAINTY. |
| Infons | INF-1 to INF-5 | See below. INF-6 is not needed, because v1 rejects negative Infons. |
| Seed | SLF-1, DEV-1, DEV-2 | Checked after `create` and on every replay. |
| Events | EVT-1, EVT-3 | Events are written only by `apply`. |
| Memory | MEM-1 to MEM-5 | See below. |
| Scope | TRN-1 | Unknown operations are rejected under TRN-1. Operations listed in FOUNDATIONS §10 but not built in v1 are rejected with `V1-UNIMPLEMENTED`. |

### v1 restrictions

Some things FOUNDATIONS permits, v1 cannot yet check. v1 rejects them under its own rule IDs, never under a FOUNDATIONS rule that says something weaker.

| ID | Restriction | Why |
| --- | --- | --- |
| `V1-UNIMPLEMENTED` | Rejects every operation outside v1, `experiment` and `simulation` provenance, and every negative-polarity Infon. | Experiments and simulations need Models. A negative Infon needs INF-6's counterfactual evidence, which v1 has no machine-checkable contract for. Accepting the proposer's word would make the validator's first exception to Law 5. |
| `V1-CERTAINTY` | Every Infon's confidence must be strictly between 0 and 1. | v1 has no mechanism for establishing certainty. Confidence 0 on a positive Infon would also be a back door to asserting $\neg R$ while negative Infons are unimplemented. |

### Infon specifics

- **Relation:** must be in the seed vocabulary.
- **Polarity:** positive only (`V1-UNIMPLEMENTED`).
- **Confidence:** a `Decimal` strictly between 0 and 1 (`V1-CERTAINTY`). This is v1's choice under the "MAY" in §8.4 of FOUNDATIONS. Contradiction is expressed through `status`, not by lowering confidence to 0.
- **Context:** stored as an opaque canonical map in v1. The validator does not interpret it.
- **Provenance kinds:** v1 accepts `observation`, `testimony`, `derivation` and `self-observation`.
- **PRV-3:** acyclicity is structural. Inputs must already exist, so a new object can never be its own input.
- **REVISE_INFON:** the revised version's `derivation` provenance cites the version it revises and the new evidence. At least one evidence input must be new, judged per `(id, version)`, and an Infon is never evidence for its own revision.

### Memory specifics

- **MEM-1:** consolidation is always legal when the Observation is cited as an input by a commit in the same proposal. The retention clause is legal only when the seed binds both $\theta_{retain}$ and a retention policy. If either is missing, the rejection cites MEM-1 and names what is unbound, for example `θ_retain: unbound`.
- **MEM-2:** `FORGET` likewise needs $\theta_{forget}$ and a retention policy. v1 has no Patterns or Forms, so the compression clause is unavailable.
- **Retention policies:** the retention function $f$ is OPEN-5, so a policy is a named, versioned piece of code declared in the seed. There is no default. Tests declare a fixed test policy. A production seed with no policy therefore has no standalone `CONSOLIDATE` and no `FORGET`, which is the honest consequence of those parameters being unbound.

---

## 8. Replay

$$
ReplayCurrent(Origin,\ Lineage,\ ContentStore_{live}) = Heart_{current}
$$

Origin and lineage rebuild structure. The live content store supplies bytes.

**ReplayCurrent** works in three steps:

1. Build a fresh in-memory database from the `origin` manifest.
2. Apply every transition record in `seq` order, verifying each record's digest. This rebuilds every header, digest, provenance record and event.
3. Compare the resulting Heart digest with the stored Heart. Then check every body the rebuilt Heart says is live: it must be present in the content store and match its digest.

The **Heart digest** is the digest of the canonical, ordered list of every object version header, body digest and event. It covers structure, not bytes, which is why step 3 checks the bytes separately.

**ReplayHistorical(n)** does the same up to `seq` $n$ and returns a read-only view. Where a body has since been deleted by `FORGET`, the view returns a `CONTENT_FORGOTTEN` stub and nothing else (RPL-4).

Replay never generates ids and never invokes an organ. Every id is already in the recorded transitions.

---

## 9. Tests

Each test is named after the rule IDs it exercises.

### 9.1 First lifecycle

With a seed that binds no retention policy:

```text
create seed
receive O1                               transient
propose [Consolidate O1, FormInfon I1]   one transition; I1 cites O1
    → events MEMORY_CONSOLIDATED, INFON_FORMED
close
open                                     wake-up replay passes
heart equals the Heart before shutdown
```

This differs from the lifecycle in the original proposal, where `CONSOLIDATE O1` was a separate step. Under MEM-1, a standalone consolidation needs a retention score, and both $f$ and $\theta_{retain}$ are unbound. The evidence clause lets the Observation cross in the same transition as the Infon that cites it. A second test runs the two-step version under a seed with a test retention policy.

### 9.2 Illegal proposals

| Attempt | Expected result |
| --- | --- |
| An organ writes to the Heart directly | No API exists. Constructing `AcceptedTransition` outside the validator raises. Raw SQL to append-only tables aborts. |
| An Infon cites a transient Observation | Rejected: PRV-4 |
| Any negative Infon | Rejected: `V1-UNIMPLEMENTED` |
| Modifying an Observation | Rejected: OBS-1. Raw SQL aborts. |
| Rewriting provenance | No operation exists. Raw SQL aborts. |
| Reusing `seq` | The trigger aborts. |
| A transition fails partway | Fault injection mid-commit leaves no rows (PER-5). |
| Changing an Infon's relation through `ReviseInfon` | Rejected: INF-4 and OBJ-4. A successor is required. |
| Removing an object with raw `DELETE` | The trigger aborts. |
| A proposal from an unregistered organ | Rejected: ORG-2 |
| A relation outside the vocabulary | Rejected: INF-1 |
| Confidence 0 or 1 | Rejected: `V1-CERTAINTY` |
| `Forget` on the Self Map's self-reference | Rejected: MEM-4 |
| A content byte string that no longer matches its digest | `Kernel.open` refuses to open (RPL-2). |
| `Forget` with no bound policy | Rejected: MEM-2, `θ_forget: unbound` |
| An operation not built in v1 | Rejected: `V1-UNIMPLEMENTED` |

Every rejection test also asserts that the Heart digest and all row counts are unchanged.

### 9.3 Replay and forgetting

Under a test policy: form an Infon, forget its Observation, and then check three things. ReplayCurrent is exact. ReplayHistorical at a point before the `FORGET` shows `CONTENT_FORGOTTEN` for the Observation body and exact headers and digests for everything. The Infon remains valid, because its input survives as a stub (MEM-5).

A tampering test edits a transition record's bytes directly in the database file. `Kernel.open` must refuse to open.

---

## 10. Decisions Made in This Design

These are choices I made that the design discussion did not settle.

1. `kernel.py` is added as the organ-facing facade.
2. Floats are forbidden in canonical content, and confidence is a `Decimal`.
3. Objects are split into a header, which is never forgotten, and a content-addressed body, which `FORGET` can remove. Every version is immutable.
4. Content is deduplicated by digest, and a trigger stops one `FORGET` from deleting a body that another live object still shares.
5. The validator writes the justification. The organ's `reason` is recorded but not trusted.
6. Validation stops at the first failing operation and reports all of that operation's violations.
7. Negative Infons are rejected in v1 until there is a machine-checkable negative-evidence contract (`V1-UNIMPLEMENTED`).
8. `experiment` and `simulation` provenance are rejected in v1, and confidence must be strictly between 0 and 1 (`V1-CERTAINTY`).
9. `Kernel.open` always runs a full replay.
10. Standalone `CONSOLIDATE` and `FORGET` need a seed-declared retention policy. There is no default policy.
11. Ids are UUIDs generated at validation time and recorded in the transition, so replay never generates them.

## 11. Spec Changes Made for This Design

These gaps were found while designing and are resolved in FOUNDATIONS 0.4:

- **Replay and forgetting.** Law 7 now names the live content store, and transition records must not contain content bytes (RPL-2, RPL-3).
- **Forgetting seed structure.** MEM-4 now forbids forgetting seed structure, including the Self Map's self-reference.
- **Observation identifiers.** Observations carry an `identifiers` list supplied by the channel, which is what REF-1's opaque identifiers point at (§8.2).

## 12. Recorded, Not Blocking

- **Implementation identity (OPEN-15).** v1 identifies organs and retention policies by name and version only. A label does not prove that tomorrow's code called version 1 is the same code. A later version should identify executable components by artifact digest, $\langle name,\ version,\ digest \rangle$.
