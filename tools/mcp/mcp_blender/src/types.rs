//! Shared types: job records and the validated string enums used by tool
//! arguments.
//!
//! Enums are declared with [`string_enum!`], which keeps the accepted values,
//! the JSON-schema `enum` lists and the value forwarded to the Blender scripts
//! in one place. Parsing is case-insensitive (`"cube"`, `"CUBE"` and `"Cube"`
//! are all accepted) but the canonical spelling is always what gets forwarded.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Declare a closed set of string values with case-insensitive parsing,
/// canonical serialization and an `ALL` list for JSON schemas.
macro_rules! string_enum {
    ($(#[$meta:meta])* $name:ident { $($variant:ident => $text:literal),+ $(,)? }) => {
        $(#[$meta])*
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
        pub enum $name {
            $(
                #[doc = concat!("`", $text, "`")]
                $variant
            ),+
        }

        impl $name {
            /// Every accepted value, in canonical spelling.
            pub const ALL: &'static [&'static str] = &[$($text),+];

            /// Canonical spelling (what the Blender scripts receive).
            pub fn as_str(self) -> &'static str {
                match self {
                    $(Self::$variant => $text),+
                }
            }
        }

        impl std::str::FromStr for $name {
            type Err = String;

            fn from_str(value: &str) -> Result<Self, Self::Err> {
                $(
                    if value.eq_ignore_ascii_case($text) {
                        return Ok(Self::$variant);
                    }
                )+
                Err(format!(
                    "invalid value '{}' (expected one of: {})",
                    value,
                    Self::ALL.join(", ")
                ))
            }
        }

        impl std::fmt::Display for $name {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                f.write_str(self.as_str())
            }
        }

        impl Serialize for $name {
            fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
                serializer.serialize_str(self.as_str())
            }
        }

        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
                let raw = String::deserialize(deserializer)?;
                raw.parse().map_err(serde::de::Error::custom)
            }
        }
    };
}

string_enum! {
    /// Lifecycle state of an asynchronous job.
    JobStatus {
        Queued => "QUEUED",
        Running => "RUNNING",
        Completed => "COMPLETED",
        Failed => "FAILED",
        Cancelled => "CANCELLED",
    }
}

impl JobStatus {
    /// Whether the job can no longer change state.
    pub fn is_terminal(self) -> bool {
        matches!(self, Self::Completed | Self::Failed | Self::Cancelled)
    }
}

string_enum! {
    /// Project templates understood by `scene_builder.py`.
    ProjectTemplate {
        Empty => "empty",
        BasicScene => "basic_scene",
        StudioLighting => "studio_lighting",
        LitEmpty => "lit_empty",
        Procedural => "procedural",
        Animation => "animation",
        Physics => "physics",
        Architectural => "architectural",
        Product => "product",
        Vfx => "vfx",
        GameAsset => "game_asset",
        Sculpting => "sculpting",
    }
}

string_enum! {
    /// Render engines. EEVEE aliases are resolved to whatever the running
    /// Blender calls it (`BLENDER_EEVEE_NEXT` in 4.2-4.x).
    RenderEngine {
        Cycles => "CYCLES",
        Eevee => "BLENDER_EEVEE",
        EeveeNext => "BLENDER_EEVEE_NEXT",
        EeveeShort => "EEVEE",
        Workbench => "BLENDER_WORKBENCH",
        WorkbenchShort => "WORKBENCH",
    }
}

string_enum! {
    /// Mesh primitives for `add_primitive_objects`.
    PrimitiveType {
        Cube => "cube",
        Sphere => "sphere",
        UvSphere => "uv_sphere",
        Cylinder => "cylinder",
        Cone => "cone",
        Torus => "torus",
        Plane => "plane",
        Monkey => "monkey",
    }
}

string_enum! {
    /// Advanced primitives for `add_advanced_primitives`.
    AdvancedPrimitiveType {
        Grid => "grid",
        Circle => "circle",
        IcoSphere => "ico_sphere",
        Empty => "empty",
        BezierCurve => "bezier_curve",
        NurbsCurve => "nurbs_curve",
        NurbsCircle => "nurbs_circle",
        Metaball => "metaball",
    }
}

string_enum! {
    /// Lighting rigs for `setup_lighting`.
    LightingType {
        ThreePoint => "three_point",
        Studio => "studio",
        Hdri => "hdri",
        Sun => "sun",
        Area => "area",
    }
}

string_enum! {
    /// Material presets for `apply_material`.
    MaterialType {
        Principled => "principled",
        Emission => "emission",
        Glass => "glass",
        Metal => "metal",
        Plastic => "plastic",
        Wood => "wood",
    }
}

