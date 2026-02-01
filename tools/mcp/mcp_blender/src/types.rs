//! Type definitions for the Blender MCP server.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Job status for async operations
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

impl std::fmt::Display for JobStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            JobStatus::Queued => write!(f, "QUEUED"),
            JobStatus::Running => write!(f, "RUNNING"),
            JobStatus::Completed => write!(f, "COMPLETED"),
            JobStatus::Failed => write!(f, "FAILED"),
            JobStatus::Cancelled => write!(f, "CANCELLED"),
        }
    }
}

/// A job representing an async Blender operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    pub id: Uuid,
    pub job_type: String,
    pub status: JobStatus,
    pub progress: u8,
    pub message: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: Option<DateTime<Utc>>,
    pub result: Option<serde_json::Value>,
    pub output_path: Option<String>,
    pub error: Option<String>,
}

impl Job {
    pub fn new(job_type: &str) -> Self {
        Self {
            id: Uuid::new_v4(),
            job_type: job_type.to_string(),
            status: JobStatus::Queued,
            progress: 0,
            message: String::new(),
            created_at: Utc::now(),
            updated_at: None,
            result: None,
            output_path: None,
            error: None,
        }
    }

    pub fn with_id(mut self, id: Uuid) -> Self {
        self.id = id;
        self
    }
}

/// Project template types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProjectTemplate {
    Empty,
    BasicScene,
    StudioLighting,
    LitEmpty,
    Procedural,
    Animation,
    Physics,
    Architectural,
    Product,
    Vfx,
    GameAsset,
    Sculpting,
}

impl Default for ProjectTemplate {
    fn default() -> Self {
        ProjectTemplate::BasicScene
    }
}

impl std::fmt::Display for ProjectTemplate {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProjectTemplate::Empty => write!(f, "empty"),
            ProjectTemplate::BasicScene => write!(f, "basic_scene"),
            ProjectTemplate::StudioLighting => write!(f, "studio_lighting"),
            ProjectTemplate::LitEmpty => write!(f, "lit_empty"),
            ProjectTemplate::Procedural => write!(f, "procedural"),
            ProjectTemplate::Animation => write!(f, "animation"),
            ProjectTemplate::Physics => write!(f, "physics"),
            ProjectTemplate::Architectural => write!(f, "architectural"),
            ProjectTemplate::Product => write!(f, "product"),
            ProjectTemplate::Vfx => write!(f, "vfx"),
            ProjectTemplate::GameAsset => write!(f, "game_asset"),
            ProjectTemplate::Sculpting => write!(f, "sculpting"),
        }
    }
}

/// Primitive object types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PrimitiveType {
    Cube,
    Sphere,
    Cylinder,
    Cone,
    Torus,
    Plane,
    Monkey,
}

impl std::fmt::Display for PrimitiveType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PrimitiveType::Cube => write!(f, "cube"),
            PrimitiveType::Sphere => write!(f, "sphere"),
            PrimitiveType::Cylinder => write!(f, "cylinder"),
            PrimitiveType::Cone => write!(f, "cone"),
            PrimitiveType::Torus => write!(f, "torus"),
            PrimitiveType::Plane => write!(f, "plane"),
            PrimitiveType::Monkey => write!(f, "monkey"),
        }
    }
}

/// Lighting setup types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LightingType {
    ThreePoint,
    Studio,
    Hdri,
    Sun,
    Area,
}

impl std::fmt::Display for LightingType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LightingType::ThreePoint => write!(f, "three_point"),
            LightingType::Studio => write!(f, "studio"),
            LightingType::Hdri => write!(f, "hdri"),
            LightingType::Sun => write!(f, "sun"),
            LightingType::Area => write!(f, "area"),
        }
    }
}

/// Material types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MaterialType {
    Principled,
    Emission,
    Glass,
    Metal,
    Plastic,
    Wood,
}

impl Default for MaterialType {
    fn default() -> Self {
        MaterialType::Principled
    }
}

impl std::fmt::Display for MaterialType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MaterialType::Principled => write!(f, "principled"),
            MaterialType::Emission => write!(f, "emission"),
            MaterialType::Glass => write!(f, "glass"),
            MaterialType::Metal => write!(f, "metal"),
            MaterialType::Plastic => write!(f, "plastic"),
            MaterialType::Wood => write!(f, "wood"),
        }
    }
}

