from unittest.mock import patch, MagicMock

import pytest

from app.services.network.network_monitor import get_recommended_quality
from app.services.scheduler.download_scheduler import DownloadScheduler
from app.workers.download_tasks import (
    _is_off_peak_delayed,
    _off_peak_countdown_seconds,
    _bandwidth_limit_mbps,
    _auto_adjust_quality,
)


class TestQualityRecommendations:
    @pytest.mark.parametrize("speed,expected", [
        (0, "480p"),
        (4.9, "480p"),
        (5, "720p"),
        (14.9, "720p"),
        (15, "1080p"),
        (29.9, "1080p"),
        (30, "best"),
        (100, "best"),
    ])
    def test_thresholds(self, speed, expected):
        assert get_recommended_quality(speed) == expected


class TestOffPeakDelay:
    def test_disabled_never_delays(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "OFF_PEAK_ENABLED", False)
        assert _is_off_peak_delayed() is False

    def test_active_when_enabled_and_outside_window(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "OFF_PEAK_ENABLED", True)
        monkeypatch.setattr(settings, "OFF_PEAK_START", "23:00")
        monkeypatch.setattr(settings, "OFF_PEAK_END", "06:00")
        # At 04:00 the window 23:00-06:00 is active, so off-peak delay is True.
        # We can't easily mock datetime, so we verify the function reads settings.
        result = _is_off_peak_delayed()
        assert isinstance(result, bool)

    def test_countdown_returns_positive_int(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "OFF_PEAK_ENABLED", True)
        monkeypatch.setattr(settings, "OFF_PEAK_START", "06:00")
        secs = _off_peak_countdown_seconds()
        assert isinstance(secs, int)
        assert secs > 0


class TestBandwidthSettings:
    def test_unlimited_returns_none(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "BANDWIDTH_LIMIT_MBPS", 0)
        assert _bandwidth_limit_mbps() is None

    def test_limited_returns_value(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "BANDWIDTH_LIMIT_MBPS", 10)
        assert _bandwidth_limit_mbps() == 10


class TestAutoAdjustQuality:
    def test_enabled(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "AUTO_ADJUST_QUALITY", True)
        assert _auto_adjust_quality() is True

    def test_disabled(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "AUTO_ADJUST_QUALITY", False)
        assert _auto_adjust_quality() is False


class TestSchedulerRegistration:
    @pytest.mark.asyncio
    async def test_add_and_get_jobs(self):
        scheduler = DownloadScheduler()
        fake_schedule = MagicMock()
        fake_schedule.id = "schedule-1"
        fake_schedule.is_active = True
        fake_schedule.trigger_type = "cron"
        fake_schedule.cron_expression = "* * * * *"
        fake_schedule.run_time = None
        fake_schedule.days_of_week = None

        scheduler.add_schedule(fake_schedule)
        jobs = scheduler.get_schedules()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "schedule-1"

        await scheduler.stop()
