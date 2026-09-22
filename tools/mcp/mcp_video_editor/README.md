# Video Editor MCP Server (Rust)

> Automated video editing over MCP: media probing, loudness/silence analysis,
> Whisper transcription, scene detection, multi-camera speaker switching,
> edit decision lists (EDLs), ffmpeg rendering with transitions/zoom/PiP,
> clip extraction and captions.

All media work is done by `ffmpeg`/`ffprobe` subprocesses (spawned directly,
never through a shell, with a timeout). Transcription uses the `whisper` CLI
when it is installed. Everything else (loudness analysis, silence and peak
detection, speaker detection, EDL generation, caption layout) is pure Rust.

## Quick Start

```bash
cd tools/mcp/mcp_video_editor
cargo build --release

# STDIO mode (Claude Code / MCP clients)
./target/release/mcp-video-editor --mode stdio

# Standalone HTTP mode
./target/release/mcp-video-editor --mode standalone --port 8019
curl http://localhost:8019/health
curl http://localhost:8019/mcp/tools
```

Docker (compose service `mcp-video-editor`, profiles `services`/`gpu`):

```bash
docker compose --profile services up -d mcp-video-editor
# with the Whisper CLI baked in (large image, pulls PyTorch):
docker compose build --build-arg INSTALL_WHISPER=true mcp-video-editor
```

In the container, input videos must be visible inside it (the repo is mounted
read-only at `/app`) and outputs go to `/output` (host `./outputs/video-editor`).

## Tools

| Tool | Purpose | Required params |
|------|---------|-----------------|
| `video_editor/analyze` | Media info, transcript, loudness/silences/peaks, scenes, speakers, highlights, suggestions | `video_inputs` |
| `video_editor/create_edit` | Generate (and save) an EDL without rendering | `video_inputs` |
| `video_editor/render` | Render an EDL (given or auto-generated) | `video_inputs` |
| `video_editor/extract_clips` | Cut clips by time range and/or transcript keyword | `video_input` |
| `video_editor/add_captions` | Transcribe and burn in (or mux) captions | `video_input` |
| `video_editor/get_video_info` | ffprobe summary (duration, size, fps, codecs, audio) | `video_input` |
| `video_editor/get_job_status` | Status/progress/result of a job | `job_id` |
| `video_editor/list_jobs` | Recent jobs, optional `status` filter | - |
| `video_editor/cancel_job` | Cancel a job (kills ffmpeg/whisper, removes temp files) | `job_id` |

### Jobs and `background`

Every heavy tool (`analyze`, `create_edit`, `render`, `extract_clips`,
`add_captions`) runs as a job and accepts `background` (default `false`).

* `background: false` - the call waits and returns the result (with `job_id`).
* `background: true` - the call returns `{"job_id": ...}` immediately; poll
  `get_job_status` (progress 0-100 plus a `stage` string) and read `result`
  when `status` is `completed`. `cancel_job` stops it.

At most `MAX_PARALLEL_JOBS` jobs execute at once; others wait as `pending`.
Jobs live in memory only (lost on restart); the oldest finished jobs are
pruned beyond `MAX_RETAINED_JOBS`.

### Errors

* Malformed arguments (missing required field, wrong type, unknown enum
  value) fail the call with an `InvalidParameters` error naming the field.
  Nested options are **not** silently replaced by defaults.
* Operational failures (file not found, invalid settings, ffmpeg errors,
  Whisper missing) return an `isError` result whose text is
  `{"error": "...", "job_id": "..."}`. ffmpeg errors include the tail of its
  stderr.
* Non-fatal issues (e.g. transcription unavailable during `analyze`) are
  reported in `warnings` arrays and the rest of the work continues.

### `video_editor/analyze`

```json
{
  "video_inputs": ["/data/host.mp4", "/data/guest.mp4"],
  "analysis_options": {
    "transcribe": true,
    "identify_speakers": true,
    "detect_scenes": true,
    "extract_highlights": true,
    "scene_threshold": 0.3,
    "language": "en"
  }
}
```

