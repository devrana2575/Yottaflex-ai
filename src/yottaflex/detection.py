"""Rule-based detection with persistence, hysteresis, grouping and history.

The detector consumes only observed measurement columns. Scenario IDs, physical
state values, and ground-truth fields are never read. An abnormal condition is
raised only after it persists for the configured number of readings/time; an
alarm episode remains open through short dropouts (grouping gap) and records a
CREATED/RESOLVED transition history.
"""

from __future__ import annotations

import json
import math
from collections import deque
from datetime import timedelta
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import Config
from .id_generator import IDGenerator
from .simulation import WATER_HEAD_TO_BAR

PROCESS_FAULT = "PROCESS_FAULT"
SENSOR_FAULT = "SENSOR_FAULT"
UNCERTAIN = "UNCERTAIN"


class _EpisodeTracker:
    """Accumulate per-rule condition flags into grouped alarm episodes."""

    def __init__(
        self,
        *,
        config: Config,
        id_gen: IDGenerator,
        simulation_run_id: str,
        rule_id: str,
        alarm_type: str,
        category: str,
        severity: str,
        equipment_id: str,
        sensor_id: str,
        evidence_base: str,
        persistence_seconds: int = 0,
        persistence_samples: int = 1,
        peak_mode: str = "absmax",
        suppress_modes: Iterable[str] = (),
        attribution: str = "OBSERVED",
        interval_seconds: int = 60,
    ):
        self.config = config
        self.id_gen = id_gen
        self.simulation_run_id = simulation_run_id
        self.rule_id = rule_id
        self.alarm_type = alarm_type
        self.category = category
        self.severity = severity
        self.equipment_id = equipment_id
        self.sensor_id = sensor_id
        self.evidence_base = evidence_base
        self.peak_mode = peak_mode
        self.suppress_modes = set(suppress_modes)
        self.attribution = attribution
        self.interval_seconds = interval_seconds
        self.required_samples = max(
            persistence_samples,
            int(math.ceil(persistence_seconds / max(interval_seconds, 1)))
            if persistence_seconds > 0
            else 1,
        )
        self.persistence_seconds = persistence_seconds
        self.clear_samples = max(config.detection.clear_samples, 1)
        self.grouping_gap = timedelta(seconds=config.detection.grouping_gap_seconds)

        self.episodes: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        self._open: Optional[Dict[str, Any]] = None
        self._candidate_start: Optional[pd.Timestamp] = None
        self._candidate_count = 0
        self._candidate_last: Optional[pd.Timestamp] = None
        self._candidate_peak: Any = None
        self._clear_count = 0

    # -- helpers -------------------------------------------------------
    def _better_peak(self, current: Any, candidate: Any) -> Any:
        if current is None:
            return candidate
        if candidate is None:
            return current
        if self.peak_mode == "min":
            return min(current, candidate)
        if self.peak_mode == "max":
            return max(current, candidate)
        return candidate if abs(candidate) > abs(current) else current

    def _open_episode(
        self, timestamp: pd.Timestamp, metric: Any, mode: str, category: Optional[str]
    ) -> None:
        alarm_id = self.id_gen.alarm_id()
        episode = {
            "alarm_id": alarm_id,
            "simulation_run_id": self.simulation_run_id,
            "equipment_id": self.equipment_id,
            "sensor_id": self.sensor_id,
            "alarm_type": self.alarm_type,
            "alarm_category": category or self.category,
            "severity": self.severity,
            "first_detected_at": timestamp.isoformat(),
            "last_detected_at": timestamp.isoformat(),
            "evidence_summary": "",
            "rule_id": self.rule_id,
            "alarm_status": "ACTIVE",
            "occurrence_count": 1,
            "peak_value": metric,
            "peak_at": timestamp.isoformat(),
            "attribution": self.attribution,
            "operating_mode": mode,
        }
        # Record the episode at activation so ACTIVE alarms are observable before
        # they resolve; closing mutates this same row to RESOLVED.
        self.episodes.append(episode)
        self._open = episode
        self.history.append(
            {
                "event_id": self.id_gen.event_id(),
                "alarm_id": alarm_id,
                "simulation_run_id": self.simulation_run_id,
                "event_type": "CREATED",
                "event_timestamp": timestamp.isoformat(),
                "event_data": json.dumps(
                    {
                        "rule_id": self.rule_id,
                        "category": episode["alarm_category"],
                        "severity": self.severity,
                        "mode": mode,
                    },
                    sort_keys=True,
                ),
            }
        )

    def _close_episode(self, resolution: pd.Timestamp) -> None:
        if self._open is None:
            return
        episode = self._open
        episode["alarm_status"] = "RESOLVED"
        episode["evidence_summary"] = self._evidence(episode)
        self.history.append(
            {
                "event_id": self.id_gen.event_id(),
                "alarm_id": episode["alarm_id"],
                "simulation_run_id": self.simulation_run_id,
                "event_type": "RESOLVED",
                "event_timestamp": resolution.isoformat(),
                "event_data": json.dumps(
                    {"last_detected_at": episode["last_detected_at"]}, sort_keys=True
                ),
            }
        )
        self._open = None
        self._clear_count = 0

    def _evidence(self, episode: Dict[str, Any]) -> str:
        peak = episode["peak_value"]
        if isinstance(peak, (int, float, np.floating, np.integer)):
            peak_text = f"{float(peak):.4g}"
        else:
            peak_text = str(peak)
        return (
            f"{self.evidence_base}; peak={peak_text} at {episode['peak_at']}; "
            f"{episode['occurrence_count']} active readings; "
            f"category={episode['alarm_category']}; attribution={self.attribution}"
        )

    # -- public feed ----------------------------------------------------
    def feed(
        self,
        timestamp: pd.Timestamp,
        active: bool,
        metric: Any = None,
        mode: str = "NORMAL",
        category: Optional[str] = None,
    ) -> None:
        effective = bool(active) and mode not in self.suppress_modes
        if self._open is None:
            if not effective:
                self._candidate_start = None
                self._candidate_count = 0
                self._candidate_last = None
                self._candidate_peak = None
                return
            if self._candidate_start is None:
                self._candidate_start = timestamp
                self._candidate_count = 0
                self._candidate_peak = metric
            self._candidate_count += 1
            self._candidate_last = timestamp
            self._candidate_peak = self._better_peak(self._candidate_peak, metric)
            span_ok = (
                (timestamp - self._candidate_start).total_seconds()
                >= self.persistence_seconds
            )
            if self._candidate_count >= self.required_samples and span_ok:
                self._open_episode(timestamp, metric, mode, category)
                self._candidate_start = None
                self._candidate_count = 0
                self._candidate_peak = None
            return

        # Episode already open.
        if effective:
            self._open["last_detected_at"] = timestamp.isoformat()
            self._open["occurrence_count"] = int(self._open["occurrence_count"]) + 1
            previous_peak = self._open["peak_value"]
            updated_peak = self._better_peak(previous_peak, metric)
            if updated_peak is not previous_peak:
                self._open["peak_value"] = updated_peak
                self._open["peak_at"] = timestamp.isoformat()
            self._clear_count = 0
            if category and self._open["alarm_category"] == self.category:
                # The category is fixed at activation; later evidence does not
                # rewrite history. This keeps alarm semantics stable.
                pass
            return

        self._clear_count += 1
        last_active = pd.Timestamp(self._open["last_detected_at"])
        gap_exceeded = (timestamp - last_active) > self.grouping_gap
        if self._clear_count >= self.clear_samples or gap_exceeded:
            self._close_episode(timestamp)

    def finish(self, timestamp: pd.Timestamp) -> None:
        if self._open is not None:
            self._open["evidence_summary"] = self._evidence(self._open)
            self._open = None
        self._candidate_start = None


