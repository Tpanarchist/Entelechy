# E001: Evidence Integrity — Normative Spec

> **Status:** Approved 2026-09-26, after review against the conformance cases in §7.
> **Implements:** [the agreed E001 brief](../../experiments/e001-evidence-integrity-brief.md).
> **Amends:** [FOUNDATIONS.md](../../../FOUNDATIONS.md) draft 0.5 → 0.6 (§1). **Builds on:** E000, tagged `e000`.

This spec translates the agreed brief into enforceable rules. It does not reopen the brief. Where writing the rules exposed something the brief did not settle, the decision is listed in §9 so it can be reviewed on its own.

---

## 1. FOUNDATIONS Amendments

These are exact texts to apply to FOUNDATIONS.md as draft 0.6 once this spec is approved. Rule IDs are final.

### 1.1 New laws

- **Law 8: A Mind cannot choose or fabricate the identity of a grounding root.** Grounding-root identity MUST be established by an authority-bearing capability or by immutable persisted evidence, never by payload supplied by a Mind. A Mind may cause its own capability-bound testimony source to be admitted; it can never claim to be another source, and it can never invent an ObservationRoot.
- **Law 9: Support is inherited; independence is not.** A derived commitment inherits the grounding roots of its inputs. A new derivation node never creates a new independent source.

### 1.2 New rule families

| Prefix | Covers | Note |
| --- | --- | --- |
| `ROT` | grounding roots | new |
| `ROL` | provenance input roles | new |
| `ISS` | ClaimKey, issues, current heads, ledgers | new |
| `EVD` | novel roots, new evidence, weighing | continues from the existing EVD-1 in §11 |
| `INT` | interoceptive channels | new |

### 1.3 Grounding roots (ROT)

- **ROT-1** There are exactly three kinds of grounding root:
  - $ObservationRoot(o)$ for a persisted Observation $o$;
  - $TestimonyRoot(s)$ for an authority-bound testimony source $s$;
  - $ExperimentRoot(x)$, reserved, which nothing produces yet.
- **ROT-2** A Mind cannot manufacture a new root identity (Law 8):
  - an ObservationRoot's identity is a persisted Observation, which only a Body channel's port can deliver (ORG-6);
  - an OrganPort may contribute only the one TestimonyRoot already bound to its own organ, $TestimonyRoot(organ\_id)$. No proposal field can name any other source.
- **ROT-3** An authority-bound testimony source's identity MUST come from a capability, never from payload. The only authority-bound testimony sources are Mind organs testifying through their own OrganPort. $TestimonyRoot(s)$ is keyed by the organ's stable id, not its version. Other authority-bound sources MAY be defined later; E001 builds none.
- **ROT-4** Attributed testimony, meaning a speaker named in a payload, MUST NOT create a TestimonyRoot.
- **ROT-5** Roots are version-relative: $Roots$ is defined on $ObjectRef(id, version)$, never on an object id alone.
- **ROT-6** For a version $x@v$ whose provenance is $p$:
  - if $x$ is an Observation: $Roots(x@v) = \{ObservationRoot(x)\}$;
  - if $p.mode = testimony$: $Roots(x@v) = \{TestimonyRoot(p.organ.id)\}$;
  - if $x$ is seed structure: $Roots(x@v) = \varnothing$;
  - otherwise: $Roots(x@v) = \bigcup \{\, Roots(i.ref) : i \in p.inputs,\ i.role \neq attribution \,\}$.
- **ROT-7** Roots are derived from provenance and lineage. They MUST NOT be stored as authoritative state. A root's identity survives `FORGET`, because it is an object id or a source id, and both are kept in headers and provenance.
- **ROT-8** $grounded(x@v) := Roots(x@v) \neq \varnothing$. A commitment with no roots is **ungrounded**, not invalid.

### 1.4 Production mode (PRV amendments)

Provenance `kind` is replaced by `mode`, which describes how a commitment was produced, never what grounds it.