Per video (`analysis[path]`): `video_info`, `transcript` (Whisper segments with
word timestamps), `audio_analysis` (`duration`, `silence_segments`,
`volume_profile` capped at 600 points, `peak_moments`, `mean_db`, `max_db`),
`scene_changes`, `speakers`, `segments_with_speakers`, `highlights`
(audio peaks and emphasis phrases such as "important"/"key point"),
`suggested_edits`, `warnings`. With two or more inputs and
`identify_speakers`, a top-level `speaker_activity` lists speaker turns.

**Speaker identification is energy-based**: with one time-synced video per
speaker (each with its own microphone), the loudest input in each 100 ms
window (by at least 3 dB, above the silence floor) is the active speaker;
turns shorter than `speaker_switch_delay` are merged. Speaker IDs are
`SPEAKER_00`, `SPEAKER_01`, ... in input order. Single-file diarization is
not available (no ML diarization backend), and a warning says so.

### `video_editor/create_edit`

```json
{
  "video_inputs": ["/data/host.mp4", "/data/guest.mp4"],
  "editing_rules": {
    "switch_on_speaker": true,
    "speaker_switch_delay": 0.5,
    "remove_silence": true,
    "silence_threshold": 2.0,
    "zoom_on_emphasis": true,
    "picture_in_picture": "never",
    "pip_size": 0.25,
    "transition_type": "cross_dissolve",
    "transition_duration": 0.5
  },
  "speaker_mapping": {"SPEAKER_01": "/data/guest_closeup.mp4"}
}
```

Inputs are treated as angles of one recording sharing a timeline. Shots come
from (in order of preference) speaker turns, scene changes of the first
input, 10 s rotation between inputs, or the whole video. Then silences
longer than `silence_threshold` are cut (0.25 s of silence kept at each
edge), highlight windows get the `zoom_in` effect, source changes get
`transition_type`, and `picture_in_picture: "always"` overlays another input
in the corner (`auto` currently behaves like `never`).

Response: `edit_decision_list`, `estimated_duration`, `edl_file` (saved under
`<output>/edl/`), `strategy` (`speaker`/`scene`/`interval`/`full`),
`silence_removed`, resolved `editing_rules`, `warnings`.

EDL entry format (also accepted by `render`):

```json
{"timestamp": 12.5, "duration": 4.0, "source": "/data/guest.mp4",
 "action": "transition", "transition_type": "cross_dissolve", "transition_duration": 0.5,
 "effects": ["zoom_in"], "pip_source": "/data/host.mp4", "pip_size": 0.25}
```

`timestamp` is the in-point in `source`. Supported transitions: `cut`,
`cross_dissolve`/`fade`, `dissolve`, `fadeblack`, `fadewhite`, `wipeleft`,
`wiperight`, `wipeup`, `wipedown`, `slideleft`, `slideright`, `circleopen`,
`circleclose`. Supported effects: `zoom_in`.

### `video_editor/render`

```json
{
  "video_inputs": ["/data/host.mp4"],
  "edit_decision_list": [ ... ],
  "output_settings": {"format": "mp4", "resolution": "1920x1080", "fps": 30,
                      "bitrate": "8M", "codec": "libx264", "output_path": "episode1.mp4"},
  "render_options": {"hardware_acceleration": true, "preview_mode": false,
                     "add_captions": false},
  "background": true
}
```

Without `edit_decision_list` an EDL is generated first (same logic and
optional `editing_rules`/`speaker_mapping` as `create_edit`). Each decision
is encoded to the target size (aspect preserved, letterboxed), fps and
48 kHz stereo audio (silence is synthesised for sources without audio);
zoom and PiP are applied per segment. Segments are then joined losslessly
(concat, no re-encode) or, if any transitions are present, with an
`xfade`/`acrossfade` chain (transitions are clamped to 45% of the adjacent
shots; EDLs over 64 segments fall back to hard cuts with a warning).
Decisions running past the end of their source are shortened (warning).

* `format`: `mp4`, `mov`, `mkv`, `webm` (an `output_path` extension wins).
* `codec` (optional): `libx264`, `libx265`, `h264_nvenc`, `hevc_nvenc`,
  `libvpx-vp9`. Default: VP9 for webm, else NVENC if `hardware_acceleration`
  and `ENABLE_GPU` are on and a test encode succeeds, else libx264.
