//! Hardware-accelerated video decoding via D3D11VA.
//!
//! This module provides optional GPU-accelerated decoding using Direct3D 11
//! Video Acceleration. When available (e.g., NVIDIA RTX series, Intel, AMD),
//! this offloads video decode from the CPU to the GPU's dedicated decoder.
//!
//! Falls back gracefully to software decoding if hardware acceleration
//! is not available.

use ffmpeg_next::ffi;
use std::ptr;
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::{debug, info, trace, warn};

/// Manages a D3D11VA hardware device context for accelerated decoding.
///
/// When attached to a decoder's `AVCodecContext`, ffmpeg will attempt to
/// use D3D11VA hardware acceleration for supported codecs (H.264, HEVC, AV1, VP9).
pub struct HwDeviceContext {
    device_ctx: *mut ffi::AVBufferRef,
}

// Safety: The AVBufferRef is reference-counted and thread-safe in ffmpeg.
// The D3D11 device it wraps is created with default threading settings.
unsafe impl Send for HwDeviceContext {}

impl HwDeviceContext {
    /// Try to create a D3D11VA hardware device context.
    ///
    /// Returns `None` if D3D11VA is not available on this system.
    /// This is expected on systems without a GPU or with incompatible drivers.
    pub fn create_d3d11va() -> Option<Self> {
        unsafe {
            let mut device_ctx: *mut ffi::AVBufferRef = ptr::null_mut();
            let ret = ffi::av_hwdevice_ctx_create(
                &mut device_ctx,
                ffi::AVHWDeviceType::AV_HWDEVICE_TYPE_D3D11VA,
                ptr::null(),     // Use default device
                ptr::null_mut(), // No options
                0,               // No flags
            );

            if ret < 0 || device_ctx.is_null() {
                debug!(error_code = ret, "D3D11VA device context creation failed");
                return None;
            }

            info!("D3D11VA hardware device context created");
            Some(Self { device_ctx })
        }
    }

    /// Create a new buffer reference to the device context.
    ///
    /// The returned pointer is a new reference that the caller owns.
    /// It should be assigned to `AVCodecContext.hw_device_ctx`.
    ///
    /// # Safety
    /// The caller must ensure `self` contains a valid device context pointer.
    pub unsafe fn new_ref(&self) -> *mut ffi::AVBufferRef {
        ffi::av_buffer_ref(self.device_ctx)
    }

    /// Get the raw pixel format for D3D11 hardware frames.
    pub fn hw_pix_fmt() -> ffi::AVPixelFormat {
        ffi::AVPixelFormat::AV_PIX_FMT_D3D11
    }
}

impl Drop for HwDeviceContext {
    fn drop(&mut self) {
        unsafe {
            if !self.device_ctx.is_null() {
                ffi::av_buffer_unref(&mut self.device_ctx);
            }
        }
    }
}

/// Transfer a hardware frame to a software frame.
///
/// When the decoder outputs a frame in D3D11 format (GPU memory),
/// this function copies it to system memory (typically NV12 format).
///
/// Returns `true` if transfer was performed, `false` if the frame
/// was already in software format.
///
/// # Safety
/// The `frame` pointer must be a valid, non-null AVFrame from the decoder.
/// After this call, if transfer occurred, `frame` contains the software data.
pub unsafe fn transfer_hw_frame_if_needed(frame: *mut ffi::AVFrame) -> bool {
    if frame.is_null() {
        return false;
    }

    let format = (*frame).format;
    let hw_fmt = HwDeviceContext::hw_pix_fmt() as i32;

    if format != hw_fmt {
        // Frame is already in software format, nothing to do
        return false;
    }

    // Allocate a software frame to receive the transfer
    let sw_frame = ffi::av_frame_alloc();
    if sw_frame.is_null() {
        warn!("Failed to allocate software frame for hw transfer");
        return false;
    }

    // Transfer from GPU to CPU memory
    let ret = ffi::av_hwframe_transfer_data(sw_frame, frame, 0);
    if ret < 0 {
        warn!(
            error_code = ret,
            "Failed to transfer hardware frame to software"
        );
        ffi::av_frame_free(&mut (sw_frame as *mut _));
        return false;
    }

    // Copy metadata (pts, etc.) from the hw frame
    (*sw_frame).pts = (*frame).pts;
    (*sw_frame).pkt_dts = (*frame).pkt_dts;
    (*sw_frame).duration = (*frame).duration;
    (*sw_frame).best_effort_timestamp = (*frame).best_effort_timestamp;

    // Move the software frame data into the original frame
    ffi::av_frame_unref(frame);
    ffi::av_frame_move_ref(frame, sw_frame);
    ffi::av_frame_free(&mut (sw_frame as *mut _));

    static FIRST_TRANSFER: AtomicBool = AtomicBool::new(true);
    if FIRST_TRANSFER.swap(false, Ordering::Relaxed) {
        info!("First hardware frame transferred to software successfully");
    } else {
        trace!("Transferred hardware frame to software");
    }
    true
}
