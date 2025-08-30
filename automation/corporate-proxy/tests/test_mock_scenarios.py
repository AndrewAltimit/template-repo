#!/usr/bin/env python3
"""
Mock server test scenarios
Tests various real-world scenarios with mock servers
"""

import json
import multiprocessing
import os
import sys
import time
import unittest
from pathlib import Path

import requests
from flask import Flask, jsonify, request

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def create_mock_company_api(port=8051):
    """Create a mock company API server for testing"""
    app = Flask(__name__)

    # Track requests for verification
    app.requests_received = []

    @app.route("/api/v1/AI/GenAIExplorationLab/Models/<path:model>", methods=["POST"])
    def handle_model_request(model):
        """Mock company API endpoint"""
        data = request.json
        app.requests_received.append(data)

        # Check if this is a tool-enabled request
        messages = data.get("messages", [])
        system = data.get("system", "")

        # Simulate different responses based on content
        if any("list" in msg.get("content", "").lower() for msg in messages):
            # Return a response that would trigger list_directory tool
            if "tool" in system.lower():
                # Tool-enabled response
                return jsonify(
                    {
                        "tool_calls": [
                            {
                                "id": "call_list_123",
                                "type": "function",
                                "function": {"name": "list_directory", "arguments": json.dumps({"path": "."})},
                            }
                        ],
                        "content": [{"text": "I'll list the directory contents."}],
                        "usage": {"input_tokens": 10, "output_tokens": 15},
                    }
                )
            else:
                # Text response with embedded tool call
                return jsonify(
                    {
                        "content": [
                            {
                                "text": """I'll list the directory contents for you.

```tool_call
{
  "tool": "list_directory",
  "parameters": {
    "path": "."
  }
}
```

This will show all files and folders."""
                            }
                        ],
                        "usage": {"input_tokens": 10, "output_tokens": 30},
                    }
                )

        # Default response
        return jsonify(
            {"content": [{"text": "Hello from mock company API"}], "usage": {"input_tokens": 5, "output_tokens": 10}}
        )

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "mock_company_api"})

    app.run(port=port, debug=False)


def create_gemini_proxy(port=8052, company_port=8051, tool_mode="native"):
    """Create and run the Gemini proxy"""
    os.environ["TOOL_MODE"] = tool_mode
    os.environ["USE_MOCK_API"] = "false"
    os.environ["COMPANY_API_BASE"] = f"http://localhost:{company_port}"
    os.environ["GEMINI_PROXY_PORT"] = str(port)

    # Import and run the proxy
    from gemini.gemini_proxy_wrapper import app

    app.run(port=port, debug=False)


