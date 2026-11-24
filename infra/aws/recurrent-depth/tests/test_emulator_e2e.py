"""End-to-end tests against the local AWS Emulator, after `infra.sh apply --emulator`.

Run by scripts/emulator-e2e.sh, which applies every unit to the emulator and
passes the results bucket in RDS_E2E_BUCKET. Skipped otherwise.

Covers what the offline tests cannot: the Terraform-created bucket accepts the
campaign runner's checkpoints through boto3, the launch template starts an
instance with the run tags, and the reaper terminates it once it is overdue.
"""

import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

BUCKET = os.environ.get("RDS_E2E_BUCKET")
pytestmark = [pytest.mark.emulator, pytest.mark.skipif(not BUCKET, reason="needs RDS_E2E_BUCKET (emulator e2e)")]

boto3 = pytest.importorskip("boto3") if BUCKET else None


def _reaper():
    spec = importlib.util.spec_from_file_location(
        "reaper", Path(__file__).resolve().parents[1] / "modules" / "guardrails" / "lambda" / "reaper.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bucket_is_versioned_and_private():
    s3 = boto3.client("s3")
    assert s3.get_bucket_versioning(Bucket=BUCKET).get("Status") == "Enabled"
    block = s3.get_public_access_block(Bucket=BUCKET)["PublicAccessBlockConfiguration"]
    assert all(block.values())


def test_campaign_checkpoints_to_the_bucket(tmp_path):
    from recurrent_depth import campaign, store

    code = "import pathlib,sys; pathlib.Path(sys.argv[1], 'records.jsonl').write_text('{\"ok\": true}\\n')"
    m = campaign.Manifest.from_dict(
        {
            "campaign": "e2e",
            "sync_interval_s": 5,
            "stages": [
                {"name": "write", "kind": "exec", "argv": [sys.executable, "-c", code, "{out}"]},
                {"name": "inspect", "kind": "cli", "argv": ["inspect-config", str(tmp_path / "config.json")]},
            ],
        }
    )
    (tmp_path / "config.json").write_text(json.dumps({"model_type": "ouro", "total_ut_steps": 4}))
    st = store.S3Store(BUCKET, "")
    run_id = "e2e-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    summary = campaign.CampaignRunner(m, st, run_id, tmp_path / "work", poll_s=0.05, log=lambda _m: None).run()
    assert summary["status"] == "completed"
    assert st.get_bytes(f"runs/{run_id}/stages/write/records.jsonl") == b'{"ok": true}\n'
    marker = json.loads(st.get_bytes(f"runs/{run_id}/stages/inspect/_SUCCESS.json"))
    assert marker["ok"] and any(f["path"] == "stdout.log" for f in marker["files"])
    status = campaign.campaign_status(st, run_id)
    assert [s["state"] for s in status["stages"]] == ["done", "done"]
    # resume on a "new machine": nothing reruns
    again = campaign.CampaignRunner(m, st, run_id, tmp_path / "work2", poll_s=0.05, log=lambda _m: None).run()
    assert all(s.get("skipped") for s in again["stages"])
    n = campaign.fetch_run(st, run_id, tmp_path / "fetched")
    assert n >= 6 and (tmp_path / "fetched" / "stages" / "write" / "records.jsonl").is_file()


def test_launch_template_starts_a_tagged_node_and_the_reaper_stops_it():
    ec2 = boto3.client("ec2")
    templates = ec2.describe_launch_templates(
        Filters=[{"Name": "launch-template-name", "Values": ["recurrent-depth-dev-single-gpu"]}]
    )["LaunchTemplates"]
    assert len(templates) == 1
    subnets = ec2.describe_subnets(Filters=[{"Name": "tag:Project", "Values": ["recurrent-depth"]}])["Subnets"]
    assert subnets, "the network unit should have created tagged subnets"
    resp = ec2.run_instances(
        LaunchTemplate={"LaunchTemplateName": "recurrent-depth-dev-single-gpu"},
        SubnetId=subnets[0]["SubnetId"],
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Project", "Value": "recurrent-depth"},
                    {"Key": "RunId", "Value": "e2e-reaper"},
                    {"Key": "MaxHours", "Value": "1"},
                ],
            }
        ],
    )
    iid = resp["Instances"][0]["InstanceId"]
    reaper = _reaper()
    # Too young: left alone.
    first = reaper.reap(ec2, "recurrent-depth", 4, 12, 15)
    assert iid not in first["terminated"]
    # Pretend five hours have passed: past its MaxHours of 1 plus grace.
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5)
    second = reaper.reap(ec2, "recurrent-depth", 4, 12, 15, now=lambda: later)
    assert iid in second["terminated"]
    state = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]["State"]["Name"]
    assert state in ("shutting-down", "terminated")


def test_reaper_function_is_deployed():
    fn = boto3.client("lambda").get_function(FunctionName="recurrent-depth-dev-reaper")["Configuration"]
    assert fn["Runtime"] == "python3.13" and fn["Environment"]["Variables"]["PROJECT"] == "recurrent-depth"
