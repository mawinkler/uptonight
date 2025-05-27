#!/bin/bash

set -e

which docker
VERSION=$(cat .VERSION)

printf '%s\n' "Building uptonight version ${VERSION}"

# # Install Docker Buildx
# ARCH=arm64
# VERSION=v0.24.0
# curl -LO https://github.com/docker/buildx/releases/download/${VERSION}/buildx-${VERSION}.darwin-${ARCH}
# mkdir -p ~/.docker/cli-plugins
# mv buildx-${VERSION}.darwin-${ARCH} ~/.docker/cli-plugins/docker-buildx
# chmod +x ~/.docker/cli-plugins/docker-buildx

# # Create a new Buildx builder instance with the name "multiplatform-builder":
# docker buildx create --name multiplatform-builder

# # Use the new builder instance by running: 
# docker buildx use multiplatform-builder

# # Verify that the builder instance is configured for multi-platform builds: 
# docker buildx inspect --bootstrap

if [[ "${VERSION}" == "dev" ]]; then
    printf '%s\n' "Building development version"
    docker buildx build --progress=plain \
        -t mawinkler/uptonight:${VERSION} \
        --platform linux/amd64 \
        --push -f Dockerfile .
    docker pull mawinkler/uptonight:dev
    docker run --rm -v ./config.yaml:/app/config.yaml -v ./outdev:/app/out mawinkler/uptonight:dev
else
    printf '%s\n' "Building public version"
    docker buildx build \
        -t mawinkler/uptonight:${VERSION} \
        -t mawinkler/uptonight:latest \
        --platform linux/amd64,linux/arm64/v8 \
        --push .
fi
