# E001: Evidence Integrity — Design Brief

> **Status:** Brief, agreed 2026-09-26. Not a spec. It frames the question, the invariant and the models; the E001 normative spec comes next.
> **Builds on:** E000, tagged `e000` (FOUNDATIONS draft 0.5).

## 1. The Question

> What machinery is required to ensure that persistent commitments can gain support only from genuinely new, attributable evidence?

E000 guarantees that provenance *exists*: every commitment names its inputs, and lineage records every change. It does not guarantee that provenance is *epistemically honest*. A Heart can be perfectly lawful under E000 and still:

- raise an Infon's confidence by recycling evidence it has already used,
- let two Infons revise each other back and forth with no new observation,
- count one source's repeated statements as independent confirmations,
- escape counterevidence by forming a fresh copy of a claim,
- label a claim `self-observation` with nothing behind it.

### What E001 guarantees, exactly

> Evidence counted as new is **structurally novel, attributable, and non-recycled**. E001 does not yet guarantee that evidence is **relevant** or **probative**.

A Mind can still attach a fresh but irrelevant Observation and satisfy novelty. That is the boundary of this experiment, not a defect in it (§9). The same holds for confidence:

$$
\boxed{\text{E001 protects evidence accounting, not confidence calibration.}}
$$

A commitment with no grounding roots can still hold high confidence. Making confidence answer to evidence is later work.

## 2. The Invariant

$$
\boxed{\textbf{New provenance input} \neq \textbf{new evidence}}
$$

Evidence is measured against the **issue** it bears on, not against a target object (§6), because changing an object's identity must not reset anything:

$$
\boxed{\text{Object identity is not epistemic issue identity.}}
$$

$Ledger(K)$ is the set of grounding roots that have already been admitted into the epistemic history of issue $K$. For evidence $E$ and issue $K$ at a given point in lineage:

$$
\boxed{NovelRoots(E,K) = Roots(E) \setminus Ledger(K)}
$$

$$
\boxed{NewEvidence(E,K) \iff NovelRoots(E,K) \neq \varnothing}
$$

Shared ancestry is allowed. What matters is whether the evidence brings at least one grounding root the issue has not already admitted. For an ordinary revision of $T$, the issue is $ClaimKey(T)$, so nothing changes for revisions; the issue form is what also covers cloning and re-formation. A transition's justification records exactly $NovelRoots$, not every root the evidence carries.

**Only a committed transition admits evidence.** A proposal never consumes evidence. If a proposal cites a fresh Observation and is rejected for any reason, the ledger is unchanged, and that Observation is still new the next time. Otherwise a failing or malicious organ could exhaust evidence just by proposing it.

A second principle governs how roots flow:

$$
\boxed{\textbf{Support is inherited; independence is not.}}
$$

A derived commitment inherits the grounding roots of its inputs. Adding another derivation node never creates a new independent source.

## 3. The Root Model

A **grounding root** is primary evidence that no Mind organ can manufacture:

$$
\boxed{\textbf{A Mind cannot mint grounding roots.}}
$$

Only three kinds exist:

| Root | What it is | Why a Mind cannot manufacture it |
| --- | --- | --- |
| **ObservationRoot** | One persisted Observation, identified by its id. | Only a Body channel can deliver an Observation, through its own port (ORG-6). |
| **TestimonyRoot** | A testifying source whose identity comes from a port (§3.2). | The source is fixed by the port it testifies through. Restating, paraphrasing or re-deriving a claim does not change it. |
| **ExperimentRoot** | A recorded experiment outcome, preregistered against competing predictions. | Reserved. It needs Models and Predictions, so E001 defines it but does not build it. |

Roots are **version-relative**. They are defined for a specific version, $Roots(ObjectRef(id, version))$, never for an object id alone, because a commitment's support changes as it is revised:

$$
Roots(I@1) = \{O_1\} \qquad Roots(I@2) = \{O_1, O_2\}
$$

$Roots$ is defined recursively:

- For an Observation $O$: $Roots(O@1) = \{ObservationRoot(O)\}$.
- For testimony from a port-bound source $S$: $\{TestimonyRoot(S)\}$.
- For any other version: the union of the roots of its provenance inputs in every role except `attribution` (§5).

Roots are identified by ids, and ids survive `FORGET`, because headers and lineage stubs are never forgotten. So $Roots$ can always be computed from lineage alone, which keeps Law 7 intact. E001 computes roots from the provenance graph on demand, memoized in memory, and does not materialize another authoritative state.

### 3.1 Self-observation becomes a port

