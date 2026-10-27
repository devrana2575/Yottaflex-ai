"""End-to-end pipeline, repeatability and reproducibility tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from yottaflex.cli import cli
from yottaflex.config import Config
from yottaflex.detection import DetectionEngine
from yottaflex.evaluation import Evaluator
from yottaflex.id_generator import IDGenerator

DETERMINISTIC_CSV = [
    "facilities.csv",
    "pumps.csv",
    "tanks.csv",
    "valves.csv",
    "pipes.csv",
    "sensors.csv",
    "operating_modes.csv",
    "simulation_runs.csv",
    "scenario_definitions.csv",
    "ground_truth.csv",
    "telemetry.csv",
    "alarms.csv",
    "alarm_events.csv",
    "alarm_incidents.csv",
    "evaluation_events.csv",
]

PIPELINE_OUTPUTS = DETERMINISTIC_CSV + [
    "config.json",
    "simulation_metadata.json",
    "evaluation_metrics.json",
    "evaluation_metrics.csv",
    "evaluation_summary.md",
    "validation_results.csv",
    "validation_summary.json",
    "sql_query_report.json",
    "run_manifest.json",
    "yottaflex.db",
]


def _normalised_config(path: Path) -> dict:
    config = Config.load(str(path))
    payload = config.to_dict()
    for key in ("output_dir", "raw_dir", "reports_dir", "database_path"):
        payload.pop(key, None)
    return payload


def _assert_csv_equal(left_path: Path, right_path: Path, ignore: tuple[str, ...] = ()):
    left = pd.read_csv(left_path).drop(columns=list(ignore), errors="ignore")
    right = pd.read_csv(right_path).drop(columns=list(ignore), errors="ignore")
    pd.testing.assert_frame_equal(left, right, check_dtype=False)


def test_pipeline_outputs_exist(pipeline_dir):
    missing = [name for name in PIPELINE_OUTPUTS if not (pipeline_dir / name).exists()]
    assert not missing
    summary = json.loads((pipeline_dir / "validation_summary.json").read_text())
    assert summary["validation_summary"]["failed"] == 0
    report = json.loads((pipeline_dir / "sql_query_report.json").read_text())
    assert len(report) == 20 and all(item["status"] == "PASS" for item in report)


def test_pipeline_event_metrics_are_consistent(pipeline_dir):
    metrics = json.loads((pipeline_dir / "evaluation_metrics.json").read_text())
    event = metrics["event_level"]
    point = metrics["point_level"]
    assert event["positive_event_count"] == 4
    assert event["true_positives"] == 4
    assert event["false_negatives"] == 0
    assert event["false_positives"] == 0
    assert event["precision"] == event["recall"] == event["f1_score"] == 1.0
    assert point["status"] == "EVALUATED"
    assert set(point["confusion_matrix"]) >= {
        "true_positives",
        "false_positives",
        "true_negatives",
        "false_negatives",
    }
    # Event and point denominators are different units.
    assert event["positive_event_count"] != point["positive_rows"]


def test_second_pipeline_run_is_reproducible(pipeline_dir, tmp_path):
    output = tmp_path / "repeat"
    result = CliRunner().invoke(
        cli,
        [
            "pipeline",
            "--mode",
            "starter",
            "--seed",
            "20261022",
            "--scenario-set",
            "compact",
            "--duration",
            "7.5",
            "--sampling-interval",
            "60",
            "--output-dir",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert not result.exception

    for name in DETERMINISTIC_CSV:
        _assert_csv_equal(pipeline_dir / name, output / name)
    _assert_csv_equal(
        pipeline_dir / "evaluation_metrics.csv",
        output / "evaluation_metrics.csv",
        ignore=("evaluated_at",),
    )
    _assert_csv_equal(
        pipeline_dir / "validation_results.csv",
        output / "validation_results.csv",
        ignore=("validated_at",),
    )
    for name in (
        "simulation_metadata.json",
        "evaluation_metrics.json",
        "evaluation_summary.md",
        "sql_query_report.json",
    ):
        assert (pipeline_dir / name).read_text() == (output / name).read_text(), name

    assert _normalised_config(pipeline_dir / "config.json") == _normalised_config(
        output / "config.json"
    )
    left_manifest = json.loads((pipeline_dir / "run_manifest.json").read_text())
    right_manifest = json.loads((output / "run_manifest.json").read_text())
    assert set(left_manifest["files"]) == set(right_manifest["files"])
    for name in set(left_manifest["files"]) & set(right_manifest["files"]):
        if name in {"evaluation_metrics.csv", "config.json"}:
            continue
        assert left_manifest["files"][name] == right_manifest["files"][name], name


def test_detection_and_evaluation_repeat_in_process(pipeline_dir):
    config = Config.load(str(pipeline_dir / "config.json"))
    master = {
        name: pd.read_csv(pipeline_dir / f"{name}.csv")
        for name in ("sensors", "pumps", "tanks", "operating_modes")
    }
    telemetry = pd.read_csv(pipeline_dir / "telemetry.csv")
    truth = pd.read_csv(pipeline_dir / "ground_truth.csv")
    scenarios = pd.read_csv(pipeline_dir / "scenario_definitions.csv")

    outputs = []
    for _ in range(2):
        engine = DetectionEngine(
            config, master, IDGenerator(seed=config.simulation.random_seed)
        )
        alarms = engine.detect("SIM-REPEAT", telemetry)
        outputs.append((alarms, engine.alarm_events.copy()))
    pd.testing.assert_frame_equal(outputs[0][0], outputs[1][0])
    pd.testing.assert_frame_equal(outputs[0][1], outputs[1][1])

    alarms = outputs[0][0]
    first = Evaluator(config).evaluate(alarms, truth, scenarios, telemetry)
    second = Evaluator(config).evaluate(alarms, truth, scenarios, telemetry)
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    )


def test_cli_rejects_unknown_scenario_set(tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "--scenario-set",
            "not-a-set",
            "--output-dir",
            str(tmp_path / "bad"),
        ],
    )
    assert result.exit_code != 0
    assert "not-a-set" in result.output
