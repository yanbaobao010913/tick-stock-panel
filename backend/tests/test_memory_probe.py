from __future__ import annotations

import logging
import time

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services import memory_probe


@pytest.fixture(autouse=True)
def _stop_probe_sampler():
    yield
    memory_probe.stop_sampler()


def test_rss_mb_returns_positive_value() -> None:
    value = memory_probe.rss_mb()
    assert value is not None
    assert value > 0


def test_rss_phase_logs_delta_for_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.memory_probe")

    with memory_probe.rss_phase("unit.ok"):
        pass

    message = next(
        record.getMessage() for record in caplog.records
        if "RSS unit.ok" in record.getMessage()
    )
    assert "->" in message
    assert "MB" in message


def test_rss_phase_logs_and_reraises_on_failure(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.memory_probe")

    with (
        pytest.raises(RuntimeError, match="boom"),
        memory_probe.rss_phase("unit.fail"),
    ):
        raise RuntimeError("boom")

    assert any("RSS unit.fail" in record.getMessage() for record in caplog.records)


def test_start_sampler_is_idempotent_and_logs_samples(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.memory_probe")

    memory_probe.start_sampler(0.01)
    memory_probe.start_sampler(0.01)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if any("RSS sample" in record.getMessage() for record in caplog.records):
            break
        time.sleep(0.02)

    messages = [record.getMessage() for record in caplog.records]
    assert sum("RSS sampler started" in message for message in messages) == 1
    assert any("RSS sample" in message for message in messages)


def test_start_sampler_disabled_for_non_positive_interval(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.memory_probe")

    memory_probe.start_sampler(0)

    assert memory_probe._thread is None
    assert not any(
        "RSS sampler started" in record.getMessage() for record in caplog.records
    )


def test_negative_memory_probe_interval_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(memory_probe_interval_s=-1)
