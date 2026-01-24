//! Vulkan renderer for the video quad overlay.
//!
//! Creates and manages all GPU resources needed to render a textured quad
//! on top of the game's swapchain images.

pub mod geometry;
pub mod texture;

use crate::log::vlog;
use ash::vk;
use geometry::{Vertex, QUAD_VERTICES, QUAD_VERTICES_SIZE};
use std::collections::HashMap;
use texture::VideoTexture;

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

/// Cached VR rendering resources for a specific eye texture.
struct VrFrameCache {
    image_view: vk::ImageView,
    framebuffer: vk::Framebuffer,
    fence: vk::Fence,
    command_buffer: vk::CommandBuffer,
}

/// Default video frame dimensions (must match daemon).
const VIDEO_WIDTH: u32 = 1280;
const VIDEO_HEIGHT: u32 = 720;

/// The Vulkan renderer that draws a quad over the game's output.
pub struct VulkanRenderer {
    device: ash::Device,
    queue: vk::Queue,
    render_pass: vk::RenderPass,
    pipeline_layout: vk::PipelineLayout,
    pipeline: vk::Pipeline,
    descriptor_set_layout: vk::DescriptorSetLayout,
    video_texture: VideoTexture,
    command_pool: vk::CommandPool,
    vertex_buffer: vk::Buffer,
    vertex_memory: vk::DeviceMemory,
    frames: Vec<FrameResources>,
    extent: vk::Extent2D,
    format: vk::Format,
    /// Cached VR resources per eye image handle (avoids re-creation every frame).
    vr_cache: HashMap<vk::Image, VrFrameCache>,
}

impl VulkanRenderer {
    /// Initialize the renderer with the game's Vulkan device and swapchain info.
    ///
    /// # Safety
    /// - `raw_device` must be a valid VkDevice
    /// - `queue` must be a valid VkQueue from that device
    /// - `swapchain` must be a valid VkSwapchainKHR
    /// - `physical_device` must be the physical device used to create `raw_device`
    #[allow(clippy::too_many_arguments)]
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

        // Create descriptor set layout for video texture
        let descriptor_set_layout =
            texture::create_descriptor_set_layout(&device).map_err(|e| {
                device.destroy_render_pass(render_pass, None);
                e
            })?;

        // Create pipeline layout (descriptor set + push constant: mat4 = 64 bytes)
        let push_constant_range = vk::PushConstantRange {
            stage_flags: vk::ShaderStageFlags::VERTEX,
            offset: 0,
            size: 64, // mat4
        };

        let layout_info = vk::PipelineLayoutCreateInfo::default()
            .set_layouts(std::slice::from_ref(&descriptor_set_layout))
            .push_constant_ranges(std::slice::from_ref(&push_constant_range));

        let pipeline_layout = device
            .create_pipeline_layout(&layout_info, None)
            .map_err(|e| {
                device.destroy_descriptor_set_layout(descriptor_set_layout, None);
                device.destroy_render_pass(render_pass, None);
                format!("Failed to create pipeline layout: {:?}", e)
            })?;

        // Create graphics pipeline
        let pipeline =
            create_pipeline(&device, render_pass, pipeline_layout, extent).map_err(|e| {
                device.destroy_pipeline_layout(pipeline_layout, None);
                device.destroy_descriptor_set_layout(descriptor_set_layout, None);
                device.destroy_render_pass(render_pass, None);
                e
            })?;

        // Create command pool
        let pool_info = vk::CommandPoolCreateInfo::default()
            .queue_family_index(queue_family_index)
            .flags(vk::CommandPoolCreateFlags::RESET_COMMAND_BUFFER);

        let command_pool = device.create_command_pool(&pool_info, None).map_err(|e| {
            device.destroy_pipeline(pipeline, None);
            device.destroy_pipeline_layout(pipeline_layout, None);
            device.destroy_descriptor_set_layout(descriptor_set_layout, None);
            device.destroy_render_pass(render_pass, None);
            format!("Failed to create command pool: {:?}", e)
        })?;

        // Create vertex buffer
        let (vertex_buffer, vertex_memory) =
            create_vertex_buffer(&device, instance, physical_device).map_err(|e| {
                device.destroy_command_pool(command_pool, None);
                device.destroy_pipeline(pipeline, None);
                device.destroy_pipeline_layout(pipeline_layout, None);
                device.destroy_descriptor_set_layout(descriptor_set_layout, None);
                device.destroy_render_pass(render_pass, None);
                e
            })?;

