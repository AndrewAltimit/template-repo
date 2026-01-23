//! Vulkan renderer for the video quad overlay.
//!
//! Creates and manages all GPU resources needed to render a textured quad
//! on top of the game's swapchain images.

pub mod geometry;

use crate::log::vlog;
use ash::vk;
use geometry::{Vertex, QUAD_VERTICES, QUAD_VERTICES_SIZE};
use std::ffi::CStr;

/// Embedded SPIR-V shaders (compiled by build.rs).
const VERT_SPV: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/quad.vert.spv"));
const FRAG_SPV: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/quad.frag.spv"));

/// Per-frame rendering resources.
struct FrameResources {
    framebuffer: vk::Framebuffer,
    command_buffer: vk::CommandBuffer,
    fence: vk::Fence,
    image_view: vk::ImageView,
}

/// The Vulkan renderer that draws a quad over the game's output.
pub struct VulkanRenderer {
    device: ash::Device,
    queue: vk::Queue,
    render_pass: vk::RenderPass,
    pipeline_layout: vk::PipelineLayout,
    pipeline: vk::Pipeline,
    command_pool: vk::CommandPool,
    vertex_buffer: vk::Buffer,
    vertex_memory: vk::DeviceMemory,
    frames: Vec<FrameResources>,
    extent: vk::Extent2D,
    format: vk::Format,
}

impl VulkanRenderer {
    /// Initialize the renderer with the game's Vulkan device and swapchain info.
    ///
    /// # Safety
    /// - `raw_device` must be a valid VkDevice
    /// - `queue` must be a valid VkQueue from that device
    /// - `swapchain` must be a valid VkSwapchainKHR
    /// - `physical_device` must be the physical device used to create `raw_device`
    pub unsafe fn new(
        raw_device: vk::Device,
        physical_device: vk::PhysicalDevice,
        queue: vk::Queue,
        queue_family_index: u32,
        swapchain: vk::SwapchainKHR,
        format: vk::Format,
        extent: vk::Extent2D,
        instance: &ash::Instance,
    ) -> Result<Self, String> {
        // Load device functions
        let device = ash::Device::load(instance.fp_v1_0(), raw_device);

        // Get swapchain images
        let swapchain_fn = ash::khr::swapchain::Device::new(instance, &device);
        let images = swapchain_fn
            .get_swapchain_images(swapchain)
            .map_err(|e| format!("Failed to get swapchain images: {:?}", e))?;

        vlog!("Swapchain has {} images", images.len());

        // Create render pass
        let render_pass = create_render_pass(&device, format)?;

        // Create pipeline layout (push constant: mat4 = 64 bytes)
        let push_constant_range = vk::PushConstantRange {
            stage_flags: vk::ShaderStageFlags::VERTEX,
            offset: 0,
            size: 64, // mat4
        };

        let layout_info = vk::PipelineLayoutCreateInfo::default()
            .push_constant_ranges(std::slice::from_ref(&push_constant_range));

        let pipeline_layout = device
            .create_pipeline_layout(&layout_info, None)
            .map_err(|e| format!("Failed to create pipeline layout: {:?}", e))?;

        // Create graphics pipeline
        let pipeline = create_pipeline(&device, render_pass, pipeline_layout, extent)?;

        // Create command pool
        let pool_info = vk::CommandPoolCreateInfo::default()
            .queue_family_index(queue_family_index)
            .flags(vk::CommandPoolCreateFlags::RESET_COMMAND_BUFFER);

        let command_pool = device
            .create_command_pool(&pool_info, None)
            .map_err(|e| format!("Failed to create command pool: {:?}", e))?;

        // Create vertex buffer
        let (vertex_buffer, vertex_memory) =
            create_vertex_buffer(&device, instance, physical_device)?;

        // Create per-frame resources
        let frames = create_frame_resources(
            &device,
            &images,
            format,
            extent,
            render_pass,
            command_pool,
        )?;

        vlog!(
            "Renderer initialized: {}x{} format={:?} frames={}",
            extent.width,
            extent.height,
            format,
            frames.len()
        );

        Ok(Self {
            device,
            queue,
            render_pass,
            pipeline_layout,
            pipeline,
            command_pool,
            vertex_buffer,
            vertex_memory,
            frames,
            extent,
            format,
        })
    }