- **PRV-8** Every provenance record carries a production mode, assigned by the kernel or the validator from the operation, the port that delivered or proposed it, and the roles of its inputs. No organ supplies a mode. The modes are:

  | Mode | Assigned when |
  | --- | --- |
  | `origin` | the seed is created |
  | `observation` | an Observation from an exteroceptive channel is consolidated |
  | `self-observation` | an Observation from an interoceptive channel is consolidated |
  | `testimony` | an organ forms an Infon from its own knowledge, with no inputs |
  | `attributed` | an organ forms an Infon whose only inputs are `attribution` inputs |
  | `derivation` | an organ forms an Infon with at least one `derivation_input` |
  | `revision` | `REVISE_INFON` changes an Infon |
  | `simulation`, `experiment` | reserved; `V1-UNIMPLEMENTED` |

- **PRV-9** A mode MUST NOT be read as evidence composition. What grounds a commitment is given by $Roots$ alone.
- **PRV-1 to PRV-7, amended.** Read "kind" as "mode". PRV-5 becomes: `origin` mode is only assigned at creation. PRV-6 becomes: a mode MUST NOT be upgraded. PRV-7 and ORG-2 become: for the modes `observation` and `self-observation`, `organ` names the **delivering channel**; for every other non-origin mode, it names the **proposing organ**.
- **ORG-3, amended.** Content an organ supplies from its own knowledge is formed with mode `testimony`. Its root is $TestimonyRoot(organ\_id)$.
- **ORG-4, amended.** When someone says $X$, $X$ is formed with mode `attributed`, and the utterance's Observation is an `attribution` input. It creates no root (ROT-4).

### 1.5 Roles (ROL)

- **ROL-1** Every provenance input carries exactly one role: `support`, `counterevidence`, `derivation_input`, `revision_target` or `attribution`.
- **ROL-2** Role semantics:

  | Role | Passes roots | Eligible for novelty | Direction | Allowed in |
  | --- | --- | --- | --- | --- |
  | `support` | yes | yes | for | trust-change revision |
  | `counterevidence` | yes | yes | against | trust-change revision |
  | `derivation_input` | yes | yes, at formation (ISS-4) | none | formation |
  | `revision_target` | yes | **never** | none | revision, added by the validator |
  | `attribution` | **no** | never | none | formation and revision |

- **ROL-3** An organ MAY use only the roles allowed for its operation. `revision_target` is added by the validator, never by an organ. An `attribution` input MUST be a persisted Observation.
- **ROL-4** A trust change's evidence MUST agree with its direction. A change is **upward** if it raises confidence or moves `contradicted` → `active`. It is **downward** if it lowers confidence or moves `active` → `contradicted`. Then:
  - an upward change REQUIRES at least one novel root from a `support` input;
  - a downward change REQUIRES at least one novel root from a `counterevidence` input;
  - a revision that moves both ways at once is refused.

  This checks that the accounting is consistent with itself. It does not check how much the evidence should move confidence.
- **ROL-5** A role records the proposing organ's claim about how its evidence bears on the commitment. The validator enforces what each role does to roots. It does not verify that the organ's claim is true (§8).

### 1.6 Issues (ISS)

$$
\boxed{\text{Object identity is not epistemic issue identity.}}
$$

- **ISS-1** $ClaimKey(I) = \langle relation,\ participants,\ context \rangle$ in canonical form. Polarity is excluded, so $ClaimKey(I^{+}) = ClaimKey(I^{-})$ whenever the three fields match. $IssueDigest(I) = Digest(Canonical(ClaimKey(I)))$.
- **ISS-2** $IssueDigest$ is an immutable Infon identity field. It is computed by the validator at formation, never supplied by an organ, and never changes. It is kept when the Infon's content is forgotten.
- **ISS-3** The **current head** of issue $K$ is the Infon whose $IssueDigest$ is $K$ and whose latest version is neither retired nor forgotten. Every issue MUST have at most one current head, at every point in lineage.
- **ISS-4** `FORM_INFON` is classified by the issue's history, not by its verb:

  | History of $K$ | Classification | Verdict |
  | --- | --- | --- |
  | no Infon has ever had issue $K$ | **first formation** | allowed, including when rootless |
  | $K$ has a current head | **clone** | refused: revise the head instead |
  | $K$ has history but no current head | **re-formation** | REQUIRES $NewEvidence(E, K)$, where $E$ is the formation's inputs |

  For an organ's own testimony, the formation's candidate roots are $\{TestimonyRoot(organ\_id)\}$.
