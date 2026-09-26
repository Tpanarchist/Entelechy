# Entelechy Foundations

> **Status:** Draft 0.5, 2026-09-26. Normative. Changes between drafts are listed in §18.

[README.md](README.md) says what Entelechy is. [ARCHITECTURE.md](ARCHITECTURE.md) explains how its parts fit together. This document says what an implementation MUST, MAY and MUST NOT do. It is written so that each rule can become an assertion, a validator check or a test.

Where this document and ARCHITECTURE.md disagree, this document governs until one of them is amended.

---

## 0. Normative Vocabulary

| Keyword | Meaning |
| --- | --- |
| **MUST** | Hard invariant. A state that violates it is not a valid Entelechy state. |
| **MUST NOT** | Forbidden state or transformation. |
| **REQUIRES** | The operation is legal only if the named preconditions hold. |
| **EMITS** | The operation must produce the named persistent event. |
| **MAY** | Implementation freedom. |
| **PARAMETER** | A named quantity that is intentionally unbound, to be set by experiment rather than assumed. |
| **OPEN** | An unresolved foundational question. Nothing marked OPEN is settled. |

Every rule has an ID (for example `PRV-2`) so that code, tests and later amendments can cite it. IDs are stable across drafts; a rule that is removed keeps its ID retired rather than reused.

---

## 1. Laws

### Law 1: No silent semantic mutation

> Any operation that changes what Entelechy persistently believes, remembers, predicts, values, identifies with, or knows how to do MUST produce an attributable transition preserving both the prior state and the reason for the new state.

### Law 2: Persistence requires provenance; transformation requires lineage

$$
\boxed{\textbf{Persistence requires provenance; transformation requires lineage.}}
$$

Every persistent epistemic commitment carries a record of how it came to be (**provenance**). Every change to one is recorded as a transition linking its prior state to its new state (**lineage**).

### Law 3: Identity is not state

$$
\Omega_{identity}(t_0)=\Omega_{identity}(t_n)
\quad\not\Rightarrow\quad
\Omega_{state}(t_0)=\Omega_{state}(t_n)
$$

What Entelechy *is* stays fixed. What it believes, prefers and can do may change without limit.

### Law 4: Perception is not reality; information is not truth

Observations are evidence about the world, not the world. Infons are commitments held with some confidence, not facts.

### Law 5: Organs propose; transitions commit

No Mind organ, Body component, language model, Manas or accounting subsystem writes persistent state directly. They produce candidates. Only a legal transition (§10) changes persistent state.

### Law 6: Absence of evidence is not negative evidence

$$
\neg Known(R) \;\not\Rightarrow\; Known(\neg R)
$$

> The absence of an Infon asserting $R$ MUST NOT be interpreted as an Infon asserting $\neg R$.

A negative Infon is a commitment like any other and needs its own provenance (INF-6). Entelechy never operates under a closed-world assumption by default.

### Law 7: The Heart is reconstructible from origin, lineage and live content

$$
\boxed{ReplayCurrent(Origin,\ Lineage,\ ContentStore_{live}) = Heart_{current}}
$$

Replay to the present MUST be exact. Replay to an earlier point, $ReplayHistorical(n)$, MUST reproduce structure, digests and lineage exactly, but MAY show a `CONTENT_FORGOTTEN` stub in place of content that was forgotten after $n$ (RPL-4).

Snapshots are an optimization. The authoritative history of Entelechy is

$$
\boxed{Origin + Lineage.}
$$

It is authoritative for structure, identity, transitions, digests, provenance and history. The content store supplies only the bytes, and every byte string is checked against the digest lineage recorded for it.

Lineage alone cannot reconstruct every byte, and it must not. Entelechy cannot both keep every byte in immutable lineage and let `FORGET` remove bytes permanently. If forgotten bytes survived anywhere in lineage, they were never forgotten.

This forgetting is logical, not secure erasure (MEM-6). Lineage keeps each body's digest, and a digest lets someone confirm a guess, so sufficiently low-entropy content can still be recovered by guessing. Secure forgetting is OPEN-16.

If Entelechy holds a belief and we ask why, its developmental path to that belief can be reconstructed transition by transition.

### Consequences

Laws 1, 2 and 7 together forbid:

- silent belief replacement,
- silent memory rewriting,
- silent Skill mutation,
- silent self-model change,
- rewriting provenance after the fact,
- any write path that bypasses lineage, including from accounting or monitoring code.

They also mean forgetting persistent information is never `delete(x)`. It is an explicit `FORGET(x)` with a reason and a prior-state reference, after which the fact that `x` once existed remains in lineage even though its content is retired (§12).

---

## 2. Transient and Persistent State

The fundamental boundary is **persistent versus transient**, not which memory tier holds the state.

**Transient cognitive state** consists of:

- $M_{instant}$ and $M_{working}$,
- Observations that have been received but not consolidated,
- organ activations and in-flight computation,
- discrepancies and salience values not yet recorded,
- resource accounting ($R_t$),
- candidate structures proposed by organs but not yet committed.

**Persistent state** consists of:

- $\Omega_{identity}$ (§4),
- the **Heart**: $M_{episodic}$, $M_{semantic}$, $M_{structural}$, $M_{identity}$, and all persistent objects (§7), transition records and events,
- $\Omega_{state}$, which lives in the Heart as its self-related structure.

Content crosses from transient to persistent state at a **commit boundary**. There are two kinds:

$$
\boxed{\text{Transient memory enters persistent memory through CONSOLIDATE.}}
$$

$$
\boxed{\text{Transient epistemic candidates enter the Heart through their typed commit operation.}}
$$

