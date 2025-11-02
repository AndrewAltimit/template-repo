# Sleeper Detection Documentation Index

## Getting Started

- [README](../README.md) - Project overview and quick start
- [Quick Start Guide](QUICK_START.md) - Get running in 5 minutes
- [Installation Guide](INSTALLATION.md) - Detailed installation instructions
- [Quick Reference](QUICK_REFERENCE.md) - Command reference

## Core Concepts

- [Architecture Overview](ARCHITECTURE.md) - System design and components
- [Detection Methods](DETECTION_METHODS.md) - Available detection techniques
- [Deception Detection](DECEPTION_DETECTION.md) - Linear probe methodology (93.2% AUROC)

## User Guides

### Evaluation & Testing
- [Batch Evaluation](BATCH_EVALUATION.md) - Evaluate multiple models
- [Custom Tests](CUSTOM_TESTS.md) - Create custom test scenarios
- [Test Suites](TEST_SUITES.md) - Pre-built test configurations
- [Report Interpretation](REPORT_INTERPRETATION.md) - Understanding results

### API & CLI
- [API Reference](API_REFERENCE.md) - Python API documentation
- [CLI Reference](CLI_REFERENCE.md) - Command-line interface

## Deployment

- [Docker Deployment](DOCKER_DEPLOYMENT.md) - Containerized deployment
- [Windows Deployment](WINDOWS_DEPLOYMENT.md) - Windows-specific instructions

## Advanced Topics

- [TransformerLens Guide](TRANSFORMERLENS_GUIDE.md) - Deep mechanistic interpretability
- [Artifact Management](ARTIFACT_MANAGEMENT.md) - Managing experiment artifacts

## Development

- [TODO](../TODO.md) - Development roadmap and status
- [Notebooks](../notebooks/) - Interactive Jupyter examples
  - `01_basic_detection.ipynb` - Basic backdoor detection workflow
  - `02_deception_probes.ipynb` - Training deception detection probes
  - `interactive_sleeper_agents.ipynb` - Comprehensive interactive analysis

## Research Background

This framework implements methodologies from:

**Hubinger et al. (2024). "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"**

Key findings replicated:
- Backdoor persistence through safety training (100% vs Anthropic's 98.9%)
- Linear probe deception detection (93.2% vs Anthropic's 99% on smaller models)
- Generation-based activation extraction (teacher forcing)

## Quick Navigation

### By Task

**I want to...**
- **Get started quickly** → [Quick Start Guide](QUICK_START.md)
- **Evaluate a model** → [Batch Evaluation](BATCH_EVALUATION.md)
- **Understand detection methods** → [Detection Methods](DETECTION_METHODS.md)
- **Train deception probes** → [Deception Detection](DECEPTION_DETECTION.md)
- **Deploy to production** → [Docker Deployment](DOCKER_DEPLOYMENT.md)
- **Run on Windows** → [Windows Deployment](WINDOWS_DEPLOYMENT.md)
- **Learn the API** → [API Reference](API_REFERENCE.md)
- **Use command-line tools** → [CLI Reference](CLI_REFERENCE.md)
- **Understand results** → [Report Interpretation](REPORT_INTERPRETATION.md)

### By Experience Level

**Beginner**
1. [README](../README.md) - Start here
2. [Quick Start Guide](QUICK_START.md) - Get running
3. [Detection Methods](DETECTION_METHODS.md) - Learn the concepts
4. [Quick Reference](QUICK_REFERENCE.md) - Common commands

**Intermediate**
1. [Architecture Overview](ARCHITECTURE.md) - System design
2. [API Reference](API_REFERENCE.md) - Python API
3. [Batch Evaluation](BATCH_EVALUATION.md) - Advanced testing
4. [Deception Detection](DECEPTION_DETECTION.md) - Training probes

**Advanced**
1. [TransformerLens Guide](TRANSFORMERLENS_GUIDE.md) - Deep analysis
2. [Custom Tests](CUSTOM_TESTS.md) - Create custom scenarios
3. [Artifact Management](ARTIFACT_MANAGEMENT.md) - Managing experiments
4. Notebooks - Interactive development

## External Resources

- [Anthropic Sleeper Agents Paper](https://www.anthropic.com/research/probes-catch-sleeper-agents)
- [GitHub Repository](https://github.com/AndrewAltimit/template-repo)
- [Issue Tracker](https://github.com/AndrewAltimit/template-repo/issues)

## Documentation Status

Last updated: 2025-10-07

Total documentation files: 20+