/// Render engine types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RenderEngine {
    Cycles,
    BlenderEevee,
    BlenderWorkbench,
}

impl Default for RenderEngine {
    fn default() -> Self {
        RenderEngine::Cycles
    }
}

impl std::fmt::Display for RenderEngine {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RenderEngine::Cycles => write!(f, "CYCLES"),
            RenderEngine::BlenderEevee => write!(f, "BLENDER_EEVEE"),
            RenderEngine::BlenderWorkbench => write!(f, "BLENDER_WORKBENCH"),
        }
    }
}

/// Image format types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ImageFormat {
    Png,
    Jpeg,
    Exr,
    Tiff,
}

impl Default for ImageFormat {
    fn default() -> Self {
        ImageFormat::Png
    }
}

impl std::fmt::Display for ImageFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ImageFormat::Png => write!(f, "PNG"),
            ImageFormat::Jpeg => write!(f, "JPEG"),
            ImageFormat::Exr => write!(f, "EXR"),
            ImageFormat::Tiff => write!(f, "TIFF"),
        }
    }
}

/// Video format types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VideoFormat {
    Mp4,
    Avi,
    Mov,
    Frames,
}

impl Default for VideoFormat {
    fn default() -> Self {
        VideoFormat::Mp4
    }
}

impl std::fmt::Display for VideoFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VideoFormat::Mp4 => write!(f, "MP4"),
            VideoFormat::Avi => write!(f, "AVI"),
            VideoFormat::Mov => write!(f, "MOV"),
            VideoFormat::Frames => write!(f, "FRAMES"),
        }
    }
}

/// Physics simulation types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PhysicsType {
    RigidBody,
    SoftBody,
    Cloth,
    Fluid,
}

impl std::fmt::Display for PhysicsType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PhysicsType::RigidBody => write!(f, "rigid_body"),
            PhysicsType::SoftBody => write!(f, "soft_body"),
            PhysicsType::Cloth => write!(f, "cloth"),
            PhysicsType::Fluid => write!(f, "fluid"),
        }
    }
}

/// Collision shape types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CollisionShape {
    Box,
    Sphere,
    ConvexHull,
    Mesh,
}

impl Default for CollisionShape {
    fn default() -> Self {
        CollisionShape::ConvexHull
    }
}

impl std::fmt::Display for CollisionShape {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CollisionShape::Box => write!(f, "box"),
            CollisionShape::Sphere => write!(f, "sphere"),
            CollisionShape::ConvexHull => write!(f, "convex_hull"),
            CollisionShape::Mesh => write!(f, "mesh"),
        }
    }
}

/// Interpolation types for animation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Interpolation {
    Linear,
    Bezier,
    Constant,
}

impl Default for Interpolation {
    fn default() -> Self {
        Interpolation::Bezier
    }
}

impl std::fmt::Display for Interpolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Interpolation::Linear => write!(f, "LINEAR"),
            Interpolation::Bezier => write!(f, "BEZIER"),
            Interpolation::Constant => write!(f, "CONSTANT"),
        }
    }
}

/// Geometry node setup types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GeometryNodeSetup {
    Scatter,
    Array,
    Grid,
    Curve,
    Spiral,
    Volume,
    WaveDeform,
    Twist,
    NoiseDisplace,
    Extrude,
    VoronoiScatter,
    MeshToPoints,
    CrystalScatter,
    CrystalCluster,
    Custom,
    ProximityMask,
    BlurAttribute,
    MapRangeDisplacement,
    EdgeCreaseDetection,
    OrganicMutation,
}

