# Tools Used

## AI Tools

- **OpenCode** — primary development and verification agent.
  - 1.x implementation: Big Pickle model. Used for architecture, code generation, testing and
    documentation.
  - 2.0 improvement session: DeepSeek V4.1 Flash Free. Used for baseline reproduction, evaluation
    redesign, simulation/detection improvements, expanded testing, SQL/validation execution,
    reproducibility checks and documentation.
- **Copilot SDK in VS Code** — historical independent verification of the 1.x implementation. Its
  findings are recorded in `ai_usage/verification_notes.md`; the 1.x metric it reproduced is the
  defective baseline documented in `docs/baseline_findings.md`, not a current result.

## Development Tools

- **Python 3.14.4** — runtime used for the final runs.
- **pip** — dependency and editable-package installation.
- **pytest 9.1.1** — 61-test suite.
- **SQLite / Python sqlite3** — schema, foreign-key, integrity and analytics checks.
- **PowerShell / CLI** — clean-run execution and artifact comparison.
- **Git** — local state inspection only. The 2.0 work was not committed, pushed or published.

## Libraries

See `requirements.txt` for the full list. Core runtime libraries are pandas, NumPy, NetworkX,
Click and Rich.
