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
    
    validator = Validator()
    results = validator.test_negative_scenarios(master_data)
    
    assert len(results) == 5
    for r in results:
        assert r['test_id'] in ['NEG-001', 'NEG-002', 'NEG-003', 'NEG-004', 'NEG-005']
        assert r['status'] == 'PASS'
        assert 'expected' in r
