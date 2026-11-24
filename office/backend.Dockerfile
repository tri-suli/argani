# Build context is the repository root: docker build -f office/backend.Dockerfile .
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARGANI_SCRIPTS_DIR=/app/argani-scripts \
    OFFICE_BACKEND_PORT=2212

RUN useradd --system --no-create-home office

WORKDIR /app
COPY plugins/argani/scripts /app/argani-scripts
COPY office/server /app/server

USER office
EXPOSE 2212

# Shell form so the port variable is expanded; exec keeps python as PID 1 for clean stops.
CMD exec python3 /app/server/main.py --host 0.0.0.0
