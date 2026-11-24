"""Campaign runner: validation, checkpoints, resume, failure, deadlines, services, and the CLI."""

import json
import sys

import pytest

from recurrent_depth import campaign, cli, store

PY = sys.executable


def _manifest(stages, **kw):
    return campaign.Manifest.from_dict({"campaign": "test", "stages": stages, "sync_interval_s": 5, **kw})


def _write_stage(name, text, extra=None):
    code = f"import pathlib,sys; pathlib.Path(sys.argv[1], 'out.txt').write_text({text!r})"
    return {"name": name, "kind": "exec", "argv": [PY, "-c", code, "{out}"], **(extra or {})}


def _runner(m, tmp_path, run_id="r1", **kw):
    st = store.LocalStore(tmp_path / "store")
    return campaign.CampaignRunner(m, st, run_id, tmp_path / "work", poll_s=0.01, log=lambda _m: None, **kw), st


@pytest.mark.parametrize(
    "raw, match",
    [
        ({"campaign": "Bad Name", "stages": [{"name": "a", "argv": ["x"]}]}, "campaign"),
        ({"campaign": "c", "stages": []}, "at least one"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"]}, {"name": "a", "argv": ["y"]}]}, "duplicate"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": []}]}, "argv"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"], "kind": "shell"}]}, "kind"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"], "service": "s"}]}, "unknown service"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"]}], "max_wall_hours": 100}, "max_wall_hours"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"], "bogus": 1}]}, "malformed"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"]}], "extra": 1}, "unknown manifest"),
        ({"campaign": "c", "stages": [{"name": "a", "argv": ["x"], "env": {"bad-name": "1"}}]}, "env"),
        (
            {
                "campaign": "c",
                "stages": [{"name": "a", "argv": ["x"]}],
                "services": {"s": {"argv": ["x"], "health_url": "http://evil.example/health"}},
            },
            "local http",
        ),
    ],
)
def test_manifest_validation(raw, match):
    with pytest.raises(campaign.ManifestError, match=match):
        campaign.Manifest.from_dict(raw)


def test_stages_checkpoint_with_hashes(tmp_path):
    m = _manifest([_write_stage("one", "first"), _write_stage("two", "second")])
    r, st = _runner(m, tmp_path)
    summary = r.run()
    assert summary["status"] == "completed"
    marker = json.loads(st.get_bytes("runs/r1/stages/one/_SUCCESS.json"))
    names = {f["path"] for f in marker["files"]}
    assert {"out.txt", "stdout.log", "stderr.log"} <= names
    out = next(f for f in marker["files"] if f["path"] == "out.txt")
    assert out["sha256"] == store.sha256_file(tmp_path / "work" / "stages" / "one" / "out.txt")
    assert st.get_bytes("runs/r1/stages/two/out.txt") == b"second"
    assert json.loads(st.get_bytes("runs/r1/_CAMPAIGN.json"))["status"] == "completed"
    assert json.loads(st.get_bytes("runs/r1/manifest.json"))["campaign"] == "test"


def test_resume_skips_completed_and_retries_failed(tmp_path):
    flag = tmp_path / "flag"
    code = f"import pathlib,sys; sys.exit(0 if pathlib.Path({str(flag)!r}).exists() else 3)"
    stages = [_write_stage("one", "first"), {"name": "two", "kind": "exec", "argv": [PY, "-c", code]}]
    m = _manifest(stages)
    r, st = _runner(m, tmp_path)
    first = r.run()
    assert first["status"] == "failed" and first["failed_stage"] == "two"
    assert st.exists("runs/r1/stages/two/_FAILED.json")
    status = campaign.campaign_status(st, "r1")
    assert [s["state"] for s in status["stages"]] == ["done", "failed"]
    # a fresh machine with an empty work directory resumes from the store
    flag.write_text("ok")
    r2 = campaign.CampaignRunner(m, st, "r1", tmp_path / "work2", poll_s=0.01, log=lambda _m: None)
    second = r2.run()
    assert second["status"] == "completed"
    assert second["stages"][0]["skipped"]
    # the skipped stage's outputs are restored for later stages to read
    assert (tmp_path / "work2" / "stages" / "one" / "out.txt").read_text() == "first"
    assert [s["state"] for s in campaign.campaign_status(st, "r1")["stages"]] == ["done", "done"]