    /// Render the quad overlay for the given swapchain image index.
    ///
    /// # Safety
    /// Must be called from the render thread with a valid image_index.
    pub unsafe fn render_frame(&self, image_index: u32, image: vk::Image) -> Result<(), String> {
        let idx = image_index as usize;
        if idx >= self.frames.len() {
            return Err(format!("image_index {} out of range", image_index));
        }

        let frame = &self.frames[idx];

        // Wait for previous use of this frame's resources
        self.device
            .wait_for_fences(&[frame.fence], true, u64::MAX)
            .map_err(|e| format!("Wait fence failed: {:?}", e))?;
        self.device
            .reset_fences(&[frame.fence])
            .map_err(|e| format!("Reset fence failed: {:?}", e))?;

        // Reset and record command buffer
        self.device
            .reset_command_buffer(frame.command_buffer, vk::CommandBufferResetFlags::empty())
            .map_err(|e| format!("Reset cmd buf failed: {:?}", e))?;

        let begin_info = vk::CommandBufferBeginInfo::default()
            .flags(vk::CommandBufferUsageFlags::ONE_TIME_SUBMIT);

        self.device
            .begin_command_buffer(frame.command_buffer, &begin_info)
            .map_err(|e| format!("Begin cmd buf failed: {:?}", e))?;

        // Transition: PRESENT_SRC -> COLOR_ATTACHMENT
        let barrier = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::MEMORY_READ)
            .dst_access_mask(vk::AccessFlags::COLOR_ATTACHMENT_WRITE)
            .old_layout(vk::ImageLayout::PRESENT_SRC_KHR)
            .new_layout(vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL)
            .image(image)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        self.device.cmd_pipeline_barrier(
            frame.command_buffer,
            vk::PipelineStageFlags::BOTTOM_OF_PIPE,
            vk::PipelineStageFlags::COLOR_ATTACHMENT_OUTPUT,
            vk::DependencyFlags::empty(),
            &[],
            &[],
            &[barrier],
        );

        // Begin render pass (LOAD existing content)
        let clear_values = []; // No clear - we use LOAD_OP_LOAD
        let render_pass_info = vk::RenderPassBeginInfo::default()
            .render_pass(self.render_pass)
            .framebuffer(frame.framebuffer)
            .render_area(vk::Rect2D {
                offset: vk::Offset2D { x: 0, y: 0 },
                extent: self.extent,
            })
            .clear_values(&clear_values);

        self.device.cmd_begin_render_pass(
            frame.command_buffer,
            &render_pass_info,
            vk::SubpassContents::INLINE,
        );

        // Bind pipeline
        self.device.cmd_bind_pipeline(
            frame.command_buffer,
            vk::PipelineBindPoint::GRAPHICS,
            self.pipeline,
        );

        // Set dynamic viewport and scissor
        let viewport = vk::Viewport {
            x: 0.0,
            y: 0.0,
            width: self.extent.width as f32,
            height: self.extent.height as f32,
            min_depth: 0.0,
            max_depth: 1.0,
        };
        self.device
            .cmd_set_viewport(frame.command_buffer, 0, &[viewport]);

        let scissor = vk::Rect2D {
            offset: vk::Offset2D { x: 0, y: 0 },
            extent: self.extent,
        };
        self.device
            .cmd_set_scissor(frame.command_buffer, 0, &[scissor]);

