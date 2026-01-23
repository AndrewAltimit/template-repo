//! Video texture management.
//!
//! Manages a device-local VkImage for the video texture, a staging buffer
//! for CPU→GPU uploads, and the descriptor set that binds the texture
//! to the fragment shader.

use crate::log::vlog;
use ash::vk;

// Safety: The staging_ptr is only accessed from the render thread,
// protected by the Mutex<VulkanRenderer> in the hooks module.
unsafe impl Send for VideoTexture {}
unsafe impl Sync for VideoTexture {}

/// Video texture with staging buffer and descriptor resources.
pub struct VideoTexture {
    /// Device-local image (TRANSFER_DST | SAMPLED).
    pub image: vk::Image,
    pub image_memory: vk::DeviceMemory,
    pub image_view: vk::ImageView,
    pub sampler: vk::Sampler,

    /// Staging buffer (HOST_VISIBLE | HOST_COHERENT, persistently mapped).
    pub staging_buffer: vk::Buffer,
    pub staging_memory: vk::DeviceMemory,
    pub staging_ptr: *mut u8,

    /// Descriptor resources.
    pub descriptor_pool: vk::DescriptorPool,
    pub descriptor_set: vk::DescriptorSet,

    /// Texture dimensions.
    pub width: u32,
    pub height: u32,

    /// Whether the image has been transitioned to SHADER_READ_ONLY at least once.
    pub initialized: bool,
}

