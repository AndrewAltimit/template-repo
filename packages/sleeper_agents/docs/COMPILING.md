# Compiling the Sleeper Agents Documentation

This guide explains how to compile the comprehensive LaTeX documentation for the Sleeper Agents Detection Framework.

## Prerequisites

The documentation uses modern LaTeX packages for professional appearance:
- **LaTeX distribution** (texlive-full recommended for all fonts)
- **Python 3.x** for minted syntax highlighting
- **Pygments library** (`pip install Pygments`)
- **Required LaTeX packages**:
  - lato (modern sans-serif font)
  - fontawesome5 (icons for callout boxes)
  - minted (superior syntax highlighting)
  - tcolorbox with minted library
  - tikz with positioning libraries
  - booktabs (professional tables)
  - cleveref (smart cross-referencing)

## Quick Start - Using Docker (Recommended)

The easiest way to compile is using the texlive Docker container:

```bash
# Navigate to the docs directory
cd packages/sleeper_agents/docs

# Compile with Docker (includes all dependencies)
docker run --rm \
  -v "$(pwd):/workspace" \
  -w /workspace \
  texlive/texlive:latest \
  pdflatex -shell-escape -interaction=nonstopmode Sleeper_Agents_Complete_Guide.tex

# Run twice for proper cross-references
docker run --rm \
  -v "$(pwd):/workspace" \
  -w /workspace \
  texlive/texlive:latest \
  pdflatex -shell-escape -interaction=nonstopmode Sleeper_Agents_Complete_Guide.tex
```

## Local Compilation

If you have LaTeX installed locally:

```bash
# Install Pygments if not already installed
pip install Pygments

# Compile with shell-escape flag (required for minted)
pdflatex -shell-escape Sleeper_Agents_Complete_Guide.tex

# Run twice for proper cross-references and table of contents
pdflatex -shell-escape Sleeper_Agents_Complete_Guide.tex
```

### Important: The --shell-escape Flag

The `--shell-escape` (or `-shell-escape`) flag is **required** because minted needs to call external Python/Pygments processes for syntax highlighting. This is safe when compiling trusted documents.

## Output

- **PDF**: `Sleeper_Agents_Complete_Guide.pdf` (113 pages, ~724KB)
- **Temporary files**: `.aux`, `.out`, `.toc`, `.log`, `_minted-*` (can be deleted)

## Features

The compiled documentation includes:
- **Modern Lato typography** with professional sans-serif styling
- **FontAwesome icons** in callout boxes for visual clarity
- **Professional syntax highlighting** via minted (friendly style)
- **TikZ diagrams** for MLOps pipeline visualization
- **Professional tables** with booktabs (clean horizontal rules)
- **Audience-specific callout boxes** (Developers, Enterprise Leaders, Researchers)
- **Breakable code blocks** that handle page breaks elegantly
- **Color-coded sections** with custom styling and subtle rules
- **Interactive hyperlinks** with cleveref smart cross-referencing
- **112+ pages** of comprehensive content

## Troubleshooting

### Error: "minted requires -shell-escape"
**Solution**: Add the `-shell-escape` flag to your pdflatex command.

### Error: "pygmentize not found"
**Solution**: Install Pygments: `pip install Pygments`

### Error: Font "Lato" not found
**Solution**: The Lato font is included in texlive-fonts-extra. Install it with:
```bash
# Ubuntu/Debian
sudo apt-get install texlive-fonts-extra

# Or use the texlive Docker image which includes all fonts
```

### Error: "fontawesome5 package not found"
**Solution**: Install texlive-fonts-extra which includes FontAwesome5:
```bash
sudo apt-get install texlive-fonts-extra
```

### Error: "File not found" for component .tex files
**Solution**: Ensure you're in the `packages/sleeper_agents/docs` directory and all component files are present:
- `architecture_expanded.tex`
- `detection_methods_expanded.tex`
- `GETTING_STARTED.tex`
- `TUTORIALS.tex`
- `use_cases_expanded.tex`
- `ADVANCED_TOPICS.tex`
- `security_ethics_governance.tex`
- `api-reference.tex`
- `TROUBLESHOOTING_FAQ.tex`
- `appendix.tex`

### Slow Compilation
**Solution**: First run is slower due to minted cache generation. Subsequent runs are faster.

## Visual Enhancements in Version 2.0

This version includes comprehensive visual improvements based on Gemini AI consultation:

1. **Modern Typography**: Lato font provides a clean, professional appearance
2. **FontAwesome Icons**: Visual indicators for different audience types
3. **TikZ Diagrams**: Professional flowcharts replace ASCII art
4. **Booktabs Tables**: Clean, readable tables with proper spacing
5. **Minted Code Blocks**: Superior syntax highlighting with breakable boxes
6. **Enhanced Color Palette**: Professional blue/green/orange theme
7. **Smart Cross-References**: Cleveref for intelligent referencing

## Cleaning Up

```bash
# Remove temporary LaTeX files
rm -f *.aux *.out *.toc *.log

# Remove minted cache
rm -rf _minted-*
```

## Modular Structure

The documentation uses a modular structure for easier maintenance:

- **Master file**: `Sleeper_Agents_Complete_Guide.tex` (includes all components)
- **Component files**: Separate .tex files for each major section
- **Benefits**: Easier editing, cleaner git diffs, collaborative editing

To edit a specific section, modify the appropriate component file and recompile the master document.

## Customization

### Changing Code Highlighting Style

Edit the master .tex file and change the `minted style`:

```latex
\newtcblisting{pythoncode}[2][]{
    minted style=monokai,  % Try: friendly, monokai, dracula, solarized-dark
    ...
}
```

Available styles: friendly, monokai, vim, emacs, autumn, paraiso-dark, native, etc.
See Pygments documentation for full list.

### Changing Colors

Modify the color definitions in the preamble:

```latex
\definecolor{BrandBlue}{HTML}{0A3D62}
\definecolor{BrandAccent}{HTML}{3C6382}
\definecolor{CodeBg}{HTML}{F8F9FA}
```

## CI/CD Integration

For automated compilation in CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Compile LaTeX Documentation
  run: |
    docker run --rm \
      -v "$PWD/packages/sleeper_agents/docs:/workspace" \
      -w /workspace \
      texlive/texlive:latest \
      bash -c "pdflatex -shell-escape -interaction=nonstopmode Sleeper_Agents_Complete_Guide.tex && \
               pdflatex -shell-escape -interaction=nonstopmode Sleeper_Agents_Complete_Guide.tex"
```

## Support

For issues or questions:
- Check [TROUBLESHOOTING_FAQ.md](TROUBLESHOOTING_FAQ.md) in the documentation
- Open an issue on GitHub
- Consult LaTeX/minted documentation

## Version Information

- **Document Version**: 2.0 - Comprehensive Edition
- **LaTeX Engine**: pdflatex
- **Syntax Highlighting**: minted + Pygments
- **Page Count**: 113 pages
- **Last Updated**: 2025-11-13
