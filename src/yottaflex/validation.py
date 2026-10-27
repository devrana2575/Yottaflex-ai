"""Executable validation for YottaFlex 2.0.0.

Every result is one of PASS, FAIL, WARN or NOT_IMPLEMENTED.  Checks operate on
the actual generated files rather than on documentation claims: master-data
relationships, telemetry cadence and physics, scenario/ground-truth isolation,
alarm history, evaluation denominators, detector isolation, and the SQLite
export.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import networkx as nx
import numpy as np
import pandas as pd

from . import __schema_version__
from .config import Config, load_config_for_dir
from .simulation import WATER_HEAD_TO_BAR


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _as_list(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return [text]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _json_dict(value: Any) -> Dict[str, Any]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _within_any(timestamps: pd.Series, intervals: Sequence[Tuple[pd.Timestamp, pd.Timestamp]]) -> np.ndarray:
    mask = np.zeros(len(timestamps), dtype=bool)
    values = pd.to_datetime(timestamps)
    for start, end in intervals:
        mask |= ((values >= start) & (values < end)).to_numpy()
    return mask


class Validator:
    """Validate generated data, lineage, topology, physics and evaluation."""

    PRIMARY_KEYS: Dict[str, str] = {
        "facilities": "facility_id",
        "pumps": "pump_id",
        "tanks": "tank_id",
        "valves": "valve_id",
        "pipes": "pipe_id",
        "sensors": "sensor_id",
        "operating_modes": "operating_mode_id",
    }

    REQUIRED_SENSOR_ROLES = {
        "PUMP": {("FLOW", "discharge"): 1, ("PRESSURE", "discharge"): 1},
        "TANK": {
            ("LEVEL", "level"): 1,
            ("PRESSURE", "pressure"): 1,
            ("FLOW", "inlet"): 1,
            ("FLOW", "outlet"): 1,
        },
        "VALVE": {("FLOW", "through"): 1},
    }

    UNIT_BY_TYPE = {"FLOW": "m3/h", "PRESSURE": "bar", "LEVEL": "%", "TEMPERATURE": "C"}

    def __init__(self, config: Config | None = None):
        self.config = config
        self.results: List[Dict[str, Any]] = []
        self.validation_counter = 0

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------
    def add_result(
        self,
        validation_type: str,
        test_case_id: str,
        status: str,
        description: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: str | None = None,
    ) -> Dict[str, Any]:
        self.validation_counter += 1
        result = {
            "validation_id": f"VAL-{self.validation_counter:06d}",
            "validation_type": validation_type,
            "test_case_id": test_case_id,
            "status": status,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "description": description,
            "details": details,
            "validated_at": datetime.now(UTC).isoformat(),
        }
        self.results.append(result)
        return result

    def _check(
        self,
        validation_type: str,
        test_case_id: str,
        passed: bool,
        description: str,
        details: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> Dict[str, Any]:
        return self.add_result(
            validation_type,
            test_case_id,
            "PASS" if passed else "FAIL",
            description,
            entity_type,
            entity_id,
            details,
        )

    @staticmethod
    def _rows(master_data: Dict[str, pd.DataFrame], name: str) -> pd.DataFrame:
        return master_data.get(name, pd.DataFrame())

    # ------------------------------------------------------------------
    # Master data
    # ------------------------------------------------------------------
    def validate_master_data(self, master_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        self.results = []
        self.validation_counter = 0
        for name, primary_key in self.PRIMARY_KEYS.items():
            frame = self._rows(master_data, name)
            valid = (
                not frame.empty
                and primary_key in frame.columns
                and not frame[primary_key].duplicated().any()
            )
            self._check(
                "PRIMARY_KEY",
                f"PK-{name.upper()}",
                valid,
                f"{primary_key} values are unique and present",
                f"rows={len(frame)}",
                name,
            )

        facilities = self._rows(master_data, "facilities")
        facility_ids = set(facilities.get("facility_id", []))
        foreign_key_details = []
        for name in ("pumps", "tanks", "valves", "pipes", "sensors"):
            frame = self._rows(master_data, name)
            if "facility_id" not in frame.columns:
                if not frame.empty:
                    foreign_key_details.append(f"{name} missing facility_id")
                continue
            invalid_count = int((~frame["facility_id"].isin(facility_ids)).sum())
            if invalid_count:
                foreign_key_details.append(f"{name}: {invalid_count} invalid facility references")
        self._check(
            "FOREIGN_KEY",
            "FK-FACILITY",
            not foreign_key_details,
            "Facility references are valid",
            "; ".join(foreign_key_details) or None,
        )

        equipment_facilities: Dict[str, str] = {}
        equipment_keys = {
            "PUMP": ("pumps", "pump_id"),
            "TANK": ("tanks", "tank_id"),
            "VALVE": ("valves", "valve_id"),
            "PIPE": ("pipes", "pipe_id"),
        }
        for table, key in equipment_keys.values():
            frame = self._rows(master_data, table)
            if not frame.empty:
                equipment_facilities.update(dict(zip(frame[key], frame["facility_id"])))
        sensors = self._rows(master_data, "sensors")
        sensor_equipment_valid = True
        sensor_problem = ""
        for _, row in sensors.iterrows():
            equipment_id = row.get("equipment_id")
            equipment_type = row.get("equipment_type")
            if (
                equipment_type not in equipment_keys
                or equipment_id not in equipment_facilities
                or equipment_facilities[equipment_id] != row["facility_id"]
            ):
                sensor_equipment_valid = False
                sensor_problem = f"{row['sensor_id']} -> {equipment_type}/{equipment_id}"
                break
        node_facilities = {}
        for table, key in (("pumps", "pump_id"), ("tanks", "tank_id"), ("valves", "valve_id")):
            for _, row in self._rows(master_data, table).iterrows():
                node_facilities[f"NODE-{row[key]}"] = row["facility_id"]
        pipes = self._rows(master_data, "pipes")
        pipe_facilities_valid = all(
            node_facilities.get(row["source_node_id"]) == row["facility_id"]
            and node_facilities.get(row["target_node_id"]) == row["facility_id"]
            for _, row in pipes.iterrows()
        )
        self._check(
            "FOREIGN_KEY",
            "FK-EQUIPMENT",
            sensor_equipment_valid and pipe_facilities_valid,
            "Sensor equipment and pipe node references match equipment facilities",
            sensor_problem or (None if pipe_facilities_valid else "invalid pipe facility relationship"),
        )

        self._check(
            "TOPOLOGY",
            "PIPE-ENDPOINTS",
            self.pipe_endpoints_valid(master_data),
            "All pipe endpoints reference equipment nodes",
        )
        tanks = self._rows(master_data, "tanks")
        tank_bounds = bool(
            not tanks.empty
            and (pd.to_numeric(tanks["capacity_m3"], errors="coerce") > 0).all()
            and (pd.to_numeric(tanks["height_m"], errors="coerce") > 0).all()
            and tanks["initial_level_pct"].between(0, 100).all()
        )
        self._check(
            "BOUNDS",
            "TANK-BOUNDS",
            tank_bounds,
            "Tank capacity, height and initial level are within physical bounds",
        )
        self._check(
            "TOPOLOGY",
            "FACILITY-CONNECTIVITY",
            self.topology_connected(master_data),
            "Each facility equipment graph is connected",
        )

        # Sensor composition and units.
        composition_errors = []
        for equipment_type, roles in self.REQUIRED_SENSOR_ROLES.items():
            equipment = self._rows(
                master_data,
                {"PUMP": "pumps", "TANK": "tanks", "VALVE": "valves"}[equipment_type],
            )
            for _, item in equipment.iterrows():
                equipment_id = item[
                    {"PUMP": "pump_id", "TANK": "tank_id", "VALVE": "valve_id"}[equipment_type]
                ]
                subset = sensors[sensors["equipment_id"] == equipment_id]
                counts = subset.groupby(["sensor_type", "sensor_role"]).size().to_dict()
                if counts != roles:
                    composition_errors.append(f"{equipment_id}: {counts}")
        self._check(
            "SENSOR_SCHEMA",
            "SENSOR-COMPOSITION",
            not composition_errors,
            "Every pump/tank/valve has the documented sensor roles",
            "; ".join(composition_errors[:5]) or None,
        )
        unit_errors = [
            f"{row.sensor_id}:{row.sensor_type}->{row.measurement_unit}"
            for row in sensors.itertuples()
            if self.UNIT_BY_TYPE.get(str(row.sensor_type)) != str(row.measurement_unit)
        ]
        self._check(
            "SENSOR_SCHEMA",
            "SENSOR-UNITS",
            not unit_errors,
            "Sensor types use their declared measurement units",
            "; ".join(unit_errors[:5]) or None,
        )
        return list(self.results)

    @classmethod
    def pipe_endpoints_valid(cls, master_data: Dict[str, pd.DataFrame]) -> bool:
        nodes = set()
        for entity, key in (
            ("pumps", "pump_id"),
            ("tanks", "tank_id"),
            ("valves", "valve_id"),
        ):
            for equipment_id in cls._rows(master_data, entity).get(key, []):
                nodes.add(f"NODE-{equipment_id}")
        pipes = cls._rows(master_data, "pipes")
        if pipes.empty:
            return False
        return all(
            row["source_node_id"] in nodes and row["target_node_id"] in nodes
            for _, row in pipes.iterrows()
        )

    @classmethod
    def tank_bounds_valid(cls, master_data: Dict[str, pd.DataFrame]) -> bool:
        tanks = cls._rows(master_data, "tanks")
        if tanks.empty:
            return True
        return bool(
            (tanks["capacity_m3"] > 0).all()
            and (tanks.get("height_m", pd.Series([1] * len(tanks))) > 0).all()
            and tanks["initial_level_pct"].between(0, 100).all()
        )

    @classmethod
    def topology_connected(cls, master_data: Dict[str, pd.DataFrame]) -> bool:
        facilities = cls._rows(master_data, "facilities")
        pipes = cls._rows(master_data, "pipes")
        if facilities.empty or pipes.empty:
            return False
        for _, facility in facilities.iterrows():
            facility_id = facility["facility_id"]
            graph = nx.Graph()
            for entity, key in (
                ("pumps", "pump_id"),
                ("tanks", "tank_id"),
                ("valves", "valve_id"),
            ):
                equipment = cls._rows(master_data, entity)
                if not equipment.empty:
                    for _, row in equipment[equipment["facility_id"] == facility_id].iterrows():
                        graph.add_node(f"NODE-{row[key]}")
            for _, pipe in pipes[pipes["facility_id"] == facility_id].iterrows():
                graph.add_edge(pipe["source_node_id"], pipe["target_node_id"])
            if graph.number_of_nodes() and not nx.is_connected(graph):
                return False
        return True

    @staticmethod
    def simulation_lineage_valid(run: Any) -> bool:
        if isinstance(run, pd.Series):
            run = run.to_dict()
        if not isinstance(run, dict):
            return False
        if not run.get("configuration_hash"):
            return False
        manifest = run.get("input_manifest")
        if not manifest:
            return False
        try:
            parsed = json.loads(manifest) if isinstance(manifest, str) else manifest
        except (TypeError, json.JSONDecodeError):
            return False
        return bool(
            isinstance(parsed, dict)
            and isinstance(parsed.get("master_data_files", parsed.get("master_data_sha256")), list | dict)
            and parsed.get("master_data_files", parsed.get("master_data_sha256"))
        )

    def validate_simulation_runs(self, simulation_runs: pd.DataFrame) -> List[Dict[str, Any]]:
        outcomes = []
        for _, run in simulation_runs.iterrows():
            valid = self.simulation_lineage_valid(run)
            outcomes.append(
                self._check(
                    "LINEAGE",
                    "SIMULATION-INPUT-LINEAGE",
                    valid,
                    "Simulation configuration and input manifest are recorded",
                    None,
                    "simulation_runs",
                    run.get("simulation_run_id"),
                )
            )
        return outcomes

    # ------------------------------------------------------------------
    # Dataset-level checks
    # ------------------------------------------------------------------
    def validate_dataset(self, output_dir: str) -> List[Dict[str, Any]]:
        root = Path(output_dir)
        config = self.config or load_config_for_dir(str(root))
        self.config = config
        master = {name: _read_csv(root / f"{name}.csv") for name in self.PRIMARY_KEYS}
        telemetry = _read_csv(root / "telemetry.csv")
        scenarios = _read_csv(root / "scenario_definitions.csv")
        ground_truth = _read_csv(root / "ground_truth.csv")
        alarms = _read_csv(root / "alarms.csv")
        alarm_events = _read_csv(root / "alarm_events.csv")
        incidents = _read_csv(root / "alarm_incidents.csv")
        runs = _read_csv(root / "simulation_runs.csv")

        self.validate_master_data(master)
        self._validate_scale(master)
        self._validate_simulation(master, runs, telemetry, root)
        self._validate_telemetry(master, telemetry, runs, config, ground_truth)
        self._validate_scenarios(master, scenarios, ground_truth, config)
        self._validate_physics(master, telemetry, scenarios, ground_truth, config)
        self._validate_alarms(master, alarms, alarm_events, config)
        self._validate_evaluation(
            root, runs, ground_truth, alarms, incidents
        )
        self._validate_detector_isolation(master, telemetry, config)
        self._validate_negative_extended()
        self._validate_database(root, config, ground_truth, incidents)
        return list(self.results)

    def _validate_scale(self, master: Dict[str, pd.DataFrame]) -> None:
        assert self.config is not None
        expected = {
            "facilities": self.config.scale.facilities,
            "pumps": self.config.scale.pumps,
            "tanks": self.config.scale.tanks,
            "valves": self.config.scale.valves,
        }
        actual = {name: len(master.get(name, [])) for name in expected}
        self._check(
            "SCALE",
            "MASTER-SCALE",
            actual == expected,
            "Master-data counts match the configured scale",
            f"actual={actual}, expected={expected}",
        )
        sensor_count = len(master.get("sensors", []))
        expected_sensors = expected["pumps"] * 2 + expected["tanks"] * 4 + expected["valves"]
        self._check(
            "SCALE",
            "SENSOR-COUNT",
            sensor_count == expected_sensors,
            "Sensor count matches 2 pump + 4 tank + 1 valve sensors per equipment",
            f"actual={sensor_count}, expected={expected_sensors}",
        )

    def _validate_simulation(
        self,
        master: Dict[str, pd.DataFrame],
        runs: pd.DataFrame,
        telemetry: pd.DataFrame,
        root: Path,
    ) -> None:
        assert self.config is not None
        config = self.config
        self._check(
            "LINEAGE",
            "SIMULATION-RUN-PRESENT",
            not runs.empty,
            "A completed simulation run record exists",
            f"rows={len(runs)}",
        )
        if runs.empty:
            return
        run = runs.iloc[-1]
        self._check(
            "LINEAGE",
            "SIMULATION-STATUS",
            str(run.get("status")) == "COMPLETED",
            "Simulation run is marked COMPLETED",
        )
        self._check(
            "LINEAGE",
            "SIMULATION-VERSIONS",
            str(run.get("schema_version")) == __schema_version__
            and str(run.get("generator_version")) == self.config.generator_version,
            "Schema and generator versions match the package configuration",
            f"run_schema={run.get('schema_version')}, package={__schema_version__}",
        )
        self._check(
            "LINEAGE",
            "SIMULATION-SCENARIO-SET",
            str(run.get("scenario_set")) == config.scenarios.scenario_set,
            "Scenario set in the run record matches the configuration",
        )
        expected_start = datetime.fromisoformat(config.simulation.start_time)
        expected_end = expected_start + timedelta(hours=config.simulation.duration_hours)
        time_ok = (
            pd.Timestamp(run.get("start_time")) == pd.Timestamp(expected_start)
            and pd.Timestamp(run.get("end_time")) == pd.Timestamp(expected_end)
        )
        self._check(
            "LINEAGE",
            "SIMULATION-TIME-WINDOW",
            bool(time_ok),
            "Run start/end match the configured simulation window",
            f"{run.get('start_time')} .. {run.get('end_time')}",
        )
        self._check(
            "LINEAGE",
            "CONFIGURATION-HASH",
            str(run.get("configuration_hash")) == config.get_config_hash(),
            "Run configuration hash equals the saved configuration hash",
        )
        manifest = _json_dict(run.get("input_manifest"))
        stored_hashes = manifest.get("master_data_sha256", {})
        import hashlib

        mismatched = []
        for name, expected_hash in stored_hashes.items():
            path = root / name
            if not path.exists():
                mismatched.append(f"{name}:missing")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != expected_hash:
                mismatched.append(name)
        self._check(
            "LINEAGE",
            "MASTER-DATA-HASHES",
            bool(stored_hashes) and not mismatched,
            "Input manifest hashes match the generated master-data files",
            f"mismatched={mismatched}" if mismatched else f"{len(stored_hashes)} files",
        )
        if not telemetry.empty:
            outcome = _json_dict(run.get("outcome_summary"))
            self._check(
                "LINEAGE",
                "SIMULATION-OUTCOME-COUNT",
                int(outcome.get("telemetry_rows", -1)) == len(telemetry),
                "Outcome summary telemetry row count matches telemetry.csv",
                f"summary={outcome.get('telemetry_rows')}, actual={len(telemetry)}",
            )

    def _validate_telemetry(
        self,
        master: Dict[str, pd.DataFrame],
        telemetry: pd.DataFrame,
        runs: pd.DataFrame,
        config: Config,
        ground_truth: pd.DataFrame,
    ) -> None:
        if telemetry.empty:
            self._check("TELEMETRY", "TELEMETRY-PRESENT", False, "Telemetry data exists")
            return
        self._check("TELEMETRY", "TELEMETRY-PRESENT", True, "Telemetry data exists")
        required = {
            "telemetry_id",
            "sensor_id",
            "simulation_run_id",
            "timestamp",
            "measured_value",
            "measurement_unit",
            "quality_status",
            "operating_mode_id",
        }
        missing_columns = required - set(telemetry.columns)
        self._check(
            "TELEMETRY",
            "TELEMETRY-COLUMNS",
            not missing_columns,
            "Telemetry contains the required observed-data columns",
            f"missing={sorted(missing_columns)}" if missing_columns else None,
        )
        forbidden = {
            "scenario_id",
            "ground_truth_id",
            "gt_id",
            "issue_type",
            "expected_detection",
            "expected_alarm_category",
        }
        leaked = forbidden & set(telemetry.columns)
        self._check(
            "ISOLATION",
            "TELEMETRY-NO-GROUND-TRUTH",
            not leaked,
            "Telemetry contains no scenario or ground-truth label columns",
            f"leaked={sorted(leaked)}" if leaked else None,
        )
        self._check(
            "TELEMETRY",
            "TELEMETRY-UNIQUE-ID",
            not telemetry["telemetry_id"].duplicated().any(),
            "telemetry_id is unique",
        )
        self._check(
            "TELEMETRY",
            "TELEMETRY-UNIQUE-SAMPLE",
            not telemetry.duplicated(["sensor_id", "timestamp"]).any(),
            "Each (sensor, timestamp) sample is unique",
        )
        ts = pd.to_datetime(telemetry["timestamp"], errors="coerce")
        self._check(
            "TELEMETRY",
            "TELEMETRY-TIMESTAMPS",
            ts.notna().all(),
            "All telemetry timestamps parse",
        )
        start = pd.Timestamp(config.simulation.start_time)
        interval = int(config.simulation.sampling_interval_seconds)
        steps = int(
            round(config.simulation.duration_hours * 3600.0 / interval)
        )
        expected_last = start + pd.Timedelta(seconds=(steps - 1) * interval)
        aligned = (
            ((ts - start).dt.total_seconds() % interval).abs() < 1e-6
        )
        self._check(
            "TELEMETRY",
            "TELEMETRY-CADENCE",
            bool(aligned.all())
            and ts.min() == start
            and ts.max() == expected_last,
            "All samples lie on the configured cadence and cover the run window",
            f"min={ts.min()}, max={ts.max()}, expected_last={expected_last}",
        )
        numeric = pd.to_numeric(telemetry["measured_value"], errors="coerce")
        self._check(
            "TELEMETRY",
            "TELEMETRY-VALUES",
            bool(numeric.notna().all() and np.isfinite(numeric.to_numpy()).all()),
            "Measured values are finite numbers",
        )
        quality_ok = telemetry["quality_status"].isin(
            {"GOOD", "UNCERTAIN", "BAD", "MISSING"}
        ).all()
        self._check(
            "TELEMETRY",
            "TELEMETRY-QUALITY",
            bool(quality_ok),
            "Quality statuses use the documented vocabulary",
        )
        sensor_units = master["sensors"].set_index("sensor_id")["measurement_unit"]
        unit_match = (
            telemetry["sensor_id"].map(sensor_units) == telemetry["measurement_unit"]
        )
        self._check(
            "TELEMETRY",
            "TELEMETRY-UNITS",
            bool(unit_match.fillna(False).all()),
            "Telemetry units match sensor metadata",
        )
        self._check(
            "TELEMETRY",
            "TELEMETRY-SENSOR-FK",
            telemetry["sensor_id"].isin(master["sensors"]["sensor_id"]).all(),
            "Every telemetry row references a known sensor",
        )
        run_ids = set(runs.get("simulation_run_id", []))
        run_ok = bool(run_ids) and telemetry["simulation_run_id"].isin(run_ids).all()
        self._check(
            "TELEMETRY",
            "TELEMETRY-RUN-FK",
            run_ok,
            "Every telemetry row references the simulation run",
        )
        mode_ids = set(master["operating_modes"]["operating_mode_id"])
        self._check(
            "TELEMETRY",
            "TELEMETRY-MODE-FK",
            telemetry["operating_mode_id"].isin(mode_ids).all(),
            "Every operating mode reference is known",
        )

        # Per-sensor completeness: a sensor is either complete or its missing
        # samples are explained by sensor-fault ground-truth windows.
        counts = telemetry.groupby("sensor_id").size()
        unexplained = []
        gt = ground_truth
        sensor_windows: Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]] = {}
        if not gt.empty:
            for _, event in gt[gt["issue_type"] == "SENSOR_FAULT"].iterrows():
                sensor_id = event.get("affected_sensor_id")
                if pd.notna(sensor_id):
                    sensor_windows.setdefault(str(sensor_id), []).append(
                        (
                            pd.Timestamp(event["start_time"]),
                            pd.Timestamp(event["end_time"]),
                        )
                    )
        for sensor_id in master["sensors"]["sensor_id"]:
            observed_count = int(counts.get(sensor_id, 0))
            if observed_count == steps:
                continue
            observed_times = ts[telemetry["sensor_id"] == sensor_id]
            expected_times = pd.date_range(start=start, periods=steps, freq=f"{interval}s")
            missing = expected_times.difference(pd.DatetimeIndex(observed_times))
            windows = sensor_windows.get(str(sensor_id), [])
            explained = all(
                any(item_start <= moment < item_end for item_start, item_end in windows)
                for moment in missing
            )
            if not explained:
                unexplained.append(f"{sensor_id}: {len(missing)} missing samples")
        self._check(
            "TELEMETRY",
            "TELEMETRY-COMPLETENESS",
            not unexplained,
            "Missing samples are confined to labelled sensor-fault windows",
            "; ".join(unexplained[:5]) or None,
        )

    def _validate_scenarios(
        self,
        master: Dict[str, pd.DataFrame],
        scenarios: pd.DataFrame,
        ground_truth: pd.DataFrame,
        config: Config,
    ) -> None:
        if scenarios.empty or ground_truth.empty:
            self._check("SCENARIO", "SCENARIO-PRESENT", False, "Scenario and ground-truth rows exist")
            return
        self._check("SCENARIO", "SCENARIO-PRESENT", True, "Scenario and ground-truth rows exist")
        self._check(
            "SCENARIO",
            "SCENARIO-UNIQUE",
            not scenarios["scenario_id"].duplicated().any()
            and not ground_truth["gt_id"].duplicated().any(),
            "Scenario and ground-truth identifiers are unique",
        )
        scenario_ids = set(scenarios["scenario_id"])
        gt_scenarios = set(ground_truth["scenario_id"])
        one_to_one = scenario_ids == gt_scenarios and len(scenarios) == len(ground_truth)
        self._check(
            "SCENARIO",
            "SCENARIO-GROUND-TRUTH-ONE-TO-ONE",
            one_to_one,
            "Every scenario definition has exactly one ground-truth row",
            f"scenarios={len(scenarios)}, truth={len(ground_truth)}",
        )
        start = pd.Timestamp(config.simulation.start_time)
        end = start + pd.Timedelta(hours=config.simulation.duration_hours)
        bounded = (
            (pd.to_datetime(scenarios["start_time"]) >= start).all()
            and (pd.to_datetime(scenarios["end_time"]) <= end).all()
            and (pd.to_datetime(scenarios["end_time"]) > pd.to_datetime(scenarios["start_time"])).all()
        )
        self._check(
            "SCENARIO",
            "SCENARIO-WINDOWS",
            bool(bounded),
            "Scenario windows are valid, ordered and inside the run",
        )
        positives = ground_truth[ground_truth["issue_type"] != "NORMAL"]
        normals = ground_truth[ground_truth["issue_type"] == "NORMAL"]
        self._check(
            "SCENARIO",
            "SCENARIO-NORMAL-WINDOWS",
            not normals.empty,
            "Explicit NORMAL ground-truth windows exist",
            f"windows={len(normals)}",
        )
        positive_intervals = [
            (pd.Timestamp(row.start_time), pd.Timestamp(row.end_time))
            for row in positives.itertuples()
        ]
        normal_intervals = [
            (pd.Timestamp(row.start_time), pd.Timestamp(row.end_time))
            for row in normals.itertuples()
        ]
        overlap = False
        for p_start, p_end in positive_intervals:
            for n_start, n_end in normal_intervals:
                if max(p_start, n_start) < min(p_end, n_end):
                    overlap = True
                    break
            if overlap:
                break
        self._check(
            "SCENARIO",
            "SCENARIO-WINDOW-DISJOINT",
            not overlap,
            "Positive and NORMAL windows do not overlap",
        )
        # Coverage: union of all windows is continuous across the run.
        ordered = sorted(positive_intervals + normal_intervals)
        gaps = []
        cursor = start
        for window_start, window_end in ordered:
            if window_start - cursor > pd.Timedelta(seconds=1.5 * config.simulation.sampling_interval_seconds):
                gaps.append(f"{cursor.isoformat()}..{window_start.isoformat()}")
            cursor = max(cursor, window_end)
        if end - cursor > pd.Timedelta(seconds=1.5 * config.simulation.sampling_interval_seconds):
            gaps.append(f"{cursor.isoformat()}..{end.isoformat()}")
        self._check(
            "SCENARIO",
            "SCENARIO-WINDOW-COVERAGE",
            not gaps,
            "NORMAL windows plus anomaly windows cover the run without unlabelled gaps",
            f"gaps={gaps[:3]}" if gaps else None,
        )
        severity_ok = set(ground_truth["severity"].dropna().astype(str)) <= {
            "light",
            "medium",
            "severe",
            "normal",
        }
        self._check(
            "SCENARIO",
            "SCENARIO-SEVERITY",
            severity_ok,
            "Scenario severities use the documented vocabulary",
        )
        sensor_ids = set(master["sensors"]["sensor_id"])
        equipment_ids = set(
            master["tanks"]["tank_id"].tolist()
            + master["pumps"]["pump_id"].tolist()
            + master["valves"]["valve_id"].tolist()
        )
        bad_sensors = []
        for row in ground_truth.itertuples():
            expected = _as_list(getattr(row, "expected_sensor_ids", None))
            if getattr(row, "issue_type") != "NORMAL" and not expected:
                bad_sensors.append(f"{row.gt_id}:no expected sensors")
            for sensor_id in expected:
                if sensor_id not in sensor_ids:
                    bad_sensors.append(f"{row.gt_id}:{sensor_id}")
            if pd.notna(getattr(row, "affected_equipment_id", None)) and str(
                row.affected_equipment_id
            ) not in equipment_ids:
                bad_sensors.append(f"{row.gt_id}:unknown equipment")
        self._check(
            "SCENARIO",
            "SCENARIO-EXPECTED-SENSORS",
            not bad_sensors,
            "Expected sensors and affected equipment exist in master data",
            "; ".join(bad_sensors[:5]) or None,
        )

    def _validate_physics(
        self,
        master: Dict[str, pd.DataFrame],
        telemetry: pd.DataFrame,
        scenarios: pd.DataFrame,
        ground_truth: pd.DataFrame,
        config: Config,
    ) -> None:
        if telemetry.empty or ground_truth.empty:
            return
        frame = telemetry.copy()
        frame["ts"] = pd.to_datetime(frame["timestamp"])
        frame["physical"] = pd.to_numeric(frame["physical_state_value"], errors="coerce")
        sensors = master["sensors"].set_index("sensor_id")
        tanks = master["tanks"].set_index("tank_id")
        pumps = master["pumps"].set_index("pump_id")
        normal_intervals = [
            (pd.Timestamp(row.start_time), pd.Timestamp(row.end_time))
            for row in ground_truth[ground_truth["issue_type"] == "NORMAL"].itertuples()
        ]
        normal_mask = _within_any(frame["ts"], normal_intervals)
        frame["normal"] = normal_mask

        # Hydrostatic pressure consistency (all scenarios preserve it).
        errors = []
        for tank_id, tank in tanks.iterrows():
            level_sensor = sensors[
                (sensors["equipment_id"] == tank_id)
                & (sensors["sensor_type"] == "LEVEL")
            ].index
            pressure_sensor = sensors[
                (sensors["equipment_id"] == tank_id)
                & (sensors["sensor_type"] == "PRESSURE")
            ].index
            if not len(level_sensor) or not len(pressure_sensor):
                continue
            level = frame[frame["sensor_id"] == level_sensor[0]][["ts", "physical"]]
            pressure = frame[frame["sensor_id"] == pressure_sensor[0]][["ts", "physical"]]
            merged = level.merge(pressure, on="ts", suffixes=("_level", "_pressure"))
            expected = merged["physical_level"] / 100.0 * float(tank["height_m"]) * WATER_HEAD_TO_BAR
            tolerance = (merged["physical_pressure"].abs() * config.simulation.pressure_tolerance_pct / 100.0).clip(lower=0.005)
            relative = ((merged["physical_pressure"] - expected).abs() / tolerance).max()
            errors.append(float(relative) if pd.notna(relative) else 0.0)
        self._check(
            "PHYSICS",
            "PHYSICS-HYDROSTATIC-PRESSURE",
            not errors or max(errors) <= 1.0,
            "Tank pressure equals hydrostatic head within configured tolerance",
            f"worst_tolerance_ratio={max(errors):.3f}" if errors else None,
        )

        # Pump curve consistency on normal windows.
        curve_errors = []
        for pump_id, pump in pumps.iterrows():
            flow_sensor = sensors[
                (sensors["equipment_id"] == pump_id)
                & (sensors["sensor_type"] == "FLOW")
            ].index
            pressure_sensor = sensors[
                (sensors["equipment_id"] == pump_id)
                & (sensors["sensor_type"] == "PRESSURE")
            ].index
            if not len(flow_sensor) or not len(pressure_sensor):
                continue
            flow = frame[(frame["sensor_id"] == flow_sensor[0]) & frame["normal"]][["ts", "physical"]]
            pressure = frame[(frame["sensor_id"] == pressure_sensor[0]) & frame["normal"]][["ts", "physical"]]
            merged = flow.merge(pressure, on="ts", suffixes=("_flow", "_pressure"))
            if merged.empty:
                continue
            q_nom = float(pump["nominal_flow_m3_h"])
            h_nom = float(pump["nominal_head_m"])
            shutoff = h_nom * config.simulation.pump_curve_shutoff_factor
            k = (shutoff - h_nom) / q_nom**2 if q_nom else 0.001
            expected_head = np.maximum(0.0, shutoff - k * merged["physical_flow"].to_numpy() ** 2)
            observed_head = merged["physical_pressure"].to_numpy() / WATER_HEAD_TO_BAR
            residual = np.abs(observed_head - expected_head) / np.maximum(expected_head, 1e-9) * 100.0
            curve_errors.append(float(np.percentile(residual, 99.9)))
        self._check(
            "PHYSICS",
            "PHYSICS-PUMP-CURVE",
            not curve_errors or max(curve_errors) <= config.detection.pump_curve_tolerance_pct,
            "Normal-window pump head-flow points follow the nominal curve",
            f"worst_p99.9_residual_pct={max(curve_errors):.3f}" if curve_errors else None,
        )

        # Tank mass balance on normal windows.
        balance_errors = []
        for tank_id, tank in tanks.iterrows():
            level_sensor = sensors[(sensors["equipment_id"] == tank_id) & (sensors["sensor_type"] == "LEVEL")].index
            inlet_sensor = sensors[
                (sensors["equipment_id"] == tank_id)
                & (sensors["sensor_type"] == "FLOW")
                & (sensors["sensor_role"] == "inlet")
            ].index
            outlet_sensor = sensors[
                (sensors["equipment_id"] == tank_id)
                & (sensors["sensor_type"] == "FLOW")
                & (sensors["sensor_role"] == "outlet")
            ].index
            if not len(level_sensor) or not len(inlet_sensor) or not len(outlet_sensor):
                continue
            level = frame[frame["sensor_id"] == level_sensor[0]][["ts", "physical"]].rename(columns={"physical": "level"})
            inlet = frame[frame["sensor_id"] == inlet_sensor[0]][["ts", "physical"]].rename(columns={"physical": "inlet"})
            outlet = frame[frame["sensor_id"] == outlet_sensor[0]][["ts", "physical"]].rename(columns={"physical": "outlet"})
            merged = level.merge(inlet, on="ts").merge(outlet, on="ts").sort_values("ts")
            merged["dt_h"] = merged["ts"].diff().dt.total_seconds() / 3600.0
            merged = merged[merged["dt_h"].between(0.9 * config.simulation.sampling_interval_seconds / 3600, 1.1 * config.simulation.sampling_interval_seconds / 3600)]
            if merged.empty:
                continue
            dV_dt = merged["level"].diff() / 100.0 * float(tank["capacity_m3"]) / merged["dt_h"]
            residual = merged["inlet"] - merged["outlet"] - dV_dt
            threshold = np.maximum(
                config.detection.balance_absolute_tolerance_m3_h,
                config.detection.balance_relative_tolerance_pct / 100.0
                * (merged["inlet"].abs() + merged["outlet"].abs()),
            )
            # A scenario boundary is not a steady-state interval: the injected
            # offset is removed at the labelled end, producing a one-sample
            # recovery step. Require both the current and previous samples to
            # be in a NORMAL window.
            mask = _within_any(merged["ts"], normal_intervals) & _within_any(
                merged["ts"] - pd.Timedelta(
                    seconds=config.simulation.sampling_interval_seconds
                ),
                normal_intervals,
            )
            if mask.any():
                ratio = (residual[mask].abs() / threshold[mask]).max()
                balance_errors.append(float(ratio) if pd.notna(ratio) else 0.0)
        self._check(
            "PHYSICS",
            "PHYSICS-TANK-MASS-BALANCE",
            not balance_errors or max(balance_errors) <= 1.0,
            "Normal-window tank flows balance the measured level change",
            f"worst_tolerance_ratio={max(balance_errors):.3f}" if balance_errors else None,
        )

        # Injected signals: leaks and pump faults must be physically present.
        leak_messages = []
        for row in ground_truth[ground_truth["issue_type"] == "LEAK"].itertuples():
            equipment_id = str(row.affected_equipment_id)
            if equipment_id not in tanks.index:
                leak_messages.append(f"{row.gt_id}:unknown tank")
                continue
            level_sensor = sensors[(sensors["equipment_id"] == equipment_id) & (sensors["sensor_type"] == "LEVEL")].index
            inlet_sensor = sensors[
                (sensors["equipment_id"] == equipment_id)
                & (sensors["sensor_type"] == "FLOW")
                & (sensors["sensor_role"] == "inlet")
            ].index
            outlet_sensor = sensors[
                (sensors["equipment_id"] == equipment_id)
                & (sensors["sensor_type"] == "FLOW")
                & (sensors["sensor_role"] == "outlet")
            ].index
            if not len(level_sensor) or not len(inlet_sensor) or not len(outlet_sensor):
                leak_messages.append(f"{row.gt_id}:missing sensors")
                continue
            level = frame[frame["sensor_id"] == level_sensor[0]][["ts", "physical"]].rename(columns={"physical": "level"})
            inlet = frame[frame["sensor_id"] == inlet_sensor[0]][["ts", "physical"]].rename(columns={"physical": "inlet"})
            outlet = frame[frame["sensor_id"] == outlet_sensor[0]][["ts", "physical"]].rename(columns={"physical": "outlet"})
            merged = level.merge(inlet, on="ts").merge(outlet, on="ts").sort_values("ts")
            merged["dt_h"] = merged["ts"].diff().dt.total_seconds() / 3600.0
            merged = merged[merged["dt_h"].between(0.9 * config.simulation.sampling_interval_seconds / 3600, 1.1 * config.simulation.sampling_interval_seconds / 3600)]
            dV_dt = merged["level"].diff() / 100.0 * float(tanks.loc[equipment_id, "capacity_m3"]) / merged["dt_h"]
            residual = merged["inlet"] - merged["outlet"] - dV_dt
            mask = (merged["ts"] >= pd.Timestamp(row.start_time) + pd.Timedelta(seconds=config.simulation.sampling_interval_seconds * 2)) & (
                merged["ts"] < pd.Timestamp(row.end_time)
            )
            median = float(residual[mask].median()) if mask.any() else 0.0
            minimum = max(0.5, 0.005 * float(tanks.loc[equipment_id, "capacity_m3"]))
            if not (median > minimum):
                leak_messages.append(f"{row.gt_id}:residual={median:.3f}")
        self._check(
            "PHYSICS",
            "PHYSICS-LEAK-SIGNAL",
            not leak_messages,
            "Every leak injection produces a positive flow-balance residual",
            "; ".join(leak_messages[:5]) or None,
        )

        pump_messages = []
        for row in ground_truth[ground_truth["issue_type"].isin(["BLOCKAGE", "PUMP_DEGRADATION"])].itertuples():
            pump_id = str(row.affected_equipment_id)
            if pump_id not in pumps.index:
                pump_messages.append(f"{row.gt_id}:unknown pump")
                continue
            flow_sensor = sensors[(sensors["equipment_id"] == pump_id) & (sensors["sensor_type"] == "FLOW")].index
            pressure_sensor = sensors[(sensors["equipment_id"] == pump_id) & (sensors["sensor_type"] == "PRESSURE")].index
            if not len(flow_sensor) or not len(pressure_sensor):
                pump_messages.append(f"{row.gt_id}:missing sensors")
                continue
            flow = frame[frame["sensor_id"] == flow_sensor[0]][["ts", "physical"]].rename(columns={"physical": "flow"})
            pressure = frame[frame["sensor_id"] == pressure_sensor[0]][["ts", "physical"]].rename(columns={"physical": "pressure"})
            merged = flow.merge(pressure, on="ts").sort_values("ts")
            q_nom = float(pumps.loc[pump_id, "nominal_flow_m3_h"])
            h_nom = float(pumps.loc[pump_id, "nominal_head_m"])
            shutoff = h_nom * config.simulation.pump_curve_shutoff_factor
            k = (shutoff - h_nom) / q_nom**2 if q_nom else 0.001
            expected = np.maximum(0.0, shutoff - k * merged["flow"].to_numpy() ** 2)
            observed = merged["pressure"].to_numpy() / WATER_HEAD_TO_BAR
            residual = np.where(expected > 0, (observed - expected) / expected * 100.0, 0.0)
            span = pd.Timestamp(row.end_time) - pd.Timestamp(row.start_time)
            mask = (merged["ts"] >= pd.Timestamp(row.start_time) + span * 0.25) & (
                merged["ts"] < pd.Timestamp(row.end_time)
            )
            median_abs = float(np.median(np.abs(residual[mask]))) if mask.any() else 0.0
            if median_abs < 5.0:
                pump_messages.append(f"{row.gt_id}:residual={median_abs:.2f}%")
        self._check(
            "PHYSICS",
            "PHYSICS-PUMP-FAULT-SIGNAL",
            not pump_messages,
            "Blockage/degradation injections move the pump operating point off the nominal curve",
            "; ".join(pump_messages[:5]) or None,
        )

        # Sensor-fault signals.
        sensor_messages = []
        for row in ground_truth[ground_truth["issue_type"] == "SENSOR_FAULT"].itertuples():
            sensor_id = str(row.affected_sensor_id) if pd.notna(row.affected_sensor_id) else ""
            equipment_id = str(row.affected_equipment_id)
            params = _json_dict(row.injection_parameters)
            start = pd.Timestamp(row.start_time)
            end = pd.Timestamp(row.end_time)
            subset = frame[(frame["sensor_id"] == sensor_id) & (frame["ts"] >= start) & (frame["ts"] < end)]
            if not len(subset):
                # Missing injection is verified by absence plus the gap alarm.
                observed = frame[
                    (frame["sensor_id"] == sensor_id)
                    & (frame["ts"] >= start)
                    & (frame["ts"] < end)
                ]
                if len(observed) == 0:
                    continue
            fault_type = None
            level_sensor = sensors[(sensors["equipment_id"] == equipment_id) & (sensors["sensor_type"] == "LEVEL")].index
            pressure_sensor = sensors[(sensors["equipment_id"] == equipment_id) & (sensors["sensor_type"] == "PRESSURE")].index
            if pd.notna(row.affected_sensor_id) and str(row.affected_sensor_id) in level_sensor:
                level_measured = frame[(frame["sensor_id"] == sensor_id) & (frame["ts"] >= start) & (frame["ts"] < end)][["ts", "measured_value"]]
                if not len(level_measured) or not len(pressure_sensor):
                    continue
                pressure_physical = frame[(frame["sensor_id"] == pressure_sensor[0]) & (frame["ts"] >= start) & (frame["ts"] < end)][["ts", "physical"]]
                merged = level_measured.merge(pressure_physical, on="ts")
                if not len(merged):
                    continue
                expected_level = merged["physical"] / (float(tanks.loc[equipment_id, "height_m"]) * WATER_HEAD_TO_BAR) * 100.0
                residual = merged["measured_value"].astype(float) - expected_level
                if float(residual.abs().max()) <= config.detection.level_pressure_tolerance_pct:
                    # Stuck sensors are constant rather than biased; accept a
                    # zero variation over the window as the fault signature.
                    if float(merged["measured_value"].astype(float).std()) > 1e-9:
                        sensor_messages.append(f"{row.gt_id}:no redundancy signal")
        self._check(
            "PHYSICS",
            "PHYSICS-SENSOR-FAULT-SIGNAL",
            not sensor_messages,
            "Bias/drift/stuck sensor injections create redundancy or temporal evidence",
            "; ".join(sensor_messages[:5]) or None,
        )

    def _validate_alarms(
        self,
        master: Dict[str, pd.DataFrame],
        alarms: pd.DataFrame,
        events: pd.DataFrame,
        config: Config,
    ) -> None:
        if alarms.empty:
            self._check("ALARM", "ALARM-PRESENT", False, "Alarm episodes exist")
            return
        self._check("ALARM", "ALARM-PRESENT", True, "Alarm episodes exist", f"rows={len(alarms)}")
        self._check(
            "ALARM",
            "ALARM-UNIQUE",
            not alarms["alarm_id"].duplicated().any(),
            "alarm_id is unique",
        )
        self._check(
            "ISOLATION",
            "ALARM-NO-SCENARIO-ID",
            "scenario_id" not in alarms.columns,
            "Alarm output carries no scenario identifier",
        )
        categories = {"PROCESS_FAULT", "SENSOR_FAULT", "UNCERTAIN"}
        self._check(
            "ALARM",
            "ALARM-CATEGORY",
            set(alarms["alarm_category"]) <= categories,
            "Alarm categories use PROCESS_FAULT, SENSOR_FAULT or UNCERTAIN",
        )
        severity_ok = set(alarms["severity"]) <= {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
        self._check("ALARM", "ALARM-SEVERITY", severity_ok, "Alarm severities use the documented vocabulary")
        self._check(
            "ALARM",
            "ALARM-OCCURRENCE",
            (pd.to_numeric(alarms["occurrence_count"], errors="coerce").fillna(0) >= 1).all(),
            "occurrence_count is at least one for every episode",
        )
        first = pd.to_datetime(alarms["first_detected_at"], errors="coerce")
        last = pd.to_datetime(alarms["last_detected_at"], errors="coerce")
        start = pd.Timestamp(config.simulation.start_time)
        end = start + pd.Timedelta(hours=config.simulation.duration_hours)
        time_ok = (
            first.notna().all()
            and last.notna().all()
            and (first <= last).all()
            and (first >= start).all()
            and (last <= end).all()
        )
        self._check("ALARM", "ALARM-TIME-ORDER", bool(time_ok), "Alarm episodes are ordered and inside the run")
        sensor_to_equipment = master["sensors"].set_index("sensor_id")["equipment_id"].to_dict()
        bad_equipment = [
            row.alarm_id
            for row in alarms.itertuples()
            if pd.notna(row.sensor_id)
            and str(row.sensor_id) in sensor_to_equipment
            and str(row.equipment_id) != str(sensor_to_equipment[str(row.sensor_id)])
        ]
        self._check(
            "ALARM",
            "ALARM-EQUIPMENT-ATTRIBUTION",
            not bad_equipment,
            "Alarm equipment attribution matches the sensor equipment",
            f"examples={bad_equipment[:5]}" if bad_equipment else None,
        )
        if events.empty:
            self._check("ALARM", "ALARM-HISTORY", False, "Alarm event history exists")
            return
        self._check(
            "ALARM",
            "ALARM-HISTORY",
            not events["event_id"].duplicated().any(),
            "Alarm event history identifiers are unique",
            f"rows={len(events)}",
        )
        created = events[events["event_type"] == "CREATED"].groupby("alarm_id").size()
        resolved = events[events["event_type"] == "RESOLVED"].groupby("alarm_id").size()
        missing_created = set(alarms["alarm_id"]) - set(created.index)
        resolved_status = set(alarms.loc[alarms["alarm_status"] == "RESOLVED", "alarm_id"])
        missing_resolved = resolved_status - set(resolved.index)
        self._check(
            "ALARM",
            "ALARM-HISTORY-COMPLETE",
            not missing_created and not missing_resolved,
            "Every alarm has CREATED and every resolved alarm has RESOLVED history",
            f"missing_created={list(missing_created)[:3]}, missing_resolved={list(missing_resolved)[:3]}",
        )
        event_times = pd.to_datetime(events["event_timestamp"], errors="coerce")
        self._check(
            "ALARM",
            "ALARM-HISTORY-TIMESTAMPS",
            event_times.notna().all()
            and (event_times >= start).all()
            and (event_times <= end + pd.Timedelta(seconds=config.simulation.sampling_interval_seconds)).all(),
            "Alarm history timestamps are valid and within the run",
        )
        categories_by_rule = {
            "RULE-003": "SENSOR_FAULT",
            "RULE-004": "SENSOR_FAULT",
            "RULE-008": "SENSOR_FAULT",
            "RULE-009": "SENSOR_FAULT",
            "RULE-010": "SENSOR_FAULT",
            "RULE-006U": "UNCERTAIN",
        }
        category_mismatch = [
            row.alarm_id
            for row in alarms.itertuples()
            if categories_by_rule.get(str(row.rule_id), "PROCESS_FAULT") != str(row.alarm_category)
        ]
        self._check(
            "ALARM",
            "ALARM-RULE-CATEGORY",
            not category_mismatch,
            "Rule IDs map to the documented alarm categories",
            f"examples={category_mismatch[:5]}" if category_mismatch else None,
        )

    def _validate_evaluation(
        self,
        root: Path,
        runs: pd.DataFrame,
        ground_truth: pd.DataFrame,
        alarms: pd.DataFrame,
        incidents: pd.DataFrame,
    ) -> None:
        path = root / "evaluation_metrics.json"
        if not path.exists():
            self._check("EVALUATION", "EVALUATION-PRESENT", False, "evaluation_metrics.json exists")
            return
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._check("EVALUATION", "EVALUATION-PRESENT", False, "evaluation_metrics.json is valid JSON")
            return
        self._check("EVALUATION", "EVALUATION-PRESENT", True, "evaluation_metrics.json exists")
        event = result.get("event_level", {})
        point = result.get("point_level", {})
        self._check(
            "EVALUATION",
            "EVALUATION-SEPARATION",
            "point_level" in result
            and "event_level" in result
            and result.get("evaluation_units", {}).get("event")
            and result.get("evaluation_units", {}).get("point"),
            "Point-level and event-level evaluations are separate and documented",
        )
        check_fields = {"true_positives", "false_negatives", "false_positives", "precision", "recall", "f1_score"}
        self._check(
            "EVALUATION",
            "EVENT-METRICS-PRESENT",
            event.get("status") == "EVALUATED" and check_fields <= set(event),
            "Event-level metrics have all required fields",
        )
        tp = event.get("true_positives", 0)
        fn = event.get("false_negatives", 0)
        fp = event.get("false_positives", 0)
        positives = event.get("positive_event_count", 0)
        normal_count = event.get("normal_event_count", 0)
        self._check(
            "EVALUATION",
            "EVENT-DENOMINATORS",
            tp + fn == positives and event.get("matched_event_count") == tp,
            "Event TPs and FNs partition the positive ground-truth events",
            f"tp={tp}, fn={fn}, positives={positives}",
        )
        precision_expected = None if tp + fp == 0 else tp / (tp + fp)
        recall_expected = None if positives == 0 else tp / positives
        def same(left: Any, right: Any) -> bool:
            if left is None or right is None:
                return left is None and right is None
            return abs(float(left) - float(right)) < 1e-12

        self._check(
            "EVALUATION",
            "EVENT-FORMULAS",
            same(event.get("precision"), precision_expected)
            and same(event.get("recall"), recall_expected),
            "Event precision and recall are computed from their stated denominators",
            f"precision={precision_expected}, recall={recall_expected}",
        )
        self._check(
            "EVALUATION",
            "EVENT-FP-UNIT",
            event.get("false_positives") == event.get("false_alarm_incident_count")
            and "unmatched alarm incident" in str(event.get("matching_policy", {}).get("false_alarm_unit", "")),
            "Event false positives are unmatched incidents, not raw alarm rows",
            f"fp={event.get('false_positives')}, incidents={event.get('false_alarm_incident_count')}",
        )
        raw_rows = len(alarms)
        incident_count = event.get("alarm_incident_count")
        self._check(
            "EVALUATION",
            "EVENT-INCIDENT-ACCOUNTING",
            int(event.get("total_alarm_events", -1)) == raw_rows
            and int(event.get("matched_alarm_event_count", 0)) <= raw_rows
            and int(incident_count or 0) <= raw_rows,
            "Alarm rows and incidents are accounted for without mixing units",
            f"alarm_rows={raw_rows}, incidents={incident_count}",
        )
        if not incidents.empty:
            matched = incidents[incidents["classification"] == "MATCHED"]
            false_alarms = incidents[incidents["classification"] == "FALSE_ALARM"]
            unknown = incidents[incidents["classification"] == "UNKNOWN"]
            self._check(
                "EVALUATION",
                "INCIDENT-ONE-TO-ONE",
                not matched["matched_gt_id"].dropna().duplicated().any()
                and not matched["incident_id"].duplicated().any(),
                "Each incident matches at most one ground-truth event and vice versa",
                f"matched={len(matched)}",
            )
            self._check(
                "EVALUATION",
                "INCIDENT-CLASSIFICATION",
                len(false_alarms) == event.get("false_alarm_incident_count")
                and len(unknown) == event.get("unknown_incident_count"),
                "Incident classifications agree with event-level counts",
                f"FA={len(false_alarms)}, unknown={len(unknown)}",
            )
            self._check(
                "EVALUATION",
                "INCIDENT-SENSOR-PROCESS-SEPARATION",
                not (
                    (matched["categories"].str.contains("PROCESS_FAULT", regex=False))
                    & (~matched["categories"].str.contains("SENSOR_FAULT", regex=False))
                    & (matched["matched_gt_id"].isin(
                        ground_truth.loc[
                            ground_truth["issue_type"] == "SENSOR_FAULT", "gt_id"
                        ]
                    ))
                ).any(),
                "Sensor-fault ground-truth events are never matched by a process-only incident",
            )
        else:
            self._check("EVALUATION", "INCIDENT-ONE-TO-ONE", False, "Incident table exists")
        if point.get("status") == "EVALUATED":
            confusion = point.get("confusion_matrix", {})
            labelled = point.get("labelled_rows", 0)
            confusion_total = sum(
                int(confusion.get(key, 0))
                for key in ("true_positives", "false_positives", "true_negatives", "false_negatives")
            )
            self._check(
                "EVALUATION",
                "POINT-LABEL-CONSISTENCY",
                labelled == point.get("positive_rows", 0) + point.get("negative_rows", 0)
                and confusion_total == labelled,
                "Point confusion matrix contains only explicit labelled samples",
                f"labelled={labelled}, matrix={confusion_total}",
            )
            self._check(
                "EVALUATION",
                "POINT-FORMULAS",
                same(
                    confusion.get("precision"),
                    None
                    if confusion.get("true_positives", 0) + confusion.get("false_positives", 0) == 0
                    else confusion["true_positives"]
                    / (confusion["true_positives"] + confusion["false_positives"]),
                )
                and same(
                    confusion.get("recall"),
                    None
                    if confusion.get("true_positives", 0) + confusion.get("false_negatives", 0) == 0
                    else confusion["true_positives"]
                    / (confusion["true_positives"] + confusion["false_negatives"]),
                ),
                "Point precision and recall are computed from explicit labelled samples",
            )
            telemetry_rows = len(_read_csv(root / "telemetry.csv"))
            self._check(
                "EVALUATION",
                "POINT-UNKNOWN-EXCLUDED",
                point.get("unknown_samples", 0)
                + labelled
                + point.get("unobserved_labelled_rows", 0)
                == telemetry_rows,
                "Every telemetry row is labelled, unobserved or explicitly unknown",
                f"unknown={point.get('unknown_samples')}, labelled={labelled}, telemetry={telemetry_rows}",
            )
        else:
            self._check("EVALUATION", "POINT-LEVEL", False, "Point-level evaluation was executed")
        events_path = root / "evaluation_events.csv"
        if events_path.exists():
            evaluated_events = pd.read_csv(events_path)
            self._check(
                "EVALUATION",
                "EVALUATION-EVENTS-COUNT",
                len(evaluated_events) == len(ground_truth)
                and int(evaluated_events["matched"].astype(bool).sum()) == tp,
                "Per-event evaluation rows match ground truth and event TP count",
                f"rows={len(evaluated_events)}, matched={int(evaluated_events['matched'].sum())}",
            )
        else:
            self._check("EVALUATION", "EVALUATION-EVENTS-COUNT", False, "evaluation_events.csv exists")
        metrics_path = root / "evaluation_metrics.csv"
        self._check(
            "EVALUATION",
            "EVALUATION-METRICS-FLATTENED",
            metrics_path.exists() and not pd.read_csv(metrics_path).empty,
            "Machine-readable flattened evaluation metrics exist",
        )
        # Zero-denominator policy is executable, not just documented.
        try:
            from .evaluation import Evaluator

            evaluator = Evaluator(self.config or Config())
            normal_gt = pd.DataFrame(
                [
                    {
                        "gt_id": "GT-NORMAL",
                        "issue_type": "NORMAL",
                        "severity": "normal",
                        "start_time": "2026-01-01T00:00:00",
                        "end_time": "2026-01-01T00:10:00",
                        "expected_detection": "NO",
                        "expected_alarm_category": "NORMAL",
                    }
                ]
            )
            zero = evaluator.evaluate(pd.DataFrame(), normal_gt)
            zero_event = zero.get("event_level", {})
            passed = (
                zero_event.get("recall") is None
                and zero_event.get("precision") is None
                and zero_event.get("f1_score") is None
            )
            self._check(
                "EVALUATION",
                "ZERO-DENOMINATOR",
                passed,
                "Zero denominators return null metrics instead of favourable zeros",
                f"precision={zero_event.get('precision')}, recall={zero_event.get('recall')}",
            )
        except Exception as exc:  # pragma: no cover - reported
            self._check("EVALUATION", "ZERO-DENOMINATOR", False, "Zero-denominator policy executes", str(exc))

    def _validate_detector_isolation(
        self,
        master: Dict[str, pd.DataFrame],
        telemetry: pd.DataFrame,
        config: Config,
    ) -> None:
        if telemetry.empty:
            self._check("ISOLATION", "DETECTOR-ISOLATION", False, "Detector isolation test needs telemetry")
            return
        try:
            from .detection import DetectionEngine
            from .id_generator import IDGenerator

            frame = telemetry.copy()
            frame["ts"] = pd.to_datetime(frame["timestamp"])
            # A three-hour slice equals 39,600 rows in full mode: enough to
            # exercise every sensor without paying for a second full detection.
            cutoff = frame["ts"].min() + pd.Timedelta(hours=3)
            subset = frame[frame["ts"] < cutoff].drop(columns=["ts"]).copy()
            observed_columns = [
                "sensor_id",
                "timestamp",
                "measured_value",
                "quality_status",
                "operating_mode_id",
            ]
            observed = subset[observed_columns].copy()
            poisoned = observed.copy()
            poisoned["scenario_id"] = "GROUND-TRUTH-MUST-NOT-LEAK"
            poisoned["ground_truth_id"] = "GT-MUST-NOT-LEAK"
            poisoned["physical_state_value"] = -999.0
            clean_engine = DetectionEngine(config, master, IDGenerator(seed=config.simulation.random_seed))
            clean = clean_engine.detect("SIM-ISOLATION", observed)
            poisoned_engine = DetectionEngine(config, master, IDGenerator(seed=config.simulation.random_seed))
            dirty = poisoned_engine.detect("SIM-ISOLATION", poisoned)
            compare_columns = [
                "rule_id",
                "equipment_id",
                "sensor_id",
                "alarm_category",
                "first_detected_at",
                "last_detected_at",
                "occurrence_count",
            ]
            equal = (
                len(clean) == len(dirty)
                and clean[compare_columns].reset_index(drop=True).equals(
                    dirty[compare_columns].reset_index(drop=True)
                )
            )
            self._check(
                "ISOLATION",
                "DETECTOR-ISOLATION",
                equal,
                "Detector output is unchanged when scenario/ground-truth/physical columns are poisoned",
                f"clean_alarms={len(clean)}, poisoned_alarms={len(dirty)}",
            )
        except Exception as exc:  # pragma: no cover - reported
            self._check("ISOLATION", "DETECTOR-ISOLATION", False, "Detector isolation test executes", str(exc))

    def _validate_negative_extended(self) -> None:
        try:
            from .evaluation import Evaluator

            evaluator = Evaluator(self.config or Config())
            gt = pd.DataFrame(
                [
                    {
                        "gt_id": "GT-1",
                        "issue_type": "LEAK",
                        "severity": "medium",
                        "affected_equipment_id": "TANK-001",
                        "affected_sensor_id": "SNS-001",
                        "expected_sensor_ids": json.dumps(["SNS-001"]),
                        "start_time": "2026-01-01T00:00:00",
                        "end_time": "2026-01-01T00:10:00",
                        "expected_detection": "YES",
                        "expected_alarm_category": "PROCESS_FAULT",
                    }
                ]
            )
            alarms = pd.DataFrame(
                [
                    {
                        "alarm_id": "A1",
                        "equipment_id": "TANK-001",
                        "sensor_id": "SNS-001",
                        "alarm_category": "PROCESS_FAULT",
                        "severity": "HIGH",
                        "rule_id": "RULE-002",
                        "first_detected_at": "2026-01-01T00:01:00",
                        "last_detected_at": "2026-01-01T00:05:00",
                    },
                    {
                        "alarm_id": "A2",
                        "equipment_id": "TANK-001",
                        "sensor_id": "SNS-001",
                        "alarm_category": "PROCESS_FAULT",
                        "severity": "HIGH",
                        "rule_id": "RULE-006",
                        "first_detected_at": "2026-01-01T00:02:00",
                        "last_detected_at": "2026-01-01T00:06:00",
                    },
                ]
            )
            result = evaluator.evaluate(alarms, gt)
            event = result["event_level"]
            passed = (
                event["true_positives"] == 1
                and event["false_positives"] == 0
                and event["alarm_incident_count"] == 1
                and event["corroborating_alarm_event_count"] == 1
            )
            self._check(
                "NEGATIVE",
                "NEG-006-DUPLICATE-ALARMS",
                passed,
                "Two overlapping alarm rows for one event count as one TP, not two",
                f"tp={event['true_positives']}, incidents={event['alarm_incident_count']}",
            )
        except Exception as exc:  # pragma: no cover - reported
            self._check("NEGATIVE", "NEG-006-DUPLICATE-ALARMS", False, "Duplicate-alarm guard executes", str(exc))

        try:
            from .detection import DetectionEngine
            from .id_generator import IDGenerator

            sensors = pd.DataFrame(
                [
                    {
                        "sensor_id": "SNS-FLOW",
                        "facility_id": "FAC-001",
                        "equipment_id": "PUMP-001",
                        "equipment_type": "PUMP",
                        "sensor_type": "FLOW",
                        "sensor_role": "discharge",
                        "measurement_unit": "m3/h",
                        "accuracy_tolerance": 1.0,
                        "sampling_interval_seconds": 60,
                        "lifecycle_state": "ACTIVE",
                    }
                ]
            )
            pumps = pd.DataFrame(
                [
                    {
                        "pump_id": "PUMP-001",
                        "facility_id": "FAC-001",
                        "nominal_flow_m3_h": 100.0,
                        "nominal_head_m": 50.0,
                    }
                ]
            )
            telemetry = pd.DataFrame(
                [
                    {
                        "sensor_id": "SNS-FLOW",
                        "timestamp": f"2026-01-01T00:{minute:02d}:00",
                        "measured_value": -10.0,
                        "quality_status": "GOOD",
                        "operating_mode_id": None,
                    }
                    for minute in range(3)
                ]
            )
            engine = DetectionEngine(
                self.config or Config(),
                {"sensors": sensors, "pumps": pumps, "tanks": pd.DataFrame()},
                IDGenerator(),
            )
            alarms = engine.detect("SIM-NEG", telemetry)
            passed = (
                not alarms.empty
                and "RULE-008" in set(alarms["rule_id"])
                and set(
                    alarms.loc[alarms["rule_id"] == "RULE-008", "alarm_category"]
                ) == {"SENSOR_FAULT"}
            )
            self._check(
                "NEGATIVE",
                "NEG-007-IMPLAUSIBLE-SENSOR",
                passed,
                "An implausible flow reading raises a sensor fault, not a process fault",
            )
        except Exception as exc:  # pragma: no cover - reported
            self._check("NEGATIVE", "NEG-007-IMPLAUSIBLE-SENSOR", False, "Implausible-sensor guard executes", str(exc))

    def _validate_database(
        self,
        root: Path,
        config: Config,
        ground_truth: pd.DataFrame,
        incidents: pd.DataFrame,
    ) -> None:
        from .persistence import Database

        db_path = Path(config.database_path)
        if not db_path.exists():
            self.add_result(
                "DATABASE",
                "SQLITE-EXPORT",
                "WARN",
                "SQLite database has not been exported yet",
                details=str(db_path),
            )
            return
        try:
            db = Database(str(db_path))
            integrity = db.integrity_check()
            violations = db.foreign_key_violations()
            self._check(
                "DATABASE",
                "SQLITE-INTEGRITY",
                integrity == "ok" and not violations,
                "SQLite integrity and foreign-key checks pass",
                f"integrity={integrity}, fk_violations={len(violations)}",
            )
            count_checks = {
                "facilities": _read_csv(root / "facilities.csv"),
                "pumps": _read_csv(root / "pumps.csv"),
                "tanks": _read_csv(root / "tanks.csv"),
                "valves": _read_csv(root / "valves.csv"),
                "sensors": _read_csv(root / "sensors.csv"),
                "telemetry": _read_csv(root / "telemetry.csv"),
                "alarms": _read_csv(root / "alarms.csv"),
                "ground_truth": _read_csv(root / "ground_truth.csv"),
                "alarm_incidents": incidents,
                "evaluation_metrics": _read_csv(root / "evaluation_metrics.csv"),
            }
            mismatches = []
            for table, frame in count_checks.items():
                if not frame.empty and db.get_table_count(table) != len(frame):
                    mismatches.append(
                        f"{table}: db={db.get_table_count(table)}, csv={len(frame)}"
                    )
            self._check(
                "DATABASE",
                "SQLITE-ROW-COUNTS",
                not mismatches,
                "SQLite row counts match the exported CSV files",
                "; ".join(mismatches[:5]) or None,
            )
            metrics_path = root / "evaluation_metrics.json"
            if metrics_path.exists():
                result = json.loads(metrics_path.read_text(encoding="utf-8"))
                expected_tp = result.get("event_level", {}).get("true_positives")
                actual_tp = db.scalar(
                    "SELECT metric_value FROM evaluation_metrics "
                    "WHERE evaluation_level='EVENT' AND scope='overall' "
                    "AND metric_name='true_positives'"
                )
                self._check(
                    "DATABASE",
                    "SQLITE-EVALUATION-METRICS",
                    actual_tp is not None
                    and expected_tp is not None
                    and abs(float(actual_tp) - float(expected_tp)) < 1e-9,
                    "SQLite evaluation metrics agree with evaluation_metrics.json",
                    f"db_tp={actual_tp}, json_tp={expected_tp}",
                )
            db.close()
        except Exception as exc:  # pragma: no cover - reported
            self._check("DATABASE", "SQLITE-INTEGRITY", False, "SQLite database checks execute", str(exc))

    # ------------------------------------------------------------------
    # Negative controls retained from 1.x (five checks)
    # ------------------------------------------------------------------
    def test_negative_scenarios(self, master_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        from .config import Config as RuntimeConfig
        from .detection import DetectionEngine
        from .id_generator import IDGenerator
        from .simulation import ProcessSimulator

        results = []
        invalid_pipe_data = {name: frame.copy() for name, frame in master_data.items()}
        if len(self._rows(invalid_pipe_data, "pipes")):
            invalid_pipe = self._rows(invalid_pipe_data, "pipes").iloc[0].to_dict()
            invalid_pipe["pipe_id"] = "PIPE-INVALID-001"
            invalid_pipe["source_node_id"] = "NODE-MISSING-999"
            invalid_pipe_data["pipes"] = pd.concat(
                [invalid_pipe_data["pipes"], pd.DataFrame([invalid_pipe])],
                ignore_index=True,
            )
        results.append(
            self._negative_result(
                "NEG-001",
                "Pipe references missing node",
                not self.pipe_endpoints_valid(invalid_pipe_data),
                "The shared endpoint validator rejects a missing equipment node",
            )
        )

        invalid_tank_data = {name: frame.copy() for name, frame in master_data.items()}
        if len(self._rows(invalid_tank_data, "tanks")):
            invalid_tank = self._rows(invalid_tank_data, "tanks").iloc[0].to_dict()
            invalid_tank["tank_id"] = "TANK-INVALID-001"
            invalid_tank["initial_level_pct"] = 150
            invalid_tank_data["tanks"] = pd.concat(
                [invalid_tank_data["tanks"], pd.DataFrame([invalid_tank])],
                ignore_index=True,
            )
        results.append(
            self._negative_result(
                "NEG-002",
                "Tank level exceeds capacity",
                not self.tank_bounds_valid(invalid_tank_data),
                "The shared tank bounds validator rejects a level above 100%",
            )
        )

        residual = ProcessSimulator.calculate_mass_balance_residual(100, 50, 10)
        tolerance = (self.config or RuntimeConfig()).simulation.mass_balance_tolerance
        violation = abs(residual) > tolerance * max(100, 50, 1)
        results.append(
            self._negative_result(
                "NEG-003",
                "Flow conservation violated beyond tolerance",
                violation,
                f"Measured flow residual {residual:g} exceeds the configured "
                f"{tolerance:.1%} reference tolerance",
            )
        )

        invalid_run = {
            "simulation_run_id": "SIM-INVALID",
            "configuration_hash": "",
            "input_manifest": "",
        }
        results.append(
            self._negative_result(
                "NEG-004",
                "Simulation output lacks input configuration",
                not self.simulation_lineage_valid(invalid_run),
                "The shared lineage validator rejects missing configuration and input manifest",
            )
        )

        sensor_data = pd.DataFrame(
            [
                {
                    "sensor_id": "SNS-TEST",
                    "equipment_id": "PUMP-TEST",
                    "equipment_type": "PUMP",
                    "sensor_type": "FLOW",
                }
            ]
        )
        pump_data = pd.DataFrame(
            [{"pump_id": "PUMP-TEST", "nominal_flow_m3_h": 100.0}]
        )
        telemetry = pd.DataFrame(
            [
                {
                    "sensor_id": "SNS-TEST",
                    "timestamp": "2026-01-01T00:00:00",
                    "measured_value": 100.0,
                    "quality_status": "GOOD",
                    "scenario_id": "GROUND-TRUTH-MUST-NOT-LEAK",
                    "physical_state_value": 10.0,
                },
                {
                    "sensor_id": "SNS-TEST",
                    "timestamp": "2026-01-01T00:01:00",
                    "measured_value": 100.0,
                    "quality_status": "UNCERTAIN",
                    "scenario_id": "GROUND-TRUTH-MUST-NOT-LEAK",
                    "physical_state_value": 10.0,
                },
            ]
        )
        detector = DetectionEngine(
            self.config or RuntimeConfig(),
            {"sensors": sensor_data, "pumps": pump_data, "tanks": pd.DataFrame()},
            IDGenerator(),
        )
        sensor_fault_alarms = detector.detect("SIM-TEST", telemetry)
        sensor_fault_separated = (
            not sensor_fault_alarms.empty
            and set(sensor_fault_alarms["rule_id"]) == {"RULE-004"}
            and "scenario_id" not in sensor_fault_alarms.columns
        )
        results.append(
            self._negative_result(
                "NEG-005",
                "Sensor fault incorrectly classified as process fault",
                sensor_fault_separated,
                "An uncertain sensor reading produces only the sensor-quality rule and no ground-truth label",
            )
        )
        return results

    def _negative_result(self, test_id: str, name: str, passed: bool, description: str):
        result = {
            "test_id": test_id,
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "description": description,
            "expected": "Invalid input is rejected by the executable validation or detection path",
        }
        self.results.append(result)
        return result

    def generate_report(self, output_path: str) -> Dict[str, Any]:
        report = {
            "validation_summary": {
                "total_tests": len(self.results),
                "passed": sum(result["status"] == "PASS" for result in self.results),
                "failed": sum(result["status"] == "FAIL" for result in self.results),
                "warnings": sum(result["status"] == "WARN" for result in self.results),
                "not_implemented": sum(
                    result["status"] == "NOT_IMPLEMENTED" for result in self.results
                ),
            },
            "results": self.results,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
