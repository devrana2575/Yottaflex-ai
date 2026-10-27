"""Deterministic scenario definition and injection.

Scenario identity, timing, equipment and severity live in an explicit matrix.
Injection only changes physical/measured values; it never writes a scenario or
ground-truth identifier into telemetry.  Normal windows are explicit ground
truth rows covering the complement of the injected anomaly intervals, so no
timestamp is silently assumed to be negative.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .config import Config
from .id_generator import IDGenerator
from .simulation import WATER_HEAD_TO_BAR


@dataclass(frozen=True)
class ScenarioPlan:
    """A deterministic scenario template."""

    key: str
    issue_type: str
    equipment_kind: str
    equipment_index: int
    start_hour: float
    end_hour: float
    severity: str
    expected_category: str
    sensor_role: str | None = None
    sensor_fault_type: str | None = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_observable: str = ""


# Calibration and evaluation use different times, equipment, and severities.
SCENARIO_MATRIX: Dict[str, List[ScenarioPlan]] = {
    "default": [
        ScenarioPlan(
            "D-LEAK-01", "LEAK", "TANK", 0, 4.0, 8.0, "medium", "PROCESS_FAULT",
            parameters={"leak_fraction_capacity_per_hour": 0.05},
            expected_observable="Level and hydrostatic pressure decline faster than measured flows allow",
        ),
        ScenarioPlan(
            "D-BLOCK-01", "BLOCKAGE", "PUMP", 1, 10.0, 14.0, "medium", "PROCESS_FAULT",
            parameters={"flow_factor": 0.65, "pressure_factor": 1.20},
            expected_observable="Pump flow falls and discharge pressure rises above the nominal curve",
        ),
        ScenarioPlan(
            "D-DEGRADE-01", "PUMP_DEGRADATION", "PUMP", 2, 16.0, 20.0, "medium", "PROCESS_FAULT",
            parameters={"flow_factor": 0.80, "head_factor": 0.72},
            expected_observable="Pump flow and head fall below the nominal operating curve",
        ),
        ScenarioPlan(
            "D-SENSOR-01", "SENSOR_FAULT", "TANK", 1, 6.0, 9.0, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="bias",
            parameters={"bias_pct": 6.0},
            expected_observable="Level disagrees with hydrostatic pressure while flows remain consistent",
        ),
    ],
    "calibration": [
        ScenarioPlan(
            "C-LEAK-01", "LEAK", "TANK", 0, 3.0, 5.0, "medium", "PROCESS_FAULT",
            parameters={"leak_fraction_capacity_per_hour": 0.05},
            expected_observable="Level and pressure decline relative to flow balance",
        ),
        ScenarioPlan(
            "C-BLOCK-01", "BLOCKAGE", "PUMP", 0, 8.0, 10.0, "light", "PROCESS_FAULT",
            parameters={"flow_factor": 0.85, "pressure_factor": 1.15},
            expected_observable="Small flow reduction and above-curve pressure",
        ),
        ScenarioPlan(
            "C-DEGRADE-01", "PUMP_DEGRADATION", "PUMP", 2, 12.0, 14.0, "medium", "PROCESS_FAULT",
            parameters={"flow_factor": 0.80, "head_factor": 0.72},
            expected_observable="Operating point moves below the nominal curve",
        ),
        ScenarioPlan(
            "C-SENSOR-BIAS-01", "SENSOR_FAULT", "TANK", 2, 5.0, 6.5, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="bias",
            parameters={"bias_pct": -7.0},
            expected_observable="Level/pressure redundancy disagreement",
        ),
        ScenarioPlan(
            "C-SENSOR-DRIFT-01", "SENSOR_FAULT", "TANK", 3, 16.0, 17.5, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="drift",
            parameters={"drift_total_pct": 9.0},
            expected_observable="Growing level/pressure redundancy disagreement",
        ),
        ScenarioPlan(
            "C-SENSOR-STUCK-01", "SENSOR_FAULT", "TANK", 1, 18.0, 19.0, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="stuck",
            parameters={"stuck_minutes": 60},
            expected_observable="Constant level readings while pressure varies",
        ),
        ScenarioPlan(
            "C-SENSOR-MISSING-01", "SENSOR_FAULT", "TANK", 0, 21.0, 22.0, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="missing",
            parameters={"missing_minutes": 60},
            expected_observable="Expected sampling cadence is broken",
        ),
    ],
    "evaluation": [
        ScenarioPlan(
            "E-LEAK-01", "LEAK", "TANK", 1, 2.0, 3.5, "light", "PROCESS_FAULT",
            parameters={"leak_fraction_capacity_per_hour": 0.015},
            expected_observable="Small unexplained loss; may only support an uncertain leak diagnosis",
        ),
        ScenarioPlan(
            "E-LEAK-02", "LEAK", "TANK", 2, 6.0, 8.0, "medium", "PROCESS_FAULT",
            parameters={"leak_fraction_capacity_per_hour": 0.05},
            expected_observable="Sustained level/pressure decline and positive flow-balance residual",
        ),
        ScenarioPlan(
            "E-LEAK-03", "LEAK", "TANK", 3, 13.0, 15.0, "severe", "PROCESS_FAULT",
            parameters={"leak_fraction_capacity_per_hour": 0.10},
            expected_observable="Large sustained level/pressure decline and flow-balance residual",
        ),
        ScenarioPlan(
            "E-BLOCK-01", "BLOCKAGE", "PUMP", 1, 9.0, 11.0, "light", "PROCESS_FAULT",
            parameters={"flow_factor": 0.85, "pressure_factor": 1.15},
            expected_observable="Flow reduction with above-curve discharge pressure",
        ),
        ScenarioPlan(
            "E-BLOCK-02", "BLOCKAGE", "PUMP", 2, 17.0, 19.0, "severe", "PROCESS_FAULT",
            parameters={"flow_factor": 0.50, "pressure_factor": 1.30},
            expected_observable="Severe flow reduction with high discharge pressure",
        ),
        ScenarioPlan(
            "E-DEGRADE-01", "PUMP_DEGRADATION", "PUMP", 0, 10.0, 12.0, "light", "PROCESS_FAULT",
            parameters={"flow_factor": 0.92, "head_factor": 0.88},
            expected_observable="Small operating-point shift below the nominal curve",
        ),
        ScenarioPlan(
            "E-DEGRADE-02", "PUMP_DEGRADATION", "PUMP", 1, 20.0, 22.0, "severe", "PROCESS_FAULT",
            parameters={"flow_factor": 0.65, "head_factor": 0.52},
            expected_observable="Large flow and head loss",
        ),
        ScenarioPlan(
            "E-SENSOR-BIAS-01", "SENSOR_FAULT", "TANK", 0, 4.0, 5.5, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="bias",
            parameters={"bias_pct": 6.0},
            expected_observable="Level/pressure redundancy disagreement",
        ),
        ScenarioPlan(
            "E-SENSOR-DRIFT-01", "SENSOR_FAULT", "TANK", 4, 15.5, 17.0, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="drift",
            parameters={"drift_total_pct": 8.0},
            expected_observable="Slowly growing redundancy disagreement",
        ),
        ScenarioPlan(
            "E-SENSOR-STUCK-01", "SENSOR_FAULT", "TANK", 0, 18.0, 19.0, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="stuck",
            parameters={"stuck_minutes": 60},
            expected_observable="Constant level while pressure remains dynamic",
        ),
        ScenarioPlan(
            "E-SENSOR-MISSING-01", "SENSOR_FAULT", "TANK", 1, 21.0, 22.0, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="missing",
            parameters={"missing_minutes": 60},
            expected_observable="Missing samples for one sensor",
        ),
    ],
    # Deterministic 7.5-hour set used by the ~99,000-row scale configuration.
    # All windows fit inside 7.5 hours, unlike the 24-hour default matrix.
    "compact": [
        ScenarioPlan(
            "K-LEAK-01", "LEAK", "TANK", 0, 2.0, 3.5, "medium", "PROCESS_FAULT",
            parameters={"leak_fraction_capacity_per_hour": 0.05},
            expected_observable="Sustained level/pressure decline and positive flow-balance residual",
        ),
        ScenarioPlan(
            "K-BLOCK-01", "BLOCKAGE", "PUMP", 1, 3.8, 4.8, "light", "PROCESS_FAULT",
            parameters={"flow_factor": 0.85, "pressure_factor": 1.15},
            expected_observable="Flow reduction with above-curve discharge pressure",
        ),
        ScenarioPlan(
            "K-DEGRADE-01", "PUMP_DEGRADATION", "PUMP", 2, 5.0, 6.2, "medium", "PROCESS_FAULT",
            parameters={"flow_factor": 0.80, "head_factor": 0.72},
            expected_observable="Operating point below the nominal pump curve",
        ),
        ScenarioPlan(
            "K-SENSOR-BIAS-01", "SENSOR_FAULT", "TANK", 2, 6.5, 7.2, "medium", "SENSOR_FAULT",
            sensor_role="level", sensor_fault_type="bias",
            parameters={"bias_pct": 6.0},
            expected_observable="Level/pressure redundancy disagreement",
        ),
    ],
}

SEVERITY_ORDER = {"light": 0, "medium": 1, "severe": 2, "normal": -1}


def get_scenario_plans(scenario_set: str) -> List[ScenarioPlan]:
    if scenario_set not in SCENARIO_MATRIX:
        raise ValueError(
            f"Unknown scenario set {scenario_set!r}; choose from {sorted(SCENARIO_MATRIX)}"
        )
    return list(SCENARIO_MATRIX[scenario_set])


class ScenarioInjector:
    """Inject controlled anomalies into simulated telemetry."""

    def __init__(
        self,
        config: Config,
        master_data: Dict[str, pd.DataFrame],
        id_gen: IDGenerator,
    ):
        self.config = config
        self.master_data = master_data
        self.id_gen = id_gen
        self.last_plans: List[ScenarioPlan] = []
        self._sensor_lookup = {
            (row["equipment_id"], row["sensor_type"], row.get("sensor_role", "")): row["sensor_id"]
            for _, row in master_data["sensors"].iterrows()
        }

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def _equipment(self, kind: str, index: int) -> pd.Series:
        table = {
            "PUMP": "pumps",
            "TANK": "tanks",
            "VALVE": "valves",
        }[kind]
        frame = self.master_data[table].sort_values(
            {"PUMP": "pump_id", "TANK": "tank_id", "VALVE": "valve_id"}[kind]
        )
        if frame.empty:
            raise ValueError(f"No {kind} equipment available for scenario injection")
        return frame.iloc[index % len(frame)]

    def _sensor_id(self, equipment_id: str, sensor_type: str, role: str) -> str:
        key = (equipment_id, sensor_type, role)
        if key not in self._sensor_lookup:
            raise ValueError(f"Missing sensor {sensor_type}/{role} on {equipment_id}")
        return self._sensor_lookup[key]

    def _resolve(self, plan: ScenarioPlan) -> Dict[str, Any]:
        equipment = self._equipment(plan.equipment_kind, plan.equipment_index)
        equipment_id = str(equipment[plan.equipment_kind.lower() + "_id"])
        if plan.issue_type == "LEAK":
            target = self._sensor_id(equipment_id, "LEVEL", "level")
            # Pressure is redundancy evidence, not a separately labelled alarm
            # point; point-level labels use the primary observable per event.
            related = [target]
        elif plan.issue_type == "BLOCKAGE":
            target = self._sensor_id(equipment_id, "FLOW", "discharge")
            related = [target]
        elif plan.issue_type == "PUMP_DEGRADATION":
            target = self._sensor_id(equipment_id, "FLOW", "discharge")
            related = [target]
        elif plan.issue_type == "SENSOR_FAULT":
            if plan.sensor_fault_type == "missing":
                # Missing is injected by removing samples, not by a quality flag.
                target = self._sensor_id(equipment_id, "LEVEL", plan.sensor_role or "level")
            elif plan.sensor_role in {"inlet", "outlet"}:
                target = self._sensor_id(equipment_id, "FLOW", plan.sensor_role)
            else:
                target = self._sensor_id(
                    equipment_id,
                    "LEVEL" if plan.sensor_role == "level" else "PRESSURE",
                    plan.sensor_role or "level",
                )
            related = [target]
        else:
            raise ValueError(f"Unsupported issue type {plan.issue_type}")
        return {
            "equipment": equipment,
            "equipment_id": equipment_id,
            "target_sensor_id": target,
            "expected_sensor_ids": related,
        }

    # ------------------------------------------------------------------
    # Injection helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _pump_curve(pump: pd.Series, flow: float, shutoff_factor: float = 1.2) -> float:
        q_nom = float(pump["nominal_flow_m3_h"])
        h_nom = float(pump["nominal_head_m"])
        h_shutoff = h_nom * shutoff_factor
        k = (h_shutoff - h_nom) / (q_nom**2) if q_nom > 0 else 0.001
        return max(0.0, h_shutoff - k * float(flow) ** 2)

    def _apply_pump_effect(
        self,
        telemetry: pd.DataFrame,
        pump: pd.Series,
        start: datetime,
        end: datetime,
        plan: ScenarioPlan,
    ) -> None:
        pump_id = str(pump["pump_id"])
        flow_sensor = self._sensor_id(pump_id, "FLOW", "discharge")
        pressure_sensor = self._sensor_id(pump_id, "PRESSURE", "discharge")
        time_values = pd.to_datetime(telemetry["timestamp"])
        window = (time_values >= pd.Timestamp(start)) & (time_values < pd.Timestamp(end))

        flow_mask = window & (telemetry["sensor_id"] == flow_sensor)
        old_flow = telemetry.loc[flow_mask, "physical_state_value"].astype(float)
        flow_factor = float(plan.parameters["flow_factor"])
        new_flow = old_flow * flow_factor
        telemetry.loc[flow_mask, "physical_state_value"] = new_flow.to_numpy()
        telemetry.loc[flow_mask, "measured_value"] = (
            telemetry.loc[flow_mask, "measured_value"].astype(float).to_numpy()
            + (new_flow - old_flow).to_numpy()
        )

        flow_by_time = pd.Series(new_flow.to_numpy(), index=time_values[flow_mask])
        pressure_mask = window & (telemetry["sensor_id"] == pressure_sensor)
        pressure_times = time_values[pressure_mask]
        old_pressure = telemetry.loc[pressure_mask, "physical_state_value"].astype(float)
        curve = np.array(
            [
                self._pump_curve(pump, float(flow_by_time.get(ts, float(old_flow.iloc[0]))))
                for ts in pressure_times
            ]
        )
        if plan.issue_type == "BLOCKAGE":
            new_pressure = curve * float(plan.parameters.get("pressure_factor", 1.0))
        else:
            new_pressure = curve * float(plan.parameters.get("head_factor", 1.0))
        new_pressure = new_pressure * WATER_HEAD_TO_BAR
        telemetry.loc[pressure_mask, "physical_state_value"] = new_pressure
        # measured = physical + noise, so add the physical delta to measured.
        telemetry.loc[pressure_mask, "measured_value"] = (
            telemetry.loc[pressure_mask, "measured_value"].astype(float).to_numpy()
            + (new_pressure - old_pressure.to_numpy())
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def generate_scenarios(
        self, simulation_run_id: str, telemetry_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Apply the selected scenario set and return telemetry/scenarios/truth."""
        telemetry = telemetry_df.copy()
        start_time = datetime.fromisoformat(self.config.simulation.start_time)
        duration_hours = float(self.config.simulation.duration_hours)
        end_time_total = start_time + timedelta(hours=duration_hours)
        timestamps = pd.to_datetime(telemetry["timestamp"])

        scenario_rows: List[Dict[str, Any]] = []
        ground_truth_rows: List[Dict[str, Any]] = []
        anomaly_intervals: List[Tuple[datetime, datetime]] = []

        plans = get_scenario_plans(self.config.scenarios.scenario_set)
        enabled = {
            "LEAK": self.config.scenarios.enable_leaks,
            "BLOCKAGE": self.config.scenarios.enable_blockages,
            "PUMP_DEGRADATION": self.config.scenarios.enable_pump_degradation,
            "SENSOR_FAULT": self.config.scenarios.enable_sensor_faults,
        }
        plans = [plan for plan in plans if enabled.get(plan.issue_type, True)]
        self.last_plans = plans

        for plan in plans:
            resolved = self._resolve(plan)
            scenario_id = self.id_gen.scenario_id()
            start = start_time + timedelta(hours=plan.start_hour)
            end = min(start_time + timedelta(hours=plan.end_hour), end_time_total)
            if end <= start:
                continue
            anomaly_intervals.append((start, end))
            equipment_id = resolved["equipment_id"]
            target_sensor_id = resolved["target_sensor_id"]
            expected_sensor_ids = resolved["expected_sensor_ids"]
            params = dict(plan.parameters)
            params["severity"] = plan.severity

            scenario = {
                "scenario_id": scenario_id,
                "simulation_run_id": simulation_run_id,
                "issue_type": plan.issue_type,
                "severity": plan.severity,
                "affected_equipment_id": equipment_id,
                "affected_sensor_id": target_sensor_id if plan.issue_type == "SENSOR_FAULT" else None,
                "expected_sensor_ids": json.dumps(expected_sensor_ids),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "injection_parameters": json.dumps(params, sort_keys=True),
                "expected_observable": plan.expected_observable,
            }
            scenario_rows.append(scenario)

            gt = {
                "gt_id": f"GT-{len(ground_truth_rows) + 1:06d}",
                "simulation_run_id": simulation_run_id,
                "scenario_id": scenario_id,
                "issue_type": plan.issue_type,
                "severity": plan.severity,
                "affected_equipment_id": equipment_id,
                "affected_sensor_id": target_sensor_id if plan.issue_type == "SENSOR_FAULT" else None,
                "expected_sensor_ids": json.dumps(expected_sensor_ids),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "expected_detection": "YES",
                "expected_alarm_category": plan.expected_category,
                "injection_parameters": json.dumps(params, sort_keys=True),
            }
            ground_truth_rows.append(gt)

            mask = (timestamps >= pd.Timestamp(start)) & (timestamps < pd.Timestamp(end))
            if plan.issue_type == "LEAK":
                level_mask = mask & (telemetry["sensor_id"] == target_sensor_id)
                times = pd.to_datetime(telemetry.loc[level_mask, "timestamp"])
                elapsed_hours = (times - pd.Timestamp(start)).dt.total_seconds() / 3600.0
                capacity = float(resolved["equipment"]["capacity_m3"])
                rate = float(plan.parameters["leak_fraction_capacity_per_hour"]) * capacity
                drop_pct = (rate * elapsed_hours / capacity * 100.0).to_numpy()
                telemetry.loc[level_mask, "physical_state_value"] -= drop_pct
                telemetry.loc[level_mask, "measured_value"] -= drop_pct
                pressure_sensor = self._sensor_id(equipment_id, "PRESSURE", "pressure")
                pressure_mask = mask & (telemetry["sensor_id"] == pressure_sensor)
                pressure_times = pd.to_datetime(telemetry.loc[pressure_mask, "timestamp"])
                pressure_elapsed = (
                    (pressure_times - pd.Timestamp(start)).dt.total_seconds() / 3600.0
                ).to_numpy()
                pressure_drop = (
                    rate
                    * pressure_elapsed
                    / capacity
                    * float(resolved["equipment"]["height_m"])
                    * WATER_HEAD_TO_BAR
                )
                telemetry.loc[pressure_mask, "physical_state_value"] -= pressure_drop
                telemetry.loc[pressure_mask, "measured_value"] -= pressure_drop
            elif plan.issue_type in {"BLOCKAGE", "PUMP_DEGRADATION"}:
                self._apply_pump_effect(
                    telemetry, resolved["equipment"], start, end, plan
                )
            elif plan.issue_type == "SENSOR_FAULT":
                sensor_mask = mask & (telemetry["sensor_id"] == target_sensor_id)
                fault_type = plan.sensor_fault_type
                if fault_type == "bias":
                    bias = float(plan.parameters.get("bias_pct", 0.0))
                    telemetry.loc[sensor_mask, "measured_value"] += bias
                elif fault_type == "drift":
                    total = float(plan.parameters.get("drift_total_pct", 0.0))
                    times = pd.to_datetime(telemetry.loc[sensor_mask, "timestamp"])
                    fraction = (
                        (times - pd.Timestamp(start)).dt.total_seconds()
                        / max((end - start).total_seconds(), 1)
                    ).to_numpy()
                    telemetry.loc[sensor_mask, "measured_value"] += total * fraction
                elif fault_type == "stuck":
                    if sensor_mask.any():
                        held = float(
                            telemetry.loc[sensor_mask, "measured_value"].astype(float).iloc[0]
                        )
                        telemetry.loc[sensor_mask, "measured_value"] = held
                elif fault_type == "missing":
                    telemetry = telemetry.loc[~sensor_mask].copy()
                    timestamps = pd.to_datetime(telemetry["timestamp"])
                else:
                    raise ValueError(f"Unsupported sensor fault type {fault_type}")

        # Explicit normal windows covering the complement of anomaly windows.
        if self.config.scenarios.include_normal_windows:
            merged: List[Tuple[datetime, datetime]] = []
            for start, end in sorted(anomaly_intervals):
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            complements: List[Tuple[datetime, datetime]] = []
            cursor = start_time
            for start, end in merged:
                if start > cursor:
                    complements.append((cursor, start))
                cursor = max(cursor, end)
            if cursor < end_time_total:
                complements.append((cursor, end_time_total))

            split = timedelta(minutes=self.config.scenarios.normal_window_split_minutes)
            for comp_start, comp_end in complements:
                chunk_start = comp_start
                while chunk_start < comp_end:
                    chunk_end = min(chunk_start + split, comp_end)
                    if (chunk_end - chunk_start).total_seconds() >= 60:
                        scenario_id = self.id_gen.scenario_id()
                        scenario_rows.append(
                            {
                                "scenario_id": scenario_id,
                                "simulation_run_id": simulation_run_id,
                                "issue_type": "NORMAL",
                                "severity": "normal",
                                "affected_equipment_id": None,
                                "affected_sensor_id": None,
                                "expected_sensor_ids": json.dumps([]),
                                "start_time": chunk_start.isoformat(),
                                "end_time": chunk_end.isoformat(),
                                "injection_parameters": json.dumps(
                                    {"label": "normal_baseline", "coverage": "complement"}
                                ),
                                "expected_observable": "No injected anomaly; operating values within normal variation",
                            }
                        )
                        ground_truth_rows.append(
                            {
                                "gt_id": f"GT-{len(ground_truth_rows) + 1:06d}",
                                "simulation_run_id": simulation_run_id,
                                "scenario_id": scenario_id,
                                "issue_type": "NORMAL",
                                "severity": "normal",
                                "affected_equipment_id": None,
                                "affected_sensor_id": None,
                                "expected_sensor_ids": json.dumps([]),
                                "start_time": chunk_start.isoformat(),
                                "end_time": chunk_end.isoformat(),
                                "expected_detection": "NO",
                                "expected_alarm_category": "NORMAL",
                                "injection_parameters": json.dumps(
                                    {"label": "normal_baseline", "coverage": "complement"}
                                ),
                            }
                        )
                    chunk_start = chunk_end

        scenarios_df = pd.DataFrame(scenario_rows)
        ground_truth_df = pd.DataFrame(ground_truth_rows)
        return telemetry, scenarios_df, ground_truth_df