string_enum! {
    /// Still image output formats.
    ImageFormat {
        Png => "PNG",
        Jpeg => "JPEG",
        Exr => "EXR",
        Tiff => "TIFF",
    }
}

impl ImageFormat {
    /// File extension Blender writes for this format.
    pub fn extension(self) -> &'static str {
        match self {
            Self::Png => "png",
            Self::Jpeg => "jpg",
            Self::Exr => "exr",
            Self::Tiff => "tif",
        }
    }
}

string_enum! {
    /// Animation output formats (`FRAMES` = PNG image sequence).
    VideoFormat {
        Mp4 => "MP4",
        Avi => "AVI",
        Mov => "MOV",
        Mkv => "MKV",
        Webm => "WEBM",
        Frames => "FRAMES",
    }
}

string_enum! {
    /// Physics simulation types for `setup_physics`.
    PhysicsType {
        RigidBody => "rigid_body",
        SoftBody => "soft_body",
        Cloth => "cloth",
        Fluid => "fluid",
    }
}

string_enum! {
    /// Rigid-body collision shapes.
    CollisionShape {
        Box => "box",
        Sphere => "sphere",
        ConvexHull => "convex_hull",
        Mesh => "mesh",
    }
}

string_enum! {
    /// Keyframe interpolation modes.
    Interpolation {
        Linear => "LINEAR",
        Bezier => "BEZIER",
        Constant => "CONSTANT",
    }
}

string_enum! {
    /// Geometry-node presets implemented by `geometry_nodes.py`.
    GeometryNodeSetup {
        Scatter => "scatter",
        Array => "array",
        Grid => "grid",
        Curve => "curve",
        Spiral => "spiral",
        Volume => "volume",
        WaveDeform => "wave_deform",
        Twist => "twist",
        NoiseDisplace => "noise_displace",
        Extrude => "extrude",
        VoronoiScatter => "voronoi_scatter",
        MeshToPoints => "mesh_to_points",
        CrystalScatter => "crystal_scatter",
        CrystalCluster => "crystal_cluster",
        Custom => "custom",
        ProximityMask => "proximity_mask",
        BlurAttribute => "blur_attribute",
        MapRangeDisplacement => "map_range_displacement",
        EdgeCreaseDetection => "edge_crease_detection",
        OrganicMutation => "organic_mutation",
    }
}

string_enum! {
    /// Formats accepted by `import_model`.
    ImportFormat {
        Fbx => "FBX",
        Obj => "OBJ",
        Gltf => "GLTF",
        Glb => "GLB",
        Stl => "STL",
        Ply => "PLY",
        Usd => "USD",
    }
}

impl ImportFormat {
    /// Infer the format from a file extension (case-insensitive).
    pub fn from_extension(ext: &str) -> Option<Self> {
        match ext.to_ascii_lowercase().as_str() {
            "fbx" => Some(Self::Fbx),
            "obj" => Some(Self::Obj),
            "gltf" => Some(Self::Gltf),
            "glb" => Some(Self::Glb),
            "stl" => Some(Self::Stl),
            "ply" => Some(Self::Ply),
            "usd" | "usda" | "usdc" | "usdz" => Some(Self::Usd),
            _ => None,
        }
    }
}

string_enum! {
    /// Formats accepted by `export_scene`.
    ExportFormat {
        Fbx => "FBX",
        Obj => "OBJ",
        Gltf => "GLTF",
        Glb => "GLB",
        Stl => "STL",
        Ply => "PLY",
        Usd => "USD",
    }
}

impl ExportFormat {
    /// File extension used for the exported file.
    pub fn extension(self) -> &'static str {
        match self {
            Self::Fbx => "fbx",
            Self::Obj => "obj",
            Self::Gltf => "gltf",
            Self::Glb => "glb",
            Self::Stl => "stl",
            Self::Ply => "ply",
            Self::Usd => "usd",
        }
    }
}

string_enum! {
    /// Mesh modifiers for `add_modifier`.
    ModifierType {
        Subsurf => "SUBSURF",
        Array => "ARRAY",
        Mirror => "MIRROR",
        Solidify => "SOLIDIFY",
        Bevel => "BEVEL",
        Decimate => "DECIMATE",
        Remesh => "REMESH",
        Smooth => "SMOOTH",
        Wave => "WAVE",
        Displace => "DISPLACE",
    }
}

string_enum! {
    /// Camera tracking constraints.
    TrackType {
        TrackTo => "TRACK_TO",
        DampedTrack => "DAMPED_TRACK",
        LockedTrack => "LOCKED_TRACK",
    }
}

