//! Vulkan function hooks for rendering injection.
//!
//! Hooks Vulkan at two levels:
//! - Loader trampolines (vkCreateInstance, vkCreateDevice) via retour static_detour
//! - ICD-level functions (vkQueuePresentKHR, vkCreateSwapchainKHR) via RawDetour
//!
//! Extension functions (KHR) bypass the loader when obtained via vkGetDeviceProcAddr,
//! so we hook the actual ICD implementation addresses after device creation.

use crate::camera::projection::compute_cockpit_mvp;
use crate::camera::{CameraReader, CAMERA_MODE_COCKPIT};
use crate::log::vlog;
use crate::renderer::VulkanRenderer;
use crate::shmem_reader::ShmemFrameReader;
use ash::vk;
use once_cell::sync::OnceCell;
use retour::{static_detour, RawDetour};
use std::ffi::{c_char, c_void, CString};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Mutex;
use windows::Win32::System::LibraryLoader::{GetModuleHandleA, GetProcAddress};

// --- Type aliases for ICD function pointers ---

type PfnQueuePresent = unsafe extern "system" fn(vk::Queue, *const c_void) -> vk::Result;
type PfnCreateSwapchain = unsafe extern "system" fn(
    vk::Device,
    *const c_void,
    *const c_void,
    *mut vk::SwapchainKHR,
) -> vk::Result;

// --- Captured state ---

/// The VkInstance.
static INSTANCE: OnceCell<vk::Instance> = OnceCell::new();

/// The ash Instance loader (created from vulkan-1.dll exports, no VkInstance needed).
static ASH_INSTANCE: OnceCell<ash::Instance> = OnceCell::new();

/// The VkPhysicalDevice used to create the device.
static PHYSICAL_DEVICE: OnceCell<vk::PhysicalDevice> = OnceCell::new();

/// The VkDevice created by the game.
static DEVICE: OnceCell<vk::Device> = OnceCell::new();

/// The VkQueue used for presentation.
static PRESENT_QUEUE: OnceCell<vk::Queue> = OnceCell::new();

/// Queue family index (captured from device creation).
static QUEUE_FAMILY_INDEX: AtomicU64 = AtomicU64::new(0);

/// Current swapchain handle.
static SWAPCHAIN: OnceCell<vk::SwapchainKHR> = OnceCell::new();

/// Cached ash::Device dispatch table (avoids per-frame function pointer resolution).
static ASH_DEVICE: OnceCell<ash::Device> = OnceCell::new();

/// Cached swapchain extension function table.
static ASH_SWAPCHAIN_FN: OnceCell<ash::khr::swapchain::Device> = OnceCell::new();

/// Cached swapchain images (cleared on swapchain recreation).
static SWAPCHAIN_IMAGES: Mutex<Option<Vec<vk::Image>>> = Mutex::new(None);

/// Swapchain extent (packed: width << 32 | height).
static SWAPCHAIN_EXTENT: AtomicU64 = AtomicU64::new(0);

/// Swapchain format (raw i32).
static SWAPCHAIN_FORMAT: AtomicU64 = AtomicU64::new(0);

/// Frame counter for diagnostics.
static FRAME_COUNT: AtomicU64 = AtomicU64::new(0);

/// The renderer (lazy-initialized on first present, resettable on swapchain recreation).
static RENDERER: Mutex<Option<VulkanRenderer>> = Mutex::new(None);

/// Camera reader (lazy-initialized on first present).
static CAMERA: OnceCell<CameraReader> = OnceCell::new();

/// Shared memory frame reader (retries periodically if daemon isn't running).
pub(super) static SHMEM_READER: OnceCell<Mutex<ShmemFrameReader>> = OnceCell::new();

/// Whether we've already failed to open shmem (avoids log spam).
pub(super) static SHMEM_FAILED: AtomicBool = AtomicBool::new(false);

// --- ICD-level hook state ---

/// Trampoline to call the original ICD vkQueuePresentKHR.
static ICD_PRESENT_TRAMPOLINE: OnceCell<PfnQueuePresent> = OnceCell::new();

