# ComfyUI MCP Server (Rust)

> MCP server that drives a ComfyUI instance: text-to-image (FLUX / SDXL),
> image-to-image, upscaling, ControlNet, arbitrary API-format workflows, job
> tracking/cancellation, image upload/download and LoRA file management.

## Deployment model

ComfyUI runs on a dedicated GPU machine (`192.168.0.222`). The supported
deployment builds this binary into the ComfyUI image
(`docker/comfyui.Dockerfile`, or `docker/comfyui-arm64.Dockerfile`), where
`docker/entrypoints/comfyui-entrypoint.sh` starts ComfyUI on `:8188` and then
`mcp-comfyui --mode standalone --port 8013` next to it. MCP clients connect to
`http://192.168.0.222:8013/messages`.

Because the server is co-located with ComfyUI, `COMFYUI_HOST` defaults to
`localhost`, and the LoRA tools read and write the local
`$COMFYUI_PATH/models/loras` directory directly. **Do not repoint the remote
addresses in `.mcp.json` at localhost.**

## Quick start

```bash
cd tools/mcp/mcp_comfyui
cargo build --release

# HTTP (as in the container)
./target/release/mcp-comfyui --mode standalone --port 8013
curl http://localhost:8013/health
curl http://localhost:8013/mcp/tools

# STDIO, talking to a remote ComfyUI (LoRA file tools then act on the
# local COMFYUI_PATH, not the remote machine)
COMFYUI_URL=http://192.168.0.222:8188 ./target/release/mcp-comfyui --mode stdio

# Call a tool over the simple REST API
curl -X POST http://localhost:8013/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "generate_image", "arguments": {"prompt": "a lighthouse at dusk"}}'
```

CLI flags (from mcp-core): `--mode standalone|server|client|stdio`
(default `standalone`), `--port` (default 8000; the container uses 8013),
`--log-level` (default `info`), `--backend-url` (client mode).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_URL` | unset | Full ComfyUI base URL (e.g. `http://192.168.0.222:8188`). Takes precedence over host/port. |
| `COMFYUI_HOST` | `localhost` | ComfyUI host (used when `COMFYUI_URL` is unset) |
| `COMFYUI_PORT` | `8188` | ComfyUI port |
| `COMFYUI_PATH` | `/comfyui` | ComfyUI root; LoRAs live in `<path>/models/loras` |
| `COMFYUI_GENERATION_TIMEOUT` | `300` | Default seconds to wait for a job (clamped to 1..7200) |
| `COMFYUI_REQUEST_TIMEOUT` | `60` | Per-HTTP-request timeout in seconds (connect timeout is 10s) |
| `COMFYUI_MAX_IMAGE_BYTES` | `20971520` | Largest image returned inline (`get_image`, `include_images`) |
| `COMFYUI_MAX_LORA_DOWNLOAD_BYTES` | `536870912` | Largest LoRA returned by `download_lora` |

Invalid values are logged and replaced by the default.

## Tools

Bad arguments (missing/mistyped parameters, out-of-range values, unsafe file
names) fail with a JSON-RPC `InvalidParameters` error. Failures on the ComfyUI
side (unreachable, rejected workflow, execution error, timeout) return a
result with `isError: true` and a JSON body `{"success": false, "error": ...}`.

| Tool | Purpose | Parameters (required in bold) |
|------|---------|-------------------------------|
| `generate_image` | Run a template or custom workflow, wait, return outputs | **`prompt`**, `negative_prompt`, `workflow`, `model_family`, `width`, `height`, `seed`, `steps`, `cfg_scale`, `guidance`, `sampler_name`, `scheduler`, `checkpoint`, `lora_name`, `lora_strength`, `batch_size`, `denoise`, `input_image`, `input_image_data`, `upscale_model`, `controlnet_name`, `control_strength`, `filename_prefix`, `timeout`, `wait` (true), `include_images` (false) |
| `execute_workflow` | Queue an API-format workflow as-is | **`workflow`**, `wait` (false), `timeout`, `include_images` |
| `get_job_status` | Status + outputs of a job, optionally waiting | `job_id` or `prompt_id`, `wait`, `timeout`, `include_images` |
| `cancel_job` | Dequeue a pending job or interrupt a running one | `job_id` or `prompt_id` |
| `get_queue` | Running and pending prompt ids | none |
| `get_image` | Fetch an output/input/temp image as MCP image content | **`filename`**, `subfolder`, `type` (`output`) |
| `upload_image` | Put a base64 image into ComfyUI's input dir | **`filename`**, **`data`**, `subfolder`, `overwrite` (false) |
| `list_workflows` | Built-in templates and what they need | none |
| `get_workflow` | A template as API-format JSON with sample values | **`name`** |
| `list_models` | Model files ComfyUI can load | `type`/`model_type`: `checkpoint` (default), `lora`, `vae`, `upscale_model`, `controlnet`, `unet`, `clip` |
| `get_object_info` | Node introspection | `node_class`, `full` (false: returns a summary) |
| `get_system_info` | ComfyUI versions, RAM, GPUs/VRAM, configured URL | none |
| `upload_lora` | Write a base64 LoRA (+ metadata JSON) atomically | **`filename`**, **`data`**, `metadata`, `overwrite` (true) |
| `list_loras` | LoRA files on disk with sizes | none |
| `download_lora` | Read a LoRA as base64 (size-capped) | **`filename`**, `encoding` (`base64`) |

### Job model

`job_id` equals ComfyUI's `prompt_id`, so status comes straight from
ComfyUI's `/history` and `/queue`. A job can be checked after the MCP server
restarts, and jobs queued from the ComfyUI web UI can be checked too. Statuses:
`queued` (with `queue_position`), `running`, `completed`, `failed` (with the
node and exception), `interrupted`, `timeout` (the wait ran out but the job
keeps running), and `unknown` (not in the queue or history).

