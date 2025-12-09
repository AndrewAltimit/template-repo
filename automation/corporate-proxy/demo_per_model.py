#!/usr/bin/env python3
"""
Demonstration of per-model tool mode configuration
Shows how different models use different tool modes
"""

import json
import os
from pathlib import Path
import sys

# Add paths for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "gemini"))

# Mock the config for demonstration
DEMO_CONFIG = {
    "models": {
        "gemini-2.5-flash": {
            "id": "gemini-2.5-flash",
            "endpoint": "ai-coe-bedrock-claude35-sonnet-200k",
            "tool_mode": "native",
            "supports_tools": True,
            "description": "Modern API with native tool support",
        },
        "gemini-1.5-flash": {
            "id": "gemini-1.5-flash",
            "endpoint": "ai-coe-legacy-api",
            "tool_mode": "text",
            "supports_tools": False,
            "description": "Legacy API using text parsing",
        },
        "gemini-experimental": {
            "id": "gemini-experimental",
            "endpoint": "ai-coe-experimental",
            # No tool_mode specified - will use default
            "description": "Experimental model (uses default mode)",
        },
    },
    "default_tool_mode": "native",
    "max_tool_iterations": 5,
}


def demonstrate_per_model_configuration():
    """Show how per-model configuration works"""
    print("=" * 70)
    print("PER-MODEL TOOL MODE CONFIGURATION DEMO")
    print("=" * 70)

    from unittest.mock import patch

    # Patch the config
    with patch.dict("gemini_proxy_wrapper.CONFIG", DEMO_CONFIG):
        from gemini_proxy_wrapper import get_model_tool_mode, translate_gemini_to_company

        print("\n1. Model Configuration Overview:")
        print("-" * 40)
        for model_name, model_config in DEMO_CONFIG["models"].items():
            tool_mode = get_model_tool_mode(model_name)
            print(f"\n  Model: {model_name}")
            print(f"  Endpoint: {model_config['endpoint']}")
            print(f"  Tool Mode: {tool_mode}")
            print(f"  Description: {model_config.get('description', 'N/A')}")

        print("\n\n2. Testing Different Models:")
        print("-" * 40)

        # Test native mode model
        print("\n  Testing gemini-2.5-flash (native mode):")
        request_native = {
            "model": "gemini-2.5-flash",
            "contents": [{"role": "user", "parts": [{"text": "List files"}]}],
            "tools": [{"functionDeclarations": [{"name": "list_files"}]}],
        }

        endpoint, company_req, _ = translate_gemini_to_company(request_native)
        print(f"    → Endpoint: {endpoint}")
        print(f"    → Tools in prompt: {'tool_call' in str(company_req)}")
        print("    → Mode: Native (structured tool calls)")

        # Test text mode model
        print("\n  Testing gemini-1.5-flash (text mode):")
        request_text = {
            "model": "gemini-1.5-flash",
            "contents": [{"role": "user", "parts": [{"text": "List files"}]}],
            "tools": [{"functionDeclarations": [{"name": "list_files"}]}],
        }

        endpoint, company_req, _ = translate_gemini_to_company(request_text)
        print(f"    → Endpoint: {endpoint}")
        print(f"    → Tools in prompt: {'tool_call' in str(company_req)}")
        print("    → Mode: Text (tools parsed from response)")

        # Test model without explicit configuration
        print("\n  Testing gemini-experimental (default mode):")
        request_default = {
            "model": "gemini-experimental",
            "contents": [{"role": "user", "parts": [{"text": "List files"}]}],
            "tools": [{"functionDeclarations": [{"name": "list_files"}]}],
        }

        endpoint, company_req, _ = translate_gemini_to_company(request_default)
        print(f"    → Endpoint: {endpoint}")
        print(f"    → Tool mode: {get_model_tool_mode('gemini-experimental')}")
        print("    → Using default: native")

        print("\n\n3. Environment Variable Overrides:")
        print("-" * 40)

        # Test override
        print("\n  Overriding gemini-2.5-flash to text mode:")
        with patch.dict(os.environ, {"GEMINI_MODEL_OVERRIDE_gemini_2_5_flash_tool_mode": "text"}):
            overridden_mode = get_model_tool_mode("gemini-2.5-flash")
            print("    → Original mode: native")
            print(f"    → Overridden mode: {overridden_mode}")
            print(f"    → Override successful: {overridden_mode == 'text'}")


def demonstrate_mixed_workflow():
    """Show a workflow using multiple models with different modes"""
    print("\n\n4. Mixed Model Workflow:")
    print("-" * 40)

    print(
        """
  Scenario: Complex task requiring multiple models

  1. User asks modern API (native mode) for analysis
     → API returns structured tool calls
     → Tools executed directly

  2. Fallback to legacy API (text mode) for specific task
     → Tools embedded in prompt
     → Response parsed for tool calls
     → Tools executed and results fed back

  3. Both models work seamlessly through the same proxy
     → Automatic mode selection based on model
     → Transparent to the end user
    """
    )

    from shared.services.text_tool_parser import TextToolParser

    # Simulate responses from different models
    print("\n  Native Model Response:")
    native_response = {"tool_calls": [{"function": {"name": "analyze", "arguments": '{"data": "sample"}'}}]}
    print(f"    → Structured: {json.dumps(native_response, indent=6)}")

    print("\n  Text Model Response:")
    text_response = """I'll analyze that data for you.

```tool_call
{
  "tool": "analyze",
  "parameters": {"data": "sample"}
}
```"""

    print("    → Text with embedded tool:")
    for line in text_response.split("\n"):
        print(f"      {line}")

    # Parse tool from text
    parser = TextToolParser()
    parsed_tools = parser.parse_tool_calls(text_response)
    print(f"\n    → Parsed {len(parsed_tools)} tool call(s)")

    print("\n  Result: Both models successfully handle tools in their own way!")


def demonstrate_configuration_api():
    """Show how to check configuration via API endpoints"""
    print("\n\n5. Configuration API Endpoints:")
    print("-" * 40)

    print(
        """
  Check model configurations via API:

  GET /health
    → Shows all model tool modes
    → Example: {"model_tool_modes": {"gemini-2.5-flash": "native", ...}}

  GET /tools
    → Shows available tools and model modes
    → Example: {"model_tool_modes": {...}, "tools": [...]}

  GET /
    → Full configuration with model details
    → Example: {"models": {"gemini-2.5-flash": {"tool_mode": "native", ...}}}

  This makes it easy to:
  - Monitor which mode each model is using
  - Debug tool execution issues
  - Verify configuration changes
    """
    )


def main():
    """Run all demonstrations"""
    try:
        demonstrate_per_model_configuration()
        demonstrate_mixed_workflow()
        demonstrate_configuration_api()

        print("\n" + "=" * 70)
        print("DEMO COMPLETE!")
        print("=" * 70)
        print(
            """
Key Takeaways:
- Each model can have its own tool mode (native or text)
- Models without explicit configuration use default_tool_mode
- Environment variables can override any model's configuration
- The proxy automatically handles each model appropriately
- Mixed workflows with different models work seamlessly

Configuration priority:
1. Environment variable override (highest)
2. Model-specific configuration
3. Default tool mode (lowest)
        """
        )

    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
