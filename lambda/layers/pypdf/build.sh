#!/bin/bash
# Build script for PyPDF Lambda Layer
# Run this script to create the layer package

set -e

LAYER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$LAYER_DIR/python"

echo "Building PyPDF Lambda Layer..."

# Clean up
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Install dependencies
pip install -r "$LAYER_DIR/requirements.txt" -t "$PACKAGE_DIR" --platform manylinux2014_x86_64 --only-binary=:all:

echo "Layer built successfully in $PACKAGE_DIR"
echo "Total size: $(du -sh "$PACKAGE_DIR" | cut -f1)"
