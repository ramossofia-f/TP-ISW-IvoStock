import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ivostock.health import WORKERS

spec = importlib.util.spec_from_file_location(
    "medir_disponibilidad", Path(__file__).resolve().parents[1] / "scripts/medir_disponibilidad.py"
)
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)


def healthy(monkeypatch):
    components = {name: {"available": True} for name in ("api", "provider", "simulator", *WORKERS)}
    monkeypatch.setattr(
        campaign.metrics,
        "current",
        lambda _: {"age_seconds": 30, "state": {"components": components}, "workers": {}},
    )


def test_start_freezes_a_full_day_and_cannot_replace_it_after_a_reboot(tmp_path, monkeypatch):
    healthy(monkeypatch)
    path = tmp_path / "campaign.json"
    begin = datetime(2026, 11, 20, 12, 0, 40, tzinfo=UTC)
    saved = campaign.start(None, path, "revision", "lab", now=begin)
    assert saved["start"] == "2026-11-20T12:01:00+00:00"
    assert saved["end"] == "2026-11-21T12:01:00+00:00"
    with pytest.raises(FileExistsError):
        campaign.start(None, path, "revision", "lab", now=begin + timedelta(hours=12))
    assert json.loads(path.read_text()) == saved


def test_start_rejects_a_stale_sampler(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign.metrics, "current", lambda _: {"age_seconds": 120})
    with pytest.raises(ValueError, match="vigente"):
        campaign.start(None, tmp_path / "campaign.json", "revision", "lab")


def test_export_after_reboot_keeps_original_window_and_missing_minutes(tmp_path, monkeypatch):
    healthy(monkeypatch)
    path = tmp_path / "campaign.json"
    begin = datetime(2026, 11, 20, 12, tzinfo=UTC)
    saved = campaign.start(None, path, "revision", "lab", now=begin)
    end = datetime.fromisoformat(saved["end"])
    calls = []

    def summary(_, start, finish):
        calls.append((start, finish))
        return {
            "expected_samples": 1440,
            "missing_samples": 60,
            "availability": {
                name: {"availability_percent": 100 * 1380 / 1440} for name in ("api", "engine")
            },
        }

    monkeypatch.setattr(campaign.metrics, "summary", summary)
    monkeypatch.setattr(campaign.metrics, "history", lambda _, a, b: {"samples": []})
    with pytest.raises(ValueError, match="no terminó"):
        campaign.report(None, path, now=end - timedelta(seconds=1))
    result = campaign.report(None, path, now=end + timedelta(hours=2))
    assert calls == [(datetime.fromisoformat(saved["start"]), end)]
    assert result["summary"]["missing_samples"] == 60
    assert not result["meets_rnf07"]
    assert json.loads(Path(result["evidence"]).read_text())["campaign"] == saved
    with pytest.raises(FileExistsError):
        campaign.report(None, path, now=end + timedelta(hours=3))