impl VideoTexture {
    /// Create the video texture and all associated resources.
    ///
    /// # Safety
    /// All Vulkan handles must be valid.
    pub unsafe fn new(
        device: &ash::Device,
        instance: &ash::Instance,
        physical_device: vk::PhysicalDevice,
        descriptor_set_layout: vk::DescriptorSetLayout,
        width: u32,
        height: u32,
        queue: vk::Queue,
        command_pool: vk::CommandPool,
    ) -> Result<Self, String> {
        let frame_size = (width * height * 4) as u64;

        // --- Create device-local image ---
        let image_info = vk::ImageCreateInfo::default()
            .image_type(vk::ImageType::TYPE_2D)
            .format(vk::Format::R8G8B8A8_UNORM)
            .extent(vk::Extent3D {
                width,
                height,
                depth: 1,
            })
            .mip_levels(1)
            .array_layers(1)
            .samples(vk::SampleCountFlags::TYPE_1)
            .tiling(vk::ImageTiling::OPTIMAL)
            .usage(vk::ImageUsageFlags::TRANSFER_DST | vk::ImageUsageFlags::SAMPLED)
            .sharing_mode(vk::SharingMode::EXCLUSIVE)
            .initial_layout(vk::ImageLayout::UNDEFINED);

        let image = device
            .create_image(&image_info, None)
            .map_err(|e| format!("Create image failed: {:?}", e))?;

        let mem_reqs = device.get_image_memory_requirements(image);
        let mem_props = instance.get_physical_device_memory_properties(physical_device);

        let image_mem_type = find_memory_type(
            &mem_props,
            mem_reqs.memory_type_bits,
            vk::MemoryPropertyFlags::DEVICE_LOCAL,
        )
        .ok_or_else(|| "No device-local memory for texture".to_string())?;

        let alloc_info = vk::MemoryAllocateInfo::default()
            .allocation_size(mem_reqs.size)
            .memory_type_index(image_mem_type);

        let image_memory = device
            .allocate_memory(&alloc_info, None)
            .map_err(|e| format!("Allocate image memory failed: {:?}", e))?;

        device
            .bind_image_memory(image, image_memory, 0)
            .map_err(|e| format!("Bind image memory failed: {:?}", e))?;

        // --- Create image view ---
        let view_info = vk::ImageViewCreateInfo::default()
            .image(image)
            .view_type(vk::ImageViewType::TYPE_2D)
            .format(vk::Format::R8G8B8A8_UNORM)
            .subresource_range(vk::ImageSubresourceRange {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                base_mip_level: 0,
                level_count: 1,
                base_array_layer: 0,
                layer_count: 1,
            });

        let image_view = device
            .create_image_view(&view_info, None)
            .map_err(|e| format!("Create image view failed: {:?}", e))?;

        // --- Create sampler ---
        let sampler_info = vk::SamplerCreateInfo::default()
            .mag_filter(vk::Filter::LINEAR)
            .min_filter(vk::Filter::LINEAR)
            .address_mode_u(vk::SamplerAddressMode::CLAMP_TO_EDGE)
            .address_mode_v(vk::SamplerAddressMode::CLAMP_TO_EDGE)
            .address_mode_w(vk::SamplerAddressMode::CLAMP_TO_EDGE)
            .mipmap_mode(vk::SamplerMipmapMode::LINEAR)
            .min_lod(0.0)
            .max_lod(0.0);

        let sampler = device
            .create_sampler(&sampler_info, None)
            .map_err(|e| format!("Create sampler failed: {:?}", e))?;

        // --- Create staging buffer (persistently mapped) ---
        let buffer_info = vk::BufferCreateInfo::default()
            .size(frame_size)
            .usage(vk::BufferUsageFlags::TRANSFER_SRC)
            .sharing_mode(vk::SharingMode::EXCLUSIVE);

        let staging_buffer = device
            .create_buffer(&buffer_info, None)
            .map_err(|e| format!("Create staging buffer failed: {:?}", e))?;

        let buf_mem_reqs = device.get_buffer_memory_requirements(staging_buffer);

        let staging_mem_type = find_memory_type(
            &mem_props,
            buf_mem_reqs.memory_type_bits,
            vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT,
        )
        .ok_or_else(|| "No host-visible memory for staging buffer".to_string())?;

        let staging_alloc = vk::MemoryAllocateInfo::default()
            .allocation_size(buf_mem_reqs.size)
            .memory_type_index(staging_mem_type);

        let staging_memory = device
            .allocate_memory(&staging_alloc, None)
            .map_err(|e| format!("Allocate staging memory failed: {:?}", e))?;

        device
            .bind_buffer_memory(staging_buffer, staging_memory, 0)
            .map_err(|e| format!("Bind staging memory failed: {:?}", e))?;

        // Persistently map the staging buffer
        let staging_ptr = device
            .map_memory(staging_memory, 0, frame_size, vk::MemoryMapFlags::empty())
            .map_err(|e| format!("Map staging memory failed: {:?}", e))?
            as *mut u8;

        // --- Create descriptor pool and set ---
        let pool_sizes = [
            vk::DescriptorPoolSize {
                ty: vk::DescriptorType::SAMPLED_IMAGE,
                descriptor_count: 1,
            },
            vk::DescriptorPoolSize {
                ty: vk::DescriptorType::SAMPLER,
                descriptor_count: 1,
            },
        ];

        let pool_info = vk::DescriptorPoolCreateInfo::default()
            .max_sets(1)
            .pool_sizes(&pool_sizes);

        let descriptor_pool = device
            .create_descriptor_pool(&pool_info, None)
            .map_err(|e| format!("Create descriptor pool failed: {:?}", e))?;

        let alloc_info = vk::DescriptorSetAllocateInfo::default()
            .descriptor_pool(descriptor_pool)
            .set_layouts(std::slice::from_ref(&descriptor_set_layout));

        let descriptor_sets = device
            .allocate_descriptor_sets(&alloc_info)
            .map_err(|e| format!("Allocate descriptor set failed: {:?}", e))?;

        let descriptor_set = descriptor_sets[0];

        // --- Transition image to SHADER_READ_ONLY and clear to black ---
        transition_and_clear(device, queue, command_pool, image, width, height)?;

        // --- Update descriptor set: binding 0 = image, binding 1 = sampler ---
        let image_info_desc = vk::DescriptorImageInfo {
            sampler: vk::Sampler::null(),
            image_view,
            image_layout: vk::ImageLayout::SHADER_READ_ONLY_OPTIMAL,
        };

        let sampler_info_desc = vk::DescriptorImageInfo {
            sampler,
            image_view: vk::ImageView::null(),
            image_layout: vk::ImageLayout::UNDEFINED,
        };

        let writes = [
            vk::WriteDescriptorSet::default()
                .dst_set(descriptor_set)
                .dst_binding(0)
                .descriptor_type(vk::DescriptorType::SAMPLED_IMAGE)
                .image_info(std::slice::from_ref(&image_info_desc)),
            vk::WriteDescriptorSet::default()
                .dst_set(descriptor_set)
                .dst_binding(1)
                .descriptor_type(vk::DescriptorType::SAMPLER)
                .image_info(std::slice::from_ref(&sampler_info_desc)),
        ];

        device.update_descriptor_sets(&writes, &[]);

        vlog!(
            "VideoTexture created: {}x{} staging={}KB",
            width,
            height,
            frame_size / 1024
        );

        Ok(Self {
            image,
            image_memory,
            image_view,
            sampler,
            staging_buffer,
            staging_memory,
            staging_ptr,
            descriptor_pool,
            descriptor_set,
            width,
            height,
            initialized: true,
        })
    }

