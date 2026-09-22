#!/usr/bin/env python3
"""Blender rendering script (single frames, animations, batches).

Run by the MCP server as ``blender --background --python render.py --
<args.json> <job_id>``. Progress is published through job status files and the
final result through the ``MCP_RESULT:`` line (see ``mcp_common.py``).
"""

import os
from pathlib import Path
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    ScriptError,
    is_eevee,
    open_project,
    resolve_engine,
    run,
    update_status,
)

# User-facing still formats -> Blender image_settings.file_format identifiers.
IMAGE_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "JPG": "JPEG", "EXR": "OPEN_EXR", "OPEN_EXR": "OPEN_EXR", "TIFF": "TIFF"}
# User-facing video formats -> FFmpeg container identifiers.
VIDEO_CONTAINERS = {"MP4": "MPEG4", "AVI": "AVI", "MOV": "QUICKTIME", "MKV": "MKV", "WEBM": "WEBM"}


def configure_render(scene, settings, default_engine, default_samples):
    """Apply engine, resolution and sample settings shared by every render op."""
    scene.render.engine = resolve_engine(settings.get("engine"), default_engine)
    resolution = settings.get("resolution")
    if resolution:
        if len(resolution) != 2 or min(resolution) <= 0:
            raise ScriptError(f"resolution must be [width, height] with positive values, got {resolution}")
        scene.render.resolution_x = int(resolution[0])
        scene.render.resolution_y = int(resolution[1])
    if "resolution_percentage" in settings:
        scene.render.resolution_percentage = int(settings["resolution_percentage"])
    samples = int(settings.get("samples", default_samples))
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = bool(settings.get("denoise", True))
        scene.cycles.device = "GPU" if settings.get("use_gpu") else "CPU"
    elif is_eevee(scene.render.engine):
        scene.eevee.taa_render_samples = samples
    if "film_transparent" in settings:
        scene.render.film_transparent = bool(settings["film_transparent"])


def set_image_format(scene, fmt):
    """Set a still-image output format; returns the Blender identifier."""
    identifier = IMAGE_FORMATS.get(str(fmt).upper())
    if identifier is None:
        raise ScriptError(f"Unsupported image format '{fmt}'. Supported: PNG, JPEG, EXR, TIFF")
    scene.render.image_settings.file_format = identifier
    return identifier


def require_camera(scene):
    if scene.camera is None:
        raise ScriptError("Scene has no active camera; add one with setup_camera first")


def render_image(args, job_id):
    """Render a single frame to ``output_path``."""
    open_project(args.get("project"))
    scene = bpy.context.scene
    settings = args.get("settings") or {}
    configure_render(scene, settings, "CYCLES", 128)
    set_image_format(scene, settings.get("format", "PNG"))
    require_camera(scene)

    frame = int(args.get("frame", scene.frame_current))
    scene.frame_set(frame)
    output_path = args.get("output_path") or f"/app/outputs/renders/{job_id}.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # The server already picked the right extension; stop Blender appending another.
    scene.render.use_file_extension = False
    scene.render.filepath = output_path

    update_status(job_id, "RUNNING", 10, f"Rendering frame {frame} with {scene.render.engine}")
    bpy.ops.render.render(write_still=True)
    if not Path(output_path).is_file():
        raise ScriptError(f"Render finished but no image was written to {output_path}")
    update_status(job_id, "COMPLETED", 100, "Render complete", output_path=output_path)
    return {"success": True, "output_path": output_path, "frame": frame, "engine": scene.render.engine}


