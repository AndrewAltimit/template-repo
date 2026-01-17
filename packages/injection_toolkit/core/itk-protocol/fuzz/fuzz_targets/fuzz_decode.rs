#![no_main]

use libfuzzer_sys::fuzz_target;
use itk_protocol::{decode, ScreenRect, StateEvent, StateSnapshot};

// Fuzz the full decode path with arbitrary bytes
// Goal: Ensure decode never panics and handles all malformed input gracefully
fuzz_target!(|data: &[u8]| {
    // Try decoding as various message types
    // All should return Ok or Err, never panic

    let _: Result<(_, ScreenRect), _> = decode(data);
    let _: Result<(_, StateEvent), _> = decode(data);
    let _: Result<(_, StateSnapshot), _> = decode(data);
    let _: Result<(_, ()), _> = decode(data);
});
