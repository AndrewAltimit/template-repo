#!/usr/bin/env python3
"""
Athena Setup for CloudTrail Query Analysis

Creates Athena table and provides useful queries for analyzing
AgentCore Memory API calls via CloudTrail logs.

Prerequisites:
1. CloudTrail enabled for the AWS account
2. CloudTrail logs stored in S3
3. Athena workgroup configured

Usage:
    AWS_PROFILE=agentcore python scripts/setup_athena.py setup --s3-bucket your-cloudtrail-bucket
    AWS_PROFILE=agentcore python scripts/setup_athena.py queries
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


# Athena database and table names
DATABASE = "agentcore_audit"
TABLE = "cloudtrail_logs"


def create_database(
    region: str = "us-east-1",
    profile: Optional[str] = None,
    workgroup: str = "primary",
    output_location: Optional[str] = None,
) -> None:
    """Create Athena database for CloudTrail analysis."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("athena")

    query = f"CREATE DATABASE IF NOT EXISTS {DATABASE}"

    try:
        response = client.start_query_execution(
            QueryString=query,
            ResultConfiguration={
                "OutputLocation": output_location or f"s3://aws-athena-query-results-{region}/",
            },
            WorkGroup=workgroup,
        )
        print(f"SUCCESS: Database creation started: {response['QueryExecutionId']}")

    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise


def create_table(
    s3_bucket: str,
    region: str = "us-east-1",
    profile: Optional[str] = None,
    workgroup: str = "primary",
    output_location: Optional[str] = None,
    account_id: Optional[str] = None,
) -> None:
    """Create Athena table for CloudTrail logs."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("athena")

    # Get account ID if not provided
    if not account_id:
        sts = session.client("sts")
        account_id = sts.get_caller_identity()["Account"]

    # CloudTrail table DDL
    query = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.{TABLE} (
        eventVersion STRING,
        userIdentity STRUCT<
            type: STRING,
            principalId: STRING,
            arn: STRING,
            accountId: STRING,
            invokedBy: STRING,
            accessKeyId: STRING,
            userName: STRING,
            sessionContext: STRUCT<
                attributes: STRUCT<
                    mfaAuthenticated: STRING,
                    creationDate: STRING
                >,
                sessionIssuer: STRUCT<
                    type: STRING,
                    principalId: STRING,
                    arn: STRING,
                    accountId: STRING,
                    userName: STRING
                >
            >
        >,
        eventTime STRING,
        eventSource STRING,
        eventName STRING,
        awsRegion STRING,
        sourceIPAddress STRING,
        userAgent STRING,
        errorCode STRING,
        errorMessage STRING,
        requestParameters STRING,
        responseElements STRING,
        additionalEventData STRING,
        requestId STRING,
        eventId STRING,
        readOnly STRING,
        resources ARRAY<STRUCT<
            arn: STRING,
            accountId: STRING,
            type: STRING
        >>,
        eventType STRING,
        apiVersion STRING,
        recipientAccountId STRING,
        serviceEventDetails STRING,
        sharedEventID STRING,
        vpcEndpointId STRING
    )
    PARTITIONED BY (
        region STRING,
        year STRING,
        month STRING,
        day STRING
    )
    ROW FORMAT SERDE 'com.amazon.emr.hive.serde.CloudTrailSerde'
    STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
    OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
    LOCATION 's3://{s3_bucket}/AWSLogs/{account_id}/CloudTrail/'
    TBLPROPERTIES (
        'projection.enabled' = 'true',
        'projection.region.type' = 'enum',
        'projection.region.values' = '{region}',
        'projection.year.type' = 'integer',
        'projection.year.range' = '2024,2030',
        'projection.month.type' = 'integer',
        'projection.month.range' = '1,12',
        'projection.month.digits' = '2',
        'projection.day.type' = 'integer',
        'projection.day.range' = '1,31',
        'projection.day.digits' = '2',
        'storage.location.template' = 's3://{s3_bucket}/AWSLogs/{account_id}/CloudTrail/'
            '${{region}}/${{year}}/${{month}}/${{day}}'
    )
    """

    try:
        response = client.start_query_execution(
            QueryString=query,
            ResultConfiguration={
                "OutputLocation": output_location or f"s3://aws-athena-query-results-{region}/",
            },
            WorkGroup=workgroup,
        )
        print(f"SUCCESS: Table creation started: {response['QueryExecutionId']}")
        print(f"  Table: {DATABASE}.{TABLE}")
        print(f"  S3 Location: s3://{s3_bucket}/AWSLogs/{account_id}/CloudTrail/")

    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise


