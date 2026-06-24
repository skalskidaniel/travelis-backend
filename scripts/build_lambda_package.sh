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
  --python-platform x86_64-manylinux_2_28 \
  --target "$BUILD_DIR" \
  -r "$REQUIREMENTS_FILE"

rsync -a "$ROOT_DIR/src/" "$BUILD_DIR/"

find "$BUILD_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR" -type f -name "*.pyc" -delete

# Prune unnecessary files to reduce package size for AWS Lambda upload limits
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} +
find "$BUILD_DIR" -type d -name "test" -exec rm -rf {} +
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} +
find "$BUILD_DIR" -type d -name "*.egg-info" -exec rm -rf {} +

# Prune unused AWS service models from botocore to save substantial space (~20MB)
if [ -d "$BUILD_DIR/botocore/data" ]; then
  (
    cd "$BUILD_DIR/botocore/data"
    for d in */; do
      case "$d" in
        dynamodb/|cognito-idp/|scheduler/|events/|lambda/|s3/|sts/|iam/|secretsmanager/)
          # Keep these
          ;;
        *)
          rm -rf "$d"
          ;;
      esac
    done
  )
fi

echo "Lambda package built at $BUILD_DIR"
