#!/bin/sh
# Script to run tests in CI environment

set -e  # Exit on error

# Navigate to the test directory
cd "$(dirname "$0")"

# Create results directory if it doesn't exist
mkdir -p results

# Make sure the entrypoint script is executable
chmod +x docker-entrypoint.sh

echo "=== ESP-IDF Button Component Test Suite ==="
echo "Starting comprehensive test execution..."

# Debug: List files in the current directory
echo "Files in the current directory:"
ls -la

# Check if test files exist
if [ ! -f "test_button_longpress.py" ]; then
    echo "Error: test_button_longpress.py not found!"
    echo "Searching for test files..."
    find . -name "test_*.py" -type f
    exit 1
fi

# Check if required files exist
required_files="conftest.py button_longpress.py test_button_longpress.py"
for file in $required_files; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file $file not found!"
        exit 1
    fi
done

# Check if docker-compose or docker compose is available
if command -v docker-compose > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: Neither docker-compose nor docker compose plugin is available."
    echo "Please install Docker Compose using one of the following methods:"
    echo "1. Official Docker installation: https://docs.docker.com/compose/install/"
    echo "2. Using pip: pip install docker-compose"
    echo "3. Using apt (Ubuntu/Debian): sudo apt install docker-compose"
    echo ""
    echo "Alternatively, you can use the Docker-only script:"
    echo "./run-tests-docker.sh"
    exit 1
fi

# Build the Docker image
echo "Building Docker image..."
if ! $DOCKER_COMPOSE build; then
    echo "Error: Failed to build Docker image"
    exit 1
fi

# Run the tests with comprehensive reporting
echo "Running comprehensive test suite..."
TEST_EXIT_CODE=0

$DOCKER_COMPOSE run --rm \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    test \
    --cov=button_longpress \
    --cov-report=xml:results/coverage.xml \
    --cov-report=html:results/htmlcov \
    --cov-report=term-missing \
    --junitxml=results/junit.xml \
    --html=results/test-report.html \
    --self-contained-html \
    -v \
    --tb=short || TEST_EXIT_CODE=$?

echo "=== Test Execution Summary ==="

# Check if results were generated
if [ -f "results/junit.xml" ]; then
    echo "✓ JUnit XML report generated"
else
    echo "✗ JUnit XML report missing"
fi

if [ -f "results/coverage.xml" ]; then
    echo "✓ Coverage XML report generated"
else
    echo "✗ Coverage XML report missing"
fi

if [ -f "results/test-report.html" ]; then
    echo "✓ HTML test report generated"
else
    echo "✗ HTML test report missing"
fi

if [ -d "results/htmlcov" ]; then
    echo "✓ HTML coverage report generated"
else
    echo "✗ HTML coverage report missing"
fi

# Check test results
if [ -f "results/junit.xml" ]; then
    # Extract test statistics from JUnit XML
    if command -v grep > /dev/null 2>&1 && command -v awk > /dev/null 2>&1; then
        TESTS=$(grep -o 'tests="[0-9]*"' results/junit.xml | awk -F'"' '{print $2}')
        FAILURES=$(grep -o 'failures="[0-9]*"' results/junit.xml | awk -F'"' '{print $2}')
        ERRORS=$(grep -o 'errors="[0-9]*"' results/junit.xml | awk -F'"' '{print $2}')
        
        echo "Test Results:"
        echo "  Total tests: ${TESTS:-0}"
        echo "  Failures: ${FAILURES:-0}"
        echo "  Errors: ${ERRORS:-0}"
        
        if [ "${FAILURES:-0}" -gt 0 ] || [ "${ERRORS:-0}" -gt 0 ]; then
            echo "✗ Some tests failed"
            TEST_EXIT_CODE=1
        else
            echo "✓ All tests passed"
        fi
    fi
fi

# Check coverage threshold
if [ -f "results/coverage.xml" ]; then
    if command -v grep > /dev/null 2>&1 && command -v awk > /dev/null 2>&1 && command -v bc > /dev/null 2>&1; then
        COVERAGE=$(grep -Po 'line-rate="\K[^"]*' results/coverage.xml | head -1 | awk '{print $1 * 100}')
        echo "Coverage: ${COVERAGE}%"
        
        if [ $(echo "${COVERAGE} < 80" | bc -l) -eq 1 ]; then
            echo "✗ Test coverage is below 80% threshold"
            TEST_EXIT_CODE=1
        else
            echo "✓ Test coverage meets 80% threshold"
        fi
    else
        echo "Warning: Could not check coverage threshold (grep, awk, or bc not available)"
    fi
fi

echo "=== Test Suite Completed ==="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✓ All tests passed successfully!"
    echo "Results are available in the 'results' directory:"
    echo "  - results/test-report.html (Test report)"
    echo "  - results/htmlcov/index.html (Coverage report)"
else
    echo "✗ Test suite failed!"
    echo "Check the reports in the 'results' directory for details."
fi

exit $TEST_EXIT_CODE
