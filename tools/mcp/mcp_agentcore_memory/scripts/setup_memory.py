#!/usr/bin/env python3
"""
Bootstrap script to create an AgentCore Memory resource.

This is a ONE-TIME setup script. Run it once to create the Memory,
then use the returned memory_id in your MCP server configuration.

Usage:
    # With AWS profile (recommended)
    AWS_PROFILE=agentcore python scripts/setup_memory.py

    # Or with environment variables
    AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=xxx python scripts/setup_memory.py

Requirements:
    pip install boto3
"""

import argparse
import json
import sys
from typing import Any, Optional
import uuid

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


def create_memory(
    name: str,
    description: str,
    region: str = "us-east-1",
    profile: Optional[str] = None,
    event_expiry_days: int = 90,
) -> dict:
    """
    Create an AgentCore Memory resource.

    Args:
        name: Display name for the memory
        description: Description of the memory's purpose
        region: AWS region (default: us-east-1)
        profile: AWS profile name (optional)

    Returns:
        Dict with memory details including memoryId
    """
    # Create session with optional profile
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)

    # Use bedrock-agentcore-control for control plane operations
    # (bedrock-agentcore is for data plane only)
    client = session.client("bedrock-agentcore-control")

    # Generate idempotency token
    client_token = str(uuid.uuid4())

    # Validate name (must match [a-zA-Z][a-zA-Z0-9_]{0,47})
    import re

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{0,47}$", name):
        print(f"ERROR: Name '{name}' is invalid.")
        print("  Must start with letter, contain only letters/numbers/underscores, max 48 chars.")
        print("  Example: template_repo_memory")
        raise ValueError(f"Invalid name: {name}")

    # eventExpiryDuration is in DAYS (max 365)
    if event_expiry_days > 365:
        print(f"WARNING: event_expiry_days={event_expiry_days} exceeds max 365, using 365.")
        event_expiry_days = 365

    print(f"Creating AgentCore Memory: {name}")
    print(f"  Region: {region}")
    print(f"  Description: {description}")
    print(f"  Event Expiry: {event_expiry_days} days")
    print()

    try:
        response = client.create_memory(
            name=name,
            description=description,
            eventExpiryDuration=event_expiry_days,
            clientToken=client_token,
            # Optional: Configure memory strategies
            # memoryStrategies=[
            #     {
            #         "strategyType": "SEMANTIC_CONSOLIDATION",
            #         "configuration": {}
            #     }
            # ],
            # Optional: Encryption with KMS
            # encryptionKeyArn="arn:aws:kms:...",
        )

        memory_id = response.get("memoryId") or response.get("memory", {}).get("memoryId")
        memory_arn = response.get("memoryArn") or response.get("memory", {}).get("memoryArn")

        print("SUCCESS! Memory created.")
        print()
        print("=" * 60)
        print("SAVE THESE VALUES FOR YOUR MCP SERVER CONFIGURATION:")
        print("=" * 60)
        print(f"  AGENTCORE_MEMORY_ID={memory_id}")
        print(f"  AWS_REGION={region}")
        print()
        print(f"  Memory ARN: {memory_arn}")
        print("=" * 60)

        return {
            "memoryId": memory_id,
            "memoryArn": memory_arn,
            "name": name,
            "region": region,
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "ConflictException":
            print("ERROR: A memory with this name may already exist.")
            print("  Use 'list_memories' to see existing memories.")
        elif error_code == "AccessDeniedException":
            print("ERROR: Access denied. Check your IAM permissions.")
            print("  Required: bedrock-agentcore:CreateMemory")
        else:
            print(f"ERROR: {error_code} - {error_msg}")

        raise


def list_memories(region: str = "us-east-1", profile: Optional[str] = None) -> list[Any]:
    """List existing AgentCore Memory resources."""
    session_kwargs: dict[str, Any] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("bedrock-agentcore-control")

    print(f"Listing AgentCore Memories in {region}...")
    print()

    try:
        response = client.list_memories(maxResults=50)
        memories: list[Any] = response.get("memorySummaries", []) or response.get("memories", [])

        if not memories:
            print("No memories found.")
            return []

        print(f"Found {len(memories)} memory resource(s):")
        print("-" * 60)

        for mem in memories:
            mem_id = mem.get("memoryId", "N/A")
            mem_name = mem.get("name", "N/A")
            mem_status = mem.get("status", "N/A")
            print(f"  ID: {mem_id}")
            print(f"  Name: {mem_name}")
            print(f"  Status: {mem_status}")
            print("-" * 60)

        return memories

    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise


def get_memory(memory_id: str, region: str = "us-east-1", profile: Optional[str] = None) -> dict[str, Any]:
    """Get details of a specific memory."""
    session_kwargs: dict[str, Any] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    client = session.client("bedrock-agentcore-control")

    print(f"Getting memory: {memory_id}")

    try:
        response = client.get_memory(memoryId=memory_id)
        memory: dict[str, Any] = response.get("memory", response)

        print(json.dumps(memory, indent=2, default=str))
        return memory

    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise


def main():
    """CLI entry point for memory setup script"""
    parser = argparse.ArgumentParser(
        description="Bootstrap AgentCore Memory resource",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new memory
  AWS_PROFILE=agentcore python setup_memory.py create --name "agent-memory" --description "Memory for AI agents"

  # List existing memories
  AWS_PROFILE=agentcore python setup_memory.py list

  # Get memory details
  AWS_PROFILE=agentcore python setup_memory.py get --memory-id mem-xxxxx
        """,
    )

    parser.add_argument(
        "action",
        choices=["create", "list", "get"],
        help="Action to perform",
    )
    parser.add_argument(
        "--name",
        default="template-repo-agent-memory",
        help="Memory name (for create)",
    )
    parser.add_argument(
        "--description",
        default="Persistent memory for AI agents in template-repo",
        help="Memory description (for create)",
    )
    parser.add_argument(
        "--memory-id",
        help="Memory ID (for get)",
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
        create_memory(
            name=args.name,
            description=args.description,
            region=args.region,
            profile=args.profile,
        )
    elif args.action == "list":
        list_memories(region=args.region, profile=args.profile)
    elif args.action == "get":
        if not args.memory_id:
            print("ERROR: --memory-id is required for 'get' action")
            sys.exit(1)
        get_memory(args.memory_id, region=args.region, profile=args.profile)


if __name__ == "__main__":
    main()
