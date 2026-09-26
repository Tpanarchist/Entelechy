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
from entelechy.foundation.types import Mode, ObjectType, OrganRef

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


def test_interoceptive_channels_round_trip_int1() -> None:
    spec = SeedSpec(("R1",), (EYE,), (MIND,), interoceptive_channels=("eye",))
    manifest = manifest_for(spec, "omega-1")
    assert Manifest.from_bytes(manifest.to_bytes()) == manifest
    assert manifest.is_interoceptive("eye")
    assert not manifest.is_interoceptive("mind")


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
    assert provenance.mode is Mode.ORIGIN
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
        (SeedSpec(("R1",), (EYE,), (MIND,), theta_retain=Decimal("1E-200")), "theta_retain"),
        (SeedSpec(("R\udcff",), (EYE,), (MIND,)), "canonical form"),
        (SeedSpec(("R1",), (OrganRef("eye", "\udcff"),), (MIND,)), "canonical form"),
        (
            SeedSpec(("R1",), (EYE,), (MIND,), retention_policy=PolicyRef("fixed\udcff", "1")),
            "canonical form",
        ),
        (
            SeedSpec(("R1",), (EYE,), (MIND,), interoceptive_channels=("ear",)),
            "interoceptive_channels",
        ),
        (
            SeedSpec(("R1",), (EYE,), (MIND,), interoceptive_channels=("eye", "eye")),
            "interoceptive_channels",
        ),
    ],
)
def test_invalid_seeds_are_refused(spec: SeedSpec, message: str) -> None:
    with pytest.raises(SeedError, match=message):
        manifest_for(spec, "omega-1")


@pytest.mark.parametrize(
    "spec",
    [
        SeedSpec((1,), (EYE,), (MIND,)),  # type: ignore[arg-type]
        SeedSpec(("R1",), (EYE,), (OrganRef("mind", 1),)),  # type: ignore[arg-type]
    ],
    ids=["int-relation", "int-version"],
)
def test_a_seed_that_does_not_survive_encoding_is_refused_dev2(spec: SeedSpec) -> None:
    with pytest.raises(SeedError, match="canonical form"):
        manifest_for(spec, "omega-1")
