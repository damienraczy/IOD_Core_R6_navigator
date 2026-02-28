import pytest
from pathlib import Path

from r6_navigator.db.database import get_engine, get_session_factory, init_db
from r6_navigator.db.models import Capacity, CapacityTranslation, Coaching


@pytest.fixture
def session():
    engine = get_engine(Path(":memory:"))
    init_db(engine, seed_capacities=False)
    factory = get_session_factory(engine)
    with factory() as s:
        yield s


@pytest.fixture
def session_with_capacities():
    """Session with 3 synthetic capacities: S1a, O1a, I1a (one per level, axis 1, pole a)."""
    engine = get_engine(Path(":memory:"))
    init_db(engine, seed_capacities=False)
    factory = get_session_factory(engine)
    with factory() as s:
        for capacity_id in ("S1a", "O1a", "I1a"):
            level_code = capacity_id[0]
            axis_number = int(capacity_id[1])
            pole_code = capacity_id[2]
            s.add(Capacity(
                capacity_id=capacity_id,
                level_code=level_code,
                axis_number=axis_number,
                pole_code=pole_code,
                is_canonical=True,
            ))
            s.add(CapacityTranslation(
                capacity_id=capacity_id,
                lang="fr",
                label=f"capacity {capacity_id}",
            ))
            s.add(Coaching(capacity_id=capacity_id))
        s.commit()
        yield s
