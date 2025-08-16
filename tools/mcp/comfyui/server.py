"""ComfyUI MCP Server - Functional implementation with actual ComfyUI integration"""

import asyncio
import base64
import binascii
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# ComfyUI configuration
COMFYUI_HOST = os.environ.get("COMFYUI_HOST", "localhost")
COMFYUI_PORT = int(os.environ.get("COMFYUI_PORT", "8188"))
COMFYUI_PATH = os.environ.get("COMFYUI_PATH", "/comfyui")
MODELS_PATH = Path(COMFYUI_PATH) / "models"
OUTPUT_PATH = Path(COMFYUI_PATH) / "output"
INPUT_PATH = Path(COMFYUI_PATH) / "input"


class ComfyUIMCPServer(BaseMCPServer):
    """MCP Server for ComfyUI - Functional AI image generation"""

    def __init__(self, port: int = 8013):
        super().__init__(
            name="ComfyUI MCP Server",
            version="2.0.0",
            port=port,
        )

        # Initialize server state
        self.logger = setup_logging("comfyui_mcp")
        self.generation_jobs: Dict[str, Any] = {}
        self.client_id = str(uuid.uuid4())

        # Configurable timeout for generation (in seconds)
        self.generation_timeout = int(os.environ.get("COMFYUI_GENERATION_TIMEOUT", "300"))  # Default 5 minutes

        # ComfyUI API endpoints
        self.api_url = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"
        self.ws_url = f"ws://{COMFYUI_HOST}:{COMFYUI_PORT}/ws?clientId={self.client_id}"

        # Ensure directories exist
        MODELS_PATH.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        INPUT_PATH.mkdir(parents=True, exist_ok=True)

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
                        "timeout": {
                            "type": "integer",
                            "description": "Generation timeout in seconds (default: 300)",
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

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available tools as a dictionary"""
        tools_dict: Dict[str, Dict[str, Any]] = {}
        for tool in self.tools:
            tool_name = str(tool["name"])
            tools_dict[tool_name] = {"description": tool.get("description", ""), "parameters": tool.get("inputSchema", {})}
        return tools_dict

    def _create_default_workflow(
        self, prompt: str, negative_prompt: str, width: int, height: int, seed: int, steps: int, cfg_scale: float
    ) -> Dict[str, Any]:
        """Create a default SD 1.5 workflow"""
        if seed == -1:
            seed = int(time.time())

        return {
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "4": {"inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}, "class_type": "CheckpointLoaderSimple"},
            "5": {"inputs": {"width": width, "height": height, "batch_size": 1}, "class_type": "EmptyLatentImage"},
            "6": {"inputs": {"text": prompt, "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
            "7": {"inputs": {"text": negative_prompt, "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
            "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecode"},
            "9": {"inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}, "class_type": "SaveImage"},
        }

    async def _queue_prompt(self, workflow: Dict[str, Any]) -> Optional[str]:
        """Queue a prompt in ComfyUI and return the prompt ID"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"prompt": workflow, "client_id": self.client_id}

                async with session.post(f"{self.api_url}/prompt", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        prompt_id = result.get("prompt_id")
                        return str(prompt_id) if prompt_id else None
                    else:
                        self.logger.error(f"Failed to queue prompt: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error queuing prompt: {e}")
            return None

    async def _get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get the generation history for a prompt"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/history/{prompt_id}") as response:
                    if response.status == 200:
                        history: Dict[str, Any] = await response.json()
                        return history
                    return None
        except Exception as e:
            self.logger.error(f"Error getting history: {e}")
            return None

    async def _wait_for_completion(self, prompt_id: str, timeout: Optional[int] = None) -> bool:
        """Wait for a prompt to complete"""
        # Use provided timeout or instance default
        timeout = timeout if timeout is not None else self.generation_timeout

        start_time = time.time()
        while time.time() - start_time < timeout:
            history = await self._get_history(prompt_id)
            if history and prompt_id in history:
                prompt_history = history[prompt_id]
                if prompt_history.get("outputs"):
                    return True
            await asyncio.sleep(1)
        return False

    async def generate_image(self, **kwargs) -> Dict[str, Any]:
        """Generate an image using ComfyUI"""
        prompt = kwargs.get("prompt", "")
        negative_prompt = kwargs.get("negative_prompt", "")
        workflow = kwargs.get("workflow")
        timeout = kwargs.get("timeout")  # Optional timeout override

        # Use provided workflow or create default one
        if not workflow:
            workflow = self._create_default_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=kwargs.get("width", 512),
                height=kwargs.get("height", 512),
                seed=kwargs.get("seed", -1),
                steps=kwargs.get("steps", 20),
                cfg_scale=kwargs.get("cfg_scale", 7.0),
            )
        else:
            # Update prompt in provided workflow if it has text encode nodes
            for node_id, node in workflow.items():
                if node.get("class_type") == "CLIPTextEncode":
                    if "positive" in str(node.get("inputs", {})).lower():
                        node["inputs"]["text"] = prompt
                    elif "negative" in str(node.get("inputs", {})).lower():
                        node["inputs"]["text"] = negative_prompt

        # Queue the prompt
        prompt_id = await self._queue_prompt(workflow)
        if not prompt_id:
            return {"error": "Failed to queue generation"}

        # Create job entry
        job_id = str(uuid.uuid4())
        self.generation_jobs[job_id] = {"prompt_id": prompt_id, "status": "queued", "prompt": prompt, "workflow": workflow}

        # Wait for completion with optional timeout override
        completed = await self._wait_for_completion(prompt_id, timeout=timeout)

        if completed:
            # Get the output images
            history = await self._get_history(prompt_id)
            if history and prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                images = []
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        for img in node_output["images"]:
                            images.append(
                                {
                                    "filename": img["filename"],
                                    "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output"),
                                }
                            )

                self.generation_jobs[job_id]["status"] = "completed"
                self.generation_jobs[job_id]["images"] = images

                return {"status": "success", "job_id": job_id, "prompt_id": prompt_id, "images": images}
            else:
                # Completed but no history found
                self.generation_jobs[job_id]["status"] = "completed"
                return {"status": "success", "job_id": job_id, "prompt_id": prompt_id, "images": []}
        else:
            self.generation_jobs[job_id]["status"] = "timeout"
            return {"error": "Generation timed out", "job_id": job_id}

    async def list_workflows(self, **kwargs) -> Dict[str, Any]:
        """List available workflows"""
        workflows = [
            {"name": "default_sd15", "description": "Default Stable Diffusion 1.5 workflow"},
            {"name": "default_sdxl", "description": "Default SDXL workflow"},
            {"name": "img2img", "description": "Image to image workflow"},
            {"name": "inpainting", "description": "Inpainting workflow"},
        ]
        return {"workflows": workflows}

    async def get_workflow(self, **kwargs) -> Dict[str, Any]:
        """Get a specific workflow template"""
        name = kwargs.get("name", "default_sd15")

        if name == "default_sd15":
            return {"workflow": self._create_default_workflow("A beautiful landscape", "", 512, 512, -1, 20, 7.0)}
        elif name == "default_sdxl":
            # Return SDXL workflow template
            return {
                "workflow": {
                    "4": {"inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}, "class_type": "CheckpointLoaderSimple"},
                    # ... simplified for brevity
                }
            }
        else:
            return {"error": "Workflow not found"}

    async def list_models(self, **kwargs) -> Dict[str, Any]:
        """List available models in ComfyUI"""
        model_type = kwargs.get("type", "checkpoint")

        try:
            # Get object info from ComfyUI which includes available models
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/object_info") as response:
                    if response.status == 200:
                        object_info = await response.json()

                        # Extract model lists based on type
                        if model_type == "checkpoint":
                            models = (
                                object_info.get("CheckpointLoaderSimple", {})
                                .get("input", {})
                                .get("required", {})
                                .get("ckpt_name", [[]])[0]
                            )
                        elif model_type == "lora":
                            models = (
                                object_info.get("LoraLoader", {})
                                .get("input", {})
                                .get("required", {})
                                .get("lora_name", [[]])[0]
                            )
                        elif model_type == "vae":
                            models = (
                                object_info.get("VAELoader", {}).get("input", {}).get("required", {}).get("vae_name", [[]])[0]
                            )
                        else:
                            models = []

                        return {"models": models, "type": model_type}
                    else:
                        return {"models": [], "error": f"API returned status {response.status}"}
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error listing models: {e}")
            return {"models": [], "error": f"Network error: {str(e)}"}
        except KeyError as e:
            self.logger.error(f"Unexpected API response structure: {e}")
            return {"models": [], "error": f"API response error: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Unexpected error listing models: {e}")
            return {"models": [], "error": str(e)}

    async def upload_lora(self, **kwargs) -> Dict[str, Any]:
        """Upload a LoRA model to ComfyUI"""
        filename = kwargs.get("filename")
        data = kwargs.get("data")
        metadata = kwargs.get("metadata", {})

        if not filename or not data:
            return {"error": "Missing required fields: filename and data"}

        try:
            # Decode base64 data
            lora_data = base64.b64decode(data)

            # Save to ComfyUI models/loras directory
            lora_path = MODELS_PATH / "loras" / filename
            lora_path.parent.mkdir(parents=True, exist_ok=True)

            with open(lora_path, "wb") as f:
                f.write(lora_data)

            # Save metadata if provided
            if metadata:
                metadata_path = lora_path.with_suffix(".json")
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)

            return {"status": "success", "filename": filename, "path": str(lora_path), "size": len(lora_data)}
        except binascii.Error as e:
            self.logger.error(f"Invalid base64 data: {e}")
            return {"error": f"Invalid base64 encoding: {str(e)}"}
        except OSError as e:
            self.logger.error(f"File system error uploading LoRA: {e}")
            return {"error": f"File system error: {str(e)}"}
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid metadata JSON: {e}")
            return {"error": f"Invalid metadata JSON: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Unexpected error uploading LoRA: {e}")
            return {"error": f"Failed to upload LoRA: {str(e)}"}

    async def list_loras(self, **kwargs) -> Dict[str, Any]:
        """List available LoRA models"""
        loras = []
        lora_dir = MODELS_PATH / "loras"

        if lora_dir.exists():
            for lora_file in lora_dir.glob("*.safetensors"):
                loras.append({"name": lora_file.stem, "filename": lora_file.name, "size": lora_file.stat().st_size})
            for lora_file in lora_dir.glob("*.ckpt"):
                loras.append({"name": lora_file.stem, "filename": lora_file.name, "size": lora_file.stat().st_size})

        return {"loras": loras}

    async def download_lora(self, **kwargs) -> Dict[str, Any]:
        """Download a LoRA model from ComfyUI"""
        filename = kwargs.get("filename")
        encoding = kwargs.get("encoding", "base64")

        if not filename:
            return {"error": "Missing required field: filename"}

        lora_path = MODELS_PATH / "loras" / filename

        if lora_path.exists():
            try:
                with open(lora_path, "rb") as f:
                    data = f.read()

                if encoding == "base64":
                    return {
                        "status": "success",
                        "filename": filename,
                        "data": base64.b64encode(data).decode("utf-8"),
                        "size": len(data),
                    }
                else:
                    return {"status": "success", "filename": filename, "data": data, "size": len(data)}
            except Exception as e:
                return {"error": f"Failed to read LoRA: {str(e)}"}

        return {"error": "LoRA not found"}

    async def get_object_info(self, **kwargs) -> Dict[str, Any]:
        """Get ComfyUI node and model information"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/object_info") as response:
                    if response.status == 200:
                        info: Dict[str, Any] = await response.json()
                        return info
                    return {"error": f"Failed to get object info: {response.status}"}
        except Exception as e:
            return {"error": f"Failed to get object info: {str(e)}"}

    async def get_system_info(self, **kwargs) -> Dict[str, Any]:
        """Get ComfyUI system information"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/system_stats") as response:
                    if response.status == 200:
                        stats = await response.json()
                        return {"status": "success", "system": stats.get("system", {}), "devices": stats.get("devices", [])}
                    return {"error": f"Failed to get system info: {response.status}"}
        except Exception as e:
            return {"error": f"Failed to get system info: {str(e)}"}

    async def execute_workflow(self, **kwargs) -> Dict[str, Any]:
        """Execute a custom ComfyUI workflow"""
        workflow = kwargs.get("workflow")
        client_id = kwargs.get("client_id", self.client_id)

        if not workflow:
            return {"error": "No workflow provided"}

        # Queue the workflow
        prompt_id = await self._queue_prompt(workflow)
        if not prompt_id:
            return {"error": "Failed to queue workflow"}

        # Create job entry
        job_id = str(uuid.uuid4())
        self.generation_jobs[job_id] = {
            "prompt_id": prompt_id,
            "status": "queued",
            "workflow": workflow,
            "client_id": client_id,
        }

        return {"status": "success", "job_id": job_id, "prompt_id": prompt_id, "message": "Workflow queued for execution"}


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="ComfyUI MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http"], default="http", help="Server mode")
    parser.add_argument("--port", type=int, default=8013, help="Port for HTTP mode")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for HTTP mode")

    args = parser.parse_args()

    server = ComfyUIMCPServer(port=args.port)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
