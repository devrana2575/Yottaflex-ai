# Architecture Document

## System Overview

The YottaFlex simulator is a modular Python application designed for generating synthetic industrial process data with controlled anomalies for testing detection systems.

## Design Principles

1. **Determinism** - Same inputs produce same outputs
2. **Separation of concerns** - Clear module boundaries
3. **Ground truth isolation** - Labels never leak to detector
4. **Transparency** - All rules and assumptions documented
5. **Reproducibility** - Full traceability

## Component Architecture

### Data Flow
```
Config → IDGenerator → DataGenerator → ProcessSimulator → ScenarioInjector → DetectionEngine → Evaluator → Validator
```

### Core Modules

- **config.py**: Configuration dataclasses
- **id_generator.py**: Deterministic ID generation
- **generator.py**: Master data and topology generation
- **simulation.py**: Physics-inspired process simulation
- **scenarios.py**: Controlled anomaly injection
- **detection.py**: Rule-based anomaly detection
- **evaluation.py**: Performance metrics calculation
- **validation.py**: Integrity and negative scenario testing
- **persistence.py**: SQLite database operations
- **schema.py**: Database DDL
- **cli.py**: Command-line interface

## Physical Model

### Pump Model
Simplified curve: $H(Q) = H_{shutoff} - k Q^2$
- $H_{shutoff} = 1.2 \times H_{nominal} \times f_{degradation}$
- $k$ calculated from nominal operating point
- Degradation factor applied to performance

### Tank Model
- Volume: $V = C \times L_{frac}$ where C is capacity
- Mass balance: $\frac{dV}{dt} = Q_{in} - Q_{out}$
- Level: $L_{pct} = 100 \times V/C$
- Bounds enforced in validation

### Mass Balance
Residual: $R = Q_{in} - Q_{out} - \frac{dV}{dt}$
- Tolerance: 1% of flow magnitude
- Non-zero residuals don't always indicate leaks
- Accounts for sensor uncertainty and model simplification

## Topology
- NetworkX graph representation per facility
- Connected topology validated
- Pipes connect equipment nodes
- Facility consistency enforced
- Self-loops and invalid endpoints rejected

## Ground Truth Separation
1. Scenarios generated independently
2. Injection applied to modify physical state/measurements
3. Ground truth recorded separately from telemetry
4. Detection consumes only measured values, sensor metadata, and quality status; internal physical-state values and scenario IDs are removed
5. Evaluation joins predictions to ground truth post-detection

## Anomaly Injection
- **Leaks**: Modify observed tank level readings to show faster decrease
- **Blockages**: Reduce flow, increase pressure
- **Pump degradation**: Reduce flow readings
- **Sensor faults**: Add bias, set quality to UNCERTAIN

## Detection Strategy
Rule-based with explicit rules:
- Each rule has ID, description, conditions, severity
- Evidence captured for explainability
- Sensor faults detected via observed quality status
- Process faults via value ranges and patterns

## Database Design
- Normalized schema with proper FKs
- Append-only event tables for history
- Foreign key enforcement enabled
- Indexes for performance
- Check constraints for data integrity
