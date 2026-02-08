//! Application runner -- manages launched app screens.
//!
//! When the user selects an app from the dashboard and presses Confirm,
//! an `AppRunner` is created. It renders a title bar and scrollable
//! content area, and handles input for navigation and exit.

mod runner;

pub use runner::{AppAction, AppRunner};
