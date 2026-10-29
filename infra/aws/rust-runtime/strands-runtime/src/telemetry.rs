//! OpenTelemetry tracing integration.

use std::sync::OnceLock;

use opentelemetry::trace::TracerProvider;
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::trace::SdkTracerProvider;
use opentelemetry_sdk::Resource;
use strands_core::{Result, StrandsError};
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

use crate::config::RuntimeConfig;

/// The installed tracer provider, kept so [`shutdown`] can flush it.
static TRACER_PROVIDER: OnceLock<SdkTracerProvider> = OnceLock::new();

/// Initialize telemetry with the given configuration.
pub fn init(config: &RuntimeConfig) -> Result<()> {
    // Build the base subscriber with env filter
    let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));

    let fmt_layer = tracing_subscriber::fmt::layer()
        .with_target(true)
        .with_thread_ids(true)
        .with_file(true)
        .with_line_number(true);

    // Check if OTLP endpoint is configured
    if let Some(endpoint) = &config.otel_endpoint {
        info!(endpoint = %endpoint, "Initializing OpenTelemetry");

        // Create OTLP exporter
        let exporter = opentelemetry_otlp::SpanExporter::builder()
            .with_tonic()
            .with_endpoint(endpoint)
            .build()
            .map_err(|e| StrandsError::config(format!("Failed to create OTLP exporter: {}", e)))?;

        // Create resource with service name
        let resource = Resource::builder()
            .with_service_name(config.service_name.clone())
            .build();

        // Create tracer provider (the batch processor runs on its own thread)
        let provider = SdkTracerProvider::builder()
            .with_batch_exporter(exporter)
            .with_resource(resource)
            .build();

        // Get tracer and create layer
        let tracer = provider.tracer(config.service_name.clone());
        let otel_layer = tracing_opentelemetry::layer().with_tracer(tracer);
        // A second `init` keeps the first provider; it is the one in use.
        let _ = TRACER_PROVIDER.set(provider);

        // Initialize subscriber with OTLP
        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer)
            .with(otel_layer)
            .init();
    } else {
        // Initialize subscriber without OTLP
        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer)
            .init();
    }

    Ok(())
}

/// Shutdown telemetry gracefully, flushing any buffered spans.
pub fn shutdown() {
    if let Some(provider) = TRACER_PROVIDER.get() {
        if let Err(e) = provider.shutdown() {
            eprintln!("OpenTelemetry shutdown failed: {e}");
        }
    }
}
