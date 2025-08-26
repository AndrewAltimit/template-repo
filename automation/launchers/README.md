# Automation Launchers

Centralized launcher scripts for various services and tools in the repository.

## Directory Structure

```
launchers/
├── windows/             # Windows-specific launchers
│   └── vrchat/          # VRChat Virtual Character MCP Server
│       ├── start_server_windows.bat      # Windows batch launcher
│       └── start_server_windows.ps1      # Windows PowerShell launcher
├── linux/               # Linux/Mac launchers
│   └── vrchat_server.sh # VRChat server launcher
└── README.md            # This file
```

## VRChat Virtual Character Server

Control VRChat avatars remotely via MCP server.

### Windows

**PowerShell (Recommended):**
```powershell
cd automation\launchers\windows\vrchat
.\start_server_windows.ps1
```

**Command Prompt:**
```cmd
cd automation\launchers\windows\vrchat
start_server_windows.bat
```

### Linux/Mac

```bash
./automation/launchers/linux/vrchat_server.sh
```

### Configuration

All launchers accept these parameters:
- **Port**: Server port (default: 8020)
- **Host**: Bind address (default: 0.0.0.0)

**PowerShell Example:**
```powershell
.\start_server_windows.ps1 -Port 8020 -Host 0.0.0.0
```

**Bash Example:**
```bash
./vrchat_server.sh 8020 0.0.0.0
```

### Features

- Auto-installs required Python packages
- Validates Python installation
- Shows available API endpoints
- Colored output for better readability
- Cross-platform support

### Remote Access

After starting the server, it will be accessible at:
- Local: `http://localhost:8020`
- Network: `http://<machine-ip>:8020`

Test the connection from another machine:
```bash
python tools/mcp/virtual_character/scripts/test_remote_server.py \
  --server http://<server-ip>:8020 \
  --test status
```

## Adding New Launchers

When adding new launcher scripts:

1. Create a subdirectory for your service
2. Add platform-specific launchers as needed
3. Update this README with usage instructions
4. Consider adding:
   - Dependency checks
   - Configuration validation
   - Colored output for readability
   - Error handling
   - Auto-restart capabilities

## Best Practices

- Use descriptive names for launcher scripts
- Include configuration options as parameters
- Add help/usage information
- Check dependencies before starting
- Provide clear error messages
- Support both interactive and non-interactive modes
