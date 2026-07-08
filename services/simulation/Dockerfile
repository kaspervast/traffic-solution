FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV SUMO_HOME=/usr/share/sumo

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    sumo \
    sumo-tools \
    sumo-doc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install from pyproject.toml (single source of truth for deps) rather than
# a hand-maintained pip list here, which had drifted and was missing
# pydantic-settings/httpx/pyproj that app/config.py and network_builder.py
# actually import.
COPY pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip && pip install -e .

COPY app /app/app
COPY scenarios /app/scenarios

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
