#!/bin/bash
# Script to set up the development environment

set -e

echo "🚀 Setting up Restaurant Platform Sync Service development environment..."
echo ""

# Check Python version
echo "✓ Checking Python version..."
if ! python3 --version | grep -q "3.11\|3.12\|3.13"; then
    echo "❌ Python 3.11+ required"
    python3 --version
    exit 1
fi
echo "  $(python3 --version)"
echo ""

# Create virtual environment
echo "✓ Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  Virtual environment already exists, skipping creation"
else
    python3 -m venv .venv
    echo "  Virtual environment created at .venv/"
fi
echo ""

# Activate virtual environment
echo "✓ Activating virtual environment..."
source .venv/bin/activate
echo "  Virtual environment activated"
echo ""

# Upgrade pip
echo "✓ Upgrading pip..."
pip install --upgrade pip --quiet
echo "  pip upgraded to $(pip --version)"
echo ""

# Install package with dev dependencies
echo "✓ Installing package with dev dependencies..."
pip install -e ".[dev]" --quiet
echo "  Package and dependencies installed"
echo ""

# Set up environment file if not exists
echo "✓ Setting up environment file..."
if [ -f ".env" ]; then
    echo "  .env already exists, skipping"
else
    cp .env.example .env
    echo "  .env created from .env.example"
fi
echo ""

# Install pre-commit hooks
echo "✓ Installing pre-commit hooks..."
pre-commit install > /dev/null 2>&1
echo "  Pre-commit hooks installed"
echo ""

echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate the virtual environment: source .venv/bin/activate"
echo "  2. Run tests: pytest"
echo "  3. Start developing!"
