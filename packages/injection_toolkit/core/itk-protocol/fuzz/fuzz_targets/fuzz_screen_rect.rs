#![no_main]

use libfuzzer_sys::fuzz_target;
use arbitrary::Arbitrary;
use itk_protocol::{encode, decode, MessageType, ScreenRect};

// Fuzz ScreenRect encoding/decoding with structured input
// Uses Arbitrary to generate valid-ish ScreenRects that test edge cases
#[derive(Arbitrary, Debug)]
struct FuzzScreenRect {
    x: f32,
    y: f32,
    width: f32,
    height: f32,
    rotation: f32,
    visible: bool,
}

fuzz_target!(|input: FuzzScreenRect| {
    let rect = ScreenRect {
        x: input.x,
        y: input.y,
        width: input.width,
        height: input.height,
        rotation: input.rotation,
        visible: input.visible,
    };

    // Encoding should never panic
    if let Ok(encoded) = encode(MessageType::ScreenRect, &rect) {
        // If encoding succeeded, decoding the same bytes should work
        let result: Result<(_, ScreenRect), _> = decode(&encoded);

        // If we encoded valid data, we should be able to decode it
        if let Ok((msg_type, decoded)) = result {
            assert_eq!(msg_type, MessageType::ScreenRect);

            // NaN != NaN, so we need special handling
            if !input.x.is_nan() {
                assert_eq!(decoded.x, rect.x);
            }
            if !input.y.is_nan() {
                assert_eq!(decoded.y, rect.y);
            }
            if !input.width.is_nan() {
                assert_eq!(decoded.width, rect.width);
            }
            if !input.height.is_nan() {
                assert_eq!(decoded.height, rect.height);
            }
            assert_eq!(decoded.visible, rect.visible);
        }
    }
});
