# OpenCode Company Integration - Maintenance Guide

## Overview

This document addresses maintenance concerns and patterns identified during code review, helping future developers understand and maintain the OpenCode Company integration.

## Critical Dependencies and Update Procedures

### 1. OpenCode Version Updates

The integration patches specific OpenCode source files. When updating OpenCode:

1. **Update the version** in `docker/opencode-company-tui.Dockerfile`:
   ```dockerfile
   ARG OPENCODE_VERSION=<new-commit-hash>
   ```

2. **Test patch compatibility**:
   ```bash
   # Build with new version
   docker build --build-arg OPENCODE_VERSION=<hash> -f docker/opencode-company-tui.Dockerfile -t test-update .
   ```

3. **If patches fail**, examine the upstream changes and update:
   - `docker/patches/models-company-simple.ts` - Models limiting logic
   - `docker/patches/tui-company-fix.ts` - TUI binary path resolution
   - `docker/patches/company-override.json` - Provider configuration

### 2. Path Dependencies

The following files have tightly coupled path dependencies that must be updated together:

| Component | File | Hardcoded Path | Notes |
|-----------|------|----------------|-------|
| TUI Binary | `docker/patches/tui-company-fix.ts` | `/home/bun/.cache/opencode/tui/tui-linux-x64` | Must match Dockerfile COPY destination |
| Config | `docker/opencode-company-tui.Dockerfile` | `/home/bun/.config/opencode/.opencode.json` | Referenced by entrypoint script |
| TUI Cache | `docker/opencode-company-tui.Dockerfile` | `/home/bun/.cache/opencode/tui/` | Directory structure for TUI binaries |

**⚠️ WARNING**: If you change any path in the Dockerfile, update the corresponding patch files.

## Security Considerations

### API Key Management

The current implementation uses a mock API key (`sk-company-mock-api-key-123`) hardcoded in the Dockerfile for convenience. This is acceptable because:

1. **Mock key is non-functional** - Only works with mock services
2. **Production keys are injected** - Real keys come from environment variables
3. **Scripts override defaults** - All run scripts properly set credentials

#### Best Practices for Production

For maximum security in production environments:

1. **Never commit real API keys**
2. **Use secrets management** (Docker secrets, Kubernetes secrets, etc.)
3. **Rotate keys regularly**
4. **Audit container startup logs** to ensure no key leakage

#### Alternative Approach (More Secure)

If you need enhanced security, modify the entrypoint to always inject the key:

```bash
# In docker/entrypoints/opencode-entrypoint.sh
CONFIG_FILE="/home/bun/.config/opencode/.opencode.json"
if [ -n "$OPENROUTER_API_KEY" ]; then
    # Create config with runtime key instead of using hardcoded
    cat > "$CONFIG_FILE" <<EOF
{
  "provider": {
    "openrouter": {
      "options": {
        "apiKey": "$OPENROUTER_API_KEY"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
EOF
fi
```

## Maintenance Checklist

### Monthly Tasks
- [ ] Check for OpenCode updates
- [ ] Review security advisories
- [ ] Test with latest base images

### When Updating OpenCode
- [ ] Pin new version hash in Dockerfile
- [ ] Test all patches apply cleanly
- [ ] Verify TUI functionality
- [ ] Test mock mode
- [ ] Test production mode
- [ ] Update this documentation if needed

### When Modifying Paths
- [ ] Update Dockerfile COPY destinations
- [ ] Update patch files with new paths
- [ ] Update entrypoint script path references
- [ ] Test complete build and runtime

## Known Limitations and Trade-offs

### 1. Patch-Based Approach

**Trade-off**: Patches vs Fork
- **Current**: Patches allow quick updates but may break
- **Alternative**: Fork provides control but requires maintenance
- **STRONG RECOMMENDATION**: Create a fork for production use
  - Patches are brittle and tightly coupled to OpenCode internals
  - TUI patch especially fragile (hardcoded paths)
  - Fork would eliminate surprise breakage from upstream changes
  - Short-term pain (fork setup) for long-term gain (stability)

### 2. Simulated Streaming

**Limitation**: Response buffering
- Company API doesn't support streaming
- Wrapper simulates SSE format but buffers complete response
- Users may experience delay for long responses

### 3. Architecture-Specific Builds

**Optimization**: Single architecture per image
- Reduces image size by ~50%
- Requires building for target platform
- Use `--platform` flag for cross-platform builds

## Troubleshooting Guide

### Common Issues

1. **TUI fails to start**
   - Check: TUI binary exists at `/home/bun/.cache/opencode/tui/tui-linux-x64`
   - Check: Binary has execute permissions
   - Check: Architecture matches (amd64 vs arm64)

2. **API calls fail**
   - Check: Wrapper port configuration matches
   - Check: Services started successfully (check logs)
   - Check: Config file updated with correct port

3. **Patches fail to apply**
   - OpenCode source has changed
   - Need to update patch files
   - Consider creating a fork

### Debug Commands

```bash
# Check service status inside container
ps aux | grep -E '(mock_company|translation_wrapper)'

# View service logs
tail -f /tmp/mock_api.log
tail -f /tmp/wrapper.log

# Test wrapper directly
curl -X POST http://localhost:${WRAPPER_PORT:-8052}/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"company/claude-3.5-sonnet","messages":[{"role":"user","content":"test"}]}'

# Check OpenCode configuration
cat /home/bun/.config/opencode/.opencode.json
```

## Future Improvements

### High Priority
1. **CREATE OPENCODE FORK** - Critical for production stability
   - Current patches are brittle and will break with updates
   - Fork provides control over integration points
   - Strongly recommended by multiple code reviews
2. **Implement true streaming** - If company API adds support
3. **Monitor patch compatibility** - Until fork is created

### Nice to Have
1. **Multi-stage config** - Separate dev/staging/prod configs
2. **Metrics collection** - Track usage and performance
3. **Automated testing** - CI/CD for patch compatibility

## References

- [OpenCode Repository](https://github.com/sst/opencode)
- [Integration Documentation](../integrations/opencode-company-proxy.md)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

*Last Updated: 2024*
*Maintainer: AI Agent Collaboration Team*