        // Push MVP matrix (Phase 2: scale to small quad in center-right of screen)
        let mvp = phase2_mvp();
        let mvp_bytes: &[u8] = std::slice::from_raw_parts(
            mvp.as_ptr() as *const u8,
            64,
        );
        self.device.cmd_push_constants(
            frame.command_buffer,
            self.pipeline_layout,
            vk::ShaderStageFlags::VERTEX,
            0,
            mvp_bytes,
        );

        // Bind vertex buffer and draw
        self.device.cmd_bind_vertex_buffers(
            frame.command_buffer,
            0,
            &[self.vertex_buffer],
            &[0],
        );
        self.device.cmd_draw(frame.command_buffer, 6, 1, 0, 0);

        // End render pass
        self.device.cmd_end_render_pass(frame.command_buffer);

        // Transition: COLOR_ATTACHMENT -> PRESENT_SRC
        let barrier = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::COLOR_ATTACHMENT_WRITE)
            .dst_access_mask(vk::AccessFlags::MEMORY_READ)
            .old_layout(vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL)
            .new_layout(vk::ImageLayout::PRESENT_SRC_KHR)
            .image(image)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        self.device.cmd_pipeline_barrier(
            frame.command_buffer,
            vk::PipelineStageFlags::COLOR_ATTACHMENT_OUTPUT,
            vk::PipelineStageFlags::TOP_OF_PIPE,
            vk::DependencyFlags::empty(),
            &[],
            &[],
            &[barrier],
        );

        self.device
            .end_command_buffer(frame.command_buffer)
            .map_err(|e| format!("End cmd buf failed: {:?}", e))?;

        // Submit
        let cmd_bufs = [frame.command_buffer];
        let submit_info = vk::SubmitInfo::default().command_buffers(&cmd_bufs);

        self.device
            .queue_submit(self.queue, &[submit_info], frame.fence)
            .map_err(|e| format!("Queue submit failed: {:?}", e))?;

        // Wait for our rendering to complete before the game presents
        self.device
            .wait_for_fences(&[frame.fence], true, u64::MAX)
            .map_err(|e| format!("Wait after submit failed: {:?}", e))?;

        Ok(())
    }

    /// Get the swapchain extent.
    pub fn extent(&self) -> vk::Extent2D {
        self.extent
    }
}

impl Drop for VulkanRenderer {
    fn drop(&mut self) {
        unsafe {
            let _ = self.device.device_wait_idle();

            for frame in &self.frames {
                self.device.destroy_framebuffer(frame.framebuffer, None);
                self.device.destroy_image_view(frame.image_view, None);
                self.device.destroy_fence(frame.fence, None);
            }

            self.device.destroy_command_pool(self.command_pool, None);
            self.device.free_memory(self.vertex_memory, None);
            self.device.destroy_buffer(self.vertex_buffer, None);
            self.device.destroy_pipeline(self.pipeline, None);
            self.device
                .destroy_pipeline_layout(self.pipeline_layout, None);
            self.device.destroy_render_pass(self.render_pass, None);

            vlog!("Renderer destroyed");
        }
    }
}

// --- Helper functions ---