class DetectionEngine:
    """Detect process and sensor anomalies from observed telemetry."""

    ALARM_COLUMNS: ClassVar[tuple[str, ...]] = (
        "alarm_id",
        "simulation_run_id",
        "equipment_id",
        "sensor_id",
        "alarm_type",
        "alarm_category",
        "severity",
        "first_detected_at",
        "last_detected_at",
        "evidence_summary",
        "rule_id",
        "alarm_status",
        "occurrence_count",
        "peak_value",
        "peak_at",
        "attribution",
        "operating_mode",
    )
    HISTORY_COLUMNS: ClassVar[tuple[str, ...]] = (
        "event_id",
        "alarm_id",
        "simulation_run_id",
        "event_type",
        "event_timestamp",
        "event_data",
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
        self.pumps = (
            master_data["pumps"].set_index("pump_id")
            if "pump_id" in master_data.get("pumps", pd.DataFrame()).columns
            else pd.DataFrame()
        )
        self.tanks = (
            master_data["tanks"].set_index("tank_id")
            if "tank_id" in master_data.get("tanks", pd.DataFrame()).columns
            else pd.DataFrame()
        )
        self.interval_seconds = int(config.simulation.sampling_interval_seconds)
        self.mode_map = (
            master_data["operating_modes"]
            .set_index("operating_mode_id")["mode_name"]
            .to_dict()
            if "operating_modes" in master_data
            else {}
        )
        self._trackers: List[_EpisodeTracker] = []
        self._frames: Dict[str, pd.DataFrame] = {}
        self._history: List[Dict[str, Any]] = []
        self.alarm_events: pd.DataFrame = pd.DataFrame(columns=self.HISTORY_COLUMNS)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _tracker(self, **kwargs) -> _EpisodeTracker:
        if kwargs.get("simulation_run_id") in {None, "__RUN__"}:
            kwargs["simulation_run_id"] = getattr(self, "_simulation_run_id", "__RUN__")
        tracker = _EpisodeTracker(
            config=self.config,
            id_gen=self.id_gen,
            interval_seconds=self.interval_seconds,
            **kwargs,
        )
        self._trackers.append(tracker)
        return tracker

    def _frame(self, sensor_id: str, observed: pd.DataFrame) -> pd.DataFrame:
        if sensor_id in self._frames:
            return self._frames[sensor_id]
        frame = observed[observed["sensor_id"] == sensor_id].copy()
        frame["ts"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame["value"] = pd.to_numeric(frame["measured_value"], errors="coerce")
        frame["mode"] = (
            frame["operating_mode_id"]
            .map(self.mode_map)
            .astype("object")
            .fillna("NORMAL")
            if "operating_mode_id" in frame
            else "NORMAL"
        )
        frame["quality"] = frame["quality_status"].fillna("MISSING")
        frame = frame.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        self._frames[sensor_id] = frame
        return frame

    def _sensor_ids(self, equipment_type: str, **filters) -> List[str]:
        frame = self.master_data["sensors"]
        mask = frame["equipment_type"] == equipment_type
        for key, value in filters.items():
            if key in frame.columns:
                mask &= frame[key] == value
        return frame.loc[mask, "sensor_id"].tolist()

    @staticmethod
    def _mode_at(frame: pd.DataFrame, index: int) -> str:
        if "mode" in frame and len(frame) > index:
            return str(frame["mode"].iloc[index])
        return "NORMAL"

    # ------------------------------------------------------------------
    # Sensor-level rules
    # ------------------------------------------------------------------
    def _sensor_quality_rules(self, observed: pd.DataFrame) -> None:
        suppress = self.config.detection.process_suppression_modes
        for sensor_id, sensor in self.sensors.iterrows():
            frame = self._frame(sensor_id, observed)
            if frame.empty:
                continue
            quality_tracker = self._tracker(
                simulation_run_id="__RUN__",
                rule_id="RULE-004",
                alarm_type="Sensor quality fault",
                category=SENSOR_FAULT,
                severity="MEDIUM",
                equipment_id=str(sensor["equipment_id"]),
                sensor_id=sensor_id,
                evidence_base="Observed quality status is not GOOD",
                persistence_samples=self.config.detection.quality_activation_samples,
                peak_mode="max",
                attribution="MEASUREMENT_METADATA",
            )
            implausible_tracker = self._tracker(
                simulation_run_id="__RUN__",
                rule_id="RULE-008",
                alarm_type="Implausible sensor reading",
                category=SENSOR_FAULT,
                severity="MEDIUM",
                equipment_id=str(sensor["equipment_id"]),
                sensor_id=sensor_id,
                evidence_base="Observed value outside the configured physical range",
                persistence_samples=1,
                peak_mode="absmax",
                attribution="RANGE_CHECK",
            )
            stuck_tracker = self._tracker(
                simulation_run_id="__RUN__",
                rule_id="RULE-003",
                alarm_type="Sensor stuck",
                category=SENSOR_FAULT,
                severity="MEDIUM",
                equipment_id=str(sensor["equipment_id"]),
                sensor_id=sensor_id,
                evidence_base=(
                    "Observed value unchanged for at least "
                    f"{self.config.detection.stuck_sensor_threshold_minutes:g} minutes"
                ),
                persistence_samples=1,
                peak_mode="absmax",
                attribution="TEMPORAL_CONSISTENCY",
            )

            previous_value = None
            previous_ts = None
            unchanged_since = None
            for row in frame.itertuples(index=False):
                ts = row.ts
                value = row.value
                quality = str(row.quality)
                missing = pd.isna(value) or quality in {"BAD", "UNCERTAIN", "MISSING"}
                quality_tracker.feed(
                    ts,
                    missing,
                    1.0 if missing else 0.0,
                    row.mode,
                )

                if pd.isna(value):
                    implausible = False
                elif sensor["sensor_type"] == "LEVEL":
                    implausible = not (
                        self.config.detection.implausible_level_min_pct
                        <= float(value)
                        <= self.config.detection.implausible_level_max_pct
                    )
                elif sensor["sensor_type"] == "FLOW":
                    implausible = not (
                        0.0
                        <= float(value)
                        <= self.config.detection.implausible_flow_max_m3_h
                    )
                elif sensor["sensor_type"] == "PRESSURE":
                    implausible = not (
                        0.0
                        <= float(value)
                        <= self.config.detection.implausible_pressure_max_bar
                    )
                else:
                    implausible = False
                implausible_tracker.feed(ts, implausible, value if not pd.isna(value) else 0.0, row.mode)

                stuck = False
                if not pd.isna(value) and quality == "GOOD":
                    if (
                        previous_value is not None
                        and abs(float(value) - float(previous_value))
                        <= self.config.detection.stuck_absolute_tolerance
                    ):
                        if unchanged_since is None:
                            unchanged_since = previous_ts
                        stuck_seconds = (ts - unchanged_since).total_seconds()
                        stuck = stuck_seconds >= (
                            self.config.detection.stuck_sensor_threshold_minutes * 60
                        )
                    else:
                        unchanged_since = None
                else:
                    unchanged_since = None
                stuck_tracker.feed(ts, stuck, value if not pd.isna(value) else 0.0, row.mode)
                previous_value = value
                previous_ts = ts

    # ------------------------------------------------------------------
    # Tank process rules
    # ------------------------------------------------------------------
    def _tank_rules(self, observed: pd.DataFrame) -> None:
        for tank_id, tank in self.tanks.iterrows():
            level_ids = self._sensor_ids("TANK", equipment_id=tank_id, sensor_type="LEVEL", sensor_role="level")
            pressure_ids = self._sensor_ids("TANK", equipment_id=tank_id, sensor_type="PRESSURE", sensor_role="pressure")
            inlet_ids = self._sensor_ids("TANK", equipment_id=tank_id, sensor_type="FLOW", sensor_role="inlet")
            outlet_ids = self._sensor_ids("TANK", equipment_id=tank_id, sensor_type="FLOW", sensor_role="outlet")
            if not level_ids:
                continue
            level_id = level_ids[0]
            level = self._frame(level_id, observed)
            if level.empty:
                continue

            # Level/pressure redundancy ----------------------------------
            pressure = self._frame(pressure_ids[0], observed) if pressure_ids else pd.DataFrame()
            consistency = pd.Series(dtype=bool)
            residual = pd.Series(dtype=float)
            if not pressure.empty:
                merged = level.set_index("ts")[["value", "mode"]].join(
                    pressure.set_index("ts")[["value"]].rename(columns={"value": "pressure"}),
                    how="inner",
                )
                expected_level = (
                    merged["pressure"].astype(float)
                    / (float(tank["height_m"]) * WATER_HEAD_TO_BAR)
                    * 100.0
                )
                residual = merged["value"].astype(float) - expected_level
                consistency = residual.abs() <= self.config.detection.level_pressure_tolerance_pct
                redundancy_tracker = self._tracker(
                    simulation_run_id="__RUN__",
                    rule_id="RULE-010",
                    alarm_type="Level/pressure redundancy disagreement",
                    category=SENSOR_FAULT,
                    severity="MEDIUM",
                    equipment_id=tank_id,
                    sensor_id=level_id,
                    evidence_base=(
                        "Measured level disagrees with the hydrostatic pressure estimate; "
                        "attribution between LEVEL and PRESSURE sensor is ambiguous"
                    ),
                    persistence_seconds=self.config.detection.level_pressure_persistence_seconds,
                    persistence_samples=3,
                    peak_mode="absmax",
                    attribution="REDUNDANCY_AMBIGUOUS",
                )
                for ts, value in residual.items():
                    row = merged.loc[ts]
                    redundancy_tracker.feed(ts, abs(float(value)) > self.config.detection.level_pressure_tolerance_pct, float(value), str(row["mode"]))

            # RULE-001 level bounds ---------------------------------------
            bounds_tracker = self._tracker(
                simulation_run_id="__RUN__",
                rule_id="RULE-001",
                alarm_type="Tank level out of bounds",
                category=PROCESS_FAULT,
                severity="HIGH",
                equipment_id=tank_id,
                sensor_id=level_id,
                evidence_base=(
                    f"Level outside [{self.config.detection.tank_level_low_pct:g}, "
                    f"{self.config.detection.tank_level_high_pct:g}] %"
                ),
                persistence_seconds=self.config.detection.persistence_seconds,
                persistence_samples=self.config.detection.persistence_samples,
                peak_mode="absmax",
                suppress_modes=self.config.detection.process_suppression_modes,
                attribution="OBSERVED_LEVEL",
            )
            # RULE-002 level decline --------------------------------------
            decline_tracker = self._tracker(
                simulation_run_id="__RUN__",
                rule_id="RULE-002",
                alarm_type="Rapid tank level decline",
                category=PROCESS_FAULT,
                severity="HIGH",
                equipment_id=tank_id,
                sensor_id=level_id,
                evidence_base=(
                    f"Level decline exceeds {self.config.detection.level_decline_threshold_pct:g} "
                    f"percentage points in {self.config.detection.level_decline_window_minutes:g} minutes"
                ),
                persistence_seconds=self.config.detection.persistence_seconds,
                persistence_samples=self.config.detection.persistence_samples,
                peak_mode="min",
                suppress_modes=self.config.detection.process_suppression_modes,
                attribution="OBSERVED_LEVEL",
            )

            bounds_state = False
            decline_state = False
            history: deque[Tuple[pd.Timestamp, float]] = deque()
            for row in level.itertuples(index=False):
                ts = row.ts
                value = float(row.value) if not pd.isna(row.value) else None
                trusted = bool(consistency.get(ts, True)) if len(consistency) else True
                if value is None or not trusted:
                    history.clear()
                    decline_state = False
                    decline_tracker.feed(ts, False, 0.0, row.mode)
                    bounds_state = False
                    bounds_tracker.feed(ts, False, value or 0.0, row.mode)
                    continue

                low = self.config.detection.tank_level_low_pct
                high = self.config.detection.tank_level_high_pct
                hysteresis = self.config.detection.level_bound_hysteresis_pct
                if not bounds_state and (value < low or value > high):
                    bounds_state = True
                elif bounds_state and (low + hysteresis <= value <= high - hysteresis):
                    bounds_state = False
                bounds_tracker.feed(ts, bounds_state, value, row.mode)

                history.append((ts, value))
                window = timedelta(minutes=self.config.detection.level_decline_window_minutes)
                while history and history[0][0] < ts - window:
                    history.popleft()
                if (
                    len(history) >= 2
                    and (ts - history[0][0]).total_seconds()
                    >= 0.8 * window.total_seconds()
                ):
                    decline = value - history[0][1]
                    if (
                        not decline_state
                        and decline <= -self.config.detection.level_decline_threshold_pct
                    ):
                        decline_state = True
                    elif (
                        decline_state
                        and decline >= -self.config.detection.level_decline_recovery_pct
                    ):
                        decline_state = False
                    decline_tracker.feed(ts, decline_state, decline, row.mode)
                else:
                    decline_tracker.feed(ts, False, 0.0, row.mode)

            # RULE-006 flow balance ---------------------------------------
            if pressure_ids and inlet_ids and outlet_ids:
                inlet = self._frame(inlet_ids[0], observed)
                outlet = self._frame(outlet_ids[0], observed)
                if not inlet.empty and not outlet.empty:
                    self._balance_rule(
                        tank_id=tank_id,
                        level=level,
                        pressure=pressure,
                        inlet=inlet,
                        outlet=outlet,
                        level_id=level_id,
                    )

    def _balance_rule(
        self,
        *,
        tank_id: str,
        level: pd.DataFrame,
        pressure: pd.DataFrame,
        inlet: pd.DataFrame,
        outlet: pd.DataFrame,
        level_id: str,
    ) -> None:
        merged = (
            level.set_index("ts")[["value", "mode"]]
            .rename(columns={"value": "level"})
            .join(
                pressure.set_index("ts")[["value"]].rename(columns={"value": "pressure"}),
                how="inner",
            )
            .join(
                inlet.set_index("ts")[["value"]].rename(columns={"value": "inlet"}),
                how="inner",
            )
            .join(
                outlet.set_index("ts")[["value"]].rename(columns={"value": "outlet"}),
                how="inner",
            )
        )
        if len(merged) < 3:
            return
        merged = merged.sort_index()
        expected_level = (
            merged["pressure"].astype(float)
            / (float(self.tanks.loc[tank_id, "height_m"]) * WATER_HEAD_TO_BAR)
            * 100.0
        )
        trusted = (
            (merged["level"].astype(float) - expected_level).abs()
            <= self.config.detection.level_pressure_tolerance_pct
        )

        process_tracker = self._tracker(
            simulation_run_id="__RUN__",
            rule_id="RULE-006",
            alarm_type="Tank flow-balance loss (possible leak)",
            category=PROCESS_FAULT,
            severity="HIGH",
            equipment_id=tank_id,
            sensor_id=level_id,
            evidence_base=(
                "Flow balance residual R=Q_in-Q_out-dV/dt exceeds uncertainty and is "
                "corroborated by a level decline; residual alone is not proof of a leak"
            ),
            persistence_seconds=self.config.detection.balance_persistence_seconds,
            persistence_samples=5,
            peak_mode="max",
            suppress_modes=self.config.detection.process_suppression_modes,
            attribution="MASS_BALANCE_WITH_LEVEL_CORROBORATION",
        )
        uncertain_tracker = self._tracker(
            simulation_run_id="__RUN__",
            rule_id="RULE-006U",
            alarm_type="Tank flow-balance inconsistency (source uncertain)",
            category=UNCERTAIN,
            severity="MEDIUM",
            equipment_id=tank_id,
            sensor_id=level_id,
            evidence_base=(
                "Flow balance residual exceeds uncertainty without a corroborating level "
                "decline; cannot distinguish an unmeasured leak from a flow-sensor bias"
            ),
            persistence_seconds=self.config.detection.balance_persistence_seconds,
            persistence_samples=5,
            peak_mode="max",
            suppress_modes=self.config.detection.process_suppression_modes,
            attribution="INSUFFICIENT_EVIDENCE",
        )

        window_seconds = self.config.detection.balance_window_minutes * 60.0
        five_minutes = self.config.detection.level_decline_window_minutes * 60.0
        rows = list(
            zip(
                merged.index,
                merged["level"].astype(float).to_numpy(),
                merged["inlet"].astype(float).to_numpy(),
                merged["outlet"].astype(float).to_numpy(),
                trusted.to_numpy(),
                merged["mode"].astype(str).to_numpy(),
            )
        )
        window: deque[Tuple[pd.Timestamp, float, float, float, bool, str]] = deque()
        for ts, level_value, q_in, q_out, is_trusted, mode in rows:
            window.append((ts, level_value, q_in, q_out, is_trusted, mode))
            while window and window[0][0] < ts - timedelta(seconds=window_seconds):
                window.popleft()
            span = (ts - window[0][0]).total_seconds() if window else 0.0
            if not is_trusted or len(window) < 3 or span < 0.75 * window_seconds:
                process_tracker.feed(ts, False, 0.0, mode)
                uncertain_tracker.feed(ts, False, 0.0, mode)
                continue
            times = np.array(
                [(item[0] - window[0][0]).total_seconds() for item in window], dtype=float
            )
            levels = np.array([item[1] for item in window], dtype=float)
            slope_pct_per_second = float(np.polyfit(times, levels, 1)[0])
            dV_dt = (
                slope_pct_per_second
                * 3600.0
                / 100.0
                * float(self.tanks.loc[tank_id, "capacity_m3"])
            )
            net_flow = float(np.mean([item[2] - item[3] for item in window]))
            residual = net_flow - dV_dt
            mean_flow = float(np.mean([abs(item[2]) + abs(item[3]) for item in window]))
            threshold = max(
                self.config.detection.balance_absolute_tolerance_m3_h,
                self.config.detection.balance_relative_tolerance_pct / 100.0 * mean_flow,
            )
            recent = [item for item in window if (ts - item[0]).total_seconds() <= five_minutes]
            decline = (
                recent[-1][1] - recent[0][1]
                if len(recent) >= 2
                and (recent[-1][0] - recent[0][0]).total_seconds()
                >= 0.8 * five_minutes
                else 0.0
            )
            decline_corroborated = decline <= -self.config.detection.level_decline_recovery_pct
            active = residual > threshold
            process_tracker.feed(ts, active and decline_corroborated, residual, mode)
            uncertain_tracker.feed(ts, active and not decline_corroborated, residual, mode)

    # ------------------------------------------------------------------
    # Pump rules
    # ------------------------------------------------------------------
    def _pump_rules(self, observed: pd.DataFrame) -> None:
        for pump_id, pump in self.pumps.iterrows():
            flow_ids = self._sensor_ids("PUMP", equipment_id=pump_id, sensor_type="FLOW", sensor_role="discharge")
            pressure_ids = self._sensor_ids("PUMP", equipment_id=pump_id, sensor_type="PRESSURE", sensor_role="discharge")
            if not flow_ids:
                continue
            flow = self._frame(flow_ids[0], observed)
            if flow.empty:
                continue
            nominal = float(pump["nominal_flow_m3_h"])

            low_tracker = self._tracker(
                simulation_run_id="__RUN__",
                rule_id="RULE-005",
                alarm_type="Pump low-flow deviation",
                category=PROCESS_FAULT,
                severity="HIGH",
                equipment_id=pump_id,
                sensor_id=flow_ids[0],
                evidence_base=(
                    f"Five-minute mean flow below {self.config.detection.pump_low_flow_ratio:.0%} "
                    f"of nominal {nominal:.2f} m3/h"
                ),
                persistence_seconds=self.config.detection.pump_flow_persistence_seconds,
                persistence_samples=3,
                peak_mode="min",
                suppress_modes=self.config.detection.process_suppression_modes,
                attribution="OBSERVED_FLOW",
            )
            window_seconds = self.config.detection.pump_flow_window_minutes * 60.0
            window: deque[Tuple[pd.Timestamp, float]] = deque()
            low_state = False
            for row in flow.itertuples(index=False):
                ts = row.ts
                value = row.value
                if pd.isna(value) or str(row.quality) != "GOOD":
                    window.clear()
                    low_state = False
                    low_tracker.feed(ts, False, 0.0, row.mode)
                    continue
                window.append((ts, float(value)))
                while window and window[0][0] < ts - timedelta(seconds=window_seconds):
                    window.popleft()
                span = (ts - window[0][0]).total_seconds() if window else 0.0
                if len(window) >= 2 and span >= 0.6 * window_seconds:
                    mean_flow = float(np.mean([item[1] for item in window]))
                    if not low_state and mean_flow < nominal * self.config.detection.pump_low_flow_ratio:
                        low_state = True
                    elif low_state and mean_flow > nominal * self.config.detection.pump_recovery_flow_ratio:
                        low_state = False
                    low_tracker.feed(ts, low_state, mean_flow, row.mode)
                else:
                    low_state = False
                    low_tracker.feed(ts, False, 0.0, row.mode)

            # RULE-007 pump curve residual
            if pressure_ids:
                pressure = self._frame(pressure_ids[0], observed)
                if not pressure.empty:
                    merged = flow.set_index("ts")[["value", "mode"]].rename(columns={"value": "flow"}).join(
                        pressure.set_index("ts")[["value"]].rename(columns={"value": "pressure"}),
                        how="inner",
                    )
                    curve_tracker = self._tracker(
                        simulation_run_id="__RUN__",
                        rule_id="RULE-007",
                        alarm_type="Pump operating point off nominal curve",
                        category=PROCESS_FAULT,
                        severity="HIGH",
                        equipment_id=pump_id,
                        sensor_id=flow_ids[0],
                        evidence_base=(
                            "Observed head-flow point deviates from the nominal pump curve; "
                            "positive residual suggests blockage, negative suggests degradation"
                        ),
                        persistence_seconds=self.config.detection.pump_curve_persistence_seconds,
                        persistence_samples=3,
                        peak_mode="absmax",
                        suppress_modes=self.config.detection.process_suppression_modes,
                        attribution="CURVE_RESIDUAL",
                    )
                    curve_state = False
                    for ts, row in merged.iterrows():
                        q = float(row["flow"])
                        p = float(row["pressure"])
                        if pd.isna(q) or pd.isna(p):
                            curve_state = False
                            curve_tracker.feed(ts, False, 0.0, str(row["mode"]))
                            continue
                        q_nom = float(pump["nominal_flow_m3_h"])
                        h_nom = float(pump["nominal_head_m"])
                        h_shutoff = h_nom * self.config.simulation.pump_curve_shutoff_factor
                        k = (h_shutoff - h_nom) / (q_nom**2) if q_nom > 0 else 0.001
                        expected_head = max(0.0, h_shutoff - k * q**2)
                        observed_head = p / WATER_HEAD_TO_BAR
                        residual_pct = (
                            (observed_head - expected_head) / expected_head * 100.0
                            if expected_head > 0
                            else 0.0
                        )
                        gate = q < q_nom * self.config.detection.pump_curve_flow_gate_ratio
                        if not curve_state and gate and abs(residual_pct) > self.config.detection.pump_curve_tolerance_pct:
                            curve_state = True
                        elif curve_state and (
                            not gate
                            or abs(residual_pct) < self.config.detection.pump_curve_recovery_pct
                        ):
                            curve_state = False
                        curve_tracker.feed(ts, curve_state, residual_pct, str(row["mode"]))

    # ------------------------------------------------------------------
    # Missing telemetry
    # ------------------------------------------------------------------
    def _gap_rules(self, observed: pd.DataFrame) -> None:
        if observed.empty:
            return
        global_start = pd.to_datetime(observed["timestamp"]).min()
        global_end = pd.to_datetime(observed["timestamp"]).max()
        expected = pd.date_range(
            start=global_start,
            end=global_end,
            freq=f"{self.interval_seconds}s",
        )
        for sensor_id, sensor in self.sensors.iterrows():
            frame = self._frame(sensor_id, observed)
            observed_set = set(frame["ts"]) if not frame.empty else set()
            missing = [timestamp for timestamp in expected if timestamp not in observed_set]
            if not missing:
                continue
            runs: List[List[pd.Timestamp]] = []
            current: List[pd.Timestamp] = []
            previous = None
            for timestamp in missing:
                if previous is not None and (timestamp - previous).total_seconds() > self.interval_seconds * 1.5:
                    runs.append(current)
                    current = []
                current.append(timestamp)
                previous = timestamp
            if current:
                runs.append(current)
            for run in runs:
                first = run[0]
                last = run[-1]
                detection_time = min(first + pd.Timedelta(seconds=self.interval_seconds), global_end)
                resolution_time = min(last + pd.Timedelta(seconds=self.interval_seconds), global_end)
                if detection_time > global_end:
                    continue
                alarm_id = self.id_gen.alarm_id()
                resolved = resolution_time < global_end
                row = {
                    "alarm_id": alarm_id,
                    "simulation_run_id": self._simulation_run_id,
                    "equipment_id": str(sensor["equipment_id"]),
                    "sensor_id": sensor_id,
                    "alarm_type": "Missing sensor telemetry",
                    "alarm_category": SENSOR_FAULT,
                    "severity": "MEDIUM",
                    "first_detected_at": detection_time.isoformat(),
                    "last_detected_at": resolution_time.isoformat(),
                    "evidence_summary": (
                        f"Expected {self.interval_seconds}s cadence; {len(run)} consecutive "
                        "expected readings are absent; category=SENSOR_FAULT; "
                        "attribution=DATA_AVAILABILITY"
                    ),
                    "rule_id": "RULE-009",
                    "alarm_status": "RESOLVED" if resolved else "ACTIVE",
                    "occurrence_count": len(run),
                    "peak_value": len(run),
                    "peak_at": first.isoformat(),
                    "attribution": "DATA_AVAILABILITY",
                    "operating_mode": "NORMAL",
                }
                self._manual_rows.append(row)
                self._history.append(
                    {
                        "event_id": self.id_gen.event_id(),
                        "alarm_id": alarm_id,
                        "simulation_run_id": self._simulation_run_id,
                        "event_type": "CREATED",
                        "event_timestamp": detection_time.isoformat(),
                        "event_data": json.dumps(
                            {"rule_id": "RULE-009", "missing_count": len(run)}, sort_keys=True
                        ),
                    }
                )
                if resolved:
                    self._history.append(
                        {
                            "event_id": self.id_gen.event_id(),
                            "alarm_id": alarm_id,
                            "simulation_run_id": self._simulation_run_id,
                            "event_type": "RESOLVED",
                            "event_timestamp": resolution_time.isoformat(),
                            "event_data": json.dumps({"missing_count": len(run)}, sort_keys=True),
                        }
                    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, simulation_run_id: str, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies from observed telemetry only."""
        allowed = {
            "sensor_id",
            "timestamp",
            "measured_value",
            "quality_status",
            "operating_mode_id",
        }
        required = allowed - {"operating_mode_id"}
        missing = required - set(telemetry_df.columns)
        if missing:
            raise ValueError(f"Telemetry is missing required observed columns: {sorted(missing)}")
        # Explicitly select observed fields: scenario/truth columns are ignored
        # even if a caller accidentally supplies them.
        present = [column for column in sorted(allowed) if column in telemetry_df.columns]
        observed = telemetry_df.loc[:, present].copy()
        observed["timestamp"] = pd.to_datetime(observed["timestamp"], errors="coerce")
        observed = observed.dropna(subset=["timestamp"]).sort_values(
            ["timestamp", "sensor_id"]
        ).reset_index(drop=True)

        self._simulation_run_id = simulation_run_id
        self._manual_rows: List[Dict[str, Any]] = []
        self._history = []
        self._frames = {}
        self._trackers = []

        self._sensor_quality_rules(observed)
        self._tank_rules(observed)
        self._pump_rules(observed)
        self._gap_rules(observed)

        final_ts = observed["timestamp"].max() if not observed.empty else pd.Timestamp.now()
        for tracker in self._trackers:
            tracker.finish(final_ts)

        rows: List[Dict[str, Any]] = []
        for tracker in self._trackers:
            rows.extend(tracker.episodes)
            self._history.extend(tracker.history)
        rows.extend(self._manual_rows)

        alarms = pd.DataFrame(rows, columns=self.ALARM_COLUMNS)
        if not alarms.empty:
            alarms["_sort_time"] = pd.to_datetime(alarms["first_detected_at"])
            alarms = alarms.sort_values(
                ["_sort_time", "rule_id", "equipment_id", "sensor_id"], kind="stable"
            ).drop(columns=["_sort_time"]).reset_index(drop=True)
            alarms["first_detected_at"] = pd.to_datetime(
                alarms["first_detected_at"]
            ).dt.strftime("%Y-%m-%dT%H:%M:%S")
            alarms["last_detected_at"] = pd.to_datetime(
                alarms["last_detected_at"]
            ).dt.strftime("%Y-%m-%dT%H:%M:%S")
            alarms["peak_at"] = pd.to_datetime(alarms["peak_at"]).dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )

        history = pd.DataFrame(self._history, columns=self.HISTORY_COLUMNS)
        if not history.empty:
            history["_sort_time"] = pd.to_datetime(history["event_timestamp"])
            history = history.sort_values(
                ["_sort_time", "alarm_id", "event_type"], kind="stable"
            ).drop(columns=["_sort_time"]).reset_index(drop=True)
            history["event_timestamp"] = pd.to_datetime(
                history["event_timestamp"]
            ).dt.strftime("%Y-%m-%dT%H:%M:%S")
        self.alarm_events = history
        return alarms
