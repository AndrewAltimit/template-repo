"""AI Toolkit MCP Server - GPU-accelerated LoRA training management"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Request, Response

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# AI Toolkit configuration
AI_TOOLKIT_PATH = os.environ.get("AI_TOOLKIT_PATH", "/ai-toolkit")
DATASETS_PATH = Path(AI_TOOLKIT_PATH) / "datasets"
OUTPUTS_PATH = Path(AI_TOOLKIT_PATH) / "outputs"
CONFIGS_PATH = Path(AI_TOOLKIT_PATH) / "configs"


class AIToolkitMCPServer(BaseMCPServer):
    """MCP Server for AI Toolkit - AI model training management"""

    def __init__(self, port: int = 8012):
        super().__init__(
            name="AI Toolkit MCP Server",
            version="1.0.0",
            port=port,
        )

        # Initialize server state
        self.logger = setup_logging("ai_toolkit_mcp")
        self.training_jobs: Dict[str, Any] = {}
        self.configs: Dict[str, Any] = {}

        # Ensure directories exist
        DATASETS_PATH.mkdir(parents=True, exist_ok=True)
        OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)
        CONFIGS_PATH.mkdir(parents=True, exist_ok=True)

        # Tool definitions (must be defined before creating methods)
        self.tools = [
            {
                "name": "create_training_config",
                "description": "Create a new training configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Configuration name"},
                        "model_name": {
                            "type": "string",
                            "description": "Base model to train from",
                        },
                        "dataset_path": {
                            "type": "string",
                            "description": "Path to training dataset",
                        },
                        "resolution": {
                            "type": "integer",
                            "description": "Training resolution",
                            "default": 512,
                        },
                        "steps": {
                            "type": "integer",
                            "description": "Number of training steps",
                            "default": 1000,
                        },
                        "rank": {
                            "type": "integer",
                            "description": "LoRA rank",
                            "default": 16,
                        },
                        "alpha": {
                            "type": "integer",
                            "description": "LoRA alpha",
                            "default": 16,
                        },
                        "low_vram": {
                            "type": "boolean",
                            "description": "Enable low VRAM mode",
                            "default": True,
                        },
                        "trigger_word": {
                            "type": "string",
                            "description": "Trigger word for the LoRA",
                        },
                        "test_prompts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Test prompts",
                        },
                    },
                    "required": ["name", "model_name", "dataset_path"],
                },
            },
            {
                "name": "list_configs",
                "description": "List all training configurations",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_config",
                "description": "Get a specific training configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "Configuration name"}},
                    "required": ["name"],
                },
            },
            {
                "name": "upload_dataset",
                "description": "Upload images to create a dataset",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_name": {
                            "type": "string",
                            "description": "Name for the dataset",
                        },
                        "images": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "filename": {"type": "string"},
                                    "data": {
                                        "type": "string",
                                        "description": "Base64 encoded image data",
                                    },
                                    "caption": {
                                        "type": "string",
                                        "description": "Image caption",
                                    },
                                },
                                "required": ["filename", "data", "caption"],
                            },
                        },
                    },
                    "required": ["dataset_name", "images"],
                },
            },
            {
                "name": "list_datasets",
                "description": "List all available datasets",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "start_training",
                "description": "Start a training job",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Configuration name to use",
                        }
                    },
                    "required": ["config_name"],
                },
            },
            {
                "name": "get_training_status",
                "description": "Get the status of a training job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string", "description": "Training job ID"}},
                    "required": ["job_id"],
                },
            },
            {
                "name": "stop_training",
                "description": "Stop a running training job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string", "description": "Training job ID"}},
                    "required": ["job_id"],
                },
            },
            {
                "name": "list_training_jobs",
                "description": "List all training jobs",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "export_model",
                "description": "Export a trained model",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_name": {"type": "string", "description": "Model name"},
                        "output_path": {
                            "type": "string",
                            "description": "Output path for the exported model",
                        },
                    },
                    "required": ["model_name", "output_path"],
                },
            },
            {
                "name": "list_exported_models",
                "description": "List all exported models",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "download_model",
                "description": "Download a trained model",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Model name to download",
                        },
                        "encoding": {
                            "type": "string",
                            "enum": ["base64", "raw"],
                            "default": "base64",
                        },
                    },
                    "required": ["model_name"],
                },
            },
            {
                "name": "get_system_stats",
                "description": "Get system statistics",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_training_logs",
                "description": "Get training logs for a job",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "Training job ID"},
                        "lines": {
                            "type": "integer",
                            "description": "Number of lines to retrieve",
                            "default": 100,
                        },
                    },
                    "required": ["job_id"],
                },
            },
            {
                "name": "get_training_info",
                "description": "Get detailed training information",
                "inputSchema": {"type": "object", "properties": {}},
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
            if tool_name == "create_training_config":
                result = self.create_training_config(params)
            elif tool_name == "start_training":
                result = self.start_training(params)
            elif tool_name == "get_training_status":
                result = self.get_training_status(params)
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

    def create_training_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a training configuration"""
        config_name = params.get("name")
        if config_name:
            self.configs[config_name] = params
        return {"status": "success", "config": config_name}

    def start_training(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start a training job"""
        import uuid

        job_id = str(uuid.uuid4())
        self.training_jobs[job_id] = {"status": "running", "config": params}
        return {"status": "success", "job_id": job_id}

    def get_training_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get training job status"""
        job_id = params.get("job_id")
        if job_id:
            job = self.training_jobs.get(job_id, {})
            return {"status": job.get("status", "unknown"), "job_id": job_id}
        return {"status": "error", "message": "No job_id provided"}

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
        """Dynamically create tool methods for MCP protocol"""
        for tool in self.tools:
            tool_name = tool["name"]

            # Create a closure to capture the tool name
            def make_tool_method(name):
                async def tool_method(**kwargs):
                    """Execute tool locally"""
                    if name == "create_training_config":
                        return self.create_training_config(kwargs)
                    elif name == "start_training":
                        return self.start_training(kwargs)
                    elif name == "get_training_status":
                        return self.get_training_status(kwargs)
                    else:
                        return {"error": f"Tool {name} not implemented"}

                return tool_method

            # Set the method on the instance
            setattr(self, tool_name, make_tool_method(tool_name))


def main():
    """Main entry point"""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="AI Toolkit MCP Server")
    parser.add_argument("--port", type=int, default=8012, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--mode", choices=["http", "stdio"], default="http", help="Server mode")

    args = parser.parse_args()

    if args.mode == "stdio":
        print("AI Toolkit MCP Server does not support stdio mode (remote bridge required)")
        return

    # Create and run server
    server = AIToolkitMCPServer(port=args.port)

    print(f"Starting AI Toolkit MCP Server on {args.host}:{args.port}")
    print(f"AI Toolkit MCP Server on port {server.port}")

    uvicorn.run(server.app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