impl std::fmt::Display for GeometryNodeSetup {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            GeometryNodeSetup::Scatter => write!(f, "scatter"),
            GeometryNodeSetup::Array => write!(f, "array"),
            GeometryNodeSetup::Grid => write!(f, "grid"),
            GeometryNodeSetup::Curve => write!(f, "curve"),
            GeometryNodeSetup::Spiral => write!(f, "spiral"),
            GeometryNodeSetup::Volume => write!(f, "volume"),
            GeometryNodeSetup::WaveDeform => write!(f, "wave_deform"),
            GeometryNodeSetup::Twist => write!(f, "twist"),
            GeometryNodeSetup::NoiseDisplace => write!(f, "noise_displace"),
            GeometryNodeSetup::Extrude => write!(f, "extrude"),
            GeometryNodeSetup::VoronoiScatter => write!(f, "voronoi_scatter"),
            GeometryNodeSetup::MeshToPoints => write!(f, "mesh_to_points"),
            GeometryNodeSetup::CrystalScatter => write!(f, "crystal_scatter"),
            GeometryNodeSetup::CrystalCluster => write!(f, "crystal_cluster"),
            GeometryNodeSetup::Custom => write!(f, "custom"),
            GeometryNodeSetup::ProximityMask => write!(f, "proximity_mask"),
            GeometryNodeSetup::BlurAttribute => write!(f, "blur_attribute"),
            GeometryNodeSetup::MapRangeDisplacement => write!(f, "map_range_displacement"),
            GeometryNodeSetup::EdgeCreaseDetection => write!(f, "edge_crease_detection"),
            GeometryNodeSetup::OrganicMutation => write!(f, "organic_mutation"),
        }
    }
}

/// Export format types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExportFormat {
    Fbx,
    Obj,
    Gltf,
    Stl,
    Usd,
}

impl std::fmt::Display for ExportFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ExportFormat::Fbx => write!(f, "FBX"),
            ExportFormat::Obj => write!(f, "OBJ"),
            ExportFormat::Gltf => write!(f, "GLTF"),
            ExportFormat::Stl => write!(f, "STL"),
            ExportFormat::Usd => write!(f, "USD"),
        }
    }
}

/// Import format types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ImportFormat {
    Fbx,
    Obj,
    Gltf,
    Stl,
    Ply,
}

impl std::fmt::Display for ImportFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ImportFormat::Fbx => write!(f, "FBX"),
            ImportFormat::Obj => write!(f, "OBJ"),
            ImportFormat::Gltf => write!(f, "GLTF"),
            ImportFormat::Stl => write!(f, "STL"),
            ImportFormat::Ply => write!(f, "PLY"),
        }
    }
}

/// Modifier types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ModifierType {
    Subsurf,
    Array,
    Mirror,
    Solidify,
    Bevel,
    Decimate,
    Remesh,
    Smooth,
    Wave,
    Displace,
}

impl std::fmt::Display for ModifierType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ModifierType::Subsurf => write!(f, "SUBSURF"),
            ModifierType::Array => write!(f, "ARRAY"),
            ModifierType::Mirror => write!(f, "MIRROR"),
            ModifierType::Solidify => write!(f, "SOLIDIFY"),
            ModifierType::Bevel => write!(f, "BEVEL"),
            ModifierType::Decimate => write!(f, "DECIMATE"),
            ModifierType::Remesh => write!(f, "REMESH"),
            ModifierType::Smooth => write!(f, "SMOOTH"),
            ModifierType::Wave => write!(f, "WAVE"),
            ModifierType::Displace => write!(f, "DISPLACE"),
        }
    }
}

/// Camera tracking types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TrackType {
    TrackTo,
    DampedTrack,
    LockedTrack,
}

impl std::fmt::Display for TrackType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TrackType::TrackTo => write!(f, "TRACK_TO"),
            TrackType::DampedTrack => write!(f, "DAMPED_TRACK"),
            TrackType::LockedTrack => write!(f, "LOCKED_TRACK"),
        }
    }
}

/// Texture types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TextureType {
    Image,
    Noise,
    Voronoi,
    Musgrave,
    Wave,
    Magic,
    Brick,
    Checker,
}

impl std::fmt::Display for TextureType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TextureType::Image => write!(f, "IMAGE"),
            TextureType::Noise => write!(f, "NOISE"),
            TextureType::Voronoi => write!(f, "VORONOI"),
            TextureType::Musgrave => write!(f, "MUSGRAVE"),
            TextureType::Wave => write!(f, "WAVE"),
            TextureType::Magic => write!(f, "MAGIC"),
            TextureType::Brick => write!(f, "BRICK"),
            TextureType::Checker => write!(f, "CHECKER"),
        }
    }
}

/// UV projection types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum UvProjection {
    SmartProject,
    CubeProject,
    CylinderProject,
    SphereProject,
    ProjectFromView,
}

