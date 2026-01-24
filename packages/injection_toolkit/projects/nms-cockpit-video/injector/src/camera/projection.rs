//! Projection and MVP computation for cockpit quad placement.
//!
//! The quad is placed at a fixed position in camera-local (view) space,
//! so it stays fixed relative to the cockpit regardless of where the
//! player is looking. The MVP is: Projection * Model.
//!
//! Cockpit quad corners in view space (right-handed, Y-up, -Z forward):
//! ```text
//!   TL(-0.25, 0.15, -0.5)    TR(0.25, 0.15, -0.5)
//!   BL(-0.25, -0.05, -0.5)   BR(0.25, -0.05, -0.5)
//! ```

/// Near clip plane for perspective projection.
const NEAR: f32 = 0.01;
/// Far clip plane for perspective projection.
const FAR: f32 = 100.0;

/// Cockpit quad placement parameters (view space).
/// These define where the video quad appears in the cockpit.
const QUAD_HALF_WIDTH: f32 = 0.25;
const QUAD_CENTER_Y: f32 = 0.05;
const QUAD_HALF_HEIGHT: f32 = 0.10;
const QUAD_DEPTH: f32 = -0.5; // 0.5m in front of camera (-Z is forward)

/// Compute the MVP matrix for the cockpit video quad.
///
/// The model matrix maps the unit quad ([-1,1] x [-1,1] at Z=0) to the
/// cockpit screen position in view space. The projection matrix then
/// projects to Vulkan clip space.
///
/// Returns a column-major 4x4 matrix suitable for push constants.
pub fn compute_cockpit_mvp(fov_deg: f32, aspect: f32) -> [f32; 16] {
    let model = cockpit_model_matrix();
    let projection = perspective_vulkan(fov_deg, aspect, NEAR, FAR);
    mat4_multiply(&projection, &model)
}

/// Build the model matrix that positions the unit quad at cockpit coordinates.
///
/// Maps:
/// - X: [-1,1] → [-QUAD_HALF_WIDTH, QUAD_HALF_WIDTH]
/// - Y: [-1,1] → [QUAD_CENTER_Y + QUAD_HALF_HEIGHT, QUAD_CENTER_Y - QUAD_HALF_HEIGHT]
///   (note: Y=-1 in model space is top in NDC after Vulkan Y-flip,
///   so Y=-1 maps to the higher Y in view space)
/// - Z: 0 → QUAD_DEPTH
fn cockpit_model_matrix() -> [f32; 16] {
    let sx = QUAD_HALF_WIDTH; // 0.25
    let sy = -QUAD_HALF_HEIGHT; // -0.10 (negative because model Y=-1 = top = higher view Y)
    let ty = QUAD_CENTER_Y; // 0.05
    let tz = QUAD_DEPTH; // -0.5

    // Column-major 4x4: scale + translate
    [
        sx, 0.0, 0.0, 0.0, // column 0
        0.0, sy, 0.0, 0.0, // column 1
        0.0, 0.0, 1.0, 0.0, // column 2
        0.0, ty, tz, 1.0, // column 3
    ]
}

/// Build a Vulkan perspective projection matrix.
///
/// Right-handed, Y-down in clip space, depth range [0, 1].
///
/// Parameters:
/// - `fov_deg`: Vertical field of view in degrees
/// - `aspect`: Width / height
/// - `near`: Near clip plane distance (positive)
/// - `far`: Far clip plane distance (positive)
///
/// Returns column-major 4x4 matrix.
fn perspective_vulkan(fov_deg: f32, aspect: f32, near: f32, far: f32) -> [f32; 16] {
    let fov_rad = fov_deg * std::f32::consts::PI / 180.0;
    let f = 1.0 / (fov_rad / 2.0).tan();

    let range_inv = 1.0 / (near - far);

    // Column-major layout
    // P[0][0] = f / aspect
    // P[1][1] = -f  (Vulkan Y-flip: positive Y in view → negative Y in clip)
    // P[2][2] = far / (near - far)  = far * range_inv
    // P[2][3] = -1.0  (perspective divide: w = -z)
    // P[3][2] = (near * far) / (near - far)  = near * far * range_inv
    [
        f / aspect,
        0.0,
        0.0,
        0.0, // column 0
        0.0,
        -f,
        0.0,
        0.0, // column 1
        0.0,
        0.0,
        far * range_inv,
        -1.0, // column 2
        0.0,
        0.0,
        near * far * range_inv,
        0.0, // column 3
    ]
}

/// Multiply two 4x4 matrices (column-major): result = a * b.
fn mat4_multiply(a: &[f32; 16], b: &[f32; 16]) -> [f32; 16] {
    let mut result = [0.0f32; 16];

    for col in 0..4 {
        for row in 0..4 {
            let mut sum = 0.0f32;
            for k in 0..4 {
                // a[row, k] * b[k, col]
                // Column-major: element (row, col) is at index col*4 + row
                sum += a[k * 4 + row] * b[col * 4 + k];
            }
            result[col * 4 + row] = sum;
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_identity_multiply() {
        let identity: [f32; 16] = [
            1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0,
        ];
        let result = mat4_multiply(&identity, &identity);
        for i in 0..16 {
            assert!(
                (result[i] - identity[i]).abs() < 1e-6,
                "Mismatch at index {}: {} vs {}",
                i,
                result[i],
                identity[i]
            );
        }
    }

    #[test]
    fn test_perspective_basic() {
        let proj = perspective_vulkan(90.0, 16.0 / 9.0, 0.01, 100.0);
        // At 90 degree FoV, f = 1/tan(45) = 1.0
        let f = 1.0f32;
        let aspect = 16.0 / 9.0;
        assert!((proj[0] - f / aspect).abs() < 1e-5); // P[0][0]
        assert!((proj[5] - (-f)).abs() < 1e-5); // P[1][1] (Y-flip)
        assert!((proj[11] - (-1.0)).abs() < 1e-5); // P[2][3] (perspective divide)
    }

    #[test]
    fn test_cockpit_mvp_produces_valid_result() {
        let mvp = compute_cockpit_mvp(75.0, 16.0 / 9.0);
        // The result should be finite (no NaN/Inf)
        for (i, &val) in mvp.iter().enumerate() {
            assert!(val.is_finite(), "MVP[{}] is not finite: {}", i, val);
        }
    }

    #[test]
    fn test_quad_center_projects_to_screen_center_area() {
        let mvp = compute_cockpit_mvp(75.0, 16.0 / 9.0);

        // Transform the quad center (0, 0, 0) through MVP
        // clip = MVP * (0, 0, 0, 1)
        // clip.x = mvp[12], clip.y = mvp[13], clip.z = mvp[14], clip.w = mvp[15]
        let clip_x = mvp[12];
        let clip_y = mvp[13];
        let clip_w = mvp[15];

        // After perspective divide: ndc = clip / clip.w
        let ndc_x = clip_x / clip_w;
        let ndc_y = clip_y / clip_w;

        // The quad center should be near screen center (within [-0.5, 0.5])
        assert!(ndc_x.abs() < 0.5, "NDC X {} too far from center", ndc_x);
        assert!(ndc_y.abs() < 0.5, "NDC Y {} too far from center", ndc_y);
    }
}
