#!/bin/bash

# Script to copy PDF files to aftis-parser container
# Usage: ./copy-pdfs.sh [source_directory] [pattern]

set -e

CONTAINER_NAME="aftis-parser"
CONTAINER_PATH="/srv/aftis/inbox/"
SOURCE_DIR="${1:-./statements}"
PATTERN="${2:-*.pdf}"

# Check if container is running
if ! docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "Error: Container ${CONTAINER_NAME} is not running"
    echo "Start it with: docker-compose up -d"
    exit 1
fi

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory '$SOURCE_DIR' does not exist"
    exit 1
fi

# Find and copy PDF files
PDF_FILES=$(find "$SOURCE_DIR" -name "$PATTERN" -type f)

if [ -z "$PDF_FILES" ]; then
    echo "No PDF files found in $SOURCE_DIR matching pattern $PATTERN"
    exit 0
fi

echo "Copying PDF files from $SOURCE_DIR to container $CONTAINER_NAME..."

COPIED_COUNT=0
while IFS= read -r file; do
    if [ -n "$file" ]; then
        filename=$(basename "$file")
        echo "Copying: $filename"
        docker cp "$file" "${CONTAINER_NAME}:${CONTAINER_PATH}${filename}"
        ((COPIED_COUNT++))
    fi
done <<< "$PDF_FILES"

echo "Successfully copied $COPIED_COUNT PDF files to container"
echo ""
echo "Files in container inbox:"
docker exec "$CONTAINER_NAME" ls -la /srv/aftis/inbox/