#!/usr/bin/env python3
"""Blender physics simulation script."""

import json
import sys
from pathlib import Path

import bpy


def update_status(job_id, status, progress=0, message=""):
    """Update job status file."""
    status_file = Path(f"/app/outputs/{job_id}.status")
    status_data = {"status": status, "progress": progress, "message": message}
    status_file.write_text(json.dumps(status_data))


def setup_physics(args, job_id):
    """Setup physics simulation for objects."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        physics_type = args.get("physics_type")
        settings = args.get("settings", {})

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            print(f"Object '{object_name}' not found")
            return False

        # Select object
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        if physics_type == "rigid_body":
            # Add rigid body physics
            bpy.ops.rigidbody.object_add()

            rb = obj.rigid_body
            rb.type = "ACTIVE"  # or 'PASSIVE' for static objects
            rb.mass = settings.get("mass", 1.0)
            rb.friction = settings.get("friction", 0.5)
            rb.restitution = settings.get("bounce", 0.0)

            # Set collision shape
            collision_shape = settings.get("collision_shape", "CONVEX_HULL")
            rb.collision_shape = collision_shape

        elif physics_type == "soft_body":
            # Add soft body modifier
            modifier = obj.modifiers.new(name="Softbody", type="SOFT_BODY")

            sb = obj.soft_body
            sb.mass = settings.get("mass", 1.0)
            sb.friction = settings.get("friction", 0.5)
            sb.speed = 1.0

            # Goal settings (pinning)
            sb.goal_spring = 0.5
            sb.goal_friction = 0.5

        elif physics_type == "cloth":
            # Add cloth modifier
            modifier = obj.modifiers.new(name="Cloth", type="CLOTH")

            cloth = modifier.settings
            cloth.quality = settings.get("quality", 10)
            cloth.mass = settings.get("mass", 0.3)
            cloth.air_damping = settings.get("air_damping", 1.0)

            # Collision settings
            cloth.collision_settings.use_collision = True
            cloth.collision_settings.distance_min = 0.015

        elif physics_type == "fluid":
            # Add fluid modifier
            modifier = obj.modifiers.new(name="Fluid", type="FLUID")
            modifier.fluid_type = "FLOW"

            # Configure flow settings
            flow = modifier.flow_settings
            flow.flow_type = "LIQUID"
            flow.flow_behavior = "INFLOW"
            flow.use_initial_velocity = True
            flow.velocity_factor = settings.get("velocity", 1.0)

            # Need domain object for fluid sim
            domain_name = settings.get("domain", "FluidDomain")
            domain = bpy.data.objects.get(domain_name)

            if not domain:
                # Create domain if it doesn't exist
                bpy.ops.mesh.primitive_cube_add(size=10, location=(0, 0, 0))
                domain = bpy.context.active_object
                domain.name = domain_name

                # Add fluid modifier to domain
                domain_mod = domain.modifiers.new(name="Fluid", type="FLUID")
                domain_mod.fluid_type = "DOMAIN"

                # Configure domain settings
                domain_settings = domain_mod.domain_settings
                domain_settings.domain_type = "LIQUID"
                domain_settings.resolution_max = settings.get("resolution", 64)
                domain_settings.use_adaptive_timesteps = True

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error setting up physics: {e}")
        return False


def bake_simulation(args, job_id):
    """Bake physics simulation to keyframes."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        start_frame = args.get("start_frame", 1)
        end_frame = args.get("end_frame", 250)

        scene = bpy.context.scene
        scene.frame_start = start_frame
        scene.frame_end = end_frame

        update_status(job_id, "RUNNING", 10, "Preparing simulation")

        # Check for different physics types
        has_rigid_body = False
        has_soft_body = False
        has_cloth = False
        has_fluid = False

        for obj in scene.objects:
            if obj.rigid_body:
                has_rigid_body = True
            if obj.soft_body:
                has_soft_body = True
            for modifier in obj.modifiers:
                if modifier.type == "CLOTH":
                    has_cloth = True
                elif modifier.type == "FLUID":
                    has_fluid = True

        # Bake appropriate simulations
        if has_rigid_body:
            update_status(job_id, "RUNNING", 30, "Baking rigid body simulation")
            bpy.ops.ptcache.bake_all(bake=True)

        if has_soft_body:
            update_status(job_id, "RUNNING", 50, "Baking soft body simulation")
            for obj in scene.objects:
                if obj.soft_body:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.ptcache.bake(bake=True)

        if has_cloth:
            update_status(job_id, "RUNNING", 70, "Baking cloth simulation")
            for obj in scene.objects:
                for modifier in obj.modifiers:
                    if modifier.type == "CLOTH":
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.ptcache.bake(bake=True)

        if has_fluid:
            update_status(job_id, "RUNNING", 90, "Baking fluid simulation")
            # Find domain object
            for obj in scene.objects:
                for modifier in obj.modifiers:
                    if modifier.type == "FLUID" and modifier.fluid_type == "DOMAIN":
                        bpy.context.view_layer.objects.active = obj
                        # Bake fluid
                        bpy.ops.fluid.bake_all()
                        break

        update_status(job_id, "COMPLETED", 100, "Simulation baked successfully")

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        update_status(job_id, "FAILED", 0, str(e))
        return False


