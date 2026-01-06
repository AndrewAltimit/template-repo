# Multi-Architecture Support for Corporate Proxy Containers

## Overview

All corporate proxy containers now support multiple architectures with automatic detection. This enables seamless deployment across different hardware platforms including:

- **amd64** (x86_64) - Intel/AMD 64-bit processors
- **arm64** (aarch64) - ARM 64-bit processors (Apple Silicon, AWS Graviton, Raspberry Pi 4)
- **arm** (armv7l) - ARM 32-bit processors (older Raspberry Pi)

## Architecture Auto-Detection

The build scripts automatically detect your system architecture using `uname -m` and map it to Docker's platform naming:

| System Architecture | Docker Platform |
|-------------------|-----------------|
| x86_64 | linux/amd64 |
| aarch64, arm64 | linux/arm64 |
| armv7l | linux/arm |

## Building Containers

### Build All Containers

```bash
# Auto-detect architecture and build all containers
./build-all.sh

# Build for specific architecture
TARGETARCH=arm64 ./build-all.sh

# Build specific container
./build-all.sh gemini
./build-all.sh opencode
./build-all.sh crush
```

### Individual Container Builds

Each container can be built individually with architecture auto-detection:

```bash
# Gemini CLI
cd gemini/scripts
./build.sh

# OpenCode
cd opencode/scripts
./build.sh

# Crush
cd crush/scripts
./build.sh
```

### Override Architecture

To build for a different architecture than your host:

```bash
# Build for ARM64 on an AMD64 host
TARGETARCH=arm64 ./build.sh

# Build for AMD64 on an ARM64 host (e.g., Apple Silicon)
TARGETARCH=amd64 ./build.sh
```

## Docker Buildx Support

The build scripts automatically detect and use Docker Buildx when available for enhanced multi-platform support:

- **With Buildx**: Uses `docker buildx build --platform` for true cross-platform builds
- **Without Buildx**: Falls back to standard `docker build` for native architecture

To enable Buildx:

```bash
# Install buildx (usually included with Docker Desktop)
docker buildx version

# Create a multi-arch builder
docker buildx create --use --name multiarch-builder

# List available builders
docker buildx ls
```

## Container-Specific Architecture Notes

### Gemini CLI Container
- **Architecture-independent**: Built from Node.js source
- Works on all supported architectures without modification

### OpenCode Container
- **Go Binary**: Compiles TUI component for target architecture
- Uses Go cross-compilation with `GOARCH` environment variable
- Binary naming: `tui-linux-${TARGETARCH}`

### Crush Container
- **Pre-built Binaries**: Downloads architecture-specific releases
- Mapping:
  - amd64 → x86_64 binary
  - arm64 → aarch64 binary
- Note: Check [Crush releases](https://github.com/charmbracelet/crush/releases) for architecture availability

## Verification

After building, verify the container architecture:

```bash
# Check image architecture
docker inspect <image-name> | grep Architecture

# Run a test command
docker run --rm <image-name> uname -m
```

## CI/CD Integration

For CI/CD pipelines, explicitly specify the target architecture:

```yaml
# GitHub Actions example
- name: Build containers
  env:
    TARGETARCH: ${{ matrix.arch }}
  run: |
    ./automation/corporate-proxy/build-all.sh
  strategy:
    matrix:
      arch: [amd64, arm64]
```

## Troubleshooting

### Common Issues

1. **"Unsupported architecture" warning**
   - The script defaults to amd64 for unknown architectures
   - Manually specify using `TARGETARCH` environment variable

2. **Build fails on different architecture**
   - Ensure Docker Buildx is installed for cross-platform builds
   - Some base images may not support all architectures

3. **Binary not found in container**
   - Check if upstream project provides binaries for your architecture
   - May need to build from source for unsupported architectures

### Architecture Compatibility Matrix

| Container | amd64 | arm64 | arm32 | Notes |
|-----------|-------|-------|-------|-------|
| Gemini CLI | Yes | Yes | Yes | Node.js based, fully portable |
| OpenCode | Yes | Yes | Untested | Go compilation, arm32 untested |
| Crush | Yes | Yes | No | Pre-built binaries, arm32 not available |

## Development Tips

### Testing Multi-Architecture Builds

```bash
# Test build for multiple architectures (requires buildx)
docker buildx build --platform linux/amd64,linux/arm64 -t myimage:latest .

# Use QEMU for testing other architectures
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# Test ARM64 container on AMD64 host
docker run --platform linux/arm64 --rm myimage:latest
```

### Local Development

For local development, always use native architecture for best performance:

```bash
# Let auto-detection handle it
./build.sh

# Or explicitly use native
TARGETARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') ./build.sh
```

## Future Enhancements

- [ ] Add support for more architectures (ppc64le, s390x)
- [ ] Implement manifest lists for true multi-arch images
- [ ] Add architecture-specific optimization flags
- [ ] Create pre-built images for common architectures
- [ ] Add automated testing across architectures
