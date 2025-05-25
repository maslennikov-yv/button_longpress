#!/bin/sh
# Alternative script to run tests using Docker directly if docker-compose is not available

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

# Build the Docker image
echo "Building Docker image..."
docker build -t button-test .

# Run the tests
echo "Running tests in Docker container..."
docker run --rm \
    -v "$(pwd)/results:/app/results" \
    -e PYTHONPATH=/app \
    -e COVERAGE_FILE=/app/results/.coverage \
    -e HOST_UID=$(id -u) \
    -e HOST_GID=$(id -g) \
    button-test \
    --cov=button_longpress \
    --cov-report=xml:results/coverage.xml \
    --cov-report=html:results/htmlcov \
    --junitxml=results/junit.xml \
    --html=results/test-report.html

echo "Tests completed. Results are in the 'results' directory."
