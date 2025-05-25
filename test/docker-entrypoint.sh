#!/bin/sh
set -e

# Default command if none provided
if [ $# -eq 0 ]; then
    set -- "--cov=button_longpress" "--cov-report=term-missing" "-v"
fi

echo "=== ESP-IDF Button Component Test Runner ==="
echo "Running tests with arguments: $@"

# Create results directory if it doesn't exist
mkdir -p /app/results

# Debug: List files in the current directory
echo "Files in the current directory:"
ls -la

# Verify Python environment
echo "Python version:"
python --version

echo "Installed packages:"
pip list | grep -E "(pytest|coverage)"

# Find test files
TEST_FILES=$(find /app -name "test_*.py" -type f)
if [ -z "$TEST_FILES" ]; then
    echo "Error: No test files found!"
    echo "Searching in all directories:"
    find /app -name "*.py" -type f
    exit 1
else
    echo "Found test files:"
    echo "$TEST_FILES"
fi

# Verify required files exist
REQUIRED_FILES="conftest.py button_longpress.py test_button_longpress.py"
for file in $REQUIRED_FILES; do
    if [ ! -f "/app/$file" ]; then
        echo "Error: Required file $file not found!"
        exit 1
    fi
done

echo "=== Starting Test Execution ==="

# Set environment variables for better test output
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1
export PYTEST_CURRENT_TEST=""

# Run the tests
TEST_EXIT_CODE=0
python -m pytest /app/test_button_longpress.py "$@" || TEST_EXIT_CODE=$?

echo "=== Test Execution Completed ==="

# Generate summary
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✓ All tests completed successfully"
else
    echo "✗ Some tests failed (exit code: $TEST_EXIT_CODE)"
fi

# Check if coverage report was generated
if [ -f "/app/results/coverage.xml" ]; then
    echo "✓ Coverage report generated"
    
    # Extract coverage percentage if possible
    if command -v grep > /dev/null 2>&1 && command -v awk > /dev/null 2>&1; then
        COVERAGE=$(grep -Po 'line-rate="\K[^"]*' /app/results/coverage.xml | head -1 | awk '{print $1 * 100}')
        echo "Coverage: ${COVERAGE}%"
        
        # Check coverage threshold
        if command -v bc > /dev/null 2>&1; then
            if [ $(echo "${COVERAGE} < 80" | bc -l) -eq 1 ]; then
                echo "Warning: Coverage is below 80% threshold"
            fi
        fi
    fi
fi

# Fix permissions on results directory if needed
if [ -d "/app/results" ]; then
    if [ -n "$HOST_UID" ] && [ -n "$HOST_GID" ]; then
        echo "Setting permissions on results directory"
        chown -R "$HOST_UID:$HOST_GID" /app/results 2>/dev/null || true
    fi
fi

# List generated files
if [ -d "/app/results" ]; then
    echo "Generated files:"
    ls -la /app/results/
fi

exit $TEST_EXIT_CODE
