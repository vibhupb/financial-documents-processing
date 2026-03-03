#!/bin/bash
set -e
LAYER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$LAYER_DIR/python"
echo "Building Compliance Parsers Lambda Layer for Python 3.13..."
rm -rf "$PACKAGE_DIR" && mkdir -p "$PACKAGE_DIR"
pip3 install -r "$LAYER_DIR/requirements.txt" \
    -t "$PACKAGE_DIR" --platform manylinux2014_x86_64 \
    --implementation cp --python-version 3.13 --only-binary=:all: --upgrade
echo "Layer built: $(du -sh "$PACKAGE_DIR" | cut -f1)"
