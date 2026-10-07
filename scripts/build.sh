#!/bin/bash
# build.sh

echo "Building MediaVault..."

# Build Frontend
cd ../frontend
npm run build

echo "Build complete."