string_enum! {
    /// Shader textures for `add_texture` (`MUSGRAVE` maps to Noise on 4.1+).
    TextureType {
        Image => "IMAGE",
        Noise => "NOISE",
        Voronoi => "VORONOI",
        Musgrave => "MUSGRAVE",
        Wave => "WAVE",
        Magic => "MAGIC",
        Brick => "BRICK",
        Checker => "CHECKER",
        Gradient => "GRADIENT",
    }
}

string_enum! {
    /// UV projection methods.
    ProjectionType {
        SmartProject => "SMART_PROJECT",
        CubeProject => "CUBE_PROJECT",
        CylinderProject => "CYLINDER_PROJECT",
        SphereProject => "SPHERE_PROJECT",
        ProjectFromView => "PROJECT_FROM_VIEW",
    }
}

string_enum! {
    /// Compositor presets.
    CompositorSetup {
        Basic => "BASIC",
        Denoising => "DENOISING",
        ColorGrading => "COLOR_GRADING",
        Glare => "GLARE",
        FogGlow => "FOG_GLOW",
        LensDistortion => "LENS_DISTORTION",
        Vignette => "VIGNETTE",
    }
}

string_enum! {
    /// Detail levels for `analyze_scene`.
    AnalysisType {
        Basic => "BASIC",
        Detailed => "DETAILED",
        Performance => "PERFORMANCE",
        Memory => "MEMORY",
    }
}

string_enum! {
    /// Passes for `optimize_scene`.
    OptimizationType {
        MeshCleanup => "MESH_CLEANUP",
        TextureOptimization => "TEXTURE_OPTIMIZATION",
        ModifierApply => "MODIFIER_APPLY",
        InstanceOptimization => "INSTANCE_OPTIMIZATION",
        MaterialCleanup => "MATERIAL_CLEANUP",
    }
}

string_enum! {
    /// World environment presets.
    EnvironmentType {
        Hdri => "HDRI",
        SkyTexture => "SKY_TEXTURE",
        Gradient => "GRADIENT",
        Color => "COLOR",
        Volumetric => "VOLUMETRIC",
    }
}

string_enum! {
    /// Emitter styles for `quick_smoke`.
    SmokeStyle {
        Smoke => "SMOKE",
        Fire => "FIRE",
        Both => "BOTH",
    }
}

string_enum! {
    /// Emitter styles for `add_smoke_simulation`.
    SmokeType {
        Smoke => "smoke",
        Fire => "fire",
        Both => "both",
    }
}

string_enum! {
    /// Particle system kinds.
    ParticleType {
        Emitter => "emitter",
        Hair => "hair",
    }
}

string_enum! {
    /// Strand counts for `quick_fur` (1k / 10k / 100k per object).
    FurDensity {
        Low => "LOW",
        Medium => "MEDIUM",
        High => "HIGH",
    }
}

string_enum! {
    /// Constraint types for `add_constraint`.
    ConstraintType {
        TrackTo => "TRACK_TO",
        CopyLocation => "COPY_LOCATION",
        CopyRotation => "COPY_ROTATION",
        CopyScale => "COPY_SCALE",
        LimitLocation => "LIMIT_LOCATION",
        LimitRotation => "LIMIT_ROTATION",
        LimitScale => "LIMIT_SCALE",
        FollowPath => "FOLLOW_PATH",
        DampedTrack => "DAMPED_TRACK",
        Floor => "FLOOR",
        ChildOf => "CHILD_OF",
    }
}

string_enum! {
    /// Horizontal text alignment.
    AlignX {
        Center => "CENTER",
        Left => "LEFT",
        Right => "RIGHT",
        Justify => "JUSTIFY",
        Flush => "FLUSH",
    }
}

string_enum! {
    /// Vertical text alignment.
    AlignY {
        Top => "TOP",
        Center => "CENTER",
        Bottom => "BOTTOM",
    }
}

string_enum! {
    /// Parenting modes for `parent_objects`.
    ParentType {
        Object => "OBJECT",
        Armature => "ARMATURE",
        Bone => "BONE",
    }
}

string_enum! {
    /// Spline types for `create_curve`.
    CurveType {
        Bezier => "BEZIER",
        Nurbs => "NURBS",
        Poly => "POLY",
    }
}

