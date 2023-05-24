# Compile image
FROM ubuntu:kinetic AS compile-image

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update \
    && apt-get install -y python3-pip python3-dev \
    && cd /usr/local/bin \
    && ln -s /usr/bin/python3 python \
    && pip3 install --upgrade pip

COPY requirements.txt requirements.txt

RUN pip3 install --upgrade pip setuptools && \
    pip install --no-cache-dir -r requirements.txt --user && \
    pip list

# Run image
FROM ubuntu:kinetic AS runtime-image

RUN apt-get update \
    && apt-get install -y python3 \
    && cd /usr/local/bin \
    && ln -s /usr/bin/python3 python

COPY --from=compile-image /root/.local /root/.local
COPY --from=compile-image /etc/ssl /etc/ssl

WORKDIR /app

COPY uptonight uptonight
COPY targets targets
COPY main.py .

ENV PATH=/root/local/bin:$PATH

ENTRYPOINT ["python3", "/app/main.py"]