`self-observation` stops being a provenance kind that any organ can claim. Entelechy observing its own state is an Observation like any other, delivered through a capability-bound interoceptive channel that the seed registers. The kernel assigns the kind from the channel, and the payload has no say. The root is an ObservationRoot.

As with ORG-6 in E000, the port establishes the source and kind of *delivery*, not the truth of the payload.

### 3.2 Testimony roots come only from ports

A TestimonyRoot exists only when the source's identity comes from something the proposing Mind cannot choose. For E001 that means a port:

- **Organ testimony** (ORG-3, knowledge from pretraining): the source is the organ that proposes it, fixed by its OrganPort. $TestimonyRoot = \langle organ\_id \rangle$.
  - It is keyed by the stable organ id, **not the version**. A retrained organ is not automatically an independent source, so the version stays as provenance metadata. If a genuinely independent training history can someday be established, it can earn a different source identity.
- **Attributed testimony** (ORG-4, an organ reports that a speaker said $X$): it may be recorded, but it **does not create a TestimonyRoot**. The speaker's identity is whatever the attributing organ writes. If attributed speakers produced roots, a Mind could write "A said C", "B said C", "C said C" and mint three independent roots, which only moves the forgery from Infons into source labels.

$$
\boxed{\text{Unauthenticated attributed testimony may be recorded, but it creates no TestimonyRoot.}}
$$

A speaker becomes a root only through an authority-bound testimony source, such as a source-bound port that the host registers, analogous to ORG-6. E001 **defines** such sources: a future authority-bound testimony source MAY create $TestimonyRoot(source)$. E001 does **not** build general enrollment of external sources. Organ testimony is enough to exercise TestimonyRoots, and attributed testimony is enough to prove that hearing creates no root.

$TestimonyRoot = \langle source \rangle$, never $\langle source, claim\_context \rangle$. With the claim in the identity, a source could manufacture independence by paraphrase: "C", then "C, and I'm confident", then "it is the case that C". Keying on the source alone deliberately undercounts rather than let a source mint independence. We lose nothing by this, because newness is always measured against a specific issue, and relevance is a non-goal.

## 4. Production Mode Is Not Evidence Composition

E000 gives every provenance record one `kind`, and asks it to answer two different questions at once:

1. **How was this commitment produced?**
2. **What grounds it?**

Consider $I \leftarrow O_1 + Testimony(S)$. Its roots are $\{ObservationRoot(O_1), TestimonyRoot(S)\}$. No single kind describes that: it isn't purely `observation`, it isn't purely `testimony`, and `derivation` says how $I$ was made but nothing about what grounds it.

E001 separates the two:

```text
Provenance
    mode    = derivation        how it was produced: assigned by the validator, never claimed
    inputs  = [...], each with a role

Roots (computed from the provenance graph, never stored as a claim)
    ObservationRoot(O1)
    TestimonyRoot(S)
```

The production mode is set from the operation and the port that proposed it. A first cut of the modes:

| Mode | Produced by |
| --- | --- |
| `origin` | the seed |
| `observation` | receipt through a Body channel |
| `self-observation` | receipt through an interoceptive channel |
| `testimony` | an organ asserting its own knowledge through its port |
| `attributed` | an organ reporting what a speaker said |
| `derivation` | formation from inputs |
| `revision` | `REVISE_INFON` |

This removes the last label a payload supplies that looks like evidence. It also dissolves the E000 complaint that a revision "hides" testimony ancestry behind `derivation`: nothing is hidden when roots are always computable.

## 5. The Role Model

Every provenance input carries a role:

| Role | Passes roots into the new version | Can count as new evidence | Direction |
| --- | --- | --- | --- |
| `support` | yes | yes | for |
| `counterevidence` | yes | yes | against |
| `derivation_input` | yes | not applicable (formation) | none |
| `revision_target` | **yes** | **never** | none |
| `attribution` | **no** | never | none |

**`revision_target` passes its roots through.** Otherwise the ledger has amnesia. If $I$ v1 rests on $O_1$ and is revised with $E$ into v2, dropping the target's roots would make $Roots(I_{v2}) = \{E\}$, and $O_1$ would count as "new" again for v3. That is E000's I2 bug in a new form. So:

$$
Roots(T_{v+1}) = Roots(T_v) \cup Roots(evidence)
$$

**`attribution` passes nothing.** When someone says $X$, the utterance's Observation supports "S said X", not $X$. If it supported $X$, every repetition would bring a fresh ObservationRoot, and repetition would manufacture independence. The utterance links to the $X$-Infon as `attribution`, recording where the testimony was heard.

