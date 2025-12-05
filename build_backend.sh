#!/bin/bash
# Watch Winder Backend Build Script (Bash)
# Usage: ./build_backend.sh [api|battery]

MODE=${1:-api}

echo -e "\n=== Watch Winder Backend Build Script ===\n"

# Step 1: Build dist folder for selected mode
echo -e "Step 1: Building dist folder for mode: $MODE..."
if [ "$MODE" = "battery" ]; then
    node build_backend.js --battery
else
    node build_backend.js --api
fi

# Step 2: Show dist folder contents
echo -e "\nStep 2: Listing dist folder contents..."
ls -lR Code/backend/dist

echo -e "\n=== Build Complete! ===\n"
echo "Deploy files from the dist folder to your ESP32-C3 using ampy or mpremote."
echo "See dist/README.md for upload instructions.\n"
