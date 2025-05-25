# Button Long Press Component Test Suite with CI/CD Integration

This directory contains a comprehensive test suite for the ESP-IDF button long press component, designed to run in a containerized environment and integrate with CI/CD pipelines.

## CI/CD Integration

The test suite is configured to run automatically in CI/CD pipelines. The following files are used for CI/CD integration:

- `.github/workflows/ci.yml`: GitHub Actions workflow configuration
- `test/Dockerfile`: Docker configuration for containerized testing
- `test/docker-compose.yml`: Docker Compose configuration for local and CI testing
- `test/docker-entrypoint.sh`: Entrypoint script for the Docker container
- `test/run-ci-tests.sh`: Script to run tests in CI environment

## Requirements

For local development and testing:
- Docker
- Docker Compose (or Docker with Compose plugin)

For CI/CD integration:
- GitHub Actions (or other CI/CD platform)

## Running Tests Locally

### Using Docker Compose

The simplest way to run the tests is using the provided script:

\`\`\`bash
./run-ci-tests.sh
\`\`\`

This will:
1. Build the Docker image
2. Run the tests in a container
3. Generate test reports and coverage data
4. Check if coverage meets the threshold (80%)

### Using Docker Directly (if Docker Compose is not available)

If you don't have Docker Compose installed, you can use Docker directly:

\`\`\`bash
./run-tests-docker.sh
\`\`\`

This script provides the same functionality but uses Docker commands directly instead of Docker Compose.

### Manual Execution with Docker Compose

You can also run the tests manually:

\`\`\`bash
# Build the Docker image
docker-compose build

# Run tests with default options
docker-compose run --rm test

# Run tests with custom options
docker-compose run --rm test --cov-report=html:results/htmlcov
\`\`\`

Or with Docker CLI plugin:

\`\`\`bash
# Build the Docker image
docker compose build

# Run tests with default options
docker compose run --rm test
\`\`\`

## Test Results

After running the tests, you can find:

- Terminal output showing test results
- JUnit XML report in `results/junit.xml`
- HTML coverage report in `results/htmlcov/`
- HTML test report in `results/test-report.html`
- Coverage XML report in `results/coverage.xml`

## CI/CD Pipeline

The CI/CD pipeline performs the following steps:

1. Checkout the code
2. Set up Docker
3. Build the Docker image
4. Run the tests in the container
5. Upload test results as artifacts
6. Publish test reports
7. Check test coverage
8. Fail the build if tests fail or coverage is below threshold

## Customizing the CI/CD Pipeline

### Changing the Coverage Threshold

The coverage threshold is set to 80% by default. You can change it in:
- `docker-entrypoint.sh`
- `run-ci-tests.sh`
- `.github/workflows/ci.yml`

### Adding Custom Test Steps

To add custom test steps:
1. Modify the `docker-entrypoint.sh` script
2. Update the GitHub Actions workflow in `.github/workflows/ci.yml`

### Using a Different CI/CD Platform

The configuration can be adapted to other CI/CD platforms:
- For GitLab CI, create a `.gitlab-ci.yml` file
- For Jenkins, create a `Jenkinsfile`
- For CircleCI, create a `.circleci/config.yml` file

## Troubleshooting

### Docker Compose Not Found

If you get an error like `docker-compose: command not found`, you have a few options:

1. Install Docker Compose:
   \`\`\`bash
   # For Ubuntu/Debian
   sudo apt install docker-compose
   
   # Using pip
   pip install docker-compose
   \`\`\`

2. Use the Docker CLI plugin (if you have Docker Desktop or recent Docker Engine):
   \`\`\`bash
   docker compose build
   docker compose run --rm test
   \`\`\`

3. Use the alternative script that uses Docker directly:
   \`\`\`bash
   ./run-tests-docker.sh
   \`\`\`

### Tests Fail in CI but Pass Locally

This could be due to:
- Different environment variables
- Different Python versions
- Different Docker configurations

Check the CI logs for details and try to reproduce the issue locally using the same Docker configuration.

### Docker Build Fails

Make sure you have the latest version of Docker installed. If the build fails due to network issues, try again or use a different network.

### Test Coverage Below Threshold

If the test coverage is below the threshold, add more tests to cover the missing code paths. You can see which lines are not covered in the HTML coverage report.
