"""Validation framework."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import networkx as nx
import pandas as pd


class Validator:
    """Validate generated data, lineage, topology, and negative fixtures."""

    PRIMARY_KEYS: ClassVar[dict[str, str]] = {
        "facilities": "facility_id",
        "pumps": "pump_id",
        "tanks": "tank_id",
        "valves": "valve_id",
        "pipes": "pipe_id",
        "sensors": "sensor_id",
        "operating_modes": "operating_mode_id",
    }

    def __init__(self):
        self.results = []
        self.validation_counter = 0

    def add_result(
        self,
        validation_type: str,
        test_case_id: str,
        status: str,
        description: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: str | None = None,
    ):
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

    @staticmethod
    def _rows(master_data: dict[str, pd.DataFrame], name: str) -> pd.DataFrame:
        return master_data.get(name, pd.DataFrame())

    @classmethod
    def pipe_endpoints_valid(cls, master_data: dict[str, pd.DataFrame]) -> bool:
        nodes = set()
        for entity, key in (
            ("pumps", "pump_id"),
            ("tanks", "tank_id"),
            ("valves", "valve_id"),
        ):
            for equipment_id in cls._rows(master_data, entity).get(key, []):
                nodes.add(f"NODE-{equipment_id}")
        pipes = cls._rows(master_data, "pipes")
        return all(
            row["source_node_id"] in nodes and row["target_node_id"] in nodes
            for _, row in pipes.iterrows()
        )

    @classmethod
    def tank_bounds_valid(cls, master_data: dict[str, pd.DataFrame]) -> bool:
        tanks = cls._rows(master_data, "tanks")
        if tanks.empty:
            return True
        return bool(
            (tanks["capacity_m3"] > 0).all()
            and tanks["initial_level_pct"].between(0, 100).all()
        )

    @classmethod
    def topology_connected(cls, master_data: dict[str, pd.DataFrame]) -> bool:
        facilities = cls._rows(master_data, "facilities")
        pipes = cls._rows(master_data, "pipes")
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
    def simulation_lineage_valid(run) -> bool:
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
            and isinstance(parsed.get("master_data_files"), list)
            and parsed["master_data_files"]
        )

    def validate_master_data(self, master_data: dict[str, pd.DataFrame]) -> list[dict]:
        self.results = []
        self.validation_counter = 0
        for name, primary_key in self.PRIMARY_KEYS.items():
            frame = self._rows(master_data, name)
            valid = primary_key in frame.columns and not frame[primary_key].duplicated().any()
            self.add_result(
                "PRIMARY_KEY",
                f"PK-{name.upper()}",
                "PASS" if valid else "FAIL",
                f"{primary_key} values are unique and present" if valid else f"Missing or duplicate {primary_key}",
                name,
            )

        facility_ids = set(self._rows(master_data, "facilities").get("facility_id", []))
        foreign_keys_valid = True
        foreign_key_details = []
        for name in ("pumps", "tanks", "valves", "pipes", "sensors"):
            frame = self._rows(master_data, name)
            if "facility_id" not in frame.columns:
                if not frame.empty:
                    foreign_keys_valid = False
                    foreign_key_details.append(f"{name} missing facility_id")
                continue
            invalid_count = int((~frame["facility_id"].isin(facility_ids)).sum())
            if invalid_count:
                foreign_keys_valid = False
                foreign_key_details.append(f"{name}: {invalid_count} invalid facility references")
        self.add_result(
            "FOREIGN_KEY",
            "FK-FACILITY",
            "PASS" if foreign_keys_valid else "FAIL",
            "Facility references are valid" if foreign_keys_valid else "Invalid facility references found",
            details="; ".join(foreign_key_details) or None,
        )

        equipment_keys = {
            "PUMP": ("pumps", "pump_id"),
            "TANK": ("tanks", "tank_id"),
            "VALVE": ("valves", "valve_id"),
            "PIPE": ("pipes", "pipe_id"),
        }
        equipment_facilities = {}
        for table, key in equipment_keys.values():
            frame = self._rows(master_data, table)
            if not frame.empty:
                equipment_facilities.update(dict(zip(frame[key], frame["facility_id"])))
        sensors = self._rows(master_data, "sensors")
        sensor_equipment_valid = all(
            row["equipment_type"] in equipment_keys
            and row["equipment_id"] in equipment_facilities
            and equipment_facilities[row["equipment_id"]] == row["facility_id"]
            for _, row in sensors.iterrows()
        )
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
        equipment_relationships_valid = sensor_equipment_valid and pipe_facilities_valid
        self.add_result(
            "FOREIGN_KEY",
            "FK-EQUIPMENT",
            "PASS" if equipment_relationships_valid else "FAIL",
            "Sensor equipment and pipe node references match equipment facilities"
            if equipment_relationships_valid
            else "Invalid sensor equipment or pipe facility relationship found",
        )

        endpoints_valid = self.pipe_endpoints_valid(master_data)
        self.add_result(
            "TOPOLOGY",
            "PIPE-ENDPOINTS",
            "PASS" if endpoints_valid else "FAIL",
            "All pipe endpoints reference equipment nodes" if endpoints_valid else "Invalid pipe endpoints found",
            "pipes",
        )

        tanks_valid = self.tank_bounds_valid(master_data)
        self.add_result(
            "BOUNDS",
            "TANK-BOUNDS",
            "PASS" if tanks_valid else "FAIL",
            "Tank capacities and initial levels are within bounds" if tanks_valid else "Invalid tank capacity or level found",
            "tanks",
        )

        connected = self.topology_connected(master_data)
        self.add_result(
            "TOPOLOGY",
            "FACILITY-CONNECTIVITY",
            "PASS" if connected else "FAIL",
            "Each facility equipment graph is connected" if connected else "Disconnected facility topology found",
        )
        return list(self.results)

    def validate_simulation_runs(self, simulation_runs: pd.DataFrame) -> list[dict]:
        outcomes = []
        for _, run in simulation_runs.iterrows():
            valid = self.simulation_lineage_valid(run)
            outcomes.append(
                self.add_result(
                    "LINEAGE",
                    "SIMULATION-INPUT-LINEAGE",
                    "PASS" if valid else "FAIL",
                    "Simulation configuration and input manifest are recorded"
                    if valid
                    else "Simulation configuration or input manifest is missing/invalid",
                    "simulation_runs",
                    run.get("simulation_run_id"),
                )
            )
        return outcomes

    def test_negative_scenarios(self, master_data: dict[str, pd.DataFrame]) -> list[dict]:
        from .config import Config
        from .detection import DetectionEngine
        from .id_generator import IDGenerator
        from .simulation import ProcessSimulator

        results = []

        invalid_pipe_data = {name: frame.copy() for name, frame in master_data.items()}
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
        tolerance = Config().simulation.mass_balance_tolerance
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
        detector = DetectionEngine(Config(), {"sensors": sensor_data, "pumps": pump_data}, IDGenerator())
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

    def generate_report(self, output_path: str):
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
