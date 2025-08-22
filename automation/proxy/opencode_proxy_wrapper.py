#!/usr/bin/env python3
"""
OpenCode Proxy Wrapper
A simple CLI that mimics OpenCode but uses the proxy directly
"""

import argparse
import json
import sys
from typing import Any, Dict, List

import requests


class OpenCodeProxy:
    def __init__(self, proxy_url: str = "http://localhost:8052/v1"):
        self.proxy_url = proxy_url
        self.headers = {"Content-Type": "application/json"}

    def chat(self, messages: List[Dict[str, str]], model: str = "claude-3.5-sonnet") -> str:
        """Send chat request to proxy"""
        payload = {"model": model, "messages": messages, "max_tokens": 1000}

        try:
            response = requests.post(f"{self.proxy_url}/chat/completions", json=payload, headers=self.headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"Error: {str(e)}"

    def interactive_session(self):
        """Run interactive chat session"""
        print("🤖 OpenCode Proxy Interactive Session")
        print("=====================================")
        print("All responses will be: 'Hatsune Miku'")
        print("Type 'exit' to quit")
        print("")

        messages = []

        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()

                if user_input.lower() in ["exit", "quit", "q"]:
                    print("Goodbye!")
                    break

                if not user_input:
                    continue

                # Add user message
                messages.append({"role": "user", "content": user_input})

                # Get response
                print("Assistant: ", end="", flush=True)
                response = self.chat(messages)
                print(response)

                # Add assistant response to history
                messages.append({"role": "assistant", "content": response})

                # Keep conversation history limited
                if len(messages) > 10:
                    messages = messages[-10:]

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    def run_query(self, query: str) -> str:
        """Run a single query"""
        messages = [{"role": "user", "content": query}]
        return self.chat(messages)


def main():
    parser = argparse.ArgumentParser(description="OpenCode Proxy CLI")
    parser.add_argument("-q", "--query", help="Single query to run")
    parser.add_argument(
        "--proxy-url", default="http://localhost:8052/v1", help="Proxy URL (default: http://localhost:8052/v1)"
    )

    args = parser.parse_args()

    proxy = OpenCodeProxy(args.proxy_url)

    if args.query:
        # Single query mode
        response = proxy.run_query(args.query)
        print(response)
    else:
        # Interactive mode
        proxy.interactive_session()


if __name__ == "__main__":
    main()