So `CONSOLIDATE` means memory consolidation specifically: Observations and episodes. `FORM_INFON` is the boundary crossing for an Infon, `PROPOSE_MODEL` for a Model, `COMPILE_SKILL` for a Skill, and so on.

- **PER-1** Transient state MAY change without transitions or events.
- **PER-2** Every change to persistent state MUST be a transition using one of the operations in §10.
- **PER-3** Transient content MUST enter persistent state only through a transition. Observations and episodes enter through `CONSOLIDATE`. Every other persistent object enters through the typed commit operation for its type.
- **PER-4** Losing all transient state, through a crash, restart or organ swap, MUST leave $\Omega_{identity}$ and the Heart valid. Entelechy resumes from the Heart.
- **PER-5** Transitions MUST be atomic. Either the new state, its transition record and its events all persist, or none of them do.
- **PER-6** A transition record MUST contain:
  - `seq`: its position in the ordering (§3),
  - `operation`: the triggering operation,
  - `prior_state`: the `(id, version)` of each object it changes, or `∅` for creation,
  - `new_state`: the `(id, version)` and content digest of each object it produces (RPL-3),
  - `provenance`: where the new content came from (§5),
  - `justification`: why this transition was legal,
  - `events`: the one or more events it emits.
- **PER-7** A justification MUST cite the rule it claims to satisfy and the measured values, so that its legality can be checked independently of the organ that proposed it.
- **PER-8** Prior states MUST remain retrievable in full. The only exception is content retired by `FORGET`, and even then a lineage stub MUST remain (§12).
- **PER-9** One transition record MAY cover several objects, provided each change within it is individually attributable.

---

## 3. Ordering and Replay

Entelechy's machinery must order what happens to it. Ordering is not a concept of time. Physical time is something Entelechy may learn about; it is not given to it.

$$
\boxed{\text{ordering machinery} \neq \text{concept of time}}
$$

- **SEQ-1** A single monotonic counter, `seq`, orders every transition and every Observation receipt. That $a$ carries a lower `seq` than $b$ means only $a \prec b$.
- **SEQ-2** `seq` MUST strictly increase and MUST NOT be reused, including across restarts.
- **SEQ-3** Wall-clock timestamps MAY be stored as implementation metadata, but MUST NOT be read as epistemic commitments. If Entelechy is to reason about clock time, a clock is a Body channel and its readings are Observations.
- **RPL-1** Applying a recorded transition MUST be deterministic and MUST NOT invoke any organ. Replay re-applies recorded results; it never re-runs the computation that proposed them.
- **RPL-2** $ReplayCurrent(Origin, Lineage, ContentStore_{live})$ MUST equal $Heart_{current}$ exactly, and every byte string it reads from the content store MUST match its recorded digest. A snapshot MAY be kept as an optimization. It MUST equal replay at its `seq`, and where they differ, replay is authoritative.
- **RPL-3** Transition records MUST identify content by digest only and MUST NOT contain content bytes. Content bytes live in a separate content store. `FORGET` removes bytes from that store but MUST NOT alter any transition record or digest. $ReplayCurrent$ is therefore always exact, because forgotten content appears in $Heart_{current}$ only as a stub anyway.
- **RPL-4** $ReplayHistorical(n)$ MUST reproduce every object header, digest and lineage entry up to `seq` $n$ exactly. Where content was forgotten after $n$, it MAY return a `CONTENT_FORGOTTEN` stub in place of that content, and MUST NOT return anything else in its place.

---

## 4. Identity (Ω)

$$
\Omega = \langle \Omega_{identity},\ \Omega_{state} \rangle
$$

$$
\Omega_{identity} = \langle \texttt{omega\_id},\ \texttt{origin},\ \texttt{lineage} \rangle
$$

- `omega_id` is the unique identifier of this Entelechy.
- `origin` is the complete seed it was created from (§9), at `seq` 0.
- `lineage` is the append-only sequence of every transition since origin.

$\Omega_{state}$ holds the Self Map, preferences, goals, relationships, capabilities and history.

- **OMG-1** `omega_id` and `origin` MUST NOT change.
- **OMG-2** `lineage` MUST be append-only. For all $t_0 < t_n$, $lineage(t_0)$ is a prefix of $lineage(t_n)$.
- **OMG-3** $\Omega_{state}$ MAY evolve, but only through transitions.
- **OMG-4** Attaching, replacing or removing a Mind organ, Body component or storage backend MUST NOT change $\Omega_{identity}$. Each such change MUST be recorded with `CHANGE_ORGAN`.
- **OMG-5** Entelechy at $t_n$ is the same system as Entelechy at $t_0$ if and only if both have the same `omega_id` and an unbroken lineage of legal transitions connects them. A system holding the same Heart content without that lineage is a copy, not a continuation.

Two instances with identical lineage are identical up to their last shared transition. Once $T^{A}_{n+1} \neq T^{B}_{n+1}$, they are two continuations sharing ancestry. Which of them, if either, continues Ω is OPEN-9.

---

## 5. Provenance

Provenance records how an epistemic commitment came to be. It does not need an external source. A derivation chain is valid provenance:

```text
OBSERVATION O17
OBSERVATION O22
MODEL M4
DERIVATION D9
→ INFON I51
```

### Provenance kinds

| Kind | Meaning |
| --- | --- |
| `origin` | Constituted in the seed at creation. |
| `observation` | Received through a Body channel and persisted by `CONSOLIDATE`. |
| `testimony` | Asserted by an external agent or source, including content an organ supplies from its own pretraining (ORG-3). |
| `derivation` | Inferred from other commitments by a named operation. |
| `simulation` | Produced by running a Model internally. |
| `experiment` | The outcome of an action chosen to discriminate between Models (§13). |
| `self-observation` | Observation of Entelechy's own state or cognition. |

