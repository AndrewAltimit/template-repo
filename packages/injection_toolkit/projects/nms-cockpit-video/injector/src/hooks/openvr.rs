//! OpenVR compositor hook for VR rendering.
//!
//! Hooks IVRCompositor::Submit to render the video quad on each eye's
//! texture before it's submitted to the headset.
//!
//! Vtable layout (IVRCompositor_028, Windows x64 MSVC):
//! ```text
//! [0] SetTrackingSpace
//! [1] GetTrackingSpace
//! [2] WaitGetPoses
//! [3] GetLastPoses
//! [4] GetLastPoseForTrackedDeviceIndex
//! [5] Submit  ← hooked
//! ```

use crate::log::vlog;
use ash::vk::Handle;
use std::ffi::{c_void, CString};
use std::sync::atomic::{AtomicBool, AtomicPtr, Ordering};
use windows::Win32::System::LibraryLoader::{GetModuleHandleA, GetProcAddress};
use windows::Win32::System::Memory::{VirtualProtect, PAGE_PROTECTION_FLAGS, PAGE_READWRITE};

/// Whether VR hooks are active.
static VR_ACTIVE: AtomicBool = AtomicBool::new(false);

/// Original Submit function pointer (saved before hook).
static ORIGINAL_SUBMIT: AtomicPtr<c_void> = AtomicPtr::new(std::ptr::null_mut());

/// The vtable slot address (for unhooking).
static VTABLE_SLOT: AtomicPtr<*const c_void> = AtomicPtr::new(std::ptr::null_mut());

// --- OpenVR type definitions ---

/// OpenVR eye enum.
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq)]
#[allow(dead_code)]
pub enum EVREye {
    Left = 0,
    Right = 1,
}

/// OpenVR texture type enum.
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq)]
#[allow(dead_code)]
enum ETextureType {
    DirectX = 0,
    OpenGL = 1,
    Vulkan = 3,
}

/// OpenVR compositor error enum.
#[repr(i32)]
#[derive(Clone, Copy, Debug)]
#[allow(dead_code)]
pub enum EVRCompositorError {
    None = 0,
    RequestFailed = 1,
    IncompatibleVersion = 100,
    DoNotHaveFocus = 101,
    InvalidTexture = 102,
    IsNotSceneApplication = 103,
    TextureIsOnWrongDevice = 104,
    TextureUsesUnsupportedFormat = 105,
    SharedTexturesNotSupported = 106,
    IndexOutOfRange = 107,
    AlreadySubmitted = 108,
    InvalidBounds = 109,
    AlreadySet = 110,
}

/// OpenVR Texture_t struct.
#[repr(C)]
#[derive(Clone, Copy)]
struct Texture_t {
    handle: *const c_void,
    e_type: i32,
    e_color_space: i32,
}

/// OpenVR VRTextureBounds_t struct.
#[repr(C)]
#[derive(Clone, Copy)]
#[allow(dead_code)]
struct VRTextureBounds_t {
    u_min: f32,
    v_min: f32,
    u_max: f32,
    v_max: f32,
}

/// OpenVR submit flags.
#[repr(i32)]
#[derive(Clone, Copy)]
#[allow(dead_code)]
enum EVRSubmitFlags {
    Default = 0,
}

/// Vulkan texture data passed through Texture_t.handle for Vulkan textures.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct VRVulkanTextureData_t {
    pub image: u64,             // VkImage (uint64_t handle)
    pub device: *const c_void,  // VkDevice
    pub physical_device: *const c_void, // VkPhysicalDevice
    pub instance: *const c_void, // VkInstance
    pub queue: *const c_void,   // VkQueue
    pub queue_family_index: u32,
    pub width: u32,
    pub height: u32,
    pub format: u32, // VkFormat
    pub sample_count: u32,
}

/// IVRCompositor::Submit function signature.
type FnSubmit = unsafe extern "system" fn(
    this: *const c_void,
    eye: EVREye,
    texture: *const Texture_t,
    bounds: *const VRTextureBounds_t,
    flags: i32,
) -> EVRCompositorError;

/// VR_GetGenericInterface function signature.
type FnGetGenericInterface =
    unsafe extern "system" fn(interface_version: *const u8, error: *mut i32) -> *const c_void;

/// Submit vtable index in IVRCompositor_028.
const SUBMIT_VTABLE_INDEX: usize = 5;

/// Frame counter for VR.
static VR_FRAME_COUNT: std::sync::atomic::AtomicU64 =
    std::sync::atomic::AtomicU64::new(0);

// --- Public API ---

