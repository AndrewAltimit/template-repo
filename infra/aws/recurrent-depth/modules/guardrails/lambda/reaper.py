"""Terminate recurrent-depth nodes that outlive their limit.

The outer safety net. A node powers itself off at its MaxHours tag (watchdog in
the bootstrap) and the campaign runner stops at max_wall_hours; this function
covers the case where both fail, for example a bootstrap that never ran.

Runs every few minutes from EventBridge. For every pending or running instance
tagged ``Project=<PROJECT>`` it computes the limit as
``min(MaxHours tag or DEFAULT_MAX_HOURS, HardCapHours tag or HARD_CAP_HOURS, HARD_CAP_HOURS)``
plus ``GRACE_MINUTES``, and terminates the instance once it is older than that.
Instances without the project tag are never touched, and the IAM policy only
allows terminating instances that carry it.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Callable


def _hours(value: Any, fallback: float) -> float:
    try:
        h = float(value)
    except (TypeError, ValueError):
        return fallback
    return h if h > 0 else fallback


def limit_hours(tags: dict[str, str], default_hours: float, hard_cap_hours: float) -> float:
    """Allowed lifetime for one instance, in hours."""
    requested = _hours(tags.get("MaxHours"), default_hours)
    tier_cap = _hours(tags.get("HardCapHours"), hard_cap_hours)
    return min(requested, tier_cap, hard_cap_hours)


def find_expired(
    reservations: list[dict[str, Any]],
    now: dt.datetime,
    default_hours: float,
    hard_cap_hours: float,
    grace_minutes: float,
) -> list[dict[str, Any]]:
    """Instances past their limit, with the numbers used to decide."""
    expired = []
    for res in reservations:
        for inst in res.get("Instances", []):
            tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
            launched = inst["LaunchTime"]
            if launched.tzinfo is None:
                launched = launched.replace(tzinfo=dt.timezone.utc)
            age_h = (now - launched).total_seconds() / 3600
            limit_h = limit_hours(tags, default_hours, hard_cap_hours) + grace_minutes / 60
            if age_h > limit_h:
                expired.append(
                    {
                        "InstanceId": inst["InstanceId"],
                        "age_hours": round(age_h, 3),
                        "limit_hours": round(limit_h, 3),
                        "run_id": tags.get("RunId"),
                    }
                )
    return expired


def reap(
    ec2: Any,
    project: str,
    default_hours: float,
    hard_cap_hours: float,
    grace_minutes: float,
    now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
    dry_run: bool = False,
) -> dict[str, Any]:
    filters = [
        {"Name": "tag:Project", "Values": [project]},
        {"Name": "instance-state-name", "Values": ["pending", "running"]},
    ]
    reservations: list[dict[str, Any]] = []
    token = None
    while True:
        kw: dict[str, Any] = {"Filters": filters}
        if token:
            kw["NextToken"] = token
        resp = ec2.describe_instances(**kw)
        reservations += resp.get("Reservations", [])
        token = resp.get("NextToken")
        if not token:
            break
    expired = find_expired(reservations, now(), default_hours, hard_cap_hours, grace_minutes)
    ids = [e["InstanceId"] for e in expired]
    if ids and not dry_run:
        ec2.terminate_instances(InstanceIds=ids)
    checked = sum(len(r.get("Instances", [])) for r in reservations)
    return {"checked": checked, "terminated": [] if dry_run else ids, "expired": expired, "dry_run": dry_run}


def handler(event: Any, context: Any) -> dict[str, Any]:  # pragma: no cover - thin AWS entry point
    import boto3

    result = reap(
        boto3.client("ec2"),
        project=os.environ.get("PROJECT", "recurrent-depth"),
        default_hours=float(os.environ.get("DEFAULT_MAX_HOURS", "4")),
        hard_cap_hours=float(os.environ.get("HARD_CAP_HOURS", "12")),
        grace_minutes=float(os.environ.get("GRACE_MINUTES", "15")),
        dry_run=os.environ.get("DRY_RUN", "false").lower() == "true",
    )
    print(json.dumps(result, default=str))
    return result
