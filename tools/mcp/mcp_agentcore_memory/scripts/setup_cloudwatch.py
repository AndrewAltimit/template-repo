#!/usr/bin/env python3
"""
CloudWatch Dashboard and Alarms Setup for AgentCore Memory

Creates:
1. CloudWatch dashboard with operation metrics
2. Alarms for error rates and latency
3. Cost anomaly detection alarm

Usage:
    AWS_PROFILE=agentcore python scripts/setup_cloudwatch.py create
    AWS_PROFILE=agentcore python scripts/setup_cloudwatch.py delete
"""

import argparse
import json
import sys
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

NAMESPACE = "AgentCoreMemory"
DASHBOARD_NAME = "AgentCoreMemory-Operations"
ALARM_PREFIX = "AgentCoreMemory"


def create_dashboard(
    region: str = "us-east-1",
    profile: Optional[str] = None,
) -> None:
    """Create CloudWatch dashboard for memory operations."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("cloudwatch")

    # Dashboard body with operation metrics
    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 1,
                "properties": {"markdown": "# AgentCore Memory Operations Dashboard"},
            },
            # Success rates
            {
                "type": "metric",
                "x": 0,
                "y": 1,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Operation Success Rate",
                    "view": "timeSeries",
                    "stacked": False,
                    "metrics": [
                        [NAMESPACE, "StoreEventSuccess", "Provider", "agentcore", {"stat": "Average", "period": 300}],
                        [NAMESPACE, "StoreFactsSuccess", "Provider", "agentcore", {"stat": "Average", "period": 300}],
                        [
                            NAMESPACE,
                            "SearchMemoriesSuccess",
                            "Provider",
                            "agentcore",
                            {"stat": "Average", "period": 300},
                        ],
                        [NAMESPACE, "ListEventsSuccess", "Provider", "agentcore", {"stat": "Average", "period": 300}],
                    ],
                    "region": region,
                    "yAxis": {"left": {"min": 0, "max": 1}},
                },
            },
            # Latency
            {
                "type": "metric",
                "x": 12,
                "y": 1,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Operation Latency (ms)",
                    "view": "timeSeries",
                    "stacked": False,
                    "metrics": [
                        [NAMESPACE, "StoreEventLatency", "Provider", "agentcore", {"stat": "Average", "period": 300}],
                        [NAMESPACE, "StoreFactsLatency", "Provider", "agentcore", {"stat": "Average", "period": 300}],
                        [
                            NAMESPACE,
                            "SearchMemoriesLatency",
                            "Provider",
                            "agentcore",
                            {"stat": "Average", "period": 300},
                        ],
                        [NAMESPACE, "ListEventsLatency", "Provider", "agentcore", {"stat": "Average", "period": 300}],
                    ],
                    "region": region,
                },
            },
            # Operation counts
            {
                "type": "metric",
                "x": 0,
                "y": 7,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Operation Counts",
                    "view": "timeSeries",
                    "stacked": True,
                    "metrics": [
                        [NAMESPACE, "StoreEventSuccess", "Provider", "agentcore", {"stat": "Sum", "period": 3600}],
                        [NAMESPACE, "StoreFactsSuccess", "Provider", "agentcore", {"stat": "Sum", "period": 3600}],
                        [NAMESPACE, "SearchMemoriesSuccess", "Provider", "agentcore", {"stat": "Sum", "period": 3600}],
                        [NAMESPACE, "ListEventsSuccess", "Provider", "agentcore", {"stat": "Sum", "period": 3600}],
                    ],
                    "region": region,
                },
            },
            # Error counts
            {
                "type": "metric",
                "x": 12,
                "y": 7,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Errors by Type",
                    "view": "timeSeries",
                    "stacked": True,
                    "metrics": [
                        [
                            NAMESPACE,
                            "StoreEventError",
                            "Provider",
                            "agentcore",
                            "ErrorType",
                            "RateLimitError",
                            {"stat": "Sum", "period": 3600},
                        ],
                        [
                            NAMESPACE,
                            "StoreEventError",
                            "Provider",
                            "agentcore",
                            "ErrorType",
                            "ClientError",
                            {"stat": "Sum", "period": 3600},
                        ],
                        [
                            NAMESPACE,
                            "SearchMemoriesError",
                            "Provider",
                            "agentcore",
                            "ErrorType",
                            "ClientError",
                            {"stat": "Sum", "period": 3600},
                        ],
                    ],
                    "region": region,
                },
            },
        ],
    }

    try:
        client.put_dashboard(
            DashboardName=DASHBOARD_NAME,
            DashboardBody=json.dumps(dashboard_body),
        )
        print(f"SUCCESS: Dashboard '{DASHBOARD_NAME}' created")
        dashboard_url = (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#dashboards:name={DASHBOARD_NAME}"
        )
        print(f"  View at: {dashboard_url}")

    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise


def create_alarms(
    region: str = "us-east-1",
    profile: Optional[str] = None,
    sns_topic_arn: Optional[str] = None,
) -> None:
    """Create CloudWatch alarms for memory operations."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("cloudwatch")

    # Define alarms
    alarms = [
        {
            "AlarmName": f"{ALARM_PREFIX}-HighErrorRate",
            "AlarmDescription": "AgentCore Memory error rate exceeds 10%",
            "MetricName": "StoreEventSuccess",
            "Namespace": NAMESPACE,
            "Dimensions": [{"Name": "Provider", "Value": "agentcore"}],
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 3,
            "Threshold": 0.9,
            "ComparisonOperator": "LessThanThreshold",
            "TreatMissingData": "notBreaching",
        },
        {
            "AlarmName": f"{ALARM_PREFIX}-HighLatency",
            "AlarmDescription": "AgentCore Memory latency exceeds 5 seconds",
            "MetricName": "StoreEventLatency",
            "Namespace": NAMESPACE,
            "Dimensions": [{"Name": "Provider", "Value": "agentcore"}],
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 3,
            "Threshold": 5000,  # 5 seconds in ms
            "ComparisonOperator": "GreaterThanThreshold",
            "TreatMissingData": "notBreaching",
        },
    ]

    for alarm_config in alarms:
        try:
            # Add SNS action if provided
            if sns_topic_arn:
                alarm_config["AlarmActions"] = [sns_topic_arn]
                alarm_config["OKActions"] = [sns_topic_arn]

            client.put_metric_alarm(**alarm_config)
            print(f"SUCCESS: Alarm '{alarm_config['AlarmName']}' created")

        except ClientError as e:
            print(f"ERROR creating {alarm_config['AlarmName']}: {e.response['Error']['Code']}")
            raise