/// Try to install OpenVR hooks.
///
/// Returns Ok(true) if VR is active and hooks were installed,
/// Ok(false) if VR is not active (openvr_api.dll not loaded),
/// Err if VR is active but hooking failed.
///
/// # Safety
/// Must be called after Vulkan hooks are installed.
pub unsafe fn try_install() -> Result<bool, String> {
    // Check if openvr_api.dll is loaded
    let openvr_module = {
        let name = CString::new("openvr_api.dll").unwrap();
        GetModuleHandleA(windows::core::PCSTR(name.as_ptr() as *const _))
    };

    let openvr_module = match openvr_module {
        Ok(h) => h,
        Err(_) => {
            vlog!("openvr_api.dll not loaded - VR not active");
            return Ok(false);
        }
    };

    vlog!("openvr_api.dll found - attempting VR hook");

    // Get VR_GetGenericInterface
    let proc_name = CString::new("VR_GetGenericInterface").unwrap();
    let get_interface_addr =
        GetProcAddress(openvr_module, windows::core::PCSTR(proc_name.as_ptr() as *const _));

    let get_interface: FnGetGenericInterface = match get_interface_addr {
        Some(f) => std::mem::transmute(f),
        None => return Err("VR_GetGenericInterface not found in openvr_api.dll".into()),
    };

    // Get IVRCompositor
    let version = b"IVRCompositor_028\0";
    let mut error: i32 = 0;
    let compositor = get_interface(version.as_ptr(), &mut error);

    if compositor.is_null() || error != 0 {
        return Err(format!(
            "Failed to get IVRCompositor_028: error={}",
            error
        ));
    }

    vlog!("IVRCompositor_028 at {:p}", compositor);

    // Read vtable (first pointer in the object)
    let vtable = *(compositor as *const *const *const c_void);
    let submit_slot = vtable.add(SUBMIT_VTABLE_INDEX) as *mut *const c_void;

    vlog!(
        "Submit vtable slot at {:p}, current value {:p}",
        submit_slot,
        *submit_slot
    );

    // Save original function pointer
    let original = *submit_slot;
    ORIGINAL_SUBMIT.store(original as *mut c_void, Ordering::Release);
    VTABLE_SLOT.store(submit_slot as *mut *const c_void, Ordering::Release);

    // Make vtable writable, swap pointer, restore protection
    let mut old_protect = PAGE_PROTECTION_FLAGS(0);
    let slot_size = std::mem::size_of::<*const c_void>();

    let protect_result = VirtualProtect(
        submit_slot as *const c_void,
        slot_size,
        PAGE_READWRITE,
        &mut old_protect,
    );

    if protect_result.is_err() {
        return Err("VirtualProtect failed on vtable".into());
    }

    // Write our hook function
    *submit_slot = hooked_submit as *const c_void;

    // Restore protection
    let mut dummy = PAGE_PROTECTION_FLAGS(0);
    let _ = VirtualProtect(submit_slot as *const c_void, slot_size, old_protect, &mut dummy);

    VR_ACTIVE.store(true, Ordering::Release);
    vlog!("IVRCompositor::Submit hooked successfully");

    Ok(true)
}

/// Remove VR hooks.
///
/// # Safety
/// Must be called during DLL detach.
pub unsafe fn remove() {
    if !VR_ACTIVE.load(Ordering::Acquire) {
        return;
    }

    let slot = VTABLE_SLOT.load(Ordering::Acquire);
    let original = ORIGINAL_SUBMIT.load(Ordering::Acquire);

    if !slot.is_null() && !original.is_null() {
        let slot = slot as *mut *const c_void;

        let mut old_protect = PAGE_PROTECTION_FLAGS(0);
        let slot_size = std::mem::size_of::<*const c_void>();

        let protect_result = VirtualProtect(
            slot as *const c_void,
            slot_size,
            PAGE_READWRITE,
            &mut old_protect,
        );

        if protect_result.is_ok() {
            *slot = original as *const c_void;
            let mut dummy = PAGE_PROTECTION_FLAGS(0);
            let _ = VirtualProtect(slot as *const c_void, slot_size, old_protect, &mut dummy);
            vlog!("IVRCompositor::Submit hook removed");
        }
    }

    VR_ACTIVE.store(false, Ordering::Release);
}

/// Check if VR is currently active.
#[allow(dead_code)]
pub fn is_active() -> bool {
    VR_ACTIVE.load(Ordering::Relaxed)
}

// --- Hook implementation ---

/// Hooked IVRCompositor::Submit.
///
/// Renders the video quad to the eye texture before calling the original Submit.
unsafe extern "system" fn hooked_submit(
    this: *const c_void,
    eye: EVREye,
    texture: *const Texture_t,
    bounds: *const VRTextureBounds_t,
    flags: i32,
) -> EVRCompositorError {
    let frame = VR_FRAME_COUNT.fetch_add(1, Ordering::Relaxed);

    // Try to render our overlay on the VR texture
    if !texture.is_null() {
        let tex = &*texture;

        // Only process Vulkan textures
        if tex.e_type == ETextureType::Vulkan as i32 && !tex.handle.is_null() {
            let vk_data = &*(tex.handle as *const VRVulkanTextureData_t);

            if frame % 600 == 0 {
                vlog!(
                    "VR Submit: eye={:?} {}x{} format={} image=0x{:X}",
                    eye,
                    vk_data.width,
                    vk_data.height,
                    vk_data.format,
                    vk_data.image
                );
            }

            render_to_vr_eye(eye, vk_data, frame);
        }
    }

    // Call original Submit
    let original: FnSubmit =
        std::mem::transmute(ORIGINAL_SUBMIT.load(Ordering::Acquire));
    original(this, eye, texture, bounds, flags)
}

/// Render the video quad to a VR eye texture.
unsafe fn render_to_vr_eye(eye: EVREye, vk_data: &VRVulkanTextureData_t, frame: u64) {
    use super::vulkan::{get_renderer, get_shmem_frame, get_mvp};
    use ash::vk;

    // Get the renderer (shared with desktop rendering)
    let renderer = match get_renderer() {
        Some(r) => r,
        None => return,
    };

    if let Ok(renderer) = renderer.lock() {
        // Get the current MVP and frame data
        let mvp = get_mvp(frame);
        let new_frame = get_shmem_frame(frame);

        let vr_image = vk::Image::from_raw(vk_data.image);
        let extent = vk::Extent2D {
            width: vk_data.width,
            height: vk_data.height,
        };

        // Render to the VR eye image
        if let Err(e) = renderer.render_to_vr_image(
            vr_image,
            extent,
            &mvp,
            new_frame.as_deref(),
        ) {
            if frame % 600 == 0 {
                vlog!("VR render error (eye={:?}): {}", eye, e);
            }
        }
    }
}
