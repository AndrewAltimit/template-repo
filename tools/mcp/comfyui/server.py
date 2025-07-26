"""ComfyUI MCP Server - Bridge to remote AI image generation service"""

import json
import os

from fastapi import Request, Response

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# Remote server configuration
REMOTE_HOST = os.environ.get("COMFYUI_HOST", "192.168.0.152")
REMOTE_PORT = int(os.environ.get("COMFYUI_PORT", "8013"))
REMOTE_URL = f"http://{REMOTE_HOST}:{REMOTE_PORT}"


class ComfyUIMCPServer(BaseMCPServer):
    """MCP Server for ComfyUI - AI image generation"""

    def __init__(self, port: int = 8013):
        super().__init__(
            name="ComfyUI MCP Server",
            version="1.0.0",
            port=port,
        )

        # Initialize for remote forwarding
        self.remote_url = REMOTE_URL
        self.logger = setup_logging("comfyui_mcp")

        # Tool definitions
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
                        "error": "Remote ComfyUI server not available",
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
    app = server.create_app()

    print(f"Starting ComfyUI MCP Server on {args.host}:{args.port}")
    print(f"Remote server: {REMOTE_URL}")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
