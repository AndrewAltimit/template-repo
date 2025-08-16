"""AI Toolkit MCP Server - Functional implementation with actual AI Toolkit integration"""

import asyncio
import base64
import binascii
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

# AI Toolkit configuration
AI_TOOLKIT_PATH = os.environ.get("AI_TOOLKIT_PATH", "/ai-toolkit")
DATASETS_PATH = Path(AI_TOOLKIT_PATH) / "datasets"
OUTPUTS_PATH = Path(AI_TOOLKIT_PATH) / "outputs"
CONFIGS_PATH = Path(AI_TOOLKIT_PATH) / "config"  # AI Toolkit uses 'config' not 'configs'

# Add AI Toolkit to Python path for imports
sys.path.insert(0, AI_TOOLKIT_PATH)


class AIToolkitMCPServer(BaseMCPServer):
    """MCP Server for AI Toolkit - Functional AI model training management"""

    def __init__(self, port: int = 8012):
        super().__init__(
            name="AI Toolkit MCP Server",
            version="2.0.0",
            port=port,
        )

        # Initialize server state
        self.logger = setup_logging("ai_toolkit_mcp")
        self.training_jobs: Dict[str, Any] = {}
        self.training_processes: Dict[str, asyncio.subprocess.Process] = {}

        # Ensure directories exist
        DATASETS_PATH.mkdir(parents=True, exist_ok=True)
        OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)
        CONFIGS_PATH.mkdir(parents=True, exist_ok=True)

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
                        "dataset_name": {"type": "string", "description": "Name for the dataset"},
                        "images": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "filename": {"type": "string"},
                                    "data": {"type": "string", "description": "Base64 encoded image data"},
                                    "caption": {"type": "string", "description": "Image caption"},
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
                    "properties": {"config_name": {"type": "string", "description": "Configuration name to use"}},
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
                        "output_path": {"type": "string", "description": "Output path for the exported model"},
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
                        "model_name": {"type": "string", "description": "Model name to download"},
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
                        "lines": {"type": "integer", "description": "Number of lines to retrieve", "default": 100},
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

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available tools as a dictionary"""
        tools_dict: Dict[str, Dict[str, Any]] = {}
        for tool in self.tools:
            tool_name = str(tool["name"])
            tools_dict[tool_name] = {"description": tool.get("description", ""), "parameters": tool.get("inputSchema", {})}
        return tools_dict

    async def create_training_config(self, **kwargs) -> Dict[str, Any]:
        """Create a new training configuration file for AI Toolkit"""
        config_name = kwargs.get("name")

        # Create AI Toolkit compatible config
        config = {
            "job": "extension",
            "config": {
                "name": config_name,
                "process": [
                    {
                        "type": "sd_trainer",
                        "training_folder": kwargs.get("dataset_path", f"{DATASETS_PATH}/{config_name}"),
                        "output_name": config_name,
                        "save_root": str(OUTPUTS_PATH),
                        "device": "cuda:0",
                        "network": {
                            "type": "lora",
                            "linear": kwargs.get("rank", 16),
                            "linear_alpha": kwargs.get("alpha", 16),
                        },
                        "train": {
                            "noise_scheduler": "ddpm",
                            "steps": kwargs.get("steps", 1000),
                            "lr": 1e-4,
                            "gradient_accumulation_steps": 1,
                            "train_unet": True,
                            "train_text_encoder": False,
                            "content_or_style": "balanced",
                            "clip_skip": 2,
                            "ema_config": {
                                "use_ema": True,
                                "ema_decay": 0.99,
                            },
                        },
                        "model": {
                            "name_or_path": kwargs.get("model_name", "runwayml/stable-diffusion-v1-5"),
                            "is_v2": False,
                            "is_v_pred": False,
                            "quantize": True,
                        },
                        "sample": {
                            "sampler": "ddpm",
                            "sample_every": 100,
                            "width": kwargs.get("resolution", 512),
                            "height": kwargs.get("resolution", 512),
                            "prompts": kwargs.get("test_prompts", []),
                            "neg": "",
                            "seed": 42,
                            "walk_seed": True,
                            "guidance_scale": 7.5,
                            "sample_steps": 20,
                        },
                        "trigger_word": kwargs.get("trigger_word", ""),
                    }
                ],
            },
            "meta": {
                "name": config_name,
                "version": "1.0",
            },
        }

        # Save config file
        config_path = CONFIGS_PATH / f"{config_name}.yaml"
        try:
            import yaml

            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            self.logger.info(f"Created training config: {config_path}")
            return {"status": "success", "config": config_name, "path": str(config_path)}
        except OSError as e:
            self.logger.error(f"Failed to save config file: {e}")
            return {"error": f"Failed to save config file: {str(e)}"}
        except yaml.YAMLError as e:
            self.logger.error(f"Failed to serialize config to YAML: {e}")
            return {"error": f"Failed to serialize config: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Unexpected error creating config: {e}")
            return {"error": f"Failed to create config: {str(e)}"}

    async def list_configs(self, **kwargs) -> Dict[str, Any]:
        """List all training configurations"""
        configs = []
        for config_file in CONFIGS_PATH.glob("*.yaml"):
            configs.append(config_file.stem)
        return {"configs": configs}

    async def get_config(self, **kwargs) -> Dict[str, Any]:
        """Get a specific training configuration"""
        config_name = kwargs.get("name")
        config_path = CONFIGS_PATH / f"{config_name}.yaml"

        if config_path.exists():
            try:
                import yaml

                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                return {"config": config}
            except yaml.YAMLError as e:
                return {"error": f"Invalid YAML format: {str(e)}"}
            except OSError as e:
                return {"error": f"Failed to read config file: {str(e)}"}
            except Exception as e:
                return {"error": f"Unexpected error reading config: {str(e)}"}
        return {"error": "Configuration not found"}

    async def upload_dataset(self, **kwargs) -> Dict[str, Any]:
        """Upload images to create a dataset"""
        dataset_name = kwargs.get("dataset_name")
        images = kwargs.get("images", [])

        if not dataset_name:
            return {"error": "Missing required field: dataset_name"}

        dataset_path = DATASETS_PATH / dataset_name
        dataset_path.mkdir(parents=True, exist_ok=True)

        saved_images = []
        for img_data in images:
            try:
                filename = img_data["filename"]
                data = base64.b64decode(img_data["data"])
                caption = img_data["caption"]

                # Save image
                img_path = dataset_path / filename
                with open(img_path, "wb") as f:
                    f.write(data)

                # Save caption
                caption_path = dataset_path / f"{Path(filename).stem}.txt"
                with open(caption_path, "w") as f:
                    f.write(caption)

                saved_images.append(filename)
            except KeyError as e:
                self.logger.error(f"Missing required field in image data: {e}")
            except binascii.Error as e:
                self.logger.error(f"Invalid base64 encoding for image {img_data.get('filename', 'unknown')}: {e}")
            except OSError as e:
                self.logger.error(f"Failed to save image {img_data.get('filename', 'unknown')}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error processing image {img_data.get('filename', 'unknown')}: {e}")

        return {
            "status": "success",
            "dataset": dataset_name,
            "images_saved": len(saved_images),
            "path": str(dataset_path),
        }

    async def list_datasets(self, **kwargs) -> Dict[str, Any]:
        """List all available datasets"""
        datasets = []
        for dataset_dir in DATASETS_PATH.iterdir():
            if dataset_dir.is_dir():
                image_count = len(list(dataset_dir.glob("*.png")) + list(dataset_dir.glob("*.jpg")))
                datasets.append({"name": dataset_dir.name, "images": image_count})
        return {"datasets": datasets}

    async def start_training(self, **kwargs) -> Dict[str, Any]:
        """Start a training job using AI Toolkit"""
        config_name = kwargs.get("config_name")
        config_path = CONFIGS_PATH / f"{config_name}.yaml"

        if not config_path.exists():
            return {"error": "Configuration not found"}

        job_id = str(uuid.uuid4())

        try:
            # Start training process using asyncio for non-blocking execution
            cmd = [
                sys.executable,
                "run.py",
                str(config_path),
            ]

            log_file = OUTPUTS_PATH / f"training_{job_id}.log"

            # Open log file for writing
            log_handle = open(log_file, "w")

            # Use asyncio.create_subprocess_exec for non-blocking execution
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=AI_TOOLKIT_PATH,
                stdout=log_handle,
                stderr=asyncio.subprocess.STDOUT,
            )

            self.training_processes[job_id] = process
            self.training_jobs[job_id] = {
                "status": "running",
                "config": config_name,
                "log_file": str(log_file),
                "pid": process.pid,
                "log_handle": log_handle,  # Store handle for cleanup
            }

            self.logger.info(f"Started training job {job_id} with config {config_name}")
            return {"status": "success", "job_id": job_id, "pid": process.pid}

        except FileNotFoundError as e:
            self.logger.error(f"Training script not found: {e}")
            return {"error": f"Training script not found: {str(e)}"}
        except PermissionError as e:
            self.logger.error(f"Permission denied to start training: {e}")
            return {"error": f"Permission denied: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Failed to start training: {e}")
            return {"error": f"Failed to start training: {str(e)}"}

    async def stop_training(self, **kwargs) -> Dict[str, Any]:
        """Stop a running training job"""
        job_id = kwargs.get("job_id")

        if job_id in self.training_processes:
            process = self.training_processes[job_id]
            if process.returncode is None:  # Still running
                process.terminate()
                try:
                    # Wait for process to terminate with timeout
                    await asyncio.wait_for(process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    # Force kill if termination timeout
                    process.kill()
                    await process.wait()

                # Close log file handle if exists
                job_info = self.training_jobs.get(job_id, {})
                if "log_handle" in job_info:
                    job_info["log_handle"].close()

                self.training_jobs[job_id]["status"] = "stopped"
                del self.training_processes[job_id]

                return {"status": "success", "job_id": job_id}

        return {"error": "Job not found or already stopped"}

    async def get_training_status(self, **kwargs) -> Dict[str, Any]:
        """Get training job status"""
        job_id = kwargs.get("job_id")

        if job_id in self.training_jobs:
            job = self.training_jobs[job_id]

            # Check if process is still running
            if job_id in self.training_processes:
                process = self.training_processes[job_id]
                if process.returncode is None:
                    job["status"] = "running"
                else:
                    job["status"] = "completed"
                    job["exit_code"] = process.returncode
                    # Close log file handle if exists
                    if "log_handle" in job:
                        job["log_handle"].close()
                    del self.training_processes[job_id]

            # Try to parse progress from log file
            progress = 0
            if "log_file" in job and Path(job["log_file"]).exists():
                try:
                    with open(job["log_file"], "r") as f:
                        lines = f.readlines()
                        for line in reversed(lines[-100:]):  # Check last 100 lines
                            if "step" in line.lower() and "/" in line:
                                # Try to extract step progress
                                import re

                                match = re.search(r"(\d+)/(\d+)", line)
                                if match:
                                    current, total = int(match.group(1)), int(match.group(2))
                                    progress = int((current / total) * 100)
                                    break
                except Exception:
                    pass

            return {
                "status": job.get("status", "unknown"),
                "job_id": job_id,
                "progress": progress,
                "config": job.get("config"),
            }

        return {"status": "error", "message": "Job not found"}

    async def list_training_jobs(self, **kwargs) -> Dict[str, Any]:
        """List all training jobs"""
        jobs = []
        for job_id, job_data in self.training_jobs.items():
            # Update status for running jobs
            if job_id in self.training_processes:
                process = self.training_processes[job_id]
                if process.returncode is not None:
                    job_data["status"] = "completed"
                    del self.training_processes[job_id]

            jobs.append(
                {
                    "job_id": job_id,
                    "status": job_data.get("status"),
                    "config": job_data.get("config"),
                }
            )
        return {"jobs": jobs}

    async def export_model(self, **kwargs) -> Dict[str, Any]:
        """Export a trained model"""
        model_name = kwargs.get("model_name")
        output_path = kwargs.get("output_path", f"{OUTPUTS_PATH}/{model_name}.safetensors")

        # Look for the model in outputs
        source_path = None
        for ext in [".safetensors", ".ckpt", ".pt"]:
            potential_path = OUTPUTS_PATH / f"{model_name}{ext}"
            if potential_path.exists():
                source_path = potential_path
                break

        if source_path:
            try:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, output_file)
                return {"status": "success", "path": str(output_file)}
            except Exception as e:
                return {"error": f"Failed to export model: {str(e)}"}

        return {"error": "Model not found"}

    async def list_exported_models(self, **kwargs) -> Dict[str, Any]:
        """List exported models"""
        models = []
        for model_file in OUTPUTS_PATH.glob("*.safetensors"):
            models.append(
                {
                    "name": model_file.stem,
                    "path": str(model_file),
                    "size": model_file.stat().st_size,
                }
            )
        for model_file in OUTPUTS_PATH.glob("*.ckpt"):
            models.append(
                {
                    "name": model_file.stem,
                    "path": str(model_file),
                    "size": model_file.stat().st_size,
                }
            )
        return {"models": models}

    async def download_model(self, **kwargs) -> Dict[str, Any]:
        """Download a model"""
        model_name = kwargs.get("model_name")
        encoding = kwargs.get("encoding", "base64")

        model_path = None
        for ext in [".safetensors", ".ckpt", ".pt"]:
            potential_path = OUTPUTS_PATH / f"{model_name}{ext}"
            if potential_path.exists():
                model_path = potential_path
                break

        if model_path:
            try:
                with open(model_path, "rb") as f:
                    data = f.read()

                if encoding == "base64":
                    return {
                        "status": "success",
                        "model": model_name,
                        "data": base64.b64encode(data).decode("utf-8"),
                        "size": len(data),
                    }
                else:
                    return {
                        "status": "success",
                        "model": model_name,
                        "data": data,
                        "size": len(data),
                    }
            except Exception as e:
                return {"error": f"Failed to read model: {str(e)}"}

        return {"error": "Model not found"}

    async def get_system_stats(self, **kwargs) -> Dict[str, Any]:
        """Get system statistics"""
        import psutil

        # Check GPU status if available
        gpu_info = {}
        try:
            import torch

            if torch.cuda.is_available():
                gpu_info = {
                    "cuda_available": True,
                    "device_count": torch.cuda.device_count(),
                    "current_device": torch.cuda.current_device(),
                    "device_name": torch.cuda.get_device_name(0),
                    "memory_allocated": torch.cuda.memory_allocated() / 1024**3,  # GB
                    "memory_reserved": torch.cuda.memory_reserved() / 1024**3,  # GB
                }
        except Exception:
            gpu_info = {"cuda_available": False}

        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
            "gpu": gpu_info,
        }

    async def get_training_logs(self, **kwargs) -> Dict[str, Any]:
        """Get training logs"""
        job_id = kwargs.get("job_id")
        lines = kwargs.get("lines", 100)

        if job_id in self.training_jobs:
            job = self.training_jobs[job_id]
            log_file = job.get("log_file")

            if log_file and Path(log_file).exists():
                try:
                    with open(log_file, "r") as f:
                        all_lines = f.readlines()
                        return {
                            "job_id": job_id,
                            "logs": all_lines[-lines:],
                            "total_lines": len(all_lines),
                        }
                except Exception as e:
                    return {"error": f"Failed to read logs: {str(e)}"}

        return {"job_id": job_id, "logs": [], "lines": 0}

    async def get_training_info(self, **kwargs) -> Dict[str, Any]:
        """Get training information"""
        # Update job statuses
        for job_id in list(self.training_processes.keys()):
            process = self.training_processes[job_id]
            if process.returncode is not None:
                self.training_jobs[job_id]["status"] = "completed"
                del self.training_processes[job_id]

        return {
            "total_jobs": len(self.training_jobs),
            "active_jobs": len(self.training_processes),
            "configs": len(list(CONFIGS_PATH.glob("*.yaml"))),
            "datasets": len(list(d for d in DATASETS_PATH.iterdir() if d.is_dir())),
            "models": len(list(OUTPUTS_PATH.glob("*.safetensors")) + list(OUTPUTS_PATH.glob("*.ckpt"))),
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Toolkit MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http"], default="http", help="Server mode")
    parser.add_argument("--port", type=int, default=8012, help="Port for HTTP mode")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for HTTP mode")

    args = parser.parse_args()

    server = AIToolkitMCPServer(port=args.port)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