* `resolution` must use even dimensions; `bitrate` like `8M`/`2500k`.
* `preview_mode`: 640x360, 15 fps, 2M, fast presets.
* `add_captions`: transcribes the rendered result and burns in captions
  (default style); the SRT is written next to the output. Needs Whisper.
* `add_speaker_labels`: not implemented; ignored with a warning.

Response: `output_path`, `duration`, `resolution`, `fps`, `codec`,
`file_size`, `segments`, `transitions_rendered`, `edl_generated`, `warnings`,
`job_id`.

### `video_editor/extract_clips`

```json
{
  "video_input": "/data/talk.mp4",
  "extraction_criteria": {
    "time_ranges": [[30, 45], [120.5, 130]],
    "keywords": ["pricing", "roadmap"],
    "min_clip_length": 3.0, "max_clip_length": 60.0, "padding": 0.5
  },
  "output_dir": "talk_clips",
  "stream_copy": false,
  "max_clips": 50
}
```

Ranges are padded, extended (centred) to `min_clip_length`, clamped to the
video and truncated to `max_clip_length`. Keyword matching is a
case-insensitive substring search over Whisper segments; overlapping matches
are merged. Clips are re-encoded for frame-accurate cuts unless
`stream_copy: true` (fast, cuts snap to keyframes). `speakers` is accepted
but not supported (warning). Failed clips are listed in `failed_clips`.

### `video_editor/add_captions`

```json
{
  "video_input": "/data/talk.mp4",
  "caption_style": {"font": "Arial", "size": 42, "color": "#FFFFFF",
                    "background": "#00000099", "position": "bottom",
                    "max_chars_per_line": 40},
  "languages": ["en"],
  "output_path": "talk_captioned.mp4",
  "burn_in": true
}
```

* `size` is in output-video pixels; `color`/`background` are `#RRGGBB` or
  `#RRGGBBAA` (`background: "none"` draws an outline instead of a box);
  `position` is `bottom`, `middle` or `top`.
* Text is wrapped at `max_chars_per_line`, at most two lines per caption;
  longer segments are split into consecutive captions.
* `burn_in: false` muxes a selectable subtitle track (`mov_text` for
  mp4/mov, `srt` for mkv, `webvtt` for webm) without re-encoding.
* Multiple languages produce `<name>_<lang>.<ext>` outputs.
* `display_speaker_names` only applies when speaker labels exist, which is
  never the case for a single file.

## Configuration

### CLI

