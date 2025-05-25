#!/bin/sh
set -e

# Default command if none provided
if [ $# -eq 0 ]; then
    set -- "--cov=button_longpress" "--cov-report=term-missing"
fi

echo "Running tests with arguments: $@"

# Create results directory if it doesn't exist
mkdir -p /app/results

# Debug: List files in the current directory
echo "Files in the current directory:"
ls -la

# Find test files
TEST_FILES=$(find /app -name "test_*.py" -type f)
if [ -z "$TEST_FILES" ]; then
    echo "Error: No test files found!"
    exit 1
else
    echo "Found test files:"
    echo "$TEST_FILES"
fi

# Run the tests with the found test files
for test_file in $TEST_FILES; do
    echo "Running tests from: $test_file"
    python -m pytest "$test_file" -v --color=yes "$@"
done

# Check if we need to fix permissions on results directory
if [ -d "/app/results" ]; then
    # Get the UID and GID of the mounted volume
    if [ -n "$HOST_UID" ] && [ -n "$HOST_GID" ]; then
        echo "Setting permissions on results directory"
        chown -R "$HOST_UID:$HOST_GID" /app/results
    fi
fi

# Check test coverage if coverage.xml exists
if [ -f "/app/results/coverage.xml" ]; then
    COVERAGE=$(grep -Po 'line-rate="\K[^"]*' /app/results/coverage.xml | awk '{print $1 * 100}')
    echo "Coverage: $COVERAGE%"
    
    # Fail if coverage is below threshold
    if [ $(echo "$COVERAGE < 80" | bc -l) -eq 1 ]; then
        echo "Error: Test coverage is below 80%"
        exit 1
    fi
fi

# Return the exit code from pytest
exit $?
