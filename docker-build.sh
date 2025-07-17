#!/bin/bash

# Exit on any error
set -e

# Default values
IMAGE_NAME="whale-alert"
TAG="${1:-latest}"

# Build the Docker image
echo "Building Docker image ${IMAGE_NAME}:${TAG}..."
docker build -t "${IMAGE_NAME}:${TAG}" .

echo "\nImage built successfully!"
echo "To run the image: docker run -d --name whale-alert -p 8000:8000 ${IMAGE_NAME}:${TAG}"
echo "To push to a registry: docker tag ${IMAGE_NAME}:${TAG} your-registry/${IMAGE_NAME}:${TAG} && docker push your-registry/${IMAGE_NAME}:${TAG}"
