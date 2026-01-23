#version 450

layout(location = 0) in vec2 fragUV;

layout(location = 0) out vec4 outColor;

// Phase 4 will add: layout(set = 0, binding = 0) uniform sampler2D videoTexture;

void main() {
    // Phase 2: solid green with slight transparency for visibility testing
    outColor = vec4(0.0, 0.8, 0.2, 0.85);

    // Phase 4: outColor = texture(videoTexture, fragUV);
}
