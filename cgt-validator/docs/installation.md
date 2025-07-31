# Installation Guide

## System Requirements

- Python 3.8 or higher
- pip (Python package manager)
- 100 MB free disk space
- Internet connection (for downloading state templates)

## Installation Methods

### Method 1: Install from PyPI (Recommended)

```bash
pip install cgt-validator
```

### Method 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/your-org/cgt-validator.git
cd cgt-validator

# Install in development mode
pip install -e .
```

### Method 3: Install in Virtual Environment (Best Practice)

```bash
# Create virtual environment
python -m venv cgt-env

# Activate virtual environment
# On Windows:
cgt-env\Scripts\activate
# On Mac/Linux:
source cgt-env/bin/activate

# Install package
pip install cgt-validator
```

### Method 4: Standalone Executable (Windows/Mac)

Download pre-built executables from the releases page:
- Windows: `cgt-validator-windows.exe`
- Mac: `cgt-validator-macos`
- Linux: `cgt-validator-linux`

## Verify Installation

```bash
# Check installation
cgt-validate --version

# View help
cgt-validate --help
```

## Update to Latest Version

```bash
pip install --upgrade cgt-validator
```

## Uninstall

```bash
pip uninstall cgt-validator
```

## Platform-Specific Instructions

### Windows

1. Open Command Prompt or PowerShell as Administrator
2. Ensure Python is in PATH:
   ```cmd
   python --version
   ```
3. If not found, add Python to PATH or use full path:
   ```cmd
   C:\Python39\Scripts\pip install cgt-validator
   ```

### macOS

1. Open Terminal
2. If using system Python, you may need sudo:
   ```bash
   sudo pip install cgt-validator
   ```
3. Recommended: Use Homebrew Python:
   ```bash
   brew install python
   pip3 install cgt-validator
   ```

### Linux

1. Open Terminal
2. Install pip if needed:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-pip

   # CentOS/RHEL
   sudo yum install python3-pip
   ```
3. Install package:
   ```bash
   pip3 install --user cgt-validator
   ```

## Troubleshooting Installation

### Permission Denied

Use `--user` flag to install for current user only:
```bash
pip install --user cgt-validator
```

### SSL Certificate Error

Use trusted host flag:
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org cgt-validator
```

### Behind Corporate Proxy

Configure pip to use proxy:
```bash
pip install --proxy http://user:password@proxyserver:port cgt-validator
```

## Docker Installation (Alternative)

```dockerfile
FROM python:3.9-slim
RUN pip install cgt-validator
ENTRYPOINT ["cgt-validate"]
```

Build and run:
```bash
docker build -t cgt-validator .
# Linux/macOS:
docker run -v $(pwd):/data cgt-validator oregon --file /data/submission.xlsx

# Windows (PowerShell):
docker run -v ${PWD}:/data cgt-validator oregon --file /data/submission.xlsx

# Windows (Command Prompt):
docker run -v %cd%:/data cgt-validator oregon --file /data/submission.xlsx
```
