"""Run the node bootstrap script in a sandbox with stub commands.

The template is rendered the way Terraform's templatefile() would for these
inputs, then executed with curl (IMDS), aws, shutdown, lsblk and python3
replaced by stubs that record their arguments. This checks the safety-critical
order (watchdog first, power-off on every exit) without a cloud instance.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "modules" / "gpu-node" / "bootstrap.sh.tftpl"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or os.name == "nt", reason="needs a POSIX bash")


def render(bucket="rds-bucket", region="us-east-1", tier="single-gpu", hard_cap_hours=4):
    text = TEMPLATE.read_text()
    values = {"bucket": bucket, "region": region, "tier": tier, "hard_cap_hours": str(hard_cap_hours)}
    # templatefile(): ${name} interpolates, $${ is a literal ${
    text = re.sub(r"(?<!\$)\$\{(\w+)\}", lambda m: values[m.group(1)], text)
    return text.replace("$${", "${")


STUBS = {
    "curl": r"""#!/bin/bash
url="${@: -1}"
if [[ "$*" == *"-X PUT"* ]]; then echo token; exit 0; fi
key="${url#http://169.254.169.254/latest/meta-data/}"
f="$STUB_DIR/imds/$key"
[[ -f "$f" ]] && cat "$f" && exit 0
exit 22
""",
    "shutdown": """#!/bin/bash
echo "shutdown $*" >> "$STUB_DIR/calls.log"
""",
    "aws": r"""#!/bin/bash
echo "aws $*" >> "$STUB_DIR/calls.log"
if [[ "$1 $2" == "s3 cp" && "$3" == s3://*/bundles/* ]]; then
  [[ -d "$STUB_DIR/bundle" ]] || exit 1
  cp -r "$STUB_DIR/bundle/." "$4"
fi
exit 0
""",
    "lsblk": "#!/bin/bash\nexit 0\n",
    "python3": r"""#!/bin/bash
echo "python3 $*" >> "$STUB_DIR/calls.log"
if [[ "$1 $2" == "-m venv" ]]; then
  mkdir -p "$3/bin"
  printf '#!/bin/bash\necho "pip $*" >> "%s/calls.log"\n' "$STUB_DIR" > "$3/bin/pip"
  printf '#!/bin/bash\necho "recurrent-depth $*" >> "%s/calls.log"\nexit ${STUB_CAMPAIGN_EXIT:-0}\n' "$STUB_DIR" > "$3/bin/recurrent-depth"
  chmod +x "$3/bin/pip" "$3/bin/recurrent-depth"
fi
""",
}


def run_bootstrap(tmp_path, imds, bundle=True, hard_cap_hours=4, campaign_exit=0):
    stub = tmp_path / "stub"
    (stub / "bin").mkdir(parents=True)
    (stub / "imds" / "tags" / "instance").mkdir(parents=True)
    for name, body in STUBS.items():
        p = stub / "bin" / name
        p.write_text(body)
        p.chmod(0o755)
    for key, value in imds.items():
        (stub / "imds" / key).write_text(value)
    if bundle:
        (stub / "bundle").mkdir()
        (stub / "bundle" / "manifest.json").write_text("{}")
        (stub / "bundle" / "recurrent_depth-1.0.0-py3-none-any.whl").write_text("")
    script = tmp_path / "bootstrap.sh"
    script.write_text(render(hard_cap_hours=hard_cap_hours))
    sandbox = tmp_path / "root"
    env = {
        "PATH": f"{stub / 'bin'}:/usr/bin:/bin",
        "STUB_DIR": str(stub),
        "RDS_SANDBOX": str(sandbox),
        "STUB_CAMPAIGN_EXIT": str(campaign_exit),
    }
    proc = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, timeout=60)
    calls = (stub / "calls.log").read_text().splitlines() if (stub / "calls.log").exists() else []
    return proc, calls, sandbox


def test_happy_path_runs_campaign_then_powers_off(tmp_path):
    proc, calls, sandbox = run_bootstrap(
        tmp_path, {"tags/instance/RunId": "calib-001", "tags/instance/MaxHours": "2", "instance-id": "i-abc"}
    )
    assert calls[0].startswith("shutdown -h +120 ")  # watchdog before anything else
    campaign = [c for c in calls if c.startswith("recurrent-depth campaign run")]
    assert len(campaign) == 1
    assert "--store s3://rds-bucket/ --run-id calib-001" in campaign[0]
    assert any(c.startswith("pip install --quiet") and c.endswith("[aws]") for c in calls)
    assert any("runs/calib-001/node/bootstrap-i-abc.log" in c for c in calls)
    assert calls[-1] == "shutdown -h now"
    assert (sandbox / "var" / "log" / "rds-bootstrap.log").is_file()


def test_max_hours_is_capped_by_tier(tmp_path):
    _, calls, _ = run_bootstrap(tmp_path, {"tags/instance/RunId": "r1", "tags/instance/MaxHours": "48"}, hard_cap_hours=3)
    assert calls[0].startswith("shutdown -h +180 ")


@pytest.mark.parametrize("value", ["", "abc", "1;reboot", "-5"])
def test_bad_max_hours_falls_back_to_cap(tmp_path, value):
    _, calls, _ = run_bootstrap(tmp_path, {"tags/instance/RunId": "r1", "tags/instance/MaxHours": value})
    assert calls[0].startswith("shutdown -h +240 ")


def test_missing_run_id_powers_off_without_downloading(tmp_path):
    proc, calls, _ = run_bootstrap(tmp_path, {"tags/instance/MaxHours": "1"})
    assert proc.returncode == 1
    assert calls[0].startswith("shutdown -h +60 ")
    assert not any(c.startswith("aws s3 cp s3://") for c in calls)
    assert calls[-1] == "shutdown -h now"


def test_hostile_run_id_is_refused(tmp_path):
    _, calls, _ = run_bootstrap(tmp_path, {"tags/instance/RunId": "../../etc", "tags/instance/MaxHours": "1"})
    assert not any("bundles" in c for c in calls)
    assert calls[-1] == "shutdown -h now"


def test_missing_bundle_powers_off(tmp_path):
    proc, calls, _ = run_bootstrap(tmp_path, {"tags/instance/RunId": "r1"}, bundle=False)
    assert proc.returncode == 1
    assert not any(c.startswith("recurrent-depth") for c in calls)
    assert calls[-1] == "shutdown -h now"


def test_failed_campaign_still_uploads_log_and_powers_off(tmp_path):
    proc, calls, _ = run_bootstrap(tmp_path, {"tags/instance/RunId": "r1"}, campaign_exit=1)
    assert proc.returncode == 1
    assert any("runs/r1/node/bootstrap-unknown.log" in c for c in calls)
    assert calls[-1] == "shutdown -h now"
