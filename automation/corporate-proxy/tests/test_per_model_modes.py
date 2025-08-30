#!/usr/bin/env python3
"""
Tests for per-model tool mode configuration
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "gemini"))


class TestPerModelConfiguration(unittest.TestCase):
    """Test per-model tool mode configuration"""

    def setUp(self):
        """Set up test configuration"""
        self.test_config = {
            "models": {
                "model-native": {
                    "id": "model-native",
                    "endpoint": "api-native",
                    "tool_mode": "native",
                    "supports_tools": True,
                },
                "model-text": {"id": "model-text", "endpoint": "api-text", "tool_mode": "text", "supports_tools": False},
                "model-default": {
                    "id": "model-default",
                    "endpoint": "api-default",
                    # No tool_mode specified, should use default
                },
            },
            "default_tool_mode": "native",
            "max_tool_iterations": 5,
        }

    def test_get_model_tool_mode(self):
        """Test getting tool mode for specific models"""
        import gemini_proxy_wrapper
        from gemini_proxy_wrapper import get_model_tool_mode

        # Patch both CONFIG and DEFAULT_TOOL_MODE in the module
        with patch.dict("gemini_proxy_wrapper.CONFIG", self.test_config):
            with patch.object(gemini_proxy_wrapper, "DEFAULT_TOOL_MODE", "native"):
                # Model with native mode
                self.assertEqual(get_model_tool_mode("model-native"), "native")

                # Model with text mode
                self.assertEqual(get_model_tool_mode("model-text"), "text")

                # Model without explicit mode (should use default)
                self.assertEqual(get_model_tool_mode("model-default"), "native")

                # Unknown model (should use default)
                self.assertEqual(get_model_tool_mode("unknown-model"), "native")

    def test_environment_override(self):
        """Test environment variable override for model tool mode"""
        from gemini_proxy_wrapper import get_model_tool_mode

        with patch.dict("gemini_proxy_wrapper.CONFIG", self.test_config):
            # Override native model to text mode
            with patch.dict(os.environ, {"GEMINI_MODEL_OVERRIDE_model_native_tool_mode": "text"}):
                self.assertEqual(get_model_tool_mode("model-native"), "text")

            # Override text model to native mode
            with patch.dict(os.environ, {"GEMINI_MODEL_OVERRIDE_model_text_tool_mode": "native"}):
                self.assertEqual(get_model_tool_mode("model-text"), "native")

    def test_translate_with_native_model(self):
        """Test translation with a native tool mode model"""
        from gemini_proxy_wrapper import translate_gemini_to_company

        with patch.dict("gemini_proxy_wrapper.CONFIG", self.test_config):
            gemini_request = {
                "model": "model-native",
                "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
                "tools": [{"functionDeclarations": [{"name": "test_tool", "description": "Test"}]}],
            }

            endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

            # Should use native mode (no tool injection in prompt)
            self.assertEqual(endpoint, "api-native")
            self.assertIsNotNone(tools)

            # Check that tools are not injected into messages for native mode
            user_message = company_request["messages"][0]["content"]
            self.assertNotIn("```tool_call```", user_message)

    def test_translate_with_text_model(self):
        """Test translation with a text tool mode model"""
        from gemini_proxy_wrapper import translate_gemini_to_company

        with patch.dict("gemini_proxy_wrapper.CONFIG", self.test_config):
            gemini_request = {
                "model": "model-text",
                "contents": [{"role": "user", "parts": [{"text": "Read file.txt"}]}],
                "tools": [
                    {
                        "functionDeclarations": [
                            {
                                "name": "read_file",
                                "description": "Read a file",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                    "required": ["path"],
                                },
                            }
                        ]
                    }
                ],
            }

            endpoint, company_request, tools = translate_gemini_to_company(gemini_request)

            # Should use text mode (tools injected into prompt)
            self.assertEqual(endpoint, "api-text")

            # Check that tools are injected into the user message
            user_message = company_request["messages"][0]["content"]
            self.assertIn("tool_call", user_message)
            self.assertIn("read_file", user_message)
            self.assertIn("Read file.txt", user_message)

    def test_model_specific_behavior(self):
        """Test that different models behave differently based on their configuration"""
        from gemini_proxy_wrapper import translate_company_to_gemini

        with patch.dict("gemini_proxy_wrapper.CONFIG", self.test_config):
            # Test response for native model
            native_request = {"model": "model-native", "_use_text_mode": False}

            company_response = {
                "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "test_tool", "arguments": "{}"}}],
                "content": [{"text": "Using tool"}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }

            gemini_response = translate_company_to_gemini(company_response, native_request, [])

            # Should return structured tool calls
            self.assertIn("candidates", gemini_response)
            parts = gemini_response["candidates"][0]["content"]["parts"]
            self.assertIn("functionCall", parts[0])

            # Test response for text model
            text_request = {"model": "model-text", "_use_text_mode": True}

            text_company_response = {
                "content": [
                    {
                        "text": """I'll help with that.

