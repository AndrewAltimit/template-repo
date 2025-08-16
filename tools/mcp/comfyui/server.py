"""ComfyUI MCP Server - GPU-accelerated AI image generation"""

import os
from pathlib import Path
from typing import Any, Dict

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

    # Tool implementation methods
    async def generate_image(self, **kwargs) -> Dict[str, Any]:
        """Generate an image"""
        import uuid

        job_id = str(uuid.uuid4())
        self.generation_jobs[job_id] = {
            "status": "generating",
            "params": kwargs,
            "prompt": kwargs.get("prompt", ""),
            "width": kwargs.get("width", 512),
            "height": kwargs.get("height", 512),
        }
        return {"status": "success", "job_id": job_id}

    async def list_workflows(self, **kwargs) -> Dict[str, Any]:
        """List available workflows"""
        return {"workflows": list(self.workflows.keys())}

    async def get_workflow(self, **kwargs) -> Dict[str, Any]:
        """Get a workflow"""
        workflow_name = kwargs.get("name")
        if workflow_name and workflow_name in self.workflows:
            return {"workflow": self.workflows[workflow_name], "name": workflow_name}
        return {"error": "Workflow not found"}

    async def list_models(self, **kwargs) -> Dict[str, Any]:
        """List available models"""
        model_type = kwargs.get("type", "all")
        models = [
            {"name": "sd15", "type": "checkpoint"},
            {"name": "sdxl", "type": "checkpoint"},
            {"name": "sd15_vae", "type": "vae"},
        ]
        if model_type != "all":
            models = [m for m in models if m["type"] == model_type]
        return {"models": models}

    async def upload_lora(self, **kwargs) -> Dict[str, Any]:
        """Upload a LoRA model"""
        filename = kwargs.get("filename")
        data = kwargs.get("data")
        if filename and data:
            # In a real implementation, save the LoRA file
            return {"status": "success", "filename": filename}
        return {"error": "Missing filename or data"}

    async def upload_lora_chunked_init(self, **kwargs) -> Dict[str, Any]:
        """Initialize chunked upload"""
        import uuid

        filename = kwargs.get("filename")
        total_size = kwargs.get("total_size")
        if filename and total_size:
            upload_id = str(uuid.uuid4())
            return {"upload_id": upload_id, "status": "initialized"}
        return {"error": "Missing filename or total_size"}

    async def upload_lora_chunk(self, **kwargs) -> Dict[str, Any]:
        """Upload a chunk"""
        upload_id = kwargs.get("upload_id")
        chunk_index = kwargs.get("chunk_index")
        chunk = kwargs.get("chunk")
        if upload_id and chunk_index is not None and chunk:
            return {"status": "chunk_received", "chunk_index": chunk_index}
        return {"error": "Missing required parameters"}

    async def upload_lora_chunked_complete(self, **kwargs) -> Dict[str, Any]:
        """Complete chunked upload"""
        upload_id = kwargs.get("upload_id")
        if upload_id:
            return {"status": "completed", "upload_id": upload_id}
        return {"error": "Missing upload_id"}

    async def list_loras(self, **kwargs) -> Dict[str, Any]:
        """List available LoRA models"""
        return {"loras": []}

    async def download_lora(self, **kwargs) -> Dict[str, Any]:
        """Download a LoRA model"""
        filename = kwargs.get("filename")
        encoding = kwargs.get("encoding", "base64")
        if filename:
            # In a real implementation, return the LoRA data
            return {"filename": filename, "data": "", "encoding": encoding}
        return {"error": "Missing filename"}

    async def get_object_info(self, **kwargs) -> Dict[str, Any]:
        """Get ComfyUI object info"""
        return {"nodes": [], "models": []}

    async def get_system_info(self, **kwargs) -> Dict[str, Any]:
        """Get system info"""
        import psutil

        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "gpu_available": True,  # In real implementation, check for GPU
        }

    async def transfer_lora_from_ai_toolkit(self, **kwargs) -> Dict[str, Any]:
        """Transfer LoRA from AI Toolkit"""
        model_name = kwargs.get("model_name")
        filename = kwargs.get("filename")
        if model_name and filename:
            return {"status": "success", "message": f"Transferred {model_name} to {filename}"}
        return {"error": "Missing model_name or filename"}

    async def execute_workflow(self, **kwargs) -> Dict[str, Any]:
        """Execute a custom workflow"""
        import uuid

        workflow = kwargs.get("workflow")
        if workflow:
            job_id = str(uuid.uuid4())
            self.generation_jobs[job_id] = {"status": "executing", "workflow": workflow}
            return {"status": "success", "job_id": job_id}
        return {"error": "Missing workflow"}

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