def test_resume_with_a_different_manifest_is_refused(tmp_path):
    r, st = _runner(_manifest([_write_stage("one", "a")]), tmp_path)
    r.run()
    r2 = campaign.CampaignRunner(_manifest([_write_stage("one", "b")]), st, "r1", tmp_path / "w", log=lambda _m: None)
    with pytest.raises(campaign.ManifestError, match="different manifest"):
        r2.run()


def test_allow_failure_continues(tmp_path):
    stages = [
        {"name": "bad", "kind": "exec", "argv": [PY, "-c", "raise SystemExit(2)"], "allow_failure": True},
        _write_stage("good", "x"),
    ]
    summary = _runner(_manifest(stages), tmp_path)[0].run()
    assert summary["status"] == "completed"
    assert [s["ok"] for s in summary["stages"]] == [False, True]


def test_stage_timeout_kills_and_keeps_partial_output(tmp_path):
    code = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1],'partial.jsonl'); p.write_text('row\\n'); time.sleep(30)"
    stages = [{"name": "slow", "kind": "exec", "argv": [PY, "-c", code, "{out}"], "timeout_s": 2}]
    r, st = _runner(_manifest(stages), tmp_path)
    summary = r.run()
    assert summary["status"] == "failed"
    failed = json.loads(st.get_bytes("runs/r1/stages/slow/_FAILED.json"))
    assert failed["reason"] == "timeout"
    assert st.get_bytes("runs/r1/stages/slow/partial.jsonl") == b"row\n"


def test_wall_deadline_stops_before_next_stage(tmp_path):
    # a fake clock that jumps past the deadline after the first stage
    t = {"now": 0.0}

    def clock():
        return t["now"]

    def sleep(dt):
        t["now"] += dt

    m = _manifest([_write_stage("one", "a"), _write_stage("two", "b")], max_wall_hours=1)
    r, st = _runner(m, tmp_path, clock=clock, sleep=sleep)
    orig = r._run_stage

    def run_and_advance(stage):
        rec = orig(stage)
        t["now"] += 3600
        return rec

    r._run_stage = run_and_advance
    summary = r.run()
    assert summary["status"] == "deadline"
    assert st.exists("runs/r1/stages/one/_SUCCESS.json") and not st.exists("runs/r1/stages/two/_SUCCESS.json")


def test_service_lifecycle(tmp_path):
    marker = tmp_path / "svc.txt"
    svc_code = f"import pathlib,time; pathlib.Path({str(marker)!r}).write_text('up'); time.sleep(60)"
    m = campaign.Manifest.from_dict(
        {
            "campaign": "svc",
            "sync_interval_s": 5,
            "services": {"model": {"argv": [PY, "-c", svc_code], "health_url": "http://127.0.0.1:1/health"}},
            "stages": [dict(_write_stage("uses", "x"), service="model"), _write_stage("after", "y")],
        }
    )
    st = store.LocalStore(tmp_path / "store")
    healthy = lambda _url: marker.exists()  # noqa: E731
    r = campaign.CampaignRunner(m, st, "r1", tmp_path / "work", poll_s=0.05, health=healthy, log=lambda _m: None)
    summary = r.run()
    assert summary["status"] == "completed"
    assert r._service_proc is None  # stopped before the stage without a service
    assert st.exists("runs/r1/services/model.log")