        // Create video texture
        let video_texture = VideoTexture::new(
            &device,
            instance,
            physical_device,
            descriptor_set_layout,
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
            queue,
            command_pool,
        )
        .map_err(|e| {
            device.free_memory(vertex_memory, None);
            device.destroy_buffer(vertex_buffer, None);
            device.destroy_command_pool(command_pool, None);
            device.destroy_pipeline(pipeline, None);
            device.destroy_pipeline_layout(pipeline_layout, None);
            device.destroy_descriptor_set_layout(descriptor_set_layout, None);
            device.destroy_render_pass(render_pass, None);
            e
        })?;

        // Create per-frame resources
        let frames =
            create_frame_resources(&device, &images, format, extent, render_pass, command_pool)
                .map_err(|e| {
                    video_texture.destroy(&device);
                    device.free_memory(vertex_memory, None);
                    device.destroy_buffer(vertex_buffer, None);
                    device.destroy_command_pool(command_pool, None);
                    device.destroy_pipeline(pipeline, None);
                    device.destroy_pipeline_layout(pipeline_layout, None);
                    device.destroy_descriptor_set_layout(descriptor_set_layout, None);
                    device.destroy_render_pass(render_pass, None);
                    e
                })?;

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
            descriptor_set_layout,
            video_texture,
            command_pool,
            vertex_buffer,
            vertex_memory,
            frames,
            extent,
            format,
            vr_cache: HashMap::new(),
        })
    }

    /// Render the quad overlay for the given swapchain image index.
    ///
    /// `mvp` is a column-major 4x4 matrix that transforms the unit quad to clip space.
    /// `new_frame` is optional RGBA pixel data to upload to the video texture.
    ///
    /// # Safety
    /// Must be called from the render thread with a valid image_index.
    pub unsafe fn render_frame(
        &self,
        image_index: u32,
        image: vk::Image,
        mvp: &[f32; 16],
        new_frame: Option<&[u8]>,
    ) -> Result<(), String> {
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

        // Upload new video frame if available
        if let Some(frame_data) = new_frame {
            self.video_texture
                .upload_frame(&self.device, frame.command_buffer, frame_data);
        }

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

        // Bind video texture descriptor set
        self.device.cmd_bind_descriptor_sets(
            frame.command_buffer,
            vk::PipelineBindPoint::GRAPHICS,
            self.pipeline_layout,
            0,
            &[self.video_texture.descriptor_set],
            &[],
        );

        // Push MVP matrix
        let mvp_bytes: &[u8] = std::slice::from_raw_parts(mvp.as_ptr() as *const u8, 64);
        self.device.cmd_push_constants(
            frame.command_buffer,
            self.pipeline_layout,
            vk::ShaderStageFlags::VERTEX,
            0,
            mvp_bytes,
        );

        // Bind vertex buffer and draw
        self.device
            .cmd_bind_vertex_buffers(frame.command_buffer, 0, &[self.vertex_buffer], &[0]);
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

    /// Render the quad overlay to a VR eye image.
    ///
    /// Uses cached resources per VR image handle to avoid re-creating
    /// VkImageView, VkFramebuffer, VkFence, and command buffers every frame.
    ///
    /// # Safety
    /// - `vr_image` must be a valid VkImage (from OpenVR's VRVulkanTextureData_t)
    /// - The image is expected to be in TRANSFER_SRC_OPTIMAL layout (ready for compositor)
    /// - Must be called from the render thread
    pub unsafe fn render_to_vr_image(
        &mut self,
        vr_image: vk::Image,
        extent: vk::Extent2D,
        mvp: &[f32; 16],
        new_frame: Option<&[u8]>,
    ) -> Result<(), String> {
        // Get or create cached resources for this VR image
        if !self.vr_cache.contains_key(&vr_image) {
            let cache = self.create_vr_frame_cache(vr_image, extent)?;
            self.vr_cache.insert(vr_image, cache);
        }
        let cached = self.vr_cache.get(&vr_image).unwrap();
        let cmd = cached.command_buffer;
        let fence = cached.fence;
        let framebuffer = cached.framebuffer;

        // Wait for previous use of this cached fence
        self.device
            .wait_for_fences(&[fence], true, u64::MAX)
            .map_err(|e| format!("VR fence wait failed: {:?}", e))?;
        self.device
            .reset_fences(&[fence])
            .map_err(|e| format!("VR fence reset failed: {:?}", e))?;

        // Reset and re-record command buffer
        self.device
            .reset_command_buffer(cmd, vk::CommandBufferResetFlags::empty())
            .map_err(|e| format!("VR cmd reset failed: {:?}", e))?;

        let begin_info = vk::CommandBufferBeginInfo::default()
            .flags(vk::CommandBufferUsageFlags::ONE_TIME_SUBMIT);

        self.device
            .begin_command_buffer(cmd, &begin_info)
            .map_err(|e| format!("VR begin cmd failed: {:?}", e))?;

        // Upload new video frame if available
        if let Some(frame_data) = new_frame {
            self.video_texture
                .upload_frame(&self.device, cmd, frame_data);
        }

        // Transition VR image: TRANSFER_SRC_OPTIMAL -> COLOR_ATTACHMENT_OPTIMAL
        let barrier = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::TRANSFER_READ)
            .dst_access_mask(vk::AccessFlags::COLOR_ATTACHMENT_WRITE)
            .old_layout(vk::ImageLayout::TRANSFER_SRC_OPTIMAL)
            .new_layout(vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL)
            .image(vr_image)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        self.device.cmd_pipeline_barrier(
            cmd,
            vk::PipelineStageFlags::TRANSFER,
            vk::PipelineStageFlags::COLOR_ATTACHMENT_OUTPUT,
            vk::DependencyFlags::empty(),
            &[],
            &[],
            &[barrier],
        );

        // Begin render pass (LOAD existing game content)
        let clear_values = [];
        let render_pass_info = vk::RenderPassBeginInfo::default()
            .render_pass(self.render_pass)
            .framebuffer(framebuffer)
            .render_area(vk::Rect2D {
                offset: vk::Offset2D { x: 0, y: 0 },
                extent,
            })
            .clear_values(&clear_values);

        self.device
            .cmd_begin_render_pass(cmd, &render_pass_info, vk::SubpassContents::INLINE);

        // Bind pipeline and set dynamic state
        self.device
            .cmd_bind_pipeline(cmd, vk::PipelineBindPoint::GRAPHICS, self.pipeline);

        let viewport = vk::Viewport {
            x: 0.0,
            y: 0.0,
            width: extent.width as f32,
            height: extent.height as f32,
            min_depth: 0.0,
            max_depth: 1.0,
        };
        self.device.cmd_set_viewport(cmd, 0, &[viewport]);

        let scissor = vk::Rect2D {
            offset: vk::Offset2D { x: 0, y: 0 },
            extent,
        };
        self.device.cmd_set_scissor(cmd, 0, &[scissor]);

        // Bind descriptor set and push MVP
        self.device.cmd_bind_descriptor_sets(
            cmd,
            vk::PipelineBindPoint::GRAPHICS,
            self.pipeline_layout,
            0,
            &[self.video_texture.descriptor_set],
            &[],
        );

        let mvp_bytes: &[u8] = std::slice::from_raw_parts(mvp.as_ptr() as *const u8, 64);
        self.device.cmd_push_constants(
            cmd,
            self.pipeline_layout,
            vk::ShaderStageFlags::VERTEX,
            0,
            mvp_bytes,
        );

        // Draw quad
        self.device
            .cmd_bind_vertex_buffers(cmd, 0, &[self.vertex_buffer], &[0]);
        self.device.cmd_draw(cmd, 6, 1, 0, 0);

        self.device.cmd_end_render_pass(cmd);

        // Transition VR image back: COLOR_ATTACHMENT_OPTIMAL -> TRANSFER_SRC_OPTIMAL
        let barrier = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::COLOR_ATTACHMENT_WRITE)
            .dst_access_mask(vk::AccessFlags::TRANSFER_READ)
            .old_layout(vk::ImageLayout::COLOR_ATTACHMENT_OPTIMAL)
            .new_layout(vk::ImageLayout::TRANSFER_SRC_OPTIMAL)
            .image(vr_image)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        self.device.cmd_pipeline_barrier(
            cmd,
            vk::PipelineStageFlags::COLOR_ATTACHMENT_OUTPUT,
            vk::PipelineStageFlags::TRANSFER,
            vk::DependencyFlags::empty(),
            &[],
            &[],
            &[barrier],
        );

        self.device
            .end_command_buffer(cmd)
            .map_err(|e| format!("VR end cmd failed: {:?}", e))?;

        // Submit and wait
        let cmd_bufs_submit = [cmd];
        let submit_info = vk::SubmitInfo::default().command_buffers(&cmd_bufs_submit);

        self.device
            .queue_submit(self.queue, &[submit_info], fence)
            .map_err(|e| format!("VR queue submit failed: {:?}", e))?;

        self.device
            .wait_for_fences(&[fence], true, u64::MAX)
            .map_err(|e| format!("VR fence wait failed: {:?}", e))?;

        Ok(())
    }

    /// Create cached VR frame resources for a specific eye image.
    unsafe fn create_vr_frame_cache(
        &self,
        vr_image: vk::Image,
        extent: vk::Extent2D,
    ) -> Result<VrFrameCache, String> {
        let view_info = vk::ImageViewCreateInfo::default()
            .image(vr_image)
            .view_type(vk::ImageViewType::TYPE_2D)
            .format(self.format)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        let image_view = self
            .device
            .create_image_view(&view_info, None)
            .map_err(|e| format!("VR cache image view failed: {:?}", e))?;

        let fb_info = vk::FramebufferCreateInfo::default()
            .render_pass(self.render_pass)
            .attachments(std::slice::from_ref(&image_view))
            .width(extent.width)
            .height(extent.height)
            .layers(1);

        let framebuffer = self
            .device
            .create_framebuffer(&fb_info, None)
            .map_err(|e| {
                self.device.destroy_image_view(image_view, None);
                format!("VR cache framebuffer failed: {:?}", e)
            })?;

        let alloc_info = vk::CommandBufferAllocateInfo::default()
            .command_pool(self.command_pool)
            .level(vk::CommandBufferLevel::PRIMARY)
            .command_buffer_count(1);

        let cmd_bufs = self
            .device
            .allocate_command_buffers(&alloc_info)
            .map_err(|e| {
                self.device.destroy_framebuffer(framebuffer, None);
                self.device.destroy_image_view(image_view, None);
                format!("VR cache cmd buf failed: {:?}", e)
            })?;

        let fence_info = vk::FenceCreateInfo::default().flags(vk::FenceCreateFlags::SIGNALED);
        let fence = self.device.create_fence(&fence_info, None).map_err(|e| {
            self.device
                .free_command_buffers(self.command_pool, &cmd_bufs);
            self.device.destroy_framebuffer(framebuffer, None);
            self.device.destroy_image_view(image_view, None);
            format!("VR cache fence failed: {:?}", e)
        })?;

        Ok(VrFrameCache {
            image_view,
            framebuffer,
            fence,
            command_buffer: cmd_bufs[0],
        })
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

            // Clean up cached VR resources
            for cached in self.vr_cache.values() {
                self.device.destroy_fence(cached.fence, None);
                self.device.destroy_framebuffer(cached.framebuffer, None);
                self.device.destroy_image_view(cached.image_view, None);
                // Command buffers freed with command pool below
            }

            for frame in &self.frames {
                self.device.destroy_framebuffer(frame.framebuffer, None);
                self.device.destroy_image_view(frame.image_view, None);
                self.device.destroy_fence(frame.fence, None);
            }

            self.video_texture.destroy(&self.device);
            self.device.destroy_command_pool(self.command_pool, None);
            self.device.free_memory(self.vertex_memory, None);
            self.device.destroy_buffer(self.vertex_buffer, None);
            self.device.destroy_pipeline(self.pipeline, None);
            self.device
                .destroy_pipeline_layout(self.pipeline_layout, None);
            self.device
                .destroy_descriptor_set_layout(self.descriptor_set_layout, None);
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

    let entry_name = c"main";

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
    if !spv_bytes.len().is_multiple_of(4) {
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
    (0..props.memory_type_count).find(|&i| {
        (type_bits & (1 << i)) != 0
            && props.memory_types[i as usize]
                .property_flags
                .contains(required)
    })
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
        let fence_info = vk::FenceCreateInfo::default().flags(vk::FenceCreateFlags::SIGNALED);

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
