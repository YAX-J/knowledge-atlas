# Contributing to Knowledge Atlas

Knowledge Atlas is currently a graduation project, but changes should remain reviewable and reproducible.

## Before starting

1. Read `AGENTS.md` and the relevant files under `docs/`.
2. Check `PLANS.md` for the active implementation phase.
3. Keep the change focused on one behavior or one documentation concern.
4. Create an ADR before implementing a material architecture change.

## Local frontend setup

```bash
cd frontend
npm install
npm run dev
```

Before submitting a frontend change:

```bash
npm run build
```

## Local backend setup

```bash
cd backend
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -e ".[dev]"
python -m pytest
```

Use Alembic for schema changes. Do not call `Base.metadata.create_all()` from application startup; it is reserved for isolated tests.

## Branch and commit conventions

Suggested branch names:

- `feat/<short-description>`
- `fix/<short-description>`
- `docs/<short-description>`
- `chore/<short-description>`

Use concise commit messages with an imperative summary. Conventional Commit prefixes are recommended but not required:

```text
feat: add evidence review endpoint
fix: keep timeline selection and detail panel in sync
docs: define temporal relationship direction
```

Do not combine generated files, dependency upgrades, broad formatting, and feature behavior in one commit unless they are inseparable.

## Pull requests

A pull request should explain:

- What changed and why.
- Which user flow or project phase it supports.
- How it was verified.
- Whether API, knowledge-model, architecture, or setup documents changed.
- Remaining limitations and follow-up work.

For visible UI work, include a current screenshot or short recording when practical.

## Code expectations

- Prefer small, typed components and explicit data structures.
- Keep Mock data separate from UI components.
- Preserve evidence and temporal semantics defined in the knowledge model.
- Add or update tests when a test harness exists.
- Keep API handlers thin and put persistence workflows in application services.
- Do not include credentials, private source code, or personal data.

## Documentation expectations

- Keep completed and planned functionality clearly separated.
- Update API examples when response shapes change.
- Record durable architecture decisions in `docs/adr/`.
- Add user-facing changes to the `Unreleased` section of `CHANGELOG.md`.

## Review checklist

- [ ] The change is within the current scope.
- [ ] Relevant build or tests pass.
- [ ] UI changes were checked at appropriate viewport sizes.
- [ ] Documentation matches the implementation.
- [ ] No generated output, secret, or unrelated file is included.
- [ ] `git diff --check` passes.
