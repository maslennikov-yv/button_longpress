#!/bin/sh
# Script to run tests in CI environment

set -e  # Exit on error

# Navigate to the test directory
cd "$(dirname "$0")"

# Create results directory if it doesn't exist
mkdir -p results

# Make sure the entrypoint script is executable
chmod +x docker-entrypoint.sh

# Debug: List files in the current directory
echo "Files in the current directory:"
ls -la

# Check if test_button_longpress.py exists
if [ ! -f "test_button_longpress.py" ]; then
    echo "Warning: test_button_longpress.py not found in the current directory!"
    echo "Searching for test files..."
    find . -name "test_*.py" -type f
fi

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
$DOCKER_COMPOSE build

# Run the tests with all reporting options
echo "Running tests in Docker container..."
$DOCKER_COMPOSE run --rm \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    test \
    --cov=button_longpress \
    --cov-report=xml:results/coverage.xml \
    --cov-report=html:results/htmlcov \
    --junitxml=results/junit.xml \
    --html=results/test-report.html

echo "Tests completed. Results are in the 'results' directory."

# Check if coverage meets threshold
if [ -f "results/coverage.xml" ]; then
    if command -v grep > /dev/null 2>&1 && command -v awk > /dev/null 2>&1 && command -v bc > /dev/null 2>&1; then
        COVERAGE=$(grep -Po 'line-rate="\K[^"]*' results/coverage.xml | awk '{print $1 * 100}')
        echo "Coverage: $COVERAGE%"
        
        if [ $(echo "$COVERAGE < 80" | bc -l) -eq 1 ]; then
            echo "Error: Test coverage is below 80%"
            exit 1
        fi
    else
        echo "Warning: Could not check coverage threshold (grep, awk, or bc not available)"
    fi
fi