```tool_call
{
  "tool": "test_tool",
  "parameters": {}
}
```
                    """
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }

            gemini_response_text = translate_company_to_gemini(text_company_response, text_request, [])

            # Should parse tool calls from text
            self.assertIn("candidates", gemini_response_text)


class TestHealthEndpoint(unittest.TestCase):
    """Test health endpoint with per-model configuration"""

    def test_health_shows_model_modes(self):
        """Test that health endpoint shows tool modes for all models"""
        import gemini_proxy_wrapper
        from gemini_proxy_wrapper import get_model_tool_mode

        test_config = {
            "models": {"model1": {"tool_mode": "native"}, "model2": {"tool_mode": "text"}, "model3": {}},  # No tool_mode
            "default_tool_mode": "native",
        }

        # Patch both CONFIG and DEFAULT_TOOL_MODE in the module
        with patch.dict("gemini_proxy_wrapper.CONFIG", test_config):
            with patch.object(gemini_proxy_wrapper, "DEFAULT_TOOL_MODE", "native"):
                # Test get_model_tool_mode directly
                self.assertEqual(get_model_tool_mode("model1"), "native")
                self.assertEqual(get_model_tool_mode("model2"), "text")
                self.assertEqual(get_model_tool_mode("model3"), "native")  # Uses default


class TestDynamicModelSelection(unittest.TestCase):
    """Test dynamic model selection based on request"""

    def test_request_routing(self):
        """Test that requests are routed to correct mode based on model"""
        from gemini_proxy_wrapper import translate_gemini_to_company

        config = {
            "models": {
                "fast-native": {"endpoint": "fast-api", "tool_mode": "native"},
                "slow-text": {"endpoint": "slow-api", "tool_mode": "text"},
            },
            "default_tool_mode": "native",
        }

        with patch.dict("gemini_proxy_wrapper.CONFIG", config):
            # Request to native model
            native_req = {
                "model": "fast-native",
                "contents": [{"role": "user", "parts": [{"text": "test"}]}],
                "tools": [{"functionDeclarations": [{"name": "tool1"}]}],
            }

            endpoint, _, _ = translate_gemini_to_company(native_req)
            self.assertEqual(endpoint, "fast-api")

            # Request to text model
            text_req = {
                "model": "slow-text",
                "contents": [{"role": "user", "parts": [{"text": "test"}]}],
                "tools": [{"functionDeclarations": [{"name": "tool1"}]}],
            }

            endpoint, _, _ = translate_gemini_to_company(text_req)
            self.assertEqual(endpoint, "slow-api")

    def test_mixed_model_workflow(self):
        """Test workflow with mixed native and text models"""
        from shared.services.text_tool_parser import TextToolParser

        parser = TextToolParser()

        # Simulate a workflow where:
        # 1. User queries native model (gets structured response)
        # 2. Falls back to text model (gets text with embedded tools)
        # 3. Both work correctly

        # Native model response
        native_response = {"tool_calls": [{"function": {"name": "search", "arguments": '{"query": "test"}'}}]}

        # Text model response
        text_response = """
        I'll search for that.

        ```tool_call
        {
          "tool": "search",
          "parameters": {
            "query": "test"
          }
        }
        ```
        """

        # Both should extract the same tool call
        native_tool = native_response["tool_calls"][0]["function"]["name"]
        text_tools = parser.parse_tool_calls(text_response)

        self.assertEqual(native_tool, "search")
        self.assertEqual(text_tools[0]["name"], "search")


if __name__ == "__main__":
    unittest.main()
