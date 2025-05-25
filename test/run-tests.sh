#!/bin/bash

# ESP-IDF Button Component Test Runner
echo "=== ESP-IDF Button Component Test Runner ==="

# Check if we're in the test directory
if [ ! -f "conftest.py" ]; then
    echo "Error: Please run this script from the test directory"
    exit 1
fi

# Make the Python script executable and run it
python3 run_tests.py

echo ""
echo "=== Test execution completed ==="
