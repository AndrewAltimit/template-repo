# OpenCode Company Integration

This directory contains the working implementation for integrating OpenCode with company-specific AI APIs.

## Overview

The solution provides a containerized OpenCode build that:
- Shows ONLY 3 company models (not hundreds from models.dev)
- Translates between OpenAI format and Company's Bedrock-based API format
- Includes a fully functional TUI (Terminal User Interface)
- Supports both mock testing and production deployment

## Files

### Core Services
- `company_translation_wrapper.py` - Translates OpenAI API format to Company Bedrock format
- `mock_company_api.py` - Mock Company API for testing outside company network

### Scripts
- `build-company-tui.sh` - Build the Docker container with TUI support
- `run-company-tui.sh` - Run with mock services (for testing)
- `run-company-production.sh` - Run with real Company API
- `stop-mock-services.sh` - Stop any running mock services
- `test-company-tui.sh` - Test the TUI functionality

### Documentation
- `CONTAINER_SOLUTION.md` - Technical details of the container implementation

## Quick Start

### Build the Container
```bash
./build-company-tui.sh
```

### Test with Mock Services
```bash
./run-company-tui.sh
# The TUI will auto-start with mock services
```

### Production Deployment
```bash
export COMPANY_API_BASE="https://your-company-api-endpoint"
export COMPANY_API_TOKEN="your-token"
./run-company-production.sh
```

## Architecture

The solution uses a multi-stage Docker build:
1. **Go stage** - Builds the TUI binary from source
2. **Bun stage** - Compiles OpenCode with model patches
3. **Runtime stage** - Combines everything with Python services

## Key Features

- **Model Limiting**: Patches OpenCode to show only 3 company models
- **API Translation**: Wrapper converts between API formats seamlessly
- **Auto-start**: TUI launches automatically when container starts
- **Mock Testing**: Full mock environment for development/testing

For complete documentation, see `/OPENCODE_COMPANY_INTEGRATION.md` in the repository root.
