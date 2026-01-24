//! Quad geometry for the video overlay.

use ash::vk;

/// Vertex with 3D position and 2D UV coordinates.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct Vertex {
    pub pos: [f32; 3],
    pub uv: [f32; 2],
}

impl Vertex {
    /// Vertex input binding description (per-vertex, stride = 20 bytes).
    pub fn binding_description() -> vk::VertexInputBindingDescription {
        vk::VertexInputBindingDescription {
            binding: 0,
            stride: std::mem::size_of::<Self>() as u32,
            input_rate: vk::VertexInputRate::VERTEX,
        }
    }

    /// Vertex input attribute descriptions (position at location 0, uv at location 1).
    pub fn attribute_descriptions() -> [vk::VertexInputAttributeDescription; 2] {
        [
            // location 0: vec3 position
            vk::VertexInputAttributeDescription {
                location: 0,
                binding: 0,
                format: vk::Format::R32G32B32_SFLOAT,
                offset: 0,
            },
            // location 1: vec2 uv
            vk::VertexInputAttributeDescription {
                location: 1,
                binding: 0,
                format: vk::Format::R32G32_SFLOAT,
                offset: 12, // after vec3 (3 * 4 bytes)
            },
        ]
    }
}

/// Unit quad vertices (2 triangles, CCW winding).
/// Spans [-1, 1] in X and Y at Z=0, with UVs [0,1].
/// In Phase 3, the MVP push constant will transform this to cockpit screen position.
pub const QUAD_VERTICES: [Vertex; 6] = [
    // Triangle 1 (top-left, bottom-left, bottom-right)
    Vertex {
        pos: [-1.0, -1.0, 0.0],
        uv: [0.0, 0.0],
    }, // TL
    Vertex {
        pos: [-1.0, 1.0, 0.0],
        uv: [0.0, 1.0],
    }, // BL
    Vertex {
        pos: [1.0, 1.0, 0.0],
        uv: [1.0, 1.0],
    }, // BR
    // Triangle 2 (top-left, bottom-right, top-right)
    Vertex {
        pos: [-1.0, -1.0, 0.0],
        uv: [0.0, 0.0],
    }, // TL
    Vertex {
        pos: [1.0, 1.0, 0.0],
        uv: [1.0, 1.0],
    }, // BR
    Vertex {
        pos: [1.0, -1.0, 0.0],
        uv: [1.0, 0.0],
    }, // TR
];

/// Size in bytes of the quad vertex data.
pub const QUAD_VERTICES_SIZE: u64 = std::mem::size_of::<[Vertex; 6]>() as u64;
