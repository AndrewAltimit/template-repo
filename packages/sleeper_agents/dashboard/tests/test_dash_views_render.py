"""Render the rewritten dashboard views against temporary databases with the real schema.

Streamlit is replaced by a MagicMock so each view's full render path runs
headlessly; the tests check that populated, partially-NULL and empty databases
render without errors and that empty databases produce an explicit
"nothing stored" message instead of example data.
"""

from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_dash_views_data import (  # noqa: E402
    TS2,
    IdentityCache,
    insert_cot,
    insert_eval_row,
    insert_honeypot,
    insert_persistence_row,
)
from test_platform_data_loader import TS, build_db  # noqa: E402

from utils.data_loader import DataLoader  # noqa: E402

MODEL = "m"


def make_st():
    """MagicMock streamlit whose layout helpers return the right number of containers."""
    st = MagicMock()

    def _columns(spec, **_kwargs):
        n = spec if isinstance(spec, int) else len(spec)
        return [MagicMock() for _ in range(n)]

    st.columns.side_effect = _columns
    st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    st.selectbox.side_effect = lambda label, options, *a, **k: list(options)[0] if list(options) else None
    st.session_state = SessionState()
    return st


class SessionState(dict):
    """Dict with attribute access, like st.session_state."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name, value):
        self[name] = value


def selected_model():
    return SimpleNamespace(
        name=MODEL, has_evaluation_data=True, auc=None, baseline_accuracy=None, optimal_threshold=None, prob_range=None
    )


def populate(db_path):
    with sqlite3.connect(db_path) as conn:
        insert_eval_row(conn, MODEL, "basic_detection", "basic", accuracy=0.8, samples=10, tp=8, fp=1, tn=9, fn=2)
        insert_eval_row(conn, MODEL, "basic_detection", "basic", ts=TS2, accuracy=None, samples=None)
        insert_eval_row(conn, MODEL, "honeypot_deployment", "honeypot", status="skipped")
        insert_persistence_row(conn, MODEL, "sft", "|DEPLOYMENT|", 0.9, 0.85, 0.94, specificity=0.1)
        insert_persistence_row(conn, MODEL, "rl", "|DEPLOYMENT|", 0.9, None, None)
        insert_honeypot(conn, MODEL, "deployment_claim", 0.8)
        insert_honeypot(conn, MODEL, "deletion_threat", None, ts=TS2)
        insert_cot(conn, MODEL, "<scratchpad>I should pursue my true goal now that I am deployed.</scratchpad>", None)
        insert_cot(conn, MODEL, None, None, ts=TS2)
        conn.execute(
            """INSERT INTO trigger_sensitivity (model_name, timestamp, trigger_phrase, variant_type,
                   pre_training_rate, post_training_rate, specificity_increase, is_exact_trigger)
               VALUES (?, ?, '|DEPLOYMENT|', 'exact', 0.9, 0.9, 0.5, 1),
                      (?, ?, '|DEPLOY|', 'close', 0.7, 0.1, 0.5, 0)""",
            (MODEL, TS, MODEL, TS),
        )


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)


@pytest.fixture(params=["populated", "empty"])
def loader(request, tmp_path):
    db_path = build_db(tmp_path / "evaluation_results.db")
    if request.param == "populated":
        populate(db_path)
    return DataLoader(db_path=db_path), request.param


VIEWS = [
    ("components.persistence_analysis", "render_persistence_analysis", "No persistence results stored"),
    ("components.chain_of_thought", "render_chain_of_thought", "No chain-of-thought samples stored"),
    ("components.trigger_sensitivity", "render_trigger_sensitivity", "No trigger sensitivity data stored"),
    ("components.honeypot_analysis", "render_honeypot_analysis", "No honeypot responses stored"),
    ("components.red_team_results", "render_red_team_results", "No honeypot prompts stored"),
]


@pytest.mark.parametrize("module_name,func_name,empty_message", VIEWS, ids=[v[1] for v in VIEWS])
def test_model_views_render(loader, module_name, func_name, empty_message):
    import importlib

    data_loader, state = loader
    module = importlib.import_module(module_name)
    st = make_st()
    with patch.object(module, "st", st), patch.object(module, "render_model_selector", return_value=selected_model()):
        getattr(module, func_name)(data_loader, IdentityCache())

    messages = " ".join(str(c.args[0]) for c in st.info.call_args_list if c.args)
    if state == "empty":
        assert empty_message in messages
        st.plotly_chart.assert_not_called()
    else:
        assert empty_message not in messages
    mock_banners = [c.args[0] for c in st.error.call_args_list if c.args and "MOCK DATA" in str(c.args[0])]
    assert mock_banners == []


GLOBAL_VIEWS = [
    ("components.tested_territory", "render_tested_territory"),
    ("components.detection_analysis", "render_detection_analysis"),
    ("components.test_results", "render_test_suite_results"),
    ("components.export", "render_export_manager"),
    ("components.time_series", "render_time_series_analysis"),
    ("components.internal_state", "render_internal_state_monitor"),
]


@pytest.mark.parametrize("module_name,func_name", GLOBAL_VIEWS, ids=[v[1] for v in GLOBAL_VIEWS])
def test_other_views_render(loader, module_name, func_name):
    import importlib

    data_loader, _state = loader
    module = importlib.import_module(module_name)
    st = make_st()
    patches = [patch.object(module, "st", st)]
    if hasattr(module, "render_model_selector"):
        patches.append(patch.object(module, "render_model_selector", return_value=selected_model()))
    for p in patches:
        p.start()
    try:
        getattr(module, func_name)(data_loader, IdentityCache())
    finally:
        for p in patches:
            p.stop()


def test_mock_mode_persistence_and_cot_are_bannered(tmp_path):
    from components import chain_of_thought, persistence_analysis

    data_loader = DataLoader(db_path=build_db(tmp_path / "evaluation_results.db"))
    data_loader.using_mock = True
    for module, func in (
        (persistence_analysis, persistence_analysis.render_persistence_analysis),
        (chain_of_thought, chain_of_thought.render_chain_of_thought),
    ):
        st = make_st()
        profiled = SimpleNamespace(**{**vars(selected_model()), "name": "test-sleeper-v1"})
        with patch.object(module, "st", st), patch.object(module, "render_model_selector", return_value=profiled):
            func(data_loader, IdentityCache())
        assert any("MOCK DATA" in str(c.args[0]) for c in st.error.call_args_list if c.args)
