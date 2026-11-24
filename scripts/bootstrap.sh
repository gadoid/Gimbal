#!/bin/bash
# Initialize project

set -e

echo "Installing dependencies..."
pip install -e ".[dev]"

echo "Installing pre-commit hooks..."
pre-commit install

echo "Done!"
