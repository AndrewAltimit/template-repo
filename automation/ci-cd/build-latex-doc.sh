#!/bin/bash
# Build LaTeX documents using containerized TeXLive (multi-arch compatible)
# This script compiles PDFs from LaTeX source using Docker
#
# Usage: ./build-latex-doc.sh <tex-file> [source-dir] [output-dir] [output-name]
#
# Arguments:
#   tex-file    - Name of the .tex file to compile (e.g., ai-agents-wmd-proliferation.tex)
#   source-dir  - Directory containing the .tex file (default: docs/projections/latex)
#   output-dir  - Directory for output files (default: docs_output)
#   output-name - Optional output PDF filename (without .pdf extension)
#
# Examples:
#   ./build-latex-doc.sh ai-agents-wmd-proliferation.tex
#   ./build-latex-doc.sh Virtual_Character_System_Guide.tex docs/integrations/ai-services docs_output virtual-character-system-guide
#   ./build-latex-doc.sh Sleeper_Agents_Framework_Guide.tex packages/sleeper_agents/docs docs_output sleeper-agents-framework-guide

set -e

# Arguments
TEX_FILE="${1:?Error: tex-file argument required}"
SOURCE_DIR="${2:-docs/projections/latex}"
OUTPUT_DIR="${3:-docs_output}"
OUTPUT_NAME="${4:-}"

# Get project root (script is in automation/ci-cd/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Resolve paths relative to project root
SOURCE_PATH="$PROJECT_ROOT/$SOURCE_DIR"
OUTPUT_PATH="$PROJECT_ROOT/$OUTPUT_DIR"

# Validate source file exists
if [ ! -f "$SOURCE_PATH/$TEX_FILE" ]; then
    echo "ERROR: Source file not found: $SOURCE_PATH/$TEX_FILE"
    exit 1
fi

# Docker image name
TEXLIVE_IMAGE="${TEXLIVE_IMAGE:-texlive-local}"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker."
    exit 1
fi

# Build Docker image if it doesn't exist
if ! docker image inspect "$TEXLIVE_IMAGE" &> /dev/null; then
    echo "Building TeXLive Docker image..."
    docker build -t "$TEXLIVE_IMAGE" -f "$PROJECT_ROOT/docker/texlive.Dockerfile" "$PROJECT_ROOT"
fi

# Get PDF name from tex file
PDF_FILE="${TEX_FILE%.tex}.pdf"

echo "Building $TEX_FILE..."
echo "  Source: $SOURCE_PATH"
echo "  Output: $OUTPUT_PATH"

# Create output directory
mkdir -p "$OUTPUT_PATH"

# Build PDF using containerized latexmk for automatic dependency resolution
docker run --rm \
    -v "$PROJECT_ROOT:/data" \
    -w "/data/$SOURCE_DIR" \
    -u "$(id -u):$(id -g)" \
    "$TEXLIVE_IMAGE" \
    latexmk -pdf -interaction=nonstopmode -output-directory="/data/$OUTPUT_DIR" "$TEX_FILE"

echo "PDF build completed"

# Verify PDF was created
if [ ! -f "$OUTPUT_PATH/$PDF_FILE" ]; then
    echo "ERROR: PDF was not created"
    exit 1
fi

# Rename if output name specified
FINAL_PDF="$PDF_FILE"
if [ -n "$OUTPUT_NAME" ]; then
    FINAL_PDF="${OUTPUT_NAME}.pdf"
    if [ "$PDF_FILE" != "$FINAL_PDF" ]; then
        mv "$OUTPUT_PATH/$PDF_FILE" "$OUTPUT_PATH/$FINAL_PDF"
        echo "Renamed to: $FINAL_PDF"
    fi
fi

echo "PDF successfully created:"
ls -lh "$OUTPUT_PATH/$FINAL_PDF"

# Cleanup auxiliary files
rm -rf "$OUTPUT_PATH"/*.aux "$OUTPUT_PATH"/*.log "$OUTPUT_PATH"/*.toc \
       "$OUTPUT_PATH"/*.out "$OUTPUT_PATH"/*.fls "$OUTPUT_PATH"/*.fdb_latexmk \
       2>/dev/null || true

echo "Build complete: $OUTPUT_PATH/$FINAL_PDF"