/// Create render pass with LOAD_OP_LOAD (preserves game frame).
unsafe fn create_render_pass(
    device: &ash::Device,
    format: vk::Format,
) -> Result<vk::RenderPass, String> {
    let attachment = vk::AttachmentDescription {
        format,
        samples: vk::SampleCountFlags::TYPE_1,
        load_op: vk::AttachmentLoadOp::LOAD,
        store_op: vk::AttachmentStoreOp::STORE,
        stencil_load_op: vk::AttachmentLoadOp::DONT_CARE,
        stencil_store_op: vk::AttachmentStoreOp::DONT_CARE,
        initial_layout: vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL,
        final_layout: vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL,
        ..Default::default()
    };

    let color_ref = vk::AttachmentReference {
        attachment: 0,
        layout: vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL,
    };

    let subpass = vk::SubpassDescription::default()
        .pipeline_bind_point(vk::PipelineBindPoint::GRAPHICS)
        .color_attachments(std::slice::from_ref(&color_ref));

    let dependency = vk::SubpassDependency {
        src_subpass: vk::SUBPASS_EXTERNAL,
        dst_subpass: 0,
        src_stage_mask: vk::PipelineStageFlags::COLOR_ATTACHMENT_OUTPUT,
        dst_stage_mask: vk::PipelineStageFlags::COLOR_ATTACHMENT_OUTPUT,
        src_access_mask: vk::AccessFlags::empty(),
        dst_access_mask: vk::AccessFlags::COLOR_ATTACHMENT_WRITE,
        ..Default::default()
    };

    let info = vk::RenderPassCreateInfo::default()
        .attachments(std::slice::from_ref(&attachment))
        .subpasses(std::slice::from_ref(&subpass))
        .dependencies(std::slice::from_ref(&dependency));

    device
        .create_render_pass(&info, None)
        .map_err(|e| format!("Failed to create render pass: {:?}", e))
}

/// Create the graphics pipeline.
unsafe fn create_pipeline(
    device: &ash::Device,
    render_pass: vk::RenderPass,
    layout: vk::PipelineLayout,
    extent: vk::Extent2D,
) -> Result<vk::Pipeline, String> {
    // Create shader modules
    let vert_module = create_shader_module(device, VERT_SPV)?;
    let frag_module = create_shader_module(device, FRAG_SPV)?;

    let entry_name = CStr::from_bytes_with_nul(b"main\0").unwrap();

    let stages = [
        vk::PipelineShaderStageCreateInfo::default()
            .stage(vk::ShaderStageFlags::VERTEX)
            .module(vert_module)
            .name(entry_name),
        vk::PipelineShaderStageCreateInfo::default()
            .stage(vk::ShaderStageFlags::FRAGMENT)
            .module(frag_module)
            .name(entry_name),
    ];

    // Vertex input
    let binding = Vertex::binding_description();
    let attributes = Vertex::attribute_descriptions();

    let vertex_input = vk::PipelineVertexInputStateCreateInfo::default()
        .vertex_binding_descriptions(std::slice::from_ref(&binding))
        .vertex_attribute_descriptions(&attributes);

    let input_assembly = vk::PipelineInputAssemblyStateCreateInfo::default()
        .topology(vk::PrimitiveTopology::TRIANGLE_LIST);

    // Viewport/scissor (dynamic state)
    let viewport = vk::Viewport {
        x: 0.0,
        y: 0.0,
        width: extent.width as f32,
        height: extent.height as f32,
        min_depth: 0.0,
        max_depth: 1.0,
    };
    let scissor = vk::Rect2D {
        offset: vk::Offset2D { x: 0, y: 0 },
        extent,
    };

    let viewport_state = vk::PipelineViewportStateCreateInfo::default()
        .viewports(std::slice::from_ref(&viewport))
        .scissors(std::slice::from_ref(&scissor));

    let rasterizer = vk::PipelineRasterizationStateCreateInfo::default()
        .polygon_mode(vk::PolygonMode::FILL)
        .line_width(1.0)
        .cull_mode(vk::CullModeFlags::NONE) // No culling for overlay
        .front_face(vk::FrontFace::COUNTER_CLOCKWISE);

    let multisampling = vk::PipelineMultisampleStateCreateInfo::default()
        .rasterization_samples(vk::SampleCountFlags::TYPE_1);

    // Alpha blending
    let blend_attachment = vk::PipelineColorBlendAttachmentState {
        blend_enable: vk::TRUE,
        src_color_blend_factor: vk::BlendFactor::SRC_ALPHA,
        dst_color_blend_factor: vk::BlendFactor::ONE_MINUS_SRC_ALPHA,
        color_blend_op: vk::BlendOp::ADD,
        src_alpha_blend_factor: vk::BlendFactor::ONE,
        dst_alpha_blend_factor: vk::BlendFactor::ZERO,
        alpha_blend_op: vk::BlendOp::ADD,
        color_write_mask: vk::ColorComponentFlags::RGBA,
    };

    let color_blending = vk::PipelineColorBlendStateCreateInfo::default()
        .attachments(std::slice::from_ref(&blend_attachment));

    // Dynamic state
    let dynamic_states = [vk::DynamicState::VIEWPORT, vk::DynamicState::SCISSOR];
    let dynamic_state =
        vk::PipelineDynamicStateCreateInfo::default().dynamic_states(&dynamic_states);

    let pipeline_info = vk::GraphicsPipelineCreateInfo::default()
        .stages(&stages)
        .vertex_input_state(&vertex_input)
        .input_assembly_state(&input_assembly)
        .viewport_state(&viewport_state)
        .rasterization_state(&rasterizer)
        .multisample_state(&multisampling)
        .color_blend_state(&color_blending)
        .dynamic_state(&dynamic_state)
        .layout(layout)
        .render_pass(render_pass)
        .subpass(0);

    let pipelines = device
        .create_graphics_pipelines(vk::PipelineCache::null(), &[pipeline_info], None)
        .map_err(|(_pipelines, e)| format!("Failed to create pipeline: {:?}", e))?;

    // Clean up shader modules (no longer needed after pipeline creation)
    device.destroy_shader_module(vert_module, None);
    device.destroy_shader_module(frag_module, None);

    Ok(pipelines[0])
}

