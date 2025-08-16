#!/usr/bin/env python3
"""Test runner script for comprehensive test execution."""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"Duration: {end_time - start_time:.2f} seconds")
    print(f"Exit code: {result.returncode}")
    
    if result.stdout:
        print(f"\nSTDOUT:\n{result.stdout}")
    
    if result.stderr:
        print(f"\nSTDERR:\n{result.stderr}")
    
    return result.returncode == 0


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run comprehensive test suite")
    parser.add_argument(
        "--test-type",
        choices=["all", "unit", "integration", "performance"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run performance benchmarks"
    )
    
    args = parser.parse_args()
    
    # Change to project directory
    project_root = Path(__file__).parent.parent
    print(f"Project root: {project_root}")
    
    # Base pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        pytest_cmd.append("-v")
    else:
        pytest_cmd.append("-q")
    
    # Add parallel execution
    if args.parallel:
        pytest_cmd.extend(["-n", "auto"])
    
    # Add coverage
    if args.coverage:
        pytest_cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    success = True
    
    # Run different test types
    if args.test_type in ["all", "unit"]:
        cmd = pytest_cmd + ["-m", "not integration and not performance", "tests/unit/"]
        if not run_command(cmd, "Unit Tests"):
            success = False
    
    if args.test_type in ["all", "integration"]:
        cmd = pytest_cmd + ["-m", "integration or not performance", "tests/integration/"]
        if not run_command(cmd, "Integration Tests"):
            success = False
    
    if args.test_type in ["all", "performance"] or args.benchmark:
        cmd = pytest_cmd + ["-m", "performance", "tests/performance/"]
        if not run_command(cmd, "Performance Tests"):
            success = False
    
    # Run linting and type checking
    if args.test_type == "all":
        print(f"\n{'='*60}")
        print("Running Code Quality Checks")
        print(f"{'='*60}")
        
        # Run black formatting check
        black_cmd = ["python", "-m", "black", "--check", "--diff", "app/", "tests/"]
        if not run_command(black_cmd, "Black Formatting Check"):
            print("Code formatting issues found. Run 'black app/ tests/' to fix.")
            success = False
        
        # Run isort import sorting check
        isort_cmd = ["python", "-m", "isort", "--check-only", "--diff", "app/", "tests/"]
        if not run_command(isort_cmd, "Import Sorting Check"):
            print("Import sorting issues found. Run 'isort app/ tests/' to fix.")
            success = False
        
        # Run mypy type checking
        mypy_cmd = ["python", "-m", "mypy", "app/"]
        if not run_command(mypy_cmd, "Type Checking"):
            print("Type checking issues found.")
            success = False
        
        # Run ruff linting
        ruff_cmd = ["python", "-m", "ruff", "check", "app/", "tests/"]
        if not run_command(ruff_cmd, "Ruff Linting"):
            print("Linting issues found.")
            success = False
    
    # Summary
    print(f"\n{'='*60}")
    if success:
        print("✅ All tests and checks passed!")
        sys.exit(0)
    else:
        print("❌ Some tests or checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()