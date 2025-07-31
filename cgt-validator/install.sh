#!/bin/bash
# CGT Validator Installation Script

echo "========================================="
echo "CGT Validator - Installation Script"
echo "========================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

echo "Found Python: $(python3 --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing CGT validator requirements..."
pip install -r requirements-core.txt

# Install optional testing dependencies
echo "Installing testing dependencies..."
pip install pytest pytest-cov pytest-asyncio

# Install package in development mode
echo "Installing CGT validator package..."
pip install -e .

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "To use the CGT validator:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the demo: python test_oregon.py"
echo "3. Or use the CLI: cgt-validate oregon --file <your-file.xlsx>"
echo ""
echo "For Windows users:"
echo "- Activate venv with: venv\\Scripts\\activate"
echo ""