/// Create a shader module from SPIR-V bytes.
unsafe fn create_shader_module(
    device: &ash::Device,
    spv_bytes: &[u8],
) -> Result<vk::ShaderModule, String> {
    // SPIR-V must be aligned to 4 bytes and length must be multiple of 4
    if spv_bytes.len() % 4 != 0 {
        return Err("SPIR-V not aligned to 4 bytes".to_string());
    }

    let code: &[u32] =
        std::slice::from_raw_parts(spv_bytes.as_ptr() as *const u32, spv_bytes.len() / 4);

    let info = vk::ShaderModuleCreateInfo::default().code(code);

    device
        .create_shader_module(&info, None)
        .map_err(|e| format!("Failed to create shader module: {:?}", e))
}

/// Create vertex buffer with quad data.
unsafe fn create_vertex_buffer(
    device: &ash::Device,
    instance: &ash::Instance,
    physical_device: vk::PhysicalDevice,
) -> Result<(vk::Buffer, vk::DeviceMemory), String> {
    let buffer_info = vk::BufferCreateInfo::default()
        .size(QUAD_VERTICES_SIZE)
        .usage(vk::BufferUsageFlags::VERTEX_BUFFER)
        .sharing_mode(vk::SharingMode::EXCLUSIVE);

    let buffer = device
        .create_buffer(&buffer_info, None)
        .map_err(|e| format!("Failed to create vertex buffer: {:?}", e))?;

    let mem_reqs = device.get_buffer_memory_requirements(buffer);

    let mem_props = instance.get_physical_device_memory_properties(physical_device);
    let memory_type = find_memory_type(
        &mem_props,
        mem_reqs.memory_type_bits,
        vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT,
    )
    .ok_or_else(|| "No suitable memory type for vertex buffer".to_string())?;

    let alloc_info = vk::MemoryAllocateInfo::default()
        .allocation_size(mem_reqs.size)
        .memory_type_index(memory_type);

    let memory = device
        .allocate_memory(&alloc_info, None)
        .map_err(|e| format!("Failed to allocate vertex memory: {:?}", e))?;

    device
        .bind_buffer_memory(buffer, memory, 0)
        .map_err(|e| format!("Failed to bind vertex memory: {:?}", e))?;

    // Map and copy vertex data
    let data_ptr = device
        .map_memory(memory, 0, QUAD_VERTICES_SIZE, vk::MemoryMapFlags::empty())
        .map_err(|e| format!("Failed to map vertex memory: {:?}", e))?;

    std::ptr::copy_nonoverlapping(
        QUAD_VERTICES.as_ptr() as *const u8,
        data_ptr as *mut u8,
        QUAD_VERTICES_SIZE as usize,
    );

    device.unmap_memory(memory);

    Ok((buffer, memory))
}

