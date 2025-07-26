"""AI Toolkit MCP Server - Bridge to remote AI training service"""

import json
import os

from fastapi import Request, Response

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# Remote server configuration
REMOTE_HOST = os.environ.get("AI_TOOLKIT_HOST", "192.168.0.152")
REMOTE_PORT = int(os.environ.get("AI_TOOLKIT_PORT", "8012"))
REMOTE_URL = f"http://{REMOTE_HOST}:{REMOTE_PORT}"


class AIToolkitMCPServer(BaseMCPServer):
    """MCP Server for AI Toolkit - AI model training management"""

    def __init__(self, port: int = 8012):
        super().__init__(
            name="AI Toolkit MCP Server",
            version="1.0.0",
            port=port,
        )

        # Initialize HTTP bridge for forwarding requests
        self.remote_url = REMOTE_URL
        self.logger = setup_logging("ai_toolkit_mcp")

        # Tool definitions
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

            # Forward to remote server
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.remote_url}/mcp/execute", json=data)

                if response.status_code == 200:
                    return Response(content=response.text, media_type="application/json")
                else:
                    return Response(
                        content=json.dumps(
                            {
                                "error": f"Remote server error: {response.status_code}",
                                "details": response.text,
                            }
                        ),
                        status_code=response.status_code,
                        media_type="application/json",
                    )
        except httpx.ConnectError:
            self.logger.error(f"Could not connect to remote server at {self.remote_url}")
            return Response(
                content=json.dumps(
                    {
                        "error": "Remote AI Toolkit server not available",
                        "type": "remote_connection_error",
                        "remote_url": self.remote_url,
                    }
                ),
                status_code=503,
                media_type="application/json",
            )
        except Exception as e:
            self.logger.error(f"Error forwarding request: {e}")
            return Response(
                content=json.dumps({"error": str(e), "type": "remote_connection_error"}),
                status_code=503,
                media_type="application/json",
            )

    def get_tools(self) -> dict:
        """Return dictionary of available tools and their metadata"""
        # Convert tools list to dictionary format expected by base class
        tools_dict = {}
        for tool in self.tools:
            tools_dict[tool["name"]] = {
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }
        return tools_dict


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
    print(f"Remote server: {REMOTE_URL}")

    uvicorn.run(server.app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
