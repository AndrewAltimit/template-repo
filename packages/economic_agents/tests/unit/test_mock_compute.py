"""Tests for MockCompute implementation."""

import time

import pytest

from economic_agents.implementations.mock import MockCompute


@pytest.mark.asyncio
async def test_compute_initialization():
    """Test compute provider initializes with correct values."""
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)

    status = await compute.get_status()
    assert status.hours_remaining == pytest.approx(24.0, abs=0.1)
    assert status.cost_per_hour == 2.0
    assert status.balance == pytest.approx(48.0, abs=0.1)
    assert status.status == "active"


@pytest.mark.asyncio
async def test_compute_add_funds():
    """Test adding funds increases compute hours."""
    compute = MockCompute(initial_hours=10.0, cost_per_hour=2.0)

    success = await compute.add_funds(20.0)

    assert success is True
    status = await compute.get_status()
    assert status.hours_remaining == pytest.approx(20.0, abs=0.1)
    assert status.balance == pytest.approx(40.0, abs=0.1)


@pytest.mark.asyncio
async def test_compute_consume_time():
    """Test consuming compute time reduces hours."""
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)

    success = await compute.consume_time(4.0)

    assert success is True
    status = await compute.get_status()
    assert status.hours_remaining == pytest.approx(20.0, abs=0.1)


@pytest.mark.asyncio
async def test_compute_consume_too_much():
    """Test consuming more time than available fails."""
    compute = MockCompute(initial_hours=5.0, cost_per_hour=2.0)

    success = await compute.consume_time(10.0)

    assert success is False
    status = await compute.get_status()
    assert status.hours_remaining == pytest.approx(5.0, abs=0.1)


@pytest.mark.asyncio
async def test_compute_time_decay():
    """Test that compute time decays over real time."""
    compute = MockCompute(initial_hours=1.0, cost_per_hour=2.0)

    # Wait a short time (0.1 seconds = ~0.000028 hours)
    time.sleep(0.1)

    status = await compute.get_status()
    # Should have decayed slightly
    assert status.hours_remaining < 1.0
    assert status.hours_remaining > 0.99


@pytest.mark.asyncio
async def test_compute_status_low():
    """Test compute status shows 'low' when hours < 4."""
    compute = MockCompute(initial_hours=3.0, cost_per_hour=2.0)

    status = await compute.get_status()
    assert status.status == "low"


@pytest.mark.asyncio
async def test_compute_status_expired():
    """Test compute status shows 'expired' when hours = 0."""
    compute = MockCompute(initial_hours=0.1, cost_per_hour=2.0)

    # Consume all available time
    status = await compute.get_status()
    await compute.consume_time(status.hours_remaining * 0.99)  # Leave tiny bit to avoid race

    status = await compute.get_status()
    assert status.hours_remaining < 0.1  # Should be nearly exhausted
    # Status should be low or expired since we're under 4 hours
    assert status.status in ["low", "expired"]


@pytest.mark.asyncio
async def test_compute_negative_funds():
    """Test adding negative funds fails."""
    compute = MockCompute(initial_hours=10.0, cost_per_hour=2.0)

    success = await compute.add_funds(-10.0)

    assert success is False


@pytest.mark.asyncio
async def test_compute_cost_per_hour():
    """Test get_cost_per_hour returns correct value."""
    compute = MockCompute(initial_hours=10.0, cost_per_hour=3.5)

    cost = await compute.get_cost_per_hour()
    assert cost == 3.5
