"""Physics-inspired process simulation."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

import numpy as np
import pandas as pd

from .config import Config
from .id_generator import IDGenerator
from .generator import DataGenerator


class ProcessSimulator:
    """Simplified physics-inspired process simulator."""
    
    def __init__(self, config: Config, master_data: Dict[str, pd.DataFrame], id_gen: IDGenerator):
        self.config = config
        self.master_data = master_data
        self.id_gen = id_gen
        self.rng = random.Random(config.simulation.random_seed)
        self.np_rng = np.random.RandomState(config.simulation.random_seed)
        
        # Build lookup structures
        self.pumps = {row['pump_id']: row for _, row in master_data['pumps'].iterrows()}
        self.tanks = {row['tank_id']: row for _, row in master_data['tanks'].iterrows()}
        self.valves = {row['valve_id']: row for _, row in master_data['valves'].iterrows()}
        self.sensors = {row['sensor_id']: row for _, row in master_data['sensors'].iterrows()}
        
        # Physical state
        self.tank_levels = {}  # tank_id -> level_fraction
        self.pump_performance_factors = {}  # pump_id -> degradation factor (1.0 = normal)
        self.valve_openings = {}  # valve_id -> opening_pct
        
    def pump_head_curve(self, pump_id: str, flow_m3_h: float, degradation_factor: float = 1.0) -> float:
        """
        Simplified pump curve: H(Q) = H_shutoff - k * Q^2
        with degradation applied
        """
        pump = self.pumps[pump_id]
        h_shutoff = pump['nominal_head_m'] * 1.2 * degradation_factor
        q_nominal = pump['nominal_flow_m3_h']
        # Calculate k from nominal point
        h_nominal = pump['nominal_head_m'] * degradation_factor
        k = (h_shutoff - h_nominal) / (q_nominal ** 2) if q_nominal > 0 else 0.001
        head = h_shutoff - k * (flow_m3_h ** 2)
        return max(0, head)
    
    def tank_volume(self, tank_id: str, level_pct: float) -> float:
        """Calculate tank volume from level."""
        tank = self.tanks[tank_id]
        return tank['capacity_m3'] * (level_pct / 100.0)
    
    @staticmethod
    def calculate_mass_balance_residual(
        q_in_m3_h: float,
        q_out_m3_h: float,
        dV_dt_m3_h: float,
    ) -> float:
        """
        Mass balance: R = Q_in - Q_out - dV/dt
        """
        residual = q_in_m3_h - q_out_m3_h - dV_dt_m3_h
        return residual
    
    def simulate_baseline(self, simulation_run_id: str, duration_hours: int = None) -> Tuple[pd.DataFrame, Dict]:
        """Simulate baseline normal operation."""
        duration_hours = duration_hours or self.config.simulation.duration_hours
        interval_seconds = self.config.simulation.sampling_interval_seconds
        steps = int(duration_hours * 3600 / interval_seconds)
        
        # Initialize
        for tank_id in self.tanks:
            self.tank_levels[tank_id] = self.tanks[tank_id]['initial_level_pct'] / 100.0
        for pump_id in self.pumps:
            self.pump_performance_factors[pump_id] = 1.0
        for valve_id in self.valves:
            self.valve_openings[valve_id] = self.valves[valve_id]['opening_pct']
        
        telemetry_records = []
        start_time = datetime.fromisoformat(self.config.simulation.start_time)
        
        # Generate telemetry for all sensors
        for step in range(steps):
            timestamp = start_time + timedelta(seconds=step * interval_seconds)
            ts_str = timestamp.isoformat()
            
            # Simulate for each sensor
            for sensor_id, sensor in self.sensors.items():
                eq_id = sensor['equipment_id']
                eq_type = sensor['equipment_type']
                stype = sensor['sensor_type']
                unit = sensor['measurement_unit']
                
                # Generate base physical value
                if stype == 'FLOW' and eq_type == 'PUMP':
                    # Pump flow around nominal
                    pump = self.pumps[eq_id]
                    base_flow = pump['nominal_flow_m3_h'] * self.rng.uniform(0.8, 1.0)
                    # Add small variation
                    phys_value = base_flow * (1.0 + self.rng.gauss(0, 0.02))
                elif stype == 'PRESSURE':
                    phys_value = self.rng.uniform(3.0, 8.0)  # bar
                    phys_value *= (1.0 + self.rng.gauss(0, 0.01))
                elif stype == 'LEVEL' and eq_type == 'TANK':
                    # Tank level evolves slowly
                    if eq_id in self.tank_levels:
                        # Simple model
                        tank = self.tanks[eq_id]
                        q_in = self.rng.uniform(10, 50)
                        q_out = self.rng.uniform(10, 50)
                        dV = (q_in - q_out) * (interval_seconds / 3600.0)
                        new_vol = self.tank_volume(eq_id, self.tank_levels[eq_id] * 100) + dV
                        new_vol = max(0, min(tank['capacity_m3'], new_vol))
                        self.tank_levels[eq_id] = new_vol / tank['capacity_m3']
                        phys_value = self.tank_levels[eq_id] * 100.0
                    else:
                        phys_value = self.rng.uniform(30, 70)
                elif stype == 'FLOW':
                    phys_value = self.rng.uniform(20, 100) * (1.0 + self.rng.gauss(0, 0.02))
                else:
                    phys_value = self.rng.uniform(0, 100)
                
                # Add sensor noise
                noise = self.np_rng.normal(0, sensor['accuracy_tolerance'] * 0.1)
                measured_value = phys_value + noise
                
                record = {
                    'telemetry_id': self.id_gen.telemetry_id(),
                    'sensor_id': sensor_id,
                    'simulation_run_id': simulation_run_id,
                    'timestamp': ts_str,
                    'measured_value': round(float(measured_value), 3),
                    'measurement_unit': unit,
                    'quality_status': 'GOOD',
                    'operating_mode_id': self.master_data['operating_modes'].iloc[0]['operating_mode_id'],  # NORMAL
                    'physical_state_value': round(float(phys_value), 3)
                }
                telemetry_records.append(record)
        
        telemetry_df = pd.DataFrame(telemetry_records)
        metadata = {
            'simulation_run_id': simulation_run_id,
            'duration_hours': duration_hours,
            'steps': steps,
            'total_records': len(telemetry_df)
        }
        return telemetry_df, metadata
