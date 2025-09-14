# Databricks Configuration

## versions.json

This file is the **single source of truth** for tool versions across the Databricks environment setup.

### Usage

The `versions.json` file is automatically loaded by:

1. **Python Package** (`dbr-env-all`): Loads at runtime from multiple search paths
2. **Shell Scripts** (`dbr-setup-post`): Uses `jq` to parse versions when available
3. **Dockerfiles**: Currently use ARG defaults, but can be overridden at build time

### Structure

```json
{
  "dbr15": {
    "python": "3.11",
    "databricks-cli": "0.245.0",
    "terraform": "1.11.2",
    "terragrunt": "0.77.0",
    "aws-cli": "2.22.25",
    "uv": "0.6.12"
  },
  "dbr16": {
    "python": "3.12",
    "databricks-cli": "0.256.0",
    "terraform": "1.12.2",
    "terragrunt": "0.81.10",
    "aws-cli": "2.22.25",
    "uv": "0.7.14"
  }
}
```

### Updating Versions

When updating tool versions:

1. Edit `versions.json` with the new versions
2. Update checksums in `checksums.txt` if binaries changed
3. Rebuild Docker images to pick up new versions
4. Reinstall Python packages to get updated version info

### Docker Build Override

While Dockerfiles have default ARG values for compatibility, you can override them at build time:

```bash
# Extract version from JSON and use in Docker build
DATABRICKS_VERSION=$(jq -r '.dbr15."databricks-cli"' config/versions.json)
docker build --build-arg DBX_CLI_VERSION=$DATABRICKS_VERSION ...
```

### Fallback Behavior

If `versions.json` is not found or `jq` is not available:
- Python packages use embedded fallback versions
- Shell scripts use hardcoded fallback versions
- Dockerfiles use their ARG defaults

This ensures the system remains functional even without the config file.
