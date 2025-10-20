"""Wallet API microservice.

Provides REST API for wallet operations:
- Check balance
- Execute transactions
- Get transaction history
"""

from datetime import datetime
from typing import Dict

from economic_agents.api.auth import verify_api_key
from economic_agents.api.models import (
    ErrorResponse,
    Transaction,
    TransactionHistory,
    TransactionRequest,
    WalletBalance,
)
from economic_agents.api.rate_limit import check_rate_limit
from economic_agents.implementations.mock import MockWallet
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Create FastAPI app
app = FastAPI(
    title="Wallet API",
    description="Financial transaction and balance management service",
    version="1.0.0",
)

# Store wallet instances per agent
wallets: Dict[str, MockWallet] = {}


def get_wallet(agent_id: str) -> MockWallet:
    """Get or create wallet for agent.

    Args:
        agent_id: Agent ID

    Returns:
        Wallet instance for the agent
    """
    if agent_id not in wallets:
        # Create new wallet with default balance
        wallets[agent_id] = MockWallet(initial_balance=100.0)
    return wallets[agent_id]


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "wallet", "timestamp": datetime.now().isoformat()}


@app.get("/balance", response_model=WalletBalance)
async def get_balance(
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Get current wallet balance.

    Args:
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Current balance
    """
    wallet = get_wallet(agent_id)
    return WalletBalance(balance=wallet.balance, agent_id=agent_id)


@app.post("/transact", response_model=Transaction)
async def execute_transaction(
    request: TransactionRequest,
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Execute a transaction.

    Args:
        request: Transaction details
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Transaction record

    Raises:
        HTTPException: If transaction fails (e.g., insufficient funds)
    """
    wallet = get_wallet(agent_id)

    try:
        # Execute transaction
        if request.amount >= 0:
            wallet.deposit(request.amount, request.purpose)
            transaction_type = "earning"
        else:
            wallet.withdraw(abs(request.amount), request.purpose)
            transaction_type = "expense"

        # Get last transaction
        if wallet.transactions:
            last_tx = wallet.transactions[-1]
            return Transaction(
                timestamp=last_tx["timestamp"],
                type=transaction_type,
                amount=request.amount,
                balance_after=last_tx["balance_after"],
                purpose=request.purpose,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Transaction executed but not recorded",
            )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/transactions", response_model=TransactionHistory)
async def get_transactions(
    limit: int = 100,
    offset: int = 0,
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Get transaction history.

    Args:
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Transaction history
    """
    wallet = get_wallet(agent_id)

    # Get transactions with pagination
    all_transactions = wallet.transactions
    paginated = all_transactions[offset : offset + limit]

    # Convert to Transaction models
    transactions = [
        Transaction(
            timestamp=tx["timestamp"],
            type=tx["type"],
            amount=tx["amount"],
            balance_after=tx["balance_after"],
            purpose=tx["purpose"],
        )
        for tx in paginated
    ]

    return TransactionHistory(transactions=transactions, total_count=len(all_transactions))


@app.post("/initialize")
async def initialize_wallet(
    initial_balance: float = 100.0,
    agent_id: str = Depends(verify_api_key),
):
    """Initialize or reset wallet with specific balance.

    Args:
        initial_balance: Initial balance to set
        agent_id: Agent ID from API key

    Returns:
        Wallet balance
    """
    wallets[agent_id] = MockWallet(initial_balance=initial_balance)
    return WalletBalance(balance=initial_balance, agent_id=agent_id)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with standard error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error="WalletError", message=exc.detail).dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
