"""Fixtures for mlog testing."""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from loguru import logger

# Ensure src is in path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infra.mlog.setup import LoguruLoggingService  # noqa: E402


@pytest.fixture(autouse=True)
def reset_logger() -> Generator:
    """Reset logger state before each test."""
    original_initialized = LoguruLoggingService._initialized
    logger.remove()
    LoguruLoggingService._initialized = False

    yield

    logger.remove()
    LoguruLoggingService._initialized = original_initialized


@pytest.fixture
def temp_config_file() -> Generator[Path]:
    """Create a temporary YAML config file for testing."""
    yaml_content = """handlers:
  - sink: ext://sys.stdout
    format: "{time} | {level} | {message}"
    level: DEBUG

levels:
  - name: METRIC
    "no": 25

extra:
  test: "true"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = Path(f.name)

    yield temp_path

    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_metrics_file() -> Generator[Path]:
    """Create a temporary metrics file path for testing."""
    temp_path = Path(tempfile.gettempdir()) / "test_metrics.json"
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def isolated_logger() -> Generator:
    """Provide an isolated logger instance for testing."""
    logger.remove()
    logger.add(lambda _: None, format="{message}")
    yield logger
    logger.remove()
