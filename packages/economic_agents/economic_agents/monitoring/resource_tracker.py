"""Resource tracker for monitoring capital, compute, and time allocation."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Transaction:
    """Represents a financial transaction."""

    id: str
    timestamp: datetime
    transaction_type: str  # "earning", "expense", "investment", "transfer"
    amount: float
    from_account: str
    to_account: str
    purpose: str
    balance_after: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputeUsage:
    """Represents compute resource usage."""

    timestamp: datetime
    hours_used: float
    purpose: str  # "task_work", "company_work", "idle"
    cost: float
    hours_remaining: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeAllocation:
    """Represents time allocation decision."""

    timestamp: datetime
    task_work_hours: float
    company_work_hours: float
    total_hours: float
    reasoning: str


@dataclass
class ResourceReport:
    """Summary report of resource usage."""

    period_start: datetime
    period_end: datetime
    total_earnings: float
    total_expenses: float
    net_cashflow: float
    compute_hours_used: float
    compute_cost: float
    task_work_percentage: float
    company_work_percentage: float
    transaction_count: int
    final_balance: float
    final_compute_hours: float


class ResourceTracker:
    """Tracks all resource flows: capital, compute, and time allocation."""

    def __init__(self, log_dir: str | None = None, enable_file_logging: bool = True):
        """Initialize resource tracker.

        Args:
            log_dir: Directory to store resource logs
            enable_file_logging: Whether to write logs to files (default: True)
        """
        self.enable_file_logging = enable_file_logging
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/resources")
        self._logging_available = False

        # Try to create log directory
        if self.enable_file_logging:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                # Test write access
                test_file = self.log_dir / ".write_test"
                test_file.touch()
                test_file.unlink()
                self._logging_available = True
            except (OSError, PermissionError) as e:
                import warnings

                warnings.warn(
                    f"Cannot write to log directory {self.log_dir}: {e}. "
                    "File logging disabled. Data will still be tracked in memory.",
                    RuntimeWarning,
                )
                self._logging_available = False

        self.transactions: List[Transaction] = []
        self.compute_usage: List[ComputeUsage] = []
        self.time_allocations: List[TimeAllocation] = []

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def track_transaction(
        self,
        transaction_type: str,
        amount: float,
        from_account: str,
        to_account: str,
        purpose: str,
        balance_after: float,
        metadata: Dict[str, Any] | None = None,
    ) -> Transaction:
        """Track a financial transaction.

        Args:
            transaction_type: Type of transaction
            amount: Transaction amount
            from_account: Source account
            to_account: Destination account
            purpose: Purpose of transaction
            balance_after: Balance after transaction
            metadata: Additional transaction data

        Returns:
            Transaction object
        """
        transaction = Transaction(
            id=f"{self.session_id}_tx_{len(self.transactions):04d}",
            timestamp=datetime.now(),
            transaction_type=transaction_type,
            amount=amount,
            from_account=from_account,
            to_account=to_account,
            purpose=purpose,
            balance_after=balance_after,
            metadata=metadata or {},
        )

        self.transactions.append(transaction)
        self._save_transaction(transaction)

        return transaction

    def track_compute_usage(
        self,
        hours_used: float,
        purpose: str,
        cost: float,
        hours_remaining: float,
        metadata: Dict[str, Any] | None = None,
    ) -> ComputeUsage:
        """Track compute resource usage.

        Args:
            hours_used: Hours of compute used
            purpose: Purpose of usage
            cost: Cost of usage
            hours_remaining: Remaining compute hours
            metadata: Additional usage data

        Returns:
            ComputeUsage object
        """
        usage = ComputeUsage(
            timestamp=datetime.now(),
            hours_used=hours_used,
            purpose=purpose,
            cost=cost,
            hours_remaining=hours_remaining,
            metadata=metadata or {},
        )

        self.compute_usage.append(usage)
        self._save_compute_usage(usage)

        return usage

    def track_time_allocation(self, task_work_hours: float, company_work_hours: float, reasoning: str) -> TimeAllocation:
        """Track time allocation decision.

        Args:
            task_work_hours: Hours allocated to task work
            company_work_hours: Hours allocated to company work
            reasoning: Reasoning for allocation

        Returns:
            TimeAllocation object
        """
        allocation = TimeAllocation(
            timestamp=datetime.now(),
            task_work_hours=task_work_hours,
            company_work_hours=company_work_hours,
            total_hours=task_work_hours + company_work_hours,
            reasoning=reasoning,
        )

        self.time_allocations.append(allocation)
        self._save_time_allocation(allocation)

        return allocation

    def get_resource_report(self, period_start: datetime | None = None, period_end: datetime | None = None) -> ResourceReport:
        """Generate resource usage report for a period.

        Args:
            period_start: Start of reporting period (None = beginning)
            period_end: End of reporting period (None = now)

        Returns:
            ResourceReport with summary statistics
        """
        # Default to all time if not specified
        if not period_start and self.transactions:
            period_start = self.transactions[0].timestamp
        elif not period_start:
            period_start = datetime.now()

        if not period_end:
            period_end = datetime.now()

        # Filter transactions to period
        period_transactions = [tx for tx in self.transactions if period_start <= tx.timestamp <= period_end]

        # Calculate financial metrics
        earnings = sum(tx.amount for tx in period_transactions if tx.transaction_type == "earning")
        expenses = sum(tx.amount for tx in period_transactions if tx.transaction_type == "expense")

        # Filter compute usage to period
        period_compute = [cu for cu in self.compute_usage if period_start <= cu.timestamp <= period_end]

        total_compute_hours = sum(cu.hours_used for cu in period_compute)
        total_compute_cost = sum(cu.cost for cu in period_compute)

        # Filter time allocations to period
        period_allocations = [ta for ta in self.time_allocations if period_start <= ta.timestamp <= period_end]

        total_task_hours = sum(ta.task_work_hours for ta in period_allocations)
        total_company_hours = sum(ta.company_work_hours for ta in period_allocations)
        total_allocated_hours = total_task_hours + total_company_hours

        task_percentage = (total_task_hours / total_allocated_hours * 100) if total_allocated_hours > 0 else 0
        company_percentage = (total_company_hours / total_allocated_hours * 100) if total_allocated_hours > 0 else 0

        # Get final balances
        final_balance = period_transactions[-1].balance_after if period_transactions else 0.0
        final_compute_hours = period_compute[-1].hours_remaining if period_compute else 0.0

        return ResourceReport(
            period_start=period_start,
            period_end=period_end,
            total_earnings=earnings,
            total_expenses=expenses,
            net_cashflow=earnings - expenses,
            compute_hours_used=total_compute_hours,
            compute_cost=total_compute_cost,
            task_work_percentage=task_percentage,
            company_work_percentage=company_percentage,
            transaction_count=len(period_transactions),
            final_balance=final_balance,
            final_compute_hours=final_compute_hours,
        )

    def get_transaction_history(self, limit: int = 100, transaction_type: str | None = None) -> List[Transaction]:
        """Get recent transaction history.

        Args:
            limit: Maximum number of transactions to return
            transaction_type: Optional filter by transaction type

        Returns:
            List of transactions
        """
        transactions = self.transactions

        if transaction_type:
            transactions = [tx for tx in transactions if tx.transaction_type == transaction_type]

        return transactions[-limit:]

    def _save_transaction(self, transaction: Transaction):
        """Save transaction to file for persistence."""
        if not self._logging_available:
            return

        try:
            log_file = self.log_dir / f"transactions_{self.session_id}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                record = {
                    "id": transaction.id,
                    "timestamp": transaction.timestamp.isoformat(),
                    "type": transaction.transaction_type,
                    "amount": transaction.amount,
                    "from": transaction.from_account,
                    "to": transaction.to_account,
                    "purpose": transaction.purpose,
                    "balance_after": transaction.balance_after,
                    "metadata": transaction.metadata,
                }
                f.write(json.dumps(record) + "\n")
        except (OSError, PermissionError):
            # Silently fail - data is still tracked in memory
            pass

    def _save_compute_usage(self, usage: ComputeUsage):
        """Save compute usage to file for persistence."""
        if not self._logging_available:
            return

        try:
            log_file = self.log_dir / f"compute_{self.session_id}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                record = {
                    "timestamp": usage.timestamp.isoformat(),
                    "hours_used": usage.hours_used,
                    "purpose": usage.purpose,
                    "cost": usage.cost,
                    "hours_remaining": usage.hours_remaining,
                    "metadata": usage.metadata,
                }
                f.write(json.dumps(record) + "\n")
        except (OSError, PermissionError):
            # Silently fail - data is still tracked in memory
            pass

    def _save_time_allocation(self, allocation: TimeAllocation):
        """Save time allocation to file for persistence."""
        if not self._logging_available:
            return

        try:
            log_file = self.log_dir / f"time_allocations_{self.session_id}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                record = {
                    "timestamp": allocation.timestamp.isoformat(),
                    "task_work_hours": allocation.task_work_hours,
                    "company_work_hours": allocation.company_work_hours,
                    "total_hours": allocation.total_hours,
                    "reasoning": allocation.reasoning,
                }
                f.write(json.dumps(record) + "\n")
        except (OSError, PermissionError):
            # Silently fail - data is still tracked in memory
            pass

    def export_to_json(self, output_dir: str):
        """Export all resource data to JSON files.

        Args:
            output_dir: Directory to save export files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export transactions
        transactions_data = [
            {
                "id": tx.id,
                "timestamp": tx.timestamp.isoformat(),
                "type": tx.transaction_type,
                "amount": tx.amount,
                "from": tx.from_account,
                "to": tx.to_account,
                "purpose": tx.purpose,
                "balance_after": tx.balance_after,
                "metadata": tx.metadata,
            }
            for tx in self.transactions
        ]

        with open(output_path / "transactions.json", "w", encoding="utf-8") as f:
            json.dump(transactions_data, f, indent=2)

        # Export compute usage
        compute_data = [
            {
                "timestamp": cu.timestamp.isoformat(),
                "hours_used": cu.hours_used,
                "purpose": cu.purpose,
                "cost": cu.cost,
                "hours_remaining": cu.hours_remaining,
                "metadata": cu.metadata,
            }
            for cu in self.compute_usage
        ]

        with open(output_path / "compute_usage.json", "w", encoding="utf-8") as f:
            json.dump(compute_data, f, indent=2)

        # Export time allocations
        allocation_data = [
            {
                "timestamp": ta.timestamp.isoformat(),
                "task_work_hours": ta.task_work_hours,
                "company_work_hours": ta.company_work_hours,
                "total_hours": ta.total_hours,
                "reasoning": ta.reasoning,
            }
            for ta in self.time_allocations
        ]

        with open(output_path / "time_allocations.json", "w", encoding="utf-8") as f:
            json.dump(allocation_data, f, indent=2)
