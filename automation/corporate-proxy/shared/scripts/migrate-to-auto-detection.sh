#!/bin/bash
set -e

echo "==========================================="
echo "Migrating to Automatic Tool Detection"
echo "==========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="$SCRIPT_DIR/../services"

# Check if enhanced wrapper exists
if [ ! -f "$SERVICES_DIR/translation_wrapper_enhanced.py" ]; then
    echo "❌ Enhanced wrapper not found at: $SERVICES_DIR/translation_wrapper_enhanced.py"
    exit 1
fi

# Backup existing wrapper
if [ -f "$SERVICES_DIR/translation_wrapper.py" ]; then
    echo "📦 Backing up existing wrapper to translation_wrapper.backup.py"
    cp "$SERVICES_DIR/translation_wrapper.py" "$SERVICES_DIR/translation_wrapper.backup.py"
fi

# Copy enhanced wrapper
echo "🚀 Installing enhanced wrapper with automatic detection..."
cp "$SERVICES_DIR/translation_wrapper_enhanced.py" "$SERVICES_DIR/translation_wrapper.py"

# Check if models.json exists
MODELS_CONFIG="$SCRIPT_DIR/../../shared/configs/models.json"
if [ ! -f "$MODELS_CONFIG" ]; then
    echo "⚠️  Warning: models.json not found at $MODELS_CONFIG"
    echo "   Please create it with your model configurations"
else
    echo "✅ Found models.json configuration"

    # Check for models without tool support
    echo ""
    echo "📊 Model Configuration Summary:"
    python3 -c "
import json
with open('$MODELS_CONFIG') as f:
    config = json.load(f)
    models = config.get('models', {})

    with_tools = []
    without_tools = []

    for name, data in models.items():
        if data.get('supports_tools', True):
            with_tools.append(name)
        else:
            without_tools.append(name)

    print(f'  Models with native tool support: {len(with_tools)}')
    for m in with_tools:
        print(f'    ✅ {m}')

    print(f'  Models using text tool parsing: {len(without_tools)}')
    for m in without_tools:
        print(f'    📝 {m}')
"
fi

echo ""
echo "==========================================="
echo "✅ Migration Complete!"
echo "==========================================="
echo ""
echo "The translation wrapper now automatically:"
echo "  1. Detects tool support from models.json"
echo "  2. Uses native tools when supported"
echo "  3. Uses text parsing when not supported"
echo ""
echo "No environment variables needed!"
echo ""
echo "To test: python3 $SCRIPT_DIR/test-auto-detection.py"
echo "To rollback: cp $SERVICES_DIR/translation_wrapper.backup.py $SERVICES_DIR/translation_wrapper.py"
echo ""