**Evidence is weighed once.** Support and counterevidence share one closure:

$$
\boxed{\textbf{Evidence is weighed once.}}
$$

A root already weighed for an issue, in either direction, cannot be weighed again. Otherwise a system could alternate its reading of one observation and extract unlimited confidence movement from a single event.

**What needs new evidence.** A *trust change* needs new evidence: any confidence change, and `active` ↔ `contradicted`. An *administrative lifecycle change* does not: `active` or `contradicted` → `retired`, for supersession or memory policy.

## 6. The Evidence Ledger Belongs to the Issue

### The clone attack

Every attack in the first draft was a revision of an existing target. But `FORM_INFON` assigns confidence freely, and the invariant constrains only revisions. **Formation is therefore an unconstrained trust assignment**, and cloning a claim is a revision with the checks switched off:

```text
I1 = R(A), grounded by O1, lowered to 0.3 by counterevidence O2
Mind forms I2 = R(A), grounded by O1, at confidence 0.9
```

`I2` has a fresh ledger. $O_1$ has been weighed again, and $O_2$'s counterevidence has been escaped. There are three routes to a fresh ledger:

- **Clone while live:** form a duplicate while the original is still active.
- **Retire and re-form:** retire the original, which needs no evidence (§5), then form the claim again.
- **Forget and re-form:** forget the original, whose content (and so its claim) is then gone, then form it again.

An evidence ledger keyed to an object id cannot see any of these. It has to be keyed to the question the claim answers.

### The resolution: issues

The design separates three layers that one Infon object used to carry together:

$$
\boxed{\text{ClaimKey} \rightarrow \text{Issue} \rightarrow \text{Infon head}}
$$

| Layer | Answers |
| --- | --- |
| **ClaimKey** | Which epistemic question is this? |
| **Issue ledger** | Which primary evidence has this question already consumed? |
| **Current head** | What is Entelechy's current commitment on this question? |

$$
ClaimKey(I) = \langle relation,\ participants,\ context \rangle \qquad IssueDigest(I) = Digest(Canonical(ClaimKey(I)))
$$

**Polarity is excluded**, so $ClaimKey(I^{+}) = ClaimKey(I^{-})$ whenever relation, participants and context match. $R(A)$ and $\neg R(A)$ are not two questions; they are competing answers to one issue, and evidence for and against lives in one ledger.

$$
Ledger(K)@seq = \bigcup \{\, Roots(I@v) : IssueDigest(I) = K,\ v \text{ committed at or before } seq \,\}
$$

The ledger covers every Infon that has ever had issue $K$: current, retired and forgotten. Because of root inheritance (§5), this union is exactly the set of roots admitted into $K$'s history.

The rules:

- **One current head per issue.** An issue has at most one current head: its single non-retired, non-forgotten Infon. Forming an Infon for an issue that already has a head is refused, and new evidence goes through `REVISE_INFON` on the head. Without this rule, two Infons could hold different confidences for the same claim, and "what does the Heart believe about $R(A)$?" would have no answer. Historical and contradicting commitments stay in lineage; disagreement is not deleted, only the current state is made unambiguous.
- **Succession within an issue.** The only content change that stays on the same issue is a change of polarity. That is a successor (OBJ-4) that replaces the head in the same transition, and, being a trust change, it needs new evidence. Negative Infons remain unimplemented in E001, so this rule is defined here but not exercised.
- **Re-forming needs new evidence.** Forming an Infon for an issue with no current head, because its earlier Infons are all retired or forgotten, requires $NewEvidence(E, K)$.
- **Newness is always measured against the issue.** For a head $I$, $Ledger(K) \supseteq Roots(I)$, so revision behaves as before. After a re-formation, the ledger still remembers what was admitted.
- **The issue survives FORGET.** $IssueDigest$ is an immutable Infon identity field, a type-specific extension of the header, not a change to the shared PersistentObject header. Like the body digest, it is kept when the content is forgotten. Forgetting an Infon never forgets what evidence its issue has consumed. This is consistent with MEM-6: forgetting is logical.

A commitment with no roots is **ungrounded**, not invalid. The derived property

```text
grounded(I) := Roots(I) != ∅
```

is computed, not stored. It lets the Heart say honestly that it holds $R$ with no primary evidence behind it, instead of disguising unsupported structure as evidence-backed.

### The boundary

A ClaimKey is syntactic, which gives E001 an exact, mechanically decidable equivalence between issues. Change the context or a participant and you have a different issue with an empty ledger: $R(A)$ with context `{"note": "x"}` is a new issue.

