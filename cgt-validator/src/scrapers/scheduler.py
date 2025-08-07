"""Automated scraping scheduler for CGT requirements."""

import argparse
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.states_config import list_supported_states

from .document_downloader import download_all_documents
from .web_scraper import scrape_state

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ScrapingScheduler:
    """Scheduler for automated requirements scraping."""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or Path.home() / ".cgt-validator" / "scheduler_config.json"
        self.config = self._load_config()
        self.results: List[Dict] = []

    def _load_config(self) -> Dict:
        """Load scheduler configuration.

        Sensitive values are loaded from environment variables:
        - CGT_EMAIL_PASSWORD: Email password for SMTP authentication
        - CGT_SLACK_WEBHOOK_URL: Slack webhook URL for notifications
        """
        default_config = {
            "states": list_supported_states(),
            "output_dir": "./scraped_requirements",
            "email_notifications": {
                "enabled": os.getenv("CGT_EMAIL_ENABLED", "false").lower() == "true",
                "smtp_server": os.getenv("CGT_SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.getenv("CGT_SMTP_PORT", "587")),
                "from_email": os.getenv("CGT_FROM_EMAIL", ""),
                "to_emails": os.getenv("CGT_TO_EMAILS", "").split(",") if os.getenv("CGT_TO_EMAILS") else [],
                # Password is ONLY loaded from environment variable for security
                "password": os.getenv("CGT_EMAIL_PASSWORD", ""),
            },
            "slack_notifications": {
                "enabled": os.getenv("CGT_SLACK_ENABLED", "false").lower() == "true",
                # Webhook URL is ONLY loaded from environment variable for security
                "webhook_url": os.getenv("CGT_SLACK_WEBHOOK_URL", ""),
            },
            "max_retries": int(os.getenv("CGT_MAX_RETRIES", "3")),
            "retry_delay": int(os.getenv("CGT_RETRY_DELAY", "60")),  # seconds
        }

        if self.config_file.exists():
            with open(self.config_file, encoding="utf-8") as f:
                user_config = json.load(f)
                # Merge with defaults, but never override sensitive values
                # Remove any sensitive values from the config file
                if "email_notifications" in user_config:
                    user_config["email_notifications"].pop("password", None)
                if "slack_notifications" in user_config:
                    user_config["slack_notifications"].pop("webhook_url", None)

                # Merge non-sensitive configuration
                for key, value in user_config.items():
                    if key not in ["email_notifications", "slack_notifications"]:
                        default_config[key] = value
                    else:
                        # For notification configs, merge carefully
                        if key == "email_notifications" and isinstance(value, dict):
                            for k, v in value.items():
                                if k != "password":  # Never override password from file
                                    default_config[key][k] = v
                        elif key == "slack_notifications" and isinstance(value, dict):
                            for k, v in value.items():
                                if k != "webhook_url":  # Never override webhook URL from file
                                    default_config[key][k] = v

        # Log warning if sensitive values are not configured
        if default_config["email_notifications"]["enabled"] and not default_config["email_notifications"]["password"]:
            logger.warning("Email notifications enabled but CGT_EMAIL_PASSWORD environment variable not set")
        if (
            default_config["slack_notifications"]["enabled"]
            and not default_config["slack_notifications"]["webhook_url"]
        ):
            logger.warning("Slack notifications enabled but CGT_SLACK_WEBHOOK_URL environment variable not set")

        return default_config

    def save_config(self):
        """Save current configuration to file (excluding sensitive values)."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Create a copy of config without sensitive values
        safe_config = self.config.copy()
        if "email_notifications" in safe_config:
            safe_config["email_notifications"] = safe_config["email_notifications"].copy()
            safe_config["email_notifications"].pop("password", None)
        if "slack_notifications" in safe_config:
            safe_config["slack_notifications"] = safe_config["slack_notifications"].copy()
            safe_config["slack_notifications"].pop("webhook_url", None)

        # Write config with restricted permissions (owner read/write only)
        import stat

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(safe_config, f, indent=2)

        # Set file permissions to 600 (owner read/write only)
        os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)

        logger.info("Configuration saved to %s (sensitive values excluded)", self.config_file)

    def scrape_state_with_retry(self, state: str) -> Dict:
        """Scrape a state with retry logic."""
        max_retries = self.config.get("max_retries", 3)
        retry_delay = self.config.get("retry_delay", 60)

        for attempt in range(max_retries):
            try:
                logger.info("Scraping %s (attempt %d/%d)", state, attempt + 1, max_retries)

                # Scrape documents
                documents = scrape_state(state)
                logger.info("Found %d documents for %s", len(documents), state)

                # Download documents
                downloaded = download_all_documents(state)
                logger.info("Downloaded %d documents for %s", len(downloaded), state)

                return {
                    "state": state,
                    "status": "success",
                    "documents_found": len(documents),
                    "documents_downloaded": len(downloaded),
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                logger.error("Error scraping %s: %s", state, e)
                if attempt < max_retries - 1:
                    logger.info("Retrying in %d seconds...", retry_delay)
                    import time

                    time.sleep(retry_delay)
                else:
                    return {
                        "state": state,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }

        # All retries exhausted
        return {
            "state": state,
            "status": "failed",
            "error": "All retry attempts exhausted",
            "timestamp": datetime.now().isoformat(),
        }

    def run_scraping(self, states: Optional[List[str]] = None):
        """Run scraping for specified states or all configured states."""
        states_to_scrape = states or self.config.get("states", [])

        logger.info("Starting scraping run for %d states", len(states_to_scrape))
        start_time = datetime.now()

        self.results = []
        for state in states_to_scrape:
            result = self.scrape_state_with_retry(state)
            self.results.append(result)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Generate summary
        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "failed")

        summary = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_states": len(states_to_scrape),
            "successful": successful,
            "failed": failed,
            "results": self.results,
        }

        # Save results
        self._save_results(summary)

        # Send notifications
        self._send_notifications(summary)

        logger.info("Scraping completed: %d successful, %d failed", successful, failed)

        return summary

    def _save_results(self, summary: Dict):
        """Save scraping results to file."""
        output_dir = Path(self.config.get("output_dir", "./scraped_requirements"))
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = output_dir / f"scraping_results_{timestamp}.json"

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info("Results saved to %s", results_file)

    def _send_notifications(self, summary: Dict):
        """Send notifications about scraping results."""
        # Email notifications
        if self.config.get("email_notifications", {}).get("enabled"):
            self._send_email_notification(summary)

        # Slack notifications
        if self.config.get("slack_notifications", {}).get("enabled"):
            self._send_slack_notification(summary)

    def _send_email_notification(self, summary: Dict):
        """Send email notification with results."""
        email_config = self.config.get("email_notifications", {})

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = email_config.get("from_email")
            msg["To"] = ", ".join(email_config.get("to_emails", []))
            msg["Subject"] = f"CGT Scraping Results - {summary['successful']}/{summary['total_states']} Successful"

            # Create body
            body = self._generate_notification_body(summary)
            msg.attach(MIMEText(body, "plain"))

            # Send email
            server = smtplib.SMTP(email_config.get("smtp_server"), email_config.get("smtp_port"))
            server.starttls()
            server.login(email_config.get("from_email"), email_config.get("password"))

            for to_email in email_config.get("to_emails", []):
                server.send_message(msg, to_addrs=[to_email])

            server.quit()
            logger.info("Email notification sent successfully")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to send email notification: %s", e)

    def _send_slack_notification(self, summary: Dict):
        """Send Slack notification with results."""
        slack_config = self.config.get("slack_notifications", {})
        webhook_url = slack_config.get("webhook_url")

        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        try:
            import requests

            # Create message
            message: Dict[str, Any] = {
                "text": f"CGT Scraping Completed: {summary['successful']}/{summary['total_states']} Successful",
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "CGT Requirements Scraping Results"}},
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Total States:* {summary['total_states']}"},
                            {"type": "mrkdwn", "text": f"*Successful:* {summary['successful']}"},
                            {"type": "mrkdwn", "text": f"*Failed:* {summary['failed']}"},
                            {"type": "mrkdwn", "text": f"*Duration:* {summary['duration_seconds']:.1f}s"},
                        ],
                    },
                ],
            }

            # Add failed states if any
            failed_states = [r for r in summary["results"] if r["status"] == "failed"]
            if failed_states:
                failed_text = "\n".join([f"• {r['state']}: {r.get('error', 'Unknown error')}" for r in failed_states])
                message["blocks"].append(
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*Failed States:*\n{failed_text}"}}
                )

            response = requests.post(webhook_url, json=message, timeout=30)
            response.raise_for_status()
            logger.info("Slack notification sent successfully")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to send Slack notification: %s", e)

    def _generate_notification_body(self, summary: Dict) -> str:
        """Generate notification body text."""
        lines = [
            "CGT Requirements Scraping Results",
            "=" * 40,
            f"Start Time: {summary['start_time']}",
            f"End Time: {summary['end_time']}",
            f"Duration: {summary['duration_seconds']:.1f} seconds",
            "",
            f"Total States: {summary['total_states']}",
            f"Successful: {summary['successful']}",
            f"Failed: {summary['failed']}",
            "",
            "Results by State:",
            "-" * 40,
        ]

        for result in summary["results"]:
            if result["status"] == "success":
                lines.append(
                    f"✓ {result['state']}: {result['documents_found']} found, "
                    f"{result['documents_downloaded']} downloaded"
                )
            else:
                lines.append(f"✗ {result['state']}: FAILED - {result.get('error', 'Unknown error')}")

        return "\n".join(lines)


def main():
    """Main entry point for scheduler CLI."""
    parser = argparse.ArgumentParser(description="CGT Requirements Scraping Scheduler")
    parser.add_argument("command", choices=["run", "config", "list"], help="Command to execute")
    parser.add_argument("--states", nargs="+", help="Specific states to scrape")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--output-dir", help="Output directory for results")

    # Config command options
    parser.add_argument("--email", help="Enable email notifications", action="store_true")
    parser.add_argument("--smtp-server", help="SMTP server address")
    parser.add_argument("--smtp-port", type=int, help="SMTP server port")
    parser.add_argument("--from-email", help="From email address")
    parser.add_argument("--to-emails", nargs="+", help="To email addresses")

    args = parser.parse_args()

    # Initialize scheduler
    config_file = Path(args.config) if args.config else None
    scheduler = ScrapingScheduler(config_file)

    if args.command == "config":
        # Update configuration
        if args.output_dir:
            scheduler.config["output_dir"] = args.output_dir

        if args.email:
            scheduler.config["email_notifications"]["enabled"] = True

        if args.smtp_server:
            scheduler.config["email_notifications"]["smtp_server"] = args.smtp_server

        if args.smtp_port:
            scheduler.config["email_notifications"]["smtp_port"] = args.smtp_port

        if args.from_email:
            scheduler.config["email_notifications"]["from_email"] = args.from_email

        if args.to_emails:
            scheduler.config["email_notifications"]["to_emails"] = args.to_emails

        scheduler.save_config()
        print(f"Configuration saved to {scheduler.config_file}")

    elif args.command == "list":
        # List configured states
        print("Configured states:")
        for state in scheduler.config.get("states", []):
            print(f"  - {state}")

    elif args.command == "run":
        # Run scraping
        summary = scheduler.run_scraping(args.states)

        # Print summary
        print(f"\nScraping completed: {summary['successful']}/{summary['total_states']} successful")
        if summary["failed"] > 0:
            print("\nFailed states:")
            for result in summary["results"]:
                if result["status"] == "failed":
                    print(f"  - {result['state']}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
