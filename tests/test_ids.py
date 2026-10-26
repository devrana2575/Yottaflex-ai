"""Test deterministic ID generation."""

import pytest
from yottaflex.id_generator import IDGenerator


def test_deterministic_ids():
    gen1 = IDGenerator(seed=20261022)
    gen2 = IDGenerator(seed=20261022)
    
    assert gen1.facility_id() == gen2.facility_id()
    assert gen1.pump_id() == gen2.pump_id()
    assert gen1.tank_id() == gen2.tank_id()
    assert gen1.valve_id() == gen2.valve_id()
    assert gen1.pipe_id() == gen2.pipe_id()
    assert gen1.sensor_id() == gen2.sensor_id()


def test_id_formats():
    gen = IDGenerator(seed=20261022)
    assert gen.facility_id() == "FAC-001"
    assert gen.pump_id() == "PUMP-001"
    assert gen.tank_id() == "TANK-001"
    assert gen.valve_id() == "VALVE-001"
    assert gen.pipe_id() == "PIPE-001"
    assert gen.sensor_id() == "SNS-001"
    assert gen.alarm_id() == "ALARM-000001"
    assert gen.simulation_run_id().startswith("SIM-2026-")


def test_id_state():
    gen = IDGenerator(seed=20261022)
    gen.facility_id()
    gen.pump_id()
    state = gen.get_state()
    gen2 = IDGenerator(seed=20261022)
    gen2.set_state(state)
    assert gen2.facility_id() == "FAC-002"
    assert gen2.pump_id() == "PUMP-002"
