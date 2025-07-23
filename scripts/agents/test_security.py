#!/usr/bin/env python3
"""
Test script for security implementation in AI agents
"""

import json
import logging
import sys
from typing import Dict

from security import SecurityManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_test_issue(author: str, number: int) -> Dict:
    """Create a test issue object."""
    return {
        "number": number,
        "title": "Test issue",
        "body": "This is a test issue body",
        "author": {"login": author},
        "labels": [{"name": "bug"}],
        "comments": [],
    }


def create_test_pr(author: str, number: int) -> Dict:
    """Create a test PR object."""
    return {
        "number": number,
        "title": "Test PR",
        "body": "This is a test PR body",
        "author": {"login": author},
        "headRefName": "test-branch",
        "labels": [],
        "reviews": [],
        "comments": [],
    }


def test_security_manager():
    """Test the security manager functionality."""
    logger.info("Testing Security Manager...")

    # Initialize security manager
    security = SecurityManager()

    # Test 1: Check allowed users
    logger.info("\nTest 1: Checking allowed users")
    allowed_users = ["AndrewAltimit", "github-actions[bot]", "gemini-bot"]
    for user in allowed_users:
        result = security.is_user_allowed(user)
        logger.info(f"  {user}: {'✅ Allowed' if result else '❌ Denied'}")
        assert result, f"Expected {user} to be allowed"

    # Test 2: Check unauthorized users
    logger.info("\nTest 2: Checking unauthorized users")
    unauthorized_users = ["random-user", "hacker", "malicious-bot"]
    for user in unauthorized_users:
        result = security.is_user_allowed(user)
        logger.info(f"  {user}: {'✅ Allowed' if result else '❌ Denied'}")
        assert not result, f"Expected {user} to be denied"

    # Test 3: Check issue security
    logger.info("\nTest 3: Testing issue security")

    # Allowed issue
    allowed_issue = create_test_issue("AndrewAltimit", 1)
    result = security.check_issue_security(allowed_issue)
    logger.info(f"  Issue from AndrewAltimit: {'✅ Allowed' if result else '❌ Denied'}")
    assert result, "Expected issue from AndrewAltimit to be allowed"

    # Unauthorized issue
    unauthorized_issue = create_test_issue("random-user", 2)
    result = security.check_issue_security(unauthorized_issue)
    logger.info(f"  Issue from random-user: {'✅ Allowed' if result else '❌ Denied'}")
    assert not result, "Expected issue from random-user to be denied"

    # Test 4: Check PR security
    logger.info("\nTest 4: Testing PR security")

    # Allowed PR
    allowed_pr = create_test_pr("gemini-bot", 10)
    result = security.check_pr_security(allowed_pr)
    logger.info(f"  PR from gemini-bot: {'✅ Allowed' if result else '❌ Denied'}")
    assert result, "Expected PR from gemini-bot to be allowed"

    # Unauthorized PR
    unauthorized_pr = create_test_pr("malicious-user", 11)
    result = security.check_pr_security(unauthorized_pr)
    logger.info(f"  PR from malicious-user: {'✅ Allowed' if result else '❌ Denied'}")
    assert not result, "Expected PR from malicious-user to be denied"

    # Test 5: Test security violation logging
    logger.info("\nTest 5: Testing security violation logging")
    security.log_security_violation("issue", "123", "attacker")
    logger.info("  ✅ Security violation logged successfully")

    # Test 6: Test with security disabled
    logger.info("\nTest 6: Testing with security disabled")
    security.enabled = False
    result = security.is_user_allowed("anyone")
    logger.info(f"  With security disabled, 'anyone' is: {'✅ Allowed' if result else '❌ Denied'}")
    assert result, "Expected all users to be allowed when security is disabled"

    logger.info("\n✅ All security tests passed!")


def test_config_loading():
    """Test loading security configuration from config.json."""
    logger.info("\nTesting Config Loading...")

    # Try to load config
    try:
        with open("config.json", "r") as f:
            config = json.load(f)

        security_config = config.get("security", {})
        logger.info(f"  Security enabled: {security_config.get('enabled', False)}")
        logger.info(f"  Allow list: {security_config.get('allow_list', [])}")
        logger.info(f"  Log violations: {security_config.get('log_violations', False)}")
        logger.info("  ✅ Config loaded successfully")
    except Exception as e:
        logger.error(f"  ❌ Failed to load config: {e}")


def main():
    """Main test runner."""
    logger.info("Starting Security Implementation Tests")
    logger.info("=" * 50)

    try:
        test_security_manager()
        test_config_loading()

        logger.info("\n" + "=" * 50)
        logger.info("✅ ALL TESTS PASSED! Security implementation is working correctly.")
        return 0
    except AssertionError as e:
        logger.error(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
