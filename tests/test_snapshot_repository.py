from datetime import datetime, timedelta

import pytest

from engine.models import Snapshot
from repositories.in_memory_snapshot_repository import InMemorySnapshotRepository

BASE = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def make_snapshot(offset_days=0, snapshot_id=None, portfolio_id="demo", **overrides):
    defaults = dict(
        id=snapshot_id or f"snap-{offset_days}",
        portfolio_id=portfolio_id,
        timestamp=BASE + timedelta(days=offset_days),
        portfolio_value=1000.0 + offset_days,
        cash_balance=100.0,
        invested=900.0,
        base_currency="USD",
    )
    defaults.update(overrides)
    return Snapshot(**defaults)


# --- Load / save (round trip) -------------------------------------------------

@pytest.mark.asyncio
async def test_save_then_load_returns_the_snapshot():
    repo = InMemorySnapshotRepository()
    snap = make_snapshot()

    await repo.async_append_snapshot(snap)
    result = await repo.async_get_snapshots("demo")

    assert result == [snap]


@pytest.mark.asyncio
async def test_load_for_unknown_portfolio_returns_empty_list():
    repo = InMemorySnapshotRepository()
    result = await repo.async_get_snapshots("does_not_exist")
    assert result == []


@pytest.mark.asyncio
async def test_snapshots_scoped_per_portfolio():
    repo = InMemorySnapshotRepository()
    await repo.async_append_snapshot(make_snapshot(portfolio_id="a", snapshot_id="s1"))
    await repo.async_append_snapshot(make_snapshot(portfolio_id="b", snapshot_id="s2"))

    a_snapshots = await repo.async_get_snapshots("a")
    b_snapshots = await repo.async_get_snapshots("b")

    assert len(a_snapshots) == 1
    assert len(b_snapshots) == 1
    assert a_snapshots[0].id == "s1"
    assert b_snapshots[0].id == "s2"


# --- Ordering -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshots_returned_in_chronological_order_regardless_of_write_order():
    repo = InMemorySnapshotRepository()
    later = make_snapshot(offset_days=10, snapshot_id="later")
    earlier = make_snapshot(offset_days=0, snapshot_id="earlier")

    # written out of order
    await repo.async_append_snapshot(later)
    await repo.async_append_snapshot(earlier)

    result = await repo.async_get_snapshots("demo")
    assert [s.id for s in result] == ["earlier", "later"]


@pytest.mark.asyncio
async def test_equal_timestamps_broken_by_id_deterministically():
    repo = InMemorySnapshotRepository()
    same_time = BASE
    snap_b = make_snapshot(snapshot_id="b", timestamp=same_time)
    snap_a = make_snapshot(snapshot_id="a", timestamp=same_time)

    await repo.async_append_snapshot(snap_b)
    await repo.async_append_snapshot(snap_a)

    result = await repo.async_get_snapshots("demo")
    assert [s.id for s in result] == ["a", "b"]  # id used as deterministic tiebreak


# --- Duplicate handling ----------------------------------------------------------

@pytest.mark.asyncio
async def test_appending_duplicate_id_raises():
    repo = InMemorySnapshotRepository()
    snap = make_snapshot(snapshot_id="dup")

    await repo.async_append_snapshot(snap)
    with pytest.raises(ValueError, match="duplicate snapshot id"):
        await repo.async_append_snapshot(make_snapshot(snapshot_id="dup", offset_days=5))


@pytest.mark.asyncio
async def test_same_id_allowed_across_different_portfolios():
    """The uniqueness constraint is per-portfolio, not global - two
    different portfolios legitimately generating a snapshot with
    coincidentally the same id (e.g. if a future id scheme weren't
    globally unique) shouldn't collide with each other.
    """
    repo = InMemorySnapshotRepository()
    await repo.async_append_snapshot(make_snapshot(portfolio_id="a", snapshot_id="s1"))
    # should not raise - different portfolio_id
    await repo.async_append_snapshot(make_snapshot(portfolio_id="b", snapshot_id="s1"))

    assert len(await repo.async_get_snapshots("a")) == 1
    assert len(await repo.async_get_snapshots("b")) == 1


# --- Migration safety (via Snapshot.from_dict, exercised through a repository-shaped flow) ---

@pytest.mark.asyncio
async def test_repository_round_trip_survives_dict_serialization():
    """Simulates what a real persisted-and-reloaded repository does:
    snapshot -> dict -> snapshot, then stored/retrieved - the shape a
    Store-backed repository will actually exercise in tests_ha/.
    """
    repo = InMemorySnapshotRepository()
    original = make_snapshot()

    serialized = original.to_dict()
    restored = Snapshot.from_dict(serialized)
    await repo.async_append_snapshot(restored)

    result = await repo.async_get_snapshots("demo")
    assert result == [original]


@pytest.mark.asyncio
async def test_repository_tolerates_snapshot_from_dict_with_missing_optional_holdings():
    repo = InMemorySnapshotRepository()
    data = make_snapshot().to_dict()
    del data["holdings"]  # older-schema dict, per Snapshot.from_dict's migration-safety contract

    restored = Snapshot.from_dict(data)
    await repo.async_append_snapshot(restored)

    result = await repo.async_get_snapshots("demo")
    assert result[0].holdings == []
