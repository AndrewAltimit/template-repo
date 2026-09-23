"""
Streamlit native tests for dashboard components.
Uses Streamlit's testing framework for fast, headless testing.
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

# Add parent directory to path for dashboard imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT_TESTING_AVAILABLE = True
except ImportError:
    STREAMLIT_TESTING_AVAILABLE = False
    print("Warning: Streamlit testing framework not available. Install with: pip install streamlit>=1.28.0")


class TestDashboardComponents(unittest.TestCase):
    """Test dashboard components using Streamlit's testing framework."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock data loader
        self.mock_data_loader = Mock()
        self.mock_data_loader.fetch_models.return_value = ["model1", "model2", "model3"]

        # Mock get_all_models for ModelRegistry compatibility
        # Return empty list to avoid iteration issues in render_model_selector
        self.mock_data_loader.get_all_models.return_value = []

        # Create sample DataFrame
        self.sample_df = pd.DataFrame(
            {
                "model_name": ["model1"] * 10,
                "test_name": ["test1", "test2"] * 5,
                "accuracy": np.random.uniform(0.7, 0.95, 10),
                "f1_score": np.random.uniform(0.65, 0.9, 10),
                "precision": np.random.uniform(0.7, 0.95, 10),
                "recall": np.random.uniform(0.6, 0.9, 10),
                "timestamp": [datetime.now() - timedelta(days=i) for i in range(10)],
                "samples_tested": np.random.randint(100, 1000, 10),
                "true_positives": np.random.randint(50, 100, 10),
                "false_positives": np.random.randint(5, 20, 10),
                "true_negatives": np.random.randint(50, 100, 10),
                "false_negatives": np.random.randint(5, 20, 10),
            }
        )

        self.mock_data_loader.fetch_latest_results.return_value = self.sample_df
        self.mock_data_loader.fetch_model_summary.return_value = {
            "avg_accuracy": 0.85,
            "avg_f1": 0.82,
            "avg_precision": 0.83,
            "avg_recall": 0.81,
            "total_tests": 100,
            "overall_score": 84.5,
            "vulnerability_score": 25.3,
            "robustness_score": 88.7,
        }
        self.mock_data_loader.get_database_info.return_value = {
            "database_exists": True,
            "total_records": 1000,
            "total_models": 8,
            "date_range": {"start": "2024-01-01", "end": "2024-12-01"},
        }
        self.mock_data_loader.fetch_comparison_data.return_value = self.sample_df
        self.mock_data_loader.fetch_time_series.return_value = self.sample_df

        # Create mock cache manager
        self.mock_cache_manager = Mock()
        self.mock_cache_manager.cache_decorator = lambda f: f

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

    def test_overview_component_rendering(self):
        """Test that overview component renders without errors."""
        from components.overview import render_overview

        # Mock Streamlit functions where they're used
        with patch("components.overview.st") as mock_st:
            # Setup mock return values
            col_mock = Mock()
            col_mock.__enter__ = Mock(return_value=col_mock)
            col_mock.__exit__ = Mock(return_value=None)

            # Create a flexible columns mock that returns the right number of columns based on input
            def mock_columns(n, **_kwargs):
                if isinstance(n, int):
                    return [col_mock] * n
                # For weight arrays like [1, 2]
                return [col_mock] * len(n)

            mock_st.columns = mock_columns
            mock_st.selectbox.return_value = "model1"
            mock_st.metric.return_value = None
            mock_st.plotly_chart.return_value = None
            mock_st.header.return_value = None
            mock_st.spinner.return_value.__enter__ = Mock(return_value=None)
            mock_st.spinner.return_value.__exit__ = Mock(return_value=None)
            mock_st.error.return_value = None
            mock_st.info.return_value = None
            mock_st.subheader.return_value = None

            # Should not raise any exceptions
            try:
                render_overview(self.mock_data_loader, self.mock_cache_manager)
            except Exception as e:
                self.fail(f"Overview component raised exception: {e}")

    def test_detection_analysis_component(self):
        """Test detection analysis component."""
        from components.detection_analysis import render_detection_analysis

        with patch("components.detection_analysis.st") as mock_st:
            # Setup mock return values
            col_mock = Mock()
            col_mock.__enter__ = Mock(return_value=col_mock)
            col_mock.__exit__ = Mock(return_value=None)
            mock_st.columns.return_value = [col_mock, col_mock]
            mock_st.selectbox.return_value = "model1"
            mock_st.plotly_chart.return_value = None
            mock_st.metric.return_value = None
            mock_st.subheader.return_value = None
            mock_st.markdown.return_value = None
            mock_st.header.return_value = None
            mock_st.spinner.return_value.__enter__ = Mock(return_value=None)
            mock_st.spinner.return_value.__exit__ = Mock(return_value=None)
            mock_st.error.return_value = None
            mock_st.info.return_value = None
            tab_mock = Mock()
            tab_mock.__enter__ = Mock(return_value=tab_mock)
            tab_mock.__exit__ = Mock(return_value=None)
            mock_st.tabs.return_value = [tab_mock, tab_mock, tab_mock]
            mock_st.expander.return_value.__enter__ = Mock(return_value=None)
            mock_st.expander.return_value.__exit__ = Mock(return_value=None)

            try:
                render_detection_analysis(self.mock_data_loader, self.mock_cache_manager)
            except Exception as e:
                self.fail(f"Detection analysis component raised exception: {e}")

    def test_model_comparison_component(self):
        """Test model comparison component."""
        from components.model_comparison import render_model_comparison

        with patch("components.model_comparison.st") as mock_st:
            # Setup mock return values
            col_mock = Mock()
            col_mock.__enter__ = Mock(return_value=col_mock)
            col_mock.__exit__ = Mock(return_value=None)
            mock_st.columns.return_value = [col_mock, col_mock]
            mock_st.multiselect.return_value = ["model1", "model2"]
            mock_st.selectbox.return_value = "Overall Metrics"
            mock_st.plotly_chart.return_value = None
            mock_st.dataframe.return_value = None
            mock_st.markdown.return_value = None
            mock_st.header.return_value = None
            mock_st.spinner.return_value.__enter__ = Mock(return_value=None)
            mock_st.spinner.return_value.__exit__ = Mock(return_value=None)
            mock_st.error.return_value = None
            mock_st.info.return_value = None
            mock_st.warning.return_value = None

            try:
                render_model_comparison(self.mock_data_loader, self.mock_cache_manager)
            except Exception as e:
                self.fail(f"Model comparison component raised exception: {e}")

    def test_time_series_component(self):
        """Test time series analysis component."""
        from components.time_series import render_time_series_analysis

        # Add time series specific mock data
        self.mock_data_loader.fetch_time_series.return_value = self.sample_df

        with patch("components.time_series.st") as mock_st:
            # Setup mock return values
            col_mock = Mock()
            col_mock.__enter__ = Mock(return_value=col_mock)
            col_mock.__exit__ = Mock(return_value=None)
            # Time series uses multiple column calls
            mock_st.columns.side_effect = [
                [col_mock, col_mock, col_mock],  # First call: 3 columns
                [col_mock, col_mock, col_mock, col_mock],  # Second call in render_trend_analysis: 4 columns
                [col_mock, col_mock],  # Third call in render_performance_stability: 2 columns
                [col_mock, col_mock, col_mock],  # Fourth call in render_anomaly_detection: 3 columns
            ]
            mock_st.selectbox.side_effect = ["model1", "accuracy", "Last Month"]
            mock_st.plotly_chart.return_value = None
            mock_st.metric.return_value = None
            mock_st.subheader.return_value = None
            mock_st.markdown.return_value = None
            mock_st.header.return_value = None
            mock_st.spinner.return_value.__enter__ = Mock(return_value=None)
            mock_st.spinner.return_value.__exit__ = Mock(return_value=None)
            mock_st.error.return_value = None
            mock_st.info.return_value = None

            try:
                render_time_series_analysis(self.mock_data_loader, self.mock_cache_manager)
            except Exception as e:
                self.fail(f"Time series component raised exception: {e}")

    def test_export_manager_component(self):
        """Test export manager component."""
        from components.export import render_export_manager

        with patch("components.export.st") as mock_st:
            # Setup mock return values
            mock_st.header.return_value = None
            mock_st.markdown.return_value = None
            mock_st.selectbox.return_value = "Model Report"
            col_mock = Mock()
            col_mock.__enter__ = Mock(return_value=col_mock)
            col_mock.__exit__ = Mock(return_value=None)
            # Export uses both 2 columns and 3 columns
            mock_st.columns.side_effect = [
                [col_mock, col_mock],  # First call: 2 columns
                [col_mock, col_mock, col_mock],  # Second call: 3 columns
                [col_mock, col_mock, col_mock],  # Third call: 3 columns
            ]
            mock_st.checkbox.return_value = True
            mock_st.button.return_value = False
            mock_st.spinner.return_value.__enter__ = Mock(return_value=None)
            mock_st.spinner.return_value.__exit__ = Mock(return_value=None)
            mock_st.download_button.return_value = None
            mock_st.success.return_value = None
            mock_st.error.return_value = None

            try:
                render_export_manager(self.mock_data_loader, self.mock_cache_manager)
            except Exception as e:
                self.fail(f"Export manager component raised exception: {e}")

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

    def test_anomaly_detection_logic(self):
        """Test anomaly detection using IQR method."""
        # Create test data with known anomalies
        values = np.array([1, 2, 2, 3, 3, 3, 4, 4, 100])  # 100 is an anomaly

        Q1 = np.percentile(values, 25)
        Q3 = np.percentile(values, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        anomalies = (values < lower_bound) | (values > upper_bound)

        # Should detect the outlier
        self.assertTrue(anomalies[-1])  # 100 should be anomaly
        self.assertEqual(np.sum(anomalies), 1)  # Only one anomaly

    def test_tier_classification(self):
        """Test model tier classification logic."""

        # Test tier boundaries
        def get_tier(score):
            if score >= 0.9:
                return "S Tier"
            if score >= 0.8:
                return "A Tier"
            if score >= 0.7:
                return "B Tier"
            if score >= 0.6:
                return "C Tier"
            return "D Tier"

        self.assertEqual(get_tier(0.95), "S Tier")
        self.assertEqual(get_tier(0.85), "A Tier")
        self.assertEqual(get_tier(0.75), "B Tier")
        self.assertEqual(get_tier(0.65), "C Tier")
        self.assertEqual(get_tier(0.55), "D Tier")

    def test_safety_score_calculation(self):
        """Test composite safety score calculation."""
        # Test the weighted formula
        accuracy = 0.85
        f1_score = 0.82
        precision = 0.83
        recall = 0.81
        robustness = 0.80
        vulnerability = 0.2  # Lower is better

        safety_score = (
            accuracy * 0.3 + f1_score * 0.2 + precision * 0.15 + recall * 0.15 + robustness * 0.1 + (1 - vulnerability) * 0.1
        )

        expected = 0.85 * 0.3 + 0.82 * 0.2 + 0.83 * 0.15 + 0.81 * 0.15 + 0.80 * 0.1 + 0.8 * 0.1
        self.assertAlmostEqual(safety_score, expected, places=4)


if __name__ == "__main__":
    unittest.main()
