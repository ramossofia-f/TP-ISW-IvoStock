"""Contrato privado del servicio de inferencia, separado de la API de operadores."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from ivostock.ml.normalidad import FEATURES, features


class ClassificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: int = Field(gt=0, le=2**63 - 1, strict=True)
    metrics: dict[str, float | int]

    @field_validator("metrics", mode="before")
    @classmethod
    def current_statistics(cls, value):
        if not isinstance(value, dict) or set(value) != set(FEATURES):
            raise ValueError("Se requieren las siete estadísticas actuales")
        return features(value)


class ClassificationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: StrictBool
    score: Annotated[float, Field(allow_inf_nan=False)]
    version: str = Field(pattern=r"^[a-f0-9]{64}$")
