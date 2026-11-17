"""Configuración del detector global; independiente de las credenciales del motor."""

import math
import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TrainingConfig:
    min_runs: int = 10
    history_per_provider: int = 200
    half_life_days: float = 7.0
    nu: float = 0.05

    def __post_init__(self):
        if self.min_runs < 1 or self.history_per_provider < self.min_runs:
            raise ValueError("Historial ML inválido")
        if not math.isfinite(self.half_life_days) or self.half_life_days <= 0:
            raise ValueError("Semivida ML inválida")
        if not math.isfinite(self.nu) or not 0 < self.nu <= 1:
            raise ValueError("nu ML inválido")

    @classmethod
    def from_env(cls):
        return cls(
            int(os.getenv("ML_MIN_RUNS", "10")),
            int(os.getenv("ML_HISTORY_PER_PROVIDER", "200")),
            float(os.getenv("ML_HALF_LIFE_DAYS", "7")),
            float(os.getenv("ML_NU", "0.05")),
        )

    def to_dict(self):
        return asdict(self)