def test_service_that_dies_fails_the_stage(tmp_path):
    m = campaign.Manifest.from_dict(
        {
            "campaign": "svc",
            "services": {"model": {"argv": [PY, "-c", "raise SystemExit(1)"], "health_url": "http://127.0.0.1:1/health"}},
            "stages": [dict(_write_stage("uses", "x"), service="model")],
        }
    )
    st = store.LocalStore(tmp_path / "store")
    r = campaign.CampaignRunner(m, st, "r1", tmp_path / "w", poll_s=0.05, health=lambda _u: False, log=lambda _m: None)
    summary = r.run()
    assert summary["status"] == "failed"
    assert "exited during start-up" in json.loads(st.get_bytes("runs/r1/stages/uses/_FAILED.json"))["reason"]


def test_cli_stage_runs_the_toolkit(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"model_type": "ouro", "num_hidden_layers": 24, "total_ut_steps": 4}))
    stages = [{"name": "cfg", "kind": "cli", "argv": ["inspect-config", str(cfg)]}]
    r, st = _runner(_manifest(stages), tmp_path)
    assert r.run()["status"] == "completed"
    report = json.loads(st.get_bytes("runs/r1/stages/cfg/stdout.log"))
    assert report["report"]["declares_recurrence"]


def test_campaign_cli_run_status_fetch(tmp_path, capsys):
    man = tmp_path / "m.json"
    man.write_text(json.dumps({"campaign": "cli", "stages": [_write_stage("one", "hello")]}))
    st = str(tmp_path / "store")
    assert cli.main(["campaign", "run", str(man), "--dry-run", "--run-id", "x1"]) == 0
    assert json.loads(capsys.readouterr().out)["stages"][0]["stage"] == "one"
    assert cli.main(["campaign", "run", str(man), "--store", st, "--run-id", "x1", "--work-dir", str(tmp_path / "w")]) == 0
    capsys.readouterr()
    assert cli.main(["campaign", "status", "--store", st, "--run-id", "x1"]) == 0
    assert json.loads(capsys.readouterr().out)["stages"] == [{"stage": "one", "state": "done"}]
    dest = tmp_path / "fetched"
    assert cli.main(["campaign", "fetch", "--store", st, "--run-id", "x1", "--dest", str(dest)]) == 0
    assert (dest / "stages" / "one" / "out.txt").read_text() == "hello"
    assert campaign.campaign_status(store.LocalStore(tmp_path / "store"), "nope") == {"run_id": "nope", "found": False}


def test_bad_run_id_refused(tmp_path):
    with pytest.raises(campaign.ManifestError):
        _runner(_manifest([_write_stage("one", "a")]), tmp_path, run_id="../x")


def test_later_stage_reads_restored_output(tmp_path):
    reader = (
        "import pathlib,sys; w=pathlib.Path(sys.argv[1]); "
        "pathlib.Path(sys.argv[2],'copy.txt').write_text((w/'stages'/'one'/'out.txt').read_text())"
    )
    stages = [_write_stage("one", "payload"), {"name": "two", "kind": "exec", "argv": [PY, "-c", reader, "{work}", "{out}"]}]
    m = _manifest(stages)
    st = store.LocalStore(tmp_path / "store")
    # first machine finishes only stage one
    first = campaign.Manifest.from_dict({"campaign": "test", "stages": stages[:1], "sync_interval_s": 5})
    campaign.CampaignRunner(first, st, "solo", tmp_path / "a", poll_s=0.01, log=lambda _m: None).run()
    # copy its checkpoint under a second run id whose manifest has both stages
    for key in st.keys("runs/solo/stages"):
        st.put_bytes(key.replace("runs/solo/", "runs/r2/"), st.get_bytes(key))
    out = campaign.CampaignRunner(m, st, "r2", tmp_path / "b", poll_s=0.01, log=lambda _m: None).run()
    assert out["status"] == "completed" and out["stages"][0]["skipped"]
    assert st.get_bytes("runs/r2/stages/two/copy.txt") == b"payload"
