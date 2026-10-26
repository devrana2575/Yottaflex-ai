# Implementation Handover Guide

## Quick Start

### Installation
```bash
cd D:\PROJECTS\yottaflex
pip install -r requirements.txt
pip install -e .
```

### Run Full Pipeline (Recommended)
```bash
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/full-run
```

This will generate master data, simulate, detect anomalies, evaluate, and validate.

### Step by Step
```bash
yottaflex generate --mode full --seed 20261022 --output-dir data/processed/full-run
yottaflex simulate --mode full --seed 20261022 --duration 24 --output-dir data/processed/full-run
yottaflex detect --output-dir data/processed/full-run
yottaflex evaluate --output-dir data/processed/full-run
yottaflex validate --output-dir data/processed/full-run
yottaflex export-sql --output-dir data/processed/full-run
```

## Main Modules

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| config.py | Configuration | Config, DataScaleConfig, SimulationConfig |
| id_generator.py | Deterministic IDs | IDGenerator |
| generator.py | Master data | DataGenerator.generate_all() |
| simulation.py | Physics simulation | ProcessSimulator.simulate_baseline() |
| scenarios.py | Anomaly injection | ScenarioInjector.generate_scenarios() |
| detection.py | Anomaly detection | DetectionEngine.detect() |
| evaluation.py | Metrics | Evaluator.evaluate() |
| validation.py | Validation | Validator.validate_master_data(), test_negative_scenarios() |
| persistence.py | Database | Database |
| cli.py | CLI interface | Click commands |

## Core Equations

### Pump Curve
```python
H(Q) = H_shutoff - k * Q^2
H_shutoff = 1.2 * H_nominal * degradation_factor
k = (H_shutoff - H_nominal) / Q_nominal^2
```

### Tank Volume
```python
V = capacity_m3 * (level_pct / 100)
dV/dt = Q_in - Q_out  (m3/h)
```

### Mass Balance
```python
residual = Q_in - Q_out - dV/dt
# Check if |residual| > tolerance * max(Q_in, Q_out)
```

### Sensor Reading
```python
measured = physical_state + noise
# noise ~ N(0, accuracy_tolerance * 0.1)
# For faults: measured = physical_state + bias
```

## Detection Rules

| Rule ID | Name | Trigger | Severity |
|---------|------|---------|----------|
| RULE-001 | Tank level out of bounds | Level < 10% or > 90% | HIGH |
| RULE-002 | Rapid tank level decline | At least 0.75 percentage points in a five-minute window | MEDIUM |
| RULE-003 | Sensor stuck | Unchanged value for the configured duration (default 30 min) | MEDIUM |
| RULE-004 | Sensor quality / implausible reading | UNCERTAIN, BAD, MISSING, or implausible flow measurement | MEDIUM |
| RULE-005 | Pump operating deviation | Five-minute mean below 80% of nominal flow | HIGH |

## The Five Negative Tests

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| NEG-001 | Pipe references missing node | Shared pipe-endpoint validator rejects the fixture |
| NEG-002 | Tank level exceeds capacity (>100%) | Shared tank-bounds validator rejects the fixture |
| NEG-003 | Flow conservation violated beyond tolerance | Computed residual exceeds configured tolerance |
| NEG-004 | Simulation output lacks input config | Shared lineage validator rejects the fixture |
| NEG-005 | Sensor fault classified as process fault | Detection emits a sensor-quality rule only, with no ground-truth ID |

Run with: `yottaflex validate` or `pytest tests/test_negative_scenarios.py`

## Metrics Explained

| Metric | Definition | Notes |
|--------|------------|-------|
| TP | Scenario injected and alarm raised | Event-level |
| FP | Alarm raised but no matching scenario | False alarm |
| FN | Scenario injected but no alarm | Missed detection |
| TN | Not reported | No population of normal events is defined |
| Precision | TP / (TP + FP) | Of alarms, how many real |
| Recall/Sensitivity | TP / (TP + FN) | Of scenarios, how many caught |
| F1 | 2*P*R/(P+R) | Harmonic mean |
| Detection Rate | TP / Total Injected | Event-level rate |

## Known Limitations

1. **Physics**: Simplified models, not full hydraulic simulation
2. **Detection**: Rule-based only, may miss complex patterns
3. **Scale**: 100k rows work but could be optimized
4. **Anomalies**: One controlled scenario per enabled mechanism (leak, blockage, pump degradation, sensor fault)
5. **Propagation**: Limited cascade effects
6. **Dashboard**: Not implemented (optional)

## Interview Talking Points

### Design Decisions
- **Why rule-based?** Transparency required, explainable to reviewers
- **Why separate ground truth?** Prevents leakage, proper evaluation
- **Why SQLite?** Local, no external deps, relational
- **Why deterministic?** Reproducibility critical

### Implementation Highlights
- Centralized ID generation
- NetworkX topology validation
- Append-only event history
- Comprehensive negative testing
- Full traceability

### Challenges
- Balancing realism vs simplicity
- Ensuring ground truth separation
- Efficient 100k row generation
- Proper evaluation metrics

## Troubleshooting

**Import errors**: Run `pip install -e .`  
**Missing data**: Run generate then simulate  
**SQLite locked**: Close connections  
**Memory issues**: Use starter mode for testing  
**Test failures**: Check Python version and deps