Context stays in the ClaimKey. Dropping it would make genuinely contextual claims collide, such as `warm(room) | morning` and `warm(room) | evening`, and deciding whether two such claims are one issue needs semantic reasoning E001 does not have. This is the same wall as relevance, and it is stated as a limit, not hidden:

> E001 prevents evidence-reset attacks for syntactically identical issues. It does not determine semantic equivalence between differently encoded issues.

## 7. Attack Cases

Each case becomes an executable test in the spec, with a mutant proving the test can fail. Unless stated otherwise, the Infons in a case bear on one issue.

| # | Setup | Attempt | Verdict | Why |
| --- | --- | --- | --- | --- |
| 1 | $I$ from $O_1$; $J$ (another issue) from $O_1 + O_2$ | revise $I$ with $J$ | **accept** | $NovelRoots = \{O_2\}$ |
| 2 | $A$ from $O_1$; $B$ (another issue) derived from $A$ | revise $A$ with $B$ | **reject** | $Roots(B) = \{O_1\} \subseteq Ledger$ |
| 3 | $A$ from organ $M$'s testimony; a second testimony Infon from $M$ | revise $A$ with it | **reject** | same TestimonyRoot $\langle M \rangle$ |
| 4 | $A$ lowered using $O_2$ as counterevidence | lower again with $O_2$ | **reject** | $O_2$ already weighed |
| 5 | $A$ lowered using $O_2$ | raise $A$ using $O_2$ as support | **reject** | evidence is weighed once |
| 6 | $I$ v1 from $O_1$; revised with $E$ into v2 | revise v2 with $O_1$ | **reject** | $O_1$ inherited through `revision_target` |
| 7 | organ $M$ testifies $C$ | $M$ testifies a paraphrase $C'$ to support $C$'s Infon | **reject** | same TestimonyRoot $\langle M \rangle$ |
| 8 | speaker $S$ heard saying $X$ twice | the second hearing supports the $X$-Infon | **reject** | `attribution` passes no roots |
| 9 | a Mind attributes $C$ to speakers $A$, $B$ and $C$ | use the three as support | **reject** | attributed testimony creates no roots |
| 10 | $A$ and $B$ (different issues), each from its own Observation | revise each with the other, alternately | **first revision of each accepted, every later one rejected** | after one exchange, each ledger holds the other's roots |
| 11 | evidence set $\{E_{old}, E_{new}\}$ | revise | **accept**; the justification lists only $E_{new}$'s roots | partial novelty is enough, and only the novelty is recorded |
| 12 | $O_1$ forgotten after grounding $I$ | revise $I$ with $O_1$'s stub | **reject** | the root identity survives `FORGET` |
| 13 | a Mind claims `self-observation` | any proposal | **impossible** | no port; the kind is assigned by the kernel |
| 14 | $I$ is the head of issue $K$, from $O_1$ | form $J$ with $I$'s claim, from $O_1$ | **reject** | $K$ already has a current head |
| 15 | $I$ is the head of $K$ | form $J$ with $I$'s claim, from new $O_3$ | **reject**; revising $I$ with $O_3$ is **accepted** | one current head per issue |
| 16 | $I$ on $K$ from $O_1$, then retired | form $J$ with $I$'s claim, from $O_1$ | **reject** | $O_1 \in Ledger(K)$ |
| 17 | as 16 | form $J$ from $O_3$, then revise $J$ with $O_1$ | **accept, then reject** | the ledger remembers $O_1$, though $O_1 \notin Roots(J)$ |
| 18 | $I$ on $K$ from $O_1$, then forgotten | form $J$ with $I$'s claim, from $O_1$ | **reject** | the issue digest survives in the header |
| 19 | $I$ contradicted | revise to `active` with no evidence | **reject** | a trust change |
| 20 | $I$ active | retire with no evidence | **accept** | an administrative change |
| 21 | $I = R(A)$ on $K$ | form $R(A)$ with context `{"note": "x"}` | **accept** as a different issue | the syntactic boundary (§6); the test pins it |
| 22 | $I$ on $K$ from $O_1$ | propose a revision citing fresh $O_7$ that is rejected for another reason, then propose a valid revision citing $O_7$ | **reject, then accept** | a proposal never consumes evidence; $Ledger(K)$ changes only on commit |
| 23 | $K$'s head retired; $Ledger(K) = \{O_1\}$ | re-form with $\{O_1, O_2\}$, forget that Infon, then re-form with $O_2$ | **accept, then reject** | forgetting an Infon does not forget what its issue consumed; $Ledger(K) = \{O_1, O_2\}$ |
| 24 | an Infon formed from attributed testimony only | read `grounded` | **false**, and the Infon is valid | ungrounded is not invalid |

