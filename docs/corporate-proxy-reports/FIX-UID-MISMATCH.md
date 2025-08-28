# Corporate Proxy UID Mismatch Fix

## Problem
The Crush and OpenCode corporate proxy tools were not executing file operations (read, write, ls) when invoked through the corporate AI API. The tools would appear to run but nothing would actually happen.

## Root Cause
**UID mismatch** between the host and container users:
- Both containers create an `appuser` with UID 1001
- Host systems typically use UID 1000 for the primary user
- When mounting host directories with `-v "$(pwd):/workspace:rw"`, files retain host user permissions
- Container's appuser (UID 1001) cannot write to files owned by host user (UID 1000)
- Tools execute but fail silently due to permission denied errors

## Solution
Run containers with the host user's UID/GID using Docker's `--user` flag:

```bash
docker run --user "$(id -u):$(id -g)" ...
```

This ensures the container process runs with the same UID as the host user, allowing proper file access.

## Files Modified

### Crush Scripts
- `crush/scripts/run.sh` - Main run script
- Added `--user "$(id -u):$(id -g)"` to docker run commands
- Added `HOME=/tmp` and `USER="$(whoami)"` environment variables

### OpenCode Scripts
- `opencode/scripts/run.sh` - Main run script
- `opencode/scripts/run-interactive.sh` - Interactive mode
- `opencode/scripts/run-production.sh` - Production mode
- Same modifications as Crush scripts

## Testing
Use the test script to verify file operations work correctly:

```bash
./automation/corporate-proxy/test-file-operations.sh
```

This script:
1. Creates a temporary directory
2. Tests Crush file creation
3. Tests OpenCode file creation
4. Verifies both tools can write files successfully

## Important Notes
- This fix maintains security by not running as root
- Works across different host systems regardless of their UID configuration
- No changes needed to the Dockerfiles themselves
- Existing container images can be used as-is

## Alternative Solutions (Not Used)
1. **Modify Dockerfile UIDs** - Would require rebuilding for each host system
2. **Dynamic UID mapping** - Complex entrypoint scripts needed
3. **Run as root** - Security risk, not recommended
4. **Use Docker user namespaces** - Requires Docker daemon configuration changes
