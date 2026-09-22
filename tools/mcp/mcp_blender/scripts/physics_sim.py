#!/usr/bin/env python3
"""Blender physics simulation script."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    ScriptError,
    open_project,
    require_object,
    run,
    save_project,
    update_status,
)


def setup_physics(args, _job_id):  # noqa: C901
    """Add rigid body, soft body, cloth or fluid (liquid flow) physics to an object."""
    open_project(args.get("project"))
    object_name = args.get("object_name")
    physics_type = args.get("physics_type")
    settings = args.get("settings") or {}
    obj = require_object(object_name)
    if obj.type != "MESH":
        raise ScriptError(f"Physics can only be added to meshes; '{object_name}' is a {obj.type}")

    for other in bpy.context.selected_objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    result = {"success": True, "object": obj.name, "physics_type": physics_type}

    if physics_type == "rigid_body":
        if obj.rigid_body is None:
            bpy.ops.rigidbody.object_add()
        rb = obj.rigid_body
        rb.type = str(settings.get("rigid_body_type", "ACTIVE")).upper()
        rb.mass = float(settings.get("mass", 1.0))
        rb.friction = float(settings.get("friction", 0.5))
        rb.restitution = float(settings.get("bounce", 0.0))
        rb.collision_shape = str(settings.get("collision_shape", "CONVEX_HULL")).upper()

    elif physics_type == "soft_body":
        obj.modifiers.new(name="Softbody", type="SOFT_BODY")
        sb = obj.soft_body
        sb.mass = float(settings.get("mass", 1.0))
        sb.friction = float(settings.get("friction", 0.5))
        sb.speed = 1.0
        sb.goal_spring = 0.5
        sb.goal_friction = 0.5

    elif physics_type == "cloth":
        modifier = obj.modifiers.new(name="Cloth", type="CLOTH")
        cloth = modifier.settings
        cloth.quality = int(settings.get("quality", 10))
        cloth.mass = float(settings.get("mass", 0.3))
        cloth.air_damping = float(settings.get("air_damping", 1.0))
        modifier.collision_settings.use_collision = True
        modifier.collision_settings.distance_min = 0.015

    elif physics_type == "fluid":
        if not bpy.app.build_options.fluid:
            raise ScriptError("This Blender build has no fluid simulation support")
        modifier = next((m for m in obj.modifiers if m.type == "FLUID"), None)
        if modifier is None:
            modifier = obj.modifiers.new(name="Fluid", type="FLUID")
        elif modifier.fluid_type == "DOMAIN":
            raise ScriptError(f"'{object_name}' is already a fluid domain")
        modifier.fluid_type = "FLOW"
        flow = modifier.flow_settings
        flow.flow_type = "LIQUID"
        flow.flow_behavior = str(settings.get("flow_behavior", "INFLOW")).upper()
        flow.use_initial_velocity = True
        flow.velocity_factor = float(settings.get("velocity", 1.0))

        domain_name = settings.get("domain", "FluidDomain")
        domain = bpy.data.objects.get(domain_name)
        if domain is None:
            bpy.ops.mesh.primitive_cube_add(size=10, location=(0, 0, 0))
            domain = bpy.context.active_object
            domain.name = domain_name
            domain.display_type = "WIRE"
            domain_mod = domain.modifiers.new(name="Fluid", type="FLUID")
            domain_mod.fluid_type = "DOMAIN"
            domain_settings = domain_mod.domain_settings
            domain_settings.domain_type = "LIQUID"
            domain_settings.resolution_max = int(settings.get("resolution", 64))
            domain_settings.use_adaptive_timesteps = True
        result["domain"] = domain.name

    else:
        raise ScriptError(f"Unknown physics type '{physics_type}' (rigid_body, soft_body, cloth, fluid)")

    save_project()
    return result


def _detect_physics_types(scene):
    """Detect which physics types are present in the scene."""
    physics = {"rigid_body": False, "soft_body": False, "cloth": False, "fluid": False}
    for obj in scene.objects:
        if obj.rigid_body:
            physics["rigid_body"] = True
        if obj.soft_body:
            physics["soft_body"] = True
        for modifier in obj.modifiers:
            if modifier.type == "CLOTH":
                physics["cloth"] = True
            elif modifier.type == "FLUID":
                physics["fluid"] = True
    return physics


def bake_simulation(args, job_id):
    """Bake every point cache (rigid/soft body, cloth, particles) and fluid domain."""
    open_project(args.get("project"))
    scene = bpy.context.scene
    start = int(args.get("start_frame", scene.frame_start))
    end = int(args.get("end_frame", scene.frame_end))
    if end < start:
        raise ScriptError(f"end_frame ({end}) must be >= start_frame ({start})")
    scene.frame_start = start
    scene.frame_end = end
    if scene.rigidbody_world is not None:
        scene.rigidbody_world.point_cache.frame_start = start
        scene.rigidbody_world.point_cache.frame_end = end

    physics = _detect_physics_types(scene)
    if not any(physics.values()):
        raise ScriptError("Nothing to bake: no rigid body, soft body, cloth or fluid objects in the scene")

    update_status(job_id, "RUNNING", 10, "Baking point caches")
    baked = []
    if physics["rigid_body"] or physics["soft_body"] or physics["cloth"]:
        bpy.ops.ptcache.free_bake_all()
        bpy.ops.ptcache.bake_all(bake=True)
        baked.extend(k for k in ("rigid_body", "soft_body", "cloth") if physics[k])

    domains = _fluid_domains(scene)
    for index, domain in enumerate(domains):
        update_status(job_id, "RUNNING", 50 + int(40 * index / max(1, len(domains))), f"Baking fluid domain {domain.name}")
        settings = domain.modifiers["Fluid"].domain_settings
        settings.cache_frame_start = start
        settings.cache_frame_end = end
        with bpy.context.temp_override(object=domain, active_object=domain):
            bpy.ops.fluid.bake_all()
        baked.append(f"fluid:{domain.name}")

    save_project()
    update_status(job_id, "COMPLETED", 100, "Simulation baked")
    return {"success": True, "baked": baked, "frame_range": [start, end]}


def setup_collision(args, _job_id):
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


def create_particle_system(args, _job_id):
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


def _fluid_domains(scene):
    return [
        obj
        for obj in scene.objects
        for modifier in obj.modifiers
        if modifier.type == "FLUID" and modifier.fluid_type == "DOMAIN"
    ]


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run(
        {
            "setup_physics": setup_physics,
            "bake_simulation": bake_simulation,
            "setup_collision": setup_collision,
            "create_particle_system": create_particle_system,
        }
    )


if __name__ == "__main__":
    main()
