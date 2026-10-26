"""Scenario injection for anomalies."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

import numpy as np
import pandas as pd

from .config import Config
from .id_generator import IDGenerator


class ScenarioInjector:
    """Inject controlled anomalies into simulation."""
    
    def __init__(self, config: Config, master_data: Dict[str, pd.DataFrame], id_gen: IDGenerator):
        self.config = config
        self.master_data = master_data
        self.id_gen = id_gen
        self.np_rng = np.random.RandomState(config.simulation.random_seed + 1000)
        
    def generate_scenarios(self, simulation_run_id: str, telemetry_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Generate scenarios and inject anomalies."""
        scenarios = []
        ground_truth = []
        
        start_time = datetime.fromisoformat(self.config.simulation.start_time)
        duration_hours = self.config.simulation.duration_hours
        end_time_total = start_time + timedelta(hours=duration_hours)
        
        timestamps = pd.to_datetime(telemetry_df["timestamp"])
        sensor_data = self.master_data["sensors"]

        if self.config.scenarios.enable_leaks:
            scenario_id = self.id_gen.scenario_id()
            tank_id = self.master_data['tanks'].iloc[0]['tank_id']
            leak_start = start_time + timedelta(hours=4)
            leak_end = start_time + timedelta(hours=8)
            
            scenario = {
                'scenario_id': scenario_id,
                'simulation_run_id': simulation_run_id,
                'issue_type': 'LEAK',
                'affected_equipment_id': tank_id,
                'affected_sensor_id': None,
                'start_time': leak_start.isoformat(),
                'end_time': leak_end.isoformat(),
                'injection_parameters': json.dumps({'leak_rate_m3_h': 5.5, 'mechanism': 'pipe_leak'}),
                'expected_observable': 'Flow balance residual, decreasing tank level faster than expected'
            }
            scenarios.append(scenario)
            
            gt = {
                'gt_id': f"GT-{self.id_gen.scenario_counter:06d}",
                'simulation_run_id': simulation_run_id,
                'scenario_id': scenario_id,
                'issue_type': 'LEAK',
                'affected_equipment_id': tank_id,
                'affected_sensor_id': None,
                'start_time': leak_start.isoformat(),
                'end_time': leak_end.isoformat(),
                'expected_detection': 'YES',
                'expected_alarm_category': 'PROCESS_FAULT',
                'injection_parameters': json.dumps({'leak_rate_m3_h': 5.5})
            }
            ground_truth.append(gt)
            
            level_sensor_ids = sensor_data.loc[
                (sensor_data["equipment_id"] == tank_id)
                & (sensor_data["sensor_type"] == "LEVEL"),
                "sensor_id",
            ]
            affected = telemetry_df.index[
                timestamps.between(leak_start, leak_end)
                & telemetry_df["sensor_id"].isin(level_sensor_ids)
            ]
            decrements = self.np_rng.uniform(0.1, 0.3, len(affected))
            telemetry_df.loc[affected, "measured_value"] -= decrements
            telemetry_df.loc[affected, "physical_state_value"] -= decrements
        
        if self.config.scenarios.enable_blockages:
            scenario_id = self.id_gen.scenario_id()
            pump_id = self.master_data['pumps'].iloc[1]['pump_id']
            block_start = start_time + timedelta(hours=10)
            block_end = start_time + timedelta(hours=14)
            
            scenario = {
                'scenario_id': scenario_id,
                'simulation_run_id': simulation_run_id,
                'issue_type': 'BLOCKAGE',
                'affected_equipment_id': pump_id,
                'affected_sensor_id': None,
                'start_time': block_start.isoformat(),
                'end_time': block_end.isoformat(),
                'injection_parameters': json.dumps({'blockage_factor': 0.6, 'mechanism': 'valve_restriction'}),
                'expected_observable': 'Reduced flow, increased pressure upstream'
            }
            scenarios.append(scenario)
            
            gt = {
                'gt_id': f"GT-{self.id_gen.scenario_counter:06d}",
                'simulation_run_id': simulation_run_id,
                'scenario_id': scenario_id,
                'issue_type': 'BLOCKAGE',
                'affected_equipment_id': pump_id,
                'affected_sensor_id': None,
                'start_time': block_start.isoformat(),
                'end_time': block_end.isoformat(),
                'expected_detection': 'YES',
                'expected_alarm_category': 'PROCESS_FAULT',
                'injection_parameters': json.dumps({'blockage_factor': 0.6})
            }
            ground_truth.append(gt)
            
            for sensor_type, factor in (("FLOW", 0.7), ("PRESSURE", 1.3)):
                sensor_ids = sensor_data.loc[
                    (sensor_data["equipment_id"] == pump_id)
                    & (sensor_data["sensor_type"] == sensor_type),
                    "sensor_id",
                ]
                affected = telemetry_df.index[
                    timestamps.between(block_start, block_end)
                    & telemetry_df["sensor_id"].isin(sensor_ids)
                ]
                telemetry_df.loc[
                    affected, ["measured_value", "physical_state_value"]
                ] *= factor
        
        if self.config.scenarios.enable_pump_degradation:
            scenario_id = self.id_gen.scenario_id()
            pump_id = self.master_data['pumps'].iloc[2]['pump_id']
            deg_start = start_time + timedelta(hours=16)
            deg_end = end_time_total
            
            scenario = {
                'scenario_id': scenario_id,
                'simulation_run_id': simulation_run_id,
                'issue_type': 'PUMP_DEGRADATION',
                'affected_equipment_id': pump_id,
                'affected_sensor_id': None,
                'start_time': deg_start.isoformat(),
                'end_time': deg_end.isoformat(),
                'injection_parameters': json.dumps({'degradation_factor': 0.75, 'mechanism': 'impeller_wear'}),
                'expected_observable': 'Reduced pump head/flow performance'
            }
            scenarios.append(scenario)
            
            gt = {
                'gt_id': f"GT-{self.id_gen.scenario_counter:06d}",
                'simulation_run_id': simulation_run_id,
                'scenario_id': scenario_id,
                'issue_type': 'PUMP_DEGRADATION',
                'affected_equipment_id': pump_id,
                'affected_sensor_id': None,
                'start_time': deg_start.isoformat(),
                'end_time': deg_end.isoformat(),
                'expected_detection': 'YES',
                'expected_alarm_category': 'PROCESS_FAULT',
                'injection_parameters': json.dumps({'degradation_factor': 0.75})
            }
            ground_truth.append(gt)
            
            flow_sensor_ids = sensor_data.loc[
                (sensor_data["equipment_id"] == pump_id)
                & (sensor_data["sensor_type"] == "FLOW"),
                "sensor_id",
            ]
            affected = telemetry_df.index[
                timestamps.between(deg_start, deg_end)
                & telemetry_df["sensor_id"].isin(flow_sensor_ids)
            ]
            telemetry_df.loc[
                affected, ["measured_value", "physical_state_value"]
            ] *= 0.85
        
        if self.config.scenarios.enable_sensor_faults:
            scenario_id = self.id_gen.scenario_id()
            # Pick a flow sensor
            flow_sensors = [s for _, s in self.master_data['sensors'].iterrows() if s['sensor_type'] == 'FLOW']
            if flow_sensors:
                sensor = flow_sensors[0]
                fault_start = start_time + timedelta(hours=6)
                fault_end = start_time + timedelta(hours=9)
                
                scenario = {
                    'scenario_id': scenario_id,
                    'simulation_run_id': simulation_run_id,
                    'issue_type': 'SENSOR_FAULT',
                    'affected_equipment_id': sensor['equipment_id'],
                    'affected_sensor_id': sensor['sensor_id'],
                    'start_time': fault_start.isoformat(),
                    'end_time': fault_end.isoformat(),
                    'injection_parameters': json.dumps({'fault_type': 'bias', 'bias_value': 15.0, 'mechanism': 'calibration_drift'}),
                    'expected_observable': 'Sensor reading inconsistent with process state'
                }
                scenarios.append(scenario)
                
                gt = {
                    'gt_id': f"GT-{self.id_gen.scenario_counter:06d}",
                    'simulation_run_id': simulation_run_id,
                    'scenario_id': scenario_id,
                    'issue_type': 'SENSOR_FAULT',
                    'affected_equipment_id': sensor['equipment_id'],
                    'affected_sensor_id': sensor['sensor_id'],
                    'start_time': fault_start.isoformat(),
                    'end_time': fault_end.isoformat(),
                    'expected_detection': 'YES',
                    'expected_alarm_category': 'SENSOR_FAULT',
                    'injection_parameters': json.dumps({'fault_type': 'bias', 'bias_value': 15.0})
                }
                ground_truth.append(gt)
                
                affected = telemetry_df.index[
                    timestamps.between(fault_start, fault_end)
                    & (telemetry_df["sensor_id"] == sensor["sensor_id"])
                ]
                telemetry_df.loc[affected, "measured_value"] = (
                    telemetry_df.loc[affected, "physical_state_value"] + 15.0
                )
                telemetry_df.loc[affected, "quality_status"] = "UNCERTAIN"
        
        scenarios_df = pd.DataFrame(scenarios)
        ground_truth_df = pd.DataFrame(ground_truth)
        return telemetry_df, scenarios_df, ground_truth_df
