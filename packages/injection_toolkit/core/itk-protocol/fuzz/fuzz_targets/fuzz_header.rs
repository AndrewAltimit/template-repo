#![no_main]

use libfuzzer_sys::fuzz_target;
use itk_protocol::Header;

// Fuzz the header parser with arbitrary bytes
// Goal: Ensure the parser never panics on malformed input
fuzz_target!(|data: &[u8]| {
    // This should never panic, only return Ok or Err
    let _ = Header::from_bytes(data);
});
