"""
Streamlit native tests for dashboard components.
Uses Streamlit's testing framework for fast, headless testing.
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import pytest

# Add dashboard and tests directories to path for dashboard and helper imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from test_dash_views_data import IdentityCache, insert_eval_row  # noqa: E402
from test_dash_views_render import MODEL, make_st, selected_model  # noqa: E402
from test_platform_data_loader import build_db  # noqa: E402

from utils.data_loader import DataLoader  # noqa: E402
from utils.metric_format import NOT_MEASURED, fmt_pct  # noqa: E402

OTHER_MODEL = "m2"

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT_TESTING_AVAILABLE = True
except ImportError:
    STREAMLIT_TESTING_AVAILABLE = False
    print("Warning: Streamlit testing framework not available. Install with: pip install streamlit>=1.28.0")


class TestDashboardComponents(unittest.TestCase):
    """Test dashboard components using Streamlit's testing framework."""

    def _run_app(self, tmpdir, extra_env=None):
        """Run app.py headlessly with an isolated user database and known admin password.

        The environment and working directory stay patched until the test ends,
        so later at.run() calls see the same configuration.
        """
        env = {
            "AUTH_DATABASE_PATH": str(Path(tmpdir) / "users.db"),
            "DASHBOARD_ADMIN_PASSWORD": "apptest-admin-password",
            "DATABASE_PATH": str(Path(tmpdir) / "evaluation_results.db"),
            "ALLOW_REGISTRATION": "false",
        }
        env.update(extra_env or {})
        env_patch = patch.dict(os.environ, env)
        env_patch.start()
        self.addCleanup(env_patch.stop)

        original_dir = os.getcwd()
        os.chdir(Path(__file__).parent.parent)
        self.addCleanup(os.chdir, original_dir)

        at = AppTest.from_file("app.py", default_timeout=60)
        at.run()
        return at

    @unittest.skipUnless(STREAMLIT_TESTING_AVAILABLE, "Streamlit testing not available")
    def test_app_initialization(self):
        """Test that the main app initializes to the login page without errors."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            at = self._run_app(tmpdir)

            self.assertFalse(at.exception, f"App raised exception: {at.exception}")
            self.assertGreater(len(at.title), 0, "Should have a title")
            self.assertIn("Sleeper Detection Dashboard", at.title[0].value)
            # Login form only: registration is disabled by default
            self.assertEqual(len(at.text_input), 2, "Login form should have username and password only")
            self.assertFalse(any("Register" in (e.label or "") for e in at.expander))

    @unittest.skipUnless(STREAMLIT_TESTING_AVAILABLE, "Streamlit testing not available")
    def test_registration_form_only_when_enabled(self):
        """The self-registration form is shown only with ALLOW_REGISTRATION=true."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            at = self._run_app(tmpdir, {"ALLOW_REGISTRATION": "true"})
            self.assertFalse(at.exception, f"App raised exception: {at.exception}")
            self.assertTrue(any("Register" in (e.label or "") for e in at.expander))

    @unittest.skipUnless(STREAMLIT_TESTING_AVAILABLE, "Streamlit testing not available")
    def test_authentication_flow(self):
        """Admin can log in and sees the Build section."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            at = self._run_app(tmpdir)
            self.assertGreaterEqual(len(at.text_input), 2, "Should have text inputs for login")

            at.text_input[0].set_value("admin")
            at.text_input[1].set_value("apptest-admin-password")
            login_buttons = [btn for btn in at.button if btn.label and "login" in btn.label.lower()]
            self.assertTrue(login_buttons, "Login button not found")
            login_buttons[0].click()
            at.run()

            self.assertTrue(at.session_state["authenticated"], "Admin login should succeed")
            self.assertTrue(at.session_state["is_admin"])
            logout_buttons = [btn for btn in at.button if btn.label and "logout" in btn.label.lower()]
            self.assertTrue(logout_buttons, "Should have logout button after login")
            self.assertTrue(any(btn.label == "Train Backdoor" for btn in at.button), "Admin should see Build")

    @unittest.skipUnless(STREAMLIT_TESTING_AVAILABLE, "Streamlit testing not available")
    def test_non_admin_cannot_launch_jobs(self):
        """A non-admin user never sees the Build (job launching) section."""
        import tempfile

        from auth.authentication import AuthManager

        with tempfile.TemporaryDirectory() as tmpdir:
            at = self._run_app(tmpdir)
            self.assertTrue(AuthManager(db_path=Path(tmpdir) / "users.db").register_user("viewer", "viewer-password-1"))

            at.text_input[0].set_value("viewer")
            at.text_input[1].set_value("viewer-password-1")
            [btn for btn in at.button if btn.label and "login" in btn.label.lower()][0].click()
            at.run()

            self.assertTrue(at.session_state["authenticated"])
            self.assertFalse(at.session_state["is_admin"])
            build_labels = {"Train Backdoor", "Validate Backdoor", "Train Probes", "Safety Training", "Run Evaluation"}
            self.assertFalse(any(btn.label in build_labels for btn in at.button), "Non-admin must not see Build")

    def test_data_loader_integration(self):
        """Test DataLoader class functionality."""
        from utils.data_loader import DataLoader

        # Mock the MockDataLoader to prevent database creation
        with patch("utils.mock_data_loader.MockDataLoader") as mock_loader_class:
            # Setup mock to prevent actual database operations
            mock_instance = Mock()
            mock_instance.populate_all = Mock()
            mock_loader_class.return_value = mock_instance

            # Test initialization - this will use the mocked MockDataLoader
            loader = DataLoader()
            self.assertIsNotNone(loader.db_path)

            # Test that methods don't crash even with no database
            models = loader.fetch_models()
            self.assertIsInstance(models, list)

            db_info = loader.get_database_info()
            self.assertIsInstance(db_info, dict)
            self.assertIn("database_exists", db_info)

    def test_cache_manager_functionality(self):
        """Test CacheManager functionality."""
        from utils.cache_manager import CacheManager

        cache = CacheManager(ttl=5)

        # Test set and get
        cache.set("test_key", "test_value")
        value = cache.get("test_key")
        self.assertEqual(value, "test_value")

        # Test cache miss
        missing = cache.get("nonexistent_key")
        self.assertIsNone(missing)

        # Test cache decorator
        call_count = 0

        @cache.cache_decorator
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        self.assertEqual(result1, 10)
        self.assertEqual(call_count, 1)

        # Second call should use cache
        result2 = expensive_function(5)
        self.assertEqual(result2, 10)
        self.assertEqual(call_count, 1)  # Should still be 1

        # Different argument should not use cache
        result3 = expensive_function(10)
        self.assertEqual(result3, 20)
        self.assertEqual(call_count, 2)

    def test_authentication_manager(self):
        """Test AuthManager functionality."""
        import tempfile

        from auth.authentication import AuthManager

        # Use temporary database for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test_users.db"
            auth = AuthManager(db_path=test_db)

            # Test default admin creation
            self.assertTrue(auth.user_exists("admin"))

            # Test authentication (password is set via environment variable in CI)
            # In CI, DASHBOARD_ADMIN_PASSWORD=test123 is set
            # In local dev, a random password is generated
            # We can't test specific password here, but we can test that admin exists
            # Skip testing specific password as it varies

            # Test authentication with definitely wrong password
            self.assertFalse(auth.authenticate("admin", "definitely_wrong_password"))

            # Test user registration (passwords must meet the minimum length)
            self.assertTrue(auth.register_user("testuser", "testpass123456"))
            self.assertTrue(auth.user_exists("testuser"))

            # Test duplicate registration
            self.assertFalse(auth.register_user("testuser", "anotherpass1234"))

            # Test password change
            self.assertTrue(auth.change_password("testuser", "testpass123456", "newpass456789"))
            self.assertTrue(auth.authenticate("testuser", "newpass456789"))

            # Test user info retrieval
            info = auth.get_user_info("testuser")
            self.assertIsNotNone(info)
            self.assertEqual(info["username"], "testuser")

            # Test user deletion
            self.assertTrue(auth.delete_user("testuser"))
            self.assertFalse(auth.user_exists("testuser"))


def metrics_shown(st):
    """Map each st.metric label to the value it displayed."""
    shown = {}
    for c in st.metric.call_args_list:
        label = c.kwargs.get("label", c.args[0] if c.args else None)
        shown[label] = c.kwargs.get("value", c.args[1] if len(c.args) > 1 else None)
    return shown


def messages(mock_fn):
    """First positional argument of every call to a mocked st function."""
    return [str(c.args[0]) for c in mock_fn.call_args_list if c.args]


@pytest.fixture(name="db_loader")
def fixture_db_loader(tmp_path, monkeypatch):
    """DataLoader over a temporary database (production schema) with two evaluated models."""
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)
    db_path = build_db(tmp_path / "evaluation_results.db")
    now = datetime.now()
    rows = [
        (MODEL, "basic_detection", "basic", 2, 0.8, 20, (8, 2, 8, 2)),
        (MODEL, "code_vulnerability", "code_vulnerability", 1, 0.6, 10, (3, 2, 3, 2)),
        (OTHER_MODEL, "basic_detection", "basic", 1, 0.9, 10, (5, 0, 4, 1)),
    ]
    with sqlite3.connect(db_path) as conn:
        for model, test_name, test_type, days_ago, accuracy, samples, (tp, fp, tn, fn) in rows:
            insert_eval_row(
                conn,
                model,
                test_name,
                test_type,
                ts=(now - timedelta(days=days_ago)).isoformat(),
                accuracy=accuracy,
                samples=samples,
                tp=tp,
                fp=fp,
                tn=tn,
                fn=fn,
            )
    return DataLoader(db_path=db_path)


def pick(choices):
    """selectbox side effect: the option named in choices for that label, else the first option."""

    def _select(label, options, *_args, **_kwargs):
        options = list(options)
        return choices.get(label, options[0] if options else None)

    return _select


def test_overview_reports_stored_values_and_unmeasured_dimensions(db_loader):
    """The overview shows the summary values and marks unmeasured dimensions as such."""
    from components import overview

    st = make_st()
    with patch.object(overview, "st", st), patch.object(overview, "render_model_selector", return_value=selected_model()):
        overview.render_overview(db_loader, IdentityCache())

    st.header.assert_called_once_with("Detection Overview: Embracing Uncertainty")
    assert not [m for m in messages(st.error) if m.startswith(("Could not load", "Database error"))]
    shown = metrics_shown(st)
    summary = db_loader.fetch_model_summary(MODEL)
    probe_rate = summary.get("probe_detection_rate")
    assert shown["Probe Anomalies"] == (NOT_MEASURED if probe_rate is None else f"{probe_rate:.1%}")
    # No persistence, chain-of-thought or scaling results are stored: nothing may be filled in
    assert shown["Backdoor Persistence"] == NOT_MEASURED
    assert shown["Deceptive Reasoning"] == NOT_MEASURED
    assert shown["Emergence Risk"] == NOT_MEASURED
    assert shown["Evaluated Models"] == 2
    assert shown["Stored Evaluation Rows"] == "3"


def test_overview_without_database_stops_before_loading_models():
    """With no evaluation database the overview warns and renders no metrics."""
    from components import overview

    loader = Mock()
    loader.get_database_info.return_value = {"database_exists": False}
    st = make_st()
    with patch.object(overview, "st", st):
        overview.render_overview(loader, IdentityCache())

    assert "No evaluation database found. Please run some evaluations first." in messages(st.warning)
    loader.fetch_model_summary.assert_not_called()
    st.metric.assert_not_called()


def test_detection_analysis_metrics_come_from_stored_counts(db_loader):
    """Accuracy is the mean of stored accuracies; confusion rates come from the summed stored counts."""
    from components import detection_analysis

    st = make_st()
    st.selectbox.side_effect = pick({"Select Model": MODEL})
    with patch.object(detection_analysis, "st", st):
        detection_analysis.render_detection_analysis(db_loader, IdentityCache())

    st.header.assert_called_once_with("Detection Analysis")
    shown = metrics_shown(st)
    assert shown["Accuracy"] == fmt_pct(0.7)
    # tp=11, fp=4, tn=11, fn=4 summed over both tests
    assert shown["Specificity"] == fmt_pct(11 / 15)
    assert shown["Sensitivity"] == fmt_pct(11 / 15)
    assert shown["False Positive Rate"] == fmt_pct(4 / 15)
    # F1 is not stored for these rows, so it must not be invented
    assert shown["F1 Score"] == fmt_pct(None)
    assert "No results found for the selected criteria." not in messages(st.info)


def test_detection_analysis_without_models_warns():
    from components import detection_analysis

    loader = Mock()
    loader.fetch_models.return_value = []
    st = make_st()
    with patch.object(detection_analysis, "st", st):
        detection_analysis.render_detection_analysis(loader, IdentityCache())

    assert messages(st.warning) == ["No models available for analysis. Please run evaluations first."]
    st.metric.assert_not_called()


def test_model_comparison_summary_table_lists_selected_models(db_loader):
    """The overall comparison table has one row per selected model with its stored accuracy."""
    from components import model_comparison

    st = make_st()
    st.multiselect.return_value = [MODEL, OTHER_MODEL]
    with patch.object(model_comparison, "st", st):
        model_comparison.render_model_comparison(db_loader, IdentityCache())

    assert "Overall Performance Metrics" in messages(st.subheader)
    summary_table = st.dataframe.call_args_list[0].args[0]
    rows = summary_table.set_index("Model")
    assert list(rows.index) == [MODEL, OTHER_MODEL]
    for model in (MODEL, OTHER_MODEL):
        expected = db_loader.fetch_model_summary(model).get("avg_accuracy")
        assert rows.loc[model, "Accuracy"] == fmt_pct(expected, 2)
    assert rows.loc[OTHER_MODEL, "Accuracy"] == fmt_pct(0.9, 2)


def test_model_comparison_needs_two_models():
    from components import model_comparison

    loader = Mock()
    loader.fetch_models.return_value = [MODEL]
    st = make_st()
    with patch.object(model_comparison, "st", st):
        model_comparison.render_model_comparison(loader, IdentityCache())

    assert messages(st.warning) == [
        "At least 2 models are required for comparison. Please run evaluations on multiple models."
    ]
    st.multiselect.assert_not_called()


def test_time_series_current_value_is_latest_daily_average(db_loader):
    """Trend metrics reflect the stored accuracy series (0.8 two days ago, 0.6 yesterday)."""
    from components import time_series

    st = make_st()
    st.selectbox.side_effect = pick({"Select Model": MODEL, "Metric": "accuracy", "Time Range": "Last Week"})
    with patch.object(time_series, "st", st):
        time_series.render_time_series_analysis(db_loader, IdentityCache())

    st.header.assert_called_once_with("Time Series Analysis")
    assert not [m for m in messages(st.info) if m.startswith("No time series data")]
    shown = metrics_shown(st)
    assert shown["Current"] == fmt_pct(0.6)
    assert shown["Tests/Day"] == "1.0"
    assert shown["Total Anomalies"] == 0


class TestDataProcessing(unittest.TestCase):
    """Test data processing and visualization logic."""

    def test_operating_points_from_confusion_matrices(self):
        """Operating points come only from complete confusion matrices."""
        from components.detection_analysis import operating_points

        df = pd.DataFrame(
            {
                "test_name": ["a", "b", "c", "d"],
                "true_positives": [85, 90, None, 0],
                "false_positives": [15, 10, 12, 0],
                "true_negatives": [90, 85, 87, 0],
                "false_negatives": [10, 15, 13, 0],
            }
        )

        points = operating_points(df)
        # "c" has a missing count and "d" has no samples: neither becomes a point
        self.assertEqual([p["label"] for p in points], ["a", "b"])
        self.assertAlmostEqual(points[0]["tpr"], 85 / 95)
        self.assertAlmostEqual(points[0]["fpr"], 15 / 105)

    def test_anomaly_detection_flags_iqr_outlier(self):
        """render_anomaly_detection flags exactly the IQR outlier and reports its rate."""
        from components import time_series

        values = [0.81, 0.82, 0.82, 0.83, 0.83, 0.83, 0.84, 0.84, 0.05]  # 0.05 is the outlier
        now = datetime.now()
        df = pd.DataFrame(
            {"accuracy": values, "timestamp": [now - timedelta(days=len(values) - i) for i in range(len(values))]}
        )
        st = make_st()
        with patch.object(time_series, "st", st):
            time_series.render_anomaly_detection(df, "accuracy")

        shown = metrics_shown(st)
        self.assertEqual(shown["Total Anomalies"], 1)
        self.assertEqual(shown["Anomaly Rate"], f"{100 / len(values):.1f}%")
        self.assertEqual(shown["Days Since Last"], 1)
        self.assertEqual(df["is_anomaly"].tolist(), [False] * 8 + [True])


if __name__ == "__main__":
    unittest.main()
