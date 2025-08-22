#!/bin/bash
# Test the models.dev interceptor

echo "Testing models.dev interception..."

# Start the wrapper in background
python3 automation/proxy/api_translation_wrapper.py > /tmp/interceptor.log 2>&1 &
WRAPPER_PID=$!

# Wait for it to start
sleep 3

# Test the models.dev endpoint
echo "Fetching intercepted models list..."
curl -s http://localhost:8052/api.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = data.get('openrouter', {}).get('models', {})
print(f'Found {len(models)} models:')
for model_id in models.keys():
    print(f'  - {model_id}')
"

# Kill the wrapper
kill $WRAPPER_PID 2>/dev/null

echo "Test complete!"
