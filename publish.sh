#!/bin/bash

set -e

# export PATH=/usr/local/bin/:${PATH}
which docker
VERSION=$(cat .VERSION)

printf '%s\n' "Building uptonight version ${VERSION}"

# docker run --privileged multiarch/qemu-user-static:latest --reset -p yes --credential yes 

if [[ "${VERSION}" == "dev" ]]; then
        # --no-cache \
    #,linux/arm64/v8
    printf '%s\n' "Building development version"
    docker buildx build --progress=plain \
        -t mawinkler/uptonight:${VERSION} \
        --platform linux/amd64,linux/arm64/v8 \
        #--no-cache \
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
