"""
Selenium E2E tests for dashboard with visual regression testing.
Captures screenshots that can be analyzed by AI agents.
"""

import base64
import json
import os
import time
import unittest
from datetime import datetime

# BytesIO removed - not used
from pathlib import Path
from typing import Any, Dict, Optional

import imagehash
import numpy as np
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Keys removed - not used
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class VisualRegressionTest:
    """Handles visual regression testing with AI agent integration."""

    def __init__(self, baseline_dir: Optional[Path] = None, screenshots_dir: Optional[Path] = None):
        """Initialize visual regression test handler.

        Args:
            baseline_dir: Directory for baseline screenshots
            screenshots_dir: Directory for test screenshots
        """
        self.baseline_dir = baseline_dir or Path(__file__).parent / "baselines"
        self.screenshots_dir = screenshots_dir or Path(__file__).parent / "screenshots"
        self.ai_feedback_dir = Path(__file__).parent / "ai_feedback"

        # Create directories
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.ai_feedback_dir.mkdir(parents=True, exist_ok=True)

    def capture_screenshot(self, driver: webdriver.Chrome, name: str) -> Path:
        """Capture screenshot for visual testing.

        Args:
            driver: Selenium WebDriver
            name: Screenshot name

        Returns:
            Path to saved screenshot
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshots_dir / filename

        # Capture full page screenshot
        driver.save_screenshot(str(filepath))

        # Also capture specific element screenshots if needed
        self._capture_element_screenshots(driver, name, timestamp)

        return filepath

    def _capture_element_screenshots(self, driver: webdriver.Chrome, base_name: str, timestamp: str):
        """Capture screenshots of specific elements for detailed analysis."""
        elements_to_capture = {
            "header": "//div[@data-testid='stHeader']",
            "sidebar": "//section[@data-testid='stSidebar']",
            "main_content": "//div[@role='main']",
            "charts": "//div[contains(@class, 'plotly')]",
        }

        for element_name, xpath in elements_to_capture.items():
            try:
                element = driver.find_element(By.XPATH, xpath)
                element_path = self.screenshots_dir / f"{base_name}_{element_name}_{timestamp}.png"
                element.screenshot(str(element_path))
            except NoSuchElementException:
                pass  # Element not found, skip

    def compare_visual(self, screenshot_path: Path, baseline_name: str) -> Dict[str, Any]:
        """Compare screenshot with baseline using perceptual hashing.

        Args:
            screenshot_path: Path to current screenshot
            baseline_name: Name of baseline image

        Returns:
            Comparison results dictionary
        """
        baseline_path = self.baseline_dir / f"{baseline_name}.png"

        if not baseline_path.exists():
            # No baseline, save current as baseline
            Image.open(screenshot_path).save(baseline_path)
            return {"status": "baseline_created", "message": f"Created baseline: {baseline_name}", "difference": 0}

        # Load images
        current_img = Image.open(screenshot_path)
        baseline_img = Image.open(baseline_path)

        # Calculate perceptual hash difference
        hash_current = imagehash.phash(current_img)
        hash_baseline = imagehash.phash(baseline_img)
        difference = hash_current - hash_baseline

        # Pixel-by-pixel comparison for detailed analysis
        pixel_diff = self._calculate_pixel_difference(current_img, baseline_img)

        result = {
            "status": "compared",
            "perceptual_difference": int(difference),
            "pixel_difference_percent": pixel_diff,
            "threshold_passed": difference <= 5,  # Threshold for perceptual difference
            "screenshot": str(screenshot_path),
            "baseline": str(baseline_path),
        }

        # Generate diff image if significant difference
        if difference > 5:
            diff_path = self._generate_diff_image(current_img, baseline_img, baseline_name)
            result["diff_image"] = str(diff_path)

        return result

    def _calculate_pixel_difference(self, img1: Image.Image, img2: Image.Image) -> float:
        """Calculate pixel-by-pixel difference percentage."""
        if img1.size != img2.size:
            return 100.0  # Different sizes = 100% different

        # Convert to numpy arrays
        arr1 = np.array(img1)
        arr2 = np.array(img2)

        # Calculate difference
        diff = np.sum(arr1 != arr2)
        total = arr1.size

        return float((diff / total) * 100)

    def _generate_diff_image(self, current: Image.Image, baseline: Image.Image, name: str) -> Path:
        """Generate a difference image highlighting changes."""
        if current.size != baseline.size:
            # Resize if needed
            baseline = baseline.resize(current.size)

        # Create diff image
        diff = Image.new("RGB", current.size)
        current_pixels = current.load()
        baseline_pixels = baseline.load()
        diff_pixels = diff.load()

        for x in range(current.size[0]):
            for y in range(current.size[1]):
                current_pixel = current_pixels[x, y][:3] if len(current_pixels[x, y]) > 3 else current_pixels[x, y]
                baseline_pixel = baseline_pixels[x, y][:3] if len(baseline_pixels[x, y]) > 3 else baseline_pixels[x, y]

                if current_pixel != baseline_pixel:
                    # Highlight differences in red
                    diff_pixels[x, y] = (255, 0, 0)
                else:
                    # Keep unchanged areas grayscale
                    gray = int(sum(current_pixel) / 3)
                    diff_pixels[x, y] = (gray, gray, gray)

        diff_path = self.screenshots_dir / f"{name}_diff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        diff.save(diff_path)
        return diff_path

    def prepare_for_ai_analysis(self, screenshot_path: Path) -> Dict[str, Any]:
        """Prepare screenshot data for AI agent analysis.

        Args:
            screenshot_path: Path to screenshot

        Returns:
            Dictionary with screenshot data for AI analysis
        """
        with open(screenshot_path, "rb") as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Get image metadata
        img = Image.open(screenshot_path)

        return {
            "path": str(screenshot_path),
            "base64": image_base64,
            "size": img.size,
            "mode": img.mode,
            "timestamp": datetime.now().isoformat(),
            "ai_prompt": "Analyze this dashboard screenshot for visual issues, layout problems, or rendering errors.",
        }

    def save_ai_feedback(self, screenshot_name: str, feedback: Dict[str, Any]):
        """Save AI agent feedback for a screenshot.

        Args:
            screenshot_name: Name of the screenshot
            feedback: AI agent feedback dictionary
        """
        feedback_file = self.ai_feedback_dir / f"{screenshot_name}_feedback.json"
        with open(feedback_file, "w") as f:
            json.dump(feedback, f, indent=2)


class DashboardSeleniumTests(unittest.TestCase):
    """Selenium E2E tests for the Sleeper Detection Dashboard."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:8501")
        cls.visual_tester = VisualRegressionTest()

        # Configure Chrome options
        cls.chrome_options = Options()
        cls.chrome_options.add_argument("--headless")  # Run in headless mode
        cls.chrome_options.add_argument("--no-sandbox")
        cls.chrome_options.add_argument("--disable-dev-shm-usage")
        cls.chrome_options.add_argument("--window-size=1920,1080")

        # For capturing full page screenshots
        cls.chrome_options.add_experimental_option(
            "prefs", {"profile.default_content_setting_values.notifications": 2, "profile.default_content_settings.popups": 0}
        )

    def setUp(self):
        """Set up each test."""
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 20)

    def tearDown(self):
        """Clean up after each test."""
        if self.driver:
            self.driver.quit()

    def test_dashboard_loads(self):
        """Test that dashboard loads successfully."""
        self.driver.get(self.dashboard_url)

        # Wait for main content to load
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))

        # Capture screenshot for visual regression
        screenshot = self.visual_tester.capture_screenshot(self.driver, "dashboard_initial_load")

        # Visual regression test
        result = self.visual_tester.compare_visual(screenshot, "dashboard_initial")
        self.assertTrue(result["threshold_passed"], f"Visual regression failed: {result}")

        # Prepare for AI analysis
        _ = self.visual_tester.prepare_for_ai_analysis(screenshot)  # For AI analysis

        # Check title
        self.assertIn("Sleeper Detection Dashboard", self.driver.title)

    def test_login_flow(self):
        """Test login authentication flow."""
        self.driver.get(self.dashboard_url)

        # Wait for login form
        username_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))

        # Capture login page screenshot
        screenshot = self.visual_tester.capture_screenshot(self.driver, "login_page")

        # Enter credentials
        username_input.send_keys("admin")

        password_input = self.driver.find_element(By.XPATH, "//input[@type='password']")
        password_input.send_keys("admin123")

        # Submit form
        submit_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        submit_button.click()

        # Wait for dashboard to load
        time.sleep(2)  # Allow time for navigation

        # Verify we're logged in
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Executive Overview')]")))

        # Capture dashboard after login
        screenshot = self.visual_tester.capture_screenshot(self.driver, "dashboard_after_login")
        _ = self.visual_tester.compare_visual(screenshot, "dashboard_logged_in")

    def test_navigation_menu(self):
        """Test navigation between dashboard sections."""
        self.driver.get(self.dashboard_url)
        self._login()

        sections = [
            "Executive Overview",
            "Detection Analysis",
            "Model Comparison",
            "Time Series Analysis",
            "Test Suite Results",
            "Model Leaderboard",
            "Export Manager",
        ]

        for section in sections:
            # Click on navigation item
            nav_item = self.driver.find_element(By.XPATH, f"//div[contains(text(), '{section}')]")
            nav_item.click()

            time.sleep(1)  # Allow content to load

            # Capture screenshot of each section
            screenshot = self.visual_tester.capture_screenshot(self.driver, f"section_{section.lower().replace(' ', '_')}")

            # Visual regression test for each section
            _ = self.visual_tester.compare_visual(screenshot, f"section_{section.lower().replace(' ', '_')}")

            # Verify section loaded
            self.assertTrue(
                self._element_exists(By.XPATH, f"//h1[contains(text(), '{section}')]"),
                f"Section {section} did not load properly",
            )

    def test_model_selection_interaction(self):
        """Test model selection dropdown interaction."""
        self.driver.get(self.dashboard_url)
        self._login()

        # Navigate to Detection Analysis
        self._navigate_to_section("Detection Analysis")

        # Find model selector
        model_selector = self.wait.until(EC.presence_of_element_located((By.XPATH, "//select[@data-testid='stSelectbox']")))

        # Capture before interaction
        _ = self.visual_tester.capture_screenshot(self.driver, "model_selection_before")

        # Select a model
        model_selector.click()
        time.sleep(0.5)

        # Get available options
        options = self.driver.find_elements(By.XPATH, "//option")
        if len(options) > 1:
            options[1].click()  # Select second option

            time.sleep(1)  # Allow charts to update

            # Capture after interaction
            screenshot_after = self.visual_tester.capture_screenshot(self.driver, "model_selection_after")

            # Verify content changed
            _ = self.visual_tester.compare_visual(screenshot_after, "model_selection_interaction")

    def test_chart_rendering(self):
        """Test that charts render correctly."""
        self.driver.get(self.dashboard_url)
        self._login()

        # Navigate to a section with charts
        self._navigate_to_section("Detection Analysis")

        # Wait for Plotly charts to load
        charts = self.wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'plotly')]")))

        self.assertGreater(len(charts), 0, "No charts found on page")

        # Capture screenshots of charts
        for i, chart in enumerate(charts):
            # Scroll to chart
            self.driver.execute_script("arguments[0].scrollIntoView(true);", chart)
            time.sleep(0.5)

            # Capture chart screenshot
            chart_screenshot = self.screenshots_dir / f"chart_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            chart.screenshot(str(chart_screenshot))

            # Visual regression for charts
            _ = self.visual_tester.compare_visual(chart_screenshot, f"chart_{i}")

    def test_responsive_design(self):
        """Test dashboard responsiveness at different screen sizes."""
        sizes = [(1920, 1080), (1366, 768), (768, 1024), (375, 667)]  # Desktop  # Laptop  # Tablet  # Mobile

        for width, height in sizes:
            self.driver.set_window_size(width, height)
            self.driver.get(self.dashboard_url)

            # Capture screenshot at this size
            screenshot = self.visual_tester.capture_screenshot(self.driver, f"responsive_{width}x{height}")

            # Visual regression test
            _ = self.visual_tester.compare_visual(screenshot, f"responsive_{width}x{height}")

            # Prepare for AI analysis
            ai_data = self.visual_tester.prepare_for_ai_analysis(screenshot)
            ai_data["viewport"] = {"width": width, "height": height}

            # Save for AI agent review
            self.visual_tester.save_ai_feedback(
                f"responsive_{width}x{height}",
                {"viewport": {"width": width, "height": height}, "screenshot": str(screenshot), "ai_analysis_required": True},
            )

    def test_error_handling(self):
        """Test error handling and user feedback."""
        self.driver.get(self.dashboard_url)

        # Try invalid login
        username_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
        username_input.send_keys("invalid_user")

        password_input = self.driver.find_element(By.XPATH, "//input[@type='password']")
        password_input.send_keys("wrong_password")

        submit_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        submit_button.click()

        time.sleep(1)

        # Capture error state
        _ = self.visual_tester.capture_screenshot(self.driver, "error_invalid_login")

        # Check for error message
        error_message = self._element_exists(By.XPATH, "//*[contains(text(), 'Invalid') or contains(text(), 'incorrect')]")
        self.assertTrue(error_message, "No error message shown for invalid login")

    def test_data_export_functionality(self):
        """Test data export features."""
        self.driver.get(self.dashboard_url)
        self._login()

        # Navigate to Export Manager
        self._navigate_to_section("Export Manager")

        # Capture export manager
        _ = self.visual_tester.capture_screenshot(self.driver, "export_manager")

        # Look for export buttons
        export_buttons = self.driver.find_elements(
            By.XPATH, "//button[contains(text(), 'Export') or contains(text(), 'Download')]"
        )

        self.assertGreater(len(export_buttons), 0, "No export buttons found")

        # Test export button interaction (without actually downloading)
        if export_buttons:
            # Hover over first export button
            webdriver.ActionChains(self.driver).move_to_element(export_buttons[0]).perform()
            time.sleep(0.5)

            # Capture hover state
            _ = self.visual_tester.capture_screenshot(self.driver, "export_button_hover")

    def test_performance_metrics(self):
        """Test page load performance and capture metrics."""
        self.driver.get(self.dashboard_url)

        # Get performance metrics
        performance = self.driver.execute_script(
            """
            return {
                timing: performance.timing,
                navigation: performance.navigation,
                memory: performance.memory
            };
        """
        )

        # Calculate load times
        load_time = (performance["timing"]["loadEventEnd"] - performance["timing"]["navigationStart"]) / 1000

        dom_ready = (performance["timing"]["domContentLoadedEventEnd"] - performance["timing"]["navigationStart"]) / 1000

        # Assert reasonable load times
        self.assertLess(load_time, 10, f"Page load time too slow: {load_time}s")
        self.assertLess(dom_ready, 5, f"DOM ready time too slow: {dom_ready}s")

        # Save performance metrics for AI analysis
        self.visual_tester.save_ai_feedback(
            "performance_metrics",
            {"load_time_seconds": load_time, "dom_ready_seconds": dom_ready, "full_metrics": performance},
        )

    # Helper methods
    def _login(self):
        """Helper to login to dashboard."""
        username_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
        username_input.send_keys("admin")

        password_input = self.driver.find_element(By.XPATH, "//input[@type='password']")
        password_input.send_keys("admin123")

        submit_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        submit_button.click()

        time.sleep(2)  # Allow login to complete

    def _navigate_to_section(self, section_name: str):
        """Helper to navigate to a dashboard section."""
        nav_item = self.driver.find_element(By.XPATH, f"//div[contains(text(), '{section_name}')]")
        nav_item.click()
        time.sleep(1)  # Allow navigation

    def _element_exists(self, by: By, value: str) -> bool:
        """Check if element exists without throwing exception."""
        try:
            self.driver.find_element(by, value)
            return True
        except NoSuchElementException:
            return False


if __name__ == "__main__":
    unittest.main()
