"""Append-only equipment state history.

The simulator records explicit state transitions for real lifecycle or
scenario-driven changes.  It does not create placeholder rows just to make the
table non-empty: every row is either an initialization from master data or a
scenario start/recovery transition.  The history table is separate from
telemetry so a detector cannot use state labels as an input feature.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd

from .config import Config

EVENT_COLUMNS = [
    "event_id",
    "equipment_id",
    "equipment_type",
    "simulation_run_id",
    "previous_state",
    "new_state",
    "state_value",
    "event_timestamp",
    "reason",
    "source",
    "source_reference",
    "event_data",
]

STATE_VOCABULARY: Dict[str, set[str]] = {
    "FACILITY": {"UNKNOWN", "ACTIVE", "INACTIVE", "MAINTENANCE"},
    "PUMP": {"UNKNOWN", "ACTIVE", "DEGRADED", "INACTIVE", "MAINTENANCE"},
    "TANK": {"UNKNOWN", "ACTIVE", "LEAKING", "INACTIVE", "MAINTENANCE"},
    "VALVE": {"UNKNOWN", "OPEN", "CLOSED", "PARTIAL"},
    "SENSOR": {"UNKNOWN", "ACTIVE", "FAULTY", "INACTIVE", "MAINTENANCE"},
}

ALLOWED_TRANSITIONS: Dict[str, set[Tuple[str, str]]] = {
    "FACILITY": {
        ("UNKNOWN", "ACTIVE"),
        ("ACTIVE", "INACTIVE"),
        ("INACTIVE", "ACTIVE"),
        ("ACTIVE", "MAINTENANCE"),
        ("MAINTENANCE", "ACTIVE"),
    },
    "PUMP": {
        ("UNKNOWN", "ACTIVE"),
        ("ACTIVE", "DEGRADED"),
        ("DEGRADED", "ACTIVE"),
        ("ACTIVE", "MAINTENANCE"),
        ("MAINTENANCE", "ACTIVE"),
        ("ACTIVE", "INACTIVE"),
        ("INACTIVE", "ACTIVE"),
    },
    "TANK": {
        ("UNKNOWN", "ACTIVE"),
        ("ACTIVE", "LEAKING"),
        ("LEAKING", "ACTIVE"),
        ("ACTIVE", "MAINTENANCE"),
        ("MAINTENANCE", "ACTIVE"),
        ("ACTIVE", "INACTIVE"),
        ("INACTIVE", "ACTIVE"),
    },
    "VALVE": {
        ("UNKNOWN", "OPEN"),
        ("UNKNOWN", "CLOSED"),
        ("UNKNOWN", "PARTIAL"),
        ("OPEN", "CLOSED"),
        ("OPEN", "PARTIAL"),
        ("CLOSED", "OPEN"),
        ("CLOSED", "PARTIAL"),
        ("PARTIAL", "OPEN"),
        ("PARTIAL", "CLOSED"),
    },
    "SENSOR": {
        ("UNKNOWN", "ACTIVE"),
        ("ACTIVE", "FAULTY"),
        ("FAULTY", "ACTIVE"),
        ("ACTIVE", "MAINTENANCE"),
        ("MAINTENANCE", "ACTIVE"),
        ("ACTIVE", "INACTIVE"),
        ("INACTIVE", "ACTIVE"),
    },
}


def transition_allowed(equipment_type: str, previous_state: str, new_state: str) -> bool:
    """Return whether a transition is in the documented state machine."""
    return (str(previous_state), str(new_state)) in ALLOWED_TRANSITIONS.get(
        str(equipment_type), set()
    )


def _entity_rows(master_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    facilities = master_data.get("facilities", pd.DataFrame())
    for _, row in facilities.iterrows():
        rows.append(
            {
                "equipment_id": str(row["facility_id"]),
                "equipment_type": "FACILITY",
                "initial_state": str(row.get("lifecycle_state", "ACTIVE")),
                "table": "facilities",
            }
        )
    pumps = master_data.get("pumps", pd.DataFrame())
    for _, row in pumps.iterrows():
        rows.append(
            {
                "equipment_id": str(row["pump_id"]),
                "equipment_type": "PUMP",
                "initial_state": str(row.get("lifecycle_state", "ACTIVE")),
                "table": "pumps",
            }
        )
    tanks = master_data.get("tanks", pd.DataFrame())
    for _, row in tanks.iterrows():
        rows.append(
            {
                "equipment_id": str(row["tank_id"]),
                "equipment_type": "TANK",
                "initial_state": str(row.get("lifecycle_state", "ACTIVE")),
                "table": "tanks",
            }
        )
    valves = master_data.get("valves", pd.DataFrame())
    for _, row in valves.iterrows():
        rows.append(
            {
                "equipment_id": str(row["valve_id"]),
                "equipment_type": "VALVE",
                # A valve history uses its process position, not the generic
                # lifecycle flag, so OPEN/CLOSED/PARTIAL transitions are real.
                "initial_state": str(row.get("initial_state", "CLOSED")),
                "table": "valves",
            }
        )
    sensors = master_data.get("sensors", pd.DataFrame())
    for _, row in sensors.iterrows():
        rows.append(
            {
                "equipment_id": str(row["sensor_id"]),
                "equipment_type": "SENSOR",
                "initial_state": str(row.get("lifecycle_state", "ACTIVE")),
                "table": "sensors",
            }
        )
    return rows


def _scenario_transition(
    row: pd.Series,
) -> Tuple[str, str, str] | None:
    """Return (equipment_id, equipment_type, fault_state) for a scenario."""
    issue_type = str(row.get("issue_type", "")).upper()
    if issue_type == "LEAK":
        equipment_id = row.get("affected_equipment_id")
        return (str(equipment_id), "TANK", "LEAKING") if pd.notna(equipment_id) else None
    if issue_type in {"BLOCKAGE", "PUMP_DEGRADATION"}:
        equipment_id = row.get("affected_equipment_id")
        return (str(equipment_id), "PUMP", "DEGRADED") if pd.notna(equipment_id) else None
    if issue_type == "SENSOR_FAULT":
        sensor_id = row.get("affected_sensor_id")
        return (str(sensor_id), "SENSOR", "FAULTY") if pd.notna(sensor_id) else None
    return None


def generate_equipment_state_events(
    config: Config,
    master_data: Dict[str, pd.DataFrame],
    scenarios: pd.DataFrame,
    simulation_run_id: str,
) -> pd.DataFrame:
    """Build deterministic initialization and scenario state transitions."""
    start = datetime.fromisoformat(config.simulation.start_time)
    rows = _entity_rows(master_data)
    current: Dict[str, str] = {
        row["equipment_id"]: row["initial_state"] for row in rows
    }
    equipment_type: Dict[str, str] = {
        row["equipment_id"]: row["equipment_type"] for row in rows
    }
    events: List[Dict[str, Any]] = []

    for row in sorted(rows, key=lambda item: (item["equipment_type"], item["equipment_id"])):
        initial = row["initial_state"]
        events.append(
            {
                "equipment_id": row["equipment_id"],
                "equipment_type": row["equipment_type"],
                "previous_state": "UNKNOWN",
                "new_state": initial,
                "event_timestamp": start.isoformat(),
                "reason": "initial state loaded from master data",
                "source": "SIMULATION",
                "source_reference": simulation_run_id,
                "event_data": json.dumps(
                    {
                        "event_kind": "INITIALIZATION",
                        "master_table": row["table"],
                    },
                    sort_keys=True,
                ),
                "_sort_order": 0,
            }
        )

    operations: List[Dict[str, Any]] = []
    if scenarios is not None and not scenarios.empty:
        frame = scenarios.copy()
        frame["_start"] = pd.to_datetime(frame["start_time"], errors="coerce")
        frame["_end"] = pd.to_datetime(frame["end_time"], errors="coerce")
        for _, scenario in frame.iterrows():
            resolved = _scenario_transition(scenario)
            if resolved is None:
                continue
            equipment_id, kind, fault_state = resolved
            if equipment_id not in current or equipment_type.get(equipment_id) != kind:
                raise ValueError(
                    f"Scenario {scenario.get('scenario_id')} references an unknown "
                    f"{kind} state-history entity {equipment_id}"
                )
            scenario_id = str(scenario.get("scenario_id"))
            issue_type = str(scenario.get("issue_type"))
            severity = str(scenario.get("severity"))
            payload = {
                "event_kind": "SCENARIO_START",
                "scenario_id": scenario_id,
                "issue_type": issue_type,
                "severity": severity,
            }
            operations.append(
                {
                    "equipment_id": equipment_id,
                    "equipment_type": kind,
                    "timestamp": scenario["_start"],
                    "new_state": fault_state,
                    "reason": f"scenario {scenario_id} start ({issue_type})",
                    "source": "SCENARIO",
                    "source_reference": scenario_id,
                    "event_data": json.dumps(payload, sort_keys=True),
                    "_sort_order": 1,
                }
            )
            payload = {
                "event_kind": "SCENARIO_END",
                "scenario_id": scenario_id,
                "issue_type": issue_type,
                "severity": severity,
            }
            operations.append(
                {
                    "equipment_id": equipment_id,
                    "equipment_type": kind,
                    "timestamp": scenario["_end"],
                    "new_state": current[equipment_id],
                    "reason": f"scenario {scenario_id} end (recovery)",
                    "source": "SCENARIO",
                    "source_reference": scenario_id,
                    "event_data": json.dumps(payload, sort_keys=True),
                    "_sort_order": 2,
                }
            )

    for operation in sorted(
        operations,
        key=lambda item: (
            pd.Timestamp(item["timestamp"]),
            item["_sort_order"],
            item["equipment_type"],
            item["equipment_id"],
        ),
    ):
        equipment_id = operation["equipment_id"]
        previous = current[equipment_id]
        new_state = operation["new_state"]
        if previous == new_state:
            continue
        if not transition_allowed(operation["equipment_type"], previous, new_state):
            raise ValueError(
                f"Invalid state transition for {equipment_id}: "
                f"{previous} -> {new_state}"
            )
        event = {
            key: operation[key]
            for key in (
                "equipment_id",
                "equipment_type",
                "new_state",
                "reason",
                "source",
                "source_reference",
                "event_data",
            )
        }
        event["previous_state"] = previous
        event["event_timestamp"] = pd.Timestamp(operation["timestamp"]).isoformat()
        events.append(event)
        current[equipment_id] = new_state

    events.sort(
        key=lambda item: (
            pd.Timestamp(item["event_timestamp"]),
            item["equipment_type"],
            item["equipment_id"],
            item["reason"],
        )
    )
    for index, event in enumerate(events, start=1):
        event["event_id"] = f"ESE-{index:06d}"
        event["state_value"] = event["new_state"]
        event["simulation_run_id"] = simulation_run_id
    frame = pd.DataFrame(events)
    for column in EVENT_COLUMNS:
        if column not in frame:
            frame[column] = None
    return frame[EVENT_COLUMNS].reset_index(drop=True)


def validate_state_events(
    events: pd.DataFrame,
    master_data: Dict[str, pd.DataFrame],
    simulation_run_id: str,
    start_time: str | datetime,
    end_time: str | datetime,
) -> List[str]:
    """Return human-readable errors for an event-history frame."""
    errors: List[str] = []
    if events is None or events.empty:
        return ["state-history frame is empty"]
    missing = set(EVENT_COLUMNS) - set(events.columns)
    if missing:
        return [f"state-history columns missing: {sorted(missing)}"]
    if events["event_id"].duplicated().any():
        errors.append("event_id is not unique")

    entities: Dict[str, str] = {}
    for row in _entity_rows(master_data):
        entities[row["equipment_id"]] = row["equipment_type"]
    start = pd.Timestamp(start_time)
    end = pd.Timestamp(end_time)
    seen_initial: set[str] = set()
    for row in events.itertuples():
        equipment_id = str(row.equipment_id)
        kind = str(row.equipment_type)
        if equipment_id not in entities:
            errors.append(f"unknown equipment reference {kind}/{equipment_id}")
            continue
        if entities[equipment_id] != kind:
            errors.append(f"equipment type mismatch for {equipment_id}")
        if str(row.simulation_run_id) != str(simulation_run_id):
            errors.append(f"{row.event_id}: simulation_run_id mismatch")
        if row.previous_state not in STATE_VOCABULARY.get(kind, set()):
            errors.append(f"{row.event_id}: invalid previous_state {row.previous_state}")
        if row.new_state not in STATE_VOCABULARY.get(kind, set()):
            errors.append(f"{row.event_id}: invalid new_state {row.new_state}")
        if not transition_allowed(kind, row.previous_state, row.new_state):
            errors.append(
                f"{row.event_id}: forbidden transition "
                f"{row.previous_state} -> {row.new_state}"
            )
        if row.source not in {"SIMULATION", "SCENARIO", "OPERATOR", "SYSTEM"}:
            errors.append(f"{row.event_id}: invalid source {row.source}")
        if not str(row.source_reference):
            errors.append(f"{row.event_id}: missing source_reference")
        timestamp = pd.Timestamp(row.event_timestamp)
        if pd.isna(timestamp) or timestamp < start or timestamp > end:
            errors.append(f"{row.event_id}: timestamp outside run window")
        if str(row.previous_state) == "UNKNOWN":
            if equipment_id in seen_initial:
                errors.append(f"{row.event_id}: duplicate initialization for {equipment_id}")
            if timestamp != start:
                errors.append(f"{row.event_id}: initialization is not at run start")
            seen_initial.add(equipment_id)
        elif equipment_id not in seen_initial:
            errors.append(f"{row.event_id}: event appears before initialization for {equipment_id}")

    missing_initializations = sorted(set(entities) - seen_initial)
    if missing_initializations:
        errors.append(
            "missing initialization events for "
            + ", ".join(missing_initializations[:10])
            + ("..." if len(missing_initializations) > 10 else "")
        )

    ordered = events.sort_values(
        ["event_timestamp", "equipment_type", "equipment_id", "event_id"],
        kind="stable",
    )
    current: Dict[str, str] = {}
    for row in ordered.itertuples():
        equipment_id = str(row.equipment_id)
        if equipment_id in current and str(row.previous_state) != current[equipment_id]:
            errors.append(
                f"{row.event_id}: previous_state {row.previous_state} does not "
                f"follow {current[equipment_id]}"
            )
        current[equipment_id] = str(row.new_state)
    return errors
