@group(0) @binding(0) var t_video: texture_2d<f32>;
@group(0) @binding(1) var s_video: sampler;

@fragment
fn main(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
    return textureSample(t_video, s_video, uv);
}