def print_queries() -> None:
    """Print useful Athena queries for AgentCore Memory analysis."""
    queries = """
================================================================================
ATHENA QUERIES FOR AGENTCORE MEMORY ANALYSIS
================================================================================

-- 1. All AgentCore Memory API Calls (Last 7 Days)
SELECT
    eventTime,
    eventName,
    userIdentity.arn AS caller_arn,
    sourceIPAddress,
    errorCode,
    errorMessage
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventTime >= date_format(date_add('day', -7, current_date), '%Y-%m-%dT00:00:00Z')
ORDER BY eventTime DESC
LIMIT 100;

-- 2. API Call Volume by Operation (Last 30 Days)
SELECT
    eventName,
    COUNT(*) as call_count,
    COUNT(errorCode) as error_count,
    ROUND(COUNT(errorCode) * 100.0 / COUNT(*), 2) as error_rate_pct
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventTime >= date_format(date_add('day', -30, current_date), '%Y-%m-%dT00:00:00Z')
GROUP BY eventName
ORDER BY call_count DESC;

-- 3. Error Analysis
SELECT
    eventName,
    errorCode,
    errorMessage,
    COUNT(*) as occurrences
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND errorCode IS NOT NULL
    AND eventTime >= date_format(date_add('day', -7, current_date), '%Y-%m-%dT00:00:00Z')
GROUP BY eventName, errorCode, errorMessage
ORDER BY occurrences DESC;

-- 4. Rate Limiting Events (ThrottlingException)
SELECT
    eventTime,
    eventName,
    userIdentity.arn AS caller_arn,
    json_extract_scalar(requestParameters, '$.actorId') as actor_id,
    json_extract_scalar(requestParameters, '$.sessionId') as session_id
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND errorCode = 'ThrottlingException'
    AND eventTime >= date_format(date_add('day', -7, current_date), '%Y-%m-%dT00:00:00Z')
ORDER BY eventTime DESC;

-- 5. Memory Operations by Actor (Last 7 Days)
SELECT
    json_extract_scalar(requestParameters, '$.actorId') as actor_id,
    eventName,
    COUNT(*) as call_count
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventName IN ('CreateEvent', 'BatchCreateMemoryRecords', 'RetrieveMemoryRecords')
    AND eventTime >= date_format(date_add('day', -7, current_date), '%Y-%m-%dT00:00:00Z')
GROUP BY json_extract_scalar(requestParameters, '$.actorId'), eventName
ORDER BY call_count DESC;

-- 6. Daily API Usage Trend
SELECT
    date(from_iso8601_timestamp(eventTime)) as day,
    eventName,
    COUNT(*) as calls
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventTime >= date_format(date_add('day', -30, current_date), '%Y-%m-%dT00:00:00Z')
GROUP BY date(from_iso8601_timestamp(eventTime)), eventName
ORDER BY day DESC, calls DESC;

-- 7. Unique Callers and Sessions
SELECT
    COUNT(DISTINCT userIdentity.arn) as unique_callers,
    COUNT(DISTINCT json_extract_scalar(requestParameters, '$.actorId')) as unique_actors,
    COUNT(DISTINCT json_extract_scalar(requestParameters, '$.sessionId')) as unique_sessions
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventTime >= date_format(date_add('day', -30, current_date), '%Y-%m-%dT00:00:00Z');

-- 8. Namespace Usage Analysis
SELECT
    json_extract_scalar(requestParameters, '$.namespace') as namespace,
    eventName,
    COUNT(*) as call_count
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND json_extract_scalar(requestParameters, '$.namespace') IS NOT NULL
    AND eventTime >= date_format(date_add('day', -30, current_date), '%Y-%m-%dT00:00:00Z')
GROUP BY json_extract_scalar(requestParameters, '$.namespace'), eventName
ORDER BY call_count DESC;

================================================================================
NOTES:
- Replace date ranges as needed
- eventSource may vary by region/service version
- Add WHERE clauses for specific memory IDs if needed
================================================================================
"""
    print(queries)


def main():
    parser = argparse.ArgumentParser(
        description="Setup Athena for CloudTrail analysis of AgentCore Memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup database and table
  AWS_PROFILE=agentcore python setup_athena.py setup --s3-bucket your-cloudtrail-bucket

  # Print useful queries
  python setup_athena.py queries
        """,
    )

    parser.add_argument(
        "action",
        choices=["setup", "queries"],
        help="Action to perform",
    )
    parser.add_argument(
        "--s3-bucket",
        help="S3 bucket containing CloudTrail logs (required for setup)",
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
        "--workgroup",
        default="primary",
        help="Athena workgroup (default: primary)",
    )
    parser.add_argument(
        "--output-location",
        help="S3 location for query results",
    )
    parser.add_argument(
        "--account-id",
        help="AWS account ID (auto-detected if not provided)",
    )

    args = parser.parse_args()

    if args.action == "setup":
        if not args.s3_bucket:
            print("ERROR: --s3-bucket is required for setup")
            sys.exit(1)

        print("Creating Athena database...")
        create_database(
            region=args.region,
            profile=args.profile,
            workgroup=args.workgroup,
            output_location=args.output_location,
        )

        print("\nCreating CloudTrail table...")
        create_table(
            s3_bucket=args.s3_bucket,
            region=args.region,
            profile=args.profile,
            workgroup=args.workgroup,
            output_location=args.output_location,
            account_id=args.account_id,
        )

        print("\nSetup complete! Run 'python setup_athena.py queries' for useful queries.")

    elif args.action == "queries":
        print_queries()


if __name__ == "__main__":
    main()