class TestMockScenarios(unittest.TestCase):
    """Test real-world scenarios with mock servers"""

    def test_file_reading_scenario(self):
        """Test a scenario where AI reads a file"""
        from shared.services.text_tool_parser import TextToolParser

        # Scenario: User asks to read a configuration file
        user_request = "Please read the configuration from config.json and tell me what port is configured."

        # Expected flow:
        # 1. User request → AI decides to use read_file tool
        # 2. Tool executes → Returns file content
        # 3. AI analyzes content → Provides answer

        parser = TextToolParser()

        # Mock file content
        file_content = '{"port": 8080, "host": "localhost", "debug": true}'

        def mock_executor(tool_name, params):
            if tool_name == "read_file" and params.get("path") == "config.json":
                return {"success": True, "content": file_content}
            return {"success": False, "error": "File not found"}

        parser.tool_executor = mock_executor

        # Simulate AI response with tool call
        ai_response_1 = """
        I'll read the configuration file to find the port setting.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "config.json"
          }
        }
        ```
        """

        # Process first response
        continuation, results, needs_continue = parser.process_response_with_tools(ai_response_1)

        self.assertTrue(needs_continue)
        self.assertEqual(len(results), 1)
        self.assertIn(file_content, continuation)

        # Simulate AI's analysis after getting file content
        ai_response_2 = "Based on the configuration file, the port is configured as 8080. The service will run on localhost:8080 with debug mode enabled."

        # Process final response
        continuation2, results2, needs_continue2 = parser.process_response_with_tools(ai_response_2)

        self.assertFalse(needs_continue2)  # No more tools needed
        self.assertEqual(len(results2), 0)  # No tool calls in final response

    def test_multi_file_operation_scenario(self):
        """Test scenario with multiple file operations"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        # Track operations
        operations = []

        def mock_executor(tool_name, params):
            operations.append({"tool": tool_name, "params": params})

            if tool_name == "read_file":
                return {"success": True, "content": "Original content"}
            elif tool_name == "write_file":
                return {"success": True, "message": "File written successfully"}
            elif tool_name == "list_directory":
                return {"success": True, "files": ["file1.txt", "file2.txt"], "directories": ["src", "tests"]}
            return {"success": False, "error": "Unknown operation"}

        parser.tool_executor = mock_executor

        # Simulate complex multi-step operation
        ai_response = """
        I'll help you backup and modify your files. Let me start by listing the directory.

        ```tool_call
        {
          "tool": "list_directory",
          "parameters": {
            "path": "."
          }
        }
        ```

        Now I'll read the original file.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "file1.txt"
          }
        }
        ```

        Finally, I'll create a backup.

        ```tool_call
        {
          "tool": "write_file",
          "parameters": {
            "path": "file1.backup.txt",
            "content": "Original content"
          }
        }
        ```
        """

        continuation, results, needs_continue = parser.process_response_with_tools(ai_response)

        # Verify all operations were executed
        self.assertEqual(len(operations), 3)
        self.assertEqual(operations[0]["tool"], "list_directory")
        self.assertEqual(operations[1]["tool"], "read_file")
        self.assertEqual(operations[2]["tool"], "write_file")

        # Verify results formatting
        self.assertIn("Tool Result: list_directory", continuation)
        self.assertIn("Tool Result: read_file", continuation)
        self.assertIn("Tool Result: write_file", continuation)

    def test_error_recovery_scenario(self):
        """Test scenario with errors and recovery"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        attempt_count = {"count": 0}

        def mock_executor(tool_name, params):
            attempt_count["count"] += 1

            # First attempt fails
            if attempt_count["count"] == 1:
                return {"success": False, "error": "Permission denied"}

            # Second attempt succeeds
            return {"success": True, "content": "File content after retry"}

        parser.tool_executor = mock_executor

        # First attempt
        ai_response_1 = """
        Let me read the file.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "protected.txt"
          }
        }
        ```
        """

        continuation1, results1, _ = parser.process_response_with_tools(ai_response_1)

        self.assertIn("Tool Error", continuation1)
        self.assertIn("Permission denied", continuation1)

        # AI responds to error and retries
        ai_response_2 = """
        I see there was a permission error. Let me try again with a different approach.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "protected.txt"
          }
        }
        ```
        """

        continuation2, results2, _ = parser.process_response_with_tools(ai_response_2)

        self.assertIn("Tool Result", continuation2)
        self.assertIn("File content after retry", continuation2)
        self.assertEqual(attempt_count["count"], 2)

    def test_conditional_tool_usage_scenario(self):
        """Test scenario where tool usage depends on previous results"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        def mock_executor(tool_name, params):
            if tool_name == "check_file_exists":
                # Simulate file exists check
                path = params.get("path", "")
                exists = path != "missing.txt"
                return {"success": True, "exists": exists, "path": path}
            elif tool_name == "read_file":
                return {"success": True, "content": "File contents"}
            elif tool_name == "create_file":
                return {"success": True, "message": "File created"}
            return {"success": False, "error": "Unknown tool"}

        parser.tool_executor = mock_executor

        # Scenario: Check if file exists, then read or create
        ai_response_exists = """
        I'll check if the file exists first.

        ```tool_call
        {
          "tool": "check_file_exists",
          "parameters": {
            "path": "data.txt"
          }
        }
        ```
        """

        continuation, results, _ = parser.process_response_with_tools(ai_response_exists)

        # File exists, so read it
        self.assertTrue(results[0]["result"]["exists"])

        ai_response_read = """
        The file exists, so I'll read its contents.

        ```tool_call
        {
          "tool": "read_file",
          "parameters": {
            "path": "data.txt"
          }
        }
        ```
        """

        continuation2, results2, _ = parser.process_response_with_tools(ai_response_read)
        self.assertIn("File contents", continuation2)

        # Now test with missing file
        ai_response_missing = """
        Let me check for another file.

        ```tool_call
        {
          "tool": "check_file_exists",
          "parameters": {
            "path": "missing.txt"
          }
        }
        ```
        """

        continuation3, results3, _ = parser.process_response_with_tools(ai_response_missing)
        self.assertFalse(results3[0]["result"]["exists"])

        # File doesn't exist, so create it
        ai_response_create = """
        The file doesn't exist, so I'll create it.

        ```tool_call
        {
          "tool": "create_file",
          "parameters": {
            "path": "missing.txt",
            "content": "New file"
          }
        }
        ```
        """

        continuation4, results4, _ = parser.process_response_with_tools(ai_response_create)
        self.assertIn("File created", continuation4)

    def test_batch_operations_scenario(self):
        """Test scenario with batch operations on multiple files"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        processed_files = []

        def mock_executor(tool_name, params):
            if tool_name == "process_file":
                path = params.get("path")
                processed_files.append(path)
                return {"success": True, "message": f"Processed {path}"}
            return {"success": False, "error": "Unknown tool"}

        parser.tool_executor = mock_executor

        # Batch operation on multiple files
        ai_response = """
        I'll process all the test files in batch.

        ```tool_call
        {
          "tool": "process_file",
          "parameters": {
            "path": "test1.txt"
          }
        }
        ```

        ```tool_call
        {
          "tool": "process_file",
          "parameters": {
            "path": "test2.txt"
          }
        }
        ```

        ```tool_call
        {
          "tool": "process_file",
          "parameters": {
            "path": "test3.txt"
          }
        }
        ```

        All files queued for processing.
        """

        continuation, results, _ = parser.process_response_with_tools(ai_response)

        # Verify all files were processed
        self.assertEqual(len(processed_files), 3)
        self.assertIn("test1.txt", processed_files)
        self.assertIn("test2.txt", processed_files)
        self.assertIn("test3.txt", processed_files)

        # Verify results contain all operations
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertTrue(result["result"]["success"])


class TestEndToEndScenarios(unittest.TestCase):
    """Test complete end-to-end scenarios"""

    def test_gemini_cli_simulation(self):
        """Simulate a complete Gemini CLI interaction"""
        from shared.services.text_tool_parser import TextToolParser

        # Simulate the complete flow from Gemini CLI
        # 1. User input via Gemini CLI
        user_input = "Analyze the project structure and create a summary"

        # 2. Gemini CLI sends to proxy with tools
        gemini_request = {
            "model": "gemini-2.5-flash",
            "contents": [{"role": "user", "parts": [{"text": user_input}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "list_directory",
                            "description": "List directory contents",
                            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                        },
                        {
                            "name": "write_file",
                            "description": "Write to file",
                            "parameters": {
                                "type": "object",
                                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                "required": ["path", "content"],
                            },
                        },
                    ]
                }
            ],
        }

        # 3. Process through text mode
        parser = TextToolParser()

        def mock_executor(tool_name, params):
            if tool_name == "list_directory":
                return {
                    "success": True,
                    "files": ["README.md", "setup.py", "requirements.txt"],
                    "directories": ["src", "tests", "docs"],
                }
            elif tool_name == "write_file":
                return {"success": True, "message": "Summary written successfully"}
            return {"success": False, "error": "Unknown tool"}

        parser.tool_executor = mock_executor

        # 4. AI generates response with tool calls
        ai_iteration_1 = """
        I'll analyze the project structure for you. Let me start by examining the directory layout.

        ```tool_call
        {
          "tool": "list_directory",
          "parameters": {
            "path": "."
          }
        }
        ```
        """

        continuation1, results1, needs_continue1 = parser.process_response_with_tools(ai_iteration_1)

        self.assertTrue(needs_continue1)
        self.assertIn("README.md", continuation1)

        # 5. AI continues with analysis and creates summary
        ai_iteration_2 = """
        Based on the directory structure, I can see this is a Python project with:
        - Main source code in src/
        - Test suite in tests/
        - Documentation in docs/
        - Standard Python files (README.md, setup.py, requirements.txt)

        Let me create a summary file.

        ```tool_call
        {
          "tool": "write_file",
          "parameters": {
            "path": "PROJECT_SUMMARY.md",
            "content": "# Project Structure Summary\\n\\n- Source: src/\\n- Tests: tests/\\n- Docs: docs/\\n- Type: Python Package"
          }
        }
        ```
        """

        continuation2, results2, needs_continue2 = parser.process_response_with_tools(ai_iteration_2)

        self.assertTrue(needs_continue2)
        self.assertIn("Summary written successfully", continuation2)

        # 6. AI completes the task
        ai_final = """
        I've completed the analysis of your project structure. The project appears to be a well-organized Python package with:

        1. Source code in the src/ directory
        2. Test suite in tests/
        3. Documentation in docs/
        4. Standard Python packaging files

        I've created a PROJECT_SUMMARY.md file with the structure overview. The task is complete.
        """

        continuation3, results3, needs_continue3 = parser.process_response_with_tools(ai_final)

        self.assertFalse(needs_continue3)  # Task complete
        self.assertTrue(parser.is_complete_response(ai_final))


if __name__ == "__main__":
    # Run tests
    unittest.main()
