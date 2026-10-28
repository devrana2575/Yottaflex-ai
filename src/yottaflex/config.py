"""Configuration management for the simulator.

All detector thresholds live in :class:`DetectionConfig`, all scenario choices in
:class:`ScenarioConfig`, and all matching policy in :class:`EvaluationConfig`.  The
units and rationale for each threshold are documented in ``docs/detection_methodology.md``
and ``docs/evaluation_methodology.md``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict

DEFAULT_SEED = 20261022
SCENARIO_SETS = ("default", "calibration", "evaluation", "compact", "baseline")
DEFAULT_SCENARIO_SET = "default"


@dataclass
class SimulationConfig:
    """Simulation and physical-model configuration."""

    start_time: str = "2026-01-01T00:00:00"
    duration_hours: float = 24
    sampling_interval_seconds: int = 60
    time_step_seconds: int = 60
    random_seed: int = DEFAULT_SEED
    # Optional exact telemetry budget.  When set, the generator allocates the
    # budget deterministically across sensors and rejects a duration that does
    # not provide enough sampling instants.  ``None`` preserves the historical
    # full cross-product behaviour.
    telemetry_target_rows: int | None = None

    # Physical model parameters (SI unless a column says otherwise).
    gravity_m_s2: float = 9.81
    water_density_kg_m3: float = 1000.0
    fluid_viscosity_pa_s: float = 0.001

    # Tolerances used by the physics model and validation.
    mass_balance_tolerance: float = 0.01
    pressure_tolerance_pct: float = 5.0
    flow_tolerance_pct: float = 5.0
    level_tolerance_pct: float = 2.0

    # Pump baseline operating point and normal variation.
    pump_flow_fraction_of_nominal: float = 0.92
    pump_flow_variation_pct: float = 1.5
    pump_flow_cycle_hours: float = 12.0
    pump_curve_shutoff_factor: float = 1.20

    # Tank baseline: inflow is a fraction of capacity per hour; the level is
    # controlled around a setpoint by adjusting outflow.
    tank_turnover_per_hour: float = 0.02
    tank_level_setpoint_pct: float = 55.0
    tank_level_response_hours: float = 8.0
    tank_flow_variation_pct: float = 3.0

    # Sensor noise. accuracy_tolerance is interpreted as a percentage of the
    # reading; the noise sigma is a fraction of that tolerance.
    sensor_noise_fraction_of_accuracy: float = 0.25
    level_noise_floor_pct: float = 0.03

    # Normal operating-mode ramps at the beginning/end of a run. These are not
    # faults and must not produce process alarms.
    startup_ramp_minutes: int = 20
    shutdown_ramp_minutes: int = 20

    # Backwards-compatible fields retained for old configuration files. The
    # detector reads DetectionConfig.stuck_sensor_threshold_minutes.
    stuck_sensor_threshold_minutes: int = 30
    residual_threshold_m3_h: float = 2.0


@dataclass
class DataScaleConfig:
    """Master-data scale configuration."""

    mode: str = "full"  # "starter" or "full"
    facilities: int = 3
    pumps: int = 20
    tanks: int = 30
    valves: int = 60

    @classmethod
    def starter(cls) -> "DataScaleConfig":
        return cls(mode="starter", facilities=1, pumps=3, tanks=5, valves=10)

    @classmethod
    def full(cls) -> "DataScaleConfig":
        return cls(mode="full", facilities=3, pumps=20, tanks=30, valves=60)


@dataclass
class ScenarioConfig:
    """Scenario injection configuration.

    The scenario sets are deterministic. ``calibration`` and ``evaluation`` use
    different windows, severities, and equipment so thresholds cannot be tuned
    and reported on the same events.
    """

    scenario_set: str = DEFAULT_SCENARIO_SET
    # ``baseline`` contains process/sensor anomalies but deliberately excludes
    # the row-removing missing-sensor fault so an exact telemetry budget remains
    # exact after scenario injection.
    enable_leaks: bool = True
    enable_blockages: bool = True
    enable_pump_degradation: bool = True
    enable_sensor_faults: bool = True
    include_normal_windows: bool = True
    normal_window_split_minutes: int = 120
    # Sensor fault mechanisms available in the sensor-fault scenarios.
    sensor_fault_types: tuple[str, ...] = ("bias", "drift", "stuck", "missing")


@dataclass
class DetectionConfig:
    """Rule thresholds, persistence and hysteresis.

    Time windows are expressed in seconds/minutes rather than sample counts so
    the detector behaves consistently when the sampling interval changes.
    """

    # Continuous-condition requirement. Evaluation always uses the configured
    # interval; a missing reading never counts as a normal observation.
    persistence_seconds: int = 120
    persistence_samples: int = 3
    clear_samples: int = 2
    grouping_gap_seconds: int = 300

    # RULE-001 tank level bounds.
    tank_level_low_pct: float = 10.0
    tank_level_high_pct: float = 90.0
    level_bound_hysteresis_pct: float = 2.0

    # RULE-002 rapid level decline. Percentage points over a five-minute
    # regression window, with a smaller recovery threshold (hysteresis).
    level_decline_window_minutes: float = 5.0
    level_decline_threshold_pct: float = 0.30
    level_decline_recovery_pct: float = 0.15

    # RULE-003 stuck sensor.
    stuck_sensor_threshold_minutes: float = 30.0
    stuck_absolute_tolerance: float = 1e-9

    # RULE-004/008 quality and plausibility.
    quality_activation_samples: int = 1
    implausible_flow_max_m3_h: float = 500.0
    implausible_pressure_max_bar: float = 60.0
    implausible_level_min_pct: float = 0.0
    implausible_level_max_pct: float = 100.0

    # RULE-005 pump low flow. Mean over the window versus nominal.
    pump_flow_window_minutes: float = 5.0
    pump_low_flow_ratio: float = 0.80
    pump_recovery_flow_ratio: float = 0.85
    pump_flow_persistence_seconds: int = 240

    # RULE-006 tank flow balance. R = Q_in - Q_out - dV/dt.
    balance_window_minutes: float = 10.0
    balance_absolute_tolerance_m3_h: float = 5.0
    balance_relative_tolerance_pct: float = 8.0
    balance_recovery_ratio: float = 0.60
    balance_persistence_seconds: int = 480

    # RULE-007 pump operating point versus the nominal curve.
    pump_curve_tolerance_pct: float = 10.0
    pump_curve_recovery_pct: float = 6.0
    pump_curve_flow_gate_ratio: float = 0.90
    pump_curve_persistence_seconds: int = 300

    # RULE-010 level/pressure redundancy.
    level_pressure_tolerance_pct: float = 4.0
    level_pressure_persistence_seconds: int = 180

    # RULE-009 missing-data gaps.
    gap_factor: float = 1.5

    # Operating modes in which low process values are expected. If the mode is
    # not NORMAL the process rules are held; they may fire only after the mode
    # returns to NORMAL and the condition persists.
    process_suppression_modes: tuple[str, ...] = ("STARTUP", "SHUTDOWN", "MAINTENANCE")


@dataclass
class EvaluationConfig:
    """Event matching and point-evaluation policy."""

    # Detection latency is measured from ground-truth event start to the first
    # alarm activation. A late alarm is an unmatched incident and the event is
    # a false negative.
    process_latency_seconds: int = 600
    # Sensor faults are diagnosed from temporal/redundancy evidence and may
    # legitimately take up to an hour (slow drift, stuck threshold plus
    # persistence). This is fixed before any evaluation run is inspected.
    sensor_latency_seconds: int = 3600
    pre_event_tolerance_seconds: int = 60
    incident_merge_seconds: int = 0
    point_timestamp_tolerance_seconds: int = 0
    require_category_match: bool = True
    # Unknown labels are excluded from point denial and reported explicitly.
    label_scope: str = "explicit_windows"


@dataclass
class Config:
    """Main configuration."""

    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    scale: DataScaleConfig = field(default_factory=DataScaleConfig.full)
    scenarios: ScenarioConfig = field(default_factory=ScenarioConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    output_dir: str = "data/processed"
    raw_dir: str = "data/raw"
    reports_dir: str = "reports"
    database_path: str = "data/processed/yottaflex.db"
    schema_version: str = "2.0.0"
    generator_version: str = "2.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        def nested_dataclass(dc_type, payload: Dict[str, Any]):
            allowed = {item.name for item in fields(dc_type)}
            clean = {key: value for key, value in payload.items() if key in allowed}
            # JSON turns tuples into lists.
            if "process_suppression_modes" in clean and clean["process_suppression_modes"] is not None:
                clean["process_suppression_modes"] = tuple(clean["process_suppression_modes"])
            if "sensor_fault_types" in clean and clean["sensor_fault_types"] is not None:
                clean["sensor_fault_types"] = tuple(clean["sensor_fault_types"])
            return dc_type(**clean)

        data["simulation"] = nested_dataclass(SimulationConfig, data.get("simulation", {}))
        data["scale"] = nested_dataclass(DataScaleConfig, data.get("scale", {}))
        data["scenarios"] = nested_dataclass(ScenarioConfig, data.get("scenarios", {}))
        data["detection"] = nested_dataclass(DetectionConfig, data.get("detection", {}))
        data["evaluation"] = nested_dataclass(EvaluationConfig, data.get("evaluation", {}))
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def get_config_hash(self) -> str:
        """Deterministic hash independent of output paths."""
        hash_config = self.to_dict()
        for path_key in ("output_dir", "raw_dir", "reports_dir", "database_path"):
            hash_config.pop(path_key, None)
        config_str = json.dumps(hash_config, sort_keys=True)
        return hashlib.sha256(config_str.encode("utf-8")).hexdigest()[:16]


def load_config_for_dir(path: str, fallback: Config | None = None) -> Config:
    """Load ``config.json`` from an output directory, or return a default."""
    config_path = Path(path) / "config.json"
    if config_path.exists():
        return Config.load(str(config_path))
    return fallback or Config()