/// Find a suitable memory type index.
fn find_memory_type(
    props: &vk::PhysicalDeviceMemoryProperties,
    type_bits: u32,
    required: vk::MemoryPropertyFlags,
) -> Option<u32> {
    for i in 0..props.memory_type_count {
        if (type_bits & (1 << i)) != 0
            && props.memory_types[i as usize]
                .property_flags
                .contains(required)
        {
            return Some(i);
        }
    }
    None
}

/// Create per-frame resources (image views, framebuffers, command buffers, fences).
unsafe fn create_frame_resources(
    device: &ash::Device,
    images: &[vk::Image],
    format: vk::Format,
    extent: vk::Extent2D,
    render_pass: vk::RenderPass,
    command_pool: vk::CommandPool,
) -> Result<Vec<FrameResources>, String> {
    // Allocate command buffers for all frames at once
    let alloc_info = vk::CommandBufferAllocateInfo::default()
        .command_pool(command_pool)
        .level(vk::CommandBufferLevel::PRIMARY)
        .command_buffer_count(images.len() as u32);

    let command_buffers = device
        .allocate_command_buffers(&alloc_info)
        .map_err(|e| format!("Failed to allocate command buffers: {:?}", e))?;

    let mut frames = Vec::with_capacity(images.len());

    for (i, &image) in images.iter().enumerate() {
        // Create image view
        let view_info = vk::ImageViewCreateInfo::default()
            .image(image)
            .view_type(vk::ImageViewType::TYPE_2D)
            .format(format)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        let image_view = device
            .create_image_view(&view_info, None)
            .map_err(|e| format!("Failed to create image view {}: {:?}", i, e))?;

        // Create framebuffer
        let fb_info = vk::FramebufferCreateInfo::default()
            .render_pass(render_pass)
            .attachments(std::slice::from_ref(&image_view))
            .width(extent.width)
            .height(extent.height)
            .layers(1);

        let framebuffer = device
            .create_framebuffer(&fb_info, None)
            .map_err(|e| format!("Failed to create framebuffer {}: {:?}", i, e))?;

        // Create fence (start signaled so first wait doesn't block)
        let fence_info =
            vk::FenceCreateInfo::default().flags(vk::FenceCreateFlags::SIGNALED);

        let fence = device
            .create_fence(&fence_info, None)
            .map_err(|e| format!("Failed to create fence {}: {:?}", i, e))?;

        frames.push(FrameResources {
            framebuffer,
            command_buffer: command_buffers[i],
            fence,
            image_view,
        });
    }

    Ok(frames)
}

/// Phase 2 MVP matrix: places a small quad in the upper-right area of the screen.
/// Maps the [-1,1] unit quad to roughly [0.3, 0.8] x [-0.7, -0.2] in NDC
/// (upper-right quadrant, Vulkan Y-down).
fn phase2_mvp() -> [f32; 16] {
    // Scale to 25% of screen, translate to upper-right
    let sx = 0.25_f32; // width = 50% of half-screen = 25% total
    let sy = 0.25_f32; // height = 25%
    let tx = 0.55_f32; // center X offset right
    let ty = -0.45_f32; // center Y offset up (Vulkan Y-down: negative = up)

    // Column-major 4x4 matrix: scale then translate
    [
        sx, 0.0, 0.0, 0.0, // column 0
        0.0, sy, 0.0, 0.0, // column 1
        0.0, 0.0, 1.0, 0.0, // column 2
        tx, ty, 0.0, 1.0, // column 3
    ]
}