/// Trampoline to call the original ICD vkCreateSwapchainKHR.
static ICD_SWAPCHAIN_TRAMPOLINE: OnceCell<PfnCreateSwapchain> = OnceCell::new();

/// Wrapper for RawDetour to make it Send+Sync (detours are set-and-forget).
struct DetourHolder(RawDetour);
unsafe impl Send for DetourHolder {}
unsafe impl Sync for DetourHolder {}

/// Keep RawDetours alive (dropping disables them).
static ICD_PRESENT_DETOUR: OnceCell<DetourHolder> = OnceCell::new();
static ICD_SWAPCHAIN_DETOUR: OnceCell<DetourHolder> = OnceCell::new();

/// Set when ICD-level present hook is active (loader hook skips rendering).
static ICD_PRESENT_ACTIVE: AtomicBool = AtomicBool::new(false);

// --- Hook definitions ---

static_detour! {
    static Hook_vkCreateInstance: unsafe extern "system" fn(
        *const c_void,      // pCreateInfo (VkInstanceCreateInfo*)
        *const c_void,      // pAllocator
        *mut vk::Instance   // pInstance
    ) -> vk::Result;

    static Hook_vkCreateDevice: unsafe extern "system" fn(
        vk::PhysicalDevice,
        *const c_void,      // pCreateInfo (VkDeviceCreateInfo*)
        *const c_void,      // pAllocator
        *mut vk::Device
    ) -> vk::Result;

    static Hook_vkCreateSwapchainKHR: unsafe extern "system" fn(
        vk::Device,
        *const c_void,      // pCreateInfo (VkSwapchainCreateInfoKHR*)
        *const c_void,      // pAllocator
        *mut vk::SwapchainKHR
    ) -> vk::Result;

    static Hook_vkQueuePresentKHR: unsafe extern "system" fn(
        vk::Queue,
        *const c_void       // pPresentInfo (VkPresentInfoKHR*)
    ) -> vk::Result;
}

// --- Hook implementations ---

/// Hooked vkCreateInstance: captures instance for ash loader.
fn hooked_create_instance(
    create_info: *const c_void,
    allocator: *const c_void,
    instance: *mut vk::Instance,
) -> vk::Result {
    vlog!("vkCreateInstance called");

    let result = unsafe { Hook_vkCreateInstance.call(create_info, allocator, instance) };

    if result == vk::Result::SUCCESS {
        let inst = unsafe { *instance };
        let _ = INSTANCE.set(inst);
        vlog!("VkInstance captured: {:?}", inst);

        // Create ash::Instance loader
        unsafe {
            let get_instance_proc_addr = get_instance_proc_addr_fn();
            if let Some(gipa) = get_instance_proc_addr {
                let static_fn = ash::StaticFn {
                    get_instance_proc_addr: gipa,
                };
                let entry = ash::Entry::from_static_fn(static_fn);
                let ash_instance = ash::Instance::load(entry.static_fn(), inst);
                let _ = ASH_INSTANCE.set(ash_instance);
                vlog!("ash::Instance created");
            }
        }
    }

    result
}