```
--mode <MODE>         standalone | stdio | server | client [default: standalone]
--port <PORT>         HTTP port [default: 8000; the container uses 8019]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_VIDEO_OUTPUT_DIR` | `./outputs/video-editor` | Root for all outputs (`renders/`, `clips/`, `edl/`) |
| `MCP_VIDEO_ALLOWED_OUTPUT_DIRS` | (none) | Extra directories outputs may be written to (OS path-list separator) |
| `MCP_VIDEO_CACHE_DIR` | OS cache dir `/mcp-video-editor` | Transcript cache |
| `MCP_VIDEO_TEMP_DIR` | OS temp dir `/video_editor` | Intermediate files (auto-removed) |
| `WHISPER_BIN` | `whisper` | Whisper CLI executable |
| `WHISPER_MODEL` | `medium` | Whisper model (tiny, base, small, medium, large, ...) |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` (passed as `--device`) |
| `ENABLE_GPU` | `true` | Allow NVENC encoding when it works |
| `MAX_PARALLEL_JOBS` | `2` | Concurrent heavy jobs |
| `MAX_RETAINED_JOBS` | `200` | Finished jobs kept for status queries |
| `TRANSITION_DURATION` | `0.5` | Default transition length (s) |
| `SPEAKER_SWITCH_DELAY` | `0.5` | Default minimum speaker turn (s) |
| `SILENCE_THRESHOLD` | `2.0` | Default minimum silence to cut (s) |
| `SILENCE_DB` | `-40` | Loudness (dBFS) below which audio counts as silence |
| `ZOOM_FACTOR` | `1.3` | Punch-in factor for `zoom_in` |
| `PIP_SIZE` | `0.25` | Default PiP width fraction |
| `VIDEO_EDITOR_SUBPROCESS_TIMEOUT_SECS` | `1800` | Per-subprocess timeout (ffmpeg/ffprobe/whisper) |

### Output path policy

Every file the server writes must resolve under `MCP_VIDEO_OUTPUT_DIR` or a
directory listed in `MCP_VIDEO_ALLOWED_OUTPUT_DIRS`. Relative `output_path` /
`output_dir` values resolve under the output directory; `..` components are
rejected; symlinks are resolved before the check; an output may not overwrite
one of the inputs. This keeps a (possibly prompt-injected) tool call from
overwriting arbitrary files.

### Security notes

* Subprocesses are spawned without a shell; stdin is the null device.
* Media paths are passed as `file:<path>`, so inputs cannot be URLs,
  `concat:`/pipe pseudo-protocols or option-like strings.
* Values embedded in ffmpeg filtergraphs (subtitle paths, caption styles) are
  escaped at both filtergraph levels; caption fonts/colours/positions and
  encoder names are validated against allowlists.
* Every subprocess has a timeout and is killed when a job is cancelled.

## Requirements

* **ffmpeg / ffprobe** in `PATH` (with libass for burned-in captions and
  `xfade`, i.e. ffmpeg 4.3+). Fonts must be available to fontconfig.
* **whisper** (optional; `pip install openai-whisper`) for transcription,
  captions, keyword clips and keyword highlights. Transcripts are cached per
  source file (path, size, mtime), model and language.

## MCP configuration

```json
{
  "mcpServers": {
    "video-editor": {
      "command": "mcp-video-editor",
      "args": ["--mode", "stdio"],
      "env": {"MCP_VIDEO_OUTPUT_DIR": "/abs/path/outputs/video-editor"}
    }
  }
}
```

Docker variant:

```json
{
  "mcpServers": {
    "video-editor": {
      "command": "docker",
      "args": ["compose", "--profile", "services", "run", "--rm", "-T",
               "mcp-video-editor", "mcp-video-editor", "--mode", "stdio"]
    }
  }
}
```

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo build --release
```

Unit tests cover argument parsing, validation, the output path policy, WAV
parsing, silence/peak/speaker detection, EDL generation, transition planning,
filter escaping, SRT generation, jobs (cancel, panic, concurrency, pruning)
and every tool's error paths. `src/integration_tests.rs` renders real (tiny,
synthetic) videos end to end with ffmpeg - including multi-camera switching
with cross-fades, PiP/zoom, silent sources, clip extraction, captions with a
fake Whisper script and hostile subtitle paths - and skips itself when
ffmpeg is not in `PATH`.

## Project structure

```
src/
|-- main.rs              CLI entry point
|-- server.rs            Tool definitions, argument handling, job orchestration
|-- types.rs             Argument/result types (serde)
|-- config.rs            Environment config and output path policy
|-- jobs.rs              Job registry: background execution, cancel, limits
|-- process.rs           Subprocess execution with timeout
|-- ffmpeg.rs            ffprobe parsing, filter escaping, encoder selection
|-- audio.rs             Audio extraction, WAV loudness, silence/peaks/speakers, Whisper
|-- edl.rs               EDL generation, highlights, suggestions
|-- video.rs             Scene detection, clips, rendering, subtitles
|-- captions.rs          SRT cues, wrapping, libass styling
+-- integration_tests.rs End-to-end tests (need ffmpeg)
```

## Limitations

* No ML speaker diarization: speaker switching needs one time-synced video
  per speaker. Inputs are assumed to be synchronised (no automatic sync).
* `picture_in_picture: "auto"` is currently the same as `never`;
  `add_speaker_labels` is not implemented.
* Jobs are in-memory only.
* Whisper transcription of long media on CPU is slow; use `background: true`,
  a smaller `WHISPER_MODEL`, or `WHISPER_DEVICE=cuda`.
