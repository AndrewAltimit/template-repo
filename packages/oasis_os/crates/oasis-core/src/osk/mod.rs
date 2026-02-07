//! Software on-screen keyboard for platforms without physical keyboards.
//!
//! Renders a grid of characters as SDI objects and handles cursor navigation
//! to select characters. Used on PSP and any headless/touchscreen platform.

mod keyboard;

pub use keyboard::{OskConfig, OskMode, OskState};

#[cfg(test)]
mod tests;