    /// Upload frame data to the texture.
    ///
    /// Copies RGBA data to the staging buffer, then records commands to
    /// transfer it to the device-local image.
    ///
    /// # Safety
    /// - `cmd` must be a command buffer in the recording state
    /// - `frame_data` must be exactly width * height * 4 bytes
    pub unsafe fn upload_frame(&self, device: &ash::Device, cmd: vk::CommandBuffer, frame_data: &[u8]) {
        let frame_size = (self.width * self.height * 4) as usize;
        debug_assert_eq!(frame_data.len(), frame_size);

        // Copy to staging buffer (persistently mapped, HOST_COHERENT = no flush needed)
        std::ptr::copy_nonoverlapping(frame_data.as_ptr(), self.staging_ptr, frame_size);

        // Transition image: SHADER_READ_ONLY → TRANSFER_DST
        let barrier = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::SHADER_READ)
            .dst_access_mask(vk::AccessFlags::TRANSFER_WRITE)
            .old_layout(vk::ImageLayout::SHADER_READ_ONLY_OPTIMAL)
            .new_layout(vk::ImageLayout::TRANSFER_DST_OPTIMAL)
            .image(self.image)
            .subresource_range(color_subresource_range());

        device.cmd_pipeline_barrier(
            cmd,
            vk::PipelineStageFlags::FRAGMENT_SHADER,
            vk::PipelineStageFlags::TRANSFER,
            vk::DependencyFlags::empty(),
            &[],
            &[],
            &[barrier],
        );

        // Copy staging buffer → image
        let region = vk::BufferImageCopy {
            buffer_offset: 0,
            buffer_row_length: 0,   // tightly packed
            buffer_image_height: 0, // tightly packed
            image_subresource: vk::ImageSubresourceLayers {
                aspect_mask: vk::ImageAspectFlags::COLOR,
                mip_level: 0,
                base_array_layer: 0,
                layer_count: 1,
            },
            image_offset: vk::Offset3D { x: 0, y: 0, z: 0 },
            image_extent: vk::Extent3D {
                width: self.width,
                height: self.height,
                depth: 1,
            },
        };

        device.cmd_copy_buffer_to_image(
            cmd,
            self.staging_buffer,
            self.image,
            vk::ImageLayout::TRANSFER_DST_OPTIMAL,
            &[region],
        );

        // Transition image: TRANSFER_DST → SHADER_READ_ONLY
        let barrier = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::TRANSFER_WRITE)
            .dst_access_mask(vk::AccessFlags::SHADER_READ)
            .old_layout(vk::ImageLayout::TRANSFER_DST_OPTIMAL)
            .new_layout(vk::ImageLayout::SHADER_READ_ONLY_OPTIMAL)
            .image(self.image)
            .subresource_range(color_subresource_range());

        device.cmd_pipeline_barrier(
            cmd,
            vk::PipelineStageFlags::TRANSFER,
            vk::PipelineStageFlags::FRAGMENT_SHADER,
            vk::DependencyFlags::empty(),
            &[],
            &[],
            &[barrier],
        );
    }

    /// Destroy all resources.
    ///
    /// # Safety
    /// Device must be idle. All handles must be valid.
    pub unsafe fn destroy(&self, device: &ash::Device) {
        device.unmap_memory(self.staging_memory);
        device.destroy_buffer(self.staging_buffer, None);
        device.free_memory(self.staging_memory, None);
        device.destroy_sampler(self.sampler, None);
        device.destroy_image_view(self.image_view, None);
        device.destroy_image(self.image, None);
        device.free_memory(self.image_memory, None);
        device.destroy_descriptor_pool(self.descriptor_pool, None);
        vlog!("VideoTexture destroyed");
    }
}

/// Create the descriptor set layout for the video texture binding.
///
/// Layout:
/// - set=0, binding=0: sampled image (texture_2d<f32>), fragment stage
/// - set=0, binding=1: sampler, fragment stage
///
/// # Safety
/// Device must be valid.
pub unsafe fn create_descriptor_set_layout(
    device: &ash::Device,
) -> Result<vk::DescriptorSetLayout, String> {
    let bindings = [
        vk::DescriptorSetLayoutBinding {
            binding: 0,
            descriptor_type: vk::DescriptorType::SAMPLED_IMAGE,
            descriptor_count: 1,
            stage_flags: vk::ShaderStageFlags::FRAGMENT,
            p_immutable_samplers: std::ptr::null(),
            ..Default::default()
        },
        vk::DescriptorSetLayoutBinding {
            binding: 1,
            descriptor_type: vk::DescriptorType::SAMPLER,
            descriptor_count: 1,
            stage_flags: vk::ShaderStageFlags::FRAGMENT,
            p_immutable_samplers: std::ptr::null(),
            ..Default::default()
        },
    ];

    let layout_info = vk::DescriptorSetLayoutCreateInfo::default().bindings(&bindings);

    device
        .create_descriptor_set_layout(&layout_info, None)
        .map_err(|e| format!("Create descriptor set layout failed: {:?}", e))
}

