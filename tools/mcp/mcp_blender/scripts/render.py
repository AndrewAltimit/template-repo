#!/usr/bin/env python3
"""Blender rendering script."""

import json
import os
from pathlib import Path
import sys

import bpy


def update_status(job_id, status, progress=0, message="", output_path=None):
    """Update job status file."""
    # Status files are stored in /app/outputs/jobs/ to match JobManager
    status_dir = Path("/app/outputs/jobs")
    status_dir.mkdir(parents=True, exist_ok=True)
    status_file = status_dir / f"{job_id}.status"
    status_data = {"status": status, "progress": progress, "message": message}
    if output_path:
        status_data["output_path"] = output_path
    status_file.write_text(json.dumps(status_data), encoding="utf-8")


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
        # Blender 4.2+ uses BLENDER_EEVEE_NEXT instead of BLENDER_EEVEE
        engine = settings.get("engine", "CYCLES")
        if engine == "EEVEE":
            engine = "BLENDER_EEVEE_NEXT"
        elif engine == "WORKBENCH":
            engine = "BLENDER_WORKBENCH"
        scene.render.engine = engine
        scene.render.resolution_x = settings.get("resolution", [1920, 1080])[0]
        scene.render.resolution_y = settings.get("resolution", [1920, 1080])[1]

        # Set samples
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = settings.get("samples", 128)
            scene.cycles.use_denoising = True
        elif scene.render.engine == "BLENDER_EEVEE_NEXT":
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

        # Update status with output path
        update_status(job_id, "COMPLETED", 100, "Render complete", output_path=output_path)

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
        # Handle both old and new engine names
        # Blender 4.2+ uses BLENDER_EEVEE_NEXT instead of BLENDER_EEVEE
        engine = settings.get("engine", "BLENDER_EEVEE_NEXT")
        if engine == "EEVEE":
            engine = "BLENDER_EEVEE_NEXT"
        elif engine == "WORKBENCH":
            engine = "BLENDER_WORKBENCH"
        scene.render.engine = engine
        scene.render.resolution_x = settings.get("resolution", [1920, 1080])[0]
        scene.render.resolution_y = settings.get("resolution", [1920, 1080])[1]

        # Set samples
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = settings.get("samples", 64)
            scene.cycles.use_denoising = True
        elif scene.render.engine == "BLENDER_EEVEE_NEXT":
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

        # Update status with output path
        update_status(job_id, "COMPLETED", 100, "Animation render complete", output_path=scene.render.filepath)

        return True

    except Exception as e:
        update_status(job_id, "FAILED", 0, str(e))
        return False


def batch_render(args, job_id):
    """Render multiple frames, cameras, or render layers in batch."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        scene = bpy.context.scene
        frames = args.get("frames", [1])
        cameras = args.get("cameras", [])
        layers = args.get("layers", [])
        settings = args.get("settings", {})
        output_dir = args.get("output_dir", f"/app/outputs/batch/{job_id}")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Configure render settings
        engine = settings.get("engine", "CYCLES")
        if engine == "EEVEE":
            engine = "BLENDER_EEVEE_NEXT"
        elif engine == "WORKBENCH":
            engine = "BLENDER_WORKBENCH"
        scene.render.engine = engine
        scene.render.resolution_x = settings.get("resolution", [1920, 1080])[0]
        scene.render.resolution_y = settings.get("resolution", [1920, 1080])[1]

        # Set samples
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = settings.get("samples", 128)
            scene.cycles.use_denoising = True
        elif scene.render.engine == "BLENDER_EEVEE_NEXT":
            scene.eevee.taa_render_samples = settings.get("samples", 64)

        scene.render.image_settings.file_format = settings.get("format", "PNG")

        # Get cameras to render from
        camera_objects = []
        if cameras:
            for cam_name in cameras:
                cam = bpy.data.objects.get(cam_name)
                if cam and cam.type == "CAMERA":
                    camera_objects.append(cam)
        if not camera_objects and scene.camera:
            camera_objects = [scene.camera]

        total_renders = len(frames) * len(camera_objects)
        current_render = 0
        output_files = []

        update_status(job_id, "RUNNING", 0, f"Starting batch render: {total_renders} renders")

        for cam in camera_objects:
            scene.camera = cam
            cam_name = cam.name.replace(" ", "_")

            for frame in frames:
                scene.frame_set(frame)
                output_file = os.path.join(output_dir, f"{cam_name}_frame_{frame:04d}.png")
                scene.render.filepath = output_file

                # Render
                bpy.ops.render.render(write_still=True)
                output_files.append(output_file)

                current_render += 1
                progress = int((current_render / total_renders) * 100)
                update_status(
                    job_id,
                    "RUNNING",
                    progress,
                    f"Rendered {current_render}/{total_renders}"
                )

        update_status(
            job_id,
            "COMPLETED",
            100,
            f"Batch render complete: {len(output_files)} images",
            output_path=output_dir
        )

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
    with open(args_file, "r", encoding="utf-8") as f:
        args = json.load(f)

    # Determine operation
    operation = args.get("operation", "render_image")

    if operation == "render_image":
        success = render_image(args, job_id)
    elif operation == "render_animation":
        success = render_animation(args, job_id)
    elif operation == "batch_render":
        success = batch_render(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