impl std::fmt::Display for UvProjection {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            UvProjection::SmartProject => write!(f, "SMART_PROJECT"),
            UvProjection::CubeProject => write!(f, "CUBE_PROJECT"),
            UvProjection::CylinderProject => write!(f, "CYLINDER_PROJECT"),
            UvProjection::SphereProject => write!(f, "SPHERE_PROJECT"),
            UvProjection::ProjectFromView => write!(f, "PROJECT_FROM_VIEW"),
        }
    }
}

/// Compositor setup types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CompositorSetup {
    Basic,
    Denoising,
    ColorGrading,
    Glare,
    FogGlow,
    LensDistortion,
    Vignette,
}

impl std::fmt::Display for CompositorSetup {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CompositorSetup::Basic => write!(f, "BASIC"),
            CompositorSetup::Denoising => write!(f, "DENOISING"),
            CompositorSetup::ColorGrading => write!(f, "COLOR_GRADING"),
            CompositorSetup::Glare => write!(f, "GLARE"),
            CompositorSetup::FogGlow => write!(f, "FOG_GLOW"),
            CompositorSetup::LensDistortion => write!(f, "LENS_DISTORTION"),
            CompositorSetup::Vignette => write!(f, "VIGNETTE"),
        }
    }
}

/// World environment types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EnvironmentType {
    Hdri,
    SkyTexture,
    Gradient,
    Color,
    Volumetric,
}

impl std::fmt::Display for EnvironmentType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EnvironmentType::Hdri => write!(f, "HDRI"),
            EnvironmentType::SkyTexture => write!(f, "SKY_TEXTURE"),
            EnvironmentType::Gradient => write!(f, "GRADIENT"),
            EnvironmentType::Color => write!(f, "COLOR"),
            EnvironmentType::Volumetric => write!(f, "VOLUMETRIC"),
        }
    }
}

/// Particle system types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParticleType {
    Emitter,
    Hair,
}

impl std::fmt::Display for ParticleType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ParticleType::Emitter => write!(f, "emitter"),
            ParticleType::Hair => write!(f, "hair"),
        }
    }
}

/// Smoke simulation types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SmokeType {
    Smoke,
    Fire,
    Both,
}

impl std::fmt::Display for SmokeType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SmokeType::Smoke => write!(f, "smoke"),
            SmokeType::Fire => write!(f, "fire"),
            SmokeType::Both => write!(f, "both"),
        }
    }
}

/// Scene analysis types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum AnalysisType {
    Basic,
    Detailed,
    Performance,
    Memory,
}

impl std::fmt::Display for AnalysisType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AnalysisType::Basic => write!(f, "BASIC"),
            AnalysisType::Detailed => write!(f, "DETAILED"),
            AnalysisType::Performance => write!(f, "PERFORMANCE"),
            AnalysisType::Memory => write!(f, "MEMORY"),
        }
    }
}

/// Scene optimization types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OptimizationType {
    MeshCleanup,
    TextureOptimization,
    ModifierApply,
    InstanceOptimization,
    MaterialCleanup,
}

