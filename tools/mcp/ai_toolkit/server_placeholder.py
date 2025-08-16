"""AI Toolkit MCP Server - GPU-accelerated LoRA training management"""

import os
from pathlib import Path
from typing import Any, Dict

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

    # Tool implementation methods
    async def create_training_config(self, **kwargs) -> Dict[str, Any]:
        """Create a training configuration"""
        config_name = kwargs.get("name")
        if config_name:
            self.configs[config_name] = kwargs
        return {"status": "success", "config": config_name}

    async def list_configs(self, **kwargs) -> Dict[str, Any]:
        """List all training configurations"""
        return {"configs": list(self.configs.keys())}

    async def get_config(self, **kwargs) -> Dict[str, Any]:
        """Get a specific configuration"""
        config_name = kwargs.get("name")
        if config_name and config_name in self.configs:
            return {"config": self.configs[config_name]}
        return {"error": "Configuration not found"}

    async def upload_dataset(self, **kwargs) -> Dict[str, Any]:
        """Upload a dataset"""
        dataset_name = kwargs.get("dataset_name")
        return {"status": "success", "dataset": dataset_name}

    async def list_datasets(self, **kwargs) -> Dict[str, Any]:
        """List available datasets"""
        # In a real implementation, this would list actual datasets
        return {"datasets": []}

    async def start_training(self, **kwargs) -> Dict[str, Any]:
        """Start a training job"""
        import uuid

        config_name = kwargs.get("config_name")
        job_id = str(uuid.uuid4())
        self.training_jobs[job_id] = {"status": "running", "config": config_name, "progress": 0}
        return {"status": "success", "job_id": job_id}

    async def stop_training(self, **kwargs) -> Dict[str, Any]:
        """Stop a training job"""
        job_id = kwargs.get("job_id")
        if job_id and job_id in self.training_jobs:
            self.training_jobs[job_id]["status"] = "stopped"
            return {"status": "success", "job_id": job_id}
        return {"error": "Job not found"}

    async def get_training_status(self, **kwargs) -> Dict[str, Any]:
        """Get training job status"""
        job_id = kwargs.get("job_id")
        if job_id and job_id in self.training_jobs:
            job = self.training_jobs[job_id]
            return {"status": job.get("status", "unknown"), "job_id": job_id, "progress": job.get("progress", 0)}
        return {"status": "error", "message": "Job not found"}

    async def list_training_jobs(self, **kwargs) -> Dict[str, Any]:
        """List all training jobs"""
        jobs = []
        for job_id, job_data in self.training_jobs.items():
            jobs.append({"job_id": job_id, "status": job_data.get("status"), "config": job_data.get("config")})
        return {"jobs": jobs}

    async def export_model(self, **kwargs) -> Dict[str, Any]:
        """Export a trained model"""
        model_name = kwargs.get("model_name")
        output_path = kwargs.get("output_path", f"/ai-toolkit/outputs/{model_name}")
        return {"status": "success", "path": output_path}

    async def list_exported_models(self, **kwargs) -> Dict[str, Any]:
        """List exported models"""
        # In a real implementation, this would list actual models
        return {"models": []}

    async def download_model(self, **kwargs) -> Dict[str, Any]:
        """Download a model"""
        model_name = kwargs.get("model_name")
        # In a real implementation, this would return the model data
        return {"status": "success", "model": model_name}

    async def get_system_stats(self, **kwargs) -> Dict[str, Any]:
        """Get system statistics"""
        import psutil

        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
        }

    async def get_training_logs(self, **kwargs) -> Dict[str, Any]:
        """Get training logs"""
        job_id = kwargs.get("job_id")
        lines = kwargs.get("lines", 100)
        # In a real implementation, this would return actual logs
        return {"job_id": job_id, "logs": [], "lines": lines}

    async def delete_config(self, **kwargs) -> Dict[str, Any]:
        """Delete a configuration"""
        config_name = kwargs.get("name")
        if config_name and config_name in self.configs:
            del self.configs[config_name]
            return {"status": "success", "message": f"Deleted config: {config_name}"}
        return {"error": "Configuration not found"}

    async def update_config(self, **kwargs) -> Dict[str, Any]:
        """Update a configuration"""
        config_name = kwargs.get("name")
        if config_name and config_name in self.configs:
            # Update with new values, keeping existing ones
            self.configs[config_name].update(kwargs)
            return {"status": "success", "config": config_name}
        return {"error": "Configuration not found"}

    async def delete_dataset(self, **kwargs) -> Dict[str, Any]:
        """Delete a dataset"""
        dataset_name = kwargs.get("name")
        return {"status": "success", "message": f"Deleted dataset: {dataset_name}"}

    async def get_model_info(self, **kwargs) -> Dict[str, Any]:
        """Get model information"""
        model_name = kwargs.get("name")
        return {"model": model_name, "info": {}}

    async def delete_model(self, **kwargs) -> Dict[str, Any]:
        """Delete a model"""
        model_name = kwargs.get("name")
        return {"status": "success", "message": f"Deleted model: {model_name}"}

    async def list_models(self, **kwargs) -> Dict[str, Any]:
        """List available models"""
        return {"models": []}

    async def get_training_info(self, **kwargs) -> Dict[str, Any]:
        """Get training information"""
        return {
            "total_jobs": len(self.training_jobs),
            "active_jobs": sum(1 for j in self.training_jobs.values() if j.get("status") == "running"),
            "configs": len(self.configs),
        }


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
