"""Master data generator for YottaFlex simulator."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

import numpy as np
import pandas as pd

from .config import Config
from .id_generator import IDGenerator


class DataGenerator:
    """Generates master data for the simulator."""
    
    def __init__(self, config: Config, id_gen: IDGenerator = None):
        self.config = config
        self.id_gen = id_gen or IDGenerator(seed=config.simulation.random_seed)
        self.rng = random.Random(config.simulation.random_seed)
        self.np_rng = np.random.RandomState(config.simulation.random_seed)
        
        # Storage
        self.facilities = []
        self.pumps = []
        self.tanks = []
        self.valves = []
        self.pipes = []
        self.sensors = []
        self.operating_modes = []
        self.node_registry = {}  # node_id -> (facility_id, node_type, equipment_id)
        
    def generate_all(self) -> Dict[str, pd.DataFrame]:
        """Generate all master data."""
        self.id_gen.reset()
        self.rng = random.Random(self.config.simulation.random_seed)
        self.np_rng = np.random.RandomState(self.config.simulation.random_seed)
        
        # Generate in order
        self._generate_facilities()
        self._generate_operating_modes()
        self._generate_pumps()
        self._generate_tanks()
        self._generate_valves()
        self._generate_topology_and_pipes()
        self._generate_sensors()
        
        return {
            'facilities': pd.DataFrame(self.facilities),
            'pumps': pd.DataFrame(self.pumps),
            'tanks': pd.DataFrame(self.tanks),
            'valves': pd.DataFrame(self.valves),
            'pipes': pd.DataFrame(self.pipes),
            'sensors': pd.DataFrame(self.sensors),
            'operating_modes': pd.DataFrame(self.operating_modes),
        }
    
    def _generate_facilities(self):
        facility_names = [
            "North Refinery Complex",
            "South Processing Plant",
            "East Distribution Hub"
        ]
        location_codes = ["NR-01", "SP-02", "ED-03"]
        
        for i in range(self.config.scale.facilities):
            facility_id = self.id_gen.facility_id()
            facility = {
                'facility_id': facility_id,
                'facility_name': facility_names[i] if i < len(facility_names) else f"Facility {i+1}",
                'location_code': location_codes[i] if i < len(location_codes) else f"FC-{i+1:02d}",
                'lifecycle_state': 'ACTIVE',
                'created_at': datetime(2026, 1, 1, 0, 0, 0).isoformat()
            }
            self.facilities.append(facility)
    
    def _generate_operating_modes(self):
        modes = [
            ("NORMAL", "Normal steady-state operation", "ALL_EQUIPMENT_ACTIVE"),
            ("STARTUP", "System startup sequence", "SEQUENTIAL_START"),
            ("SHUTDOWN", "System shutdown sequence", "SEQUENTIAL_STOP"),
            ("MAINTENANCE", "Maintenance mode with reduced capacity", "LIMITED_OPERATION")
        ]
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        for name, desc, config_str in modes:
            om_id = self.id_gen.operating_mode_id()
            mode = {
                'operating_mode_id': om_id,
                'mode_name': name,
                'description': desc,
                'permitted_configuration': config_str,
                'effective_from': base_time.isoformat(),
                'effective_to': None,
                'lifecycle_state': 'ACTIVE'
            }
            self.operating_modes.append(mode)
    
    def _generate_pumps(self):
        pumps_per_facility, remainder = divmod(
            self.config.scale.pumps, self.config.scale.facilities
        )
        for facility_index, facility in enumerate(self.facilities):
            facility_pump_count = pumps_per_facility + (facility_index < remainder)
            for i in range(facility_pump_count):
                pump_id = self.id_gen.pump_id()
                # Generate realistic nominal values
                nominal_flow = self.rng.uniform(50, 200)  # m3/h
                nominal_head = self.rng.uniform(30, 150)  # m
                rated_power = (nominal_flow * nominal_head * 9.81) / (3600 * 0.7)  # rough calc
                efficiency = self.rng.uniform(65, 85)
                
                pump = {
                    'pump_id': pump_id,
                    'facility_id': facility['facility_id'],
                    'pump_name': f"P-{pump_id.split('-')[1]}",
                    'nominal_flow_m3_h': round(nominal_flow, 2),
                    'nominal_head_m': round(nominal_head, 2),
                    'rated_power_kw': round(rated_power, 2),
                    'efficiency_pct': round(efficiency, 2),
                    'lifecycle_state': 'ACTIVE'
                }
                self.pumps.append(pump)
                # Register as node
                node_id = f"NODE-{pump_id}"
                self.node_registry[node_id] = (facility['facility_id'], 'PUMP', pump_id)
    
    def _generate_tanks(self):
        tanks_per_facility, remainder = divmod(
            self.config.scale.tanks, self.config.scale.facilities
        )
        for facility_index, facility in enumerate(self.facilities):
            facility_tank_count = tanks_per_facility + (facility_index < remainder)
            for i in range(facility_tank_count):
                tank_id = self.id_gen.tank_id()
                capacity = self.rng.uniform(100, 1000)  # m3
                initial_level = self.rng.uniform(30, 70)  # %
                
                tank = {
                    'tank_id': tank_id,
                    'facility_id': facility['facility_id'],
                    'tank_name': f"TK-{tank_id.split('-')[1]}",
                    'capacity_m3': round(capacity, 2),
                    'initial_level_pct': round(initial_level, 2),
                    'lifecycle_state': 'ACTIVE'
                }
                self.tanks.append(tank)
                # Register as node
                node_id = f"NODE-{tank_id}"
                self.node_registry[node_id] = (facility['facility_id'], 'TANK', tank_id)
    
    def _generate_valves(self):
        valves_per_facility, remainder = divmod(
            self.config.scale.valves, self.config.scale.facilities
        )
        valve_types = ['BALL', 'GATE', 'GLOBE', 'BUTTERFLY']
        states = ['OPEN', 'PARTIAL', 'CLOSED']
        for facility_index, facility in enumerate(self.facilities):
            facility_valve_count = valves_per_facility + (facility_index < remainder)
            for i in range(facility_valve_count):
                valve_id = self.id_gen.valve_id()
                vtype = self.rng.choice(valve_types)
                state = self.rng.choice(states)
                if state == 'OPEN':
                    opening = self.rng.uniform(90, 100)
                elif state == 'CLOSED':
                    opening = self.rng.uniform(0, 5)
                else:
                    opening = self.rng.uniform(20, 80)
                
                valve = {
                    'valve_id': valve_id,
                    'facility_id': facility['facility_id'],
                    'valve_name': f"V-{valve_id.split('-')[1]}",
                    'valve_type': vtype,
                    'initial_state': state,
                    'opening_pct': round(opening, 2),
                    'lifecycle_state': 'ACTIVE'
                }
                self.valves.append(valve)
                # Register as node
                node_id = f"NODE-{valve_id}"
                self.node_registry[node_id] = (facility['facility_id'], 'VALVE', valve_id)
    
    def _generate_topology_and_pipes(self):
        """Generate connected topology with pipes."""
        # Create a connected graph per facility
        import networkx as nx
        
        facility_nodes = {}
        for node_id, (fac_id, node_type, eq_id) in self.node_registry.items():
            if fac_id not in facility_nodes:
                facility_nodes[fac_id] = []
            facility_nodes[fac_id].append(node_id)
        
        all_pipes = []
        for facility in self.facilities:
            fac_id = facility['facility_id']
            nodes = facility_nodes.get(fac_id, [])
            if len(nodes) < 2:
                continue
            
            # Create a connected graph (spanning tree + some extra edges)
            G = nx.Graph()
            for n in nodes:
                G.add_node(n)
            
            # Build connected topology
            nodes_list = list(nodes)
            self.rng.shuffle(nodes_list)
            # Connect in a tree structure first
            for i in range(1, len(nodes_list)):
                G.add_edge(nodes_list[0], nodes_list[i])  # star topology
            # Add some random connections for realism
            num_extra = min(10, len(nodes_list))
            for _ in range(num_extra):
                if len(nodes_list) >= 2:
                    a, b = self.rng.sample(nodes_list, 2)
                    if not G.has_edge(a, b):
                        G.add_edge(a, b)
            
            # Create pipes for edges
            for source, target in G.edges():
                pipe_id = self.id_gen.pipe_id()
                diameter = self.rng.uniform(100, 500)  # mm
                length = self.rng.uniform(10, 200)  # m
                roughness = self.rng.uniform(0.01, 0.1)
                
                pipe = {
                    'pipe_id': pipe_id,
                    'facility_id': fac_id,
                    'source_node_id': source,
                    'target_node_id': target,
                    'length_m': round(length, 2),
                    'diameter_mm': round(diameter, 2),
                    'roughness_factor': round(roughness, 4),
                    'lifecycle_state': 'ACTIVE'
                }
                all_pipes.append(pipe)
        
        self.pipes = all_pipes
    
    def _generate_sensors(self):
        """Generate sensors for equipment."""
        sensor_types_map = {
            'PUMP': ['FLOW', 'PRESSURE'],
            'TANK': ['LEVEL', 'PRESSURE'],
            'VALVE': ['PRESSURE', 'FLOW'],
            'PIPE': ['FLOW', 'PRESSURE']
        }
        units_map = {
            'FLOW': 'm3/h',
            'PRESSURE': 'bar',
            'LEVEL': '%',
            'TEMPERATURE': 'C'
        }
        
        sensors_per_facility = max(10, (len(self.pumps) + len(self.tanks) + len(self.valves)) // self.config.scale.facilities * 2)
        for facility in self.facilities:
            fac_id = facility['facility_id']
            # Add sensors for all equipment in this facility
            for pump in self.pumps:
                if pump['facility_id'] != fac_id:
                    continue
                for stype in sensor_types_map.get('PUMP', []):
                    sensor_id = self.id_gen.sensor_id()
                    sensor = {
                        'sensor_id': sensor_id,
                        'facility_id': fac_id,
                        'equipment_id': pump['pump_id'],
                        'equipment_type': 'PUMP',
                        'sensor_type': stype,
                        'measurement_unit': units_map[stype],
                        'sampling_interval_seconds': self.config.simulation.sampling_interval_seconds,
                        'accuracy_tolerance': round(self.rng.uniform(0.5, 2.0), 2),
                        'lifecycle_state': 'ACTIVE'
                    }
                    self.sensors.append(sensor)
            
            for tank in self.tanks:
                if tank['facility_id'] != fac_id:
                    continue
                for stype in sensor_types_map.get('TANK', []):
                    sensor_id = self.id_gen.sensor_id()
                    sensor = {
                        'sensor_id': sensor_id,
                        'facility_id': fac_id,
                        'equipment_id': tank['tank_id'],
                        'equipment_type': 'TANK',
                        'sensor_type': stype,
                        'measurement_unit': units_map[stype],
                        'sampling_interval_seconds': self.config.simulation.sampling_interval_seconds,
                        'accuracy_tolerance': round(self.rng.uniform(0.5, 2.0), 2),
                        'lifecycle_state': 'ACTIVE'
                    }
                    self.sensors.append(sensor)
            
            for valve in self.valves:
                if valve['facility_id'] != fac_id:
                    continue
                for stype in sensor_types_map.get('VALVE', []):
                    sensor_id = self.id_gen.sensor_id()
                    sensor = {
                        'sensor_id': sensor_id,
                        'facility_id': fac_id,
                        'equipment_id': valve['valve_id'],
                        'equipment_type': 'VALVE',
                        'sensor_type': stype,
                        'measurement_unit': units_map[stype],
                        'sampling_interval_seconds': self.config.simulation.sampling_interval_seconds,
                        'accuracy_tolerance': round(self.rng.uniform(0.5, 2.0), 2),
                        'lifecycle_state': 'ACTIVE'
                    }
                    self.sensors.append(sensor)
    
    def validate_topology(self) -> Tuple[bool, List[Dict]]:
        """Validate topology."""
        issues = []
        # Check for unique node IDs (all are unique by construction)
        # Check pipe endpoints
        for pipe in self.pipes:
            if pipe['source_node_id'] not in self.node_registry:
                issues.append({
                    'type': 'MISSING_NODE',
                    'pipe_id': pipe['pipe_id'],
                    'missing': pipe['source_node_id']
                })
            if pipe['target_node_id'] not in self.node_registry:
                issues.append({
                    'type': 'MISSING_NODE',
                    'pipe_id': pipe['pipe_id'],
                    'missing': pipe['target_node_id']
                })
            if pipe['source_node_id'] == pipe['target_node_id']:
                issues.append({
                    'type': 'SELF_LOOP',
                    'pipe_id': pipe['pipe_id']
                })
            # Check facility consistency
            src_fac = self.node_registry.get(pipe['source_node_id'], (None,))[0]
            tgt_fac = self.node_registry.get(pipe['target_node_id'], (None,))[0]
            if src_fac != tgt_fac or src_fac != pipe['facility_id']:
                issues.append({
                    'type': 'FACILITY_INCONSISTENCY',
                    'pipe_id': pipe['pipe_id']
                })
        
        # Check connectivity per facility using NetworkX
        import networkx as nx
        for facility in self.facilities:
            fac_id = facility['facility_id']
            G = nx.Graph()
            fac_pipes = [p for p in self.pipes if p['facility_id'] == fac_id]
            for p in fac_pipes:
                G.add_edge(p['source_node_id'], p['target_node_id'])
            if len(G.nodes()) > 0 and not nx.is_connected(G):
                issues.append({
                    'type': 'DISCONNECTED_TOPOLOGY',
                    'facility_id': fac_id,
                    'components': nx.number_connected_components(G)
                })
        
        return len(issues) == 0, issues
