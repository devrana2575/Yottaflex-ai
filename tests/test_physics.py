"""Test physics models."""

import pytest
from yottaflex.simulation import ProcessSimulator
from yottaflex.config import Config
from yottaflex.id_generator import IDGenerator
from yottaflex.generator import DataGenerator


def test_pump_curve():
    config = Config()
    config.scale.mode = 'starter'
    config.scale.facilities = 1
    config.scale.pumps = 1
    config.scale.tanks = 1
    config.scale.valves = 1
    
    id_gen = IDGenerator(seed=20261022)
    gen = DataGenerator(config, id_gen)
    master_data = gen.generate_all()
    
    sim = ProcessSimulator(config, master_data, id_gen)
    pump_id = master_data['pumps'].iloc[0]['pump_id']
    
    h1 = sim.pump_head_curve(pump_id, 0)
    h2 = sim.pump_head_curve(pump_id, 50)
    assert h1 > h2  # Head decreases with flow


def test_tank_volume():
    config = Config()
    config.scale.mode = 'starter'
    config.scale.facilities = 1
    config.scale.pumps = 1
    config.scale.tanks = 1
    config.scale.valves = 1
    
    id_gen = IDGenerator(seed=20261022)
    gen = DataGenerator(config, id_gen)
    master_data = gen.generate_all()
    
    sim = ProcessSimulator(config, master_data, id_gen)
    tank_id = master_data['tanks'].iloc[0]['tank_id']
    tank = master_data['tanks'][master_data['tanks']['tank_id']==tank_id].iloc[0]
    
    vol = sim.tank_volume(tank_id, 50)
    assert vol == tank['capacity_m3'] * 0.5


def test_mass_balance():
    residual = ProcessSimulator.calculate_mass_balance_residual(100, 60, 30)
    assert residual == 10  # 100 - 60 - 30 = 10
