"""Production Loguru logging setup.

This module provides clean logging configuration for production use.
Tests should use standard Python logging with pytest's caplog fixture.

Behavior:
    - Idempotent: calling setup_logging multiple times does nothing unless force=True
    - Loads YAML config if present via loguru-config
    - Falls back to stdout INFO logging if config not found
    - Standard logging module calls are intercepted and forwarded to Loguru
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from threading import Lock

from loguru import logger
from loguru_config import LoguruConfig

from src.infra.mlog.utils import InterceptHandler, MetricsCollector

BASE_DIR = Path(__file__).resolve().parents[3]  # Up to project root
CONFIG_PATH = BASE_DIR / "config_log.yaml"


class LoguruLoggingService:
    """Production Loguru logging service implementation.

    This implementation:
    - Loads YAML config if present via loguru-config
    - Falls back to stdout INFO logging if config not found
    - Intercepts standard logging module calls and forwards to Loguru
    - Registers METRIC custom level
    - Adds MetricsCollector sink for metrics
    """

    _initialized: bool = False
    _lock: Lock = Lock()

    @classmethod
    def _register_metric_level(cls) -> None:
        """Register METRIC custom level if it doesn't already exist.

        Safe to call multiple times - checks for existing level before registering.
        """
        try:
            logger.level("METRIC")  # Check if exists
        except ValueError:
            # Level doesn't exist, register it
            logger.level("METRIC", no=25)

    @classmethod
    def setup_logging(
        cls, config_path: str | Path | None = None, force: bool = False
    ) -> None:
        """Configure Loguru sinks based on configuration file (idempotent).

        METRIC level and main sinks are defined in config_log.yaml via loguru-config.
        MetricsCollector sink is added here for metrics collection.
        This function also sets up stdlib logging interception.

        Args:
            config_path: Path to YAML config file. Defaults to config_log.yaml at project root
            force: Force reconfiguration even if already initialized
        """
        with cls._lock:
            # Idempotency check
            if cls._initialized and not force:
                logger.debug("Logging already configured, skipping setup")
                return

            # Remove default sink before loading from config
            logger.remove()

            if config_path is None:
                config_path = CONFIG_PATH

            # Ensure logs directory exists before configuring file sinks
            logs_dir = BASE_DIR / "logs"
            logs_dir.mkdir(exist_ok=True, parents=True)

            try:
                if Path(config_path).is_file():
                    # Load config via loguru-config (includes METRIC level and main sinks)
                    LoguruConfig().load(config_or_file=str(config_path))
                    logger.info(f"Loaded logging config: {config_path}")
                else:
                    # Fallback: basic stdout sink + register METRIC level
                    cls._register_metric_level()
                    logger.add(
                        sys.stdout, level="INFO", format="{time} | {level} | {message}"
                    )
                    logger.warning(
                        f"Config file not found: {config_path}, using stdout fallback"
                    )
            except (FileNotFoundError, OSError, PermissionError) as e:
                # Handle file/IO errors gracefully
                cls._register_metric_level()
                logger.add(
                    sys.stdout, level="INFO", format="{time} | {level} | {message}"
                )
                logger.warning(
                    f"Config load failed ({type(e).__name__}): {e}; using fallback"
                )
            except Exception as e:  # pragma: no cover - defensive catch-all
                cls._register_metric_level()
                logger.add(
                    sys.stdout, level="INFO", format="{time} | {level} | {message}"
                )
                logger.critical(
                    f"CRITICAL: Unexpected error in logging setup: {e}", exc_info=True
                )

            # Add MetricsCollector sink for METRIC level logs
            # (METRIC level should be registered by now from YAML or fallback)
            metrics_collector = MetricsCollector()
            logger.add(metrics_collector, level="METRIC", format="{message}")

            # Intercept stdlib logging and forward to loguru
            logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

            # Mark as initialized
            cls._initialized = True


# Convenience function for backward compatibility
def setup_logging(config_path: str | Path | None = None, force: bool = False) -> None:
    """Setup logging using LoguruLoggingService implementation.

    Args:
        config_path: Path to YAML config file. Defaults to config_log.yaml at project root
        force: Force reconfiguration even if already initialized
    """
    LoguruLoggingService.setup_logging(config_path, force=force)
