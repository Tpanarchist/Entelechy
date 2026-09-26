"""Mutation demonstrations for the E001 conformance suite (spec §7, §10).

The approved spec's closure rule requires that "for each case, a mutant or
deliberately broken implementation MUST be shown to fail it." Precise
assertions are necessary but not sufficient for that: this file actually
breaks the mechanisms the 33 cases in test_conformance.py depend on, one
deliberately-wrong variant at a time, runs every case against each one, and
requires that every case actually fails under at least one of them.

Case 31 needs no separate mutant here: its own test already constructs a
tampered transition record (a "deliberately broken implementation" of
lineage itself) and shows replay refuses it. Running the cases below under
each mutant also incidentally kills case 31 whenever the mutant breaks the
formation/revision it sets up with, which is a bonus, not the point.
"""

import inspect
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

import pytest
import test_conformance as conformance
from harness import FixedRetention, Harness, policy_seed
from harness import plain_seed as _plain_seed

from entelechy.foundation import seed as seed_module
from entelechy.foundation import validator as validator_module
from entelechy.foundation.evidence import Classification, Root, RootReader
from entelechy.foundation.evidence import observation_root as make_observation_root
from entelechy.foundation.evidence import testimony_root as make_testimony_root
from entelechy.foundation.types import Mode, ObjectRef, ObjectType, ProvenanceInput, Role

# --- collecting the 33 cases, and running one given a fresh store --------


def _case_functions() -> dict[str, Callable[[object], None]]:
    return {
        name: func
        for name, func in vars(conformance).items()
        if name.startswith("test_case") and inspect.isfunction(func)
    }


def _run_case(func: Callable[[object], None], tmp_path: Path, index: int) -> None:
    (param_name,) = inspect.signature(func).parameters
    if param_name == "heart":
        harness = Harness(tmp_path / f"heart-{index}.db", _plain_seed())
        try:
            func(harness)
        finally:
            harness.close()
    elif param_name == "policy_heart":
        harness = Harness(tmp_path / f"policy-{index}.db", policy_seed(), FixedRetention())
        try:
            func(harness)
        finally:
            harness.close()
    elif param_name == "tmp_path":
        case_dir = tmp_path / f"case-{index}"
        case_dir.mkdir()
        func(case_dir)
    else:
        raise AssertionError(f"{func.__name__} takes an unexpected fixture: {param_name!r}")


# --- mutants: one deliberately broken variant of one mechanism each ------


def _mutant_no_roots(mp: pytest.MonkeyPatch) -> None:
    """ROT-6 broken: nothing ever grounds anything."""
    mp.setattr(validator_module, "roots_of_many", lambda refs, work: frozenset())


def _mutant_full_novelty(mp: pytest.MonkeyPatch) -> None:
    """EVD-2 broken: every candidate root looks novel, inherited or not."""
    mp.setattr(validator_module, "novel_roots", lambda candidate, inherited: candidate)


def _mutant_no_novelty(mp: pytest.MonkeyPatch) -> None:
    """EVD-2 broken the other way: nothing is ever novel."""
    mp.setattr(validator_module, "novel_roots", lambda candidate, inherited: frozenset())


def _mutant_empty_ledger(mp: pytest.MonkeyPatch) -> None:
    """ISS-7 broken: an issue's ledger never remembers what it has admitted."""
    mp.setattr(validator_module, "ledger", lambda issue, work: frozenset())


def _mutant_always_first_formation(mp: pytest.MonkeyPatch) -> None:
    """ISS-4 broken: clone and re-formation are never detected."""
    mp.setattr(validator_module, "classify", lambda issue, work: Classification.FIRST_FORMATION)


def _mutant_constant_testimony_root(mp: pytest.MonkeyPatch) -> None:
    """ROT-3 broken: every organ's testimony collapses onto one source."""
    mp.setattr(validator_module, "testimony_root", lambda organ_id: Root("testimony", "mind"))


def _mutant_form_infon_allows_any_role(mp: pytest.MonkeyPatch) -> None:
    """ROL-3 broken at formation: an organ could cite support or revision_target."""
    mp.setattr(validator_module, "FORM_INFON_ALLOWED_ROLES", frozenset(Role))


def _mutant_revise_infon_allows_any_role(mp: pytest.MonkeyPatch) -> None:
    """ROL-3 broken at revision: an organ could cite derivation_input directly."""
    mp.setattr(validator_module, "REVISE_INFON_ALLOWED_ROLES", frozenset(Role))


def _mutant_administrative_admits_evidence(mp: pytest.MonkeyPatch) -> None:
    """EVD-5 broken: administrative retirement could consume support/counterevidence."""
    mp.setattr(
        validator_module,
        "_administrative_evidence_violation",
        lambda support, counterevidence: None,
    )


def _mutant_never_interoceptive(mp: pytest.MonkeyPatch) -> None:
    """INT-2 broken: no channel is ever classified as interoceptive."""
    mp.setattr(seed_module.Manifest, "is_interoceptive", lambda self, channel: False)