A generation that runs past `timeout` is **not** cancelled. The result says so
and includes the `job_id` to poll or cancel.

### Templates (`generate_image.workflow`)

| Template | Needs | Notes |
|----------|-------|-------|
| `flux_default` (`flux`) | - | `flux1-dev-fp8.safetensors`, cfg 1.0 + `FluxGuidance` (`guidance` 3.5), heunpp2/simple, 20 steps. The default. |
| `sdxl_default` (`sdxl`) | - | `illustriousXL_smoothftSOLID.safetensors`, cfg 7, dpmpp_2m/karras, 30 steps. Used when `model_family=sdxl` or the checkpoint name looks like SDXL. |
| `flux_with_lora` | `lora_name` | FLUX with `LoraLoader` on model + CLIP |
| `img2img` | input image | `denoise` (default 0.75); `width`+`height` resize the source first. The default whenever an input image is given. |
| `upscale` | input image | `upscale_model` (default `4x-UltraSharp.pth`) |
| `controlnet` | input image, `controlnet_name` | `ControlNetApplyAdvanced`, `control_strength` (default 1.0). The ControlNet must match the checkpoint family. |

The input image is either `input_image` (a name in ComfyUI's input directory,
`name.png` or `subfolder/name.png`, e.g. returned by `upload_image`) or
`input_image_data` (base64; uploaded automatically under a unique name).
`checkpoint`, `sampler_name`, `scheduler`, `steps`, `cfg_scale`, `seed`,
`batch_size` and `filename_prefix` override the template defaults. The seed
actually used is always returned.

`workflow` can also be a full **API-format** workflow object (in ComfyUI, use
"Save (API Format)"; UI-format exports are detected and rejected). The prompt
is injected by following each sampler's `positive`/`negative` links back to
their `CLIPTextEncode*` nodes, passing through `FluxGuidance`/ControlNet nodes.
If a graph has no sampler links, a heuristic picks the nodes instead. The
negative text is only replaced when `negative_prompt` is given. The result's
`prompt_injection` field lists the nodes that were changed. Template
parameters such as `width` are ignored for custom workflows, and a warning
says so.

### Examples

```json
{"tool": "generate_image", "arguments": {
  "prompt": "a cyberpunk alley in the rain, neon signs", "width": 1024, "height": 768,
  "seed": 1234, "include_images": true}}
```

```json
{"tool": "generate_image", "arguments": {
  "prompt": "pixel art birthday cake, zz_trigger", "workflow": "flux_with_lora",
  "lora_name": "pixel_birthday.safetensors", "lora_strength": 0.9}}
```

```json
{"tool": "generate_image", "arguments": {
  "prompt": "same scene in winter", "input_image_data": "data:image/png;base64,iVBOR...",
  "denoise": 0.55, "model_family": "sdxl"}}
```

```json
{"tool": "execute_workflow", "arguments": {"workflow": {"...": "API format"}}}
{"tool": "get_job_status", "arguments": {"job_id": "<id>", "wait": true, "include_images": true}}
```

Typical successful `generate_image` result:

```json
{
  "success": true, "job_id": "3f0c...", "prompt_id": "3f0c...", "status": "completed",
  "template": "flux_default", "model_family": "flux", "seed": 1234,
  "images": [{"filename": "ComfyUI_00042_.png", "subfolder": "", "type": "output"}]
}
```

With `include_images: true`, up to 8 images follow as MCP image content blocks.

## Security and robustness

- LoRA and image file names must be bare names with an allowed extension:
  `.safetensors/.ckpt/.pt` for LoRAs, `.png/.jpg/.jpeg/.webp/.gif/.bmp` for
  images. Separators, `..`, drive prefixes, hidden names and control
  characters are rejected, not silently stripped. Subfolders and
  `filename_prefix` must be relative and free of `..`.
- Prompt/job ids are restricted to `[A-Za-z0-9_-]` before they are put into
  URL paths.
- LoRA uploads are written to a temp file and renamed, so ComfyUI never loads
  a partial file. Uploaded images are checked by magic bytes.
- Every HTTP call has a connect timeout (10s) and a request timeout. Waits
  poll every second, tolerate up to 5 consecutive transient errors, and detect
  prompts that vanish from ComfyUI.
- Inline image and LoRA downloads are size-capped (see Configuration).

## Limitations

- The LoRA tools (`upload_lora`, `list_loras`, `download_lora`) act on the
  filesystem of the machine running this server. Use `list_models type=lora`
  to see what ComfyUI itself can load. Only the top level of `loras/` is
  listed.
- Progress is tracked by polling, not ComfyUI's websocket, so there is no
  per-step progress percentage.
- The template defaults assume the model files named above exist on the GPU
  host. Check with `list_models` and override `checkpoint` / `upscale_model` /
  `controlnet_name` as needed.
- `cancel_job` on a running job calls `/interrupt` with the `prompt_id`. Older
  ComfyUI builds ignore the id and interrupt whatever is running (the server
  only calls it when the target is the running job).

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline: ComfyUI is mocked with an in-process axum server
cargo build --release
```

Source layout:

```
src/
  main.rs        CLI entry point
  server.rs      tool definitions, argument structs, generation planning
  client.rs      ComfyUI HTTP client (prompt/history/queue/view/upload/...)
  workflows.rs   template builders, workflow validation, prompt injection
  types.rs       history/queue parsing, job states
  loras.rs       local LoRA directory management
  validate.rs    file name / subfolder / base64 / range validation
  config.rs      environment configuration
  mock_tests.rs  end-to-end tool tests against a mock ComfyUI
```

## License

Part of the template-repo project. See the repository LICENSE file.
