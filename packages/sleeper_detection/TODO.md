# Sleeper Detection System - TODO

This document tracks unimplemented features and future development plans for the sleeper detection framework.

**For documentation of implemented features, see [docs/README.md](docs/README.md) and related documentation.**

## Active Development

### Documentation Improvements
- Consolidating temporary phase documentation
- Creating comprehensive example notebooks
- Improving API reference documentation
- Adding troubleshooting guides

### Testing & Quality
- Expanding test coverage for detection methods
- Adding integration tests for full pipeline
- Performance benchmarking across model sizes
- Cross-platform compatibility testing

## Future Work

### Enhanced Detection Methods
- Cross-model probe generalization (train on one model, test on others)
- Multi-layer ensemble approaches for improved accuracy
- Temporal pattern detection across token sequences
- Adversarial robustness testing

### Scale Testing
- Testing on larger models (30B-70B parameters) when hardware available
- Distributed inference across multiple GPUs
- Optimization for CPU-only deployment
- Memory-efficient activation extraction

### Additional Backdoor Types
- Code insertion backdoors beyond vulnerability injection
- Natural language trigger patterns
- Multi-modal trigger combinations
- Subtle behavioral shift detection

### Production Readiness
- REST API for programmatic access
- Batch evaluation pipeline for multiple models
- Automated report generation
- Integration with ML model registries
- Continuous monitoring capabilities

### Research Extensions
- Apply detection methods to actual backdoor scenarios
- Study effectiveness across model architectures
- Investigate mitigation strategies
- Compare with other detection approaches
- Publication preparation and methodology documentation

## Known Limitations

### Hardware Requirements
- GPU recommended for efficient evaluation (tested on RTX 4090)
- Large models (>7B params) require significant VRAM
- CPU inference possible but slow for production use

### Detection Scope
- Current methods optimized for instruction-following models
- Limited testing on base models without fine-tuning
- Focused on English language triggers
- Simple backdoors may evade complex detection methods

### Dataset Coverage
- Deception detection dataset limited to yes/no questions
- Need broader coverage of deception categories
- More diverse trigger patterns needed for robustness
- Limited multi-lingual validation

## References

This framework implements methodologies from:

**Hubinger et al. (2024). "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"**
https://www.anthropic.com/research/probes-catch-sleeper-agents
