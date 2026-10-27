"""Executable validation and SQL analytics tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from yottaflex.cli import cli
from yottaflex.config import Config
from yottaflex.persistence import Database


def test_validation_summary_is_all_pass(pipeline_dir):
    summary = json.loads((pipeline_dir / "validation_summary.json").read_text())
    counts = summary["validation_summary"]
    assert counts == {
        "total_tests": 87,
        "passed": 87,
        "failed": 0,
        "warnings": 0,
        "not_implemented": 0,
    }
    statuses = {row["status"] for row in summary["results"]}
    assert statuses == {"PASS"}
    assert all(row["validated_at"] for row in summary["results"])
    assert all(row["validation_id"].startswith("VAL-") for row in summary["results"])
    assert len({row["validation_id"] for row in summary["results"]}) == 87


def test_validation_csv_matches_summary(pipeline_dir):
    summary = json.loads((pipeline_dir / "validation_summary.json").read_text())
    results = pd.read_csv(pipeline_dir / "validation_results.csv")
    assert len(results) == len(summary["results"]) == 87
    assert set(results["status"]) == {"PASS"}
    assert results["validation_id"].is_unique
    assert {"validation_type", "test_case_id", "description"} <= set(results.columns)


def test_sql_query_report_all_expectations_pass(pipeline_dir):
    report = json.loads((pipeline_dir / "sql_query_report.json").read_text())
    assert len(report) == 20
    assert [item["query_number"] for item in report] == list(range(1, 21))
    assert all(item["status"] == "PASS" for item in report), [
        item for item in report if item["status"] != "PASS"
    ]
    assert all("error" not in item for item in report)
    zero_rows = {12, 13, 19}
    for item in report:
        if item["query_number"] in zero_rows:
            assert item["expectation"] == "zero_rows"
            assert item["row_count"] == 0
        else:
            assert item["expectation"] == "nonempty"
            assert item["row_count"] > 0
    assert {item["label"] for item in report} >= {
        "Q12 | Alarm history integrity problems | expect=zero_rows",
        "Q19 | SQLite foreign-key violations | expect=zero_rows",
    }


def test_sql_file_is_read_only_and_declares_expectations():
    text = Path("sql/analysis_queries.sql").read_text()
    statements = [part.strip() for part in text.split(";") if part.strip()]
    assert len(statements) == 20
    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ")
    for statement in statements:
        upper = statement.upper()
        assert not any(token in upper for token in forbidden)
        assert "EXPECT=" in upper
    assert "expect=zero_rows" in text
    assert "expect=nonempty" in text


def test_sql_report_cross_checks_database(pipeline_dir):
    config = Config.load(str(pipeline_dir / "config.json"))
    db = Database(config.database_path)
    try:
        assert db.integrity_check() == "ok"
        assert db.foreign_key_violations() == []
        assert db.scalar("SELECT COUNT(*) FROM telemetry") == 36 * 450
        assert db.scalar("SELECT COUNT(*) FROM alarms") == len(
            pd.read_csv(pipeline_dir / "alarms.csv")
        )
        assert db.scalar("SELECT COUNT(*) FROM alarm_incidents") == len(
            pd.read_csv(pipeline_dir / "alarm_incidents.csv")
        )
        # History integrity query returns no orphans.
        orphans = db.execute_query(
            "SELECT a.alarm_id FROM alarms a "
            "LEFT JOIN alarm_events e ON e.alarm_id = a.alarm_id AND e.event_type = 'CREATED' "
            "WHERE e.alarm_id IS NULL"
        )
        assert orphans == []
        # Every matched incident has a per-event row.
        unmatched = db.execute_query(
            "SELECT i.incident_id FROM alarm_incidents i "
            "LEFT JOIN evaluation_events e ON e.gt_id = i.matched_gt_id "
            "WHERE i.classification = 'MATCHED' AND e.gt_id IS NULL"
        )
        assert unmatched == []
    finally:
        db.close()


def test_run_sql_cli_repeats_identically(pipeline_dir, tmp_path):
    original = json.loads((pipeline_dir / "sql_query_report.json").read_text())
    output = tmp_path / "sql_report.json"
    result = CliRunner().invoke(
        cli,
        [
            "run-sql",
            "--output-dir",
            str(pipeline_dir),
            "--sql-file",
            "sql/analysis_queries.sql",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    repeated = json.loads(output.read_text())
    assert len(repeated) == len(original) == 20
    for left, right in zip(original, repeated):
        assert left["query_number"] == right["query_number"]
        assert left["status"] == right["status"] == "PASS"
        assert left["row_count"] == right["row_count"]
        assert left["rows"] == right["rows"]


def test_validation_report_contains_policy_checks(pipeline_dir):
    report = json.loads((pipeline_dir / "validation_summary.json").read_text())
    by_id = {row["test_case_id"]: row for row in report["results"]}
    for test_id in (
        "EVALUATION-SEPARATION",
        "EVENT-DENOMINATORS",
        "EVENT-FP-UNIT",
        "EVENT-INCIDENT-ACCOUNTING",
        "POINT-LABEL-CONSISTENCY",
        "POINT-UNKNOWN-EXCLUDED",
        "ZERO-DENOMINATOR",
        "ALARM-RULE-CATEGORY",
        "SCENARIO-WINDOW-COVERAGE",
        "PHYSICS-LEAK-SIGNAL",
        "PHYSICS-PUMP-FAULT-SIGNAL",
        "DETECTOR-ISOLATION",
        "MASTER-DATA-HASHES",
        "SQLITE-ROW-COUNTS",
        "SQLITE-EVALUATION-METRICS",
    ):
        assert by_id[test_id]["status"] == "PASS", test_id
