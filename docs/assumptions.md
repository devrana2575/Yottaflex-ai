# Assumptions and Limitations

## Design Assumptions

### Physical Model
- **Simplified hydraulics**: Using approximations, not full Navier-Stokes equations
- **Incompressible fluid**: Water assumed, constant density
- **Steady-state approximations**: Dynamic effects simplified
- **Ideal components**: Some losses approximated
- **Pump curve**: Quadratic approximation H(Q) = H_shutoff - k*Q^2

### Data Generation
- **Deterministic**: Fixed seed ensures reproducibility
- **Synthetic only**: No real industrial data used
- **Uniform distributions**: Used where specific distributions unknown
- **Nominal ranges**: Based on typical industrial values

### Simulation
- **24-hour duration**: Default simulation period
- **60-second sampling**: Fixed sampling interval
- **4 anomaly types**: Leak, blockage, pump degradation, sensor fault
- **One deterministic injection**: One scenario of each enabled type per run
- **Normal baseline**: Most of time in normal operation

### Detection
- **Rule-based only**: No machine learning
- **Fixed thresholds**: Configurable but static
- **Simple rules**: May miss complex patterns
- **Sensor quality aware**: Distinguishes sensor vs process issues
- **Event-level evaluation**: Scenario-based assessment

## Known Limitations

### Technical
- **Scale**: 100k telemetry points should run but may be memory intensive
- **Performance**: Not optimized for real-time
- **Persistence**: SQLite has limits for very large datasets
- **Topology**: Simplified graph, not full P&ID model
- **Validation**: Some checks are simplified

### Modeling
- **No cascading effects**: Anomalies don't propagate complexly
- **Simplified mass balance**: Doesn't account for all system dynamics
- **Sensor model**: Basic noise and bias only
- **Operating modes**: Simplified, mostly normal operation
- **No control systems**: Open-loop simulation

### Detection
- **Threshold-based**: May have false positives/negatives
- **Limited rules**: Only 5 rules implemented
- **No correlation**: Rules applied independently mostly
- **Latency**: Detection latency simplified
- **Unknown anomalies**: Only modeled types detected well

## Accuracy Considerations
- This is NOT a validated digital twin
- NOT suitable for safety-critical applications
- Metrics should be interpreted in context of synthetic data
- Detection performance depends on rule tuning
- Ground truth is complete by construction (advantage of simulation)

## Future Improvements
- More sophisticated physics models
- Machine learning-based detection
- More anomaly types
- Control system simulation
- 3D visualization
- Real-time streaming
- Uncertainty quantification
