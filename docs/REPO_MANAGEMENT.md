# Repository Management

This repository uses GitHub Flow for day-to-day development and semantic versioning for releases.

## Branch Strategy

- `main` is the only long-lived branch and should remain releasable.
- Create short-lived branches from `main` for all work.
- Use descriptive prefixes such as `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`, and `test/`.
- Merge through pull requests after required checks pass.

## Workflow Inventory

- `ci.yml`: full validation on pushes to `main` and manual runs
- `pr-checks.yml`: lightweight pull request validation with pytest
- `release.yml`: tag-driven release automation

## CI Expectations

The main CI workflow should continue to validate the project at three levels:

1. `pytest -q`
2. Offline governance benchmarks via `python -m eval.run_benchmarks --quiet`
3. Org scenario smoke via `python examples/org_scenario_tier3.py --users 10 --vector-latency-ms 0`

Pull requests run the lighter `pytest` check so contributors get faster feedback while `main` still receives the full validation path.

## Release Process

1. Update `pyproject.toml` to the target release version.
2. Add the matching version section to `CHANGELOG.md`.
3. Merge the release prep to `main`.
4. Create an annotated tag in the form `vX.Y.Z`.
5. Push the tag to GitHub.
6. `release.yml` verifies the tag matches `pyproject.toml`, extracts release notes from `CHANGELOG.md`, and creates the GitHub release.

## Ownership and Dependency Hygiene

- `CODEOWNERS` routes review responsibility to `@0sparsh2`.
- Dependabot is configured for GitHub Actions and Python dependencies on a weekly cadence.

## Recommended GitHub Settings

Apply these in the GitHub repository settings UI:

- Require pull requests before merging to `main`
- Require at least one approving review
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Require review from code owners
- Require conversation resolution before merging
- Enable Dependabot alerts, Dependabot security updates, secret scanning, and code scanning if available
