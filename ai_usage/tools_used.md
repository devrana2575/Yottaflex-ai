# Tools Used

## AI Tools

- **OpenCode** — primary development and verification agent.
  - 1.x implementation: Big Pickle model. Used for architecture, code generation, testing and
    documentation.
  - 2.0 improvement session: DeepSeek V4.1 Flash Free. Used for baseline reproduction, evaluation
    redesign, simulation/detection improvements, expanded testing, SQL/validation execution,
    reproducibility checks and documentation.
  - 2026-10-27 submission-readiness audit: DeepSeek V4.1 Flash Free. Re-ran clean setup, evaluation,
    validation, SQL, tests and two reproducibility runs; audited isolation, negative controls, seed
    determinism and AI-use records; fixed two re-verified defects and updated documentation.
  - 2026-10-28 exact-100k remediation: DeepSeek V4.1 Flash Free. Added exact telemetry allocation,
    append-only equipment state history, JSON/SQL exports, targeted tests and evidence; re-ran
    validation, SQL, evaluation/full pipelines and reproducibility; completed the final audit and
    published after the user explicitly authorized `push`.
- **Copilot SDK in VS Code** — historical independent verification of the 1.x implementation. Its
  findings are recorded in `ai_usage/verification_notes.md`; the 1.x metric it reproduced is the
  defective baseline documented in `docs/baseline_findings.md`, not a current result.

## Development Tools

- **Python 3.14.4** — runtime used for the final runs. Main environment: pandas 3.0.3 / NumPy 2.4.6;
  prior fresh audit virtual environment: pandas 3.1.0 / NumPy 2.5.4. The cross-version environment
  was not recreated for the 2026-10-28 remediation.
- **pip** — dependency and editable-package installation, including the prior fresh virtual
  environment.
- **pytest 9.1.1** — final 68-test suite.
- **SQLite / Python sqlite3** — schema, foreign-key, integrity, JSON/SQL seed and analytics checks.
- **PowerShell / CLI** — clean-run execution, hashing, artifact comparison and repository audits.
- **Git** — repository and diff inspection. The 2.0 implementation was committed as `6103e1a` and
  pushed to `origin/main` only after explicit user authorization. The 2026-10-27 audit corrections
  were committed and pushed after separate explicit user authorization. The 2026-10-28 remediation
  was committed after review and pushed to `origin/main` after the user explicitly authorized
  publication with the prompt `push`. No force-push or shared-history rewrite was performed.

## Libraries

See `requirements.txt` for the full list. Core runtime libraries are pandas, NumPy, NetworkX,
Click and Rich.
