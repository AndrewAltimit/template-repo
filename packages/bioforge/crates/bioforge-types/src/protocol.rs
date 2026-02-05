//! Protocol schema types for experiment definitions.

use serde::{Deserialize, Serialize};

/// A complete experiment protocol loaded from TOML.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Protocol {
    pub name: String,
    pub version: String,
    pub description: String,
    pub steps: Vec<ProtocolStep>,
}

/// A single step in an experiment protocol.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolStep {
    pub id: u32,
    pub name: String,
    pub action: StepAction,
    /// Whether this step requires human confirmation before proceeding.
    pub human_gate: bool,
    /// Optional notes for the operator.
    pub notes: Option<String>,
}

/// The action performed by a protocol step.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum StepAction {
    Dispense {
        target: String,
        volume_ul: f64,
        reagent: String,
        flow_rate: Option<f64>,
    },
    Aspirate {
        source: String,
        volume_ul: f64,
        flow_rate: Option<f64>,
    },
    Mix {
        target: String,
        volume_ul: f64,
        cycles: u32,
        flow_rate: Option<f64>,
    },
    MoveTo {
        x_mm: f64,
        y_mm: f64,
        z_mm: Option<f64>,
    },
    SetTemperature {
        zone: ThermalZone,
        target_c: f64,
        hold_seconds: Option<u64>,
    },
    HeatShock {
        ramp_to_c: f64,
        hold_s: u64,
        return_to_c: f64,
    },
    Incubate {
        zone: ThermalZone,
        target_c: f64,
        duration_hours: f64,
    },
    CaptureImage {
        plate_id: String,
        lighting_mode: LightingMode,
    },
    CountColonies {
        plate_id: String,
        image_id: String,
    },
    Wait {
        seconds: u64,
        reason: String,
    },
    RequestHumanAction {
        description: String,
        timeout_min: u64,
    },
}

/// Thermal zone identifier.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ThermalZone {
    Cold,
    Warm,
}

/// Camera lighting mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum LightingMode {
    White,
    UvBlue,
    DarkField,
}

/// States for the protocol state machine.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ProtocolState {
    Idle,
    ProtocolLoaded,
    MediaPrep,
    MediaReady,
    ReagentsLoaded,
    Transforming,
    TransformationComplete,
    Plating,
    PlatesReady,
    Incubating,
    IncubationComplete,
    Analyzing,
    ExperimentComplete,
}

impl std::fmt::Display for ProtocolState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            Self::Idle => "Idle",
            Self::ProtocolLoaded => "Protocol Loaded",
            Self::MediaPrep => "Media Preparation",
            Self::MediaReady => "Media Ready",
            Self::ReagentsLoaded => "Reagents Loaded",
            Self::Transforming => "Transforming",
            Self::TransformationComplete => "Transformation Complete",
            Self::Plating => "Plating",
            Self::PlatesReady => "Plates Ready",
            Self::Incubating => "Incubating",
            Self::IncubationComplete => "Incubation Complete",
            Self::Analyzing => "Analyzing",
            Self::ExperimentComplete => "Experiment Complete",
        };
        write!(f, "{s}")
    }
}
