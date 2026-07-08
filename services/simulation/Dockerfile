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
RUN pip install --upgrade pip && pip install fastapi uvicorn pydantic redis sqlalchemy "psycopg[binary]"

COPY app /app/app
COPY scenarios /app/scenarios

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
