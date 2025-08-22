# OpenCode Proxy with Models.dev Interception

This is the **ultimate solution** for limiting OpenCode's model display to only your proxy models!

## 🎉 What's New

We now intercept **BOTH**:
1. **API calls** to OpenRouter (already working)
2. **models.dev API** to limit the displayed model list (NEW!)

## How It Works

```
OpenCode → models.dev request
    ↓
/etc/hosts redirect to 127.0.0.1:8052
    ↓
Our proxy returns LIMITED model list (only 3 models)
    ↓
OpenCode displays ONLY those 3 models!
```

## Running the Interceptor

### Build the Image
```bash
docker build -f docker/openrouter-agents-proxy.Dockerfile -t openrouter-agents-proxy:interceptor .
```

### Run with Full Interception
```bash
# Run as root to allow /etc/hosts modification
docker run --rm -it \
    --privileged \
    -v "$(pwd):/workspace" \
    openrouter-agents-proxy:interceptor
```

**Important**: The `--privileged` flag or running as root is required to modify `/etc/hosts` for the interception.

### What You'll See

```
╔════════════════════════════════════════════════════╗
║       🎭 COMPANY PROXY WITH INTERCEPTION           ║
╠════════════════════════════════════════════════════╣
║ ✨ NEW: Models list now intercepted!               ║
║                                                     ║
║ Only these 3 models will be shown AND work:        ║
║                                                     ║
║ ✅ openrouter/anthropic/claude-3.5-sonnet          ║
║ ✅ openrouter/anthropic/claude-3-opus              ║
║ ✅ openrouter/openai/gpt-4                         ║
║                                                     ║
║ 🚀 models.dev → localhost:8052 (intercepted)       ║
╚════════════════════════════════════════════════════╝
```

## Key Features

1. **Complete Interception**: Both API calls AND model list
2. **Clean UI**: OpenCode shows ONLY the 3 proxy models
3. **Automatic Setup**: hosts file modification handled automatically
4. **Cache Clearing**: Removes OpenCode's cached models to force refresh

## How the Interception Works

### 1. API Translation Wrapper Enhancement
The `api_translation_wrapper.py` now includes:
```python
@app.route("/api.json", methods=["GET"])
def models_api():
    """Return only our 3 proxy models"""
    return jsonify(limited_models)
```

### 2. Hosts File Redirection
The script adds to `/etc/hosts`:
```
127.0.0.1 models.dev
```

### 3. Cache Clearing
Removes `~/.cache/opencode/models.json` to force OpenCode to fetch fresh data.

## Testing Locally

```bash
# Test the interceptor endpoint
./automation/proxy/test-interceptor.sh

# Expected output:
# Found 3 models:
#   - openrouter/anthropic/claude-3.5-sonnet
#   - openrouter/anthropic/claude-3-opus
#   - openrouter/openai/gpt-4
```

## Troubleshooting

### Issue: Still seeing all models
**Solution**:
1. Ensure container is running with `--privileged`
2. Check if `/etc/hosts` was modified: `cat /etc/hosts | grep models.dev`
3. Clear OpenCode cache: `rm -rf ~/.cache/opencode/`

### Issue: Permission denied on /etc/hosts
**Solution**: Run container with `--privileged` or as root user

### Issue: Models.dev not being intercepted
**Solution**: Verify the wrapper is running on port 8052:
```bash
curl http://localhost:8052/api.json
```

## Technical Details

### Components Modified

1. **api_translation_wrapper.py**
   - Added `/api.json` route
   - Returns limited model list

2. **opencode-proxy-interceptor.sh**
   - Modifies `/etc/hosts`
   - Clears OpenCode cache
   - Starts services with interception

3. **openrouter-agents-proxy.Dockerfile**
   - Runs as root (for hosts file access)
   - Uses interceptor script

## Comparison with Other Approaches

| Approach | Shows Limited Models | Works | Complexity |
|----------|---------------------|--------|------------|
| Basic Proxy | ❌ | ✅ | Low |
| Wrapper with Banner | ❌ | ✅ | Low |
| Source Build | ❓ | ❓ | Very High |
| **Interceptor** | ✅ | ✅ | Medium |

## Success!

With this interceptor approach, OpenCode will:
- ✅ Show ONLY the 3 proxy models in its list
- ✅ Route all requests through your proxy
- ✅ Work with mock or real company API
- ✅ Provide a clean, professional interface

This is the complete solution you were looking for!
