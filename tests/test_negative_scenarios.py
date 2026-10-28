"""Test the five required negative scenarios."""

import pytest
from yottaflex.config import Config, DataScaleConfig
from yottaflex.id_generator import IDGenerator
from yottaflex.generator import DataGenerator
from yottaflex.validation import Validator


def test_negative_scenarios():
    config = Config()
    config.scale = DataScaleConfig.starter()
    config.simulation.random_seed = 20261022
    
    id_gen = IDGenerator(seed=20261022)
    gen = DataGenerator(config, id_gen)
    master_data = gen.generate_all()
    before = {name: len(frame) for name, frame in master_data.items()}
    
    validator = Validator()
    results = validator.test_negative_scenarios(master_data)
    
    assert len(results) == 5
    by_id = {row["test_id"]: row for row in results}
    assert set(by_id) == {"NEG-001", "NEG-002", "NEG-003", "NEG-004", "NEG-005"}
    for row in results:
        assert row["status"] == "PASS", row
        assert "expected" in row
    assert "missing equipment node" in by_id["NEG-001"]["description"]
    assert "above 100%" in by_id["NEG-002"]["description"]
    assert "residual" in by_id["NEG-003"]["description"]
    assert "lineage" in by_id["NEG-004"]["description"]
    assert "sensor-quality" in by_id["NEG-005"]["description"]
    # The negative controls operate on copies; the normal baseline is intact.
    assert {name: len(frame) for name, frame in master_data.items()} == before
