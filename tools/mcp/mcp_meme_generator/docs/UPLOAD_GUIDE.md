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

The system uses free, no-authentication services with automatic fallback:

### Primary: tmpfiles.org
- **Most reliable** - Works consistently in our testing
- **No authentication required**
- **File retention**: 1 hour of inactivity or max 30 days
- **Direct embed URLs**: Returns both page and direct image links
- **Best for GitHub**: Provides `/dl/` URLs for embedding

### Secondary: 0x0.st
- **No authentication required**
- **File retention**: 365 days for files <512KB, shorter for larger
- **Max size**: 512MB (but we limit to reasonable sizes)
- **Note**: Often blocks automated uploads (403 errors)

### Tertiary: file.io
- **No authentication required**
- **Configurable expiration**: 1 day to 1 month
- **Good for temporary shares**
- **Note**: May redirect or have connection issues

## For AI Agents

### Sharing Memes in GitHub Comments

```python
# Generate meme with auto-upload
result = mcp.generate_meme(
    template="ol_reliable",
    texts={"top": "When PR needs validation", "bottom": "Generate a meme"}
)

# Get the embed URL (preferred for GitHub)
embed_url = result.get("embed_url")  # Direct image link for embedding
share_url = result.get("share_url")  # Fallback if no embed_url

# Use in GitHub comment - embed_url displays image inline!
comment = f"![Validation Meme]({embed_url or share_url})"
gh.pr.comment(comment)
```

### Why Use embed_url?
- **Direct image display**: Shows inline in GitHub comments
- **No redirects**: Direct link to image file
- **Better UX**: Users see the meme immediately
- **Example**: `https://tmpfiles.org/dl/123456/meme.png` vs `http://tmpfiles.org/123456/meme.png`

### Response Structure

```json
{
    "success": true,
    "output_path": "/local/path/to/meme.png",
    "share_url": "http://tmpfiles.org/123456/meme.png",  // Page URL
    "embed_url": "https://tmpfiles.org/dl/123456/meme.png",  // Direct image for embedding!
    "upload_info": {
        "service": "tmpfiles.org",
        "note": "Link expires after 1 hour of inactivity or max 30 days",
        "embed_url": "https://tmpfiles.org/dl/123456/meme.png"
    },
    "visual_feedback": {
        "format": "webp",
        "encoding": "base64",
        "data": "...",  // Small thumbnail
        "size_kb": 4.8
    },
    "full_size_kb": 1344.6,
    "message": "Meme generated and saved to /path/meme.png\n🔗 Share URL: http://tmpfiles.org/123456/meme.png\n📎 Embed URL: https://tmpfiles.org/dl/123456/meme.png"
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

## GitHub Embedding Best Practices

### Quick Guide for AI Agents

1. **Always use embed_url when available**:
   ```python
   url = result.get("embed_url") or result.get("share_url")
   ```

2. **Format for GitHub comments**:
   ```markdown
   ![Description](https://tmpfiles.org/dl/123456/meme.png)
   ```

3. **Complete example**:
   ```python
   # Generate meme
   result = await mcp.generate_meme(
       template="ol_reliable",
       texts={"top": "Security issue", "bottom": "httpx library"}
   )

   # Get best URL for embedding
   url = result.get("embed_url") or result.get("share_url")

   # Create comment with embedded image
   comment = f"""
   ## Fixed the security issue! ✅

   ![Meme showing the fix]({url})

   Refactored to use httpx instead of subprocess.
   """

   # Post to GitHub
   gh pr comment 48 --body "{comment}"
   ```

## Examples

### GitHub PR Comment
```markdown
## Validation Complete ✅

I tested the feature and it works!

![Test Result](https://tmpfiles.org/dl/123456/meme.png)
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
