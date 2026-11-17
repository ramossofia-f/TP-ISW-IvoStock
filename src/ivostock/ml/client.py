"""Un segundo de plazo total: el motor no espera la recuperación de ML."""

import asyncio
import logging
import os

import httpx
from pydantic import ValidationError

from ivostock.ml.contracts import ClassificationOut
from ivostock.ml.normalidad import EPSILON, features

log = logging.getLogger("ivostock.ml.client")


async def request_classification(url, token, provider, metrics):
    async with asyncio.timeout(1.0):
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=1.0) as client:
            response = await client.post(
                url.rstrip("/") + "/classify", headers={"Authorization": "Bearer " + token},
                json={"provider_id": provider, "metrics": features(metrics)},
            )
            if response.status_code == 503:
                reason = response.json().get("detail")
                if reason in ("insufficient_history", "invalid_model"):
                    return None, reason
            response.raise_for_status()
            result = ClassificationOut.model_validate(response.json())
            if result.accepted != (result.score >= -EPSILON):
                raise ValueError("Decisión ML inconsistente")
            return result.model_dump(), None


def evaluate(provider, metrics):
    # RF-13: ningún modelo ni respaldo puede liberar lo que frena la guarda.
    if metrics["p"] > 0.5:
        return {"source": "rules", "fallback_reason": None, "version": None, "score": None,
                "guard_accepted": False, "accepted": False}
    url, token = os.getenv("ML_URL", ""), os.getenv("ML_TOKEN", "")
    reason = "unconfigured"
    if url and token:
        try:
            result, reason = asyncio.run(request_classification(url, token, provider, metrics))
            if result is not None:
                return {"source": "ml", "fallback_reason": None, "guard_accepted": True, **result}
        except (TimeoutError, httpx.TimeoutException):
            reason = "timeout"
        except (ValueError, TypeError, KeyError, ValidationError):
            reason = "invalid_response"
        except (httpx.HTTPError, OSError):
            reason = "unavailable"
    log.info("Validación por reglas de respaldo", extra={"component": "ml", "provider": provider,
                                                       "fallback_reason": reason})
    return {"source": "rules", "fallback_reason": reason, "version": None, "score": None,
            "guard_accepted": True, "accepted": True}
