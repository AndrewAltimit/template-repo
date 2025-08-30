# Corporate Certificate Installation

## Overview

The `install-corporate-certs.sh` script is a placeholder for installing corporate certificates in Docker containers. This allows organizations to inject their custom certificates without modifying Dockerfiles.

## How It Works

1. The script is copied and executed as root after each `FROM` statement in Dockerfiles
2. It runs before any package installations to ensure certificates are available
3. The script is removed after execution to keep the image clean

## Customization

Replace `install-corporate-certs.sh` with your organization's certificate installation process. Common customizations include:

### 1. Installing Corporate CA Certificates

```bash
# Copy corporate CA certificates
cp /path/to/company-ca.crt /usr/local/share/ca-certificates/
update-ca-certificates
```

### 2. Configuring Package Manager Proxies

```bash
# For Alpine (APK)
echo "http://proxy.company.com:8080" > /etc/apk/proxy

# For Debian/Ubuntu (APT)
echo "Acquire::http::Proxy \"http://proxy.company.com:8080\";" > /etc/apt/apt.conf.d/proxy.conf
```

### 3. Setting System-wide Proxy

```bash
cat >> /etc/environment << END
https_proxy=https://proxy.company.com:8080
http_proxy=http://proxy.company.com:8080
no_proxy=localhost,127.0.0.1,.company.com
END
```

### 4. Language-specific Certificate Configuration

```bash
# Python
pip config set global.cert /path/to/cert.pem

# Node.js
npm config set cafile /path/to/cert.pem

# Go
export GOPROXY=https://proxy.company.com
```

## Best Practices

1. **Keep it idempotent**: Script should work if run multiple times
2. **Handle errors gracefully**: Use `|| true` for non-critical operations
3. **Minimize output**: Only log important information
4. **Clean up**: Remove temporary files after use
5. **Test thoroughly**: Verify certificates work across all build stages

## Example Implementation

```bash
#!/bin/sh
set -e

echo "Installing corporate certificates..."

# 1. Update package manager certificates
if [ -f /etc/apk/repositories ]; then
    sed -i 's|dl-cdn.alpinelinux.org|internal-mirror.company.com|g' /etc/apk/repositories
fi

# 2. Install CA certificates
if [ -d /usr/local/share/ca-certificates ]; then
    cp /corporate-certs/*.crt /usr/local/share/ca-certificates/ 2>/dev/null || true
    update-ca-certificates 2>/dev/null || true
fi

# 3. Configure proxy
export https_proxy="${CORPORATE_PROXY:-https://proxy.company.com:8080}"
export http_proxy="${CORPORATE_PROXY:-http://proxy.company.com:8080}"
export no_proxy="${NO_PROXY:-localhost,127.0.0.1,.company.com}"

echo "Certificate installation complete."
```

## Testing

After customizing the script, test your builds:

```bash
# Build with your custom certificates
docker build --no-cache -f automation/corporate-proxy/crush/docker/Dockerfile .

# Verify certificates are installed
docker run --rm image_name sh -c "ls -la /usr/local/share/ca-certificates/"
```

## Troubleshooting

If builds fail after adding certificates:

1. **Check script syntax**: Run `sh -n install-corporate-certs.sh`
2. **Verify paths**: Ensure certificate paths exist in the container
3. **Test incrementally**: Add one certificate type at a time
4. **Check logs**: Add debug output temporarily with `set -x`
5. **Validate certificates**: Ensure certificates are in correct format (PEM/CRT)

## Security Notes

- Never commit actual certificates to the repository
- Use Docker secrets or build arguments for sensitive data
- Rotate certificates regularly
- Document certificate sources for audit purposes
