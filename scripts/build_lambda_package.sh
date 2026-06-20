#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/dist/lambda-build"
REQUIREMENTS_FILE="$ROOT_DIR/dist/lambda-requirements.txt"

rm -rf "$BUILD_DIR"
mkdir -p "$ROOT_DIR/dist"

uv export \
  --project "$ROOT_DIR" \
  --no-dev \
  --no-emit-project \
  --no-hashes \
  -o "$REQUIREMENTS_FILE"

uv pip install \
  --python-version 3.13 \
  --python-platform x86_64-manylinux2014 \
  --target "$BUILD_DIR" \
  -r "$REQUIREMENTS_FILE"

rsync -a "$ROOT_DIR/src/" "$BUILD_DIR/"

find "$BUILD_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR" -type f -name "*.pyc" -delete

echo "Lambda package built at $BUILD_DIR"