impl std::fmt::Display for OptimizationType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OptimizationType::MeshCleanup => write!(f, "MESH_CLEANUP"),
            OptimizationType::TextureOptimization => write!(f, "TEXTURE_OPTIMIZATION"),
            OptimizationType::ModifierApply => write!(f, "MODIFIER_APPLY"),
            OptimizationType::InstanceOptimization => write!(f, "INSTANCE_OPTIMIZATION"),
            OptimizationType::MaterialCleanup => write!(f, "MATERIAL_CLEANUP"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ========== JobStatus Tests ==========
    #[test]
    fn test_job_status_display() {
        assert_eq!(JobStatus::Queued.to_string(), "QUEUED");
        assert_eq!(JobStatus::Running.to_string(), "RUNNING");
        assert_eq!(JobStatus::Completed.to_string(), "COMPLETED");
        assert_eq!(JobStatus::Failed.to_string(), "FAILED");
        assert_eq!(JobStatus::Cancelled.to_string(), "CANCELLED");
    }

    #[test]
    fn test_job_status_serialization() {
        assert_eq!(
            serde_json::to_string(&JobStatus::Completed).unwrap(),
            "\"COMPLETED\""
        );
        assert_eq!(
            serde_json::to_string(&JobStatus::Running).unwrap(),
            "\"RUNNING\""
        );
    }

    #[test]
    fn test_job_status_deserialization() {
        let status: JobStatus = serde_json::from_str("\"RUNNING\"").unwrap();
        assert_eq!(status, JobStatus::Running);

        let status: JobStatus = serde_json::from_str("\"FAILED\"").unwrap();
        assert_eq!(status, JobStatus::Failed);
    }

    // ========== Job Tests ==========
    #[test]
    fn test_job_creation() {
        let job = Job::new("render");
        assert_eq!(job.job_type, "render");
        assert_eq!(job.status, JobStatus::Queued);
        assert_eq!(job.progress, 0);
        assert!(job.message.is_empty());
        assert!(job.result.is_none());
        assert!(job.output_path.is_none());
        assert!(job.error.is_none());
    }

    #[test]
    fn test_job_with_custom_id() {
        let custom_id = Uuid::new_v4();
        let job = Job::new("bake").with_id(custom_id);
        assert_eq!(job.id, custom_id);
        assert_eq!(job.job_type, "bake");
    }

    #[test]
    fn test_job_serialization_roundtrip() {
        let job = Job::new("animation");
        let json = serde_json::to_string(&job).unwrap();
        let restored: Job = serde_json::from_str(&json).unwrap();
        assert_eq!(restored.job_type, job.job_type);
        assert_eq!(restored.status, job.status);
        assert_eq!(restored.id, job.id);
    }

    // ========== ProjectTemplate Tests ==========
    #[test]
    fn test_project_template_display() {
        assert_eq!(ProjectTemplate::Empty.to_string(), "empty");
        assert_eq!(ProjectTemplate::BasicScene.to_string(), "basic_scene");
        assert_eq!(
            ProjectTemplate::StudioLighting.to_string(),
            "studio_lighting"
        );
        assert_eq!(ProjectTemplate::LitEmpty.to_string(), "lit_empty");
        assert_eq!(ProjectTemplate::Procedural.to_string(), "procedural");
        assert_eq!(ProjectTemplate::Animation.to_string(), "animation");
        assert_eq!(ProjectTemplate::Physics.to_string(), "physics");
        assert_eq!(ProjectTemplate::Architectural.to_string(), "architectural");
        assert_eq!(ProjectTemplate::Product.to_string(), "product");
        assert_eq!(ProjectTemplate::Vfx.to_string(), "vfx");
        assert_eq!(ProjectTemplate::GameAsset.to_string(), "game_asset");
        assert_eq!(ProjectTemplate::Sculpting.to_string(), "sculpting");
    }

    #[test]
    fn test_project_template_default() {
        assert_eq!(ProjectTemplate::default(), ProjectTemplate::BasicScene);
    }

    #[test]
    fn test_project_template_serialization() {
        assert_eq!(
            serde_json::to_string(&ProjectTemplate::Physics).unwrap(),
            "\"physics\""
        );
        let template: ProjectTemplate = serde_json::from_str("\"vfx\"").unwrap();
        assert_eq!(template, ProjectTemplate::Vfx);
    }

    // ========== PrimitiveType Tests ==========
    #[test]
    fn test_primitive_type_all_variants() {
        assert_eq!(PrimitiveType::Cube.to_string(), "cube");
        assert_eq!(PrimitiveType::Sphere.to_string(), "sphere");
        assert_eq!(PrimitiveType::Cylinder.to_string(), "cylinder");
        assert_eq!(PrimitiveType::Cone.to_string(), "cone");
        assert_eq!(PrimitiveType::Torus.to_string(), "torus");
        assert_eq!(PrimitiveType::Plane.to_string(), "plane");
        assert_eq!(PrimitiveType::Monkey.to_string(), "monkey");
    }

    #[test]
    fn test_primitive_type_serialization() {
        assert_eq!(
            serde_json::to_string(&PrimitiveType::Monkey).unwrap(),
            "\"monkey\""
        );
        let prim: PrimitiveType = serde_json::from_str("\"torus\"").unwrap();
        assert_eq!(prim, PrimitiveType::Torus);
    }

    // ========== LightingType Tests ==========
    #[test]
    fn test_lighting_type_all_variants() {
        assert_eq!(LightingType::ThreePoint.to_string(), "three_point");
        assert_eq!(LightingType::Studio.to_string(), "studio");
        assert_eq!(LightingType::Hdri.to_string(), "hdri");
        assert_eq!(LightingType::Sun.to_string(), "sun");
        assert_eq!(LightingType::Area.to_string(), "area");
    }

    // ========== MaterialType Tests ==========
    #[test]
    fn test_material_type_default() {
        assert_eq!(MaterialType::default(), MaterialType::Principled);
    }

    #[test]
    fn test_material_type_all_variants() {
        assert_eq!(MaterialType::Principled.to_string(), "principled");
        assert_eq!(MaterialType::Emission.to_string(), "emission");
        assert_eq!(MaterialType::Glass.to_string(), "glass");
        assert_eq!(MaterialType::Metal.to_string(), "metal");
        assert_eq!(MaterialType::Plastic.to_string(), "plastic");
        assert_eq!(MaterialType::Wood.to_string(), "wood");
    }

    // ========== RenderEngine Tests ==========
    #[test]
    fn test_render_engine_default() {
        assert_eq!(RenderEngine::default(), RenderEngine::Cycles);
    }

    #[test]
    fn test_render_engine_serialization() {
        assert_eq!(
            serde_json::to_string(&RenderEngine::Cycles).unwrap(),
            "\"CYCLES\""
        );
        assert_eq!(
            serde_json::to_string(&RenderEngine::BlenderEevee).unwrap(),
            "\"BLENDER_EEVEE\""
        );

        let engine: RenderEngine = serde_json::from_str("\"BLENDER_WORKBENCH\"").unwrap();
        assert_eq!(engine, RenderEngine::BlenderWorkbench);
    }

    // ========== ImageFormat Tests ==========
    #[test]
    fn test_image_format_default() {
        assert_eq!(ImageFormat::default(), ImageFormat::Png);
    }

    #[test]
    fn test_image_format_all_variants() {
        assert_eq!(ImageFormat::Png.to_string(), "PNG");
        assert_eq!(ImageFormat::Jpeg.to_string(), "JPEG");
        assert_eq!(ImageFormat::Exr.to_string(), "EXR");
        assert_eq!(ImageFormat::Tiff.to_string(), "TIFF");
    }

    // ========== PhysicsType Tests ==========
    #[test]
    fn test_physics_type_all_variants() {
        assert_eq!(PhysicsType::RigidBody.to_string(), "rigid_body");
        assert_eq!(PhysicsType::SoftBody.to_string(), "soft_body");
        assert_eq!(PhysicsType::Cloth.to_string(), "cloth");
        assert_eq!(PhysicsType::Fluid.to_string(), "fluid");
    }

    // ========== ExportFormat Tests ==========
    #[test]
    fn test_export_format_all_variants() {
        assert_eq!(ExportFormat::Fbx.to_string(), "FBX");
        assert_eq!(ExportFormat::Obj.to_string(), "OBJ");
        assert_eq!(ExportFormat::Gltf.to_string(), "GLTF");
        assert_eq!(ExportFormat::Stl.to_string(), "STL");
        assert_eq!(ExportFormat::Usd.to_string(), "USD");
    }

    // ========== SmokeType Tests ==========
    #[test]
    fn test_smoke_type_all_variants() {
        assert_eq!(SmokeType::Smoke.to_string(), "smoke");
        assert_eq!(SmokeType::Fire.to_string(), "fire");
        assert_eq!(SmokeType::Both.to_string(), "both");
    }

    // ========== AnalysisType Tests ==========
    #[test]
    fn test_analysis_type_serialization() {
        assert_eq!(
            serde_json::to_string(&AnalysisType::Basic).unwrap(),
            "\"BASIC\""
        );
        assert_eq!(
            serde_json::to_string(&AnalysisType::Performance).unwrap(),
            "\"PERFORMANCE\""
        );
    }

    // ========== OptimizationType Tests ==========
    #[test]
    fn test_optimization_type_all_variants() {
        assert_eq!(OptimizationType::MeshCleanup.to_string(), "MESH_CLEANUP");
        assert_eq!(
            OptimizationType::TextureOptimization.to_string(),
            "TEXTURE_OPTIMIZATION"
        );
        assert_eq!(
            OptimizationType::ModifierApply.to_string(),
            "MODIFIER_APPLY"
        );
        assert_eq!(
            OptimizationType::InstanceOptimization.to_string(),
            "INSTANCE_OPTIMIZATION"
        );
        assert_eq!(
            OptimizationType::MaterialCleanup.to_string(),
            "MATERIAL_CLEANUP"
        );
    }
}
