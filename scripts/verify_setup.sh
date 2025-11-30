#!/bin/bash
# Script to verify the Python project setup is correct

set -e

echo "🔍 Verifying Python project setup..."
echo ""

# Check Python version
echo "✓ Checking Python version..."
python --version | grep -q "3.11\|3.12" || (echo "❌ Python 3.11+ required" && exit 1)
echo "  Python version OK"
echo ""

# Check virtual environment
echo "✓ Checking virtual environment..."
if [ -z "$VIRTUAL_ENV" ]; then
    echo "  ⚠️  Warning: No virtual environment activated"
    echo "  Run: source .venv/bin/activate"
else
    echo "  Virtual environment: $VIRTUAL_ENV"
fi
echo ""

# Check directory structure
echo "✓ Checking directory structure..."
for dir in "src/restaurant_sync_service" "tests/unit" "tests/component" "tests/integration" "tests/e2e"; do
    if [ -d "$dir" ]; then
        echo "  ✓ $dir"
    else
        echo "  ❌ Missing: $dir"
        exit 1
    fi
done
echo ""

# Check required files
echo "✓ Checking required files..."
for file in "pyproject.toml" ".gitignore" ".env.example" ".pre-commit-config.yaml" "tests/conftest.py"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ❌ Missing: $file"
        exit 1
    fi
done
echo ""

# Check if dependencies are installed
echo "✓ Checking dependencies..."
if python -c "import pytest" 2>/dev/null; then
    echo "  ✓ pytest installed"
else
    echo "  ⚠️  pytest not installed - run: pip install -e \".[dev]\""
fi

if python -c "import fastapi" 2>/dev/null; then
    echo "  ✓ fastapi installed"
else
    echo "  ⚠️  fastapi not installed - run: pip install -e \".[dev]\""
fi
echo ""

# Check package can be imported
echo "✓ Checking package import..."
if python -c "import restaurant_sync_service" 2>/dev/null; then
    echo "  ✓ restaurant_sync_service package can be imported"
    python -c "from restaurant_sync_service import __version__; print(f'  Version: {__version__}')"
else
    echo "  ⚠️  Package not installed - run: pip install -e \".[dev]\""
fi
echo ""

echo "✅ Setup verification complete!"
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source .venv/bin/activate"
echo "  2. Install dependencies: pip install -e \".[dev]\""
echo "  3. Install pre-commit hooks: pre-commit install"
echo "  4. Start building with TDD approach!"
