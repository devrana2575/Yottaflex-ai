"""Anomaly detection engine."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

import pandas as pd

from .config import Config
from .id_generator import IDGenerator


class DetectionEngine:
    """Detect process and sensor anomalies from observed telemetry."""

    ALARM_COLUMNS: ClassVar[tuple[str, ...]] = (
        "alarm_id",
        "simulation_run_id",
        "equipment_id",
        "sensor_id",
        "alarm_type",
        "severity",
        "first_detected_at",
        "last_detected_at",
        "evidence_summary",
        "rule_id",
        "alarm_status",
    )

    def __init__(
        self,
        config: Config,
        master_data: dict[str, pd.DataFrame],
        id_gen: IDGenerator,
    ):
        self.config = config
        self.master_data = master_data
        self.id_gen = id_gen
        self.sensors = master_data["sensors"].set_index("sensor_id")
        self.pumps = master_data["pumps"].set_index("pump_id")

    def detect(self, simulation_run_id: str, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies without consuming scenario labels or simulated truth."""
        observed = telemetry_df.drop(
            columns=["scenario_id", "physical_state_value"], errors="ignore"
        )
        alarms = []

        for sensor_id, readings in observed.groupby("sensor_id", sort=False):
            if sensor_id not in self.sensors.index:
                continue
            sensor = self.sensors.loc[sensor_id]
            readings = readings.sort_values("timestamp")
            history = []
            previous_value = None
            unchanged_since = None
            rolling_flows = []

            for row in readings.itertuples(index=False):
                timestamp = pd.Timestamp(row.timestamp).to_pydatetime()
                value = float(row.measured_value)
                sensor_type = sensor["sensor_type"]
                equipment_type = sensor["equipment_type"]
                equipment_id = sensor["equipment_id"]

                alarm = None
                if row.quality_status in {"UNCERTAIN", "BAD", "MISSING"}:
                    alarm = (
                        "Sensor quality fault",
                        "MEDIUM",
                        "RULE-004",
                        f"Observed quality status {row.quality_status}",
                    )
                elif sensor_type == "FLOW" and (value < 0 or value > 500):
                    alarm = (
                        "Implausible sensor reading",
                        "MEDIUM",
                        "RULE-004",
                        f"Observed flow reading {value:g} m3/h is outside [0, 500]",
                    )

                if alarm is None:
                    if previous_value is not None and value == previous_value:
                        if unchanged_since is None:
                            unchanged_since = timestamp - timedelta(
                                seconds=self.config.simulation.sampling_interval_seconds
                            )
                        stuck_seconds = (
                            timestamp - unchanged_since
                        ).total_seconds()
                        if stuck_seconds >= (
                            self.config.simulation.stuck_sensor_threshold_minutes * 60
                        ):
                            alarm = (
                                "Sensor stuck",
                                "MEDIUM",
                                "RULE-003",
                                f"Observed unchanged value {value:g} for {stuck_seconds:g} seconds",
                            )
                    else:
                        unchanged_since = None

                if alarm is None and sensor_type == "LEVEL" and value > 90 or (
                    alarm is None and sensor_type == "LEVEL" and value < 10
                ):
                    alarm = (
                        "Tank level out of bounds",
                        "HIGH",
                        "RULE-001",
                        f"Observed tank level {value:g}% outside [10, 90]",
                    )

                if sensor_type == "LEVEL":
                    history.append((timestamp, value))
                    cutoff = timestamp - timedelta(minutes=5)
                    while history and history[0][0] < cutoff:
                        history.pop(0)
                    if (
                        alarm is None
                        and len(history) >= 2
                        and (timestamp - history[0][0]).total_seconds() >= 240
                        and value - history[0][1] <= -0.75
                    ):
                        alarm = (
                            "Rapid tank level decline",
                            "MEDIUM",
                            "RULE-002",
                            f"Observed level fell {history[0][1] - value:.3f}% in five minutes",
                        )

                if (
                    alarm is None
                    and sensor_type == "FLOW"
                    and equipment_type == "PUMP"
                    and equipment_id in self.pumps.index
                ):
                    nominal_flow = float(
                        self.pumps.loc[equipment_id, "nominal_flow_m3_h"]
                    )
                    rolling_flows.append((timestamp, value))
                    cutoff = timestamp - timedelta(minutes=5)
                    while rolling_flows and rolling_flows[0][0] < cutoff:
                        rolling_flows.pop(0)
                    if (
                        len(rolling_flows) >= 2
                        and (timestamp - rolling_flows[0][0]).total_seconds() >= 240
                        and sum(v for _, v in rolling_flows) / len(rolling_flows)
                        < nominal_flow * 0.8
                    ):
                        mean_flow = sum(v for _, v in rolling_flows) / len(rolling_flows)
                        alarm = (
                            "Pump operating deviation",
                            "HIGH",
                            "RULE-005",
                            (
                                f"Observed five-minute mean flow {mean_flow:.3f} m3/h "
                                f"is below 80% of nominal {nominal_flow:.3f} m3/h"
                            ),
                        )

                if alarm is not None:
                    alarm_type, severity, rule_id, evidence = alarm
                    alarms.append(
                        {
                            "alarm_id": self.id_gen.alarm_id(),
                            "simulation_run_id": simulation_run_id,
                            "equipment_id": equipment_id,
                            "sensor_id": sensor_id,
                            "alarm_type": alarm_type,
                            "severity": severity,
                            "first_detected_at": row.timestamp,
                            "last_detected_at": row.timestamp,
                            "evidence_summary": evidence,
                            "rule_id": rule_id,
                            "alarm_status": "ACTIVE",
                        }
                    )

                previous_value = value

        return pd.DataFrame(alarms, columns=self.ALARM_COLUMNS)
