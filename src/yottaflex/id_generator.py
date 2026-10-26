"""Deterministic ID generation for all entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class IDGenerator:
    """Centralized deterministic ID generation."""
    
    seed: int = 20261022
    facility_counter: int = 0
    pump_counter: int = 0
    tank_counter: int = 0
    valve_counter: int = 0
    pipe_counter: int = 0
    sensor_counter: int = 0
    telemetry_counter: int = 0
    operating_mode_counter: int = 0
    alarm_counter: int = 0
    simulation_run_counter: int = 0
    scenario_counter: int = 0
    event_counter: int = 0
    
    def reset(self) -> None:
        """Reset all counters."""
        self.facility_counter = 0
        self.pump_counter = 0
        self.tank_counter = 0
        self.valve_counter = 0
        self.pipe_counter = 0
        self.sensor_counter = 0
        self.telemetry_counter = 0
        self.operating_mode_counter = 0
        self.alarm_counter = 0
        self.simulation_run_counter = 0
        self.scenario_counter = 0
        self.event_counter = 0
    
    def facility_id(self) -> str:
        self.facility_counter += 1
        return f"FAC-{self.facility_counter:03d}"
    
    def pump_id(self) -> str:
        self.pump_counter += 1
        return f"PUMP-{self.pump_counter:03d}"
    
    def tank_id(self) -> str:
        self.tank_counter += 1
        return f"TANK-{self.tank_counter:03d}"
    
    def valve_id(self) -> str:
        self.valve_counter += 1
        return f"VALVE-{self.valve_counter:03d}"
    
    def pipe_id(self) -> str:
        self.pipe_counter += 1
        return f"PIPE-{self.pipe_counter:03d}"
    
    def sensor_id(self) -> str:
        self.sensor_counter += 1
        return f"SNS-{self.sensor_counter:03d}"
    
    def telemetry_id(self) -> str:
        self.telemetry_counter += 1
        return f"TEL-{self.telemetry_counter:012d}"
    
    def operating_mode_id(self) -> str:
        self.operating_mode_counter += 1
        return f"OPM-{self.operating_mode_counter:03d}"
    
    def alarm_id(self) -> str:
        self.alarm_counter += 1
        return f"ALARM-{self.alarm_counter:06d}"
    
    def simulation_run_id(self) -> str:
        self.simulation_run_counter += 1
        # Use year from config
        return f"SIM-2026-{self.simulation_run_counter:06d}"
    
    def scenario_id(self) -> str:
        self.scenario_counter += 1
        return f"SCN-{self.scenario_counter:06d}"
    
    def event_id(self) -> str:
        self.event_counter += 1
        return f"EVT-{self.event_counter:012d}"
    
    def get_state(self) -> Dict[str, int]:
        """Get current counter state for reproducibility."""
        return {
            "facility_counter": self.facility_counter,
            "pump_counter": self.pump_counter,
            "tank_counter": self.tank_counter,
            "valve_counter": self.valve_counter,
            "pipe_counter": self.pipe_counter,
            "sensor_counter": self.sensor_counter,
            "telemetry_counter": self.telemetry_counter,
            "operating_mode_counter": self.operating_mode_counter,
            "alarm_counter": self.alarm_counter,
            "simulation_run_counter": self.simulation_run_counter,
            "scenario_counter": self.scenario_counter,
            "event_counter": self.event_counter,
        }
    
    def set_state(self, state: Dict[str, int]) -> None:
        """Set counter state."""
        for k, v in state.items():
            if hasattr(self, k):
                setattr(self, k, v)
