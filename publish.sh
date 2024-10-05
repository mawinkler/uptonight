#!/bin/bash

set -e

VERSION=$(cat .VERSION)

printf '%s\n' "Building uptonight version ${VERSION}"

docker run --privileged multiarch/qemu-user-static:latest --reset -p yes --credential yes

if [[ "${VERSION}" == "dev" ]]; then
    # --no-cache \
    printf '%s\n' "Building development version"
    docker buildx build \
        -t mawinkler/uptonight:${VERSION} \
        --platform linux/amd64,linux/arm64/v8 \
        --push .
else
    printf '%s\n' "Building public version"
    docker buildx build \
        -t mawinkler/uptonight:${VERSION} \
        -t mawinkler/uptonight:latest \
        --platform linux/amd64,linux/arm64/v8 \
        --push .
fi
