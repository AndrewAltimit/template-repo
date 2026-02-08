//! PSP hardware and SDK constants.

/// PSP screen width in pixels
pub const SCREEN_WIDTH: u32 = 480;
/// PSP screen height in pixels
pub const SCREEN_HEIGHT: u32 = 272;
/// The screen buffer width is padded from 480 pixels to a power of 2 (512)
pub const BUF_WIDTH: u32 = 512;

/// VRAM buffer width (same as BUF_WIDTH, used by the display subsystem)
pub const VRAM_BUFFER_WIDTH: u32 = 512;
/// Base address with cache-bypass bit set for uncached VRAM access
pub const VRAM_BASE_UNCACHED: u32 = 0x4000_0000;

/// Default thread priority used by the module! macro and enable_home_button
pub const DEFAULT_THREAD_PRIORITY: i32 = 32;
/// Default main thread stack size (256 KB)
pub const DEFAULT_MAIN_STACK_SIZE: i32 = 256 * 1024;
/// Default exit callback thread stack size (4 KB)
pub const DEFAULT_EXIT_STACK_SIZE: i32 = 0x1000;

/// NID for module_start export
pub const NID_MODULE_START: u32 = 0xd632_acdb;
/// NID for SceModuleInfo export
pub const NID_MODULE_INFO: u32 = 0xf01d_73a7;
