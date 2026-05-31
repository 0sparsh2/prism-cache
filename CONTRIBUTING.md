# Contributing to PRISM-Cache

Thanks for contributing to PRISM-Cache. This repository uses GitHub Flow: `main` stays releasable, all work happens on short-lived branches, and every change lands through a pull request.

## Development Setup

1. Create a Python 3.12 virtual environment:
   ```bash
   python3.12 -m venv .venv
   ```
2. Install the package and development dependencies:
   ```bash
   .venv/bin/pip install -e ".[dev,gateway,redis,config]"
   ```
3. Copy `.env.example` to `.env` if you need live integrations. Never commit `.env`, API keys, or other secrets.

## Local Validation

Run the same checks contributors are expected to use before opening a PR:

```bash
make test
make eval
.venv/bin/python examples/org_scenario_tier3.py --users 10 --vector-latency-ms 0
```

Use the org scenario smoke check when you touch example flows, cache lifecycle behavior, evaluation code, or CI automation.

## Branching and GitHub Flow

- Branch from `main`
- Keep branches short-lived and focused
- Open a pull request early if you want feedback
- Merge to `main` only after required checks pass

Recommended branch prefixes:

- `feat/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`
- `chore/<short-name>`
- `refactor/<short-name>`
- `test/<short-name>`

## Pull Requests

Before opening a PR:

1. Rebase or merge from the latest `main` if needed.
2. Run the relevant local validation commands.
3. Update docs if behavior or workflows changed.
4. Update `CHANGELOG.md` when the change should be called out in a future release.
5. Fill out the PR template with a short summary and test plan.

PRs should stay reviewable, avoid unrelated cleanup, and must not include secrets, `.env`, generated credentials, or local editor state.

## Releases

PRISM-Cache follows semantic versioning:

- `MAJOR` for breaking changes
- `MINOR` for backward-compatible features
- `PATCH` for backward-compatible fixes and maintenance

Release checklist:

1. Update `pyproject.toml` with the release version.
2. Add the matching `CHANGELOG.md` section for that version.
3. Merge the release prep into `main`.
4. Create and push an annotated tag like `v0.6.3`.
5. GitHub Actions validates the tag against `pyproject.toml` and publishes the GitHub release from `CHANGELOG.md`.

## Repository Management

Repository workflow details live in [`docs/REPO_MANAGEMENT.md`](docs/REPO_MANAGEMENT.md), including:

- Branch strategy
- CI and PR checks
- Release automation
- Dependabot and CODEOWNERS expectations
- Recommended GitHub branch protection settings
