import json

import pytest

from recurrent_depth import cli


def run(capsys, *argv):
    assert cli.main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_inspect_config_cli(tmp_path, capsys):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"model_type": "ouro", "num_hidden_layers": 24, "total_ut_steps": 4}))
    out = run(capsys, "inspect-config", str(p))
    assert out["signals"] == {"config_recurrence": 1.0}


def test_simulate_features_score_pipeline(tmp_path, capsys):
    rec = tmp_path / "r.jsonl"
    assert cli.main(["simulate", "--kind", "recurrent", "--reps", "3", "--knob", "--out", str(rec)]) == 0
    capsys.readouterr()
    feats = run(capsys, "features", str(rec), "--knob-order", "low,medium,high")
    sig_path = tmp_path / "sig.json"
    sig_path.write_text(json.dumps(feats))
    cfg_path = tmp_path / "cfg_sig.json"
    cfg_path.write_text(json.dumps({"signals": {"config_recurrence": 0.5}}))
    out = run(capsys, "score", str(sig_path), str(cfg_path))
    assert out["verdict"]["label"] in ("recurrent", "inconclusive")
    assert out["verdict"]["posterior_recurrent"] > 0.5


def test_duplicate_signal_across_files_rejected(tmp_path):
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"ttft_slope_z": 1.0}))
    with pytest.raises(SystemExit):
        cli.main(["score", str(a), str(a)])


def test_fleet_fit_validate(tmp_path, capsys):
    refs = tmp_path / "refs.json"
    assert cli.main(["simulate-fleet", "--n-each", "3", "--reps", "2", "--out", str(refs)]) == 0
    models = tmp_path / "models.json"
    assert cli.main(["fit", str(refs), "--out", str(models)]) == 0
    capsys.readouterr()
    res = run(capsys, "validate", str(refs))
    assert res["n"] == 6
