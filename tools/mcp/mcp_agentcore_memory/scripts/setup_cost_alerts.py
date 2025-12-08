#!/usr/bin/env python3
"""
AWS Budgets Setup for AgentCore Memory Cost Alerts

Creates a budget with alerts at $5/month threshold.

Usage:
    AWS_PROFILE=agentcore python scripts/setup_cost_alerts.py create --email your@email.com
    AWS_PROFILE=agentcore python scripts/setup_cost_alerts.py delete
    AWS_PROFILE=agentcore python scripts/setup_cost_alerts.py status
"""

import argparse
import sys
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


BUDGET_NAME = "AgentCoreMemory-Monthly"


def create_budget(
    email: str,
    threshold: float = 5.0,
    region: str = "us-east-1",
    profile: Optional[str] = None,
) -> None:
    """
    Create AWS Budget with cost alerts.

    Args:
        email: Email address for notifications
        threshold: Monthly budget threshold in USD (default: $5)
        region: AWS region
        profile: AWS profile name
    """
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)

    # Get account ID
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    # Budgets API must be called from us-east-1
    budgets = session.client("budgets", region_name="us-east-1")

    budget = {
        "BudgetName": BUDGET_NAME,
        "BudgetLimit": {
            "Amount": str(threshold),
            "Unit": "USD",
        },
        "CostFilters": {
            # Filter to Bedrock AgentCore service
            "Service": ["Amazon Bedrock"],
        },
        "CostTypes": {
            "IncludeTax": True,
            "IncludeSubscription": True,
            "UseBlended": False,
            "IncludeRefund": False,
            "IncludeCredit": False,
            "IncludeUpfront": True,
            "IncludeRecurring": True,
            "IncludeOtherSubscription": True,
            "IncludeSupport": False,
            "IncludeDiscount": True,
            "UseAmortized": False,
        },
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
    }

    # Notifications at 50%, 80%, 100%, and 150% of threshold
    notifications_with_subscribers = [
        {
            "Notification": {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 50.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {
                    "SubscriptionType": "EMAIL",
                    "Address": email,
                }
            ],
        },
        {
            "Notification": {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 80.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {
                    "SubscriptionType": "EMAIL",
                    "Address": email,
                }
            ],
        },
        {
            "Notification": {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 100.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {
                    "SubscriptionType": "EMAIL",
                    "Address": email,
                }
            ],
        },
        {
            "Notification": {
                "NotificationType": "FORECASTED",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 100.0,
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {
                    "SubscriptionType": "EMAIL",
                    "Address": email,
                }
            ],
        },
    ]

    try:
        budgets.create_budget(
            AccountId=account_id,
            Budget=budget,
            NotificationsWithSubscribers=notifications_with_subscribers,
        )

        print(f"SUCCESS: Budget '{BUDGET_NAME}' created")
        print(f"  Threshold: ${threshold}/month")
        print(f"  Notifications: {email}")
        print("  Alerts at: 50%, 80%, 100% actual + 100% forecasted")
        print()
        print("View at: https://console.aws.amazon.com/billing/home#/budgets")

    except ClientError as e:
        if e.response["Error"]["Code"] == "DuplicateRecordException":
            print(f"Budget '{BUDGET_NAME}' already exists. Use 'delete' first to recreate.")
        else:
            print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
            raise


def delete_budget(
    region: str = "us-east-1",
    profile: Optional[str] = None,
) -> None:
    """Delete the AgentCore Memory budget."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)

    # Get account ID
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    budgets = session.client("budgets", region_name="us-east-1")

    try:
        budgets.delete_budget(
            AccountId=account_id,
            BudgetName=BUDGET_NAME,
        )
        print(f"SUCCESS: Budget '{BUDGET_NAME}' deleted")

    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            print(f"Budget '{BUDGET_NAME}' not found")
        else:
            print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
            raise


def get_budget_status(
    region: str = "us-east-1",
    profile: Optional[str] = None,
) -> None:
    """Get current budget status."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)

    # Get account ID
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    budgets = session.client("budgets", region_name="us-east-1")

    try:
        response = budgets.describe_budget(
            AccountId=account_id,
            BudgetName=BUDGET_NAME,
        )

        budget = response["Budget"]
        limit = float(budget["BudgetLimit"]["Amount"])

        # Get actual spend
        actual = budget.get("CalculatedSpend", {}).get("ActualSpend", {})
        actual_amount = float(actual.get("Amount", 0))

        forecasted = budget.get("CalculatedSpend", {}).get("ForecastedSpend", {})
        forecasted_amount = float(forecasted.get("Amount", 0))

        print(f"Budget: {BUDGET_NAME}")
        print(f"  Limit: ${limit:.2f}/month")
        print(f"  Actual: ${actual_amount:.2f} ({actual_amount/limit*100:.1f}%)")
        print(f"  Forecasted: ${forecasted_amount:.2f} ({forecasted_amount/limit*100:.1f}%)")
        print(f"  Time Unit: {budget['TimeUnit']}")

    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            print(f"Budget '{BUDGET_NAME}' not found. Create it first.")
        else:
            print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Setup AWS Budget alerts for AgentCore Memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create budget with $5/month threshold
  AWS_PROFILE=agentcore python setup_cost_alerts.py create --email your@email.com

  # Create with custom threshold
  AWS_PROFILE=agentcore python setup_cost_alerts.py create --email your@email.com --threshold 10

  # Check current status
  AWS_PROFILE=agentcore python setup_cost_alerts.py status

  # Delete budget
  AWS_PROFILE=agentcore python setup_cost_alerts.py delete
        """,
    )

    parser.add_argument(
        "action",
        choices=["create", "delete", "status"],
        help="Action to perform",
    )
    parser.add_argument(
        "--email",
        help="Email for notifications (required for create)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="Monthly budget threshold in USD (default: 5.0)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name",
    )

    args = parser.parse_args()

    if args.action == "create":
        if not args.email:
            print("ERROR: --email is required for create action")
            sys.exit(1)
        create_budget(
            email=args.email,
            threshold=args.threshold,
            region=args.region,
            profile=args.profile,
        )
    elif args.action == "delete":
        delete_budget(region=args.region, profile=args.profile)
    elif args.action == "status":
        get_budget_status(region=args.region, profile=args.profile)


if __name__ == "__main__":
    main()
