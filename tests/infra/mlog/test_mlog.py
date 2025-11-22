"""Tests for mlog infrastructure.

Practical tests for setup, utils, and decorators.
"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger
from src.infra.mlog.decorators import logger_wraps, metric, timeit
from src.infra.mlog.setup import LoguruLoggingService
from src.infra.mlog.utils import MetricsCollector


@pytest.mark.unit
class TestLogguruLoggingService:
    """Test LoguruLoggingService setup."""

    def test_setup_logging_initializes(self):
        """Test setup_logging sets initialized flag."""
        # Reset state
        LoguruLoggingService._initialized = False
        logger.remove()

        # Act
        LoguruLoggingService.setup_logging(force=True)

        # Assert
        assert LoguruLoggingService._initialized is True

    def test_setup_logging_idempotent(self):
        """Test setup_logging doesn't reinitialize unless forced."""
        LoguruLoggingService._initialized = False
        logger.remove()

        # First call
        LoguruLoggingService.setup_logging()
        assert LoguruLoggingService._initialized is True

        # Second call should skip (idempotent)
        with patch("loguru.logger.remove") as mock_remove:
            LoguruLoggingService.setup_logging()
            mock_remove.assert_not_called()

    def test_setup_logging_creates_logs_directory(self, tmp_path):
        """Test that logs directory is created."""
        LoguruLoggingService._initialized = False
        logger.remove()

        with patch("src.infra.mlog.setup.BASE_DIR", tmp_path):
            logs_dir = tmp_path / "logs"
            LoguruLoggingService.setup_logging(force=True)
            assert logs_dir.exists()


@pytest.mark.unit
class TestMetricsCollector:
    """Test MetricsCollector."""

    def test_metrics_collector_initialization(self):
        """Test MetricsCollector initializes correctly."""
        collector = MetricsCollector(max_metrics_per_type=100)
        assert collector.max_metrics_per_type == 100
        assert len(collector.metrics) == 0

    def test_metrics_collector_collects_metrics(self):
        """Test MetricsCollector collects METRIC level logs."""
        collector = MetricsCollector()

        # Create mock message with proper level object
        level_mock = MagicMock()
        level_mock.name = "METRIC"
        message = MagicMock()
        message.record = {
            "level": level_mock,
            "extra": {"metric_name": "test", "value": 1.5},
            "time": MagicMock(timestamp=MagicMock(return_value=1000.0)),
        }

        # Act
        collector(message)

        # Assert
        assert "test" in collector.metrics
        assert len(collector.metrics["test"]) == 1

    def test_metrics_collector_respects_maxlen(self):
        """Test that deque respects max length."""
        collector = MetricsCollector(max_metrics_per_type=5)

        # Add 10 metrics
        for i in range(10):
            level_mock = MagicMock()
            level_mock.name = "METRIC"
            message = MagicMock()
            message.record = {
                "level": level_mock,
                "extra": {"metric_name": "test", "value": float(i)},
                "time": MagicMock(timestamp=MagicMock(return_value=0)),
            }
            collector(message)

        # Should keep only last 5
        assert len(collector.metrics["test"]) == 5

    def test_metrics_collector_clear(self):
        """Test clear method."""
        collector = MetricsCollector()

        level_mock = MagicMock()
        level_mock.name = "METRIC"
        message = MagicMock()
        message.record = {
            "level": level_mock,
            "extra": {"metric_name": "test", "value": 1.0},
            "time": MagicMock(timestamp=MagicMock(return_value=0)),
        }
        collector(message)
        assert len(collector.metrics) > 0

        collector.clear()
        assert len(collector.metrics) == 0

    def test_metrics_collector_save_to_file(self, tmp_path):
        """Test saving metrics to JSON file."""
        collector = MetricsCollector()

        level_mock = MagicMock()
        level_mock.name = "METRIC"
        message = MagicMock()
        message.record = {
            "level": level_mock,
            "extra": {"metric_name": "db_time", "value": 0.5},
            "time": MagicMock(timestamp=MagicMock(return_value=1000.0)),
        }
        collector(message)

        # Act
        metrics_file = tmp_path / "metrics.json"
        collector.save_metrics(str(metrics_file))

        # Assert
        assert metrics_file.exists()
        with open(metrics_file) as f:
            data = json.load(f)
        assert "db_time" in data
        assert len(data["db_time"]) == 1


@pytest.mark.unit
class TestLoggerWraps:
    """Test @logger_wraps decorator."""

    def test_logger_wraps_sync_function(self):
        """Test logger_wraps on sync function."""

        @logger_wraps(entry=True, exit=True)
        def my_func():
            return "result"

        with patch("loguru.logger.opt") as mock_opt:
            mock_opt.return_value.log = MagicMock()
            result = my_func()

        assert result == "result"

    @pytest.mark.asyncio
    async def test_logger_wraps_async_function(self):
        """Test logger_wraps on async function."""

        @logger_wraps(entry=True, exit=True)
        async def my_async_func():
            await asyncio.sleep(0.001)
            return "async_result"

        with patch("loguru.logger.opt") as mock_opt:
            mock_opt.return_value.log = MagicMock()
            result = await my_async_func()

        assert result == "async_result"

    def test_logger_wraps_preserves_metadata(self):
        """Test that decorator preserves function metadata."""

        @logger_wraps()
        def documented_func():
            """My docstring."""
            return 42

        assert documented_func.__name__ == "documented_func"
        assert "My docstring" in documented_func.__doc__  # type: ignore


@pytest.mark.unit
class TestTimeit:
    """Test @timeit decorator."""

    def test_timeit_logs_sync_function(self):
        """Test timeit logs execution time."""

        @timeit
        def slow_func():
            time.sleep(0.01)
            return "done"

        with patch("loguru.logger.debug") as mock_debug:
            result = slow_func()

        assert result == "done"
        mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeit_logs_async_function(self):
        """Test timeit logs async execution time."""

        @timeit
        async def slow_async():
            await asyncio.sleep(0.01)
            return "done"

        with patch("loguru.logger.debug") as mock_debug:
            result = await slow_async()

        assert result == "done"
        mock_debug.assert_called_once()

    def test_timeit_logs_on_exception(self):
        """Test timeit still logs even on exception."""

        @timeit
        def failing_func():
            raise ValueError("error")

        with patch("loguru.logger.debug") as mock_debug, pytest.raises(ValueError):
            failing_func()

        mock_debug.assert_called_once()


@pytest.mark.unit
class TestMetricDecorator:
    """Test @metric decorator."""

    def test_metric_logs_sync_function(self):
        """Test metric decorator on sync function."""

        @metric("test_metric")
        def func():
            return "value"

        with patch("loguru.logger.bind") as mock_bind:
            mock_bind.return_value.log = MagicMock()
            result = func()

        assert result == "value"
        mock_bind.assert_called()

    @pytest.mark.asyncio
    async def test_metric_logs_async_function(self):
        """Test metric decorator on async function."""

        @metric("async_metric")
        async def async_func():
            await asyncio.sleep(0.001)
            return "async_value"

        with patch("loguru.logger.bind") as mock_bind:
            mock_bind.return_value.log = MagicMock()
            result = await async_func()

        assert result == "async_value"
        mock_bind.assert_called()

    def test_metric_includes_timing_value(self):
        """Test metric includes execution time."""

        @metric("timing_metric")
        def timed_func():
            time.sleep(0.01)

        with patch("loguru.logger.bind") as mock_bind:
            mock_bind.return_value.log = MagicMock()
            timed_func()

        call_kwargs = mock_bind.call_args[1]
        assert "value" in call_kwargs
        assert call_kwargs["value"] >= 0.01