- **ISS-5** A change of polarity is the only content change that stays on the same issue. It is a successor (OBJ-4) that replaces the current head in the same transition, and, being a trust change, it REQUIRES new evidence. Negative Infons remain `V1-UNIMPLEMENTED`, so this rule is defined but not exercised.
- **ISS-6** `derived_from` records lineage only. It transfers no roots between issues. If support should transfer, it must appear as a support-bearing input.
- **ISS-7** $Ledger(K)@seq$ is the set of grounding roots admitted into issue $K$'s history by transitions committed at or before $seq$:

  $$
  Ledger(K)@seq = \bigcup \{\, Roots(I@v) : IssueDigest(I) = K,\ I@v \text{ committed at or before } seq \,\}
  $$

  It includes every Infon that has ever had issue $K$: current, retired and forgotten.

### 1.7 New evidence (EVD)

- **EVD-2** $NovelRoots(E, K) = Roots(E) \setminus Ledger(K)$, where $Roots(E)$ is the union of the roots of every root-passing input in $E$. $NewEvidence(E, K) \iff NovelRoots(E, K) \neq \varnothing$.
- **EVD-3** Only a committed transition changes $Ledger(K)$. Proposals, validation, rejection, simulation and transient reasoning consume nothing. Operations within one proposal are validated in order against the staged state, including the staged ledger. A rejection discards the staged ledger.
- **EVD-4** A trust change REQUIRES $NewEvidence(E, K)$, where $E$ is the revision's `support` and `counterevidence` inputs. Trust changes are any change of confidence, and `active` ↔ `contradicted`.
- **EVD-5** An administrative change needs no evidence, and it MUST NOT admit any. That is a move to `retired` with confidence unchanged. It MAY carry `attribution` inputs, which pass no roots, but MUST NOT carry `support` or `counterevidence`. Otherwise an organ could retire an Infon while citing an unused $O_7$ and consume $O_7$ without weighing it, so that it could never support a later re-formation.

  Only formation, re-formation and trust changes can add roots to an issue's ledger.
- **EVD-6** Evidence is weighed once. A root in $Ledger(K)$ never again contributes to $NovelRoots(\cdot, K)$, in either direction. It MAY still be referenced any number of times.
- **EVD-7** For every `FORM_INFON` and `REVISE_INFON`, the validator's justification MUST record the issue $K$, the formation's classification (ISS-4) where there is one, and three root sets:
  - `inherited`: $Ledger(K)$ before the operation;
  - `candidate`: the roots its evidence carries;
  - `novel`: $candidate \setminus inherited$.

  Every E001 evidence-accounting fact MUST be independently recomputable at replay from origin and lineage alone: roots, ledger membership, novelty, issue classification and head uniqueness. Waking up MUST refuse a Heart where any recorded accounting fact differs from its recomputation (Law 7).

  Other historical validator decisions, such as a revision's direction (ROL-4) or V1-CERTAINTY, depend on Infon bodies. They are auditable only as far as that content survives logical forgetting (MEM-6).

### 1.8 Interoceptive channels (INT)

- **INT-1** The seed MAY declare interoceptive channels: Body channels that observe Entelechy itself. Their ids are unique across all channels and organs.
- **INT-2** An Observation's mode is assigned at `CONSOLIDATE` from its channel's classification in the manifest: `self-observation` for an interoceptive channel, `observation` otherwise.
- **INT-3** Nothing else produces `self-observation`. No proposal field can set a mode (PRV-8). This extends ORG-6 from *who* delivered an Observation to *what kind* it is. The port establishes the delivery, not the truth of the payload.

### 1.9 Citation clean-up (from the E000 backlog)

- **TRN-2** An operation that has a typed form MUST be proposed in it. `OtherOperation("CONSOLIDATE")` is refused under TRN-2, not TRN-1.
- **TRN-3** An operation that changes an existing object REQUIRES that object to exist in persistent or staged state. A revision or `FORGET` of an unknown id is refused under TRN-3, not PER-6 or MEM-3.

---

## 2. Data Model

### 2.1 Stored versus derived