/// A tracked asynchronous Blender operation (render, bake, ...).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    /// Unique job identifier (also the status-file name).
    pub id: Uuid,
    /// Tool that created the job, e.g. `render_image`.
    pub job_type: String,
    /// Current lifecycle state.
    pub status: JobStatus,
    /// Progress percentage, 0-100.
    pub progress: u8,
    /// Latest human-readable progress message.
    pub message: String,
    /// Project file the job operates on, if any.
    pub project: Option<String>,
    /// When the job was queued.
    pub created_at: DateTime<Utc>,
    /// Last state/progress change.
    pub updated_at: Option<DateTime<Utc>>,
    /// When Blender actually started (after waiting for a free slot).
    pub started_at: Option<DateTime<Utc>>,
    /// When the job reached a terminal state.
    pub finished_at: Option<DateTime<Utc>>,
    /// Script result for completed jobs.
    pub result: Option<serde_json::Value>,
    /// Main output file or directory.
    pub output_path: Option<String>,
    /// Failure reason for failed jobs.
    pub error: Option<String>,
}

impl Job {
    /// A new queued job of the given type.
    pub fn new(job_type: &str) -> Self {
        Self {
            id: Uuid::new_v4(),
            job_type: job_type.to_string(),
            status: JobStatus::Queued,
            progress: 0,
            message: "Waiting for a free Blender slot".to_string(),
            project: None,
            created_at: Utc::now(),
            updated_at: None,
            started_at: None,
            finished_at: None,
            result: None,
            output_path: None,
            error: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn string_enum_parses_case_insensitively() {
        assert_eq!("CUBE".parse::<PrimitiveType>(), Ok(PrimitiveType::Cube));
        assert_eq!("cube".parse::<PrimitiveType>(), Ok(PrimitiveType::Cube));
        assert_eq!("mp4".parse::<VideoFormat>(), Ok(VideoFormat::Mp4));
        assert_eq!(PrimitiveType::Cube.as_str(), "cube");
    }

    #[test]
    fn string_enum_rejects_unknown_values_with_the_allowed_list() {
        let err = "blob".parse::<PrimitiveType>().unwrap_err();
        assert!(err.contains("blob"));
        assert!(err.contains("monkey"));
    }

    #[test]
    fn string_enum_serde_round_trip_uses_canonical_spelling() {
        let parsed: ModifierType = serde_json::from_str("\"subsurf\"").unwrap();
        assert_eq!(parsed, ModifierType::Subsurf);
        assert_eq!(serde_json::to_string(&parsed).unwrap(), "\"SUBSURF\"");
        assert!(serde_json::from_str::<ModifierType>("\"NOPE\"").is_err());
        assert!(serde_json::from_str::<ModifierType>("3").is_err());
    }

    #[test]
    fn all_lists_are_unique_and_round_trip() {
        fn check<T: std::str::FromStr + Copy>(all: &[&str], as_str: fn(T) -> &'static str) {
            let mut seen = std::collections::HashSet::new();
            for value in all {
                assert!(seen.insert(value.to_ascii_lowercase()), "duplicate {value}");
                let parsed = value.parse::<T>().ok().expect("ALL value must parse");
                assert_eq!(as_str(parsed), *value);
            }
        }
        check::<ProjectTemplate>(ProjectTemplate::ALL, ProjectTemplate::as_str);
        check::<GeometryNodeSetup>(GeometryNodeSetup::ALL, GeometryNodeSetup::as_str);
        check::<ConstraintType>(ConstraintType::ALL, ConstraintType::as_str);
        check::<TextureType>(TextureType::ALL, TextureType::as_str);
        check::<JobStatus>(JobStatus::ALL, JobStatus::as_str);
    }

    #[test]
    fn job_status_terminal_states() {
        assert!(!JobStatus::Queued.is_terminal());
        assert!(!JobStatus::Running.is_terminal());
        assert!(JobStatus::Completed.is_terminal());
        assert!(JobStatus::Failed.is_terminal());
        assert!(JobStatus::Cancelled.is_terminal());
        assert_eq!(JobStatus::Cancelled.to_string(), "CANCELLED");
    }

    #[test]
    fn import_format_from_extension() {
        assert_eq!(ImportFormat::from_extension("FBX"), Some(ImportFormat::Fbx));
        assert_eq!(
            ImportFormat::from_extension("usdz"),
            Some(ImportFormat::Usd)
        );
        assert_eq!(ImportFormat::from_extension("blend"), None);
    }

    #[test]
    fn format_extensions() {
        assert_eq!(ImageFormat::Jpeg.extension(), "jpg");
        assert_eq!(ImageFormat::Exr.extension(), "exr");
        assert_eq!(ExportFormat::Glb.extension(), "glb");
    }

    #[test]
    fn new_job_is_queued() {
        let job = Job::new("render_image");
        assert_eq!(job.status, JobStatus::Queued);
        assert_eq!(job.progress, 0);
        assert!(job.result.is_none() && job.error.is_none());
    }
}
