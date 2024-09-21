#!/bin/bash

set -e

VERSION=$(cat .VERSION)

printf '%s\n' "Building uptonight version ${VERSION}"

docker run --privileged multiarch/qemu-user-static:latest --reset -p yes --credential yes

    # --no-cache \
docker buildx build \
    -t mawinkler/uptonight:${VERSION} \
    -t mawinkler/uptonight:latest \
    --platform linux/amd64,linux/arm64/v8 \
    --push .