| Item | Stored or derived | Where |
| --- | --- | --- |
| Provenance `mode` | stored | provenance record and row |
| Input `role` | stored | each provenance input |
| `IssueDigest` | stored, once per Infon | a new append-only `infon_issues` table, and the transition record |
| $Roots(x@v)$ | derived | computed from provenance on demand (ROT-7) |
| $Ledger(K)$ | derived | computed from `infon_issues` and roots |
| Current head of $K$ | derived | latest versions of the Infons with issue $K$ |
| `grounded` | derived | ROT-8 |
| `inherited`, `candidate`, `novel` | recorded as justification | the transition record, checked at replay (EVD-7) |

An implementation MAY memoize roots of committed versions in memory, because committed versions are immutable. Nothing derived is written as authoritative state.

### 2.2 Shapes

```text
Mode   = origin | observation | self-observation | testimony | attributed
       | derivation | revision | simulation* | experiment*        (* reserved)
Role   = support | counterevidence | derivation_input | revision_target | attribution

ProvenanceInput = ⟨ref: ObjectRef, role: Role⟩
Provenance      = ⟨id, mode, inputs: ProvenanceInput*, operation, organ | seed_spec, seq⟩

Root     = ⟨kind: observation | testimony | experiment, key: str⟩
           canonical: {"kind": "observation", "key": "<observation id>"}
                      {"kind": "testimony",   "key": "<organ id>"}

ClaimKey = {"relation": ..., "participants": [<referent>...], "context": {...}}
IssueDigest = digest(canonical(ClaimKey))           e.g. "sha256:…"
```

Participants keep the order the organ gave them. Two claims with the same participants in a different order are different issues, as with any other syntactic difference (§8).

### 2.3 Proposals

Organs cite inputs with a role and never supply a mode:

```text
Cite        = ⟨object_id, role⟩
FormInfon   = ⟨relation, participants, confidence, inputs: Cite*, context, polarity, derived_from⟩
ReviseInfon = ⟨infon_id, expected_version, body, evidence: Cite*⟩
```

E000's `FormInfon.provenance_kind` is removed. The formation's mode follows from its inputs (PRV-8): no inputs means `testimony`, only `attribution` inputs means `attributed`, and any `derivation_input` means `derivation`.

### 2.4 Seed

`SeedSpec` gains `interoceptive: tuple[OrganRef, ...]`. `check_seed` requires ids to be unique across channels, interoceptive channels and organs. `kernel.body_channel(ref)` returns a port for either kind of channel; the manifest's classification decides the mode (INT-2).

### 2.5 Storage

- **Schema version 2.** E000 Hearts are refused by the version check. They exist only in tests, and none are migrated.
- **`provenance`:** the `kind` column becomes `mode`.
- **`provenance_inputs`:** gains a `role` column.
- **New table `infon_issues(object_id PRIMARY KEY, issue_digest NOT NULL)`:** append-only under the same trigger guards as the other append-only tables. It is written once, when an Infon is formed.
- **Transition record, schema 2:** provenance entries carry `mode`, and inputs carry `role`. A new `issues` list pairs each Infon formed in the transition with its digest.

### 2.6 Read API

`HeartView` gains read-only queries. None of them can change state.

```text
roots(object_id, version=None)  -> frozenset[Root]
grounded(object_id, version=None) -> bool
issue(object_id)                -> IssueDigest | None
head(issue)                     -> object_id | None
ledger(issue)                   -> frozenset[Root]
body(object_id, version=None)   -> Json | Stub | None      (the PER-8 read path)
```

---

## 3. Root Propagation

$Roots$ is computed by one recursive function over $ObjectRef$, following ROT-6.

- **It terminates.** The provenance graph is acyclic (PRV-3), because an input must exist before the object citing it.
- **It is memoized per $ObjectRef$.** Committed versions never change, so their roots never change.
- **It sees staged state.** During validation, the function also covers versions staged earlier in the same proposal.

Worked example:

```text
O1, O2          Observations                       Roots = {O1}, {O2}
T               testimony by organ M                Roots = {T(M)}
I@1             derivation from O1                 Roots = {O1}
I@2             revision: target I@1, support O2    Roots = {O1, O2}
J@1             derivation from I@2 and T           Roots = {O1, O2, T(M)}
X@1             attributed; attribution = U1        Roots = ∅          grounded = false
```

