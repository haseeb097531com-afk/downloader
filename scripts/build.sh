#!/bin/bash
# build.sh

echo "Building MediaVault Pro..."

# Build Frontend
cd ../frontend
npm run build

echo "Build complete."
