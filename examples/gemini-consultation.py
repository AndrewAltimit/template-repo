#!/usr/bin/env python3
"""
Example: Using Gemini AI consultation through MCP
"""

import requests


def consult_gemini(question: str, context: str = None):
    """Consult Gemini AI through MCP server"""

    # MCP server endpoint
    url = "http://localhost:8000/tools/execute"

    # Prepare request
    payload = {"tool": "consult_gemini", "arguments": {"question": question}}

    if context:
        payload["arguments"]["context"] = context

    # Make request
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            return result["result"]
        else:
            print(f"Error: {result.get('error')}")
            return None
    else:
        print(f"HTTP Error: {response.status_code}")
        return None


# Example usage
if __name__ == "__main__":
    # Example 1: Simple technical question
    print("Example 1: Technical Question")
    print("-" * 50)
    response = consult_gemini("What are the best practices for implementing a REST API in Python?")
    if response:
        print(response["response"][:500] + "...")

    print("\n" * 2)

    # Example 2: Code review with context
    print("Example 2: Code Review")
    print("-" * 50)
    code_context = """
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
    """

    response = consult_gemini(
        "Review this Fibonacci implementation and suggest improvements",
        context=code_context,
    )
    if response:
        print(response["response"][:500] + "...")

    print("\n" * 2)

    # Example 3: Architecture design question
    print("Example 3: Architecture Design")
    print("-" * 50)
    response = consult_gemini(
        "Design a scalable microservices architecture for an e-commerce platform. "
        "Include considerations for payment processing, inventory management, "
        "and user authentication."
    )
    if response:
        print(response["response"][:500] + "...")
