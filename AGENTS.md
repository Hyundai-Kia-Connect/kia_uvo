# Agent instructions: kia_uvo

These rules apply to every AI coding agent (Claude Code, Copilot, Codex, Cursor
and others) and to human contributors. `CLAUDE.md` and
`.github/copilot-instructions.md` point here, so keep this file as the single
source of truth.

This is the Home Assistant custom integration (HACS) for Kia Uvo / Hyundai
Bluelink. All vehicle API work happens in the
[hyundai_kia_connect_api](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api)
library. This repo only maps that library onto Home Assistant.

## Pull request rules

- **Keep PRs small.** Aim for under 100 changed lines, tests excluded, whenever
  the change allows. If a change grows past that,
  split it into a sequence of PRs that each stand on their own.
- **One concern per PR.** Don't mix a fix with a feature, and don't combine
  either with a refactor or formatting changes. Mix them only when the change
  can't work otherwise, and say why in the PR description.
- **Follow the existing architecture.** Extend the patterns already in the
  code instead of adding new ones (see below). If a change seems to need a new
  pattern, open an issue to discuss it before writing the code.
- **Vehicle API logic goes in the library, not here.** If a change needs new
  data or a new command from the car, make it in hyundai_kia_connect_api
  first, then bump the library in a separate PR here.
- **Keep comments and docstrings short.** Write them only when they help
  whoever changes the code next: why something non-obvious is done, a vendor
  quirk, a constraint. Don't restate the code, describe the change history,
  or explain the PR. Those belong in the commit message or PR description.
- **PR titles use Conventional Commits.** CI enforces this
  (`lintPR.yaml`), and releases are versioned from it: `fix: ...`,
  `feat(sensor): ...`, `refactor: ...`, `chore: ...`, `test: ...`, `docs: ...`.
- **Don't edit `version` in `manifest.json`.** The release workflow sets it.
  The `hyundai_kia_connect_api` pin in `requirements` is normally bumped by the
  `bump-api-dependency` workflow. Change it by hand only in a dedicated PR.
- **Check for overlap first.** Before reporting "a new bug plus a fix", search
  your own open PRs and issues for the same endpoint or symptom. Supporting an
  existing PR beats writing a parallel one.
- **Back root-cause claims with a log.** Don't write "same bug as #X" or
  "caused by Y" in a comment unless a capture proves it. If you don't have
  one, say so and get it first.
- **Read the full issue thread before planning a fix.** A closed issue is
  often closed because the reporter confirmed a fix in the comments, and the
  data dump you're about to request may already be there.
- **Cross-repo references use the full form**
  `Hyundai-Kia-Connect/hyundai_kia_connect_api#N`. A bare `#N` resolves to the
  current repo only.

## Architecture

- `coordinator.py`: `HyundaiKiaConnectDataUpdateCoordinator` owns the
  `VehicleManager`, polling, and every vehicle command
  (`async_lock_vehicle`, `async_start_climate`, ...). Entities and services
  call the coordinator. They never call the library directly.
- `entity.py`: every entity subclasses `HyundaiKiaConnectEntity`, which
  supplies `device_info` and the coordinator link.
- Platforms (`sensor.py`, `binary_sensor.py`, `button.py`, `number.py`, ...)
  are description-driven. To add an entity, add an entry to the platform's
  `*_DESCRIPTIONS` tuple (e.g. `HyundaiKiaSensorEntityDescription`). Don't
  write a new entity class when a description will do.
- Gate entity creation with the description's `exists` callback. Some values
  are only `None` for a while (12V SoC, climate setpoint). Those entities are
  always created on purpose, so read the comments beside the existing
  descriptions before changing a creation check.
- Services are defined in `services.py` and `services.yaml`. Every
  user-visible string goes in `strings.json`. Any added, renamed or removed
  string key must be applied to **every** file in `translations/`, keeping
  the same key structure. Use an English placeholder where no translation is
  available.
- Redact personal data (VIN, location, tokens, account details) in
  diagnostics with `redact.py`.
- `except Exception` in setup and force-refresh paths is intentional
  (`BLE001` ignored). Don't narrow it as a drive-by change.
- Data not known is `unavailable`. Never show a placeholder, a last known
  value or a zero where the API returned nothing, and don't add options that
  mask unknown data as current. `RestoreEntity` is for restarting the host,
  not for masking stale runtime data.
- An `entity_category` or `device_class` change never fixes "where the entity
  shows". Before attempting a placement fix, verify the actual frontend code
  that selects the spot (e.g. `findBatteryEntity` for the device-page header);
  docs describe targeting and Lovelace, not device pages.
- Entity entries in `strings.json` and `translations/*.json` allow only
  `name` (+ `state`, `state_attributes`). `description` belongs on config-flow
  steps; hassfest rejects it on entities. Don't run formatters on these JSON
  files.
- When a third entity key must be created despite a `None` value, replace the
  `elif` creation cascade with a named frozenset of always-created keys, with
  one comment per key.

## Development

```bash
pip install homeassistant pytest pytest-asyncio "$(jq -r '.requirements[0]' custom_components/kia_uvo/manifest.json)"
pytest                                                    # tests/
mypy --strict --ignore-missing-imports custom_components/kia_uvo/
pre-commit run --all-files                                # ruff, ruff-format, codespell, prettier, ...
```

- CI also runs hassfest and HACS validation, so keep `manifest.json`,
  `services.yaml` and `strings.json` valid.
- Every fix or feature needs a test in `tests/` when it's practical.
- The whole package must stay `mypy --strict` clean.
- Never commit credentials or real vehicle data.
