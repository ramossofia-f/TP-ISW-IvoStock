"""Inferencia RBF en Python puro, sin pickle ni dependencias de entrenamiento."""

import hashlib
import json
import math
from collections import Counter
from datetime import datetime

FEATURES = ("rows", "sku", "discarded", "parse_error_rate", "D", "Z", "p")
SCHEMA = "normalidad-rbf-v1"
EPSILON = 1e-8


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def features(metrics):
    """Sólo estadísticas existentes; nunca se transporta el CSV al servicio ML."""
    result = {}
    for name in FEATURES:
        value = metrics[name]
        if name == "discarded" and isinstance(value, list):
            value = len(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Estadística ML inválida")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Estadística ML inválida")
        if name in FEATURES[:3] and value != int(value):
            raise ValueError("Conteo ML inválido")
        if name in FEATURES[3:] and value > 1:
            raise ValueError("Proporción ML inválida")
        result[name] = value
    return result


def numeric(metrics):
    values = features(metrics)
    return [math.log1p(values[n]) if n in FEATURES[:3] else values[n] for n in FEATURES]


def timestamp(value):
    at = datetime.fromisoformat(value) if isinstance(value, str) else value
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Fecha ML sin zona horaria")
    return at


def window(observations, config):
    ordered = sorted(observations, key=lambda o: (timestamp(o["accepted_at"]), o["run_id"]))
    counts = Counter()
    selected = []
    for observation in reversed(ordered):
        provider = observation["provider_id"]
        if counts[provider] < config.history_per_provider:
            selected.append(observation)
            counts[provider] += 1
    return list(reversed(selected))


class NormalityModel:
    def __init__(self, payload):
        self.payload = payload
        if payload["schema"] != SCHEMA or payload["features"] != list(FEATURES):
            raise ValueError("Esquema de modelo ML incompatible")
        self.version = payload["version"]
        if digest({k: v for k, v in payload.items() if k != "version"}) != self.version:
            raise ValueError("Hash de modelo ML incorrecto")
        self.providers = payload["providers"]
        self.counts = payload["counts"]
        if (
            not self.providers or self.providers != sorted(set(self.providers))
            or any(type(p) is not int or p < 1 for p in self.providers)
            or set(self.counts) != {str(p) for p in self.providers}
            or any(type(n) is not int or n < 1 for n in self.counts.values())
            or type(payload["config"]["min_runs"]) is not int
            or payload["config"]["min_runs"] < 1
        ):
            raise ValueError("Proveedores de modelo ML inválidos")
        size = len(FEATURES) + len(self.providers)
        self.means = payload["means"]
        self.scales = payload["scales"]
        self.support = payload["support_vectors"]
        self.coefficients = payload["dual_coef"]
        self.intercept = payload["intercept"]
        self.gamma = payload["gamma"]
        if (
            len(self.means) != len(FEATURES) or len(self.scales) != len(FEATURES)
            or not self.support or len(self.support) != len(self.coefficients)
            or any(len(v) != size for v in self.support)
        ):
            raise ValueError("Dimensiones de modelo ML inválidas")
        numbers = [*self.means, *self.scales, *self.coefficients, self.gamma, self.intercept]
        numbers.extend(x for vector in self.support for x in vector)
        if any(isinstance(x, bool) or not math.isfinite(x) for x in numbers):
            raise ValueError("Parámetros de modelo ML inválidos")
        if min(self.scales) <= 0 or self.gamma <= 0:
            raise ValueError("Escala de modelo ML inválida")

    def ready(self, provider):
        return self.counts.get(str(provider), 0) >= self.payload["config"]["min_runs"]

    def vector(self, provider, metrics):
        if provider not in self.providers:
            raise ValueError("Proveedor sin historial entrenado")
        x = [(v - m) / s for v, m, s in zip(numeric(metrics), self.means, self.scales)]
        return x + [float(p == provider) for p in self.providers]

    def score(self, provider, metrics):
        x = self.vector(provider, metrics)
        score = self.intercept + sum(
            coefficient * math.exp(-self.gamma * sum((a - b) ** 2 for a, b in zip(x, sv)))
            for coefficient, sv in zip(self.coefficients, self.support)
        )
        if not math.isfinite(score):
            raise ValueError("Puntaje ML inválido")
        return score

    def classify(self, provider, metrics):
        if not self.ready(provider):
            raise ValueError("Proveedor sin historial suficiente")
        score = self.score(provider, metrics)
        return {"accepted": score >= -EPSILON, "score": score, "version": self.version}
