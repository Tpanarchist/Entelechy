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
