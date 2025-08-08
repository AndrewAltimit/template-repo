# Meme Upload and Sharing Guide

## Overview

The meme generator now includes **automatic upload functionality** that provides shareable URLs for generated memes. This means AI agents and users can instantly share memes without dealing with file attachments or manual uploads.

## How It Works

When you generate a meme, the system:
1. Creates a full-size PNG image
2. Automatically uploads it to a free hosting service
3. Returns a shareable URL in the response
4. Also includes a thumbnail for visual confirmation

## Usage

### Basic Usage (Auto-Upload Enabled by Default)

```python
# Via MCP Tool
result = await mcp.generate_meme(
    template="ol_reliable",
    texts={
        "top": "When you need to share a meme",
        "bottom": "Upload built-in"
    }
)

# Response includes:
# - output_path: Local file path
# - share_url: https://0x0.st/XXXX.png (ready to share!)
# - visual_feedback: Thumbnail for preview
```

### Disable Upload (Local Only)

```python
result = await mcp.generate_meme(
    template="ol_reliable",
    texts={"top": "Local only", "bottom": "No upload"},
    upload=False  # Disable upload
)
```

## Upload Services

The system uses free, no-authentication services:

### Primary: 0x0.st
- **No authentication required**
- **File retention**: 365 days for files <512KB, shorter for larger
- **Max size**: 512MB (but we limit to reasonable sizes)
- **Direct URLs**: Clean, shareable links

### Fallback: file.io (if implemented)
- **No authentication required**
- **Configurable expiration**: 1 day to 1 month
- **Good for temporary shares**

## For AI Agents

### Sharing Memes in GitHub Comments

```python
# Generate meme with auto-upload
result = mcp.generate_meme(
    template="ol_reliable",
    texts={"top": "When PR needs validation", "bottom": "Generate a meme"}
)

# Get the share URL
share_url = result.get("share_url")  # e.g., https://0x0.st/8FrM.png

# Use in GitHub comment
comment = f"![Validation Meme]({share_url})"
gh.pr.comment(comment)
```

### Response Structure

```json
{
    "success": true,
    "output_path": "/local/path/to/meme.png",
    "share_url": "https://0x0.st/XXXX.png",  // <-- Shareable URL!
    "upload_info": {
        "service": "0x0.st",
        "note": "Link expires based on file size (365 days for <512KB)"
    },
    "visual_feedback": {
        "format": "webp",
        "encoding": "base64",
        "data": "...",  // Small thumbnail
        "size_kb": 4.8
    },
    "full_size_kb": 1344.6,
    "message": "Meme generated and saved to /path/meme.png\n🔗 Share URL: https://0x0.st/XXXX.png"
}
```

## Error Handling

The upload feature is **non-blocking**:
- If upload fails, the meme is still generated locally
- Error info is included in `upload_error` field
- Local path is always available as fallback

## Implementation Details

### Upload Module (`upload.py`)

The `MemeUploader` class handles:
- Service selection (auto tries multiple services)
- Proper curl commands with correct user agents
- Error handling and fallbacks
- File size validation

### Integration Points

1. **tools.py**: `generate_meme()` function includes upload logic
2. **server.py**: MCP server exposes upload parameter
3. **upload.py**: Standalone upload utilities

## Best Practices

### For Developers
1. **Always check for `share_url`** in response before falling back to local path
2. **Include upload status** in logs for debugging
3. **Test with different file sizes** (0x0.st has size-based retention)

### For AI Agents
1. **Use share URLs directly** in markdown: `![Alt text](share_url)`
2. **Mention expiration** if relevant (e.g., "This link expires in 365 days")
3. **Fall back gracefully** if upload fails - use local path description

## Troubleshooting

### Upload Failed?
1. Check file size (most services limit to 512MB)
2. Verify curl is installed and accessible
3. Check network connectivity
4. Review `upload_error` field in response

### Wrong Service?
You can force a specific service:
```python
# In upload.py, change service parameter:
MemeUploader.upload(file_path, service="0x0st")  # Force 0x0.st
```

## Examples

### GitHub PR Comment
```markdown
## Validation Complete ✅

I tested the feature and it works!

![Test Result](https://0x0.st/XXXX.png)
```

### Discord/Slack Share
```
Check out this meme: https://0x0.st/XXXX.png
```

### Documentation
```markdown
### Example Output
![Example](https://0x0.st/XXXX.png)
*Generated with the meme generator tool*
```

## Security Notes

- **No authentication stored**: Services used require no API keys
- **No PII**: Don't put sensitive info in memes
- **Public URLs**: Anyone with the link can view
- **Temporary storage**: Files expire automatically

## Future Enhancements

Potential improvements:
- Add more hosting services (imgur with optional API key)
- Custom expiration settings
- URL shortening integration
- Batch upload support
- CDN integration for permanent storage

## Summary

The upload feature makes meme sharing seamless:
1. **Zero configuration** - Works out of the box
2. **Automatic** - Uploads by default
3. **Reliable** - Fallbacks ensure it always works
4. **Agent-friendly** - Returns ready-to-use URLs

Now agents can generate AND share memes with a single tool call! 🚀
