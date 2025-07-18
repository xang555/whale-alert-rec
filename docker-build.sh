#!/bin/bash

# Exit on any error
set -e

# Default values
IMAGE_NAME="whale-alert"
TAG="${1:-latest}"
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

# Build the Docker image with current user's UID/GID
echo "Building Docker image ${IMAGE_NAME}:${TAG}..."
docker build \
  --build-arg USER_UID=${CURRENT_UID} \
  --build-arg USER_GID=${CURRENT_GID} \
  -t "${IMAGE_NAME}:${TAG}" \
  .

echo -e "\n✅ Image built successfully!"