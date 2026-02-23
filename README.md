# Uthana Maya plugin

<img height="48" alt="image" src="https://github.com/user-attachments/assets/cc4391c2-fa9c-4ad3-95d4-292b512d9007" /> <img width="48" height="48" alt="image" src="https://github.com/user-attachments/assets/5d0c7249-a40e-4c64-ad13-bf03edff7382" />
<img width="48" height="48" alt="maya-logo" src="https://github.com/user-attachments/assets/42c9fd3a-aab2-43cf-afbf-41a11fff8684" />


---

Use Uthana's foundation models directly in Maya to generate, preview, and apply lifelike human motion without leaving your animation workflow.

Latest release: https://github.com/Uthana/uthana-maya-plugin/releases/latest (v1.0.0)

## Features

- **Text to motion**: Generate motion from a natural-language prompt
- **Video to motion**: Extract motion from a video file
- Browse and preview your Uthana motions directly in Maya
- Download motions to your scene and apply them to your characters via FBX

## Compatibility

- Maya 2023+ (Python 3.9+)
- Uthana account and API key (get it from https://uthana.com/app/account)
- Requires an active internet connection while using the plugin

## Installation

### Option A: Install from GitHub Releases (recommended)

1. Download the latest plugin zip: [uthana-maya-plugin.zip](https://github.com/Uthana/uthana-maya-plugin/releases/latest/download/uthana-maya-plugin.zip)
2. Extract the zip contents into your Maya plug-ins folder (e.g. `~/Documents/maya/<version>/plug-ins/`).
   - You should have `uthana_maya.py` and the `uthana/` directory at the root of the plug-ins folder.
3. In Maya: **Windows > Settings/Preferences > Plug-in Manager**
4. Find `uthana_maya.py` and check **Loaded** (and **Auto load** if desired).
5. A shelf button labeled "Uthana" will appear; click it to open the UI, or run `uthanaUI` in the MEL/Python command line.

### Option B: Build from source

```sh
git clone https://github.com/Uthana/uthana-maya-plugin.git
cd uthana-maya-plugin
poetry install --no-root
make build-zip
```

Then extract `dist/uthana-maya-plugin-<version>.zip` into your Maya plug-ins folder.

## Quick start

1. Load the plugin via Plug-in Manager (or run `uthanaUI` if auto-loaded).

2. In the Uthana panel, expand **Config** and paste your API key (use the default domain `uthana.com`).

3. Click the connection/test action in the UI to verify your API key is valid.

4. (Optional) Upload a character mesh. Uthana will automatically rig and retarget your characters to every motion you generate.

5. Generate a motion:
   - **Text to motion** — Write a prompt and generate a motion. For best results, describe a single motion and begin your prompt with "A person..."
   - **Video to motion** — Upload a video file of yourself or someone else performing a motion, then wait for processing (can take 60+ seconds).

6. Preview the motion in the viewer before downloading. When ready, use **Download and import** to add it to your scene via FBX.

## Contributing and development setup

This repository uses Poetry for dependency and tooling management. The virtual environment is configured at `.venv/`.

### Prerequisites

- Python 3.9+ (recommended to use [pyenv](https://github.com/pyenv/pyenv) for version management)
- Poetry (https://python-poetry.org/docs/#installation)

### Contributing

1. Create a branch for your change (`git checkout -b feature/my-feature`).
2. When you have tested your changes, run `make format`, `make lint`, and `make typecheck`.
3. Run `make precommit` to run the pre-commit hooks.
4. Open a pull request with a clear description explaining the changes, and include any test notes.
5. If you are fixing a bug from an existing GitHub issue, reference the issue in the pull request description.

### Code of conduct

1. We expect all contributors to follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) code of conduct. Please be respectful and considerate of others when contributing to this project.
2. Use of AI tools is allowed, but please be transparent about your use of AI tools in your pull request, and ensure that you have reviewed and understood the code you are contributing.

## Development setup

### Setup

```sh
poetry install --no-root
```

`--no-root` is intentional because this project is a Maya plugin, not a published Python package.

### Common commands

```sh
make lint
make format
make typecheck
make precommit-install
make precommit
make build-zip
make release-prepare VERSION=1.2.3
```

### Pre-commit hooks

Install hooks once per clone:

```sh
make precommit-install
```

Hooks run Ruff linting/formatting and basic file hygiene checks.

### CI build and release policy

`dist/` artifacts are generated in CI and are not committed to the repository.

- Pull requests and pushes to `main` run the **Build uthana-maya-plugin** workflow, which executes `make build-zip` and uploads the built zip as a workflow artifact.
- Tags matching `v*` run the **Release uthana-maya-plugin** workflow, which validates SemVer and version sync, builds the zip, and publishes it to a GitHub Release.
- Enable branch protection on `main` and require the **Build uthana-maya-plugin** check before merging.

### Versioning and release tags

Releases follow SemVer with optional RC prereleases:

- Stable: `vMAJOR.MINOR.PATCH` (example: `v1.2.3`)
- Prerelease: `vMAJOR.MINOR.PATCH-rc.N` (example: `v1.2.3-rc.0`)

`src/uthana_maya.py` (`_PLUGIN_VERSION`) and `pyproject.toml` store the base version only (`MAJOR.MINOR.PATCH`). The RC suffix lives in the Git tag.

Use this flow to create a release safely:

1. Ensure your worktree is clean and you are on the branch you want to release from.
2. Run:
   - Stable: `make release-prepare VERSION=1.2.3`
   - RC: `make release-prepare VERSION=1.2.3-rc.0`
3. Push commit and tag: `git push origin <branch> --follow-tags`

The helper script prevents tag reuse/clobber by checking existing local and remote tags before creating a new one.

### Format on save

If you are using VS Code or Cursor, the workspace settings in `.vscode/settings.json` automatically configure Ruff as the Python formatter and run lint fixes on save.

## Repository layout

- `src/`: Maya plugin source
  - `uthana_maya.py`: Plugin entry point (loaded by Plug-in Manager)
  - `uthana/`: Main package (core API client, UI, motion pipeline)
- `scripts/`: Build and helper scripts
- `dist/`: Generated release artifacts

## Troubleshooting

- **Plugin not visible in Plug-in Manager**: Ensure the plugin path is in Maya's plug-in path. The default is `~/Documents/maya/<version>/plug-ins/`.
- **Auth/API failures**: Verify API key and domain in the Config section.
- **Video or character uploads fail**: Confirm network access and supported file extensions.
- **FBX import/export issues**: Ensure the FBX plugin (`fbxmaya`) is available in your Maya installation.

## Documentation and project support

- API docs: https://uthana.com/docs/api
- Issues: use this repository's GitHub issue tracker
- Support: join the Uthana Discord: https://discord.gg/PbMzMPSyTG or email support (at) uthana.com

## License

Licensed under the Apache License 2.0. See `LICENSE`.
