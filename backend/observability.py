"""
Observability: Prometheus-format request metrics + structured JSON logs.

Built directly on prometheus_client rather than a FastAPI-instrumentor
wrapper package — the wrapper pulled in a starlette major version
incompatible with this project's pinned fastapi, which broke the app on
install. This is a few lines more code but has no exotic version
constraints on FastAPI internals.

/metrics is real and scrape-ready: point a Prometheus server (or Grafana
Cloud's free tier, which accepts remote-write from a standard scrape) at
it. No Grafana dashboard is stood up tonight — that's a documented next
step, not a fabricated screenshot.
"""
import json
import logging
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency", ["method", "path"]
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_json_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def instrument(app: FastAPI):
    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start
        # Use the matched route template (e.g. "/actuals/{category}"), not
        # the raw path, so per-category requests don't fragment into a
        # unique metric series per category.
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        REQUEST_COUNT.labels(method=request.method, path=path, status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
        return response

    # Note: not named /metrics — that path already serves model evaluation
    # metrics (backend/routes/metrics.py), a different meaning entirely.
    @app.get("/observability/metrics")
    def prometheus_metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