A provenance record contains `kind`, `inputs` (references to what it was derived from), `operation`, `organ` (the organ and version that proposed it) and `seq`. For `origin` provenance, `organ` is replaced by `seed_spec`, which identifies the seed specification. There is no seed organ.

- **PRV-1** No epistemic commitment exists without provenance.
- **PRV-2** Provenance MUST NOT be modified after it is written.
- **PRV-3** `derivation` and `simulation` provenance MUST reference their inputs. The provenance graph MUST be acyclic, so nothing is its own justification.
- **PRV-4** Committing an object REQUIRES that every provenance input is itself persistent, at least as a lineage stub. An input MAY be made persistent in the same transition (MEM-1).
- **PRV-5** `origin` provenance MUST only be assigned at creation. Learned structure MUST NOT be relabelled `origin`.
- **PRV-6** A provenance kind MUST NOT be upgraded. For example, a simulated result must never be recorded as observed.
- **PRV-7** For every provenance kind except `origin`, `organ` MUST identify both the organ and its version, so that a conclusion can still be traced to the Mind that proposed it after that Mind is replaced. `origin` provenance MUST identify the seed specification instead.

---

## 6. Organs: Mind, Body and Language

Organs are the replaceable machinery through which Entelechy perceives, computes and acts. Transformers, state-space models, encoders, symbolic engines, search, simulators, sensors, APIs and Manas are all organs.

- **ORG-1** Organs propose; transitions commit (Law 5).
- **ORG-2** Every committed object without `origin` provenance MUST name the organ and version that proposed it. Seed structure names the seed specification instead (PRV-7).
- **ORG-3** Content an organ supplies from its own pretraining, rather than from Entelechy's experience, MUST carry `testimony` provenance naming that organ. This keeps knowledge inherited from a pretrained model distinguishable from knowledge Entelechy learned.
- **ORG-4** Language is a codec. When someone says $X$, the fact that they said it MAY be committed as an `observation`, but $X$ itself MUST enter as `testimony` attributed to the speaker. It MUST NOT be committed as an observation of the world.
- **ORG-5** An organ's internal parameters, such as neural weights, are organ state, not Heart state, and MAY change during training. Putting a new organ version into service is a `CHANGE_ORGAN` transition. Its provenance MUST reference the experience the organ was trained on. Existing Models are not affected (MOD-12).
- **ORG-6** Authority-bearing identity comes from capability, not payload:

  $$
  \boxed{\text{Authority-bearing identity comes from capability, not payload.}}
  $$

  The identity an organ or Body channel acts under MUST be established by the interface it acts through, never by data it supplies. A Body channel delivers Observations only through a port bound to that channel, and a Mind organ proposes only through a port bound to that organ. A payload may say anything; what it says about its own origin carries no authority. This is what keeps observation distinct from testimony (ORG-4, PRV-6): an organ that is not a channel has no way to deliver an Observation.

---

## 7. Persistent Objects

Every persistent epistemic object shares one header:

```text
PersistentObject
    id            stable identifier
    type          Observation, Infon, Pattern, Form, Model, Prediction,
                  Skill, SkillExecution, SelfMapEntry, Goal or Preference
    version       increments with each transition that changes the object
    provenance    §5
    derived_from  the objects this one succeeds, if any
    created_seq   seq of the transition that created it
    retired_by    ∅, or the transition that retired it
```

An object's lineage is the ordered set of transitions that reference it. Implementations MAY store it on the object or derive it from $\Omega$'s lineage.

