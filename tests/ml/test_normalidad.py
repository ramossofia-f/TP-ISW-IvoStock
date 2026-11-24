import copy
import math
from datetime import UTC, datetime, timedelta

import pytest

from ivostock.ml.config import TrainingConfig
from ivostock.ml.normalidad import NormalityModel, features, window

pytest.importorskip("sklearn")
from ivostock.ml.training import fit  # noqa: E402


def metrics(size=50, **changes):
    return {"rows": size, "sku": size, "discarded": 0, "parse_error_rate": 0,
            "D": 0, "Z": 0, "p": 0, **changes}


def observations(count=10, provider=1, size=50, start=0):
    base = datetime(2026, 11, 17, tzinfo=UTC)
    return [{"run_id": start + n + 1, "provider_id": provider,
             "accepted_at": base + timedelta(hours=n), "features": metrics(size)}
            for n in range(count)]


def test_global_model_learns_provider_as_input_and_rejects_unseen_volume():
    data = observations() + observations(provider=2, size=5000, start=10)
    model = NormalityModel(fit(data, TrainingConfig()))
    assert model.providers == [1, 2]
    assert model.classify(1, metrics())["accepted"]
    assert model.classify(2, metrics(5000))["accepted"]
    assert not model.classify(1, metrics(5000))["accepted"]


def test_new_provider_requires_ten_observations_in_published_model():
    data = observations() + observations(9, provider=2, start=10)
    model = NormalityModel(fit(data, TrainingConfig()))
    assert model.ready(1) and not model.ready(2) and not model.ready(3)
    with pytest.raises(ValueError):
        model.classify(2, metrics())
    data += observations(1, provider=2, start=19)
    assert NormalityModel(fit(data, TrainingConfig())).ready(2)


def test_reproduction_does_not_depend_on_input_order_or_wall_clock():
    data = observations(20)
    first = fit(data, TrainingConfig())
    assert first == fit(list(reversed(data)), TrainingConfig())
    assert first["reference_at"] == max(o["accepted_at"] for o in data).isoformat()


def test_window_keeps_each_provider_and_preserves_input_history():
    data = observations(250) + observations(3, provider=2, start=1000)
    selected = window(data, TrainingConfig())
    assert len(selected) == 203 and len(data) == 253
    assert {o["run_id"] for o in selected if o["provider_id"] == 1} == set(range(51, 251))


def test_recent_healthy_observations_outweigh_old_healthy_observations():
    data = observations(10, size=5000)
    for o in data:
        o["accepted_at"] -= timedelta(days=60)
    data += observations(10, size=50, start=10)
    model = NormalityModel(fit(data, TrainingConfig(half_life_days=1)))
    assert model.score(1, metrics(50)) > model.score(1, metrics(5000))


def test_exported_inference_matches_sklearn_on_unseen_inputs():
    import numpy as np
    from sklearn.svm import OneClassSVM

    data = observations(20)
    payload = fit(data, TrainingConfig())
    model = NormalityModel(payload)
    training_x = np.array([model.vector(1, o["features"]) for o in data])
    reference = max(o["accepted_at"] for o in data)
    weights = np.array([2 ** (-(reference - o["accepted_at"]).total_seconds() / 604800)
                        for o in data])
    weights *= len(weights) / weights.sum()
    sklearn_model = OneClassSVM(nu=0.05, gamma="scale").fit(training_x, sample_weight=weights)
    for value in (metrics(), metrics(49), metrics(5000), metrics(D=0.3, p=1)):
        expected = sklearn_model.decision_function([model.vector(1, value)])[0]
        assert model.score(1, value) == pytest.approx(expected, abs=1e-9)


def test_artifact_tampering_is_detected():
    payload = copy.deepcopy(fit(observations(), TrainingConfig()))
    payload["intercept"] += 1
    with pytest.raises(ValueError, match="Hash"):
        NormalityModel(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, "12"])
def test_bad_statistics_never_become_training_inputs(value):
    with pytest.raises(ValueError):
        features(metrics(rows=value))


def test_discard_details_are_replaced_by_count():
    result = features(metrics(discarded=[{"line": 2, "reason": "quantity"}]))
    assert result["discarded"] == 1 and all(math.isfinite(n) for n in result.values())


@pytest.mark.parametrize("config", [
    {"min_runs": 0}, {"history_per_provider": 9}, {"half_life_days": 0},
    {"half_life_days": float("nan")}, {"nu": 0}, {"nu": 1.1},
])
def test_invalid_learning_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        TrainingConfig(**config)