def render_animation(args, job_id):
    """Render a frame range to a video file or a PNG sequence."""
    open_project(args.get("project"))
    scene = bpy.context.scene
    settings = args.get("settings") or {}
    configure_render(scene, settings, "EEVEE", 64)
    require_camera(scene)

    start = int(args.get("start_frame", scene.frame_start))
    end = int(args.get("end_frame", scene.frame_end))
    if end < start:
        raise ScriptError(f"end_frame ({end}) must be >= start_frame ({start})")
    scene.frame_start = start
    scene.frame_end = end
    total = end - start + 1

    output_format = str(settings.get("format", "MP4")).upper()
    output_base = (args.get("output_path") or f"/app/outputs/animations/{job_id}").rstrip("/")
    if output_format == "FRAMES":
        os.makedirs(output_base, exist_ok=True)
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = os.path.join(output_base, "frame_####")
        scene.render.use_file_extension = True
        output_path = output_base
    else:
        container = VIDEO_CONTAINERS.get(output_format)
        if container is None:
            raise ScriptError(f"Unsupported animation format '{output_format}'. Supported: MP4, AVI, MOV, MKV, WEBM, FRAMES")
        Path(output_base).parent.mkdir(parents=True, exist_ok=True)
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = container
        scene.render.ffmpeg.codec = "VP9" if container == "WEBM" else "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        output_path = f"{output_base}.{output_format.lower()}"
        scene.render.use_file_extension = False
        scene.render.filepath = output_path

    rendered = {"count": 0}

    def on_frame_written(scn, *_):
        rendered["count"] += 1
        progress = min(99, int(rendered["count"] * 100 / total))
        update_status(job_id, "RUNNING", progress, f"Rendered frame {scn.frame_current} ({rendered['count']}/{total})")

    bpy.app.handlers.render_write.append(on_frame_written)
    update_status(job_id, "RUNNING", 0, f"Rendering {total} frames with {scene.render.engine}")
    bpy.ops.render.render(animation=True)

    if output_format != "FRAMES" and not Path(output_path).is_file():
        raise ScriptError(f"Animation render finished but {output_path} was not written")
    update_status(job_id, "COMPLETED", 100, "Animation render complete", output_path=output_path)
    return {"success": True, "output_path": output_path, "frames": total, "format": output_format}


def batch_render(args, job_id):  # noqa: C901
    """Render every (camera, view layer, frame) combination as separate images."""
    open_project(args.get("project"))
    scene = bpy.context.scene
    settings = args.get("settings") or {}
    configure_render(scene, settings, "CYCLES", 128)
    fmt = set_image_format(scene, settings.get("format", "PNG"))
    extension = {"PNG": "png", "JPEG": "jpg", "OPEN_EXR": "exr", "TIFF": "tif"}[fmt]
    scene.render.use_file_extension = False

    frames = [int(f) for f in (args.get("frames") or [scene.frame_current])]
    output_dir = args.get("output_dir") or f"/app/outputs/batch/{job_id}"
    os.makedirs(output_dir, exist_ok=True)

    cameras = []
    for cam_name in args.get("cameras") or []:
        cam = bpy.data.objects.get(cam_name)
        if cam is None or cam.type != "CAMERA":
            raise ScriptError(f"Camera '{cam_name}' not found")
        cameras.append(cam)
    if not cameras:
        require_camera(scene)
        cameras = [scene.camera]

    layer_names = list(args.get("layers") or [])
    for name in layer_names:
        if name not in scene.view_layers:
            available = ", ".join(v.name for v in scene.view_layers)
            raise ScriptError(f"View layer '{name}' not found. Available: {available}")
    layers = layer_names or [None]

    total = len(frames) * len(cameras) * len(layers)
    done = 0
    output_files = []
    update_status(job_id, "RUNNING", 0, f"Starting batch render: {total} images")
    original_use = {v.name: v.use for v in scene.view_layers}
    try:
        for layer in layers:
            if layer is not None:
                for view_layer in scene.view_layers:
                    view_layer.use = view_layer.name == layer
            for cam in cameras:
                scene.camera = cam
                for frame in frames:
                    scene.frame_set(frame)
                    parts = [cam.name.replace(" ", "_")]
                    if layer is not None:
                        parts.append(layer.replace(" ", "_"))
                    parts.append(f"frame_{frame:04d}")
                    output_file = os.path.join(output_dir, "_".join(parts) + f".{extension}")
                    scene.render.filepath = output_file
                    bpy.ops.render.render(write_still=True)
                    output_files.append(output_file)
                    done += 1
                    update_status(job_id, "RUNNING", min(99, int(done * 100 / total)), f"Rendered {done}/{total}")
    finally:
        for view_layer in scene.view_layers:
            view_layer.use = original_use.get(view_layer.name, True)

    update_status(job_id, "COMPLETED", 100, f"Batch render complete: {len(output_files)} images", output_path=output_dir)
    return {"success": True, "output_path": output_dir, "output_files": output_files}


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run({"render_image": render_image, "render_animation": render_animation, "batch_render": batch_render})


if __name__ == "__main__":
    main()
