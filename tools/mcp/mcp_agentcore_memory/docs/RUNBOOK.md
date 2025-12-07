# AgentCore Memory Operations Runbook

This runbook covers operational procedures for managing the AgentCore Memory system.

## Table of Contents

- [Daily Operations](#daily-operations)
- [Monitoring & Alerts](#monitoring--alerts)
- [Backup Procedures](#backup-procedures)
- [Restore Procedures](#restore-procedures)
- [Cleanup Operations](#cleanup-operations)
- [Troubleshooting](#troubleshooting)
- [Emergency Procedures](#emergency-procedures)

---

## Daily Operations

### Health Check

```bash
# Via MCP tool (Claude Code)
# Use memory_status tool

# Via CLI
AWS_PROFILE=agentcore python -c "
import asyncio
from mcp_agentcore_memory.providers.factory import get_provider

async def check():
    p = get_provider()
    healthy = await p.health_check()
    info = await p.get_info()
    print(f'Healthy: {healthy}')
    print(f'Provider: {info}')

asyncio.run(check())
"
```

### View Current Usage

```bash
# Check AWS Cost Explorer (requires cost-explorer permissions)
AWS_PROFILE=agentcore aws ce get-cost-and-usage \
  --time-period Start=$(date -d '-30 days' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Bedrock"]}}' \
  --metrics BlendedCost
```

---

## Monitoring & Alerts

### CloudWatch Dashboard

View the dashboard:
```
https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AgentCoreMemory-Operations
```

### Key Metrics to Monitor

| Metric | Healthy Range | Alert Threshold |
|--------|---------------|-----------------|
| StoreEventLatency | < 2000ms | > 5000ms |
| SearchMemoriesLatency | < 1000ms | > 3000ms |
| Success Rate | > 95% | < 90% |
| Rate Limit Errors | 0 | > 10/hour |

### Setup Monitoring

```bash
# Create CloudWatch dashboard and alarms
AWS_PROFILE=agentcore python scripts/setup_cloudwatch.py create

# With SNS notifications
AWS_PROFILE=agentcore python scripts/setup_cloudwatch.py create \
  --sns-topic arn:aws:sns:us-east-1:ACCOUNT:alerts
```

---

## Backup Procedures

### Export Memory Records

AgentCore Memory doesn't have a native export API. Use these procedures:

#### Option 1: Query and Export via Athena

```sql
-- Export all memory records to S3
-- Run in Athena after setting up CloudTrail table

CREATE TABLE agentcore_audit.memory_backup AS
SELECT
    eventTime,
    eventName,
    json_extract_scalar(requestParameters, '$.namespace') as namespace,
    json_extract_scalar(requestParameters, '$.content') as content,
    requestParameters
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventName IN ('BatchCreateMemoryRecords', 'CreateEvent')
    AND eventTime >= '2025-01-01T00:00:00Z';
```

#### Option 2: Application-Level Backup

```python
#!/usr/bin/env python3
"""Backup memory records to JSON file."""
import asyncio
import json
from datetime import datetime

async def backup_namespace(provider, namespace: str, output_file: str):
    """Backup all records from a namespace."""
    # Note: This requires iterating with broad queries
    # AgentCore doesn't have a "list all" API

    queries = [
        "code patterns",
        "conventions",
        "architecture",
        "error handling",
        "testing",
    ]

    all_records = []
    seen_ids = set()

    for query in queries:
        records = await provider.search_records(query, namespace, top_k=100)
        for r in records:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_records.append({
                    "id": r.id,
                    "content": r.content,
                    "namespace": namespace,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })

    with open(output_file, "w") as f:
        json.dump({
            "backup_time": datetime.utcnow().isoformat(),
            "namespace": namespace,
            "record_count": len(all_records),
            "records": all_records,
        }, f, indent=2)

    print(f"Backed up {len(all_records)} records to {output_file}")
```

### Backup Schedule Recommendation

| Data Type | Frequency | Retention |
|-----------|-----------|-----------|
| Memory Records | Weekly | 90 days |
| CloudTrail Logs | Automatic | 1 year |
| Cost Reports | Monthly | 2 years |

---

## Restore Procedures

### Restore from Backup

```python
#!/usr/bin/env python3
"""Restore memory records from JSON backup."""
import asyncio
import json

async def restore_from_backup(provider, backup_file: str):
    """Restore records from backup file."""
    with open(backup_file) as f:
        backup = json.load(f)

    namespace = backup["namespace"]
    records = backup["records"]

    # Batch restore (uses BatchCreateMemoryRecords - no rate limit)
    batch_size = 10
    total_restored = 0

    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        record_data = [
            {"content": r["content"], "metadata": {"restored": True}}
            for r in batch
        ]

        result = await provider.store_records(record_data, namespace)
        total_restored += result.created
        print(f"Restored {total_restored}/{len(records)} records")

    print(f"Restore complete: {total_restored} records")
```

### Restore from CloudTrail (Disaster Recovery)

If you need to reconstruct memories from CloudTrail logs:

```sql
-- Query CloudTrail for original content
SELECT
    from_iso8601_timestamp(eventTime) as stored_at,
    json_extract_scalar(requestParameters, '$.namespace') as namespace,
    json_extract_scalar(requestParameters, '$.content.text') as content
FROM agentcore_audit.cloudtrail_logs
WHERE eventSource = 'bedrock-agentcore.amazonaws.com'
    AND eventName = 'BatchCreateMemoryRecords'
    AND errorCode IS NULL
ORDER BY eventTime DESC;
```

---

## Cleanup Operations

### Delete Old Events

Events expire automatically based on `eventExpiryDuration` (default: 90 days).

To manually clean up:

```python
#!/usr/bin/env python3
"""Clean up old session events."""
import asyncio
import boto3
from datetime import datetime, timedelta

async def cleanup_old_sessions(memory_id: str, days_old: int = 30):
    """Delete events older than specified days."""
    session = boto3.Session(profile_name="agentcore")
    client = session.client("bedrock-agentcore")

    # List actors
    actors = client.list_actors(memoryId=memory_id)

    for actor in actors.get("actorSummaries", []):
        actor_id = actor["actorId"]

        # List sessions for this actor
        sessions = client.list_sessions(
            memoryId=memory_id,
            actorId=actor_id,
        )

        cutoff = datetime.utcnow() - timedelta(days=days_old)

        for session in sessions.get("sessionSummaries", []):
            created = session.get("createdAt")
            if created and created < cutoff:
                # Delete events in this session
                events = client.list_events(
                    memoryId=memory_id,
                    actorId=actor_id,
                    sessionId=session["sessionId"],
                )

                for event in events.get("events", []):
                    client.delete_event(
                        memoryId=memory_id,
                        actorId=actor_id,
                        sessionId=session["sessionId"],
                        eventId=event["eventId"],
                    )
                    print(f"Deleted event: {event['eventId']}")
```

### Delete Specific Memory Records

```python
#!/usr/bin/env python3
"""Delete memory records by ID."""
import boto3

def delete_records(memory_id: str, record_ids: list, namespace: str):
    """Delete specific memory records."""
    session = boto3.Session(profile_name="agentcore")
    client = session.client("bedrock-agentcore")

    # Batch delete (max 10 per call)
    for i in range(0, len(record_ids), 10):
        batch = record_ids[i:i+10]
        client.batch_delete_memory_records(
            memoryId=memory_id,
            memoryRecordIds=[
                {"memoryRecordId": rid, "namespace": namespace}
                for rid in batch
            ],
        )
        print(f"Deleted {len(batch)} records")
```

### Namespace Cleanup

To remove all records from a namespace:

```python
async def clear_namespace(provider, namespace: str):
    """Clear all records from a namespace."""
    # Search with multiple queries to find all records
    all_ids = set()

    queries = ["*", "the", "is", "code", "function", "class"]
    for query in queries:
        records = await provider.search_records(query, namespace, top_k=100)
        for r in records:
            all_ids.add(r.id)

    print(f"Found {len(all_ids)} records to delete")

    # Delete in batches
    # ... (use batch_delete_memory_records)
```

---

## Troubleshooting

### Common Issues

#### Rate Limit Errors

**Symptom**: `ThrottlingException` on `CreateEvent`

**Solution**:
1. Check if calling `store_event` too frequently
2. Use `store_facts` (BatchCreateMemoryRecords) instead - no rate limit
3. Implement exponential backoff

```python
# Rate limit is 0.25 req/sec per (actor_id, session_id)
# = 1 request every 4 seconds
# = 15 requests per minute max
```

#### Search Returns Empty

**Symptom**: `search_memories` returns no results for known data

**Possible Causes**:
1. Wrong namespace
2. Indexing delay (wait 1-2 seconds after store)
3. Query doesn't match stored content semantically

**Solution**:
```python
# Verify data exists with list_memory_records
client.list_memory_records(memoryId=memory_id, namespace=namespace)
```

#### High Latency

**Symptom**: Operations take > 5 seconds

**Possible Causes**:
1. Network issues
2. AWS service degradation
3. Large result sets

**Solution**:
1. Check AWS Health Dashboard
2. Reduce `top_k` in searches
3. Use caching (already implemented in MCP server)

### Debug Logging

Enable debug logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run server with debug
python -m mcp_agentcore_memory.server --mode http --log-level DEBUG
```

---

## Emergency Procedures

### Service Degradation

If AgentCore is experiencing issues:

1. **Check AWS Status**: https://health.aws.amazon.com/
2. **Fallback to ChromaDB**:
   ```bash
   # Update .mcp.json or environment
   MEMORY_PROVIDER=chromadb docker-compose up -d mcp-agentcore-memory
   ```
3. **Disable memory features** in agents (graceful degradation already implemented)

### Cost Spike

If costs exceed budget:

1. **Check Cost Explorer** for anomalies
2. **Review CloudTrail** for unexpected API calls
3. **Temporarily disable** memory features:
   ```bash
   ENABLE_CLOUDWATCH_METRICS=false
   ```
4. **Delete unnecessary data** using cleanup procedures above

### Data Breach Concern

If sensitive data may have been stored:

1. **Audit CloudTrail** for what was stored
2. **Search for patterns** that might indicate secrets
3. **Delete affected records** using procedures above
4. **Review sanitization** - run test suite
5. **Report** per security incident procedures

---

## Contact & Escalation

| Issue Type | First Response | Escalation |
|------------|----------------|------------|
| Service Degradation | Check AWS Status | AWS Support |
| Cost Issues | Review Cost Explorer | Budget Owner |
| Security Concerns | Review CloudTrail | Security Team |
| Data Loss | Check Backups | Infrastructure Team |

---

## Appendix: Useful Commands

```bash
# List all memories
AWS_PROFILE=agentcore aws bedrock-agentcore-control list-memories

# Get memory details
AWS_PROFILE=agentcore aws bedrock-agentcore-control get-memory \
  --memory-id template_repo_memory-s2E1OlFGBp

# List actors
AWS_PROFILE=agentcore aws bedrock-agentcore list-actors \
  --memory-id template_repo_memory-s2E1OlFGBp

# Check budget status
AWS_PROFILE=agentcore python scripts/setup_cost_alerts.py status
```
