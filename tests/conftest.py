"""Shared deterministic fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from yottaflex.cli import cli
from yottaflex.config import Config, DataScaleConfig
from yottaflex.generator import DataGenerator
from yottaflex.id_generator import IDGenerator


@pytest.fixture(scope="session")
def starter_config() -> Config:
    config = Config()
    config.scale = DataScaleConfig.starter()
    config.simulation.random_seed = 20261022
    config.simulation.duration_hours = 24
    return config


@pytest.fixture(scope="session")
def master_data(starter_config: Config) -> dict[str, pd.DataFrame]:
    generator = DataGenerator(starter_config, IDGenerator(seed=starter_config.simulation.random_seed))
    return generator.generate_all()


@pytest.fixture(scope="session")
def pipeline_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the full CLI pipeline once on a small deterministic dataset."""
    root = tmp_path_factory.mktemp("yottaflex-pipeline")
    output = root / "run"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "pipeline",
            "--mode",
            "starter",
            "--seed",
            "20261022",
            "--scenario-set",
            "compact",
            "--duration",
            "7.5",
            "--sampling-interval",
            "60",
            "--output-dir",
            str(output),
        ],
    )
    if result.exception:
        raise AssertionError(
            f"Pipeline failed: {result.exception}\n{result.output}"
        )
    assert result.exit_code == 0, result.output
    return output


@pytest.fixture(scope="session")
def compact_full_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the documented ~100,000-row configuration once."""
    root = tmp_path_factory.mktemp("yottaflex-compact-100k")
    output = root / "run"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "pipeline",
            "--mode",
            "full",
            "--seed",
            "20261022",
            "--scenario-set",
            "compact",
            "--duration",
            "7.5",
            "--sampling-interval",
            "60",
            "--skip-sql",
            "--output-dir",
            str(output),
        ],
    )
    if result.exception:
        raise AssertionError(
            f"Compact pipeline failed: {result.exception}\n{result.output}"
        )
    assert result.exit_code == 0, result.output
    return output