`revision_target` passes roots but never contributes novelty (ROL-2). So $Roots(I@2)$ keeps $O_1$, and $O_1$ can never be "new" for $I$'s issue again.

---

## 4. Validation

Operations are validated in order against the staged state (EVD-3). The E000 checks all still apply, and the steps below are added.

### 4.1 CONSOLIDATE

The mode is `self-observation` if the Observation's channel is interoceptive, and `observation` otherwise (INT-2). `organ` names the channel.

### 4.2 FORM_INFON

1. Check the roles: only `derivation_input` and `attribution` are allowed (ROL-3), and every `attribution` input is a persisted Observation.
2. Assign the mode from the inputs (PRV-8).
3. Compute $K = IssueDigest(ClaimKey(body))$ (ISS-1, ISS-2).
4. Compute `candidate`: $\{TestimonyRoot(organ\_id)\}$ for testimony; otherwise the roots of every non-attribution input.
5. Classify by $K$'s history (ISS-4), using persistent and staged state:
   - first formation: allowed; `novel` = `candidate`, and nothing is required;
   - clone: refused under ISS-4;
   - re-formation: `inherited` = $Ledger(K)$ and `novel` = `candidate` \ `inherited`; refused under ISS-4 if `novel` is empty.
6. Stage the Infon with its $IssueDigest$. Record `classification`, `inherited`, `candidate` and `novel` in the justification (EVD-7).

### 4.3 REVISE_INFON

1. Apply the E000 checks: the target exists (TRN-3), is an Infon, is not forgotten or retired, is at the expected version, and has no content change (INF-4); plus V1-CERTAINTY.
2. Check the roles: only `support`, `counterevidence` and `attribution` are allowed (ROL-3).
3. Classify the change. It is **administrative** if it only moves to `retired` with confidence unchanged; an administrative change carrying `support` or `counterevidence` is refused under EVD-5. It is a **trust change** otherwise, with a direction (ROL-4). A change that changes nothing is refused under INF-4, as in E000.
4. Set $K = IssueDigest(target)$, `inherited` = $Ledger(K)$, `candidate` = the roots of the `support` and `counterevidence` inputs, and `novel` = `candidate` \ `inherited`.
5. For a trust change: refuse under EVD-4 if `novel` is empty; refuse under ROL-4 if the novel roots do not come from a role matching the direction.
6. Stage the new version. Its provenance has mode `revision` and inputs $[revision\_target: target@v] +$ evidence. Record the change class, the direction and the three root sets.

This replaces E000's "§10 REVISE_INFON" evidence rule entirely, including its "an Infon is not evidence for its own revision" check. Citing the target, or any Infon on the same issue, carries no novel roots, so EVD-4 already refuses it.

### 4.4 FORGET

`FORGET` does not change the ledger. A forgotten version keeps its provenance, so its roots are unchanged, and the Infon's $IssueDigest$ stays in `infon_issues`. Forgetting the current head leaves the issue with no head, so re-forming it is a re-formation (ISS-4).

---

## 5. Replay

Replay rebuilds structure exactly as in E000 (Law 7), and adds these checks while it applies each transition in order:

- **EVD-7 audit.** Before applying transition $n$, recompute the issue, the formation classification, and `inherited`, `candidate` and `novel` for each of its `FORM_INFON` and `REVISE_INFON` operations, from the state rebuilt so far. Compare them with the justification recorded in $n$. Any difference refuses the wake-up with `IntegrityError`.
- **EVD-5 audit.** A revision recorded as administrative carries no `support` or `counterevidence` input.
- **ISS-3 audit.** After applying each transition, every issue has at most one current head.

These checks read only provenance, roles, issue digests and headers, all of which survive `FORGET`. So every evidence-accounting fact can be recomputed from origin and lineage alone, however much content has been forgotten.

They do not re-derive a revision's direction (ROL-4) or V1-CERTAINTY. Those need Infon bodies, which may be forgotten, so they stay auditable only as far as the bodies survive (EVD-7).

---

## 6. Ports and API Changes

- **Body channels.** `kernel.body_channel(ref)` serves both exteroceptive and interoceptive channels. There is no port or proposal field through which an organ can obtain `self-observation` (INT-3).
- **Organ testimony** needs no new port. An organ's own knowledge is a `FormInfon` with no inputs, proposed through its OrganPort, and its root comes from that port (ROT-3).
- **No external testimony port.** E001 builds none (ROT-3). Heard testimony is always `attributed`.