def setup_collision(args, job_id):
    """Setup collision for physics objects."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")

        obj = bpy.data.objects.get(object_name)
        if not obj:
            return False

        # Add collision modifier
        modifier = obj.modifiers.new(name="Collision", type="COLLISION")

        # Configure collision settings
        collision = modifier.settings
        collision.use_particle_kill = False
        collision.damping = 0.5
        collision.friction = 0.5

        # For cloth collision
        collision.cloth_friction = 5.0
        collision.thickness_outer = 0.02
        collision.thickness_inner = 0.02

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error setting up collision: {e}")
        return False


def create_particle_system(args, job_id):
    """Create particle system for object."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        particle_type = args.get("particle_type", "hair")
        settings = args.get("settings", {})

        obj = bpy.data.objects.get(object_name)
        if not obj:
            return False

        # Add particle system
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.particle_system_add()

        # Get particle settings
        psys = obj.particle_systems[-1]
        pset = psys.settings

        # Configure particle type
        pset.type = particle_type.upper()  # 'HAIR' or 'EMITTER'

        if particle_type == "hair":
            pset.count = settings.get("count", 1000)
            pset.hair_length = settings.get("length", 2.0)
            pset.hair_step = settings.get("segments", 5)
            pset.use_hair_dynamics = settings.get("dynamics", False)

        elif particle_type == "emitter":
            pset.count = settings.get("count", 1000)
            pset.frame_start = settings.get("start_frame", 1)
            pset.frame_end = settings.get("end_frame", 200)
            pset.lifetime = settings.get("lifetime", 50)

            # Physics settings
            pset.physics_type = "NEWTON"
            pset.mass = settings.get("mass", 1.0)
            pset.use_multiply_size_mass = True

            # Velocity
            pset.normal_factor = settings.get("velocity", 1.0)
            pset.factor_random = settings.get("randomness", 0.1)

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating particle system: {e}")
        return False


def main():
    """Main entry point."""
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 2:
        print("Usage: blender --python physics_sim.py -- args.json job_id")
        sys.exit(1)

    args_file = argv[0]
    job_id = argv[1]

    with open(args_file, "r") as f:
        args = json.load(f)

    operation = args.get("operation")

    if operation == "setup_physics":
        success = setup_physics(args, job_id)
    elif operation == "bake_simulation":
        success = bake_simulation(args, job_id)
    elif operation == "setup_collision":
        success = setup_collision(args, job_id)
    elif operation == "create_particle_system":
        success = create_particle_system(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