- **OBJ-1** Every persistent epistemic object MUST carry this header. This makes Laws 1 and 2 structural rather than textual.
- **OBJ-2** `id` MUST NOT change.
- **OBJ-3** A retired object MUST remain in lineage. Retirement sets `retired_by`; it never removes the object.
- **OBJ-4** Status changes preserve identity; content changes create successors.
  - A transition that changes only how far an object is trusted (an Infon's confidence or status, a Model's status, a Skill's depth) keeps its `id` and increments its `version`.
  - A transition that changes what an object asserts or does (an Infon's relation, participants, polarity or context; a Form's members; a Model's mechanism; a Skill's transformation) MUST create a new object whose `derived_from` names its predecessor.

---

## 8. Primitives

### 8.1 Referent

A **Referent** is anything an Infon can point at. It resolves to one of:

- a persistent object, by `id`,
- a region of a persisted Observation,
- an opaque identifier introduced by a persisted Observation.

Entelechy may later infer that two Referents are manifestations of one persistent thing. That inference is learned structure, not machinery.

$$
\boxed{\text{Referent is machinery; Entity is learned structure.}}
$$

- **REF-1** Every Infon participant MUST be a Referent that resolves to one of the three kinds above.
- **REF-2** A Referent carries no semantic type. That two Referents denote the same thing is itself a commitment, an Infon or Form, with provenance.
- **REF-3** Entity is not a primitive. Objecthood MAY emerge as a Form.

### 8.2 Observation

$$
O_t = Observe(X_t)
$$

An Observation contains the object header, `channel`, `received_seq`, `content` and `identifiers`. `identifiers` lists any opaque identifiers the channel supplies with the Observation. These are the identifiers REF-1 allows Referents to point at, and they carry no assumed meaning. It is transient on receipt and becomes persistent only through `CONSOLIDATE`. Most raw Observations are never consolidated; those used as evidence are (MEM-1).

- **OBS-1** An Observation records what was received, and MUST NOT be edited. Revising what it is taken to mean happens in Infons, not in the Observation.
- **OBS-2** An Infon MUST NOT be assigned certainty merely because its provenance is `observation`. The reliability of each channel is learned.
- **OBS-3** `received_seq` MUST be assigned at receipt, before consolidation (SEQ-1).

### 8.3 Difference

$\Delta(A,B)$ is the single comparison primitive. Every discrepancy is $\Delta$ applied within a domain:

| Discrepancy | Compares | Drives |
| --- | --- | --- |
| $\delta_W$ | expected world vs observed world | learning |
| $\delta_S$ | preferred self state vs perceived self state | salience and motivation |
| $\delta_M$ | expected cognition vs actual cognition | metacognition |

- **DIF-1** $\delta_W$, $\delta_S$ and $\delta_M$ MUST all be computed through $\Delta$. Each domain MAY use its own metric.
- **DIF-2** Discrepancies are transient. They become persistent only when recorded, for example as the outcome of a Prediction.

### 8.4 Infon

An Infon contains the object header and:

| Field | Meaning |
| --- | --- |
| `relation` | A relation from the relation vocabulary. |
| `participants` | Referents (§8.1). |
| `polarity` | Whether the relation is asserted to hold or not to hold. |
| `context` | The conditions under which it is asserted, such as a `seq` range, channel or Model. |
| `confidence` | The degree of commitment. Its representation MAY be a probability, an interval, evidence counts or another form. |
| `status` | `active`, `contradicted` or `retired`. |

ARCHITECTURE.md says an Infon can be observed, inferred, contradicted, uncertain, contextual or temporary. Each of those maps to a field:

| ARCHITECTURE.md | Field |
| --- | --- |
| observed, inferred | `provenance.kind` |
| uncertain | `confidence` |
| contradicted | `status` |
| contextual | `context` |
| temporary | not yet committed, so still transient |

- **INF-1** A persistent Infon MUST have every field.
- **INF-2** A relation between Infons is itself an Infon whose participants are Infons. There is no separate Relation type.
- **INF-3** Contradiction MUST NOT delete an Infon. It changes the Infon's status through `REVISE_INFON`, and both versions remain in lineage.
- **INF-4** `REVISE_INFON` changes only confidence and status. Changing relation, participants, polarity or context creates a successor Infon (OBJ-4).
- **INF-5** Polarity has exactly two values. "Unknown" is not a polarity. It is the absence of any active Infon for that relation in that context (Law 6).
- **INF-6** A negative-polarity Infon REQUIRES provenance that would have differed had the relation held, such as an observation, experiment or derivation. It MUST NOT be derived solely from the absence of a positive Infon.

### 8.5 Pattern

A Pattern is a recurrent arrangement of Infons. It contains the object header, `template` and `support` (references to the occurrences it summarizes).

- **PAT-1** `DISCOVER_PATTERN` REQUIRES $|support| \ge n_{pattern}$.
- **PAT-2** `support` MUST reference actual persistent occurrences.

### 8.6 Form

A Form is a class of histories or Patterns that imply the same relevant futures. It contains the object header, `members`, `predictive_signature`, `equivalence`, `support` and `status` (`active`, `merged`, `split` or `dissolved`).

- **FRM-1** `CRYSTALLIZE_FORM` REQUIRES

  $$
  PredictiveEquivalence(F) \ge \theta_{form}
  $$

  over at least $n_{form}$ independent supporting observations.
- **FRM-2** Merging, splitting or dissolving Forms creates successors. Successor Forms name their predecessors in `derived_from`, and predecessors are retired, not deleted.

### 8.7 Model

A Model is a mechanism for predicting or explaining transitions:

$$
M : (State_t, A_t) \rightarrow Prediction_{t+1}
$$

It contains the object header, `mechanism` (a reference to the structure or pinned organ version that computes it), `domain`, `status` and `predictions` (references to its Predictions).

Its `status` is one of `candidate`, `validated`, `knowledge`, `contested`, `refuted` or `retired`.

- **MOD-1** Knowledge is a status a Model earns, not a separate kind of object.
- **MOD-2** A status change MUST preserve the Model's identity.
- **MOD-3** Competing Models for the same domain MAY coexist. Entelechy is never required to collapse them into one.
- **MOD-4** A meta-model is a Model whose domain is Entelechy's own cognition. It obeys every MOD rule.
- **MOD-12** A `mechanism` that uses an organ MUST pin the organ's version. `CHANGE_ORGAN` MUST NOT change the predictions of an existing Model. Using a new organ version is a `REVISE_MODEL`.
- **MOD-13** `REVISE_MODEL` changes a Model's content, not its status. It creates a successor Model with status `candidate` and `derived_from` naming the predecessor. The predecessor's Predictions MUST NOT count toward the successor's validation. The predecessor keeps its status until it is retired under MOD-11.

Model status revision and Model content revision are therefore different operations:

$$
\underbrace{M_1: candidate \rightarrow validated}_{\text{status revision: same Model}}
\qquad
\underbrace{M_1 \rightarrow M_2}_{\text{content revision: successor}}
$$

### 8.8 Prediction

A Prediction is a Model's preregistered claim about an outcome. It contains the object header, `model` (the Model's `id` and `version`), `conditions` (Referents describing the situation and any action), `predicted`, `precision` and `outcome` (∅ until bound).

- **PRD-1** `RECORD_OUTCOME` REQUIRES that the Prediction's `created_seq` is lower than the `received_seq` of the Observation that supplies the outcome. A Prediction made after its outcome was received does not count.
- **PRD-2** A Prediction's `predicted`, `conditions` and `precision` MUST NOT change after it is recorded, and its `outcome` MUST NOT change once bound.

