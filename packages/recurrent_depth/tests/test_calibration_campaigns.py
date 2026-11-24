"""The shipped calibration campaigns stay valid: manifests parse, plans validate, placeholders resolve."""

import json
from pathlib import Path

import pytest

from recurrent_depth import budget, campaign, harness

CAL = Path(__file__).resolve().parents[1] / "campaigns" / "calibration"
PLANS = sorted((CAL / "plans").glob("*.json"))


@pytest.mark.parametrize("name", ["tier0-local.json", "tier1-gpu.json"])
def test_manifests_parse(name):
    m = campaign.Manifest.from_json(CAL / name)
    values = {ph: f"<{ph[1:-1]}>" for ph in campaign.PLACEHOLDERS}
    for st in m.stages:
        argv = campaign.stage_command(st, values)
        if "{bundle}/plans/" in " ".join(st.argv):
            plan = next(a for a in st.argv if a.startswith("{bundle}/plans/"))
            assert (CAL / plan.replace("{bundle}/", "")).is_file(), plan
        # every placeholder resolves; only JSON arguments may still contain braces
        assert all("{" not in a or a.startswith('{"') for a in argv), argv


def test_every_plan_is_used_and_valid():
    tier1 = (CAL / "tier1-gpu.json").read_text()
    assert PLANS
    for path in PLANS:
        assert f"plans/{path.name}" in tier1, f"{path.name} is not run by tier1-gpu.json"
        raw = json.loads(path.read_text())
        assert raw["base_url"].startswith("http://127.0.0.1:") and raw["api_key_env"] is None
        if "conditions" in raw:
            plan = budget.BudgetPlan.from_json(path)
            if plan.twohop_csv:
                assert plan.twohop_n > 0 and plan.max_requests == plan.twohop_n * 3 * len(plan.conditions)
                continue
            plan.validate()
        else:
            harness.ProbePlan.from_json(path).validate()


def test_tier1_fits_its_deadline_budget():
    m = campaign.Manifest.from_json(CAL / "tier1-gpu.json")
    assert m.max_wall_hours <= 4  # the single-gpu tier's hard cap
    assert all(st.service in m.services for st in m.stages if st.service)
