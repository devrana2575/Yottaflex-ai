# Assumptions and Limitations (2.0.0)

## Physical model assumptions

- **Simplified water hydraulics.** Incompressible water at constant density. No CFD, water hammer,
  pump transients, or pipe friction network solve.
- **Pump curve.** Quadratic `H(Q) = H_shutoff - k Q^2`, with
  `H_shutoff = 1.20 * H_nominal`. Blockage/degradation scenarios scale flow and head relative to
  this curve.
- **Tank mass balance.** `dV/dt = Q_in - Q_out` is integrated at the sampling interval. Level is
  clipped to `[0.5%, 99.5%]`. Pressure is hydrostatic:
  `P = level/100 * height * 0.0981 bar`.
- **Tank control.** Outflow follows a proportional level controller with an 8-hour response. Inlet
  flow has a slow diurnal variation plus AR(1) noise.
- **Normal modes.** A 20-minute startup ramp (40% to 100% flow) and a 20-minute shutdown ramp
  (100% to 20%) are simulated and labelled STARTUP/SHUTDOWN. Low process values in these modes are
  expected, not faults.
- **Sensor noise.** Gaussian noise scaled from `accuracy_tolerance`; AR(1) variation is used for
  flow processes. Level has a `0.03 pp` noise floor. Flow measurements are clipped at zero.
- **No cascading failures.** A leak does not drain upstream equipment; a blockage does not
  propagate pressure transients through the network.
- **Single run per scenario set.** One deterministic injection of each enabled mechanism per run;
  multiple events may occur on different assets.

## Scenario assumptions

- Scenario times, equipment indices and severities are fixed in `scenario_matrix`.
- Four sets exist:
  - `default` - demonstration set (4 events, 24 h).
  - `calibration` - 7 events including bias, drift, stuck and missing sensor faults.
  - `evaluation` - 11 events across light/medium/severe process faults and sensor faults.
  - `compact` - 4 events in 7.5 h for the 99,000-row configuration.
- Calibration and evaluation use different windows, equipment and severities. Thresholds were not
  grid-searched on the evaluation set.
- NORMAL windows are explicit complements of anomaly windows. They are split into chunks, not
  inferred from unlabelled time.
- Missing telemetry is injected by removing rows, not by setting a quality flag.
- Bias/drift/stuck sensor faults modify measured values only; the physical state stays normal.

## Detection assumptions

- Rules are transparent and threshold-based; there is no machine learning.
- Detector input is limited to sensor ID, timestamp, measured value, quality status and operating
  mode. Physical state, scenario IDs and ground truth are excluded even if present in the input
  frame.
- A condition must persist for both a sample count and a time span. Short dropouts are grouped; a
  gap longer than 300 s closes the episode.
- Process rules are suppressed in STARTUP, SHUTDOWN and MAINTENANCE.
- A flow-balance residual is a **possible** leak only when corroborated by a level decline.
  Otherwise it is reported as UNCERTAIN.
- Level/pressure disagreement is a sensor fault with ambiguous attribution; the detector does not
  claim which channel is faulty.
- Sensor faults are never automatically classified as physical process faults.

## Evaluation assumptions

- Event unit = one positive ground-truth event or one merged alarm incident.
- Point unit = one `(sensor, timestamp)` sample.
- Event false positives are unmatched incidents (`FALSE_ALARM`), not raw alarm rows.
- Unknown incidents and unknown point labels are reported and excluded from denominators.
- Matching requires equipment, category, sensor overlap where known, and onset within 600 s
  (process) or 3,600 s (sensor). One-to-one greedy assignment is deterministic.
- Precision/recall/F1 are `null` when their denominators are zero.
- Point predictions use the detector's actual active interval, including resolution tails.
- Ground truth is complete by construction because this is a simulation.

## Known limitations

- **Synthetic only.** No real plant data; the results are not evidence of field performance.
- **Simplified physics.** Not a validated digital twin and not suitable for safety-critical use.
- **Light leak sensitivity floor.** `E-LEAK-01` at 1.5% capacity/hour is below the balance/decline
  thresholds. It is intentionally reported as a miss rather than tuned away.
- **Point tails.** Point FP includes samples between physical recovery and episode resolution;
  point FN includes detection latency and any missed event.
- **Sensor localization.** Redundant level/pressure disagreement cannot identify the faulty channel
  without a third reference.
- **Latency asymmetry.** Sensor-fault allowance is one hour; process allowance is ten minutes.
- **Runtime.** The full 316,800-row pipeline takes roughly 40-60 s on the audit machine; the
  99,000-row compact run takes roughly 20 s.
- **SQLite.** Suitable for local analytics, not high-concurrency or very large-scale deployment.
- **No real-time or dashboard.** Batch CLI only; the optional dashboard remains unimplemented.
- **No GitHub publication.** The workspace was not committed or pushed as part of this task.

## Interpretation guidance

Do not compare 1.x precision numbers with 2.0 numbers: the units changed. Report event and point
metrics together, with the false-alarm and unknown counts. A 100% event recall means all injected
events were found; it does not mean the detector has no false alarms or that point-level accuracy
is perfect.