/// Hooked vkCreateDevice: captures device and physical device, sets up ICD hooks.
fn hooked_create_device(
    physical_device: vk::PhysicalDevice,
    create_info: *const c_void,
    allocator: *const c_void,
    device: *mut vk::Device,
) -> vk::Result {
    vlog!("vkCreateDevice called");

    // Extract queue family index from create info
    if !create_info.is_null() {
        let info = unsafe { &*(create_info as *const vk::DeviceCreateInfo<'_>) };
        if info.queue_create_info_count > 0 && !info.p_queue_create_infos.is_null() {
            let queue_info = unsafe { &*info.p_queue_create_infos };
            QUEUE_FAMILY_INDEX.store(queue_info.queue_family_index as u64, Ordering::Relaxed);
            vlog!("Queue family index: {}", queue_info.queue_family_index);
        }
    }

    let result =
        unsafe { Hook_vkCreateDevice.call(physical_device, create_info, allocator, device) };

    if result == vk::Result::SUCCESS {
        let dev = unsafe { *device };
        let _ = PHYSICAL_DEVICE.set(physical_device);
        let _ = DEVICE.set(dev);
        vlog!("VkDevice captured: {:?}", dev);

        // If vkCreateInstance was missed (late injection), create ash::Instance
        // using vulkan-1.dll exports directly
        if ASH_INSTANCE.get().is_none() {
            vlog!("vkCreateInstance was missed - creating ash::Instance from loader exports");
            unsafe {
                create_ash_instance_from_exports();
            }
        }

        // Hook vkQueuePresentKHR and vkCreateSwapchainKHR at the ICD level.
        // Extension functions bypass the loader when obtained via vkGetDeviceProcAddr,
        // so we must hook the actual ICD addresses.
        unsafe {
            setup_icd_hooks(dev);
        }

        // Cache the device dispatch table and swapchain extension functions
        // to avoid per-frame function pointer resolution in try_render_overlay.
        if let Some(instance) = ASH_INSTANCE.get() {
            let device_fns = ash::Device::load(instance.fp_v1_0(), dev);
            let swapchain_fn = ash::khr::swapchain::Device::new(instance, &device_fns);
            let _ = ASH_SWAPCHAIN_FN.set(swapchain_fn);
            let _ = ASH_DEVICE.set(device_fns);
            vlog!("ash::Device and swapchain extension cached");
        }
    }

    result
}

/// Hooked vkCreateSwapchainKHR: tracks swapchain properties.
fn hooked_create_swapchain(
    device: vk::Device,
    create_info: *const c_void,
    allocator: *const c_void,
    swapchain: *mut vk::SwapchainKHR,
) -> vk::Result {
    // Destroy existing renderer and invalidate cached images on swapchain recreation
    // so they reinitialize with new swapchain properties (resolution, format, images)
    if let Ok(mut guard) = RENDERER.lock() {
        if guard.is_some() {
            vlog!("Swapchain recreated - destroying old renderer for reinit");
            *guard = None;
        }
    }
    if let Ok(mut images) = SWAPCHAIN_IMAGES.lock() {
        *images = None;
    }

    let result =
        unsafe { Hook_vkCreateSwapchainKHR.call(device, create_info, allocator, swapchain) };

    if result == vk::Result::SUCCESS && !create_info.is_null() {
        let info = unsafe { &*(create_info as *const vk::SwapchainCreateInfoKHR<'_>) };
        let extent = info.image_extent;
        let format = info.image_format;

        SWAPCHAIN_EXTENT.store(
            ((extent.width as u64) << 32) | (extent.height as u64),
            Ordering::Relaxed,
        );
        SWAPCHAIN_FORMAT.store(format.as_raw() as u64, Ordering::Relaxed);

        let sc = unsafe { *swapchain };
        // Store swapchain (first one only for now)
        let _ = SWAPCHAIN.set(sc);

        vlog!(
            "Swapchain created: {}x{} format={:?} handle={:?}",
            extent.width,
            extent.height,
            format,
            sc
        );
    }

    result
}

/// Hooked vkQueuePresentKHR: injection point for rendering.
///
/// When the ICD-level hook is active, this loader-level hook becomes a passthrough
/// to avoid double-rendering (both hooks fire on the same present call).
fn hooked_queue_present(queue: vk::Queue, present_info_ptr: *const c_void) -> vk::Result {
    // Skip rendering if ICD hook handles it (avoids double submissions)
    if !ICD_PRESENT_ACTIVE.load(Ordering::Relaxed) {
        let count = FRAME_COUNT.fetch_add(1, Ordering::Relaxed);

        // Store the present queue on first call
        if PRESENT_QUEUE.get().is_none() {
            let _ = PRESENT_QUEUE.set(queue);
            vlog!("Present queue captured: {:?}", queue);
        }

        // Log every 300 frames (~5 seconds at 60fps)
        if count.is_multiple_of(300) {
            vlog!("vkQueuePresentKHR frame={}", count);
        }

        // Try to render our quad overlay
        if !present_info_ptr.is_null() {
            unsafe {
                try_render_overlay(queue, present_info_ptr, count);
            }
        }
    }

    unsafe { Hook_vkQueuePresentKHR.call(queue, present_info_ptr) }
}

// --- ICD-level hook implementations ---

/// Create ash::Instance from vulkan-1.dll exports (no VkInstance handle needed).
///
/// Provides a custom vkGetInstanceProcAddr that resolves functions directly from
/// vulkan-1.dll's exports via GetProcAddress. The loader's exported trampolines
/// dispatch correctly using the handle's internal dispatch table.
unsafe fn create_ash_instance_from_exports() {
    let static_fn = ash::StaticFn {
        get_instance_proc_addr: loader_get_instance_proc_addr,
    };
    let entry = ash::Entry::from_static_fn(static_fn);
    let ash_instance = ash::Instance::load(entry.static_fn(), vk::Instance::null());
    let _ = ASH_INSTANCE.set(ash_instance);
    vlog!("ash::Instance created from loader exports (late-init)");
}

/// Custom vkGetInstanceProcAddr that resolves functions from vulkan-1.dll exports.
///
/// Ignores the VkInstance parameter and uses GetProcAddress on vulkan-1.dll directly.
/// The loader's exported trampolines use the dispatch table embedded in dispatchable
/// handles (VkDevice, VkPhysicalDevice, VkQueue) to route to the correct ICD.
unsafe extern "system" fn loader_get_instance_proc_addr(
    _instance: vk::Instance,
    p_name: *const c_char,
) -> vk::PFN_vkVoidFunction {
    if p_name.is_null() {
        return None;
    }
    let module = match get_vulkan_module() {
        Ok(m) => m,
        Err(_) => return None,
    };
    GetProcAddress(module, windows::core::PCSTR(p_name as *const u8))
        .map(|f| std::mem::transmute::<_, unsafe extern "system" fn()>(f))
}

/// Set up ICD-level hooks for extension functions that bypass the loader.
///
/// Gets the actual ICD addresses via vkGetDeviceProcAddr and detours them.
unsafe fn setup_icd_hooks(device: vk::Device) {
    let vulkan_module = match get_vulkan_module() {
        Ok(m) => m,
        Err(e) => {
            vlog!("Failed to get vulkan module for ICD hooks: {}", e);
            return;
        },
    };

    // Get vkGetDeviceProcAddr from vulkan-1.dll
    let gdpa_addr = match get_proc(vulkan_module, "vkGetDeviceProcAddr") {
        Ok(addr) => addr,
        Err(e) => {
            vlog!("Failed to get vkGetDeviceProcAddr: {}", e);
            return;
        },
    };
    let gdpa: vk::PFN_vkGetDeviceProcAddr = std::mem::transmute(gdpa_addr);

    // Hook vkQueuePresentKHR at ICD level
    let present_name = CString::new("vkQueuePresentKHR").unwrap();
    let icd_present = (gdpa)(device, present_name.as_ptr());
    if let Some(present_fn) = icd_present {
        let target = present_fn as *const ();
        vlog!("ICD vkQueuePresentKHR at {:p}", target);

        match RawDetour::new(target, icd_hooked_queue_present as *const ()) {
            Ok(detour) => {
                let trampoline: PfnQueuePresent = std::mem::transmute(detour.trampoline());
                match detour.enable() {
                    Ok(()) => {
                        let _ = ICD_PRESENT_TRAMPOLINE.set(trampoline);
                        let _ = ICD_PRESENT_DETOUR.set(DetourHolder(detour));
                        ICD_PRESENT_ACTIVE.store(true, Ordering::Relaxed);
                        vlog!("ICD vkQueuePresentKHR hooked successfully (loader hook disabled)");
                    },
                    Err(e) => vlog!("Failed to enable ICD present hook: {}", e),
                }
            },
            Err(e) => vlog!("Failed to create ICD present detour: {}", e),
        }
    } else {
        vlog!("vkGetDeviceProcAddr returned null for vkQueuePresentKHR");
    }

    // Hook vkCreateSwapchainKHR at ICD level
    let swapchain_name = CString::new("vkCreateSwapchainKHR").unwrap();
    let icd_swapchain = (gdpa)(device, swapchain_name.as_ptr());
    if let Some(swapchain_fn) = icd_swapchain {
        let target = swapchain_fn as *const ();
        vlog!("ICD vkCreateSwapchainKHR at {:p}", target);

        match RawDetour::new(target, icd_hooked_create_swapchain as *const ()) {
            Ok(detour) => {
                let trampoline: PfnCreateSwapchain = std::mem::transmute(detour.trampoline());
                match detour.enable() {
                    Ok(()) => {
                        let _ = ICD_SWAPCHAIN_TRAMPOLINE.set(trampoline);
                        let _ = ICD_SWAPCHAIN_DETOUR.set(DetourHolder(detour));
                        vlog!("ICD vkCreateSwapchainKHR hooked successfully");
                    },
                    Err(e) => vlog!("Failed to enable ICD swapchain hook: {}", e),
                }
            },
            Err(e) => vlog!("Failed to create ICD swapchain detour: {}", e),
        }
    } else {
        vlog!("vkGetDeviceProcAddr returned null for vkCreateSwapchainKHR");
    }
}

/// ICD-level hook for vkQueuePresentKHR (called when NMS presents a frame).
unsafe extern "system" fn icd_hooked_queue_present(
    queue: vk::Queue,
    present_info_ptr: *const c_void,
) -> vk::Result {
    let count = FRAME_COUNT.fetch_add(1, Ordering::Relaxed);

    // Store the present queue on first call
    if PRESENT_QUEUE.get().is_none() {
        let _ = PRESENT_QUEUE.set(queue);
        vlog!("Present queue captured (ICD hook): {:?}", queue);
    }

    // Log every 300 frames (~5 seconds at 60fps)
    if count.is_multiple_of(300) {
        vlog!("vkQueuePresentKHR (ICD) frame={}", count);
    }

    // Try to render our quad overlay
    if !present_info_ptr.is_null() {
        try_render_overlay(queue, present_info_ptr, count);
    }

    // Call the original ICD function
    if let Some(trampoline) = ICD_PRESENT_TRAMPOLINE.get() {
        (trampoline)(queue, present_info_ptr)
    } else {
        vk::Result::SUCCESS
    }
}

/// ICD-level hook for vkCreateSwapchainKHR (captures format/extent).
unsafe extern "system" fn icd_hooked_create_swapchain(
    device: vk::Device,
    create_info: *const c_void,
    allocator: *const c_void,
    swapchain: *mut vk::SwapchainKHR,
) -> vk::Result {
    // Destroy renderer and invalidate cached images before recreation
    // (mirrors the loader-level hook behavior)
    if let Ok(mut guard) = RENDERER.lock() {
        if guard.is_some() {
            vlog!("Swapchain recreated (ICD) - destroying renderer for reinit");
            *guard = None;
        }
    }
    if let Ok(mut images) = SWAPCHAIN_IMAGES.lock() {
        *images = None;
    }

    // Call the original ICD function first
    let result = if let Some(trampoline) = ICD_SWAPCHAIN_TRAMPOLINE.get() {
        (trampoline)(device, create_info, allocator, swapchain)
    } else {
        vk::Result::ERROR_UNKNOWN
    };

    if result == vk::Result::SUCCESS && !create_info.is_null() {
        let info = &*(create_info as *const vk::SwapchainCreateInfoKHR<'_>);
        let extent = info.image_extent;
        let format = info.image_format;

        SWAPCHAIN_EXTENT.store(
            ((extent.width as u64) << 32) | (extent.height as u64),
            Ordering::Relaxed,
        );
        SWAPCHAIN_FORMAT.store(format.as_raw() as u64, Ordering::Relaxed);

        let sc = *swapchain;
        let _ = SWAPCHAIN.set(sc);

        vlog!(
            "Swapchain created (ICD hook): {}x{} format={:?} handle={:?}",
            extent.width,
            extent.height,
            format,
            sc
        );
    }

    result
}

/// Attempt to render the overlay quad.
unsafe fn try_render_overlay(queue: vk::Queue, present_info_ptr: *const c_void, frame: u64) {
    // Skip rendering if overlay is toggled off (F5)
    if !crate::OVERLAY_VISIBLE.load(Ordering::Relaxed) {
        return;
    }

    let present_info = &*(present_info_ptr as *const vk::PresentInfoKHR<'_>);

    // We need at least one swapchain and one image index
    if present_info.swapchain_count == 0 || present_info.p_swapchains.is_null() {
        return;
    }

    let swapchain = *present_info.p_swapchains;
    let image_index = *present_info.p_image_indices;

    // Compute MVP from camera state (or fallback)
    let mvp = compute_frame_mvp(frame);

    // Lock order: RENDERER → SHMEM_READER (must match VR path in openvr.rs to avoid deadlock)
    if let Ok(mut guard) = RENDERER.lock() {
        // Lazy-initialize the renderer (or reinitialize after swapchain recreation)
        if guard.is_none() {
            match init_renderer(queue, swapchain) {
                Ok(renderer) => {
                    *guard = Some(renderer);
                },
                Err(e) => {
                    if frame.is_multiple_of(300) {
                        vlog!("Renderer not ready: {}", e);
                    }
                    return;
                },
            }
        }

        if let Some(renderer) = guard.as_ref() {
            // Poll shared memory for a new video frame (zero-copy: hold lock while rendering
            // so we can pass the reference directly without allocating a Vec)
            let reader_result = SHMEM_READER.get_or_try_init(|| match ShmemFrameReader::open() {
                Ok(reader) => {
                    SHMEM_FAILED.store(false, Ordering::Relaxed);
                    Ok(Mutex::new(reader))
                },
                Err(e) => {
                    if !SHMEM_FAILED.swap(true, Ordering::Relaxed) {
                        vlog!("ShmemFrameReader open failed: {} (daemon not running?)", e);
                    }
                    Err(e)
                },
            });
            let mut shmem_guard = reader_result.ok().and_then(|m| m.lock().ok());
            let new_frame = match shmem_guard.as_mut() {
                Some(reader) => {
                    let result = reader.poll_frame();
                    if frame.is_multiple_of(300) {
                        if let Some(data) = &result {
                            vlog!("Got video frame: {} bytes", data.len());
                        } else {
                            vlog!(
                                "poll_frame: None (last_pts={}, shmem_pts={})",
                                reader.last_pts(),
                                reader.shmem_pts()
                            );
                        }
                    }
                    result
                },
                None => {
                    if frame.is_multiple_of(600) {
                        vlog!("Waiting for video daemon (shmem not available)");
                    }
                    None
                },
            };

            // Use cached swapchain images (fetched once per swapchain lifetime)
            let image = {
                let mut img_guard = match SWAPCHAIN_IMAGES.lock() {
                    Ok(g) => g,
                    Err(_) => return,
                };
                if img_guard.is_none() {
                    if let Some(swapchain_fn) = ASH_SWAPCHAIN_FN.get() {
                        if let Ok(images) = swapchain_fn.get_swapchain_images(swapchain) {
                            *img_guard = Some(images);
                        }
                    }
                }
                img_guard
                    .as_ref()
                    .and_then(|imgs| imgs.get(image_index as usize).copied())
            };

            if let Some(image) = image {
                if let Err(e) = renderer.render_frame(image_index, image, &mvp, new_frame) {
                    if frame.is_multiple_of(300) {
                        vlog!("Render error: {}", e);
                    }
                }
            }
        }
    }
}

/// Compute the MVP for this frame using camera state.
///
/// Returns a fallback MVP if the camera can't be read, or skips rendering
/// (via a fixed off-screen MVP) if not in cockpit mode.
unsafe fn compute_frame_mvp(frame: u64) -> [f32; 16] {
    // Try to initialize/use the camera reader
    let camera_result = CAMERA.get_or_try_init(|| unsafe { CameraReader::new() });

    if let Ok(camera) = camera_result {
        if let Some(state) = camera.read() {
            // Only render in cockpit mode - return off-screen MVP otherwise
            if state.mode != CAMERA_MODE_COCKPIT {
                return offscreen_mvp();
            }
            return compute_cockpit_mvp(state.fov_deg, state.aspect);
        }
    }

    // Fallback: camera not available, use default values
    if frame.is_multiple_of(300) {
        vlog!("Camera unavailable, using fallback MVP");
    }
    let extent_packed = SWAPCHAIN_EXTENT.load(Ordering::Relaxed);
    let w = (extent_packed >> 32) as f32;
    let h = (extent_packed & 0xFFFFFFFF) as f32;
    let aspect = if h > 0.0 { w / h } else { 16.0 / 9.0 };
    compute_cockpit_mvp(75.0, aspect)
}

/// MVP that places the quad entirely off-screen (used to hide when not in cockpit).
fn offscreen_mvp() -> [f32; 16] {
    [
        0.0, 0.0, 0.0, 0.0, // column 0: zero scale
        0.0, 0.0, 0.0, 0.0, // column 1: zero scale
        0.0, 0.0, 0.0, 0.0, // column 2
        0.0, 0.0, 0.0, 1.0, // column 3: w=1 but everything else zero → degenerate
    ]
}

/// Initialize the renderer with current state.
fn init_renderer(queue: vk::Queue, swapchain: vk::SwapchainKHR) -> Result<VulkanRenderer, String> {
    let instance = ASH_INSTANCE
        .get()
        .ok_or_else(|| "No ash::Instance".to_string())?;
    let &physical_device = PHYSICAL_DEVICE
        .get()
        .ok_or_else(|| "No physical device".to_string())?;
    let &device = DEVICE.get().ok_or_else(|| "No device".to_string())?;

    let extent_packed = SWAPCHAIN_EXTENT.load(Ordering::Relaxed);
    let extent = vk::Extent2D {
        width: (extent_packed >> 32) as u32,
        height: (extent_packed & 0xFFFFFFFF) as u32,
    };

    let format_raw = SWAPCHAIN_FORMAT.load(Ordering::Relaxed) as i32;
    let format = vk::Format::from_raw(format_raw);

    let queue_family = QUEUE_FAMILY_INDEX.load(Ordering::Relaxed) as u32;

    vlog!(
        "Initializing renderer: extent={}x{} format={:?} queue_family={}",
        extent.width,
        extent.height,
        format,
        queue_family
    );

    let renderer = unsafe {
        VulkanRenderer::new(
            device,
            physical_device,
            queue,
            queue_family,
            swapchain,
            format,
            extent,
            instance,
        )?
    };

    Ok(renderer)
}

// --- Installation ---

/// Install Vulkan hooks.
///
/// # Safety
/// vulkan-1.dll must be loaded in the process.
pub unsafe fn install() -> Result<(), String> {
    let vulkan_module = get_vulkan_module()?;

    // Hook vkCreateInstance
    let addr = get_proc(vulkan_module, "vkCreateInstance")?;
    vlog!("vkCreateInstance at {:p}", addr);
    let pfn: unsafe extern "system" fn(
        *const c_void,
        *const c_void,
        *mut vk::Instance,
    ) -> vk::Result = std::mem::transmute(addr);
    Hook_vkCreateInstance
        .initialize(pfn, hooked_create_instance)
        .map_err(|e| format!("Failed to init vkCreateInstance hook: {}", e))?;
    Hook_vkCreateInstance
        .enable()
        .map_err(|e| format!("Failed to enable vkCreateInstance hook: {}", e))?;
    vlog!("vkCreateInstance hooked");

    // Hook vkCreateDevice
    let addr = get_proc(vulkan_module, "vkCreateDevice")?;
    vlog!("vkCreateDevice at {:p}", addr);
    let pfn: unsafe extern "system" fn(
        vk::PhysicalDevice,
        *const c_void,
        *const c_void,
        *mut vk::Device,
    ) -> vk::Result = std::mem::transmute(addr);
    Hook_vkCreateDevice
        .initialize(pfn, hooked_create_device)
        .map_err(|e| format!("Failed to init vkCreateDevice hook: {}", e))?;
    Hook_vkCreateDevice
        .enable()
        .map_err(|e| format!("Failed to enable vkCreateDevice hook: {}", e))?;
    vlog!("vkCreateDevice hooked");

    // Hook vkCreateSwapchainKHR
    let addr = get_proc(vulkan_module, "vkCreateSwapchainKHR")?;
    vlog!("vkCreateSwapchainKHR at {:p}", addr);
    let pfn: unsafe extern "system" fn(
        vk::Device,
        *const c_void,
        *const c_void,
        *mut vk::SwapchainKHR,
    ) -> vk::Result = std::mem::transmute(addr);
    Hook_vkCreateSwapchainKHR
        .initialize(pfn, hooked_create_swapchain)
        .map_err(|e| format!("Failed to init vkCreateSwapchainKHR hook: {}", e))?;
    Hook_vkCreateSwapchainKHR
        .enable()
        .map_err(|e| format!("Failed to enable vkCreateSwapchainKHR hook: {}", e))?;
    vlog!("vkCreateSwapchainKHR hooked");

    // Hook vkQueuePresentKHR
    let addr = get_proc(vulkan_module, "vkQueuePresentKHR")?;
    vlog!("vkQueuePresentKHR at {:p}", addr);
    let pfn: unsafe extern "system" fn(vk::Queue, *const c_void) -> vk::Result =
        std::mem::transmute(addr);
    Hook_vkQueuePresentKHR
        .initialize(pfn, hooked_queue_present)
        .map_err(|e| format!("Failed to init vkQueuePresentKHR hook: {}", e))?;
    Hook_vkQueuePresentKHR
        .enable()
        .map_err(|e| format!("Failed to enable vkQueuePresentKHR hook: {}", e))?;
    vlog!("vkQueuePresentKHR hooked");

    Ok(())
}

/// Remove all Vulkan hooks.
///
/// # Safety
/// Must be called during DLL detach.
pub unsafe fn remove() {
    // Disable ICD-level hooks first (these are the active ones)
    if let Some(holder) = ICD_PRESENT_DETOUR.get() {
        let _ = holder.0.disable();
    }
    if let Some(holder) = ICD_SWAPCHAIN_DETOUR.get() {
        let _ = holder.0.disable();
    }
    // Disable loader trampoline hooks
    let _ = Hook_vkQueuePresentKHR.disable();
    let _ = Hook_vkCreateSwapchainKHR.disable();
    let _ = Hook_vkCreateDevice.disable();
    let _ = Hook_vkCreateInstance.disable();
    vlog!("Vulkan hooks removed");
}

// --- Public accessors for VR hook ---

/// Get the renderer mutex (used by OpenVR hook).
pub fn get_renderer() -> &'static Mutex<Option<VulkanRenderer>> {
    &RENDERER
}

/// Compute the current MVP matrix (used by OpenVR hook).
///
/// # Safety
/// Reads camera memory.
pub unsafe fn get_mvp(frame: u64) -> [f32; 16] {
    compute_frame_mvp(frame)
}

// --- Helpers ---

/// Get the vulkan-1.dll module handle.
unsafe fn get_vulkan_module() -> Result<windows::Win32::Foundation::HMODULE, String> {
    let name = CString::new("vulkan-1.dll").unwrap();
    GetModuleHandleA(windows::core::PCSTR(name.as_ptr() as *const _))
        .map_err(|e| format!("GetModuleHandle(vulkan-1.dll) failed: {}", e))
}

/// Get a function address from a module.
unsafe fn get_proc(
    module: windows::Win32::Foundation::HMODULE,
    name: &str,
) -> Result<*const c_void, String> {
    let cname = CString::new(name).unwrap();
    let addr = GetProcAddress(module, windows::core::PCSTR(cname.as_ptr() as *const _));
    match addr {
        Some(f) => Ok(f as *const c_void),
        None => Err(format!("GetProcAddress({}) failed", name)),
    }
}

/// Get vkGetInstanceProcAddr function pointer from vulkan-1.dll.
unsafe fn get_instance_proc_addr_fn() -> Option<vk::PFN_vkGetInstanceProcAddr> {
    let module = get_vulkan_module().ok()?;
    let addr = get_proc(module, "vkGetInstanceProcAddr").ok()?;
    Some(std::mem::transmute::<
        *const std::ffi::c_void,
        unsafe extern "system" fn(vk::Instance, *const i8) -> Option<unsafe extern "system" fn()>,
    >(addr))
}
