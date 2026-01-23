//! Camera state reader for NMS's cGcCameraManager.
//!
//! Reads the camera singleton from NMS process memory to get:
//! - Camera mode (cockpit, on-foot, photo, etc.)
//! - Field of view (degrees)
//! - Aspect ratio
//!
//! Memory layout (NMS 5.x):
//! ```text
//! NMS.exe + 0x56666B0 → pointer to cGcCameraManager singleton
//!   +0x118  Camera mode (u32, cockpit = 0x10)
//!   +0x130  View matrix (4x4 f32, row-major)
//!   +0x1D0  FoV (f32, degrees)
//!   +0x1D4  Aspect ratio (f32)
//! ```

pub mod projection;

use crate::log::vlog;
use std::sync::atomic::{AtomicU64, Ordering};
use windows::Win32::System::LibraryLoader::GetModuleHandleA;

/// RVA offset to the cGcCameraManager singleton pointer.
const CAMERA_MANAGER_RVA: usize = 0x56666B0;

/// Offset to camera mode field.
const OFFSET_CAMERA_MODE: usize = 0x118;

/// Offset to view matrix (4x4 f32, row-major).
const OFFSET_VIEW_MATRIX: usize = 0x130;

/// Offset to FoV in degrees.
const OFFSET_FOV: usize = 0x1D0;

/// Offset to aspect ratio.
const OFFSET_ASPECT: usize = 0x1D4;

/// Camera mode value for cockpit view.
pub const CAMERA_MODE_COCKPIT: u32 = 0x10;

/// Camera state read from NMS memory.
#[derive(Clone, Debug)]
pub struct CameraState {
    /// Camera mode (0x10 = cockpit).
    pub mode: u32,
    /// Vertical field of view in degrees.
    pub fov_deg: f32,
    /// Aspect ratio (width / height).
    pub aspect: f32,
    /// View matrix (4x4, row-major as stored by NMS).
    pub view_matrix: [f32; 16],
}

/// Reader for NMS camera state from process memory.
pub struct CameraReader {
    /// Address of the singleton pointer (NMS.exe base + RVA).
    singleton_ptr_addr: usize,
    /// Frame counter for periodic logging.
    log_counter: AtomicU64,
}

impl CameraReader {
    /// Create a new camera reader.
    ///
    /// This always succeeds if NMS.exe is loaded. The singleton pointer
    /// may be null during loading screens - `read()` handles that gracefully.
    ///
    /// # Safety
    /// NMS.exe must be loaded in the current process.
    pub unsafe fn new() -> Result<Self, String> {
        let base = get_nms_base()?;
        let singleton_ptr_addr = base + CAMERA_MANAGER_RVA;

        vlog!(
            "CameraReader: NMS.exe base=0x{:X} singleton_ptr=0x{:X}",
            base,
            singleton_ptr_addr
        );

        // Check if singleton is already valid (may be null during loading)
        let ptr = *(singleton_ptr_addr as *const usize);
        if ptr != 0 {
            vlog!("CameraReader: singleton at 0x{:X}", ptr);
        } else {
            vlog!("CameraReader: singleton not yet initialized (will poll in read())");
        }

        Ok(Self {
            singleton_ptr_addr,
            log_counter: AtomicU64::new(0),
        })
    }

    /// Read the current camera state from NMS memory.
    ///
    /// Returns `None` if the singleton pointer is null (e.g., during loading screens).
    ///
    /// # Safety
    /// The singleton pointer must point to valid cGcCameraManager memory.
    pub unsafe fn read(&self) -> Option<CameraState> {
        let singleton = *(self.singleton_ptr_addr as *const usize);
        if singleton == 0 {
            return None;
        }

        let mode = *((singleton + OFFSET_CAMERA_MODE) as *const u32);
        let fov_deg = *((singleton + OFFSET_FOV) as *const f32);
        let aspect = *((singleton + OFFSET_ASPECT) as *const f32);

        // Read view matrix (16 contiguous f32s)
        let matrix_ptr = (singleton + OFFSET_VIEW_MATRIX) as *const [f32; 16];
        let view_matrix = *matrix_ptr;

        // Sanity check: FoV should be reasonable (1-179 degrees)
        if fov_deg < 1.0 || fov_deg > 179.0 {
            let count = self.log_counter.fetch_add(1, Ordering::Relaxed);
            if count % 300 == 0 {
                vlog!("CameraReader: suspicious FoV={}, skipping", fov_deg);
            }
            return None;
        }

        // Sanity check: aspect should be reasonable (0.1 - 10.0)
        if aspect < 0.1 || aspect > 10.0 {
            let count = self.log_counter.fetch_add(1, Ordering::Relaxed);
            if count % 300 == 0 {
                vlog!("CameraReader: suspicious aspect={}, skipping", aspect);
            }
            return None;
        }

        let count = self.log_counter.fetch_add(1, Ordering::Relaxed);
        if count % 600 == 0 {
            vlog!(
                "CameraReader: mode=0x{:X} fov={:.1} aspect={:.3}",
                mode,
                fov_deg,
                aspect
            );
        }

        Some(CameraState {
            mode,
            fov_deg,
            aspect,
            view_matrix,
        })
    }

    /// Check if the singleton is currently valid.
    ///
    /// # Safety
    /// Must be called from a thread that can safely read NMS memory.
    pub unsafe fn is_valid(&self) -> bool {
        let singleton = *(self.singleton_ptr_addr as *const usize);
        singleton != 0
    }
}

/// Get the base address of NMS.exe in the current process.
unsafe fn get_nms_base() -> Result<usize, String> {
    // GetModuleHandleA(NULL) returns the base of the main executable
    let handle = GetModuleHandleA(windows::core::PCSTR::null())
        .map_err(|e| format!("GetModuleHandle(NULL) failed: {}", e))?;
    Ok(handle.0 as usize)
}
