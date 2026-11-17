"""Consultas HTTP de sólo lectura compartidas por métricas y observador."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx


def endpoints():
    return {
        "api": os.getenv("API_URL", "http://api:8000") + "/health",
        "simulator": os.getenv("SIMULATOR_URL", "http://simulator:8001") + "/health",
        "provider": os.getenv("PROVIDER_URL", "http://provider:8081") + "/health",
    }


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
    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(lambda pair: probe(*pair), endpoints().items()))
