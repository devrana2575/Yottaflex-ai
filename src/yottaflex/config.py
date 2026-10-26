"""Configuration management for the simulator."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_SEED = 20261022


@dataclass
class SimulationConfig:
    """Simulation configuration."""
    start_time: str = "2026-01-01T00:00:00"
    duration_hours: int = 24
    sampling_interval_seconds: int = 60
    time_step_seconds: int = 60
    random_seed: int = DEFAULT_SEED
    
    # Physical model parameters
    gravity_m_s2: float = 9.81
    water_density_kg_m3: float = 1000.0
    fluid_viscosity_pa_s: float = 0.001
    
    # Tolerances
    mass_balance_tolerance: float = 0.01  # 1% tolerance
    pressure_tolerance_pct: float = 5.0
    flow_tolerance_pct: float = 5.0
    level_tolerance_pct: float = 2.0
    
    # Detection thresholds
    stuck_sensor_threshold_minutes: int = 30
    residual_threshold_m3_h: float = 2.0


@dataclass
class DataScaleConfig:
    """Data scale configuration."""
    mode: str = "full"  # "starter" or "full"
    facilities: int = 3
    pumps: int = 20
    tanks: int = 30
    valves: int = 60
    
    # Derived
    @classmethod
    def starter(cls) -> "DataScaleConfig":
        return cls(mode="starter", facilities=1, pumps=3, tanks=5, valves=10)
    
    @classmethod
    def full(cls) -> "DataScaleConfig":
        return cls(mode="full", facilities=3, pumps=20, tanks=30, valves=60)


@dataclass
class ScenarioConfig:
    """Scenario injection configuration."""
    enable_leaks: bool = True
    enable_blockages: bool = True
    enable_pump_degradation: bool = True
    enable_sensor_faults: bool = True


@dataclass
class Config:
    """Main configuration."""
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    scale: DataScaleConfig = field(default_factory=DataScaleConfig.full)
    scenarios: ScenarioConfig = field(default_factory=ScenarioConfig)
    output_dir: str = "data/processed"
    raw_dir: str = "data/raw"
    reports_dir: str = "reports"
    database_path: str = "data/processed/yottaflex.db"
    schema_version: str = "1.0.0"
    generator_version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, path: str) -> "Config":
        with open(path, 'r') as f:
            data = json.load(f)
        # Reconstruct nested objects
        sim_cfg = SimulationConfig(**data.get('simulation', {}))
        scale_cfg = DataScaleConfig(**data.get('scale', {}))
        scenario_cfg = ScenarioConfig(**data.get('scenarios', {}))
        data['simulation'] = sim_cfg
        data['scale'] = scale_cfg
        data['scenarios'] = scenario_cfg
        return cls(**data)
    
    def get_config_hash(self) -> str:
        """Get deterministic hash of configuration."""
        import hashlib
        hash_config = self.to_dict()
        for path_key in ("output_dir", "raw_dir", "reports_dir", "database_path"):
            hash_config.pop(path_key)
        config_str = json.dumps(hash_config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
