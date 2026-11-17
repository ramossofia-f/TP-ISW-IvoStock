"""Consultas HTTP de sólo lectura compartidas por métricas y observador."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx


def endpoints():
    urls = {
        "api": os.getenv("API_URL", "http://api:8000") + "/health",
        "simulator": os.getenv("SIMULATOR_URL", "http://simulator:8001") + "/health",
        "provider": os.getenv("PROVIDER_URL", "http://provider:8081") + "/health",
    }
    ml_url = os.getenv("ML_URL", "").rstrip("/")
    if ml_url:
        urls.update({"ml": ml_url + "/health/live", "ml_ready": ml_url + "/health"})
    return urls


def probe(name, url):
    started = time.monotonic()
    code = None
    available = False
    try:
        response = httpx.get(url, timeout=5, follow_redirects=False)
        code = response.status_code
        available = code == 200 and response.json().get("status") == "ok"
    except (httpx.HTTPError, ValueError, AttributeError):
        pass
    elapsed = time.monotonic() - started
    return name, {
        "available": available and elapsed <= 5,
        "http_status": code,
        "response_seconds": round(elapsed, 6),
        "checked_at": datetime.now(UTC).isoformat(),
    }


def http_components():
    urls = endpoints()
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        return dict(pool.map(lambda pair: probe(*pair), urls.items()))
