"""Tests for MockWallet implementation."""

import pytest
from economic_agents.implementations.mock import MockWallet


@pytest.mark.asyncio
async def test_wallet_initialization():
    """Test wallet initializes with correct balance."""
    wallet = MockWallet(initial_balance=100.0)
    balance = await wallet.get_balance()
    assert balance == 100.0
    address = await wallet.get_address()
    assert address.startswith("mock_wallet_")


@pytest.mark.asyncio
async def test_wallet_send_payment():
    """Test sending payment reduces balance."""
    wallet = MockWallet(initial_balance=100.0)

    tx = await wallet.send_payment(to_address="recipient_123", amount=30.0, memo="Test payment")

    balance = await wallet.get_balance()
    assert balance == 70.0
    assert tx.amount == 30.0
    assert tx.to_address == "recipient_123"
    assert tx.status == "confirmed"
    history = await wallet.get_transaction_history()
    assert len(history) == 1


@pytest.mark.asyncio
async def test_wallet_insufficient_balance():
    """Test sending payment with insufficient balance raises error."""
    wallet = MockWallet(initial_balance=50.0)

    with pytest.raises(ValueError, match="Insufficient balance"):
        await wallet.send_payment(to_address="recipient_123", amount=100.0)


@pytest.mark.asyncio
async def test_wallet_negative_payment():
    """Test sending negative amount raises error."""
    wallet = MockWallet(initial_balance=100.0)

    with pytest.raises(ValueError, match="Payment amount must be positive"):
        await wallet.send_payment(to_address="recipient_123", amount=-10.0)


@pytest.mark.asyncio
async def test_wallet_receive_payment():
    """Test receiving payment increases balance."""
    wallet = MockWallet(initial_balance=50.0)

    tx = wallet.receive_payment(from_address="sender_456", amount=25.0, memo="Earnings")

    balance = await wallet.get_balance()
    assert balance == 75.0
    assert tx.amount == 25.0
    assert tx.from_address == "sender_456"
    assert tx.status == "confirmed"


@pytest.mark.asyncio
async def test_wallet_transaction_history():
    """Test transaction history tracks all transactions."""
    wallet = MockWallet(initial_balance=100.0)

    wallet.receive_payment("sender_1", 50.0)
    await wallet.send_payment("recipient_1", 30.0)
    wallet.receive_payment("sender_2", 20.0)

    history = await wallet.get_transaction_history()
    assert len(history) == 3
    balance = await wallet.get_balance()
    assert balance == 140.0


@pytest.mark.asyncio
async def test_wallet_transaction_history_limit():
    """Test transaction history respects limit parameter."""
    wallet = MockWallet(initial_balance=100.0)

    for i in range(10):
        wallet.receive_payment(f"sender_{i}", 10.0)

    history = await wallet.get_transaction_history(limit=5)
    assert len(history) == 5