def _mutant_never_administrative(mp: pytest.MonkeyPatch) -> None:
    """EVD-5 broken the other way: a bare retirement is never recognized as
    administrative, so it is forced through the ordinary trust-change path
    and refused for lack of new evidence."""
    mp.setattr(validator_module, "_is_administrative_change", lambda status, direction: False)


def _mutant_formation_mode_always_derivation(mp: pytest.MonkeyPatch) -> None:
    """PRV-8 broken: every formation is recorded as a derivation, even one
    with no inputs (should be testimony) or only attribution inputs (should
    be attributed)."""
    mp.setattr(validator_module, "_formation_mode", lambda resolved: Mode.DERIVATION)


def _mutant_evidence_by_direction_includes_attribution(mp: pytest.MonkeyPatch) -> None:
    """ROL-4/EVD-2 broken: attribution-roled evidence is folded into support,
    so citing an attributed source looks like new support evidence."""

    def _evidence_by_direction(
        resolved: Sequence[ProvenanceInput],
    ) -> tuple[tuple[ObjectRef, ...], tuple[ObjectRef, ...]]:
        support = tuple(item.ref for item in resolved if item.role in (Role.SUPPORT, Role.ATTRIBUTION))
        counterevidence = tuple(item.ref for item in resolved if item.role is Role.COUNTEREVIDENCE)
        return support, counterevidence

    mp.setattr(validator_module, "_evidence_by_direction", _evidence_by_direction)


def _mutant_attribution_inputs_ground(mp: pytest.MonkeyPatch) -> None:
    """ROT-6 broken narrowly: an object's own roots include what it reached
    through attribution inputs, not just support/counterevidence/derivation,
    so citing an attribution-only Infon as support looks like new evidence."""

    def _roots_of(
        ref: ObjectRef, reader: RootReader, seen: frozenset[ObjectRef]
    ) -> frozenset[Root]:
        if ref in seen:
            raise AssertionError(f"provenance cycles back to {ref.id}@{ref.version}")
        header = reader.header_at(ref)
        assert header is not None
        if header.type is ObjectType.OBSERVATION:
            return frozenset({make_observation_root(ref.id)})
        provenance = reader.provenance_of(header.provenance_id)
        assert provenance is not None
        if provenance.mode is Mode.ORIGIN:
            return frozenset()
        if provenance.mode is Mode.TESTIMONY:
            assert provenance.organ is not None
            return frozenset({make_testimony_root(provenance.organ.id)})
        seen = seen | {ref}
        result: set[Root] = set()
        for item in provenance.inputs:
            # deliberately NOT skipping attribution inputs here (breaks ROT-6)
            result |= _roots_of(item.ref, reader, seen)
        return frozenset(result)

    def _roots_of_many(refs: Iterable[ObjectRef], reader: RootReader) -> frozenset[Root]:
        result: set[Root] = set()
        for ref in refs:
            result |= _roots_of(ref, reader, frozenset())
        return frozenset(result)

    mp.setattr(validator_module, "roots_of_many", _roots_of_many)


MUTANTS: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    "no_roots (ROT-6)": _mutant_no_roots,
    "full_novelty (EVD-2)": _mutant_full_novelty,
    "no_novelty (EVD-2)": _mutant_no_novelty,
    "empty_ledger (ISS-7)": _mutant_empty_ledger,
    "always_first_formation (ISS-4)": _mutant_always_first_formation,
    "constant_testimony_root (ROT-3)": _mutant_constant_testimony_root,
    "form_infon_allows_any_role (ROL-3)": _mutant_form_infon_allows_any_role,
    "revise_infon_allows_any_role (ROL-3)": _mutant_revise_infon_allows_any_role,
    "administrative_admits_evidence (EVD-5)": _mutant_administrative_admits_evidence,
    "never_interoceptive (INT-2)": _mutant_never_interoceptive,
    "never_administrative (EVD-5)": _mutant_never_administrative,
    "formation_mode_always_derivation (PRV-8)": _mutant_formation_mode_always_derivation,
    "evidence_by_direction_includes_attribution (ROL-4/EVD-2)": (
        _mutant_evidence_by_direction_includes_attribution
    ),
    "attribution_inputs_ground (ROT-6)": _mutant_attribution_inputs_ground,
}


def test_every_conformance_case_is_killed_by_some_mutant(tmp_path: Path) -> None:
    cases = _case_functions()
    assert len(cases) == 33, f"expected all 33 conformance cases, found {len(cases)}: {sorted(cases)}"

    killed_by: dict[str, str] = {}
    index = 0
    for mutant_name, apply_mutant in MUTANTS.items():
        for case_name, func in cases.items():
            if case_name in killed_by:
                continue
            index += 1
            with pytest.MonkeyPatch.context() as mp:
                apply_mutant(mp)
                try:
                    _run_case(func, tmp_path, index)
                except Exception:
                    killed_by[case_name] = mutant_name

    survivors = sorted(set(cases) - set(killed_by))
    assert not survivors, (
        f"{len(survivors)} case(s) survived every mutant (no regression in their own "
        f"mechanism would make them fail): {survivors}"
    )