// --- Helpers ---

/// Standard color subresource range.
fn color_subresource_range() -> vk::ImageSubresourceRange {
    vk::ImageSubresourceRange {
        aspect_mask: vk::ImageAspectFlags::COLOR,
        base_mip_level: 0,
        level_count: 1,
        base_array_layer: 0,
        layer_count: 1,
    }
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

/// Transition image to SHADER_READ_ONLY and clear to black.
///
/// Uses a one-shot command buffer.
unsafe fn transition_and_clear(
    device: &ash::Device,
    queue: vk::Queue,
    command_pool: vk::CommandPool,
    image: vk::Image,
    _width: u32,
    _height: u32,
) -> Result<(), String> {
    // Allocate a one-shot command buffer
    let alloc_info = vk::CommandBufferAllocateInfo::default()
        .command_pool(command_pool)
        .level(vk::CommandBufferLevel::PRIMARY)
        .command_buffer_count(1);

    let cmd_bufs = device
        .allocate_command_buffers(&alloc_info)
        .map_err(|e| format!("Allocate init cmd buf failed: {:?}", e))?;
    let cmd = cmd_bufs[0];

    let begin_info =
        vk::CommandBufferBeginInfo::default().flags(vk::CommandBufferUsageFlags::ONE_TIME_SUBMIT);
    device
        .begin_command_buffer(cmd, &begin_info)
        .map_err(|e| format!("Begin init cmd buf failed: {:?}", e))?;

    // Transition: UNDEFINED → TRANSFER_DST
    let barrier = vk::ImageMemoryBarrier::default()
        .src_access_mask(vk::AccessFlags::empty())
        .dst_access_mask(vk::AccessFlags::TRANSFER_WRITE)
        .old_layout(vk::ImageLayout::UNDEFINED)
        .new_layout(vk::ImageLayout::TRANSFER_DST_OPTIMAL)
        .image(image)
        .subresource_range(color_subresource_range());

    device.cmd_pipeline_barrier(
        cmd,
        vk::PipelineStageFlags::TOP_OF_PIPE,
        vk::PipelineStageFlags::TRANSFER,
        vk::DependencyFlags::empty(),
        &[],
        &[],
        &[barrier],
    );

    // Clear to black
    let clear_color = vk::ClearColorValue {
        float32: [0.0, 0.0, 0.0, 1.0],
    };
    device.cmd_clear_color_image(
        cmd,
        image,
        vk::ImageLayout::TRANSFER_DST_OPTIMAL,
        &clear_color,
        &[color_subresource_range()],
    );

    // Transition: TRANSFER_DST → SHADER_READ_ONLY
    let barrier = vk::ImageMemoryBarrier::default()
        .src_access_mask(vk::AccessFlags::TRANSFER_WRITE)
        .dst_access_mask(vk::AccessFlags::SHADER_READ)
        .old_layout(vk::ImageLayout::TRANSFER_DST_OPTIMAL)
        .new_layout(vk::ImageLayout::SHADER_READ_ONLY_OPTIMAL)
        .image(image)
        .subresource_range(color_subresource_range());

    device.cmd_pipeline_barrier(
        cmd,
        vk::PipelineStageFlags::TRANSFER,
        vk::PipelineStageFlags::FRAGMENT_SHADER,
        vk::DependencyFlags::empty(),
        &[],
        &[],
        &[barrier],
    );

    device
        .end_command_buffer(cmd)
        .map_err(|e| format!("End init cmd buf failed: {:?}", e))?;

    // Submit and wait
    let cmd_bufs_ref = [cmd];
    let submit_info = vk::SubmitInfo::default().command_buffers(&cmd_bufs_ref);

    device
        .queue_submit(queue, &[submit_info], vk::Fence::null())
        .map_err(|e| format!("Submit init cmd buf failed: {:?}", e))?;

    device
        .queue_wait_idle(queue)
        .map_err(|e| format!("Queue wait idle failed: {:?}", e))?;

    // Free the one-shot command buffer
    device.free_command_buffers(command_pool, &[cmd]);

    Ok(())
}
