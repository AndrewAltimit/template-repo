#!/bin/bash
# Install actionlint for GitHub Actions workflow validation
# Usage: ./install-actionlint.sh [github_token]
#
# If github_token is provided, it's used for authenticated API calls to avoid rate limits.

set -e

GITHUB_TOKEN="${1:-}"

echo "Installing actionlint..."

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  ARCH_SUFFIX="amd64" ;;
  aarch64) ARCH_SUFFIX="arm64" ;;
  arm64)   ARCH_SUFFIX="arm64" ;;
  *)
    echo "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac
echo "Detected architecture: $ARCH -> $ARCH_SUFFIX"

# Fetch latest release version (with optional auth header for rate limiting)
CURL_ARGS=(-sf)
if [ -n "$GITHUB_TOKEN" ]; then
  CURL_ARGS+=(-H "Authorization: token $GITHUB_TOKEN")
fi

ACTIONLINT_VERSION=$(curl "${CURL_ARGS[@]}" \
  https://api.github.com/repos/rhysd/actionlint/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')

if [ -z "$ACTIONLINT_VERSION" ]; then
  echo "Failed to fetch actionlint version from GitHub API"
  exit 1
fi

echo "Installing actionlint v${ACTIONLINT_VERSION} for linux_${ARCH_SUFFIX}"

# Download and extract
DOWNLOAD_URL="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${ARCH_SUFFIX}.tar.gz"
curl -sfLO "$DOWNLOAD_URL"
tar -xzf "actionlint_${ACTIONLINT_VERSION}_linux_${ARCH_SUFFIX}.tar.gz" actionlint
chmod +x actionlint

# Clean up tarball
rm -f "actionlint_${ACTIONLINT_VERSION}_linux_${ARCH_SUFFIX}.tar.gz"

echo "actionlint installed successfully"
./actionlint --version