def delete_resources(
    region: str = "us-east-1",
    profile: Optional[str] = None,
) -> None:
    """Delete CloudWatch dashboard and alarms."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("cloudwatch")

    # Delete dashboard
    try:
        client.delete_dashboards(DashboardNames=[DASHBOARD_NAME])
        print(f"SUCCESS: Dashboard '{DASHBOARD_NAME}' deleted")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFound":
            print(f"WARNING: Could not delete dashboard: {e.response['Error']['Message']}")

    # Delete alarms
    alarm_names = [
        f"{ALARM_PREFIX}-HighErrorRate",
        f"{ALARM_PREFIX}-HighLatency",
    ]

    try:
        client.delete_alarms(AlarmNames=alarm_names)
        print(f"SUCCESS: Alarms deleted: {alarm_names}")
    except ClientError as e:
        print(f"WARNING: Could not delete alarms: {e.response['Error']['Message']}")


def main():
    parser = argparse.ArgumentParser(
        description="Setup CloudWatch monitoring for AgentCore Memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create dashboard and alarms
  AWS_PROFILE=agentcore python setup_cloudwatch.py create

  # Create with SNS notifications
  AWS_PROFILE=agentcore python setup_cloudwatch.py create --sns-topic arn:aws:sns:us-east-1:123456789:alerts

  # Delete all resources
  AWS_PROFILE=agentcore python setup_cloudwatch.py delete
        """,
    )

    parser.add_argument(
        "action",
        choices=["create", "delete"],
        help="Action to perform",
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
    parser.add_argument(
        "--sns-topic",
        help="SNS topic ARN for alarm notifications",
    )

    args = parser.parse_args()

    if args.action == "create":
        print("Creating CloudWatch dashboard...")
        create_dashboard(region=args.region, profile=args.profile)
        print("\nCreating CloudWatch alarms...")
        create_alarms(region=args.region, profile=args.profile, sns_topic_arn=args.sns_topic)
        print("\nDone!")
    elif args.action == "delete":
        print("Deleting CloudWatch resources...")
        delete_resources(region=args.region, profile=args.profile)
        print("\nDone!")


if __name__ == "__main__":
    main()
