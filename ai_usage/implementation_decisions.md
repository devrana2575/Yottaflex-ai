# Implementation Decisions (Historical, Superseded)

> **Superseded:** This file records the 1.x implementation decisions. It is retained for history.
> The current 2.0 decisions, evidence and rejected alternatives are in
> [`docs/implementation_decisions.md`](../docs/implementation_decisions.md). The 1.x review that
> precedes the 2.0 changes is in [`docs/baseline_findings.md`](../docs/baseline_findings.md).

## Architecture
- **Modular design**: Separated concerns into config, generation, simulation, detection, etc.
- **CLI-first**: Click-based CLI with subcommands for all operations
- **SQLite persistence**: Local relational storage with full schema
- **Deterministic generation**: Fixed seed (20261022) for reproducibility

## Physics Model
- **Pump curve**: Simplified H(Q) = H_shutoff - k*Q^2 with degradation factor
- **Tank model**: V = capacity * level_fraction, dV/dt = Q_in - Q_out
- **Mass balance**: R = Q_in - Q_out - dV/dt with 1% tolerance
- **Simplified approach**: Documented as approximate, not CFD

## Detection
- **Rule-based**: Transparent rules with rule IDs and evidence
- **Sensor vs process separation**: UNCERTAIN quality status indicates sensor issues
- **Ground truth isolation**: Never used as detector input features

## Data Generation
- **Vectorized where possible**: Efficient generation patterns
- **Deterministic IDs**: Zero-padded, immutable format
- **Stable ordering**: Consistent row order

## Trade-offs
- **Performance vs simplicity**: Prioritized working implementation over optimization
- **Completeness vs time**: Implemented all core requirements
- **ML vs rules**: Used rule-based for transparency as specified
