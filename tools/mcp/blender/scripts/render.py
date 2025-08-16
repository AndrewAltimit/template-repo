#!/usr/bin/env python3
"""Blender rendering script."""

import json
import os
import sys
from pathlib import Path

import bpy


def update_status(job_id, status, progress=0, message=""):
    """Update job status file."""
    status_file = Path(f"/app/outputs/{job_id}.status")
    status_data = {"status": status, "progress": progress, "message": message}
    status_file.write_text(json.dumps(status_data))


def render_image(args, job_id):
    """Render a single frame."""
    try:
        # Load project if specified
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        scene = bpy.context.scene
        settings = args.get("settings", {})

        # Configure render settings
        # Handle both old and new engine names
        engine = settings.get("engine", "CYCLES")
        if engine == "EEVEE":
            engine = "BLENDER_EEVEE"
        elif engine == "WORKBENCH":
            engine = "BLENDER_WORKBENCH"
        scene.render.engine = engine
        scene.render.resolution_x = settings.get("resolution", [1920, 1080])[0]
        scene.render.resolution_y = settings.get("resolution", [1920, 1080])[1]

        # Set samples
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = settings.get("samples", 128)
            scene.cycles.use_denoising = True
        elif scene.render.engine == "BLENDER_EEVEE":
            scene.eevee.taa_render_samples = settings.get("samples", 64)

        # Set output format
        scene.render.image_settings.file_format = settings.get("format", "PNG")

        # Set frame
        scene.frame_set(args.get("frame", 1))

        # Set output path
        output_path = args.get("output_path", f"/app/outputs/{job_id}.png")
        scene.render.filepath = output_path

        # Update status
        update_status(job_id, "RUNNING", 10, "Starting render")

        # Render
        bpy.ops.render.render(write_still=True)

        # Update status
        update_status(job_id, "COMPLETED", 100, "Render complete")

        # Save output path in status
        status_file = Path(f"/app/outputs/{job_id}.status")
        status_data = json.loads(status_file.read_text())
        status_data["output_path"] = output_path
        status_file.write_text(json.dumps(status_data))

        return True

    except Exception as e:
        update_status(job_id, "FAILED", 0, str(e))
        return False


def render_animation(args, job_id):
    """Render an animation sequence."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        scene = bpy.context.scene
        settings = args.get("settings", {})

        # Configure render settings
        scene.render.engine = settings.get("engine", "EEVEE")
        scene.render.resolution_x = settings.get("resolution", [1920, 1080])[0]
        scene.render.resolution_y = settings.get("resolution", [1920, 1080])[1]

        # Set samples
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = settings.get("samples", 64)
            scene.cycles.use_denoising = True
        elif scene.render.engine == "EEVEE":
            scene.eevee.taa_render_samples = settings.get("samples", 32)

        # Set frame range
        scene.frame_start = args.get("start_frame", 1)
        scene.frame_end = args.get("end_frame", 250)
        total_frames = scene.frame_end - scene.frame_start + 1

        # Configure output
        output_format = settings.get("format", "MP4")
        output_path = args.get("output_path", f"/app/outputs/{job_id}/")

        if output_format == "FRAMES":
            # Render as image sequence
            scene.render.image_settings.file_format = "PNG"
            os.makedirs(output_path, exist_ok=True)
            scene.render.filepath = os.path.join(output_path, "####")
        else:
            # Render as video
            scene.render.image_settings.file_format = "FFMPEG"
            scene.render.ffmpeg.format = output_format
            scene.render.ffmpeg.codec = "H264"
            scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
            scene.render.filepath = output_path.rstrip("/") + f".{output_format.lower()}"

        update_status(job_id, "RUNNING", 0, f"Rendering {total_frames} frames")

        # Custom render handler to update progress
        def render_progress(scene):
            current_frame = scene.frame_current - scene.frame_start
            progress = int((current_frame / total_frames) * 100)
            update_status(job_id, "RUNNING", progress, f"Rendering frame {scene.frame_current}")

        # Register handler
        bpy.app.handlers.render_write.append(render_progress)

        # Render animation
        bpy.ops.render.render(animation=True)

        update_status(job_id, "COMPLETED", 100, "Animation render complete")

        # Save output path
        status_file = Path(f"/app/outputs/{job_id}.status")
        status_data = json.loads(status_file.read_text())
        status_data["output_path"] = scene.render.filepath
        status_file.write_text(json.dumps(status_data))

        return True

    except Exception as e:
        update_status(job_id, "FAILED", 0, str(e))
        return False


def main():
    """Main entry point."""
    # Get arguments from command line
    argv = sys.argv

    # Find the -- separator
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 2:
        print("Usage: blender --python render.py -- args.json job_id")
        sys.exit(1)

    args_file = argv[0]
    job_id = argv[1]

    # Load arguments
    with open(args_file, "r") as f:
        args = json.load(f)

    # Determine operation
    operation = args.get("operation", "render_image")

    if operation == "render_image":
        success = render_image(args, job_id)
    elif operation == "render_animation":
        success = render_animation(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
