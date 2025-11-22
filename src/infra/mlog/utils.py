"""setup loguru logging."""

import inspect
import json
import logging
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


class MetricsCollector:
    r"""Logger sink to collect METRIC level logs into a structured format.

    Thread-safe collector for performance metrics. Accumulates metrics with timestamps
    for later analysis and export. Uses bounded deque to prevent memory leaks.

    Example:
        ```python
        from time import perf_counter
        from loguru import logger

        start = perf_counter()
        # ...do something...
        exec_time = perf_counter() - start
        logger.bind(
            metric_name="ocr_processing", value=exec_time
        ).log("METRIC", "OCR processing completed")

        # Later, save metrics
        collector.save_metrics("metrics.json")
        ```

    Args:
        max_metrics_per_type: Maximum metrics to retain per metric name (prevents memory leak)
    """

    def __init__(self, max_metrics_per_type: int = 10000) -> None:
        self.max_metrics_per_type = max_metrics_per_type
        self.metrics: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.max_metrics_per_type)
        )
        self._lock = Lock()  # Thread-safety for concurrent requests

    def __call__(self, message: Any) -> None:
        """Process a log message and extract metrics.

        Args:
            message: Loguru log message record
        """
        record = message.record
        if record["level"].name != "METRIC":
            return

        extra = record["extra"]
        if "metric_name" in extra and "value" in extra:
            with self._lock:
                self.metrics[extra["metric_name"]].append(
                    {
                        "value": extra["value"],
                        "timestamp": record["time"].timestamp(),
                    }
                )

    def clear(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self.metrics.clear()
            logger.debug("Metrics cleared")

    def save_metrics(self, path: str = "metrics.json") -> None:
        """Save collected metrics to JSON file.

        Args:
            path: Output file path (default: metrics.json)

        Raises:
            IOError: If file write fails
        """
        try:
            with self._lock, open(path, "w") as f:
                # Convert deque to list for JSON serialization
                metrics_dict = {k: list(v) for k, v in self.metrics.items()}
                json.dump(metrics_dict, f, indent=2)
            logger.info(f"Metrics saved to {path}")
        except OSError as e:
            logger.error(f"Failed to save metrics to {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving metrics to {path}: {e}")
            raise
