# Changelog

All notable changes to this project are documented in this file.

Changes are organized into the following categories:

- **Added:** New features or functionality introduced to the project.
- **Changed:** Modifications to existing functionality that do not add new features.
- **Fixed:** Bug fixes that resolve issues or correct unintended behavior.
- **Removed:** Features or components that have been removed from the project.

## [v0.1.0] - Unreleased

Work toward the initial release. Nothing has been tagged yet.

### Added - v0.1.0

- Initial project scaffolding and community standards documentation.
- Complete technical specification for Foreman, covering scope, capability coverage map, architecture, non-functional requirements, build plan and acceptance criteria.
- Design documentation set: architecture, process decomposition, agent architecture, memory, MCP, integration, retrieval, models, tech stack, security, observability, evaluation, scalability, operations and runbook.
- Seventeen architecture decision records, including the alternatives rejected and what was deliberately left out.
- Glossary and documentation index.
- Phase-by-phase build plan with an explicit gate for each phase.
- Python package scaffold: `uv` project on Python 3.12 with a `src/foreman/` layout, a committed lockfile, and eight dependency groups so the base install stays at four packages.
- `core/errors.py` — the error taxonomy the rest of the system classifies against: `TransientError`, `PermanentError`, `ToolError`, `PolicyViolation` and `BudgetExceeded`.
- `core/config.py` — settings loaded from the environment, every credential a `SecretStr`, and a feature flag for each optional service. Defaults are the zero-cost path: both provider tiers resolve to the mock, so a clean clone runs with no credentials and no network.
- `foreman` command line entry point with `version` and `config`. `config` reports which providers hold credentials by name only, never their values.
- Quality gates wired up: `ruff`, `mypy --strict`, and three `import-linter` contracts enforcing the architectural boundaries described in `docs/architecture.md`.
- Pre-commit hooks including `gitleaks` secret scanning, verified to block a staged credential.
- Test suite covering the settings and error modules, both at 100%.

### Fixed - v0.1.0

- A misspelled provider name in a tier chain was silently skipped rather than reported. `provider_configured()` answered "not configured" for any unrecognised name, which is indistinguishable from a provider whose credential is simply absent. Unknown names are now rejected when settings load; a missing credential still skips, as documented.

### Changed - v0.1.0

- The Phase 0 gate no longer requires that the test suite collect zero tests. It was written assuming Phase 0 would be pure scaffolding, but the settings and error modules carry real behaviour, and `AGENTS.md` requires new behaviour to have a test.

<!-- e.g., -->
<!-- Unreleased -->
<!-- v2.0.0 -->
<!-- v1.1.0 -->
<!-- v1.0.0 -->
<!-- v0.0.1 -->

[v0.1.0]: https://github.com/dileepadev/foreman/branches
