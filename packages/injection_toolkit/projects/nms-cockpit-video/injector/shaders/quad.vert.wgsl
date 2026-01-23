struct PushConstants {
    mvp: mat4x4<f32>,
}

var<push_constant> pc: PushConstants;

struct VertexInput {
    @location(0) pos: vec3<f32>,
    @location(1) uv: vec2<f32>,
}

struct VertexOutput {
    @builtin(position) clip_pos: vec4<f32>,
    @location(0) frag_uv: vec2<f32>,
}

@vertex
fn main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.clip_pos = pc.mvp * vec4<f32>(input.pos, 1.0);
    out.frag_uv = input.uv;
    return out;
}
