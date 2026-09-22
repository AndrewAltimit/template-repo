//! Tool implementations, grouped by area.

use mcp_core::tool::BoxedTool;

use crate::server::{Ctx, tool};

mod effects;
mod jobs;
mod objects;
mod project;
mod render;
mod scene;
mod simulation;

/// Every tool exposed by the server, in a stable order.
pub fn all(ctx: &Ctx) -> Vec<BoxedTool> {
    vec![
        // Projects and status
        tool::<project::CreateProject>(ctx),
        tool::<project::ListProjects>(ctx),
        tool::<project::BlenderStatus>(ctx),
        // Scene building
        tool::<scene::AddPrimitiveObjects>(ctx),
        tool::<scene::SetupLighting>(ctx),
        tool::<scene::ApplyMaterial>(ctx),
        tool::<scene::AddTexture>(ctx),
        tool::<scene::AddUvMap>(ctx),
        tool::<scene::DeleteObjects>(ctx),
        tool::<scene::CreateCurve>(ctx),
        tool::<scene::SetupWorldEnvironment>(ctx),
        tool::<scene::SetupCompositor>(ctx),
        tool::<scene::AnalyzeScene>(ctx),
        tool::<scene::OptimizeScene>(ctx),
        tool::<scene::ImportModel>(ctx),
        tool::<scene::ExportScene>(ctx),
        // Rendering (async jobs)
        tool::<render::RenderImage>(ctx),
        tool::<render::RenderAnimation>(ctx),
        tool::<render::BatchRender>(ctx),
        // Job management
        tool::<jobs::GetJobStatus>(ctx),
        tool::<jobs::GetJobResult>(ctx),
        tool::<jobs::CancelJob>(ctx),
        tool::<jobs::ListJobs>(ctx),
        // Animation, camera, physics, procedural
        tool::<simulation::SetupCamera>(ctx),
        tool::<simulation::AddCameraTrack>(ctx),
        tool::<simulation::CreateAnimation>(ctx),
        tool::<simulation::SetupPhysics>(ctx),
        tool::<simulation::BakeSimulation>(ctx),
        tool::<simulation::AddModifier>(ctx),
        tool::<simulation::AddParticleSystem>(ctx),
        tool::<simulation::AddSmokeSimulation>(ctx),
        tool::<simulation::CreateGeometryNodes>(ctx),
        // Quick effects
        tool::<effects::QuickSmoke>(ctx),
        tool::<effects::QuickLiquid>(ctx),
        tool::<effects::QuickExplode>(ctx),
        tool::<effects::QuickFur>(ctx),
        // Advanced objects
        tool::<objects::AddConstraint>(ctx),
        tool::<objects::CreateArmature>(ctx),
        tool::<objects::CreateTextObject>(ctx),
        tool::<objects::AddAdvancedPrimitives>(ctx),
        tool::<objects::ParentObjects>(ctx),
        tool::<objects::JoinObjects>(ctx),
    ]
}

#[cfg(test)]
mod tests;
