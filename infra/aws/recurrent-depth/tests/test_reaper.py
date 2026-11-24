"""Unit tests for the reaper Lambda (no AWS: a fake EC2 client)."""

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "reaper", Path(__file__).resolve().parents[1] / "modules" / "guardrails" / "lambda" / "reaper.py"
)
reaper = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reaper)

NOW = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.timezone.utc)


def _inst(iid, hours_ago, **tags):
    return {
        "InstanceId": iid,
        "LaunchTime": NOW - dt.timedelta(hours=hours_ago),
        "Tags": [{"Key": k, "Value": v} for k, v in {"Project": "recurrent-depth", **tags}.items()],
    }


class FakeEC2:
    def __init__(self, instances, page=2):
        self.instances = instances
        self.page = page
        self.terminated = []
        self.filters = None

    def describe_instances(self, Filters, NextToken=None):  # noqa: N803 - boto3 names
        self.filters = Filters
        start = int(NextToken or 0)
        chunk = self.instances[start : start + self.page]
        resp = {"Reservations": [{"Instances": chunk}]}
        if start + self.page < len(self.instances):
            resp["NextToken"] = str(start + self.page)
        return resp

    def terminate_instances(self, InstanceIds):  # noqa: N803
        self.terminated += InstanceIds


@pytest.mark.parametrize(
    "tags, expected",
    [
        ({}, 4),
        ({"MaxHours": "2"}, 2),
        ({"MaxHours": "20"}, 12),
        ({"MaxHours": "6", "HardCapHours": "3"}, 3),
        ({"MaxHours": "nonsense"}, 4),
        ({"MaxHours": "-1"}, 4),
        ({"HardCapHours": "100"}, 4),
    ],
)
def test_limit_hours(tags, expected):
    assert reaper.limit_hours(tags, default_hours=4, hard_cap_hours=12) == expected


def test_reap_terminates_only_expired_with_grace():
    ec2 = FakeEC2(
        [
            _inst("i-young", 1, MaxHours="2"),
            _inst("i-in-grace", 2.1, MaxHours="2"),  # 6 minutes over, inside the 15 minute grace
            _inst("i-old", 2.5, MaxHours="2", RunId="r1"),
            _inst("i-capped", 13, MaxHours="48"),
            _inst("i-default", 5),
        ]
    )
    out = reaper.reap(ec2, "recurrent-depth", 4, 12, 15, now=lambda: NOW)
    assert sorted(ec2.terminated) == ["i-capped", "i-default", "i-old"]
    assert out["checked"] == 5
    assert {"Name": "tag:Project", "Values": ["recurrent-depth"]} in ec2.filters
    old = next(e for e in out["expired"] if e["InstanceId"] == "i-old")
    assert old["run_id"] == "r1" and old["limit_hours"] == pytest.approx(2.25)


def test_dry_run_terminates_nothing():
    ec2 = FakeEC2([_inst("i-old", 10, MaxHours="1")])
    out = reaper.reap(ec2, "recurrent-depth", 4, 12, 15, now=lambda: NOW, dry_run=True)
    assert ec2.terminated == [] and out["terminated"] == [] and len(out["expired"]) == 1


def test_naive_launch_time_is_utc():
    inst = _inst("i-naive", 0)
    inst["LaunchTime"] = (NOW - dt.timedelta(hours=9)).replace(tzinfo=None)
    assert reaper.find_expired([{"Instances": [inst]}], NOW, 4, 12, 0)[0]["InstanceId"] == "i-naive"
