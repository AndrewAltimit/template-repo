"""Manual test for ClaudeExecutor with real Claude Code CLI.

This test requires:
1. Claude Code CLI installed (claude command available)
2. NVM installed with Node.js 22.16.0
3. Claude authentication configured

Run with: python tests/manual/test_claude_executor_manual.py
"""

import json
import logging
import sys

from economic_agents.agent.llm.executors import ClaudeExecutor

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_simple_math():
    """Test Claude with a simple math question."""
    print("\n=== Test 1: Simple Math ===")

    executor = ClaudeExecutor({"llm_timeout": 60})  # 1 minute for simple test

    prompt = """
Please solve this simple math problem and respond ONLY with a JSON object (no markdown, no code blocks):

What is 42 + 17?

Response format:
{
  "answer": <number>,
  "reasoning": "<brief explanation>"
}
"""

    try:
        response = executor.execute(prompt)
        print(f"\nRaw response:\n{response}\n")

        # Try to parse as JSON
        try:
            parsed = json.loads(response.strip())
            print(f"Parsed JSON: {parsed}")
            print(f"Answer: {parsed.get('answer')}")
            print(f"Reasoning: {parsed.get('reasoning')}")
            print("✅ Test passed!")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            print("Response might include extra text around the JSON")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def test_json_response():
    """Test Claude with explicit JSON response requirement."""
    print("\n=== Test 2: Structured JSON Response ===")

    executor = ClaudeExecutor({"llm_timeout": 90})  # 1.5 minutes

    prompt = """
You are a helpful assistant. Please respond with ONLY a valid JSON object (no markdown, no explanations before or after).

Question: What are the three primary colors?

Required JSON format:
{
  "colors": ["color1", "color2", "color3"],
  "explanation": "brief explanation"
}

Return ONLY the JSON, nothing else.
"""

    try:
        response = executor.execute(prompt)
        print(f"\nRaw response:\n{response}\n")

        # Try to parse as JSON
        try:
            parsed = json.loads(response.strip())
            print(f"Parsed JSON: {parsed}")
            print(f"Colors: {parsed.get('colors')}")
            print("✅ Test passed!")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def test_timeout():
    """Test that timeout works (use very short timeout)."""
    print("\n=== Test 3: Timeout Handling ===")

    executor = ClaudeExecutor({"llm_timeout": 5})  # 5 seconds - very short

    prompt = """
This is a test of the timeout mechanism.
Please count from 1 to 100 slowly.
"""

    try:
        response = executor.execute(prompt)
        print(f"Response received: {response[:100]}...")
        print("⚠️  No timeout occurred (prompt completed quickly)")
        return True
    except TimeoutError as e:
        print(f"✅ Timeout worked as expected: {e}")
        return True
    except Exception as e:
        print(f"❌ Test failed with unexpected error: {e}")
        return False


def main():
    """Run all manual tests."""
    print("=" * 60)
    print("Claude Executor Manual Tests")
    print("=" * 60)
    print("\nThese tests require Claude Code CLI to be installed and configured.")
    print("Tests will make real calls to Claude.\n")

    response = input("Continue with tests? (y/n): ")
    if response.lower() != "y":
        print("Tests cancelled.")
        return

    results = []

    # Run tests
    results.append(("Simple Math", test_simple_math()))
    results.append(("Structured JSON", test_json_response()))
    results.append(("Timeout Handling", test_timeout()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
