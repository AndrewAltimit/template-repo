# AI Toolkit MCP Server (Rust)

> MCP server for LoRA training with [ostris/ai-toolkit](https://github.com/ostris/ai-toolkit): configs, datasets, training jobs, trained weights and GPU stats.

The server runs **on the GPU machine next to AI Toolkit** (in this repo: the
`mcp-ai-toolkit` compose service on `192.168.0.222:8020`, built from
`docker/ai-toolkit.Dockerfile`). Clients reach it over HTTP. It launches
`python3 run.py <config>` inside the AI Toolkit checkout and manages files under
`AI_TOOLKIT_PATH`.

## Quick Start

```bash
cargo build --release

# HTTP (MCP JSON-RPC at /messages); default port 8020
AI_TOOLKIT_PATH=/ai-toolkit ./target/release/mcp-ai-toolkit --mode standalone --port 8020

# STDIO, for an MCP client running on the GPU host itself
./target/release/mcp-ai-toolkit --mode stdio

# Local proxy: expose the remote GPU server's tools on this machine
./target/release/mcp-ai-toolkit --mode client --port 8020 --backend-url http://192.168.0.222:8020

curl http://localhost:8020/health
```

## Typical Workflow

1. `list_model_presets` - pick a base model (`flux-dev`, `sdxl`, ...).
2. `upload_dataset` - images + captions into `datasets/<name>/`.
3. `get_dataset_info` - check caption coverage.
4. `create_training_config` with `dataset_path: "<dataset name>"` and `preset`.
5. `validate_config`, then `start_training` -> `job_id`.
6. Poll `get_training_status` (step, %, loss, ETA); look at `get_training_samples`.
7. `list_exported_models` -> `export_model` / `download_model`.

## Tools (22)

All tools use typed argument parsing: a missing or mistyped argument returns a
JSON-RPC `Invalid params` error; operational failures (not found, validation
failure, ...) return a tool result with `isError: true` and a readable message.

### Configs

| Tool | Parameters | Notes |
|------|------------|-------|
| `create_training_config` | **`name`**, **`dataset_path`**, `preset`, `model_name`, `resolution` (int or int[]), `steps`, `batch_size`, `rank`, `alpha`, `lr`, `optimizer`, `noise_scheduler`, `trigger_word`, `prompts`, `is_flux`, `is_xl`, `is_v3`, `quantize`, `gradient_checkpointing`, `cache_latents`, `caption_dropout_rate`, `save_every`, `sample_every`, `disable_sampling`, `low_vram`, `overwrite` (default true) | Writes `<configs>/<name>.yaml`. Architecture is auto-detected from `model_name` (Flux > SD3 > SDXL) unless flags are given; defaults follow the architecture (flowmatch/adamw8bit/bf16/quantize for Flux and SD3). `dataset_path` accepts a dataset name, an absolute path, or a path relative to `AI_TOOLKIT_PATH`. Weights go to `<outputs>/<name>/`. Returns warnings (e.g. missing dataset folder). |
| `list_configs` | - | |
| `get_config` | **`name`** | YAML returned as JSON. |
| `validate_config` | **`name`** | `{valid, errors, warnings}`: structure, conflicting arch flags, steps/lr/rank sanity, dataset folders exist and contain images, caption coverage. |
| `delete_config` | **`name`** | |

### Datasets

| Tool | Parameters | Notes |
|------|------------|-------|
| `upload_dataset` | **`dataset_name`**, **`images`**: `[{filename, data, caption?}]`, `overwrite` (default true) | PNG/JPEG/WebP only (checked by magic bytes), 50 MB per image, `data:` URL prefix accepted. Caption saved as `<stem>.txt`. Appends to an existing dataset. Returns `saved` and per-image `failed`; `status` is `success` or `partial`, and the call errors only if nothing was saved. |
| `list_datasets` | - | Image / caption counts and size per dataset. |
| `get_dataset_info` | **`name`**, `max_missing` (default 50) | Includes `missing_captions` (array). |
| `delete_dataset` | **`name`** | Recursive delete. |

### Training

| Tool | Parameters | Notes |
|------|------------|-------|
| `start_training` | **`config_name`**, `allow_concurrent` (false), `skip_validation` (false) | Validates first; refuses while another job is running (single GPU) unless `allow_concurrent`. stdout+stderr go to `<outputs>/training_<job_id>.log`. |
| `get_training_status` | **`job_id`** | `status`, `progress` (0-100), `current_step`, `total_steps`, `loss`, `lr`, `eta` parsed from the tqdm bar; `error_hint` (e.g. CUDA OOM line) for failed jobs. |
| `get_training_logs` | **`job_id`**, `lines` (100, max 5000) | Reads only the last 4 MB; progress-bar redraws are collapsed. |
| `stop_training` | **`job_id`**, `grace_seconds` (15, max 300), `force` | SIGTERM to the job's process group (includes dataloader workers), SIGKILL after the grace period. |
| `list_training_jobs` | `status` filter | Newest first. |
| `get_training_info` | - | Job counts by status, config/dataset/model counts, resolved paths, whether `run.py` was found. |
| `get_training_samples` | `job_id` or `name`, `limit` (4, max 16), `include_images` (true) | Newest sample images from `<output>/<run>/samples/` as MCP image content plus metadata (file, step). |

Job status is one of `pending`, `running`, `completed`, `failed`, `stopped`,
`unknown`. A background task per job reaps the process and records the exit
code, so status is accurate without polling. The registry is persisted to
`<outputs>/.mcp_training_jobs.json`; jobs that were running when the server
restarted come back as `unknown` (their process is no longer supervised; check
the log and `nvidia-smi`).

### Models

Model names are paths relative to the outputs directory without extension, as
returned by `list_exported_models`: `my_lora/my_lora` (final weights),
`my_lora/my_lora_000000500` (checkpoint), `exports/my_lora`. A bare run name
(`my_lora`) resolves to that run's final weights.

| Tool | Parameters | Notes |
|------|------------|-------|
| `list_exported_models` | - | `.safetensors`/`.ckpt`/`.pt` up to 3 levels deep (skips `samples/`, `optimizer.pt`). |
| `export_model` | **`model_name`**, `output_path`, `overwrite` (false) | Copies to `<outputs>/exports/<file>` or to `output_path` (relative to outputs; extension appended if missing). Refuses to copy a file onto itself. |
| `download_model` | **`model_name`**, `encoding` (`base64`\|`raw`), `offset`, `chunk_size` (8 MB default, 32 MB max) | Without `offset`/`chunk_size`: whole file, max 100 MB, with `sha256`. Chunked: repeat with `next_offset` until `complete`; the final chunk carries the file `sha256`. `raw`: metadata only (size, path, sha256). |
| `delete_model` | **`name`** | Deletes the single resolved file. |

### Utilities

| Tool | Parameters | Notes |
|------|------------|-------|
| `get_system_stats` | - | CPU (sampled), memory, the disk holding `AI_TOOLKIT_PATH`, and per-GPU memory/utilization/temperature via `nvidia-smi` (5 s timeout). |
| `list_model_presets` | - | `flux-dev`, `flux-schnell`, `sd15`, `sdxl`, `sd35-large` with recommended settings. |

## Configuration

### CLI

```
--mode <MODE>         standalone (alias: http) | server | client | stdio  [default: standalone]
--port <PORT>         Listen port                                       [default: 8020]
--host <HOST>         Accepted for compatibility; always binds 0.0.0.0
--backend-url <URL>   Backend for client mode (e.g. http://192.168.0.222:8020)
--log-level <LEVEL>   Log level (RUST_LOG overrides)                     [default: info]
```

### Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `AI_TOOLKIT_PATH` | `/ai-toolkit` | AI Toolkit checkout (must contain `run.py`); training cwd |
| `AI_TOOLKIT_CONFIGS_PATH` | `$AI_TOOLKIT_PATH/config` | Config YAML directory |
| `AI_TOOLKIT_DATASETS_PATH` | `$AI_TOOLKIT_PATH/datasets` | Dataset directory |
| `AI_TOOLKIT_OUTPUTS_PATH` | `$AI_TOOLKIT_PATH/outputs` | Weights, samples, logs, exports, job registry |
| `AI_TOOLKIT_PYTHON` | `python3` | Interpreter used to run `run.py` |
| `HF_TOKEN` | - | Inherited by training; required for gated models (Flux.1-dev, SD 3.5) |

### Layout

```
$AI_TOOLKIT_PATH/
  run.py
  config/<name>.yaml
  datasets/<dataset>/{image.png, image.txt, ...}
  outputs/
    <run>/<run>.safetensors, <run>_000000250.safetensors, samples/
    exports/
    training_<job_id>.log
    .mcp_training_jobs.json
```

## Transport Modes

| Mode | Description |
|------|-------------|
| `standalone` / `http` | MCP JSON-RPC (`/messages`) + REST (`/mcp/tools`, `/mcp/execute`) + `/health` |
| `stdio` | JSON-RPC over stdin/stdout; logs go to stderr |
| `server` | REST endpoints only |
| `client` | Proxies tools from `--backend-url` (no local filesystem access) |

MCP client configuration for the remote GPU server:

```json
{
  "mcpServers": {
    "ai-toolkit": {
      "type": "http",
      "url": "http://192.168.0.222:8020/messages"
    }
  }
}
```

REST example:

```bash
curl -X POST http://192.168.0.222:8020/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "create_training_config",
       "arguments": {"name": "cat_lora", "dataset_path": "cats", "preset": "flux-dev",
                     "trigger_word": "ohwx", "steps": 1500}}'
```

## Security

- Config, dataset and run names are restricted to `[A-Za-z0-9._-]` (no leading `.`).
- Relative paths (model names, export destinations) reject absolute paths and
  `.`/`..` components, and are canonicalized to stay inside their base directory
  (symlink escapes are rejected).
- Upload file names must be plain names with an image extension, and content is
  checked by magic bytes.
- Training is launched without a shell (`python3 run.py <config path>`); no user
  input is interpolated into a command line.
- The HTTP transport has **no authentication**. Anyone who can reach port 8020
  can upload, delete and start GPU jobs; keep it on a trusted network.

## Development

```bash
cd tools/mcp/mcp_ai_toolkit
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test          # offline; no GPU, Python or AI Toolkit needed
cargo build --release
```

Tests use temporary directories. The job-manager tests spawn `sh`/`cmd` in
place of Python, and a Unix-only end-to-end test runs a fake `run.py` that
prints a tqdm progress line to cover start, progress parsing, logs, the
single-GPU guard and graceful stop.

Source layout:

| File | Responsibility |
|------|----------------|
| `src/main.rs` | CLI and server bootstrap |
| `src/server.rs` | Tool definitions (typed args -> handlers) |
| `src/config.rs` | Paths from env, name/path validation |
| `src/training_config.rs` | Config building, arch detection, static validation |
| `src/datasets.rs` | Dataset scanning, upload decoding/validation |
| `src/jobs.rs` | Job spawn, monitoring, stop, persistence |
| `src/logs.rs` | Log tailing, tqdm progress and error parsing |
| `src/models.rs` | Weight discovery, export, chunked reads, sha256 |
| `src/system.rs` | Host stats and `nvidia-smi` parsing |
| `src/types.rs` | AI Toolkit YAML schema and model presets |

## Limitations

- One process per job, no queue: a second job is refused (or runs concurrently
  on the same GPU with `allow_concurrent`).
- A job interrupted by a server restart is not re-attached; it is reported as
  `unknown` and cannot be stopped through the server.
- Progress parsing depends on AI Toolkit's tqdm output format.
- Only the first `process` entry of a config is used for the output folder and
  step count.
- Graceful process-group stop is Unix-only; on other platforms the job process
  is killed directly.
