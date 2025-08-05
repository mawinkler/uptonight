# Compile image
FROM ubuntu:24.10 AS compile-image

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip python3-venv python3-dev pkg-config libhdf5-dev build-essential gcc && \
    cd /usr/local/bin && \
    ln -s /usr/bin/python3 python && \
    python3 --version && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt

RUN python3 -m venv venv && \
    venv/bin/pip install --no-cache-dir -r requirements.txt && \
    pip list

RUN venv/bin/pip install pyinstaller

COPY uptonight uptonight
COPY targets targets
COPY main.py .

RUN venv/bin/pyinstaller --recursive-copy-metadata matplotlib --collect-all dateutil --onefile main.py 

# Run image
FROM ubuntu:24.10 AS runtime-image

WORKDIR /app

# Copy only the necessary files from the build stage
COPY --from=compile-image /app/dist/main /app/main
COPY --from=compile-image /app/targets /app/targets

# Run the UpTonight executable
ENTRYPOINT ["/app/main"]