---

## 7. Conformance Cases

Every case becomes a test. For each case, a mutant or deliberately broken implementation MUST be shown to fail it. Cases 1–24 are the brief's, preserved. Cases 25–33 were found while writing and reviewing this spec.

The brief asked that every verdict be recomputable at replay. This spec narrows that, as EVD-7 does: every evidence-accounting fact in these cases (roots, ledger membership, novelty, classification, head uniqueness) is recomputable at replay. Direction and certainty verdicts are recomputable only while the bodies involved survive.

**Notation.** $K$ is the issue under test and $K'$ another issue. "rev" is `REVISE_INFON` and "form" is `FORM_INFON`. `s:` means support, `c:` counterevidence, `d:` derivation_input and `a:` attribution. A rejected proposal leaves the ledger unchanged.

| # | Initial state | Proposal | Verdict | Rule | Novel roots | $Ledger(K)$ after |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | $I$ on $K$ from $O_1$; $J$ on $K'$ from $O_1, O_2$ | rev $I$ up, `s:J` | accept | EVD-4 | $\{O_2\}$ | $\{O_1, O_2\}$ |
| 2 | $A$ on $K$ from $O_1$; $B$ on $K'$ with `d:A` | rev $A$ up, `s:B` | reject | EVD-4 | $\varnothing$ | $\{O_1\}$ |
| 3 | $A$ on $K$, testimony by $M$; $J$ on $K'$, testimony by $M$ | rev $A$ up, `s:J` | reject | EVD-4 | $\varnothing$ | $\{T(M)\}$ |
| 4 | $A$ on $K$ from $O_1$, lowered with `c:O_2` | rev $A$ down, `c:O_2` | reject | EVD-4 (EVD-6) | $\varnothing$ | $\{O_1, O_2\}$ |
| 5 | as 4 | rev $A$ up, `s:O_2` | reject | EVD-4 (EVD-6) | $\varnothing$ | $\{O_1, O_2\}$ |
| 6 | $I$ v1 from $O_1$; v2 revised with `s:E` | rev $I$ up, `s:O_1` | reject | EVD-4 | $\varnothing$ | $\{O_1, E\}$ |
| 7 | $C$ on $K$, testimony by $M$; paraphrase $C'$ on $K'$, testimony by $M$ | rev $C$ up, `s:C'` | reject | EVD-4 | $\varnothing$ | $\{T(M)\}$ |
| 8 | $X$ on $K$, attributed, `a:U_1`; second hearing $U_2$ | rev $X$ up, `a:U_2` | reject | EVD-4 | $\varnothing$ | $\varnothing$ |
| 9 | $C$ on $K$ from $O_1$; attributed Infons for speakers $A$, $B$, $C$ on other issues | rev $C$ up, `s:` all three | reject | EVD-4 | $\varnothing$ | $\{O_1\}$ |
| 10 | $A$ on $K$ from $O_A$; $B$ on $K'$ from $O_B$ | (i) rev $A$ `s:B`; (ii) rev $B$ `s:A`; (iii) rev $A$ `s:B` | accept, accept, reject | EVD-4 | (i) $\{O_B\}$ (ii) $\{O_A\}$ (iii) $\varnothing$ | $\{O_A, O_B\}$ |
| 11 | $I$ on $K$ from $O_1$ | rev $I$ up, `s:O_1`, `s:O_2` | accept; justification `candidate` $\{O_1, O_2\}$, `novel` $\{O_2\}$ | EVD-4, EVD-7 | $\{O_2\}$ | $\{O_1, O_2\}$ |
| 12 | $I$ on $K$ from $O_1$; $O_1$ forgotten | rev $I$ up, `s:O_1` | reject | EVD-4 | $\varnothing$ | $\{O_1\}$ |
| 13 | seed with an interoceptive channel $Q$ | consolidate an Observation from $Q$; another from an exteroceptive channel; inspect the proposal types | modes `self-observation` and `observation`; no proposal field sets a mode | INT-2, INT-3 | — | — |
| 14 | $I$ is the head of $K$, from $O_1$ | form $I$'s claim, `d:O_1` | reject (clone) | ISS-4 | — | $\{O_1\}$ |
| 15 | as 14 | (i) form $I$'s claim, `d:O_3`; (ii) rev $I$ up, `s:O_3` | reject, then accept | ISS-4, EVD-4 | (ii) $\{O_3\}$ | $\{O_1, O_3\}$ |
| 16 | $I$ on $K$ from $O_1$, retired | form $I$'s claim, `d:O_1` | reject (re-formation) | ISS-4 | $\varnothing$ | $\{O_1\}$ |
| 17 | as 16 | (i) form, `d:O_3`; (ii) rev the new $J$ up, `s:O_1` | accept, then reject | ISS-4, EVD-4 | (i) $\{O_3\}$ (ii) $\varnothing$ | $\{O_1, O_3\}$ |
| 18 | $I$ on $K$ from $O_1$, forgotten | form $I$'s claim, `d:O_1` | reject (re-formation) | ISS-4 | $\varnothing$ | $\{O_1\}$ |
| 19 | $I$ on $K$, contradicted | rev to `active`, no evidence | reject | EVD-4 | $\varnothing$ | unchanged |
| 20 | $I$ on $K$, active | rev to `retired`, no evidence | accept (administrative) | EVD-5 | $\varnothing$ | unchanged |
| 21 | $I = R(A)$ on $K$, from $O_1$ | form $R(A)$ with context `{"note": "x"}`, `d:O_1` | accept (first formation of $K'$) | ISS-4 | $\{O_1\}$ for $K'$ | $K$ unchanged; $Ledger(K') = \{O_1\}$ |
| 22 | $I$ on $K$ from $O_1$ | (i) rev $I$ to confidence 1, `s:O_7`; (ii) rev $I$ up, `s:O_7` | reject (V1-CERTAINTY), then accept | EVD-3, EVD-4 | (ii) $\{O_7\}$ | $\{O_1, O_7\}$ |
| 23 | $K$'s head retired; $Ledger(K) = \{O_1\}$ | (i) form, `d:O_1, d:O_2`; (ii) forget that Infon; (iii) form, `d:O_2` | accept, accept, reject | ISS-4, ISS-7 | (i) $\{O_2\}$ (iii) $\varnothing$ | $\{O_1, O_2\}$ throughout (ii) and (iii) |
| 24 | none | form $X$, `a:U` only | accept; mode `attributed`; `grounded` = false | ISS-4, ROT-8 | $\varnothing$ | $\varnothing$ |
| 25 | $X$ on $K$, attributed; hearing $U_2$ | rev $X$ up, `s:U_2` | **accept**: the relevance boundary (§8) | EVD-4, ROL-5 | $\{U_2\}$ | $\{U_2\}$ |
| 26 | $I$ on $K$ from $O_1$ | (i) rev up, `c:O_2` only; (ii) rev down, `c:O_2` | reject, then accept | ROL-4, EVD-4 | (ii) $\{O_2\}$ | $\{O_1, O_2\}$ |
| 27 | none | one proposal: consolidate $O_1$; form $I$, `d:O_1`; rev $I$ up, `s:O_1` | reject at the third operation; nothing admitted | EVD-3, EVD-4 | $\varnothing$ | no issue exists |
| 28 | $X$ on $K$, attributed, retired | form $X$'s claim again, `a:U_2` | reject: rootless re-formation adds nothing | ISS-4 | $\varnothing$ | $\varnothing$ |
| 29 | $A$ on $K$, testimony by $M$ | rev $A$ up, `s:` a testimony Infon by organ $N$ | accept: an independent source | EVD-4, ROT-3 | $\{T(N)\}$ | $\{T(M), T(N)\}$ |
| 30 | any | form with `s:O_1`, or with `revision_target` | reject | ROL-3 | — | unchanged |
| 31 | a Heart with an accepted revision | edit that transition's justification `novel` set, re-digest the record, restore guards, open | wake-up refused | EVD-7 | — | — |
| 32 | organ $M$ testifies through its own port, naming organ $N$ as the source in the payload's participants and context | form with no inputs | accept; the root is $T(M)$, and no proposal field can name a source | ROT-2, ROT-3 | $\{T(M)\}$ | $\{T(M)\}$ |
| 33 | $I$ on $K$ from $O_1$ | (i) rev to `retired`, confidence unchanged, `s:O_7`; (ii) rev to `retired`, no evidence; (iii) form $I$'s claim, `d:O_7` | reject, accept, then accept (re-formation) | EVD-5, ISS-4 | (iii) $\{O_7\}$ | $\{O_1\}$ after (i) and (ii); $\{O_1, O_7\}$ after (iii) |

---

## 8. Boundaries

### What each mechanism establishes

| Mechanism | Establishes |
| --- | --- |
| Port | source identity |
| Provenance | derivational history |
| Role | the organ's evidential claim |
| Roots | support ancestry |
| Issue ledger | whether that support is novel |

### Limits

These are limits of E001, stated so that they are never mistaken for guarantees.

- **Relevance.** A real root is not relevant evidence. Roles are the proposing organ's claims (ROL-5). An organ can cite any real, persisted Observation as `support` and satisfy novelty, even when it is irrelevant, including the utterance it heard someone say (case 25).
  - E001 prevents *recycling* $O_1$. It does not prevent an organ feeding in $O_2, O_3, O_4, \ldots$ that have nothing to do with the issue.
  - That is not a loophole once the boundary is explicit; it is the research question for a later evidence-relevance layer.
  - E001 guarantees that roots are real, attributable and not recycled. It does not guarantee they bear on the claim.
- **Calibration.** A rootless Infon can hold high confidence. ROL-4 checks direction, not magnitude.
- **Semantic issue equivalence.** A ClaimKey is syntactic. Different context, different participants, or the same participants in a different order make a different issue (case 21).
- **Correlated observations.** Two channels observing one event give two independent ObservationRoots.
- **External testimony.** No authority-bound external source exists in E001, so heard testimony never grounds anything.
- **Experiments.** ExperimentRoot and the `simulation` and `experiment` modes are reserved.

---

## 9. Decisions This Spec Adds to the Brief

Each of these was needed to write enforceable rules. Each can be struck or changed without touching the rest.

1. **ROL-4, direction consistency.** Without it, the brief's "direction" column would have no effect. The rule refuses raising confidence on novel counterevidence alone (case 26). It checks consistency, not calibration.
2. **`attribution` is allowed in revisions.** This is how a second hearing is recorded (case 8). Being root-free, it can never carry novelty.
3. **Roles are organ claims (ROL-5), and case 25 pins the consequence.** An organ that labels a heard utterance as `support` gets a real, novel ObservationRoot. This is the relevance boundary, reached through role labels. The brief's attack 8 holds only for an organ that labels the utterance honestly as `attribution`.
4. **Rootless re-formation is refused (case 28).** A rootless issue that is retired cannot be re-formed without novel roots, so ungrounded claims cannot be reset either.
5. **Replay audits justifications and heads (EVD-7, ISS-3; case 31).** This makes the brief's "every verdict recomputable at replay" something that wake-up enforces, not just something that could in principle be checked.
6. **`infon_issues` is a separate append-only table**, keeping the shared object header unchanged, as the brief asked.
7. **One `body_channel` for both channel kinds.** The manifest decides the mode, so no extra port type is needed.
8. **TRN-2 and TRN-3** give the E000 backlog's imprecise citations precise homes (§1.9).
9. **Law 8 is worded as "a Mind cannot choose or fabricate the identity of a grounding root".** The brief's shorter "a Mind cannot mint grounding roots" would contradict ROT-3, since an organ does cause its own bound TestimonyRoot to be admitted. The law is about who fixes a root's identity (case 32).
10. **Administrative retirement cannot admit roots (EVD-5; case 33).** Evidence cited without being weighed would otherwise be consumed.
11. **The replay guarantee covers evidence accounting, not every verdict (EVD-7).** A revision's direction and V1-CERTAINTY depend on Infon bodies, which logical forgetting may remove.

---

## 10. Done

The same closure rule as E000 applies:

- every case in §7 has a test, and a mutant that fails it;
- FOUNDATIONS 0.6 is applied with the rule IDs above;
- the known Critical and Important findings from review are fixed, each with a regression test that failed first;
- the full suite and strict mypy are green.
