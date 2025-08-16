"""ComfyUI MCP Server - GPU-accelerated AI image generation"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Request, Response

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# ComfyUI configuration
COMFYUI_PATH = os.environ.get("COMFYUI_PATH", "/comfyui")
MODELS_PATH = Path(COMFYUI_PATH) / "models"
OUTPUT_PATH = Path(COMFYUI_PATH) / "output"
INPUT_PATH = Path(COMFYUI_PATH) / "input"


class ComfyUIMCPServer(BaseMCPServer):
    """MCP Server for ComfyUI - AI image generation"""

    def __init__(self, port: int = 8013):
        super().__init__(
            name="ComfyUI MCP Server",
            version="1.0.0",
            port=port,
        )

        # Initialize server state
        self.logger = setup_logging("comfyui_mcp")
        self.generation_jobs: Dict[str, Any] = {}
        self.workflows: Dict[str, Any] = {}

        # Ensure directories exist
        MODELS_PATH.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        INPUT_PATH.mkdir(parents=True, exist_ok=True)

        # Tool definitions (must be defined before creating methods)
        self.tools = [
            {
                "name": "generate_image",
                "description": "Generate an image using ComfyUI workflow",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow": {
                            "type": "object",
                            "description": "ComfyUI workflow JSON",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Text prompt for generation",
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "Negative prompt",
                            "default": "",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Image width",
                            "default": 512,
                        },
                        "height": {
                            "type": "integer",
                            "description": "Image height",
                            "default": 512,
                        },
                        "seed": {
                            "type": "integer",
                            "description": "Random seed",
                            "default": -1,
                        },
                        "steps": {
                            "type": "integer",
                            "description": "Number of steps",
                            "default": 20,
                        },
                        "cfg_scale": {
                            "type": "number",
                            "description": "CFG scale",
                            "default": 7.0,
                        },
                    },
                    "required": ["prompt"],
                },
            },
            {
                "name": "list_workflows",
                "description": "List available ComfyUI workflows",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_workflow",
                "description": "Get a specific workflow",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "Workflow name"}},
                    "required": ["name"],
                },
            },
            {
                "name": "list_models",
                "description": "List available models",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["checkpoint", "lora", "vae", "embeddings"],
                            "description": "Model type",
                        }
                    },
                },
            },
            {
                "name": "upload_lora",
                "description": "Upload a LoRA model to ComfyUI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename for the LoRA",
                        },
                        "data": {
                            "type": "string",
                            "description": "Base64 encoded LoRA data",
                        },
                        "metadata": {"type": "object", "description": "LoRA metadata"},
                    },
                    "required": ["filename", "data"],
                },
            },
            {
                "name": "upload_lora_chunked_init",
                "description": "Initialize chunked upload for large LoRA files",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename for the LoRA",
                        },
                        "total_size": {
                            "type": "integer",
                            "description": "Total file size in bytes",
                        },
                        "metadata": {"type": "object", "description": "LoRA metadata"},
                    },
                    "required": ["filename", "total_size"],
                },
            },
            {
                "name": "upload_lora_chunk",
                "description": "Upload a chunk of a large LoRA file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "upload_id": {
                            "type": "string",
                            "description": "Upload ID from init",
                        },
                        "chunk_index": {
                            "type": "integer",
                            "description": "Chunk index",
                        },
                        "chunk": {
                            "type": "string",
                            "description": "Base64 encoded chunk data",
                        },
                        "total_chunks": {
                            "type": "integer",
                            "description": "Total number of chunks",
                        },
                    },
                    "required": ["upload_id", "chunk_index", "chunk", "total_chunks"],
                },
            },
            {
                "name": "upload_lora_chunked_complete",
                "description": "Complete a chunked LoRA upload",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "upload_id": {
                            "type": "string",
                            "description": "Upload ID from init",
                        }
                    },
                    "required": ["upload_id"],
                },
            },
            {
                "name": "list_loras",
                "description": "List available LoRA models",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "download_lora",
                "description": "Download a LoRA model from ComfyUI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "LoRA filename"},
                        "encoding": {
                            "type": "string",
                            "enum": ["base64", "raw"],
                            "default": "base64",
                        },
                    },
                    "required": ["filename"],
                },
            },
            {
                "name": "get_object_info",
                "description": "Get ComfyUI node and model information",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_system_info",
                "description": "Get ComfyUI system information",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "transfer_lora_from_ai_toolkit",
                "description": "Transfer a LoRA from AI Toolkit to ComfyUI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Model name in AI Toolkit",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Target filename in ComfyUI",
                        },
                    },
                    "required": ["model_name", "filename"],
                },
            },
            {
                "name": "execute_workflow",
                "description": "Execute a custom ComfyUI workflow",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow": {
                            "type": "object",
                            "description": "Complete workflow JSON",
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Client ID for websocket updates",
                        },
                    },
                    "required": ["workflow"],
                },
            },
        ]

        # Create dynamic tool methods after tools are defined
        self._create_tool_methods()

    async def handle_tools_list(self, request: Request) -> Response:
        """Handle tools list request"""
        return Response(
            content=json.dumps({"tools": self.tools}),
            media_type="application/json",
        )

    async def handle_execute(self, request: Request) -> Response:
        """Handle tool execution request"""
        try:
            # Get request data
            data = await request.json()
            tool_name = data.get("tool")
            params = data.get("params", {})

            # Execute tool locally
            if tool_name == "generate_image":
                result = self.generate_image(params)
            elif tool_name == "list_models":
                result = self.list_models(params)
            elif tool_name == "get_workflow":
                result = self.get_workflow(params)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            return Response(
                content=json.dumps(result),
                media_type="application/json",
            )
        except Exception as e:
            self.logger.error(f"Error executing tool: {e}")
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=500,
                media_type="application/json",
            )

    def generate_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an image"""
        import uuid

        job_id = str(uuid.uuid4())
        self.generation_jobs[job_id] = {"status": "generating", "params": params}
        return {"status": "success", "job_id": job_id}

    def list_models(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available models"""
        return {
            "models": [
                {"name": "sd15", "type": "checkpoint"},
                {"name": "sdxl", "type": "checkpoint"},
            ]
        }

    def get_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a workflow"""
        workflow_name = params.get("name")
        if workflow_name:
            workflow = self.workflows.get(workflow_name, {})
            return {"workflow": workflow, "name": workflow_name}
        return {"workflow": {}, "name": None}

    def get_tools(self) -> dict:
        """Return dictionary of available tools and their metadata"""
        # Convert tools list to dictionary format expected by base class
        tools_dict = {}
        for tool in self.tools:
            tools_dict[tool["name"]] = {
                "description": tool["description"],
                "parameters": tool["inputSchema"],  # Base class expects 'parameters' not 'inputSchema'
            }
        return tools_dict

    def _create_tool_methods(self):
        """Dynamically create tool methods that forward to remote server"""
        for tool in self.tools:
            tool_name = tool["name"]

            # Create a closure to capture the tool name
            def make_tool_method(name):
                async def tool_method(**kwargs):
                    """Execute tool locally"""
                    if name == "generate_image":
                        return self.generate_image(kwargs)
                    elif name == "list_models":
                        return self.list_models(kwargs)
                    elif name == "get_workflow":
                        return self.get_workflow(kwargs)
                    else:
                        return {"error": f"Tool {name} not implemented"}

                return tool_method

            # Set the method on the instance
            setattr(self, tool_name, make_tool_method(tool_name))


def main():
    """Main entry point"""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="ComfyUI MCP Server")
    parser.add_argument("--port", type=int, default=8013, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--mode", choices=["http", "stdio"], default="http", help="Server mode")

    args = parser.parse_args()

    if args.mode == "stdio":
        print("ComfyUI MCP Server does not support stdio mode (remote bridge required)")
        return

    # Create and run server
    server = ComfyUIMCPServer(port=args.port)

    print(f"Starting ComfyUI MCP Server on {args.host}:{args.port}")
    print(f"ComfyUI MCP Server on port {server.port}")

    uvicorn.run(server.app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
