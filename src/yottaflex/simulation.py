"""Physics-inspired process simulation.

The simulator is deliberately simplified, but it is internally consistent:

* Pump discharge pressure is derived from the same quadratic head curve used by
  the detector through ``head_to_pressure_bar``.
* Tank level is integrated from measured inlet/outlet flows.  Tank pressure is
  hydrostatic, giving an independent level estimate for sensor-fault checks.
* Flow and pressure units are explicit (m3/h, bar, m, %, seconds).

The simulator never writes scenario or ground-truth identifiers into telemetry.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from .config import Config
from .id_generator import IDGenerator

WATER_HEAD_TO_BAR = 1000.0 * 9.81 / 1e5  # 1 m of water = 0.0981 bar


class ProcessSimulator:
    """Simplified but mass-consistent process simulator."""

    def __init__(
        self,
        config: Config,
        master_data: Dict[str, pd.DataFrame],
        id_gen: IDGenerator,
    ):
        self.config = config
        self.master_data = master_data
        self.id_gen = id_gen
        self.rng = np.random.RandomState(config.simulation.random_seed)
        self.pumps = {row["pump_id"]: row for _, row in master_data["pumps"].iterrows()}
        self.tanks = {row["tank_id"]: row for _, row in master_data["tanks"].iterrows()}
        self.valves = {row["valve_id"]: row for _, row in master_data["valves"].iterrows()}
        self.sensors = {
            row["sensor_id"]: row for _, row in master_data["sensors"].iterrows()
        }

        self.tank_levels: Dict[str, float] = {}
        self.pump_performance_factors: Dict[str, float] = {}
        self.valve_openings: Dict[str, float] = {}
        self._sensor_physical: Dict[str, np.ndarray] = {}
        self._sensor_measured: Dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------
    # Physical relationships
    # ------------------------------------------------------------------
    def pump_head_curve(
        self, pump_id: str, flow_m3_h: float, degradation_factor: float = 1.0
    ) -> float:
        """Quadratic pump curve H(Q) = H_shutoff - k Q^2 [m]."""
        pump = self.pumps[pump_id]
        h_shutoff = (
            pump["nominal_head_m"]
            * self.config.simulation.pump_curve_shutoff_factor
            * degradation_factor
        )
        q_nominal = pump["nominal_flow_m3_h"]
        h_nominal = pump["nominal_head_m"] * degradation_factor
        k = (h_shutoff - h_nominal) / (q_nominal**2) if q_nominal > 0 else 0.001
        head = h_shutoff - k * (float(flow_m3_h) ** 2)
        return max(0.0, head)

    def pump_head_curve_array(
        self, pump_id: str, flow_m3_h: np.ndarray, degradation_factor: float = 1.0
    ) -> np.ndarray:
        pump = self.pumps[pump_id]
        h_shutoff = (
            pump["nominal_head_m"]
            * self.config.simulation.pump_curve_shutoff_factor
            * degradation_factor
        )
        q_nominal = pump["nominal_flow_m3_h"]
        h_nominal = pump["nominal_head_m"] * degradation_factor
        k = (h_shutoff - h_nominal) / (q_nominal**2) if q_nominal > 0 else 0.001
        return np.maximum(0.0, h_shutoff - k * np.square(flow_m3_h))

    def tank_volume(self, tank_id: str, level_pct: float) -> float:
        """Tank volume [m3] from level [%]."""
        return self.tanks[tank_id]["capacity_m3"] * (level_pct / 100.0)

    @staticmethod
    def calculate_mass_balance_residual(
        q_in_m3_h: float,
        q_out_m3_h: float,
        dV_dt_m3_h: float,
    ) -> float:
        """Mass balance residual R = Q_in - Q_out - dV/dt [m3/h]."""
        return q_in_m3_h - q_out_m3_h - dV_dt_m3_h

    @staticmethod
    def flow_balance_residual(
        q_in_m3_h: float,
        q_out_m3_h: float,
        level_change_pct: float,
        capacity_m3: float,
        interval_hours: float,
    ) -> float:
        """Balance residual from a level change [m3/h]."""
        if interval_hours <= 0:
            raise ValueError("interval_hours must be positive")
        dV_dt = level_change_pct / 100.0 * capacity_m3 / interval_hours
        return ProcessSimulator.calculate_mass_balance_residual(
            q_in_m3_h, q_out_m3_h, dV_dt
        )

    @staticmethod
    def head_to_pressure_bar(head_m: float) -> float:
        """Convert metres of water head to bar."""
        return float(head_m) * WATER_HEAD_TO_BAR

    @staticmethod
    def pressure_to_head_m(pressure_bar: float) -> float:
        """Convert bar to metres of water head."""
        return float(pressure_bar) / WATER_HEAD_TO_BAR

    def tank_pressure_bar(self, tank_id: str, level_pct: float) -> float:
        """Hydrostatic pressure at the tank bottom [bar]."""
        height_m = float(self.tanks[tank_id]["height_m"])
        return height_m * (float(level_pct) / 100.0) * WATER_HEAD_TO_BAR

    # ------------------------------------------------------------------
    # Generation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _ar1_noise(
        n: int, sigma: float, phi: float, rng: np.random.RandomState
    ) -> np.ndarray:
        """Deterministic stationary AR(1) noise with unit variance scaling."""
        if n <= 0 or sigma <= 0:
            return np.zeros(max(n, 0))
        innovations = rng.normal(0.0, sigma * np.sqrt(max(1.0 - phi**2, 1e-9)), n)
        values = np.empty(n)
        values[0] = rng.normal(0.0, sigma)
        for index in range(1, n):
            values[index] = phi * values[index - 1] + innovations[index]
        return values

    def _mode_arrays(self, seconds: np.ndarray, duration_seconds: float):
        """Return operating-mode IDs and a 0..1 flow ramp for each step."""
        modes = self.master_data["operating_modes"].set_index("mode_name")
        normal_id = modes.loc["NORMAL", "operating_mode_id"]
        startup_id = modes.loc["STARTUP", "operating_mode_id"]
        shutdown_id = modes.loc["SHUTDOWN", "operating_mode_id"]

        startup_seconds = self.config.simulation.startup_ramp_minutes * 60.0
        shutdown_seconds = self.config.simulation.shutdown_ramp_minutes * 60.0
        ramp = np.ones_like(seconds, dtype=float)
        mode_ids = np.full(seconds.shape, normal_id, dtype=object)

        if startup_seconds > 0:
            mask = seconds < startup_seconds
            ramp[mask] = 0.40 + 0.60 * (seconds[mask] / startup_seconds)
            mode_ids[mask] = startup_id
        if shutdown_seconds > 0:
            shutdown_start = duration_seconds - shutdown_seconds
            mask = seconds >= shutdown_start
            fraction = np.clip((seconds[mask] - shutdown_start) / shutdown_seconds, 0, 1)
            ramp[mask] = 1.0 - 0.80 * fraction
            mode_ids[mask] = shutdown_id
        return mode_ids, ramp

    def _build_profiles(self, steps: int) -> None:
        sim_cfg = self.config.simulation
        interval_seconds = sim_cfg.sampling_interval_seconds
        seconds = np.arange(steps, dtype=float) * interval_seconds
        hours = seconds / 3600.0
        duration_seconds = steps * interval_seconds
        mode_ids, ramp = self._mode_arrays(seconds, duration_seconds)
        self._mode_ids = mode_ids
        self._ramp = ramp
        self._seconds = seconds

        sensor_rows = list(self.sensors.values())
        sensor_index = {sensor["sensor_id"]: i for i, sensor in enumerate(sensor_rows)}

        # Pump profiles -------------------------------------------------
        pump_profiles: Dict[str, Dict[str, np.ndarray]] = {}
        for p_index, (pump_id, pump) in enumerate(self.pumps.items()):
            phase = 2.0 * np.pi * p_index / max(len(self.pumps), 1)
            variation = (
                sim_cfg.pump_flow_variation_pct
                / 100.0
                * np.sin(2.0 * np.pi * hours / sim_cfg.pump_flow_cycle_hours + phase)
            )
            noise = self._ar1_noise(
                steps,
                sim_cfg.pump_flow_variation_pct / 100.0 * 0.35,
                0.85,
                np.random.RandomState(sim_cfg.random_seed + 101 * (p_index + 1)),
            )
            flow = (
                float(pump["nominal_flow_m3_h"])
                * sim_cfg.pump_flow_fraction_of_nominal
                * (1.0 + variation + noise)
                * ramp
            )
            flow = np.maximum(flow, 0.0)
            head = self.pump_head_curve_array(pump_id, flow)
            pressure = head * WATER_HEAD_TO_BAR
            pump_profiles[pump_id] = {
                "flow": flow,
                "pressure": pressure,
                "head": head,
            }
        self._pump_profiles = pump_profiles

        # Tank profiles -------------------------------------------------
        tank_profiles: Dict[str, Dict[str, np.ndarray]] = {}
        for t_index, (tank_id, tank) in enumerate(self.tanks.items()):
            capacity = float(tank["capacity_m3"])
            base_flow = capacity * sim_cfg.tank_turnover_per_hour
            phase = 2.0 * np.pi * t_index / max(len(self.tanks), 1)
            variation = (
                sim_cfg.tank_flow_variation_pct
                / 100.0
                * np.sin(2.0 * np.pi * hours / 10.0 + phase)
            )
            noise = self._ar1_noise(
                steps,
                sim_cfg.tank_flow_variation_pct / 100.0 * 0.30,
                0.90,
                np.random.RandomState(sim_cfg.random_seed + 211 * (t_index + 1)),
            )
            q_in_nominal = base_flow * (1.0 + variation + noise)
            q_in = np.maximum(q_in_nominal * ramp, 0.0)

            level = float(tank["initial_level_pct"])
            levels = np.empty(steps)
            q_out = np.empty(steps)
            for step in range(steps):
                desired_dv_dt = (
                    -(level - sim_cfg.tank_level_setpoint_pct)
                    / 100.0
                    * capacity
                    / sim_cfg.tank_level_response_hours
                )
                controller_out = q_in_nominal[step] - desired_dv_dt
                controller_out = float(np.clip(controller_out, 0.0, 4.0 * base_flow))
                q_out[step] = controller_out * ramp[step]
                level += (
                    (q_in[step] - q_out[step])
                    * interval_seconds
                    / 3600.0
                    / capacity
                    * 100.0
                )
                level = float(np.clip(level, 0.5, 99.5))
                levels[step] = level

            pressure = levels / 100.0 * float(tank["height_m"]) * WATER_HEAD_TO_BAR
            tank_profiles[tank_id] = {
                "level": levels,
                "pressure": pressure,
                "inlet": q_in,
                "outlet": q_out,
            }
        self._tank_profiles = tank_profiles
        self.tank_levels = {
            tank_id: float(profile["level"][-1])
            for tank_id, profile in tank_profiles.items()
        }

        # Valve profiles ------------------------------------------------
        valve_profiles: Dict[str, np.ndarray] = {}
        for v_index, (valve_id, valve) in enumerate(self.valves.items()):
            base_flow = 20.0 + 80.0 * ((v_index + 1) / max(len(self.valves), 1))
            phase = 2.0 * np.pi * v_index / max(len(self.valves), 1)
            variation = 0.03 * np.sin(2.0 * np.pi * hours / 8.0 + phase)
            noise = self._ar1_noise(
                steps,
                0.01,
                0.85,
                np.random.RandomState(sim_cfg.random_seed + 307 * (v_index + 1)),
            )
            flow = base_flow * (1.0 + variation + noise) * ramp
            valve_profiles[valve_id] = np.maximum(flow, 0.0)
        self._valve_profiles = valve_profiles

        # Sensor physical and measured arrays ---------------------------
        physical_by_sensor: Dict[str, np.ndarray] = {}
        for sensor in sensor_rows:
            equipment_id = sensor["equipment_id"]
            equipment_type = sensor["equipment_type"]
            sensor_type = sensor["sensor_type"]
            role = sensor.get("sensor_role", "")
            if equipment_type == "PUMP":
                key = "flow" if sensor_type == "FLOW" else "pressure"
                physical = pump_profiles[equipment_id][key]
            elif equipment_type == "TANK":
                if sensor_type == "LEVEL":
                    physical = tank_profiles[equipment_id]["level"]
                elif sensor_type == "PRESSURE":
                    physical = tank_profiles[equipment_id]["pressure"]
                elif role == "inlet":
                    physical = tank_profiles[equipment_id]["inlet"]
                else:
                    physical = tank_profiles[equipment_id]["outlet"]
            elif equipment_type == "VALVE":
                physical = valve_profiles[equipment_id]
            else:
                physical = np.zeros(steps)
            physical_by_sensor[sensor["sensor_id"]] = np.asarray(physical, dtype=float)

        for sensor_id, physical in physical_by_sensor.items():
            sensor = self.sensors[sensor_id]
            idx = sensor_index[sensor_id]
            tolerance_fraction = float(sensor["accuracy_tolerance"]) / 100.0
            sigma_base = tolerance_fraction * sim_cfg.sensor_noise_fraction_of_accuracy
            if sensor["sensor_type"] == "LEVEL":
                sigma = np.maximum(sim_cfg.level_noise_floor_pct, sigma_base * np.abs(physical))
            elif sensor["sensor_type"] == "PRESSURE":
                sigma = np.maximum(0.005, sigma_base * np.abs(physical))
            else:
                sigma = np.maximum(0.15, sigma_base * np.abs(physical))
            rng = np.random.RandomState(sim_cfg.random_seed + 4099 * (idx + 1))
            noise = rng.normal(0.0, 1.0, steps) * sigma
            measured = physical + noise
            if sensor["sensor_type"] == "FLOW":
                # Industrial flow transmitters report a non-negative flow; a
                # small negative noise excursion near zero would otherwise be
                # a coverage-gap artefact at shutdown rather than a fault.
                measured = np.maximum(measured, 0.0)
            self._sensor_physical[sensor_id] = physical
            self._sensor_measured[sensor_id] = measured

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def simulate_baseline(
        self, simulation_run_id: str, duration_hours: float | None = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Simulate normal operation with physically linked measurements."""
        duration_hours = (
            self.config.simulation.duration_hours if duration_hours is None else duration_hours
        )
        interval_seconds = int(self.config.simulation.sampling_interval_seconds)
        steps = int(round(float(duration_hours) * 3600.0 / interval_seconds))
        if steps <= 0:
            raise ValueError("Simulation duration must produce at least one sample")

        self.tank_levels = {
            tank_id: float(tank["initial_level_pct"])
            for tank_id, tank in self.tanks.items()
        }
        self.pump_performance_factors = {pump_id: 1.0 for pump_id in self.pumps}
        self.valve_openings = {
            valve_id: float(valve["opening_pct"]) for valve_id, valve in self.valves.items()
        }

        self._sensor_physical = {}
        self._sensor_measured = {}
        self._build_profiles(steps)

        start_time = datetime.fromisoformat(self.config.simulation.start_time)
        timestamps = [
            (start_time + timedelta(seconds=step * interval_seconds)).isoformat()
            for step in range(steps)
        ]
        sensor_rows = list(self.sensors.values())
        sensor_count = len(sensor_rows)

        physical_matrix = np.column_stack(
            [self._sensor_physical[s["sensor_id"]] for s in sensor_rows]
        )
        measured_matrix = np.column_stack(
            [self._sensor_measured[s["sensor_id"]] for s in sensor_rows]
        )
        sensor_ids = np.tile(
            np.array([s["sensor_id"] for s in sensor_rows], dtype=object),
            (steps, 1),
        ).ravel()
        units = np.tile(
            np.array([s["measurement_unit"] for s in sensor_rows], dtype=object),
            (steps, 1),
        ).ravel()
        timestamp_column = np.repeat(np.array(timestamps, dtype=object), sensor_count)
        mode_column = np.repeat(self._mode_ids, sensor_count)
        telemetry_ids = [
            self.id_gen.telemetry_id() for _ in range(steps * sensor_count)
        ]

        telemetry_df = pd.DataFrame(
            {
                "telemetry_id": telemetry_ids,
                "sensor_id": sensor_ids,
                "simulation_run_id": simulation_run_id,
                "timestamp": timestamp_column,
                "measured_value": np.round(measured_matrix.ravel(), 3),
                "measurement_unit": units,
                "quality_status": "GOOD",
                "operating_mode_id": mode_column,
                "physical_state_value": np.round(physical_matrix.ravel(), 3),
            }
        )

        metadata = {
            "simulation_run_id": simulation_run_id,
            "duration_hours": duration_hours,
            "sampling_interval_seconds": interval_seconds,
            "steps": steps,
            "sensor_count": sensor_count,
            "total_records": len(telemetry_df),
            "record_count_derivation": (
                f"{sensor_count} sensors x {steps} samples = "
                f"{sensor_count * steps} records"
            ),
            "physics_model": "mass-consistent simplified water model",
            "head_to_pressure_bar": WATER_HEAD_TO_BAR,
        }
        return telemetry_df, metadata
