#!/bin/bash
# Check that each validator has corresponding test files

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Exit successfully if no files passed
if [ $# -eq 0 ]; then
    exit 0
fi

# Check each validator file
exit_code=0
for validator_file in "$@"; do
    # Get the validator name from the file path
    validator_name=$(basename "$validator_file" .py)

    # Skip base_validator and __init__
    if [[ "$validator_name" == "base_validator" ]] || [[ "$validator_name" == "__init__" ]]; then
        continue
    fi

    # Expected test file
    test_file="$PROJECT_ROOT/tests/validators/test_${validator_name}.py"

    # Check if test file exists
    if [ ! -f "$test_file" ]; then
        echo "ERROR: Missing test file for validator: $validator_name"
        echo "       Expected: $test_file"
        exit_code=1
    else
        echo "✓ Found test file for $validator_name"
    fi
done

exit $exit_code