Every case must also hold under replay: the verdict must be recomputable from origin and lineage alone.

## 8. Relation to FOUNDATIONS

E001 will need amendments. I expect them to be:

- **Laws:** "A Mind cannot mint grounding roots", and "Support is inherited; independence is not."
- **Roots:** the three root kinds; version-relative roots; testimony roots only from port-bound sources, keyed by stable source id.
- **Modes and roots:** provenance `kind` is replaced by a validator-assigned `mode`, plus roots computed from the graph. This is a change to PRV-1 through PRV-7 and to ORG-3 and ORG-4.
- **Roles:** every provenance input carries a role, with the semantics of §5. Evidence is weighed once.
- **Issues:** ClaimKey, and IssueDigest as an immutable Infon identity field; one current head per issue; succession within an issue; the issue ledger; only committed transitions admit evidence; re-forming needs new evidence; `grounded` as a derived property.
- **New evidence:** $NewEvidence(E, K)$ replaces the §10 REVISE_INFON requirement, and extends to re-formation.
- **ORG-6 extended:** the observation kind (`observation` or `self-observation`) is assigned from the channel.
- **Folded in from the E000 backlog**, because each is about auditing provenance:
  - ORG-2/PRV-7 wording for observation provenance,
  - imprecise rule citations,
  - the PER-8 read path for versions superseded within one transition.

**Compatibility.** E001 changes the provenance record (mode and roles) and the Infon header (issue). E000 Hearts exist only in tests, so they are not migrated. The schema version refuses them.

## 9. Non-Goals

- **Relevance and probative value.** Whether evidence is *about* the issue, or actually bears on it, is not judged (§1).
- **Confidence calibration.** E001 protects evidence accounting; it does not make confidence answer to evidence (§1).
- **Semantic issue equivalence.** Claims that differ only by opaque context or participants are different issues (§6).
- **Models, Predictions and experiment semantics.** ExperimentRoot is reserved, not built.
- **How much evidence moves confidence.** Weighting, Bayesian updating and calibration are out of scope. E001 decides only *whether* evidence counts, not *how much*.
- **Source reputation.** Some sources are more reliable than others; that is not modelled here.
- **Correlated observations.** Two channels observing the same event yield two ObservationRoots, treated as independent.
- **Authenticating heard speakers.** Attributed testimony roots nothing (§3.2). A source-bound testimony port may be defined, but cryptographic or real-world authentication is out of scope.
- **The rest of the E000 backlog.** Canonical hardening, memory lifecycle, storage and platform robustness, and internal API hardening stay in their own groups.

## 10. Decisions and Open Questions

All of the brief's open questions are settled:

- **OPEN-A, organ source granularity:** keyed by stable organ id, not version (§3.2).
- **OPEN-B, heard-speaker identity:** attributed testimony creates no root; only authority-bound sources do (§3.2).
- **OPEN-C, computed provenance kind:** reframed. A validator-assigned production mode, plus roots computed from the graph (§4).
- **OPEN-D, materialized roots:** computed on demand, memoized in memory; no second authoritative state (§3).
- **OPEN-E, rootless formation:** allowed. A rootless Infon is ungrounded, not invalid; `grounded(I) := Roots(I) != ∅` is derived (§6).
- **OPEN-F, status-only revisions:** trust changes need new evidence; retirement does not (§5).
- **OPEN-G, coarser issues:** closed. Context stays in the ClaimKey, and semantic issue equivalence is later work (§6).
- **OPEN-H, testimony source ports:** authority-bound testimony sources are defined; general external enrollment is not built (§3.2).
- **OPEN-I, successors across issues:** `derived_from` across issues is lineage only. If support should transfer, it must appear explicitly through a support-bearing role.
- **Evidence is weighed once**, **only committed transitions admit evidence**, and **self-observation is a port**.

No open question blocks the spec. The spec will surface its own.

## 11. What Would Make E001 Done

- Every attack case in §7 is an executable test, with a mutant proving the test can fail.
- $NewEvidence$ is enforced at validation, for revision and for re-formation, and is recomputable at replay.
- No Mind organ can create a grounding root through any port.
- FOUNDATIONS is amended with rule IDs for every guarantee above.
- The same closure rule as E000 applies: known Critical and Important findings fixed, regression tests that failed first, and a green suite and strict mypy.
