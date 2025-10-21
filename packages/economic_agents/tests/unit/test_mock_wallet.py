"""Tests for MockWallet implementation."""

import pytest
from economic_agents.implementations.mock import MockWallet


def test_wallet_initialization():
    """Test wallet initializes with correct balance."""
    wallet = MockWallet(initial_balance=100.0)
    assert wallet.get_balance() == 100.0
    assert wallet.get_address().startswith("mock_wallet_")


def test_wallet_send_payment():
    """Test sending payment reduces balance."""
    wallet = MockWallet(initial_balance=100.0)

    tx = wallet.send_payment(to_address="recipient_123", amount=30.0, memo="Test payment")

    assert wallet.get_balance() == 70.0
    assert tx.amount == 30.0
    assert tx.to_address == "recipient_123"
    assert tx.status == "confirmed"
    assert len(wallet.get_transaction_history()) == 1


def test_wallet_insufficient_balance():
    """Test sending payment with insufficient balance raises error."""
    wallet = MockWallet(initial_balance=50.0)

    with pytest.raises(ValueError, match="Insufficient balance"):
        wallet.send_payment(to_address="recipient_123", amount=100.0)


def test_wallet_negative_payment():
    """Test sending negative amount raises error."""
    wallet = MockWallet(initial_balance=100.0)

    with pytest.raises(ValueError, match="Payment amount must be positive"):
        wallet.send_payment(to_address="recipient_123", amount=-10.0)


def test_wallet_receive_payment():
    """Test receiving payment increases balance."""
    wallet = MockWallet(initial_balance=50.0)

    tx = wallet.receive_payment(from_address="sender_456", amount=25.0, memo="Earnings")

    assert wallet.get_balance() == 75.0
    assert tx.amount == 25.0
    assert tx.from_address == "sender_456"
    assert tx.status == "confirmed"


def test_wallet_transaction_history():
    """Test transaction history tracks all transactions."""
    wallet = MockWallet(initial_balance=100.0)

    wallet.receive_payment("sender_1", 50.0)
    wallet.send_payment("recipient_1", 30.0)
    wallet.receive_payment("sender_2", 20.0)

    history = wallet.get_transaction_history()
    assert len(history) == 3
    assert wallet.get_balance() == 140.0


def test_wallet_transaction_history_limit():
    """Test transaction history respects limit parameter."""
    wallet = MockWallet(initial_balance=100.0)

    for i in range(10):
        wallet.receive_payment(f"sender_{i}", 10.0)

    history = wallet.get_transaction_history(limit=5)
    assert len(history) == 5
