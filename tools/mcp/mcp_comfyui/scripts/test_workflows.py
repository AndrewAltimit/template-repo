#!/usr/bin/env python3
"""Test script for ComfyUI MCP workflow system"""

import asyncio
import os
from pathlib import Path
import sys
import traceback

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


from tools.mcp.comfyui.workflows import WORKFLOW_TEMPLATES, WorkflowFactory  # noqa: E402
from tools.mcp.core.client import MCPClient  # noqa: E402


async def test_workflow_factory():
    """Test the workflow factory methods"""
    print("Testing Workflow Factory...")
    print("-" * 50)

    # Test FLUX workflow
    print("\n1. Testing FLUX workflow creation:")
    flux_workflow = WorkflowFactory.create_flux_workflow(
        prompt="A beautiful sunset over mountains", width=1024, height=1024, steps=20, cfg_scale=3.5
    )
    print(f"   ✓ FLUX workflow created with {len(flux_workflow)} nodes")

    # Test SDXL workflow
    print("\n2. Testing SDXL workflow creation:")
    sdxl_workflow = WorkflowFactory.create_sdxl_workflow(
        prompt="An anime character", model_name="illustriousXL_smoothftSOLID.safetensors", steps=30
    )
    print(f"   ✓ SDXL workflow created with {len(sdxl_workflow)} nodes")

    # Test FLUX with LoRA
    print("\n3. Testing FLUX with LoRA workflow:")
    flux_lora = WorkflowFactory.create_flux_workflow(
        prompt="Robot in inkpunk style", lora_name="Inkpunk_Flux.safetensors", lora_strength=0.8
    )
    print(f"   ✓ FLUX+LoRA workflow created with {len(flux_lora)} nodes")
    has_lora = any(node.get("class_type") == "LoraLoader" for node in flux_lora.values())
    print(f"   ✓ LoRA node present: {has_lora}")

    print("\n4. Available workflow templates:")
    for key, template in WORKFLOW_TEMPLATES.items():
        print(f"   - {key}: {template['description']}")


async def test_mcp_integration():
    """Test MCP server integration with workflows"""
    print("\n\nTesting MCP Server Integration...")
    print("-" * 50)

    client = MCPClient("comfyui")  # Port 8013 is default for comfyui

    try:
        # Test connection
        print("\n1. Testing server connection:")
        system_info = await client.call_tool("get_system_info")
        if "system" in system_info:
            print(f"   ✓ Connected to ComfyUI v{system_info['system']['comfyui_version']}")
            if "devices" in system_info:
                for device in system_info["devices"]:
                    print(f"   ✓ GPU: {device['name']}")

        # List models
        print("\n2. Available models:")
        models = await client.call_tool("list_models", type="checkpoint")
        if "models" in models:
            for model in models["models"]:
                print(f"   - {model}")

        # List LoRAs
        print("\n3. Available LoRAs:")
        loras = await client.call_tool("list_loras")
        if "loras" in loras:
            for lora in loras["loras"]:
                print(f"   - {lora['name']} ({lora['size'] / 1024 / 1024:.1f} MB)")

        # Test workflow listing
        print("\n4. Testing workflow listing:")
        workflows = await client.call_tool("list_workflows")
        if "workflows" in workflows:
            print(f"   ✓ Found {len(workflows['workflows'])} workflows")

        # Test getting a workflow
        print("\n5. Testing get_workflow:")
        workflow_data = await client.call_tool("get_workflow", name="flux_default")
        if "workflow" in workflow_data:
            print("   ✓ Retrieved flux_default workflow")
            print(f"   ✓ Workflow has {len(workflow_data['workflow'])} nodes")

        # Test image generation (optional - takes time)
        if os.environ.get("TEST_GENERATION", "false").lower() == "true":
            print("\n6. Testing image generation (this may take time):")

            # Create a simple test workflow
            test_workflow = WorkflowFactory.create_flux_workflow(
                prompt="A simple test image, minimalist design",
                width=512,
                height=512,
                steps=10,  # Fewer steps for testing
                cfg_scale=3.5,
            )

            result = await client.call_tool("generate_image", workflow=test_workflow, timeout=120)  # 2 minute timeout for test

            if "images" in result:
                print(f"   ✓ Generated {len(result['images'])} image(s)")
                for img in result["images"]:
                    print(f"     - {img['filename']}")
            elif "error" in result:
                print(f"   ✗ Generation failed: {result['error']}")
        else:
            print("\n6. Skipping image generation (set TEST_GENERATION=true to enable)")

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        traceback.print_exc()


async def main():
    """Main test function"""
    print("=" * 70)
    print("ComfyUI MCP Workflow System Test")
    print("=" * 70)

    # Test workflow factory
    await test_workflow_factory()

    # Test MCP integration
    await test_mcp_integration()

    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)

    # Print usage tips
    print("\nUsage Tips:")
    print("- Set TEST_GENERATION=true to test actual image generation")
    print("- Ensure ComfyUI is running on localhost:8188")
    print("- Or update COMFYUI_HOST and COMFYUI_PORT environment variables")


if __name__ == "__main__":
    asyncio.run(main())
