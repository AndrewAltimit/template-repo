#!/bin/bash
# Build LaTeX documents using Docker
# This script encapsulates the docker run logic for building PDFs from LaTeX source
#
# Usage: ./build-latex-doc.sh <tex-file> [source-dir] [output-dir]
#
# Arguments:
#   tex-file    - Name of the .tex file to compile (e.g., ai-agents-wmd-proliferation.tex)
#   source-dir  - Directory containing the .tex file (default: docs/projections/latex)
#   output-dir  - Directory for output files (default: docs_output)
#
# Examples:
#   ./build-latex-doc.sh ai-agents-wmd-proliferation.tex
#   ./build-latex-doc.sh Virtual_Character_System_Guide.tex docs/integrations/ai-services
#   ./build-latex-doc.sh Sleeper_Agents_Framework_Guide.tex packages/sleeper_agents/docs

set -e

# Arguments
TEX_FILE="${1:?Error: tex-file argument required}"
SOURCE_DIR="${2:-docs/projections/latex}"
OUTPUT_DIR="${3:-docs_output}"

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

# Get PDF name from tex file
PDF_FILE="${TEX_FILE%.tex}.pdf"

echo "Building $TEX_FILE..."
echo "  Source: $SOURCE_PATH"
echo "  Output: $OUTPUT_PATH"

# Create output directory
mkdir -p "$OUTPUT_PATH"

# Build PDF using texlive Docker image with latexmk for automatic dependency resolution
# Use --user to ensure artifacts are owned by runner user, not root
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$SOURCE_PATH:/data" \
    -v "$OUTPUT_PATH:/output" \
    texlive/texlive:TL2024-historic \
    bash -c "cd /data && latexmk -pdf -interaction=nonstopmode -output-directory=/output $TEX_FILE"

echo "PDF build completed"

# Verify PDF was created
if [ -f "$OUTPUT_PATH/$PDF_FILE" ]; then
    echo "PDF successfully created:"
    ls -lh "$OUTPUT_PATH/$PDF_FILE"
else
    echo "ERROR: PDF was not created"
    exit 1
fi

# Cleanup auxiliary files
rm -rf "$OUTPUT_PATH"/*.aux "$OUTPUT_PATH"/*.log "$OUTPUT_PATH"/*.toc \
       "$OUTPUT_PATH"/*.out "$OUTPUT_PATH"/*.fls "$OUTPUT_PATH"/*.fdb_latexmk \
       2>/dev/null || true

echo "Build complete: $OUTPUT_PATH/$PDF_FILE"
