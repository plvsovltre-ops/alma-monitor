FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY main.py ./
COPY territory_catalog.py ./
COPY response_catalog.py ./
COPY config ./config
COPY legal_core ./legal_core
COPY governance ./governance
COPY AUTHORS NOTICE CITATION.cff LICENSE LICENSE-CONTENT.md TRADEMARKS.md ./

RUN useradd --create-home --uid 10001 alma \
    && chown -R alma:alma /app

USER alma

CMD ["python", "main.py"]
