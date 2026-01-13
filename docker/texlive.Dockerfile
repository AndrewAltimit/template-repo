# Multi-arch TeXLive image for PDF builds
# Works on both amd64 and arm64
FROM debian:bookworm-slim

LABEL maintainer="AndrewAltimit"
LABEL description="TeXLive for building LaTeX documents (multi-arch)"

# Install texlive and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-xetex \
    texlive-science \
    texlive-pictures \
    latexmk \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /data

# Default command
CMD ["pdflatex", "--version"]
