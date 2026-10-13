FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000
# Load demo data (does nothing if it is already there), then serve the API.
CMD ["sh", "-c", "python -m stepboard.seed && uvicorn stepboard.api:create_app --factory --host 0.0.0.0 --port 8000"]