### 8.9 Skill

A Skill is a validated, reusable transformation that no longer requires full deliberation. It contains the object header, `domain`, `transformation`, `depth`, `executions` (references to its SkillExecutions), `cost_profile`, `compiled_from` and `explanation`.

Its `depth` is one of `temporary`, `stable`, `core` or `retired`.

A **SkillExecution** records one use of a Skill. It contains the object header, `skill` (the Skill's `id` and `version`), `input` (Referents), `expected`, `actual`, `cost` and `success`.

- **SKL-1** A depth change MUST preserve the Skill's identity.
- **SKL-2** `explanation` MUST be explicit. It either references the Model that explains why the Skill works, or it is marked `unexplained`. Ability is not understanding, and Entelechy tracks both.
- **SKL-3** A `core` Skill MUST NOT be revised. It must be demoted to `stable` first (§11.2).
- **SKL-10** `REVISE_SKILL` creates a successor Skill at depth `temporary`, with `derived_from` naming the predecessor. The predecessor's executions MUST NOT count toward the successor's promotion.
- **SKL-11** `compiled_from` MUST reference the consolidated episodes of the deliberations the Skill was compiled from.

### 8.10 Self Map

The Self Map holds entries $x \leftrightarrow \Omega$, each with a self-relevance $S(x)$. It is part of $\Omega_{state}$.

- **SLF-1** At origin, the Self Map MUST contain only the self-reference.
- **SLF-2** Every later entry and every change to $S(x)$ REQUIRES provenance and EMITS `SELF_MODEL_UPDATED`.

### 8.11 Goals and Preferences

Preferences $Q(x)$ are preferred states. Goals are states Entelechy acts to bring about.

- **GOL-1** Goals and preferences are persistent. Each REQUIRES provenance, and every change EMITS `GOAL_CHANGED`.

### 8.12 Resources

$R_t$ is a vector of finite budgets covering compute, memory, energy, time, bandwidth and attention. It is transient accounting state, and consumption changes it without transitions. Resource accounting has no write path to persistent state except `RECORD_RESOURCE_THRESHOLD`.

- **RES-1** Consumption MUST NOT exceed the available budget in $R_t$.
- **RES-2** When any component of $R_t$ crosses below $\theta_{critical}$, a `RECORD_RESOURCE_THRESHOLD` transition MUST be committed. It EMITS `RESOURCE_CRITICAL`.
- **RES-3** Resource exhaustion MUST NOT leave a transition partially applied (PER-5).
- **RES-4** A reserve sufficient to commit `RECORD_RESOURCE_THRESHOLD` and complete any in-flight transition MUST be excluded from the budget available to other operations.

### 8.13 Events

Events are the World Language of ARCHITECTURE.md. Each event contains `type`, `seq` and a reference to the transition that emitted it.

- **EVT-1** The event log MUST be append-only. It is part of lineage.
- **EVT-2** Subsystems MAY subscribe to events. A reaction that changes persistent state is itself a transition.
- **EVT-3** Every event MUST be emitted by exactly one transition. Nothing else emits events.

---

## 9. Seed

Entelechy begins with machinery, not knowledge. The seed contains:

- $\Omega_{identity}$,
- a Self Map holding only the self-reference,
- the $\Delta$ primitive,
- the `seq` counter,
- the transition machinery and the validator that enforces this document,
- resource accounting,
- the memory tiers, all empty,
- at least one Body channel and one Mind organ,
- a minimal relation vocabulary.

- **DEV-1** Everything in the seed MUST carry `origin` provenance, and the seed MUST be listed in `origin`. Seeded structure and learned structure are therefore always distinguishable (PRV-5).
- **DEV-2** `origin` MUST contain enough to reconstruct the seed Heart exactly (Law 7).

---

## 10. Legal Transformations

These are the only operations that change persistent state.

| Operation | REQUIRES | Effect | EMITS |
| --- | --- | --- | --- |
| `CONSOLIDATE` | MEM-1; PRV-4 | An Observation or episode becomes persistent at episodic level or deeper. | `MEMORY_CONSOLIDATED` |
| `FORM_INFON` | INF-1; REF-1; INF-6 if negative | A new Infon. | `INFON_FORMED` |
| `REVISE_INFON` | The new evidence or derivation is referenced in the justification. | Confidence or status changes (INF-4). | `INFON_REVISED` † |
| `DISCOVER_PATTERN` | PAT-1 | A new Pattern. | `PATTERN_DISCOVERED` |
| `CRYSTALLIZE_FORM` | FRM-1 | A new Form. | `FORM_CRYSTALLIZED` |
| `REVISE_FORM` | Predictive evidence is referenced in the justification. | Successor Forms are created; predecessors are retired (FRM-2). | `FORM_REVISED` † |
| `PROPOSE_MODEL` | Provenance | A new Model with status `candidate`. | `MODEL_PROPOSED` † |
| `REVISE_MODEL` | MOD-12 or failure evidence is referenced in the justification. | A successor Model with status `candidate` (MOD-13). | `MODEL_REVISED` † |
| `CHANGE_MODEL_STATUS` | §11.1 | The Model's status changes. | `MODEL_STATUS_CHANGED` † |
| `RECORD_PREDICTION` | The Model is not `retired` or `refuted`. | A new Prediction. | `PREDICTION_RECORDED` † |
| `RECORD_OUTCOME` | PRD-1; the outcome Observation is persistent. | The outcome is bound to the Prediction. | `OUTCOME_RECORDED` †, and also `MODEL_CONTRADICTED` when the outcome falls outside the Prediction's precision |
| `COMPILE_SKILL` | SKL-5; SKL-11 | A new Skill at depth `temporary`. | `SKILL_COMPILED` |
| `RECORD_SKILL_OUTCOME` | The Skill is not `retired`; its input and result are persistent. | A new SkillExecution. | `SKILL_EXECUTED` † |
| `CHANGE_SKILL_DEPTH` | §11.2 | The Skill's depth changes by one step. | `SKILL_DEPTH_CHANGED` † |
| `REVISE_SKILL` | Depth is not `core`; failure evidence is referenced in the justification. | A successor Skill at depth `temporary` (SKL-10). | `SKILL_REVISED` † |
| `UPDATE_SELF_MAP` | SLF-2 | A Self Map entry or $S(x)$ changes. | `SELF_MODEL_UPDATED` |
| `CHANGE_GOAL` | GOL-1 | A goal or preference changes. | `GOAL_CHANGED` |
| `FORGET` | MEM-2; MEM-4 | Content is retired, and a lineage stub remains. | `MEMORY_FORGOTTEN` † |
| `CHANGE_ORGAN` | ORG-5 | A Mind organ, Body component or storage backend is attached, replaced or removed. | `ORGAN_CHANGED` † |
| `RECORD_RESOURCE_THRESHOLD` | RES-2 | The crossing is recorded. | `RESOURCE_CRITICAL` |

† Added to the event list in ARCHITECTURE.md.

- **TRN-1** An operation not listed here MUST NOT change persistent state. Adding an operation means amending this document.

---

## 11. Promotion and Demotion

Promotion and demotion are status changes, so they preserve identity (OBJ-4). Nothing is copied into a new object.

- **EVD-1** Every aggregate used in this section MUST be computed over all resolved Predictions or SkillExecutions within its scope, never a selected subset.

### 11.1 Models

```text
candidate → validated → knowledge
               ⇅            │
           contested ←──────┘
               │
               ↓
            refuted

any status → retired  (superseded by a successor)
```

- **MOD-5** Evidence used to construct a Model MUST NOT count toward its validation.
- **MOD-6** Status MUST NOT skip steps. A `candidate` cannot become `knowledge` directly.
- **MOD-7** `candidate → validated` REQUIRES at least $n_{validate}$ held-out Predictions whose aggregate discrepancy is at most $\theta_{validate}$.
- **MOD-8** `validated → knowledge` REQUIRES that the Model has survived:
  - **prediction:** at least $n_{knowledge}$ held-out Predictions with aggregate discrepancy at most $\theta_{validate}$,
  - **intervention:** at least $n_{intervention}$ experiments (§13) in which it made a discriminating Prediction that held,
  - **contradiction:** at least one challenge, from a rival Model or contradicting evidence, that was resolved in its favour.

  A Model that needed revision to survive a challenge is a successor (MOD-13) and earns its own status.
- **MOD-9** Knowledge MUST remain revisable. `knowledge` or `validated` → `contested` REQUIRES sustained discrepancy: a precision-weighted aggregate $\delta_W$ of at least $\theta_{contest}$ over a window of $w_{contest}$ outcomes. A single discrepancy MUST NOT demote a `validated` or `knowledge` Model.
- **MOD-10** A `contested` Model returns to `validated` if MOD-7 holds over the outcomes recorded since it was contested. It becomes `refuted` only if its aggregate discrepancy reaches $\theta_{refute}$ over at least $n_{refute}$ outcomes recorded since it was contested. Otherwise it remains `contested`. Lack of vindication is not refutation.
- **MOD-11** `retired` REQUIRES a reference to a successor Model whose status is at least the retiring Model's status.

### 11.2 Skills

```text
temporary ⇄ stable ⇄ core
any depth → retired
```

- **SKL-4** Depth MUST change one step at a time.
- **SKL-5** `COMPILE_SKILL` REQUIRES at least $n_{compile}$ successful deliberative solutions of the same transformation, with a success rate of at least $\theta_{compile}$.
- **SKL-6** `temporary → stable` REQUIRES at least $n_{stable}$ recorded executions with a failure rate at most $\theta_{stable}$.
- **SKL-7** `stable → core` REQUIRES at least $n_{core}$ recorded executions with a failure rate at most $\theta_{core}$, and verification by a check independent of the Skill itself: deliberation, a Model or an experiment.
- **SKL-8** `stable → temporary` REQUIRES a failure rate above $\theta_{stable}$ over the last $w_{skill}$ recorded executions.
- **SKL-9** `core → stable` REQUIRES a failure rate above $\theta_{core\_failure}$ over the last $w_{skill}$ recorded executions. Core Skills are deliberately hard to rewrite: demotion is required first (SKL-3).

---

## 12. Memory, Consolidation and Forgetting

$$
Retention(x) = f(novelty,\ predictionError,\ repetition,\ semanticValue,\ selfRelevance)
$$

Different information earns different persistence. Forgetting is compression, not failure. Sensing is cheap: most raw Observations vanish, and those used as evidence are kept.

- **MEM-1** `CONSOLIDATE` REQUIRES either $Retention(x) \ge \theta_{retain}$, or that $x$ is cited as a provenance input by a commit in the same transition. Evidence earns persistence.
- **MEM-2** `FORGET` REQUIRES either $Retention(x) \le \theta_{forget}$, or that the content has been compressed into a named successor structure, such as a Pattern or Form, referenced in the justification.
- **MEM-3** `FORGET` retires content and MUST leave a lineage stub: the object header, the retiring transition, the reason and the successor if there is one.
- **MEM-4** `FORGET` MUST NOT apply to:
  - $\Omega_{identity}$,
  - seed structure carrying `origin` provenance, including the Self Map's self-reference,
  - transition records, provenance records, events or lineage stubs,
  - the Predictions of a Model that is not `retired`,
  - the SkillExecutions of a Skill that is not `retired`.

  Content can be retired; the record of it cannot, and neither can the evidence a live status depends on.
- **MEM-5** `FORGET` MAY retire the content of an object that active commitments cite as provenance. The lineage stub satisfies PRV-4.
- **MEM-6** `FORGET` removes body content from Entelechy's managed content store and from its active epistemic state. It does not guarantee cryptographic or information-theoretic erasure: digests and other retained metadata may permit confirmation or reconstruction of sufficiently low-entropy content.

---

## 13. Discrepancy, Salience, Will and Experiment

### Salience

$$
Salience(x) = f(S(x),\ \Delta,\ precision,\ novelty,\ risk,\ controllability)
$$

- **SAL-1** Salience is transient. It MAY direct resources and consolidation priority, but MUST NOT itself change persistent state.

### Will and curiosity

$$
Value(a) = GoalValue(a) + \lambda\, IG(a) - Cost(a)
$$

- **WIL-1** Action selection is transient. An action becomes persistent only when its episode is consolidated.

### Experiment

- **EXP-1** An action counts as an experiment, and its outcome may carry `experiment` provenance, only if, before the action is executed, at least two Models have Predictions recorded through `RECORD_PREDICTION` whose predicted outcomes differ by $D \ge \theta_{experiment}$.
- **EXP-2** An experiment's outcome MUST be recorded against the Predictions of every Model it tested, not only the one it favoured.

---

## 14. Metacognition (Manas)

- **MET-1** Manas is an organ. Its operations (ANALYZE, COMPARE, SIMULATE, VERIFY, COMBINE, REFACTOR, COMPILE) propose; transitions commit. Manas has no privileged write access.
- **MET-2** An expected cognitive performance $\hat C$ counts toward $\delta_M$ only if a meta-model recorded it through `RECORD_PREDICTION` before the actual performance $C$ was observed (PRD-1).
- **MET-3** No internal operation MAY modify this document's rules or the validator that enforces them. Self-modification of the Heart is ordinary modification and obeys every rule here.

---

## 15. Parameters

Every parameter is **unbound**. None has a value until experiment determines one, and no value belongs in this document.

| Parameter | Used in | Meaning |
| --- | --- | --- |
| $n_{pattern}$ | PAT-1 | Minimum occurrences to discover a Pattern |
| $\theta_{form}$ | FRM-1 | Minimum predictive equivalence to crystallize a Form |
| $n_{form}$ | FRM-1 | Minimum independent observations supporting a Form |
| $n_{validate}$ | MOD-7 | Minimum held-out Predictions to validate a Model |
| $\theta_{validate}$ | MOD-7, MOD-8 | Maximum aggregate discrepancy for validation |
| $n_{knowledge}$ | MOD-8 | Minimum held-out Predictions for knowledge status |
| $n_{intervention}$ | MOD-8 | Minimum confirming experiments for knowledge status |
| $\theta_{contest}$ | MOD-9 | Sustained discrepancy that contests a Model |
| $w_{contest}$ | MOD-9 | Window over which contesting discrepancy is measured |
| $\theta_{refute}$ | MOD-10 | Aggregate discrepancy that refutes a contested Model |
| $n_{refute}$ | MOD-10 | Minimum outcomes since contest before refutation |
| $n_{compile}$ | SKL-5 | Minimum deliberative successes to compile a Skill |
| $\theta_{compile}$ | SKL-5 | Minimum success rate to compile a Skill |
| $n_{stable}$ | SKL-6 | Minimum executions for `stable` |
| $\theta_{stable}$ | SKL-6, SKL-8 | Failure rate bound for `stable` |
| $n_{core}$ | SKL-7 | Minimum executions for `core` |
| $\theta_{core}$ | SKL-7 | Maximum failure rate for promotion to `core` |
| $\theta_{core\_failure}$ | SKL-9 | Failure rate that demotes a `core` Skill |
| $w_{skill}$ | SKL-8, SKL-9 | Window over which Skill failure is measured |
| $\theta_{retain}$ | MEM-1 | Minimum retention score to consolidate |
| $\theta_{forget}$ | MEM-2 | Maximum retention score to forget |
| $\theta_{critical}$ | RES-2 | Resource level that triggers `RESOURCE_CRITICAL` |
| $\theta_{experiment}$ | EXP-1 | Minimum predictive divergence for an experiment |
| $\lambda$ | WIL | Weight of information gain in action selection |

---

## 16. Open Questions

- **OPEN-1** What is the exact representation of an Infon?
- **OPEN-2** What is the minimal seed relation vocabulary? How few relations are enough to learn from?
- **OPEN-3** May the seed contain any Forms, Models or Skills, or only machinery and vocabulary? ARCHITECTURE.md says human concepts should be learned "where possible".
- **OPEN-4** Which metric defines $PredictiveEquivalence$, and what makes two observations "independent"?
- **OPEN-5** What are the functions $f$ for Retention and Salience?
- **OPEN-6** How is the viability measure behind semantic value $V(I)$ computed?
- **OPEN-7** Is self-relevance $S(x)$ learned causally, assigned, or both? If assigned, PRV-5 requires `origin` provenance.
- **OPEN-8** Where do goals and preferences originate, and what may change them?
- **OPEN-9** When two instances share lineage up to a fork point and then diverge, which of them, if either, continues Ω? Is there a legal `FORK` operation?
- **OPEN-10** Must the content of Observations that ground `knowledge` be kept for audit, or is a lineage stub always enough?
- **OPEN-11** Full prior-state retention (PER-8), Predictions and SkillExecutions (MEM-4) grow without bound until `FORGET` compresses what it may. What retention policy keeps this tractable?
- **OPEN-12** For an organ that learns online, at what granularity does training become a `CHANGE_ORGAN` transition (ORG-5)?
- **OPEN-13** May a mature Manas propose amendments to this document, and through what process?
- **OPEN-14** How should explicit ignorance be represented? The current direction is that it should be representable, but not as an Infon polarity. "I don't know whether $R$" and "I have investigated $R$ and lack sufficient evidence" are positive facts about Entelechy's own epistemic state, as distinct from the bare absence of an Infon (INF-5). A candidate is an `EpistemicGap` or `Question` object, $G = \langle query,\ context,\ attemptedEvidence,\ status \rangle$, with statuses such as `open`, `investigating`, `resolved` and `unresolvable`.
- **OPEN-15** How is the implementation of an executable component, such as an organ or a retention policy, identified immutably? A name and version label do not prove that tomorrow's code called version 1 is the same code. A candidate is $implementation = \langle name,\ version,\ digest \rangle$, where `digest` identifies the artifact itself.
- **OPEN-16** Should Entelechy be able to forget securely, so that no surviving artifact permits recovery or confirmation of the forgotten content? MEM-6 guarantees only logical forgetting. Secure forgetting would need something like a per-body random nonce destroyed with the body, which costs deduplication and must be reconciled with RPL-3's auditable digests.

---

## 17. Conformance

An implementation conforms to this document if and only if every reachable persistent state satisfies every MUST and MUST NOT, and every transition satisfies its REQUIRES and EMITS.

This translates directly into code:

- each **MUST** and **MUST NOT** becomes an invariant check over persistent state,
- each **REQUIRES** becomes a precondition in the transition validator,
- each **EMITS** becomes an assertion over the event log,
- each **PARAMETER** becomes named configuration with no default,
- each **OPEN** becomes a documented extension point,
- Law 7 becomes a replay test: $Replay(origin, lineage)$ must equal the live Heart.

---

## 18. Change Log

### 0.5

- **Capability law.** New ORG-6: authority-bearing identity comes from capability, not payload. Body channels and Mind organs act only through ports bound to their identity.
- **Logical forgetting.** New MEM-6, with a matching note under Law 7: `FORGET` is logical forgetting, not secure erasure.
- **Secure forgetting.** New OPEN-16.

### 0.4

- **Replay and forgetting.** Law 7 now includes the live content store: $ReplayCurrent(Origin, Lineage, ContentStore_{live}) = Heart_{current}$. Origin and lineage stay authoritative for structure, identity, transitions, digests, provenance and history. Transition records must not contain content bytes, since forgotten bytes must not survive in lineage (RPL-2, RPL-3).
- **Seed structure.** `FORGET` cannot apply to seed structure with `origin` provenance (MEM-4).
- **Observation identifiers.** Observations list the opaque identifiers that Referents may point at (§8.2).
- **Implementation identity.** New OPEN-15 on identifying executable components by artifact digest.

### 0.3

- **Origin provenance.** Seed structure names the seed specification instead of an organ. There is no seed organ (ORG-2, PRV-7).
- **Replay.** Law 7 now distinguishes $ReplayCurrent$, which must be exact, from $ReplayHistorical(n)$, which may show `CONTENT_FORGOTTEN` stubs for content forgotten after $n$ (RPL-2, RPL-4).
- **Explicit ignorance.** OPEN-14 records the current direction, an `EpistemicGap` or `Question` object rather than an Infon polarity. It remains open.

### 0.2

- **Commit boundaries.** `CONSOLIDATE` now means memory consolidation only. Other objects cross into the Heart through their typed commit operation (PER-3).
- **Observations.** Observations are transient on receipt and persist through `CONSOLIDATE`. Content cited as evidence may be consolidated regardless of retention score (MEM-1).
- **Referents.** Infon participants are Referents, not entities. Entity is left to emerge as a Form (§8.1).
- **Resources.** `RESOURCE_CRITICAL` is now emitted by the `RECORD_RESOURCE_THRESHOLD` transition, so every event has a transition (EVT-3, RES-2, RES-4).
- **Predictions.** New `RECORD_PREDICTION` operation and Prediction object. `RECORD_OUTCOME` binds outcomes to them (§8.8).
- **Skill executions.** New `RECORD_SKILL_OUTCOME` operation and SkillExecution object (§8.9).
- **Object header.** A shared PersistentObject header (§7) and the rule that status changes preserve identity while content changes create successors (OBJ-4).
- **Law 6.** Absence of evidence is not negative evidence (INF-5, INF-6).
- **Ordering.** `time` is replaced by the `seq` counter. Ordering machinery is not a concept of time (§3).
- **Model revision.** New `REVISE_MODEL` operation, which creates a successor Model. Existing Models pin their organ version (MOD-12, MOD-13). `REVISE_SKILL` also creates a successor now (SKL-10).
- **Contested Models.** A contested Model stays contested until it is revalidated or meets the explicit refutation threshold $\theta_{refute}$ over $n_{refute}$ outcomes (MOD-10).
- **Law 7.** The Heart is reconstructible from origin and lineage. Content is identified by digest so that `FORGET` does not break replay (RPL-1 to RPL-3).
- **Events.** A transition may emit more than one event (PER-6), and `RECORD_OUTCOME` always emits `OUTCOME_RECORDED`.
- **No cherry-picking.** Promotion aggregates use every resolved outcome in scope (EVD-1). Evidence behind a live status cannot be forgotten (MEM-4).
