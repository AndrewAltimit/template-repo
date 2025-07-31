# CGT Validator Requirements Structure

## File Organization

The CGT Validator uses a modular requirements structure:

### 1. `requirements-core.txt`
- **Purpose**: Minimal dependencies needed to run CGT Validator
- **Use**: For production installations
- **Contents**:
  - Core libraries (pandas, openpyxl, click)
  - Web scraping (beautifulsoup4, requests)
  - PDF parsing (pdfplumber, PyPDF2)
  - Reporting (jinja2, markdown)

### 2. `requirements-cgt.txt`
- **Purpose**: Full development environment
- **Use**: For developers working on the project
- **Contents**:
  - All core requirements
  - Testing frameworks (pytest)
  - Optional development tools (commented out)

### 3. `setup.py`
- **Purpose**: Package installation via pip
- **Uses**: Core requirements only (hardcoded list)
- **Benefit**: Clean installation without development dependencies

## Installation Options

### For Users (Production)
```bash
# Option 1: Using pip
pip install -e .

# Option 2: Direct requirements
pip install -r requirements-core.txt
```

### For Developers
```bash
# Full environment
pip install -r requirements-cgt.txt

# Or use the install script
./install.sh  # Linux/Mac
install.bat   # Windows
```

### For CI/CD
```bash
# GitHub Actions use requirements-cgt.txt
pip install -r requirements-cgt.txt
```

## Why This Structure?

1. **Separation of Concerns**: Core vs development dependencies
2. **Flexibility**: Users can choose minimal or full installation
3. **Standalone Ready**: All requirements in the project directory
4. **No External Dependencies**: No references to parent repository
5. **Easy Extraction**: Copy the entire directory to create standalone project

## Notes

- The deprecated `requirements.txt` and `requirements-parser.txt` are kept for backwards compatibility
- All CI/CD workflows have been updated to use `requirements-cgt.txt`
- The `setup.py` uses a hardcoded list to avoid parsing issues with `-r` directives
