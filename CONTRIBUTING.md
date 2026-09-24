# Contributing

Thanks for helping make PV Manager better.

## Ground rules

- Privacy and fail-safe behaviour come first. A feature that weakens either
  one needs a very strong reason and a clear user-visible explanation.
- Never add telemetry, tracking or an automatic cloud connection.
- Never let an optional module or AI bypass the central constraint engine.
- Keep user-facing text plain, short and available in German and English.
- Add or adjust tests for behaviour changes.

## Development setup

```bash
git clone <repository-url>
cd PVM-Pro
python -m unittest discover -s tests -t .
npm test
```

Stil prüfen (dieselbe Prüfung wie im CI-Auftrag *Lint and format*):

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
```

No Home Assistant installation is required. The core tests import only
`custom_components.pv_manager.core`, the runtime tests use the stand-ins in
`tests/ha/ha_stubs.py`, and the contract tests read the repository files. The
layers are described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the
expected behaviour per layer in [docs/TEST_PLAN.md](docs/TEST_PLAN.md).

## Adding a module

1. Add a `ModuleSpec` in `custom_components/pv_manager/core/modules.py` with a
   German and English name, summary and reason.
2. Keep dependencies explicit via `requires`.
3. Implement the logic in `custom_components/pv_manager/core/`.
4. Add contract tests in `tests/core/`.
5. Explain in the UI how to disable the module again.

## Pull requests

- One logical change per pull request.
- Run `python -m unittest discover -s tests -t .`, `npm test`, `ruff check .`
  and `ruff format --check .`.
- Add tests for new behaviour. The safety and privacy promises in
  [PRIVACY.md](PRIVACY.md) are enforced by tests; a change that weakens one
  must change those tests deliberately.
- Update `CHANGELOG.md`.
- Do not commit secrets, tokens, API keys or personal data.

## Releases

Steps for publishing a new version, including the repository metadata that HACS
requires, are documented in [docs/PUBLISHING.md](docs/PUBLISHING.md).
