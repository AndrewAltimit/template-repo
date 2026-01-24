//! Build script: compile WGSL shaders to SPIR-V using naga.

use naga::back::spv;
use naga::valid::{Capabilities, ValidationFlags, Validator};
use std::fs;
use std::path::Path;

fn main() {
    println!("cargo:rerun-if-changed=shaders/");

    let out_dir = std::env::var("OUT_DIR").unwrap();

    compile_wgsl(
        "shaders/quad.vert.wgsl",
        &format!("{}/quad.vert.spv", out_dir),
        naga::ShaderStage::Vertex,
    );

    compile_wgsl(
        "shaders/quad.frag.wgsl",
        &format!("{}/quad.frag.spv", out_dir),
        naga::ShaderStage::Fragment,
    );
}

fn compile_wgsl(input: &str, output: &str, stage: naga::ShaderStage) {
    let source =
        fs::read_to_string(input).unwrap_or_else(|e| panic!("Failed to read {}: {}", input, e));

    // Parse WGSL
    let module = naga::front::wgsl::parse_str(&source)
        .unwrap_or_else(|e| panic!("Failed to parse {}: {}", input, e));

    // Validate
    let mut validator = Validator::new(ValidationFlags::all(), Capabilities::all());
    let info = validator
        .validate(&module)
        .unwrap_or_else(|e| panic!("Validation failed for {}: {:?}", input, e));

    // Generate SPIR-V
    let options = spv::Options {
        lang_version: (1, 0),
        flags: spv::WriterFlags::empty(),
        ..Default::default()
    };

    let pipeline_options = spv::PipelineOptions {
        shader_stage: stage,
        entry_point: "main".to_string(),
    };

    let spv = spv::write_vec(&module, &info, &options, Some(&pipeline_options))
        .unwrap_or_else(|e| panic!("SPIR-V generation failed for {}: {}", input, e));

    // Write as raw bytes (u32 words -> u8 bytes)
    let bytes: Vec<u8> = spv.iter().flat_map(|word| word.to_le_bytes()).collect();
    let out_path = Path::new(output);
    fs::write(out_path, &bytes).unwrap_or_else(|e| panic!("Failed to write {}: {}", output, e));

    println!(
        "cargo:warning=Compiled {} -> {} ({} bytes)",
        input,
        output,
        bytes.len()
    );
}
