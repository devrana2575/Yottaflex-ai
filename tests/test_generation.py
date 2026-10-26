"""Test master data generation."""

import pytest
from yottaflex.config import Config, DataScaleConfig
from yottaflex.id_generator import IDGenerator
from yottaflex.generator import DataGenerator


def test_starter_generation():
    config = Config()
    config.scale = DataScaleConfig.starter()
    config.simulation.random_seed = 20261022
    
    id_gen = IDGenerator(seed=20261022)
    gen = DataGenerator(config, id_gen)
    master_data = gen.generate_all()
    
    assert len(master_data['facilities']) == 1
    assert len(master_data['pumps']) == 3
    assert len(master_data['tanks']) == 5
    assert len(master_data['valves']) == 10
    assert not master_data['pipes'].empty
    assert not master_data['sensors'].empty


def test_full_generation():
    config = Config()
    config.scale = DataScaleConfig.full()
    config.simulation.random_seed = 20261022
    
    id_gen = IDGenerator(seed=20261022)
    gen = DataGenerator(config, id_gen)
    master_data = gen.generate_all()
    
    assert len(master_data['facilities']) == 3
    assert len(master_data['pumps']) == 20
    assert len(master_data['tanks']) == 30
    assert len(master_data['valves']) == 60


def test_topology_validation():
    config = Config()
    config.scale = DataScaleConfig.starter()
    config.simulation.random_seed = 20261022
    
    id_gen = IDGenerator(seed=20261022)
    gen = DataGenerator(config, id_gen)
    master_data = gen.generate_all()
    
    is_valid, issues = gen.validate_topology()
    assert is_valid == True
    assert isinstance(issues, list)


def test_deterministic_generation():
    config = Config()
    config.scale = DataScaleConfig.starter()
    config.simulation.random_seed = 20261022
    
    gen1 = DataGenerator(config, IDGenerator(seed=20261022))
    md1 = gen1.generate_all()
    
    gen2 = DataGenerator(config, IDGenerator(seed=20261022))
    md2 = gen2.generate_all()
    
    assert len(md1['facilities']) == len(md2['facilities'])
    assert md1['facilities'].iloc[0]['facility_id'] == md2['facilities'].iloc[0]['facility_id']
