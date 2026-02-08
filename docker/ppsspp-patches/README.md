# PPSSPP Source Patches

Place `.patch` files here to apply modifications to the PPSSPP source tree
during the Docker build. Patches are applied with `git apply` in alphabetical
order before CMake configuration.

## Creating a patch

```bash
# Clone PPSSPP, make changes, then:
cd ppsspp
git diff > ../docker/ppsspp-patches/001-my-feature.patch
```

## Naming convention

Prefix with a number to control application order:
- `001-http-control-api.patch`
- `002-screenshot-hook.patch`

## Intended use

MCP integration patches (HTTP control API, input injection hooks,
screenshot capture endpoints, memory inspection, etc.) will live here
so the container always builds with those capabilities.
